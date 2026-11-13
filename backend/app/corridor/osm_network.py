"""Build the corridor road network from the committed OpenStreetMap snapshot.

Junctions are real OSM nodes shared by several roads. Each road piece between two
junctions becomes one directed link per allowed direction. Every link records where its
lane count and speed came from ("osm" or "assumed"), so the UI can show which numbers
still need checking on the ground. Links that cross the corridor boundary end in a GATE:
the places where traffic must be counted for the model to have real demand.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.corridor.config import ASSUMPTIONS, CORRIDOR, OSM_SNAPSHOT


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lng1, lat1 = map(math.radians, a)
    lng2, lat2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def bearing_deg(a: tuple[float, float], b: tuple[float, float]) -> float:
    lng1, lat1, lng2, lat2 = map(math.radians, (*a, *b))
    y = math.sin(lng2 - lng1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lng2 - lng1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def compass(deg: float) -> str:
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int(((deg + 22.5) % 360) // 45)]


@dataclass
class Link:
    id: str
    from_node: str
    to_node: str
    street: str
    highway: str
    length_m: float
    speed_kmh: float
    car_lanes: int
    bus_lane: bool
    geometry: list[list[float]]
    lanes_source: str           # "osm" | "osm (split assumed)" | "assumed"
    speed_source: str           # "osm" | "assumed (RO:urban 50)"
    osm_way_ids: list[int] = field(default_factory=list)

    @property
    def t0_min(self) -> float:
        return self.length_m / 1000.0 / self.speed_kmh * 60.0

    @property
    def bearing(self) -> float:
        return bearing_deg(tuple(self.geometry[0]), tuple(self.geometry[-1]))


@dataclass
class Node:
    id: str
    lng: float
    lat: float
    inside: bool
    signalized: bool = False
    streets: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        names = [s for s in dict.fromkeys(self.streets) if s and s != "(fără nume)"]
        return " / ".join(names[:2]) if names else f"Nod {self.id}"


@dataclass
class Gate:
    id: str
    node: str                    # outside terminal node
    street: str
    side: str                    # N/S/E/W edge of the corridor box
    in_link: str | None          # link that brings traffic INTO the area
    out_link: str | None         # link that takes traffic OUT of the area
    lng: float
    lat: float


@dataclass
class CorridorNetwork:
    nodes: dict[str, Node]
    links: list[Link]
    gates: list[Gate]
    source: dict[str, Any]
    link_index: dict[str, int] = field(default_factory=dict)

    def link(self, link_id: str) -> Link:
        return self.links[self.link_index[link_id]]

    @property
    def junctions(self) -> list[Node]:
        """Inside nodes where ≥3 links meet — the intersections that can be counted."""
        deg: dict[str, set] = {}
        for l in self.links:
            deg.setdefault(l.from_node, set()).add(l.to_node)
            deg.setdefault(l.to_node, set()).add(l.from_node)
        return [n for n in self.nodes.values() if n.inside and len(deg.get(n.id, ())) >= 3]

    def streets(self) -> list[str]:
        return sorted({l.street for l in self.links if l.street != "(fără nume)"})


# ---------------------------------------------------------------------------

def _lanes(tags: dict[str, str], oneway: int) -> tuple[int, int, str]:
    """(forward, backward, source). oneway: 1 forward-only, -1 backward-only, 0 two-way."""
    def num(key):
        m = re.match(r"\d+", tags.get(key, ""))
        return int(m.group()) if m else None

    total, fwd, bwd = num("lanes"), num("lanes:forward"), num("lanes:backward")
    if oneway != 0:
        n = total if total else 1
        return (n, 0, "osm" if total else "assumed") if oneway == 1 else (0, n, "osm" if total else "assumed")
    if fwd and bwd:
        return fwd, bwd, "osm"
    if total:
        f = max(1, total // 2)
        return f, max(1, total - f), "osm" if total % 2 == 0 else "osm (split assumed)"
    return 1, 1, "assumed"


def _speed(tags: dict[str, str]) -> tuple[float, str]:
    m = re.match(r"\d+", tags.get("maxspeed", ""))
    if m:
        return float(m.group()), "osm"
    return ASSUMPTIONS["default_speed_kmh"], "assumed (RO:urban 50)"


def _oneway(tags: dict[str, str]) -> int:
    ow = tags.get("oneway", "no")
    if ow in ("yes", "1", "true"):
        return 1
    if ow == "-1":
        return -1
    if tags.get("junction") == "roundabout":
        return 1
    return 0


def _bus_lane(tags: dict[str, str]) -> bool:
    return any("designated" in tags.get(k, "") for k in ("bus:lanes", "lanes:bus", "busway", "psv:lanes")) \
        or tags.get("busway") in ("lane", "opposite_lane")


@lru_cache(maxsize=1)
def load_network() -> CorridorNetwork:
    raw = json.loads(OSM_SNAPSHOT.read_text(encoding="utf-8"))
    s, w, n, e = CORRIDOR.bbox

    def inside(lng: float, lat: float) -> bool:
        return s <= lat <= n and w <= lng <= e

    coords: dict[int, tuple[float, float]] = {}
    ways = []
    signals: list[tuple[float, float]] = []
    for el in raw["elements"]:
        if el["type"] == "way" and el.get("tags", {}).get("highway") in CORRIDOR.highways:
            for nid, g in zip(el["nodes"], el["geometry"]):
                coords[nid] = (g["lon"], g["lat"])
            ways.append(el)
        elif el["type"] == "node" and el.get("tags", {}).get("highway") == "traffic_signals":
            signals.append((el["lon"], el["lat"]))

    # 1. keep node pairs with at least one end inside the corridor box
    pairs = []          # (a, b, way)
    for wy in ways:
        nds = wy["nodes"]
        for a, b in zip(nds[:-1], nds[1:]):
            if inside(*coords[a]) or inside(*coords[b]):
                pairs.append((a, b, wy))
    adj: dict[int, list[int]] = {}
    for idx, (a, b, _) in enumerate(pairs):
        adj.setdefault(a, []).append(idx)
        adj.setdefault(b, []).append(idx)

    def sig(wy) -> tuple:
        t = wy["tags"]
        return (t.get("name", ""), t.get("highway"), _lanes(t, 0)[:2] if _oneway(t) == 0 else (t.get("lanes"),),
                t.get("maxspeed"), _oneway(t) != 0, _bus_lane(t))

    def is_key(nid: int) -> bool:
        inc = adj[nid]
        if len(inc) != 2 or not inside(*coords[nid]):
            return True
        return sig(pairs[inc[0]][2]) != sig(pairs[inc[1]][2])

    # 2. walk chains between key nodes
    used = [False] * len(pairs)
    raw_links: list[dict] = []
    for start, inc in adj.items():
        if not is_key(start):
            continue
        for pidx in inc:
            if used[pidx]:
                continue
            chain_nodes = [start]
            fwd_ok = bwd_ok = True
            wy_ids = []
            cur, p = start, pidx
            while True:
                used[p] = True
                a, b, wy = pairs[p]
                nxt = b if cur == a else a
                ow = _oneway(wy["tags"])
                along = (cur == a)            # walking in the way's node order?
                if ow == 1:
                    fwd_ok &= along
                    bwd_ok &= not along
                elif ow == -1:
                    fwd_ok &= not along
                    bwd_ok &= along
                wy_ids.append(wy["id"])
                chain_nodes.append(nxt)
                cur = nxt
                if is_key(cur):
                    break
                p = next(q for q in adj[cur] if q != p)
                if used[p]:
                    break
            tags = pairs[pidx][2]["tags"]
            raw_links.append({"nodes": chain_nodes, "fwd": fwd_ok, "bwd": bwd_ok, "tags": tags,
                              "ways": sorted(set(wy_ids))})

    # 3. directed links
    nodes: dict[str, Node] = {}

    def node(nid: int) -> str:
        key = str(nid)
        if key not in nodes:
            lng, lat = coords[nid]
            nodes[key] = Node(key, lng, lat, inside(lng, lat))
        return key

    links: dict[tuple[str, str], Link] = {}
    for rl in raw_links:
        tags = rl["tags"]
        ow = _oneway(tags)
        f_lanes, b_lanes, lsrc = _lanes(tags, 0 if ow == 0 else 1)
        speed, ssrc = _speed(tags)
        geom = [list(coords[x]) for x in rl["nodes"]]
        length = sum(haversine_m(tuple(geom[i]), tuple(geom[i + 1])) for i in range(len(geom) - 1))
        if length < 1.0:
            continue
        street = tags.get("name", "(fără nume)")
        for direction, ok, lanes in (("f", rl["fwd"], f_lanes), ("b", rl["bwd"], b_lanes if ow == 0 else f_lanes)):
            if not ok or lanes <= 0:
                continue
            seq = rl["nodes"] if direction == "f" else rl["nodes"][::-1]
            u, v = node(seq[0]), node(seq[-1])
            g = geom if direction == "f" else geom[::-1]
            link = Link(f"L{u}_{v}", u, v, street, tags.get("highway", ""), round(length, 1), speed, lanes,
                        _bus_lane(tags), g, lsrc, ssrc, rl["ways"])
            prev = links.get((u, v))
            if prev is None or link.length_m < prev.length_m:   # parallel duplicates: keep the shorter
                links[(u, v)] = link
            for nid in (u, v):
                nodes[nid].streets.append(street)

    # 4. keep the largest weakly connected component
    comp: dict[str, int] = {}
    nbrs: dict[str, set] = {}
    for (u, v) in links:
        nbrs.setdefault(u, set()).add(v)
        nbrs.setdefault(v, set()).add(u)
    cid = 0
    for start in nbrs:
        if start in comp:
            continue
        stack = [start]
        comp[start] = cid
        while stack:
            x = stack.pop()
            for y in nbrs[x]:
                if y not in comp:
                    comp[y] = cid
                    stack.append(y)
        cid += 1
    sizes: dict[int, int] = {}
    for c in comp.values():
        sizes[c] = sizes.get(c, 0) + 1
    main = max(sizes, key=sizes.get)
    link_list = sorted((l for (u, v), l in links.items() if comp[u] == main), key=lambda l: l.id)
    keep_nodes = {l.from_node for l in link_list} | {l.to_node for l in link_list}
    nodes = {k: v for k, v in nodes.items() if k in keep_nodes}

    # 5. signals → nearest inside junction within 40 m
    for lng, lat in signals:
        best = None
        for nd in nodes.values():
            if not nd.inside:
                continue
            d = haversine_m((lng, lat), (nd.lng, nd.lat))
            if d <= 40 and (best is None or d < best[0]):
                best = (d, nd)
        if best:
            best[1].signalized = True

    # 6. gates: outside terminal nodes
    gates = []
    by_node_in = {l.to_node: l for l in link_list}
    out_from: dict[str, Link] = {}
    in_to: dict[str, Link] = {}
    for l in link_list:
        if not nodes[l.from_node].inside:
            out_from[l.from_node] = l      # outside → inside : entering
        if not nodes[l.to_node].inside:
            in_to[l.to_node] = l           # inside → outside : leaving
    for nid in sorted(set(out_from) | set(in_to)):
        nd = nodes[nid]
        enter, leave = out_from.get(nid), in_to.get(nid)
        street = (enter or leave).street
        d = {"S": nd.lat - s, "N": n - nd.lat, "W": nd.lng - w, "E": e - nd.lng}
        side = min(d, key=lambda k: abs(d[k]))
        gates.append(Gate(f"G{nid}", nid, street, side, enter.id if enter else None, leave.id if leave else None,
                          nd.lng, nd.lat))
    del by_node_in
    gates.sort(key=lambda g: ("NESW".index(g.side), g.street))

    net = CorridorNetwork(nodes, link_list, gates, {
        "osm": raw["source"], "fetchedAt": raw["fetchedAt"], "bbox": list(CORRIDOR.bbox),
    })
    net.link_index = {l.id: i for i, l in enumerate(net.links)}
    return net


def street_directions(net: CorridorNetwork) -> dict[str, dict[str, list[str]]]:
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
