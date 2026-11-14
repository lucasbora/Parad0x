"""Link-based static traffic assignment (Wardrop user equilibrium).

Link cost (minutes):   c_e(z) = fixed_e + k_e · (z / cap_e) ** beta_e
  * BPR road link:      fixed = t0 + signal uniform delay,  k = α·t0
  * textbook Braess:    fixed = 0 or 45, k = 1, cap = 100, beta = 1   (c = z/100)

Solved with Conjugate Frank–Wolfe (Mitradjieva & Lindberg 2013): shortest paths
(Dijkstra, scipy) give the all-or-nothing direction, an exact line search minimises
the Beckmann objective Σ∫c along it. Turning-movement flows are carried along with
link flows so turn counts can be compared with the model.

Shortest paths run on the LINK graph ("dual graph"): every road link is a vertex and every
ALLOWED turn (in_link → out_link) is an edge. That is what makes turn restrictions (no left
turn, only straight on, no U-turn) part of the route choice. Each network node v also has a
source vertex S_v (trips starting at v) and a sink vertex T_v (trips ending at v):

    S_v → j   for links j leaving v        weight c_j
    i  → j    for allowed turns i → j      weight c_j
    i  → T_v  for links i arriving at v    weight ε   (keeps the tree strictly ordered)
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


SINK_EPS = 1e-7    # minutes on the link → sink edges


class Network:
    """Directed graph in the form the solver needs. Links are (from_idx, to_idx).

    ``banned`` = set of (in_link, out_link) movements that are not allowed (turn restrictions)."""

    def __init__(self, n_nodes: int, link_from: list[int], link_to: list[int],
                 banned: "set[tuple[int, int]] | None" = None):
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
        banned = banned or set()
        self.n_banned = 0
        for j, u in enumerate(link_from):
            for i in incoming.get(u, []):
                if (i, j) in banned:
                    self.n_banned += 1
                    continue
                self.movements[(i, j)] = len(self.movements)

        # dual graph: vertices 0..L-1 links, L+v source of node v, L+N+v sink of node v
        L, N = self.n_links, n_nodes
        self.n_dual = L + 2 * N
        tails = [L + u for u in link_from] + [i for i, _ in self.movements] + list(range(L))
        heads = list(range(L)) + [j for _, j in self.movements] + [L + N + v for v in link_to]
        paid = list(range(L)) + [j for _, j in self.movements] + [-1] * L     # link whose cost is paid
        self._dual_tail = np.asarray(tails, dtype=np.int64)
        self._dual_head = np.asarray(heads, dtype=np.int64)
        self._dual_paid = np.asarray(paid, dtype=np.int64)
        self._mov_idx = np.full((L, L), -1, dtype=np.int64)
        if self.movements:
            ij = np.array(list(self.movements), dtype=np.int64)
            self._mov_idx[ij[:, 0], ij[:, 1]] = np.arange(len(ij))

    def shortest_paths(self, cost: np.ndarray, origins: list[int], usable: np.ndarray):
        """Dijkstra on the dual graph from the SOURCE vertices of ``origins``.

        Returns (dist, pred) over dual vertices; the time to node d is dist[:, L+N+d] − SINK_EPS."""
        c = np.maximum(cost, 1e-9)
        paid = self._dual_paid
        w = np.where(paid >= 0, c[np.maximum(paid, 0)], SINK_EPS)
        ok = np.where(paid >= 0, usable[np.maximum(paid, 0)], usable[np.minimum(self._dual_tail, self.n_links - 1)])
        g = csr_matrix((w[ok], (self._dual_tail[ok], self._dual_head[ok])), shape=(self.n_dual, self.n_dual))
        return dijkstra(g, directed=True, indices=[self.n_links + o for o in origins], return_predecessors=True)

    def path_links(self, pred_row: np.ndarray, d: int) -> list[int]:
        """Link indices of the tree path to node ``d`` (empty if unreachable)."""
        L = self.n_links
        v = int(pred_row[L + self.n_nodes + d])
        out = []
        while 0 <= v < L:
            out.append(v)
            v = int(pred_row[v])
        return out[::-1]


class _ODIndex:
    """Demand grouped by origin as dense node vectors (built once per assign call)."""

    def __init__(self, net: Network, ods: list[tuple[int, int, float]]):
        self.origins = sorted({o for o, _, _ in ods})
        self.row = {o: r for r, o in enumerate(self.origins)}
        self.demand = np.zeros((len(self.origins), net.n_nodes))
        self.pairs = ods
        for o, d, q in ods:
            self.demand[self.row[o], d] += max(q, 0.0)


def _all_or_nothing(net: Network, cost: np.ndarray, ods: "list[tuple[int, int, float]] | _ODIndex",
                    usable: np.ndarray):
    """All-or-nothing loading by shortest-path TREES on the dual (link) graph, all origins at once.

    Every dual vertex gets its depth in its origin's tree; demand at the sink vertices is then
    pushed to the parents level by level (deepest first), vectorised over all origins. The flow
    through a link vertex is the link flow; the flow over a tree edge link i → link j is the
    turning-movement flow.
    """
    idx = ods if isinstance(ods, _ODIndex) else _ODIndex(net, ods)
    L, N, D = net.n_links, net.n_nodes, net.n_dual
    R = len(idx.origins)
    y = np.zeros(L)
    ym = np.zeros(len(net.movements))
    if R == 0:
        return y, ym, {}
    dist, pred = net.shortest_paths(cost, idx.origins, usable)
    sink = dist[:, L + N:]
    bad = (idx.demand > 0) & ~np.isfinite(sink)
    if np.any(bad):
        r, d = np.argwhere(bad)[0]
        raise ValueError(f"no route from node {idx.origins[r]} to node {d}")

    valid = pred >= 0
    # depth in the tree by pointer jumping (log2(depth) steps): roots point to themselves
    rows = np.arange(R)[:, None]
    anc = np.where(valid, pred, np.arange(D)[None, :])
    depth = valid.astype(np.int32)
    while True:
        nxt = anc[rows, anc]
        if np.array_equal(nxt, anc):
            break
        depth = depth + depth[rows, anc]
        anc = nxt

    acc = np.zeros((R, D))
    acc[:, L + N:] = np.where(np.isfinite(sink), idx.demand, 0.0)
    flat = np.flatnonzero(valid)
    if len(flat):
        dep = depth.ravel()[flat]
        order = np.argsort(-dep, kind="stable")
        flat, dep = flat[order], dep[order]
        parent_flat = (flat // D) * D + pred.ravel()[flat]
        cuts = np.flatnonzero(np.diff(dep)) + 1
        accf = acc.ravel()
        for a, b in zip(np.concatenate(([0], cuts)), np.concatenate((cuts, [len(flat)]))):
            np.add.at(accf, parent_flat[a:b], accf[flat[a:b]])
        acc = accf.reshape(R, D)
    y = acc[:, :L].sum(axis=0)
    pl = pred[:, :L]
    turn = (pl >= 0) & (pl < L)
    if np.any(turn):
        mi = net._mov_idx[pl[turn], np.nonzero(turn)[1]]
        np.add.at(ym, mi, acc[:, :L][turn])
    od_time = {(o, d): float(dist[idx.row[o], L + N + d] - SINK_EPS) for o, d, _ in idx.pairs}
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
