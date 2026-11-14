"""Corridor demand from gate counts (OWNER: Lucas).

We only know how many cars ENTER and LEAVE the area at each gate (counted). Which
entering car leaves where is estimated with a doubly-constrained gravity model
(Furness / iterative proportional fitting):

    T_ij ∝ exp(−β · t_ij)      rows sum to the counted inflow O_i,
                                columns sum to the counted outflow D_j

t_ij is the free-flow travel time through the network; trips that leave by the gate
they entered are not allowed. β is an ASSUMPTION until calibrated against turn counts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np


@dataclass
class GateMatrix:
    origins: list[str]          # gate ids (have inflow)
    destinations: list[str]     # gate ids (have outflow)
    trips: np.ndarray           # veh/h, shape (len(origins), len(destinations))
    inflow_total: float
    outflow_total: float
    imbalance_pct: float        # (out − in) / in · 100, before balancing
    iterations: int


def furness(inflow: dict[str, float], outflow: dict[str, float], free_time: dict[tuple[str, str], float],
            beta: float, max_iter: int = 200, tol: float = 1e-6) -> GateMatrix:
    origins = [g for g, v in inflow.items() if v > 0]
    dests = [g for g, v in outflow.items() if v > 0]
    O = np.array([inflow[g] for g in origins])
    D = np.array([outflow[g] for g in dests])
    if O.sum() <= 0 or D.sum() <= 0:
        raise ValueError("need positive inflow and outflow counts")
    imbalance = (D.sum() - O.sum()) / O.sum() * 100.0
    D = D * (O.sum() / D.sum())                     # trust inflow totals; report the gap
    seed = np.zeros((len(origins), len(dests)))
    for i, o in enumerate(origins):
        for j, d in enumerate(dests):
            t = free_time.get((o, d))
            if o != d and t is not None and np.isfinite(t):
                seed[i, j] = np.exp(-beta * t)
    if np.any(seed.sum(axis=1) == 0) or np.any(seed.sum(axis=0) == 0):
        raise ValueError("a counted gate has no reachable partner gate")
    T = seed.copy()
    it = 0
    for it in range(1, max_iter + 1):
        T *= (O / T.sum(axis=1))[:, None]
        T *= (D / T.sum(axis=0))[None, :]
        if np.max(np.abs(T.sum(axis=1) - O) / O) < tol:
            break
    return GateMatrix(origins, dests, T, float(O.sum()), float(sum(outflow[g] for g in dests)),
                      float(imbalance), it)

# ---------------------------------------------------------------------------
# Land-use demand (default) — homes, destinations and gateways for one profile
# ---------------------------------------------------------------------------

@dataclass
class Endpoint:
    id: str              # zone id ("Z…") or gate id ("G…")
    node: int            # solver node index
    label: str
    kind: str            # "zone" | "gate"


@dataclass
class ODTable:
    rows: list[Endpoint]
    cols: list[Endpoint]
    trips: np.ndarray            # veh/h
    summary: dict


def balance(seed: np.ndarray, row_tot: np.ndarray, col_tot: np.ndarray, max_iter: int = 300,
            tol: float = 1e-7) -> tuple[np.ndarray, float]:
    """Doubly-constrained balancing (Furness / IPF). Returns (matrix, column imbalance % before)."""
    imbalance = (col_tot.sum() - row_tot.sum()) / max(row_tot.sum(), 1e-9) * 100.0
    col = col_tot * (row_tot.sum() / max(col_tot.sum(), 1e-9))
    T = seed.astype(float).copy()
    live_r, live_c = row_tot > 0, col > 0
    T[~live_r, :] = 0
    T[:, ~live_c] = 0
    for _ in range(max_iter):
        rs = T.sum(axis=1)
        T *= np.where(rs > 0, row_tot / np.where(rs > 0, rs, 1), 0)[:, None]
        cs = T.sum(axis=0)
        T *= np.where(cs > 0, col / np.where(cs > 0, cs, 1), 0)[None, :]
        rs = T.sum(axis=1)
        if np.max(np.abs(rs - row_tot) / np.maximum(row_tot, 1e-9) * live_r) < tol:
            break
    return T, float(imbalance)


def landuse_od(zones: list, gates: list, node_of: dict[str, int], free_time: "Callable[[int, int], float]",
               gate_cap_in: dict[str, float], gate_cap_out: dict[str, float], profile, landuse: dict,
               counted_in: dict[str, float] | None = None, counted_out: dict[str, float] | None = None,
               local_multiplier: float = 1.0, through_scale: float = 1.0) -> ODTable:
    """Trips for one profile from homes (residents) and activities, plus gateway traffic.

    home-end car trips  H_i = residents × trips/day × level × hour share × car share ÷ occupancy
    activity ends       A_i ∝ Σ_cat weight_cat(profile) × activity_i,cat   (scaled so ΣA = ΣH)
    origins  O_i = H_i(1+dir)/2 + A_i(1−dir)/2     destinations D_i = H_i(1−dir)/2 + A_i(1+dir)/2
    A share ``external_share`` of local trips leaves/enters through the gateways (by capacity);
    through-traffic = ``through_share_of_capacity`` × gateway capacity × ``through_scale`` (time of day,
    relative to the reference profile). Counted gates replace
    the estimate for that gate. Then a gravity seed exp(−β t) is balanced to all totals.
    """
    per_res = (landuse["trips_per_resident_day"] * profile.trip_level * profile.hour_share
               * landuse["car_share"] / landuse["car_occupancy"])
    H = np.array([z.residents * per_res for z in zones]) * local_multiplier
    act = np.array([sum(z.activity.get(k, 0.0) * profile.activity.get(k, 0.0) for k in profile.activity)
                    for z in zones])
    A = act / max(act.sum(), 1e-9) * H.sum()
    d = profile.direction
    O = H * (1 + d) / 2 + A * (1 - d) / 2
    D = H * (1 - d) / 2 + A * (1 + d) / 2
    ext = landuse["external_share"]
    gin = [g for g in gates if g.in_link]
    gout = [g for g in gates if g.out_link]
    cin = np.array([gate_cap_in[g.id] for g in gin])
    cout = np.array([gate_cap_out[g.id] for g in gout])
    through = landuse["through_share_of_capacity"] * cin.sum() * through_scale
    g_in = ext * D.sum() * cin / cin.sum() + through * cin / cin.sum()
    g_out = ext * O.sum() * cout / cout.sum() + through * cout / cout.sum()
    estimated_in, estimated_out = g_in.copy(), g_out.copy()
    for i, g in enumerate(gin):
        if counted_in and g.id in counted_in:
            g_in[i] = counted_in[g.id]
    for j, g in enumerate(gout):
        if counted_out and g.id in counted_out:
            g_out[j] = counted_out[g.id]

    rows = [Endpoint(z.id, node_of[z.node], z.label, "zone") for z in zones] + \
           [Endpoint(g.id, node_of[g.node], f"{g.street} ({g.side})", "gate") for g in gin]
    cols = [Endpoint(z.id, node_of[z.node], z.label, "zone") for z in zones] + \
           [Endpoint(g.id, node_of[g.node], f"{g.street} ({g.side})", "gate") for g in gout]
    beta = profile.gravity_beta
    seed = np.zeros((len(rows), len(cols)))
    for i, r in enumerate(rows):
        for j, c in enumerate(cols):
            if r.node == c.node:
                continue                              # no trips that start and end at the same point
            t = free_time(r.node, c.node)
            if not np.isfinite(t):
                continue
            if r.kind == "gate" and c.kind == "gate":
                seed[i, j] = 1.0                       # through traffic: any other gateway
            elif r.kind == "gate" or c.kind == "gate":
                seed[i, j] = np.exp(-beta * 0.5 * t)   # trip continues outside the box
            else:
                seed[i, j] = np.exp(-beta * t)
    # zone rows/cols carry ALL their trips (the gateway columns/rows absorb the external share
    # because their totals were set to ext·ΣO / ext·ΣD plus through-traffic above)
    row_tot = np.concatenate([O, g_in])
    col_tot = np.concatenate([D, g_out])
    T, imbalance = balance(seed, row_tot, col_tot)
    summary = {
        "residents": round(float(sum(z.residents for z in zones))),
        "homeTripsVehH": round(float(H.sum())),
        "localTripsVehH": round(float(O.sum())),
        "gatewayInVehH": round(float(g_in.sum())),
        "gatewayOutVehH": round(float(g_out.sum())),
        "estimatedGatewayInVehH": round(float(estimated_in.sum())),
        "throughVehH": round(float(through)),
        "throughScale": round(float(through_scale), 3),
        "totalVehH": round(float(T.sum())),
        "imbalancePct": round(imbalance, 2),
        "localMultiplier": round(local_multiplier, 3),
        "countedGates": sorted(set(counted_in or {}) | set(counted_out or {})),
    }
    return ODTable(rows, cols, T, summary)
