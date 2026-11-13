"""Link-based static traffic assignment (Wardrop user equilibrium).

Link cost (minutes):   c_e(z) = fixed_e + k_e · (z / cap_e) ** beta_e
  * BPR road link:      fixed = t0 + signal uniform delay,  k = α·t0
  * textbook Braess:    fixed = 0 or 45, k = 1, cap = 100, beta = 1   (c = z/100)

Solved with Conjugate Frank–Wolfe (Mitradjieva & Lindberg 2013): shortest paths
(Dijkstra, scipy) give the all-or-nothing direction, an exact line search minimises
the Beckmann objective Σ∫c along it. Turning-movement flows are carried along with
link flows so turn counts can be compared with the model.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra


@dataclass
class LinkCosts:
    fixed: np.ndarray     # minutes
    k: np.ndarray         # minutes
    cap: np.ndarray       # veh/h
    beta: np.ndarray

    def cost(self, z: np.ndarray) -> np.ndarray:
        return self.fixed + self.k * np.power(np.maximum(z, 0.0) / self.cap, self.beta)

    def dcost(self, z: np.ndarray) -> np.ndarray:
        return self.k * self.beta * np.power(np.maximum(z, 0.0) / self.cap, self.beta - 1.0) / self.cap

    def potential(self, z: np.ndarray) -> float:
        return float(np.sum(self.fixed * z + self.k * self.cap / (self.beta + 1.0)
                            * np.power(np.maximum(z, 0.0) / self.cap, self.beta + 1.0)))


@dataclass
class AssignmentResult:
    flow: np.ndarray             # veh/h per link
    cost: np.ndarray             # minutes per link at equilibrium
    movement_flow: np.ndarray    # veh/h per (in_link, out_link) movement
    od_time: dict[tuple[int, int], float]   # equilibrium (shortest) OD travel time, minutes
    total_time: float            # Σ z·c   [veh·min/h]
    rel_gap: float
    iterations: int
    elapsed_ms: float


class Network:
    """Directed graph in the form the solver needs. Links are (from_idx, to_idx)."""

    def __init__(self, n_nodes: int, link_from: list[int], link_to: list[int]):
        self.n_nodes = n_nodes
        self.link_from = np.asarray(link_from)
        self.link_to = np.asarray(link_to)
        self.n_links = len(link_from)
        self.edge_link: dict[tuple[int, int], int] = {}
        for i, (u, v) in enumerate(zip(link_from, link_to)):
            if (u, v) in self.edge_link:
                raise ValueError(f"parallel links between nodes {u}→{v} are not supported")
            self.edge_link[(u, v)] = i
        self.movements: dict[tuple[int, int], int] = {}
        incoming: dict[int, list[int]] = {}
        for i, v in enumerate(link_to):
            incoming.setdefault(v, []).append(i)
        for j, u in enumerate(link_from):
            for i in incoming.get(u, []):
                self.movements[(i, j)] = len(self.movements)

    def shortest_paths(self, cost: np.ndarray, origins: list[int], usable: np.ndarray):
        w = np.where(usable, np.maximum(cost, 1e-9), 0.0)
        mask = usable
        g = csr_matrix((w[mask], (self.link_from[mask], self.link_to[mask])), shape=(self.n_nodes, self.n_nodes))
        return dijkstra(g, directed=True, indices=origins, return_predecessors=True)


def _all_or_nothing(net: Network, cost: np.ndarray, ods: list[tuple[int, int, float]], usable: np.ndarray):
    origins = sorted({o for o, _, _ in ods})
    dist, pred = net.shortest_paths(cost, origins, usable)
    row = {o: r for r, o in enumerate(origins)}
    y = np.zeros(net.n_links)
    ym = np.zeros(len(net.movements))
    od_time = {}
    for o, d, q in ods:
        r = row[o]
        if not np.isfinite(dist[r, d]):
            raise ValueError(f"no route from node {o} to node {d}")
        od_time[(o, d)] = float(dist[r, d])
        if q <= 0:
            continue
        prev_link = None
        v = d
        while v != o:
            u = pred[r, v]
            li = net.edge_link[(u, v)]
            y[li] += q
            if prev_link is not None:
                ym[net.movements[(li, prev_link)]] += q
            prev_link = li
            v = u
    return y, ym, od_time


def _line_search(costs: LinkCosts, z: np.ndarray, dz: np.ndarray) -> float:
    def g(lam):
        return float(np.dot(costs.cost(z + lam * dz), dz))

    if g(0.0) >= 0:
        return 0.0
    if g(1.0) <= 0:
        return 1.0
    lo, hi, lam = 0.0, 1.0, 0.5
    for _ in range(40):
        zl = z + lam * dz
        gl = float(np.dot(costs.cost(zl), dz))
        if gl > 0:
            hi = lam
        else:
            lo = lam
        h = float(np.dot(costs.dcost(zl), dz * dz))
        nxt = lam - gl / h if h > 1e-14 else 0.5 * (lo + hi)
        if not (lo < nxt < hi):
            nxt = 0.5 * (lo + hi)
        if abs(nxt - lam) < 1e-10:
            return nxt
        lam = nxt
    return lam


def assign(net: Network, costs: LinkCosts, ods: list[tuple[int, int, float]], usable: np.ndarray | None = None,
           rel_gap: float = 1e-5, max_iter: int = 500) -> AssignmentResult:
    """User equilibrium for OD demand ``ods`` = [(origin_node, dest_node, veh_h)]."""
    t_start = time.perf_counter()
    usable = np.ones(net.n_links, dtype=bool) if usable is None else usable
    z, zm, _ = _all_or_nothing(net, costs.cost(np.zeros(net.n_links)), ods, usable)
    s_prev = sm_prev = None
    gap = np.inf
    it = 0
    for it in range(1, max_iter + 1):
        c = costs.cost(z)
        y, ym, _ = _all_or_nothing(net, c, ods, usable)
        tstt = float(np.dot(z, c))
        gap = (tstt - float(np.dot(y, c))) / max(tstt, 1e-12)
        if gap < rel_gap:
            break
        if s_prev is None:
            s, sm = y, ym
        else:
            H = costs.dcost(z)
            dbar = s_prev - z
            num = float(np.dot(dbar * H, y - z))
            den = float(np.dot(dbar * H, y - s_prev))
            a = min(max(num / den, 0.0), 0.99) if abs(den) > 1e-14 else 0.0
            s, sm = a * s_prev + (1 - a) * y, a * sm_prev + (1 - a) * ym
        lam = _line_search(costs, z, s - z)
        if lam <= 0.0:
            s, sm = y, ym
            lam = _line_search(costs, z, s - z)
        z = z + lam * (s - z)
        zm = zm + lam * (sm - zm)
        s_prev, sm_prev = s, sm
    c = costs.cost(z)
    _, _, od_time = _all_or_nothing(net, c, ods, usable)
    return AssignmentResult(flow=z, cost=c, movement_flow=zm, od_time=od_time, total_time=float(np.dot(z, c)),
                            rel_gap=float(max(gap, 0.0)), iterations=it,
                            elapsed_ms=(time.perf_counter() - t_start) * 1000.0)
