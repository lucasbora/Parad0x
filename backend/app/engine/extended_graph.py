"""Extended graph G = (N, L_road ∪ L_queue) after Burov et al.

Road links carry BPR delay; phantom intersection queue links carry the
piecewise-linear queue delay. Both expose analytical Beckmann potentials.

Units used throughout the engine:
  * flow z in veh/h
  * delays Φ in minutes (queue parameters are given in seconds and converted)
  * total system travel time Y = Σ z·Φ in veh·min per hour
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterable

import networkx as nx
import numpy as np

from app.services import seed_timisoara as seed

CAR = "car"
LANE_TYPES = ("car", "bus", "bike", "pedestrian_trees", "parking_green", "parking_red", "parking_yellow", "parking_blue")
DEFAULT_LANE_CAPACITY = 900.0
BPR_A = 0.15
BPR_B = 4.0


@dataclass
class RoadLink:
    id: str
    tag: str
    from_node: str
    to_node: str
    street_name: str
    cod_gis: str
    cartier: str
    lanes: list[str]
    length_m: float
    speed_kmh: float
    coords: list[list[float]]
    lane_capacity: float = DEFAULT_LANE_CAPACITY
    a: float = BPR_A
    b: float = BPR_B
    cycleway: bool = False
    hotspot: str | None = None
    twin_id: str | None = None

    @property
    def m_car(self) -> int:
        return sum(1 for l in self.lanes if l == CAR)

    @property
    def t0_min(self) -> float:
        return (self.length_m / 1000.0) / self.speed_kmh * 60.0

    @property
    def capacity(self) -> float:
        return self.m_car * self.lane_capacity

    @property
    def timpark_zone(self) -> str | None:
        for l in self.lanes:
            if l.startswith("parking_"):
                return l.split("_", 1)[1]
        return None


@dataclass
class QueueLink:
    id: str
    node: str
    in_link: str
    out_link: str
    cycle_s: float
    red_s: float
    n_per_lane: float
    alpha_s_per_vehh: float
    control: str = "signal"
    stop_w_s: float = 4.0

    def d0_s(self) -> float:
        # Burov et al.: expected low-flow wait d0 = L(1+L)/(2D)
        return self.red_s * (1.0 + self.red_s) / (2.0 * self.cycle_s)

    def saturation(self, approach_car_lanes: int) -> float:
        if self.control == "stop":
            return 3600.0 / self.stop_w_s * max(approach_car_lanes, 0) / 2.0
        n = self.n_per_lane * max(approach_car_lanes, 0)
        return 3600.0 * n / self.cycle_s


@dataclass
class EdgeParams:
    """Vectorised parameters over E = road ∪ queue edges (road first)."""
    n_road: int
    t0: np.ndarray        # road free-flow time (min); 0 for queue
    cap: np.ndarray       # road capacity veh/h
    a: np.ndarray
    b: np.ndarray
    d0: np.ndarray        # queue low-flow delay (min)
    s: np.ndarray         # queue saturation veh/h
    alpha: np.ndarray     # queue slope (min per veh/h)

    @property
    def n_queue(self) -> int:
        return len(self.d0)

    def copy(self) -> "EdgeParams":
        return EdgeParams(self.n_road, self.t0.copy(), self.cap.copy(), self.a.copy(), self.b.copy(),
                          self.d0.copy(), self.s.copy(), self.alpha.copy())


@dataclass
class ODPair:
    id: str
    origin: str
    destination: str
    label: str
    corridor: str
    inbound: bool
    base: float | None = None
    curated_paths: list[list[str]] | None = None


@dataclass
class Path:
    od_index: int
    road_links: list[int]          # indices into graph.road_links
    edges: list[int]               # indices into E (road + queue) in traversal order


@dataclass
class ExtendedGraph:
    nodes: dict[str, dict]
    road_links: list[RoadLink]
    queue_links: list[QueueLink]
    od_pairs: list[ODPair]
    road_index: dict[str, int] = field(default_factory=dict)
    queue_index: dict[str, int] = field(default_factory=dict)
    movement_queue: dict[tuple[int, int], int] = field(default_factory=dict)
    paths: list[Path] = field(default_factory=list)
    queues_by_in_link: dict[int, list[int]] = field(default_factory=dict)

    # ------------------------------------------------------------------
    @property
    def n_road(self) -> int:
        return len(self.road_links)

    @property
    def n_edges(self) -> int:
        return len(self.road_links) + len(self.queue_links)

    def link(self, link_id: str) -> RoadLink:
        return self.road_links[self.road_index[link_id]]

    # ------------------------------------------------------------------
    # FROZEN INTERFACE (owner: Rareș) — what demand / layers may rely on.
    def node_table(self) -> list[dict]:
        """[{id, name, coordinates: [lng, lat], cartier}] for every network node."""
        return [{"id": n["id"], "name": n["name"], "coordinates": n["coordinates"], "cartier": n["cartier"]}
                for n in self.nodes.values()]

    def snap_to_node(self, lng: float, lat: float) -> str:
        """Id of the network node nearest to a WGS84 point (for centroids, POIs, counts)."""
        best = min(self.nodes.values(), key=lambda n: seed.haversine_m((lng, lat), tuple(n["coordinates"])))
        return best["id"]

    def base_params(self, lane_overrides: dict[str, list[str]] | None = None) -> EdgeParams:
        """Edge parameters for a given lane allocation (overrides keyed by link id)."""
        lane_overrides = lane_overrides or {}
        nr, nq = self.n_road, len(self.queue_links)
        t0 = np.zeros(nr + nq)
        cap = np.ones(nr + nq)
        a = np.zeros(nr + nq)
        b = np.ones(nr + nq)
        d0 = np.zeros(nq)
        s = np.zeros(nq)
        alpha = np.zeros(nq)
        m_car_now = np.zeros(nr)
        for i, rl in enumerate(self.road_links):
            lanes = lane_overrides.get(rl.id, rl.lanes)
            m_new = sum(1 for l in lanes if l == CAR)
            m_orig = max(rl.m_car, 1)
            m_car_now[i] = m_new
            t0[i] = rl.t0_min
            # cap_new = cap · m_car / m_orig ; a closed link keeps a token 0.01 capacity
            cap[i] = rl.capacity * (m_new / m_orig) if m_new > 0 else 0.01
            a[i] = rl.a
            b[i] = rl.b
        for j, q in enumerate(self.queue_links):
            in_idx = self.road_index[q.in_link]
            d0[j] = q.d0_s() / 60.0
            # saturation scales with the approaching car lanes
            s[j] = max(q.saturation(int(m_car_now[in_idx])), 1.0)
            alpha[j] = q.alpha_s_per_vehh / 60.0
        return EdgeParams(nr, t0, cap, a, b, d0, s, alpha)

    # ------------------------------------------------------------------
    def road_digraph(self, weight: str = "t0") -> nx.DiGraph:
        g = nx.DiGraph()
        for i, rl in enumerate(self.road_links):
            g.add_edge(rl.from_node, rl.to_node, idx=i, t0=rl.t0_min, length=rl.length_m)
        return g

    def edges_for_road_path(self, road_idx: list[int]) -> list[int]:
        edges: list[int] = []
        for k, ri in enumerate(road_idx):
            edges.append(ri)
            if k + 1 < len(road_idx):
                q = self.movement_queue.get((ri, road_idx[k + 1]))
                if q is not None:
                    edges.append(self.n_road + q)
        return edges

    def enumerate_paths(self, k: int = 6, max_ratio: float = 1.9) -> None:
        """Candidate acyclic path sets P^k.

        Curated route sets from the seed are used when present (as in Burov et al.);
        otherwise the k shortest simple paths by free-flow time within ``max_ratio``.
        """
        g = self.road_digraph()
        self.paths = []
        for od_i, od in enumerate(self.od_pairs):
            if od.curated_paths:
                for node_path in od.curated_paths:
                    if node_path[0] != od.origin or node_path[-1] != od.destination:
                        raise ValueError(f"{od.id}: curated path endpoints mismatch")
                    road_idx = [g[u][v]["idx"] for u, v in zip(node_path[:-1], node_path[1:])]
                    if len(set(node_path)) != len(node_path):
                        raise ValueError(f"{od.id}: curated path is cyclic")
                    self.paths.append(Path(od_i, road_idx, self.edges_for_road_path(road_idx)))
                continue
            gen = nx.shortest_simple_paths(g, od.origin, od.destination, weight="t0")
            best = None
            for count, node_path in enumerate(gen):
                if count >= k * 3:
                    break
                road_idx = [g[u][v]["idx"] for u, v in zip(node_path[:-1], node_path[1:])]
                cost = sum(self.road_links[r].t0_min for r in road_idx)
                if best is None:
                    best = cost
                if cost > best * max_ratio:
                    break
                self.paths.append(Path(od_i, road_idx, self.edges_for_road_path(road_idx)))
                if sum(1 for p in self.paths if p.od_index == od_i) >= k:
                    break

    def incidence(self, paths: Iterable[Path] | None = None) -> np.ndarray:
        """Path–edge incidence matrix R (|P| × |E|) so that z = Rᵀx."""
        paths = list(self.paths if paths is None else paths)
        R = np.zeros((len(paths), self.n_edges))
        for p_i, p in enumerate(paths):
            for e in p.edges:
                R[p_i, e] += 1.0
        return R

    def path_coordinates(self, path: Path) -> list[list[float]]:
        coords: list[list[float]] = []
        for ri in path.road_links:
            seg = self.road_links[ri].coords
            if coords and coords[-1] == seg[0]:
                coords.extend(seg[1:])
            else:
                coords.extend(seg)
        return coords

    def path_name(self, path: Path, max_streets: int = 3) -> str:
        names: list[str] = []
        for ri in path.road_links:
            n = self.road_links[ri].street_name
            base = n.split(" (")[0]
            if not names or names[-1] != base:
                names.append(base)
        # keep the most informative middle streets
        if len(names) > max_streets:
            names = names[:max_streets]
        return "Via " + " → ".join(names)


NETWORK_ENV = "TMBG_NETWORK"   # "seed" (default, hand-built graph) | "osm" (real OSM snapshot)


def build_graph(k_paths: int = 6, network: str | None = None) -> ExtendedGraph:
    """Build the network selected by ``network`` or ``$TMBG_NETWORK`` (default ``seed``)."""
    network = (network or os.getenv(NETWORK_ENV, "seed")).lower()
    if network == "osm":
        return build_osm_graph(k_paths=k_paths)
    if network != "seed":
        raise ValueError(f"unknown network {network!r} (expected 'seed' or 'osm')")
    return build_seed_graph(k_paths=k_paths)


def _seed_od_pairs(snap=None) -> list[ODPair]:
    """The seed OD pairs; with ``snap`` their endpoints are moved onto another network."""
    out = []
    for o in seed.OD_PAIRS:
        origin, dest, paths = o["origin"], o["destination"], o.get("paths")
        if snap is not None:
            origin, dest, paths = snap(origin), snap(dest), None   # curated routes are seed-only
        out.append(ODPair(o["id"], origin, dest, o["label"], o["corridor"], bool(o["inbound"]),
                          float(o["base"]) if o.get("base") is not None else None, paths))
    return out


def build_osm_graph(k_paths: int = 6, snapshot_path: str | None = None) -> ExtendedGraph:
    """Extended graph on the real OSM network (offline snapshot, see app.seed.osm_network).

    No phantom queue links yet (the seed QUEUE_MOVEMENTS reference seed link ids); signalised
    nodes are flagged so queue movements can be generated in the solver task. OD pairs are the
    seed ones snapped to the nearest OSM node until the new demand model is plugged in.
    """
    from app.seed.osm_network import load_snapshot

    snap_data = load_snapshot(snapshot_path)
    nodes = {
        n["id"]: {"id": n["id"], "name": n["name"], "coordinates": [n["lng"], n["lat"]],
                  "cartier": n["cartier"], "signalized": bool(n["signalized"])}
        for n in snap_data["nodes"]
    }
    road_links = [
        RoadLink(
            id=l["id"], tag=str(l["osm_way"]), from_node=l["from"], to_node=l["to"], street_name=l["street"],
            cod_gis="", cartier=nodes[l["to"]]["cartier"], lanes=list(l["lanes"]),
            length_m=float(l["length_m"]), speed_kmh=float(l["speed_kmh"]), coords=l["coords"],
            lane_capacity=float(l.get("lane_capacity", DEFAULT_LANE_CAPACITY)), twin_id=l.get("twin"),
        )
        for l in snap_data["links"]
    ]
    road_index = {rl.id: i for i, rl in enumerate(road_links)}
    g = ExtendedGraph(nodes, road_links, [], [], road_index, {}, {}, queues_by_in_link={})
    seed_nodes = seed.NODES

    def snap(seed_id: str) -> str:
        _, lng, lat, _, _ = seed_nodes[seed_id]
        return g.snap_to_node(lng, lat)

    g.od_pairs = _seed_od_pairs(snap)
    g.enumerate_paths(k=k_paths)
    return g


def build_seed_graph(k_paths: int = 6) -> ExtendedGraph:
    nodes = {
        nid: {"id": nid, "name": n[0], "coordinates": [n[1], n[2]], "cartier": n[3], "signalized": n[4]}
        for nid, n in seed.NODES.items()
    }
    road_links: list[RoadLink] = []
    for tag, a, b, name, cod, lanes, speed, opts in seed.SEGMENTS:
        ca, cb = nodes[a]["coordinates"], nodes[b]["coordinates"]
        length = float(opts.get("length_m", seed.haversine_m(tuple(ca), tuple(cb)) * 1.12))
        fwd = RoadLink(
            id=f"LINK_{tag}_01", tag=tag, from_node=a, to_node=b, street_name=name, cod_gis=cod,
            cartier=nodes[a]["cartier"] if nodes[a]["cartier"] == nodes[b]["cartier"] else nodes[b]["cartier"],
            lanes=list(lanes), length_m=length, speed_kmh=speed, coords=[list(ca), list(cb)],
            cycleway=bool(opts.get("cycleway", False)), hotspot=opts.get("hotspot"), twin_id=f"LINK_{tag}_02",
        )
        road_links.append(fwd)
        if not opts.get("oneway"):
            back_lanes = list(opts.get("lanes_back", [l for l in lanes]))
            road_links.append(RoadLink(
                id=f"LINK_{tag}_02", tag=tag, from_node=b, to_node=a, street_name=name, cod_gis=cod,
                cartier=fwd.cartier, lanes=back_lanes, length_m=length, speed_kmh=speed,
                coords=[list(cb), list(ca)], cycleway=fwd.cycleway, hotspot=None, twin_id=fwd.id,
            ))
    road_index = {rl.id: i for i, rl in enumerate(road_links)}

    queue_links: list[QueueLink] = []
    for qid, node, in_link, out_link, D, L, n, alpha, control in seed.QUEUE_MOVEMENTS:
        if in_link not in road_index or out_link not in road_index:
            raise ValueError(f"queue {qid} references unknown link")
        if road_links[road_index[in_link]].to_node != node or road_links[road_index[out_link]].from_node != node:
            raise ValueError(f"queue {qid} movement does not meet at {node}")
        queue_links.append(QueueLink(qid, node, in_link, out_link, D, L, n, alpha, control))
    queue_index = {q.id: j for j, q in enumerate(queue_links)}
    movement_queue = {(road_index[q.in_link], road_index[q.out_link]): j for j, q in enumerate(queue_links)}
    by_in: dict[int, list[int]] = {}
    for j, q in enumerate(queue_links):
        by_in.setdefault(road_index[q.in_link], []).append(j)

    od_pairs = _seed_od_pairs()
    g = ExtendedGraph(nodes, road_links, queue_links, od_pairs, road_index, queue_index, movement_queue,
                      queues_by_in_link=by_in)
    g.enumerate_paths(k=k_paths)
    return g
