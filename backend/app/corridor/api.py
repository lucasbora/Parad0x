"""/api/corridor — the single-corridor, data-backed simulator.

Every endpoint takes ``profile`` (morning | day | evening; default morning).
Demand is estimated from OpenStreetMap land use and calibrated by field counts when present,
so results are always available; ``demandSource`` says which one you are looking at.
``testData`` is still accepted for older clients and ignored.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import difflib

from app.corridor import calibration, config, survey
from app.corridor.config import DEFAULT_PROFILE, LANDUSE, PROFILES
from app.corridor.model import LaneChange, NeedsData, get_model
from app.corridor.osm_network import compass, street_directions

router = APIRouter(prefix="/api/corridor", tags=["corridor"])

ProfileQ = Literal["morning", "day", "evening"]


class Change(BaseModel):
    linkId: str
    carLanesAfter: int = Field(..., ge=0, le=6)
    use: Literal["bus", "bike", "sidewalk", "closed"]


class SimulateBody(BaseModel):
    changes: list[Change] = Field(..., min_length=1, max_length=40)
    demandScale: float = Field(1.0, ge=0.5, le=1.5)
    profile: ProfileQ = DEFAULT_PROFILE
    testData: bool = False     # deprecated: estimated land-use demand replaces test mode
    evaporation: float = Field(0.0, ge=0.0, le=0.3)   # share of the changed street's drivers who leave the car


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
        "landUse": {**m.landuse.summary, "carShare": LANDUSE["car_share"], "carShareVerified": LANDUSE["car_share_verified"],
                    "carShareSource": LANDUSE["car_share_source"], "carOccupancy": LANDUSE["car_occupancy"],
                    "carOccupancySource": LANDUSE["car_occupancy_source"]},
        "tripCosts": _trip_costs(),
        "evaporation": config.EVAPORATION,
        "dataStatus": m.status,
        "assumptions": m.assumptions_in_use(),
        "sources": {"network": net.source["osm"], "networkFetchedAt": net.source["fetchedAt"],
                    "stats": {"links": len(net.links), "junctions": len(net.junctions),
                              "signalized": sum(1 for n in net.junctions if n.signalized), "gates": len(net.gates),
                              "sideStreetLinks": sum(1 for l in net.links if l.highway in config.SIDE_STREET_CLASSES),
                              "zones": len(m.landuse.zones)},
                    "turns": {**m.turn_stats, "bannedMovements": m.solver_net.n_banned,
                              "allowedMovements": len(m.solver_net.movements)}},
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
    result = m.compare(changes, round(body.demandScale, 2), profile=body.profile, evaporation=body.evaporation)
    return {"status": "ok", **result, "warnings": m.status["warnings"]}


@router.post("/breakeven")
def breakeven(body: SimulateBody) -> dict[str, Any]:
    """Drivers who must switch mode for a lane removal to cost cars nothing (several solves)."""
    changes = _changes(body.changes)
    if not changes:
        raise HTTPException(400, "no changes")
    try:
        return {"status": "ok", **get_model().break_even(changes, profile=body.profile, scale=round(body.demandScale, 2))}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/package")
def package_endpoint(profile: ProfileQ = Query(DEFAULT_PROFILE)) -> dict[str, Any]:
    """Greedy filter package from the Braess search, plus a bus lane on top if the total stays lower."""
    from app.corridor import package
    return {"status": "ok", **package.best_package(get_model(), profile)}


@router.post("/allday")
def allday_endpoint(body: SimulateBody) -> dict[str, Any]:
    """The same changes in every time window (total time change per profile)."""
    from app.corridor import package
    return {"status": "ok", "profiles": package.all_day(get_model(), _changes(body.changes), body.evaporation)}


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
def baseline(profile: ProfileQ = Query(DEFAULT_PROFILE), demandScale: float = Query(1.0, ge=0.5, le=1.5),
             testData: bool = False) -> dict[str, Any]:
    return {"status": "ok", **get_model().baseline(profile=profile, scale=round(demandScale, 2))}


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


def _match_street(answer: str, names: list[str]) -> str | None:
    """Network street for a free-text answer: exact, substring (≥ 5 chars), else close spelling."""
    def key(x: str) -> str:
        k = survey.norm(x)
        return k[len("strada "):] if k.startswith("strada ") else k
    a = key(answer)
    if not a:
        return None
    keyed = {key(n): n for n in names}
    if a in keyed:
        return keyed[a]
    if len(a) >= 5:
        for k, n in keyed.items():
            if a in k or (len(k) >= 5 and k in a):
                return n
    best = max(keyed, key=lambda k: difflib.SequenceMatcher(None, a, k).ratio(), default=None)
    if best and difflib.SequenceMatcher(None, a, best).ratio() >= 0.88:
        return keyed[best]
    return None


def _trip_costs() -> dict[str, Any]:
    """Bus ticket (SMTT wallet API) vs paid street parking in the zone (Timpark API). Live data only:
    if either API is down and only the seed fallback exists, that part is left out."""
    from collections import Counter

    from app.services import pmt_client

    out: dict[str, Any] = {}
    try:
        types, prov = pmt_client.get_wallet_types()
        if prov.source != "seed":
            by_id = {t.get("id"): t for t in types if isinstance(t, dict)}
            single, day = by_id.get("transit-single"), by_id.get("transit-day")
            if single:
                out["ticket"] = {"lei": single.get("priceLei"), "minutes": 60, "dayPassLei": (day or {}).get("priceLei"),
                                 "source": "SMTT wallet API (cont.primariatm.ro)", "fetchedAt": prov.fetched_at}
        park, prov = pmt_client.get_parking()
        if prov.source != "seed" and park.get("features"):
            la0, lo0, la1, lo1 = config.CORRIDOR.bbox
            zones = Counter(f.get("tariff") for f in park["features"] if f.get("kind") == "street" and any(
                lo0 <= c[0] <= lo1 and la0 <= c[1] <= la1 for c in f.get("coordinates") or []))
            hourly = (park.get("tariffs") or {}).get("hourly") or {}
            out["parking"] = {"streetSegmentsByTariff": dict(zones.most_common()),
                              "eurPerHour": {k: v.get("eur") for k, v in hourly.items() if isinstance(v, dict)},
                              "schedule": (park.get("tariffs") or {}).get("schedule"),
                              "source": "Timpark API (cont.primariatm.ro)", "fetchedAt": prov.fetched_at}
    except Exception:  # noqa: BLE001 — context only, never break /api/corridor
        pass
    return out


@router.get("/survey")
def survey_endpoint() -> dict[str, Any]:
    """Citizen survey summary (anonymous) and which answers feed the model."""
    s = config.SURVEY
    if not s:
        return {"status": "no_data"}
    names = sorted({l.street for l in get_model().net.links})
    mentioned = s["routeChoice"]["avoidStreetsMentioned"]
    return {
        "status": "ok", **s,
        "avoidStreetsInModel": [{**x, "streetInModel": _match_street(x["answer"], names)} for x in mentioned],
        "usedInModel": {k: {"value": LANDUSE[k], "default": LANDUSE[f"{k}_default"], "source": LANDUSE[f"{k}_source"]}
                        for k in ("car_share", "car_occupancy")},
        "surveyEnabled": survey.enabled(),
        "minResponses": survey.MIN_RESPONSES,
    }
