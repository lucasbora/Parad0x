"""Wardrop user equilibrium via Beckmann potentials.

min_{x ≥ 0} F(x) = Σ_road φ_i(z_i) + Σ_queue φ_q(z_q)   s.t.  Σ_{r∈P^k} x_r = d_k,  z = Rᵀx

Solved with Conjugate Frank–Wolfe (Mitradjieva & Lindberg, 2013) over fixed path
sets, with an exact Newton line search (bisection-safeguarded) on F along the
search direction. ∇_x F = R Φ(Rᵀx).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from app.engine.extended_graph import EdgeParams

# ---------------------------------------------------------------------------
# Delay functions and Beckmann potentials (vectorised over all edges)
# ---------------------------------------------------------------------------


def delays(z: np.ndarray, p: EdgeParams) -> np.ndarray:
    """Φ_e(z_e) in minutes for road (BPR) and queue (piecewise-linear) edges."""
    nr = p.n_road
    out = np.empty_like(z)
    zr = z[:nr]
    capc = np.maximum(p.cap[:nr], 1.0)
    out[:nr] = p.t0[:nr] * (1.0 + p.a[:nr] * (zr / capc) ** p.b[:nr])
    zq = z[nr:]
    beta = p.d0 - p.alpha * p.s
    out[nr:] = np.where(zq < p.s, p.d0, p.alpha * zq + beta)
    return out


def delay_derivatives(z: np.ndarray, p: EdgeParams) -> np.ndarray:
    nr = p.n_road
    out = np.empty_like(z)
    zr = z[:nr]
    capc = np.maximum(p.cap[:nr], 1.0)
    b = p.b[:nr]
    out[:nr] = p.t0[:nr] * p.a[:nr] * b * np.power(zr / capc, b - 1.0) / capc
    out[nr:] = np.where(z[nr:] < p.s, 0.0, p.alpha)
    return out


def potentials(z: np.ndarray, p: EdgeParams) -> np.ndarray:
    """φ_e(z_e) = ∫_0^z Φ_e (analytical)."""
    nr = p.n_road
    out = np.empty_like(z)
    zr = z[:nr]
    capc = np.maximum(p.cap[:nr], 1.0)
    b = p.b[:nr]
    out[:nr] = p.t0[:nr] * (zr + p.a[:nr] * capc / (b + 1.0) * (zr / capc) ** (b + 1.0))
    zq = z[nr:]
    beta = p.d0 - p.alpha * p.s
    over = p.d0 * p.s + 0.5 * p.alpha * (zq ** 2 - p.s ** 2) + beta * (zq - p.s)
    out[nr:] = np.where(zq < p.s, p.d0 * zq, over)
    return out


def beckmann_objective(z: np.ndarray, p: EdgeParams) -> float:
    return float(potentials(z, p).sum())


def total_system_time(z: np.ndarray, p: EdgeParams) -> float:
    """Y(z) = Σ_e z_e Φ_e(z_e)   [veh·min / h]."""
    return float(np.dot(z, delays(z, p)))


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------


@dataclass
class EquilibriumResult:
    x: np.ndarray            # path flows
    z: np.ndarray            # edge flows (road + queue)
    phi: np.ndarray          # edge delays (min)
    path_cost: np.ndarray    # path travel times (min)
    total_time: float        # Y
    objective: float         # Beckmann F
    rel_gap: float
    iterations: int
    elapsed_ms: float


class PathSystem:
    """Fixed path set + OD structure, prepared once and reused across scenarios."""

    def __init__(self, R: np.ndarray, od_of_path: np.ndarray, n_od: int):
        self.R = R
        self.RT = np.ascontiguousarray(R.T)
        self.od_of_path = od_of_path
        self.n_od = n_od
        order = np.argsort(od_of_path, kind="stable")
        if not np.all(order == np.arange(len(order))):
            raise ValueError("paths must be grouped by OD index")
        starts = np.searchsorted(od_of_path, np.arange(n_od))
        self.starts = starts
        self.counts = np.bincount(od_of_path, minlength=n_od)

    def all_or_nothing(self, cost: np.ndarray, demand: np.ndarray, active: np.ndarray) -> np.ndarray:
        """Assign each OD's demand to its cheapest active path."""
        c = np.where(active, cost, np.inf)
        y = np.zeros_like(cost)
        for k in range(self.n_od):
            s, n = self.starts[k], self.counts[k]
            if n == 0 or demand[k] <= 0:
                continue
            j = s + int(np.argmin(c[s:s + n]))
            y[j] = demand[k]
        return y

    def initial_flow(self, demand: np.ndarray, active: np.ndarray, p: EdgeParams) -> np.ndarray:
        cost = self.R @ delays(np.zeros(self.R.shape[1]), p)
        return self.all_or_nothing(cost, demand, active)


def _line_search(z: np.ndarray, dz: np.ndarray, p: EdgeParams, iters: int = 30) -> float:
    """Exact minimiser of F(z + λ dz) on [0, 1] (Newton with bisection safeguard)."""
    def g(lam):
        return float(np.dot(delays(z + lam * dz, p), dz))

    g0 = g(0.0)
    if g0 >= 0:
        return 0.0
    g1 = g(1.0)
    if g1 <= 0:
        return 1.0
    lo, hi = 0.0, 1.0
    lam = 0.5
    for _ in range(iters):
        zl = z + lam * dz
        gl = float(np.dot(delays(zl, p), dz))
        if abs(gl) < 1e-10:
            break
        if gl > 0:
            hi = lam
        else:
            lo = lam
        hl = float(np.dot(delay_derivatives(zl, p), dz * dz))
        nxt = lam - gl / hl if hl > 1e-14 else 0.5 * (lo + hi)
        if not (lo < nxt < hi):
            nxt = 0.5 * (lo + hi)
        if abs(nxt - lam) < 1e-9:
            lam = nxt
            break
        lam = nxt
    return lam


def _relative_gap(system: PathSystem, p: EdgeParams, demand: np.ndarray, active: np.ndarray, z: np.ndarray) -> float:
    phi = delays(z, p)
    cost = system.R @ phi
    y = system.all_or_nothing(cost, demand, active)
    tstt = float(np.dot(z, phi))
    sptt = float(np.dot(system.RT @ y, phi))
    return (tstt - sptt) / max(tstt, 1e-12)


def _gradient_projection_polish(
    system: PathSystem, p: EdgeParams, demand: np.ndarray, active: np.ndarray,
    x: np.ndarray, rel_gap: float, max_sweeps: int,
) -> tuple[np.ndarray, np.ndarray, float, int]:
    """Gauss–Seidel path flow shifts with Newton step (c_p − c_s) / Σ_{e∈p⊕s} Φ'_e."""
    R, RT = system.R, system.RT
    x = x.copy()
    z = RT @ x
    gap = _relative_gap(system, p, demand, active, z)
    sweeps = 0
    eps = 1e-7
    for sweeps in range(1, max_sweeps + 1):
        if gap < rel_gap:
            break
        for k in range(system.n_od):
            s0, n = system.starts[k], system.counts[k]
            if n < 2 or demand[k] <= 0:
                continue
            idx = np.arange(s0, s0 + n)
            idx = idx[active[idx]]
            if len(idx) < 2:
                continue
            phi = delays(z, p)
            H = delay_derivatives(z, p)
            c = R[idx] @ phi
            best = idx[int(np.argmin(c))]
            cbest = c.min()
            for j, pi in enumerate(idx):
                if pi == best or x[pi] <= 0:
                    continue
                diff = R[pi] - R[best]
                denom = float(np.dot(np.abs(diff), H)) + eps
                shift = min(x[pi], (c[j] - cbest) / denom)
                if shift <= 0:
                    continue
                x[pi] -= shift
                x[best] += shift
                z = z - shift * diff
        gap = _relative_gap(system, p, demand, active, z)
    return x, z, gap, sweeps


def solve_equilibrium(
    system: PathSystem,
    p: EdgeParams,
    demand: np.ndarray,
    active: np.ndarray | None = None,
    rel_gap: float = 1e-5,
    max_iter: int = 600,
    x0: np.ndarray | None = None,
    polish: bool = True,
    polish_switch_gap: float = 2e-3,
    max_polish_sweeps: int = 400,
) -> EquilibriumResult:
    """Conjugate Frank–Wolfe with exact Newton line search.

    CFW drives the relative gap down to ``polish_switch_gap``; the tail is then
    finished with path-based Newton flow shifts (Jayakrishnan et al. gradient
    projection), which converge much faster than FW once the active route set
    is known. Set ``polish=False`` for pure CFW.
    """
    t_start = time.perf_counter()
    R, RT = system.R, system.RT
    n_paths = R.shape[0]
    if active is None:
        active = np.ones(n_paths, dtype=bool)

    if x0 is not None and x0.shape == (n_paths,):
        x = np.where(active, x0, 0.0)
        # repair demand feasibility per OD (warm starts after a path was removed)
        for k in range(system.n_od):
            s, n = system.starts[k], system.counts[k]
            tot = x[s:s + n].sum()
            if demand[k] <= 0:
                x[s:s + n] = 0
            elif tot <= 1e-9:
                x[s:s + n] = 0
                cand = np.where(active[s:s + n])[0]
                if len(cand):
                    x[s + cand[0]] = demand[k]
            else:
                x[s:s + n] *= demand[k] / tot
    else:
        x = system.initial_flow(demand, active, p)

    z = RT @ x
    s_prev_x = None
    s_prev_z = None
    gap = np.inf
    it = 0
    for it in range(1, max_iter + 1):
        phi = delays(z, p)
        cost = R @ phi
        y = system.all_or_nothing(cost, demand, active)
        zy = RT @ y
        tstt = float(np.dot(z, phi))
        sptt = float(np.dot(zy, phi))
        gap = (tstt - sptt) / max(tstt, 1e-12)
        if gap < rel_gap:
            break
        # Conjugate direction (CFW)
        if s_prev_z is None:
            sx, sz = y, zy
        else:
            H = delay_derivatives(z, p)
            dbar = s_prev_z - z
            num = float(np.dot(dbar * H, zy - z))
            den = float(np.dot(dbar * H, zy - s_prev_z))
            if abs(den) > 1e-14:
                a_k = num / den
                a_k = min(max(a_k, 0.0), 0.99)
            else:
                a_k = 0.0
            sx = a_k * s_prev_x + (1 - a_k) * y
            sz = a_k * s_prev_z + (1 - a_k) * zy
        dx, dz = sx - x, sz - z
        lam = _line_search(z, dz, p)
        if lam <= 0.0:
            # conjugate direction not descending: fall back to plain FW direction
            dx, dz = y - x, zy - z
            lam = _line_search(z, dz, p)
            sx, sz = y, zy
        x = x + lam * dx
        z = z + lam * dz
        s_prev_x, s_prev_z = sx, sz

        if polish and gap < polish_switch_gap:
            break

    cfw_iters = it
    if polish and gap >= rel_gap:
        x, z, gap, gp_iters = _gradient_projection_polish(system, p, demand, active, x, rel_gap, max_polish_sweeps)
        it = cfw_iters + gp_iters

    phi = delays(z, p)
    cost = R @ phi
    return EquilibriumResult(
        x=x, z=z, phi=phi, path_cost=cost,
        total_time=float(np.dot(z, phi)),
        objective=beckmann_objective(z, p),
        rel_gap=float(max(gap, 0.0)),
        iterations=it,
        elapsed_ms=(time.perf_counter() - t_start) * 1000.0,
    )
