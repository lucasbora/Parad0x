"""Featured Braess hotspots.

OWNER: Rareș. Hotspots are LOCATIONS (anchor coordinates + street name); the road link is
resolved at runtime by app.seed.hotspots.resolve_hotspots(), so they survive a network swap.
``linkId``/``queueId`` are only hints for the current seed network.
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Featured hotspots (§5). Target figures in CLAUDE.md are design goals; the
# figures the API returns are always computed live by the solver.
# ---------------------------------------------------------------------------

HOTSPOTS: list[dict[str, Any]] = [
    {
        "id": "HOTSPOT_CLUJ_EROILOR",
        "rank": 1,
        "linkId": "LINK_CLUJ_01",
        "anchor": {"from": [21.2368, 45.741], "to": [21.233, 45.7478]},
        "codGis": "1042",
        "name": "Str. Cluj / Bd. Eroilor de la Tisa",
        "streetHint": "cluj",
        "cartier": "Complexul Studențesc / Elisabetin",
        "baselineLanes": ["car", "car", "parking_blue"],
        "suggestedLanes": ["car", "bus", "bike"],
        "queueId": "Q_BRATIANU_SHARED",
        "stptLines": ["15", "16", "M11"],
        "bikeCorridor": "BIKE_CLUJ_JUSTITIEI",
        "dataBadge": "FIWARE Traffic Sensor · Cluj/Eroilor · Jul 2026",
        "center": [21.2349, 45.7444],
        "zoom": 15.2,
        "story_ro": "Traficul de scurtătură dinspre Calea Martirilor inundă Str. Cluj și saturează coada de la Podul Eroilor.",
        "story_en": "Selfish cut-through traffic from Calea Martirilor floods Str. Cluj and saturates the Podul Eroilor queue.",
    },
    {
        "id": "HOTSPOT_FERDINAND_CATEDRALA",
        "rank": 2,
        "linkId": "LINK_FERDINAND_01",
        "anchor": {"from": [21.2243, 45.7508], "to": [21.2318, 45.753]},
        "codGis": "0218",
        "name": "Bd. Regele Ferdinand I",
        "streetHint": "ferdinand",
        "cartier": "Cetate",
        "baselineLanes": ["car", "car"],
        "suggestedLanes": ["car", "bus"],
        "queueId": "Q_3AUG_SHARED",
        "stptLines": ["E1", "E2", "33", "1", "2"],
        "bikeCorridor": "BIKE_CATEDRALA_TRAIAN",
        "dataBadge": "PMT Nomenclator Străzi · codGis #0218",
        "center": [21.2282, 45.7520],
        "zoom": 15.4,
        "story_ro": "Bulevardul din fața Catedralei servește drept scurtătură între Iosefin și Fabric.",
        "story_en": "The boulevard in front of the Cathedral acts as a shortcut between Iosefin and Fabric.",
    },
    {
        "id": "HOTSPOT_CIRCUMVALATIUNII",
        "rank": 3,
        "linkId": "LINK_CIRCUMVALATIUNII_01",
        "anchor": {"from": [21.2172, 45.768], "to": [21.2118, 45.7635]},
        "codGis": "0389",
        "name": "Calea Circumvalațiunii / Str. Gheorghe Lazăr",
        "streetHint": "circumvala",
        "cartier": "Circumvalațiunii",
        "baselineLanes": ["car", "car", "car"],
        "suggestedLanes": ["car", "car", "bike"],
        "queueId": "Q_LAZARE_SHARED",
        "stptLines": ["14", "40"],
        "bikeCorridor": "BIKE_DACIA_UNIRII",
        "dataBadge": "PMT Nomenclator Străzi · codGis #0389",
        "center": [21.2150, 45.7650],
        "zoom": 15.0,
        "story_ro": "Coada de la intersecția cu Str. Gh. Lazăr se formează din traficul de tranzit pe Circumvalațiunii.",
        "story_en": "The merge queue at Str. Gh. Lazăr is fed by through-traffic on Circumvalațiunii.",
    },
    {
        "id": "HOTSPOT_SESIZARI_IOSEFIN",
        "rank": 4,
        "linkId": "LINK_16DEC_01",
        "anchor": {"from": [21.21, 45.7476], "to": [21.2172, 45.7497]},
        "codGis": "0815",
        "name": "Bd. 16 Decembrie 1989 / Piața Iosefin",
        "streetHint": "16 decembrie",
        "cartier": "Iosefin",
        "baselineLanes": ["car", "car", "parking_red"],
        "suggestedLanes": ["car", "bus", "pedestrian_trees"],
        "queueId": "Q_CAROL_SHARED",
        "stptLines": ["E2", "33", "2"],
        "bikeCorridor": "BIKE_GARA_CATEDRALA",
        "dataBadge": "Sesizări API · Anonimizat GDPR · 19 rapoarte",
        "center": [21.2136, 45.7487],
        "zoom": 15.3,
        "story_ro": "Validat de 19 sesizări anonimizate: amestecul tramvai/autobuz/auto blochează Piața Maria.",
        "story_en": "Validated by 19 anonymised citizen reports: tram/bus/car mixing blocks Piața Maria.",
    },
]


# ---------------------------------------------------------------------------
# Runtime resolution: hotspot location → link of whatever network is loaded
# ---------------------------------------------------------------------------

def _dist_m(a: list[float], b: list[float]) -> float:
    import math

    kx = 111_320 * math.cos(math.radians(a[1]))
    return math.hypot((a[0] - b[0]) * kx, (a[1] - b[1]) * 110_540)


def resolve_link_id(graph: Any, hotspot: dict[str, Any], max_error_m: float = 250.0) -> str | None:
    """Find the directed link matching a hotspot's anchor (from → to) in ``graph``.

    The ``linkId`` hint is used when it exists and still matches the anchor; otherwise the
    link minimising the endpoint distance (same direction) is chosen, preferring links
    whose street name matches. Returns None if nothing is within ``max_error_m``.
    """
    a_from, a_to = hotspot["anchor"]["from"], hotspot["anchor"]["to"]

    def err(rl) -> float:
        return _dist_m(rl.coords[0], a_from) + _dist_m(rl.coords[-1], a_to)

    hint = hotspot.get("linkId")
    if hint in graph.road_index and err(graph.link(hint)) <= max_error_m:
        return hint
    want = hotspot.get("streetHint", "").lower()
    best = None
    for rl in graph.road_links:
        e = err(rl) - (100.0 if want and want in rl.street_name.lower() else 0.0)
        if best is None or e < best[0]:
            best = (e, rl.id)
    if best and best[0] <= max_error_m:
        return best[1]
    return _resolve_along_route(graph, hotspot, want)


def _resolve_along_route(graph: Any, hotspot: dict[str, Any], want: str) -> str | None:
    """Fine-grained networks (OSM): a hotspot street spans several links (one per block).

    Route from the node nearest the anchor ``from`` to the node nearest ``to`` by free-flow time
    and return the longest link on that route whose street name matches ``streetHint``
    (the longest link of the route if none matches).
    """
    import networkx as nx

    a_from, a_to = hotspot["anchor"]["from"], hotspot["anchor"]["to"]
    src, dst = graph.snap_to_node(*a_from), graph.snap_to_node(*a_to)
    if src == dst:
        return None
    g = getattr(graph, "_hotspot_digraph", None)
    if g is None:
        g = graph.road_digraph()
        graph._hotspot_digraph = g
    try:
        nodes = nx.shortest_path(g, src, dst, weight="t0")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None
    route = [graph.road_links[g[u][v]["idx"]] for u, v in zip(nodes[:-1], nodes[1:])]
    named = [rl for rl in route if want and want in rl.street_name.lower()]
    if named:
        return max(named, key=lambda rl: rl.length_m).id
    if want:
        # anchor is approximate: nearest same-named link around the anchor, aligned with from → to
        mid = [(a_from[0] + a_to[0]) / 2, (a_from[1] + a_to[1]) / 2]
        ax, ay = a_to[0] - a_from[0], a_to[1] - a_from[1]
        cands = []
        for rl in graph.road_links:
            if want not in rl.street_name.lower():
                continue
            lx, ly = rl.coords[-1][0] - rl.coords[0][0], rl.coords[-1][1] - rl.coords[0][1]
            if lx * ax + ly * ay <= 0:
                continue
            c = [(rl.coords[0][0] + rl.coords[-1][0]) / 2, (rl.coords[0][1] + rl.coords[-1][1]) / 2]
            d = _dist_m(c, mid)
            if d <= 1000.0:
                cands.append((d - 0.2 * rl.length_m, rl.id))
        if cands:
            return min(cands)[1]
        return None   # the named street does not run this way on this network: drop, don't guess
    return max(route, key=lambda rl: rl.length_m).id


def resolve_hotspots(graph: Any) -> list[dict[str, Any]]:
    """Hotspots with ``linkId``/``queueId`` valid for ``graph`` (unresolvable ones are dropped)."""
    out = []
    for h in HOTSPOTS:
        lid = resolve_link_id(graph, h)
        if lid is None:
            continue
        q = h.get("queueId")
        out.append({**h, "linkId": lid, "queueId": q if q in graph.queue_index else None})
    return out
