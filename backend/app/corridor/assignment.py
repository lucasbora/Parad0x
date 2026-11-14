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


class _ODIndex:
    """Demand grouped by origin as dense node vectors (built once per assign call)."""

    def __init__(self, net: Network, ods: list[tuple[int, int, float]]):
        self.origins = sorted({o for o, _, _ in ods})
        self.row = {o: r for r, o in enumerate(self.origins)}
        self.demand = np.zeros((len(self.origins), net.n_nodes))
        self.pairs = ods
        for o, d, q in ods:
            self.demand[self.row[o], d] += max(q, 0.0)


def _edge_index(net: Network) -> np.ndarray:
    if not hasattr(net, "_edge_idx"):
        idx = np.full((net.n_nodes, net.n_nodes), -1, dtype=np.int64)
        idx[net.link_from, net.link_to] = np.arange(net.n_links)
        net._edge_idx = idx  # type: ignore[attr-defined]
    return net._edge_idx  # type: ignore[attr-defined]


def _all_or_nothing(net: Network, cost: np.ndarray, ods: "list[tuple[int, int, float]] | _ODIndex",
                    usable: np.ndarray):
    """All-or-nothing loading by shortest-path TREES: one backward sweep per origin.

    For each origin the demand of every destination is pushed back up the shortest-path tree
    (nodes in decreasing distance), so each link is touched once per origin instead of once per
    OD pair. Turning-movement flows fall out of the same sweep: flow on tree edge u→v arrived
    at u through u's own tree edge.
    """
    idx = ods if isinstance(ods, _ODIndex) else _ODIndex(net, ods)
    dist, pred = net.shortest_paths(cost, idx.origins, usable)
    edge = _edge_index(net)
    y = np.zeros(net.n_links)
    ym = np.zeros(len(net.movements))
    mov = net.movements
    for r, o in enumerate(idx.origins):
        dem = idx.demand[r]
        need = np.nonzero(dem > 0)[0]
        if len(need) and not np.all(np.isfinite(dist[r, need])):
            bad = int(need[~np.isfinite(dist[r, need])][0])
            raise ValueError(f"no route from node {o} to node {bad}")
        acc = dem.copy()
        pr = pred[r]
        reach = np.nonzero(np.isfinite(dist[r]) & (acc >= 0))[0]
        order = reach[np.argsort(-dist[r, reach], kind="stable")]
        for v in order:
            q = acc[v]
            if q <= 0 or v == o:
                continue
            u = pr[v]
            e = edge[u, v]
            y[e] += q
            pu = pr[u]
            if pu >= 0:
                ym[mov[(int(edge[pu, u]), int(e))]] += q
            acc[u] += q
    od_time = {(o, d): float(dist[idx.row[o], d]) for o, d, _ in idx.pairs}
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
           rel_gap: float = 1e-5, max_iter: int = 500,
           x0: "tuple[np.ndarray, np.ndarray] | None" = None) -> AssignmentResult:
    """User equilibrium for OD demand ``ods`` = [(origin_node, dest_node, veh_h)].

    ``x0`` = (link flows, movement flows) of a previous solution to warm-start from (e.g. the
    base state when testing a closure). Flows on unusable links are first re-routed.
    """
    t_start = time.perf_counter()
    usable = np.ones(net.n_links, dtype=bool) if usable is None else usable
    idx = _ODIndex(net, ods)
    ods = idx  # type: ignore[assignment]
    if x0 is not None and not np.any(x0[0][~usable] > 1e-9):
        z, zm = x0[0].copy(), x0[1].copy()
    elif x0 is not None:
        # closed links carry flow in the warm start: blend toward a feasible AON so the CFW
        # line search can move it off (convex combination keeps demand consistent)
        y0, ym0, _ = _all_or_nothing(net, costs.cost(x0[0] * usable), ods, usable)
        z, zm = y0, ym0
    else:
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
