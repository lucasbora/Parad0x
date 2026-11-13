"""Simulated road network + phantom queue layers. OWNER: Rareș."""
from __future__ import annotations

from typing import Any

from app.engine.braess_detector import Scenario
from app.services import green_scorer, live_data
from app.services import seed_timisoara as seed
from app.services.layers.common import feature_collection


def roads_geojson(sim: Any, base: Scenario, scan: dict[str, dict], hotspots: list[dict]) -> dict[str, Any]:
    g = sim.g
    scores = green_scorer.score_links(g, base.result.z)
    hotspot_by_link = {h["linkId"]: h["id"] for h in hotspots}
    official = live_data.official_streets(g)
    feats = []
    for i, rl in enumerate(g.road_links):
        props = sim.link_props(base, i)
        ps = scan.get(rl.id)
        mid = [(rl.coords[0][0] + rl.coords[-1][0]) / 2, (rl.coords[0][1] + rl.coords[-1][1]) / 2]
        feats.append({
            "type": "Feature",
            "id": i,
            "geometry": {"type": "LineString", "coordinates": rl.coords},
            "properties": {
                "id": rl.id,
                "codGis": official.get(rl.id, {}).get("codGis", rl.cod_gis),
                "seedCodGis": rl.cod_gis,
                "codGisSource": "PMT Nomenclator (live)" if rl.id in official else "seed",
                "officialName": official.get(rl.id, {}).get("denumireCompleta"),
                "streetName": rl.street_name,
                "cartier": rl.cartier,
                "direction": rl.id[-2:],
                "twinId": rl.twin_id,
                "fromName": g.nodes[rl.from_node]["name"],
                "toName": g.nodes[rl.to_node]["name"],
                "lengthM": round(rl.length_m, 0),
                "freeFlowSpeedKmh": rl.speed_kmh,
                "lanes": rl.lanes,
                "baselineFlow": props["flow"],
                "capacity": props["capacity"],
                "vOverC": props["vOverC"],
                "speedKmh": props["speedKmh"],
                "travelTimeSec": props["travelTimeSec"],
                "bprDelaySec": props["bprDelaySec"],
                "braessValueV": round(ps["V"], 1) if ps else None,
                "braessImprovementPct": round(ps["I"], 2) if ps else None,
                "prescanMode": ps["mode"] if ps else None,
                "isBraessCandidate": bool(ps and ps["V"] < -0.5),
                "isGreenOpportunity": bool(ps and abs(ps["I"]) < 0.5),
                "greenSuitabilityScores": scores[rl.id],
                "recommendedReallocation": green_scorer.recommend_reallocation(scores[rl.id]),
                "timparkZone": rl.timpark_zone,
                "cyclewayExisting": rl.cycleway,
                "hotspotId": hotspot_by_link.get(rl.id),
                "stptLines": sorted(set(sim.lines_by_link.get(rl.id, []))),
                "sesizariSummary": seed.sesizari_for_point(mid[0], mid[1], 500),
            },
        })
    return feature_collection(feats)


def queue_point(g: Any, j: int) -> list[float]:
    """Marker position: slightly back along the approach so co-located queues don't overlap."""
    q = g.queue_links[j]
    node = g.nodes[q.node]["coordinates"]
    frm = g.link(q.in_link).coords[0]
    t = 0.16
    return [round(node[0] + (frm[0] - node[0]) * t, 6), round(node[1] + (frm[1] - node[1]) * t, 6)]


def queues_geojson(g: Any, base: Scenario) -> dict[str, Any]:
    feats = []
    for j, q in enumerate(g.queue_links):
        zq = float(base.result.z[g.n_road + j])
        s = float(base.params.s[j])
        feats.append({
            "type": "Feature",
            "id": j,
            "geometry": {"type": "Point", "coordinates": queue_point(g, j)},
            "properties": {
                "id": q.id,
                "intersectionName": g.nodes[q.node]["name"],
                "inLinkId": q.in_link,
                "outLinkId": q.out_link,
                "control": q.control,
                "flow": round(zq, 1),
                "saturationS": round(s, 1),
                "isSaturated": zq >= s,
                "queueDelaySec": round(float(base.result.phi[g.n_road + j]) * 60.0, 1),
                "d0Sec": round(q.d0_s(), 1),
            },
        })
    return feature_collection(feats)
