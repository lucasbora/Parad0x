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
