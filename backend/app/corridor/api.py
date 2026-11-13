"""/api/corridor — the single-corridor, data-backed simulator."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.corridor import calibration, config
from app.corridor.model import LaneChange, NeedsData, get_model
from app.corridor.osm_network import compass

router = APIRouter(prefix="/api/corridor", tags=["corridor"])


class Change(BaseModel):
    linkId: str
    carLanesAfter: int = Field(..., ge=0, le=6)
    use: Literal["bus", "bike", "sidewalk", "closed"]


class SimulateBody(BaseModel):
    changes: list[Change] = Field(..., min_length=1, max_length=12)
    demandScale: float = Field(1.0, ge=0.5, le=1.5)


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


def street_directions(net) -> dict[str, dict[str, list[str]]]:
    """street → {heading label: [link ids]}, split into the street's two travel directions.

    Curved streets get many compass bearings; we split relative to the street's longest
    segment (same way / opposite way) and label each side by its length-weighted mean bearing.
    """
    import math

    by_street: dict[str, list] = {}
    for l in net.links:
        if l.street == "(fără nume)" or not (net.nodes[l.from_node].inside and net.nodes[l.to_node].inside):
            continue
        by_street.setdefault(l.street, []).append(l)
    out: dict[str, dict[str, list[str]]] = {}
    for street, ls in by_street.items():
        ref = max(ls, key=lambda l: l.length_m).bearing
        groups: dict[bool, list] = {True: [], False: []}
        for l in ls:
            diff = abs((l.bearing - ref + 180) % 360 - 180)
            groups[diff < 90].append(l)
        dirs: dict[str, list[str]] = {}
        for g in groups.values():
            if not g:
                continue
            x = sum(l.length_m * math.sin(math.radians(l.bearing)) for l in g)
            y = sum(l.length_m * math.cos(math.radians(l.bearing)) for l in g)
            label = compass(math.degrees(math.atan2(x, y)) % 360)
            dirs.setdefault(label, []).extend(sorted(l.id for l in g))
        out[street] = dirs
    return out


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
                "signalAtEnd": bool(sig), "signalSource": sig[2] if sig else None,
                "fromName": net.nodes[l.from_node].name, "toName": net.nodes[l.to_node].name,
                "inside": net.nodes[l.from_node].inside or net.nodes[l.to_node].inside,
            },
        })
    gates = [{
        "type": "Feature", "geometry": {"type": "Point", "coordinates": [g.lng, g.lat]},
        "properties": {"id": g.id, "street": g.street, "side": g.side,
                       "needsIn": bool(g.in_link), "needsOut": bool(g.out_link),
                       "countedIn": g.id in m.fd.gate_in, "countedOut": g.id in m.fd.gate_out,
                       "inVehH": round(m.fd.gate_in.get(g.id, 0)), "outVehH": round(m.fd.gate_out.get(g.id, 0)),
                       "source": m.fd.gate_sources.get(g.id)},
    } for g in net.gates]
    junctions = [{
        "type": "Feature", "geometry": {"type": "Point", "coordinates": [n.lng, n.lat]},
        "properties": {"id": n.id, "name": n.name, "signalized": n.signalized},
    } for n in net.junctions]
    streets = street_directions(net)
    main_first = sorted(streets, key=lambda s: (s not in config.CORRIDOR.main_streets, s))
    return {
        "corridor": {"id": config.CORRIDOR.id, "name": config.CORRIDOR.name, "bbox": list(config.CORRIDOR.bbox),
                     "mainStreets": list(config.CORRIDOR.main_streets), "peak": config.CORRIDOR.peak_label},
        "links": {"type": "FeatureCollection", "features": links},
        "gates": {"type": "FeatureCollection", "features": gates},
        "junctions": {"type": "FeatureCollection", "features": junctions},
        "streets": [{"street": s, "directions": [{"heading": h, "linkIds": ids} for h, ids in sorted(streets[s].items())]}
                    for s in main_first],
        "dataStatus": m.status,
        "assumptions": m.assumptions_in_use(),
        "sources": {"network": net.source["osm"], "networkFetchedAt": net.source["fetchedAt"],
                    "stats": {"links": len(net.links), "junctions": len(net.junctions),
                              "signalized": sum(1 for n in net.junctions if n.signalized), "gates": len(net.gates)}},
    }


@router.post("/simulate")
def simulate(body: SimulateBody) -> dict[str, Any]:
    changes = _changes(body.changes)
    m = get_model()
    try:
        result = m.compare(changes, body.demandScale)
    except NeedsData as nd:
        return {"status": "needs_data", "dataStatus": nd.status}
    return {"status": "ok", **result, "warnings": m.status["warnings"]}


@router.post("/sensitivity")
def sensitivity(body: SimulateBody) -> dict[str, Any]:
    changes = _changes(body.changes)
    m = get_model()
    rows = []
    try:
        for s in (0.8, 1.0, 1.2):
            r = m.compare(changes, s)
            main = r["carRoutes"][0] if r["carRoutes"] else None
            bus = next((b for b in r["buses"] if b["usesChangedStreet"]), r["buses"][0] if r["buses"] else None)
            rows.append({"demandScale": s, "totalChangePct": r["totals"]["changePct"],
                         "mainRoute": main and {"name": f"{main['from']} → {main['to']}",
                                                "minutesBefore": main["minutesBefore"], "minutesAfter": main["minutesAfter"]},
                         "bus": bus and {"shortName": bus["shortName"], "minutesBefore": bus["minutesBefore"],
                                         "minutesAfter": bus["minutesAfter"]}})
    except NeedsData as nd:
        return {"status": "needs_data", "dataStatus": nd.status}
    return {"status": "ok", "rows": rows}


@router.get("/calibration")
def calibration_endpoint() -> dict[str, Any]:
    m = get_model()
    try:
        return {"status": "ok", **calibration.calibration_report(m)}
    except NeedsData as nd:
        return {"status": "needs_data", "dataStatus": nd.status}
