"""/api/corridor — the single-corridor, data-backed simulator.

Every endpoint takes ``profile`` (morning | day | evening | sunday; default morning).
Demand is estimated from OpenStreetMap land use and calibrated by field counts when present,
so results are always available; ``demandSource`` says which one you are looking at.
``testData`` is still accepted for older clients and ignored.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.corridor import calibration, config
from app.corridor.config import DEFAULT_PROFILE, LANDUSE, PROFILES
from app.corridor.model import LaneChange, NeedsData, get_model
from app.corridor.osm_network import compass, street_directions

router = APIRouter(prefix="/api/corridor", tags=["corridor"])

ProfileQ = Literal["morning", "day", "evening", "sunday"]


class Change(BaseModel):
    linkId: str
    carLanesAfter: int = Field(..., ge=0, le=6)
    use: Literal["bus", "bike", "sidewalk", "closed"]


class SimulateBody(BaseModel):
    changes: list[Change] = Field(..., min_length=1, max_length=40)
    demandScale: float = Field(1.0, ge=0.5, le=1.5)
    profile: ProfileQ = DEFAULT_PROFILE
    testData: bool = False     # deprecated: estimated land-use demand replaces test mode


def _changes(body_changes: list[Change]) -> list[LaneChange]:
    m = get_model()
    out = []
    for c in body_changes:
        if c.linkId not in m.net.link_index:
            raise HTTPException(404, f"unknown linkId {c.linkId}")
        current, _ = m.car_lanes(c.linkId)
        if c.carLanesAfter > current:
            raise HTTPException(422, f"{c.linkId}: carLanesAfter ({c.carLanesAfter}) exceeds current lanes ({current})")
        out.append(LaneChange(c.linkId, c.carLanesAfter, "closed" if c.carLanesAfter == 0 else c.use))
    return out


def _profiles_meta() -> list[dict[str, Any]]:
    return [{"id": p.id, "labelRo": p.label_ro, "labelEn": p.label_en, "start": p.start, "end": p.end, "day": p.day}
            for p in PROFILES.values()]


@router.get("")
def corridor() -> dict[str, Any]:
    m = get_model()
    net = m.net
    heading_of = {lid: h for dirs in street_directions(net).values() for h, ids in dirs.items() for lid in ids}
    links = []
    for l in net.links:
        lanes, lanes_src = m.car_lanes(l.id)
        sig = m.signal(l.id)
        links.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": l.geometry},
            "properties": {
                "id": l.id, "street": l.street, "heading": heading_of.get(l.id, compass(l.bearing)), "lengthM": round(l.length_m),
                "carLanes": lanes, "lanesSource": lanes_src, "speedKmh": l.speed_kmh, "speedSource": l.speed_source,
                "busLane": l.bus_lane, "isMainStreet": l.street in config.CORRIDOR.main_streets,
                "roadClass": l.highway, "isSideStreet": l.highway in config.SIDE_STREET_CLASSES,
                "signalAtEnd": bool(sig), "signalSource": sig[2] if sig else None,
                "fromName": net.nodes[l.from_node].name, "toName": net.nodes[l.to_node].name,
                "inside": net.nodes[l.from_node].inside or net.nodes[l.to_node].inside,
            },
        })

    def counted(store: dict[str, dict[str, float]], gid: str) -> list[str]:
        return [p for p, gates in store.items() if gid in gates]

    gates = []
    for g in net.gates:
        cin, cout = counted(m.fd.gate_in, g.id), counted(m.fd.gate_out, g.id)
        gates.append({
            "type": "Feature", "geometry": {"type": "Point", "coordinates": [g.lng, g.lat]},
            "properties": {"id": g.id, "street": g.street, "side": g.side,
                           "needsIn": bool(g.in_link), "needsOut": bool(g.out_link),
                           "countedIn": bool(cin), "countedOut": bool(cout),
                           "countedProfiles": sorted(set(cin) | set(cout)),
                           "inVehH": round(m.fd.gate_in.get(DEFAULT_PROFILE, {}).get(g.id, 0)),
                           "outVehH": round(m.fd.gate_out.get(DEFAULT_PROFILE, {}).get(g.id, 0)),
                           "source": m.fd.gate_sources.get(g.id)},
        })
    junctions = [{
        "type": "Feature", "geometry": {"type": "Point", "coordinates": [n.lng, n.lat]},
        "properties": {"id": n.id, "name": n.name, "signalized": n.signalized},
    } for n in net.junctions]
    zones = [{
        "type": "Feature", "geometry": {"type": "Point", "coordinates": [z.lng, z.lat]},
        "properties": {"id": z.id, "label": z.label, "residents": round(z.residents),
                       "activity": {k: round(v, 1) for k, v in z.activity.items()}},
    } for z in m.landuse.zones]
    streets = street_directions(net)
    main_first = sorted(streets, key=lambda s: (s not in config.CORRIDOR.main_streets, s))
    return {
        "corridor": {"id": config.CORRIDOR.id, "name": config.CORRIDOR.name, "bbox": list(config.CORRIDOR.bbox),
                     "mainStreets": list(config.CORRIDOR.main_streets), "peak": config.CORRIDOR.peak_label},
        "profiles": _profiles_meta(),
        "defaultProfile": DEFAULT_PROFILE,
        "links": {"type": "FeatureCollection", "features": links},
        "gates": {"type": "FeatureCollection", "features": gates},
        "junctions": {"type": "FeatureCollection", "features": junctions},
        "zones": {"type": "FeatureCollection", "features": zones},
        "streets": [{"street": s, "directions": [{"heading": h, "linkIds": ids} for h, ids in sorted(streets[s].items())]}
                    for s in main_first],
        "landUse": {**m.landuse.summary, "carShare": LANDUSE["car_share"], "carShareVerified": LANDUSE["car_share_verified"]},
        "dataStatus": m.status,
        "assumptions": m.assumptions_in_use(),
        "sources": {"network": net.source["osm"], "networkFetchedAt": net.source["fetchedAt"],
                    "stats": {"links": len(net.links), "junctions": len(net.junctions),
                              "signalized": sum(1 for n in net.junctions if n.signalized), "gates": len(net.gates),
                              "sideStreetLinks": sum(1 for l in net.links if l.highway in config.SIDE_STREET_CLASSES),
                              "zones": len(m.landuse.zones)}},
    }


@router.get("/demand")
def demand(profile: ProfileQ = Query(DEFAULT_PROFILE)) -> dict[str, Any]:
    """The OD table behind a profile: where trips start and end (veh/h)."""
    m = get_model()
    od = m.od_table(profile)
    pairs = sorted(((float(od.trips[i, j]), r, c) for i, r in enumerate(od.rows) for j, c in enumerate(od.cols)
                    if od.trips[i, j] > 0.5), key=lambda t: -t[0])
    return {"profile": profile, "demandSource": m.demand_source(profile), "summary": od.summary,
            "topPairs": [{"from": r.label, "to": c.label, "fromKind": r.kind, "toKind": c.kind, "vehH": round(q, 1)}
                         for q, r, c in pairs[:25]]}


@router.post("/simulate")
def simulate(body: SimulateBody) -> dict[str, Any]:
    changes = _changes(body.changes)
    m = get_model()
    result = m.compare(changes, body.demandScale, profile=body.profile)
    return {"status": "ok", **result, "warnings": m.status["warnings"]}


@router.post("/sensitivity")
def sensitivity(body: SimulateBody) -> dict[str, Any]:
    changes = _changes(body.changes)
    m = get_model()
    rows = []
    for s in (0.8, 1.0, 1.2):
        r = m.compare(changes, s, profile=body.profile)
        main = r["carRoutes"][0] if r["carRoutes"] else None
        bus = next((b for b in r["buses"] if b["usesChangedStreet"]), r["buses"][0] if r["buses"] else None)
        rows.append({"demandScale": s, "totalChangePct": r["totals"]["changePct"],
                     "braess": r["braess"]["detected"],
                     "mainRoute": main and {"name": f"{main['from']} → {main['to']}",
                                            "minutesBefore": main["minutesBefore"], "minutesAfter": main["minutesAfter"]},
                     "bus": bus and {"shortName": bus["shortName"], "minutesBefore": bus["minutesBefore"],
                                     "minutesAfter": bus["minutesAfter"]}})
    return {"status": "ok", "profile": body.profile, "demandSource": m.demand_source(body.profile), "rows": rows}


@router.get("/baseline")
def baseline(profile: ProfileQ = Query(DEFAULT_PROFILE), testData: bool = False) -> dict[str, Any]:
    return {"status": "ok", **get_model().baseline(profile=profile)}


@router.get("/scan")
def scan(profile: ProfileQ = Query(DEFAULT_PROFILE), testData: bool = False) -> dict[str, Any]:
    """Braess search: close every busy street segment (both ways) and take a lane from every
    multi-lane street, re-solving the equilibrium each time. Cached per profile."""
    return {"status": "ok", **get_model().scan(profile=profile)}


@router.get("/calibration")
def calibration_endpoint(profile: ProfileQ = Query(DEFAULT_PROFILE)) -> dict[str, Any]:
    m = get_model()
    try:
        return {"status": "ok", **calibration.calibration_report(m, profile=profile)}
    except NeedsData as nd:
        return {"status": "needs_data", "dataStatus": nd.status}
