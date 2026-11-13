"""Scenario engine: lane reallocation, closures, greedy route removal and V.

V = Y_new − Y_baseline   (V < 0 ⇒ removing car capacity reduces city-wide delay)
I_th = (Y_baseline − Y_new) / Y_baseline × 100 %
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from app.config import SOLVER_MAX_ITER, SOLVER_REL_GAP
from app.engine.beckmann_solver import EquilibriumResult, PathSystem, delays, solve_equilibrium
from app.engine.demand_model import od_demand
from app.engine.extended_graph import CAR, EdgeParams, ExtendedGraph, build_graph

# CO2 model (documented in README): running emissions + idling during congestion delay
CO2_KG_PER_VEH_KM = 0.170
CO2_KG_PER_VEH_MIN_DELAY = 0.030


@dataclass
class LaneIntervention:
    link_id: str
    new_lanes: list[str]
    filter_cut_through: bool = False


@dataclass
class Scenario:
    preset: str
    demand: np.ndarray
    params: EdgeParams
    active: np.ndarray
    result: EquilibriumResult
    lane_overrides: dict[str, list[str]] = field(default_factory=dict)
    removed_paths: list[int] = field(default_factory=list)
    closed_links: list[str] = field(default_factory=list)

    @property
    def total_time(self) -> float:
        return self.result.total_time


class BraessEngine:
    """Owns the extended graph, the path system and per-preset baselines."""

    def __init__(self, graph: ExtendedGraph | None = None):
        self.graph = graph or build_graph()
        g = self.graph
        self.R = g.incidence()
        self.od_of_path = np.array([p.od_index for p in g.paths])
        self.system = PathSystem(self.R, self.od_of_path, len(g.od_pairs))
        self.path_uses_road = (self.R[:, : g.n_road] > 0)
        self._baselines: dict[str, Scenario] = {}
        self._prescan: dict[str, dict[str, dict]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def _preset_key(self, preset: str, now: datetime | None = None) -> str:
        if preset == "now":
            now = now or datetime.now()
            return f"now@{now:%Y-%m-%d %H}"
        return preset

    def _solve(self, params: EdgeParams, demand: np.ndarray, active: np.ndarray,
               x0: np.ndarray | None = None) -> EquilibriumResult:
        return solve_equilibrium(self.system, params, demand, active=active,
                                 rel_gap=SOLVER_REL_GAP, max_iter=SOLVER_MAX_ITER, x0=x0)

    def baseline(self, preset: str, now: datetime | None = None) -> Scenario:
        key = self._preset_key(preset, now)
        with self._lock:
            if key in self._baselines:
                return self._baselines[key]
        demand = od_demand(self.graph, preset, now)
        params = self.graph.base_params()
        active = np.ones(len(self.graph.paths), dtype=bool)
        res = self._solve(params, demand, active)
        sc = Scenario(preset, demand, params, active, res)
        with self._lock:
            self._baselines[key] = sc
        return sc

    # ------------------------------------------------------------------
    def _close_link_paths(self, active: np.ndarray, link_idx: int) -> np.ndarray:
        """Deactivate routes through a fully closed link, keeping ≥1 route per OD."""
        active = active.copy()
        uses = self.path_uses_road[:, link_idx]
        for k in range(self.system.n_od):
            s, n = self.system.starts[k], self.system.counts[k]
            sl = slice(s, s + n)
            remaining = active[sl] & ~uses[sl]
            if remaining.any():
                active[sl] = remaining
        return active

    def _greedy_route_removal(self, sc: Scenario, link_idx: int, max_removals: int = 3) -> Scenario:
        """Burov et al. greedy single-route removal restricted to routes over ``link_idx``.

        Repeatedly removes (navigation-filters) the one cut-through route whose
        removal lowers Y the most; stops when no removal helps.
        """
        current = sc
        for _ in range(max_removals):
            cands = []
            for r in np.where(current.active & self.path_uses_road[:, link_idx])[0]:
                k = self.od_of_path[r]
                s, n = self.system.starts[k], self.system.counts[k]
                others = current.active[s:s + n].sum() - 1
                if others >= 1 and current.result.x[r] > 1e-6:
                    cands.append(int(r))
            best = None
            for r in cands:
                act = current.active.copy()
                act[r] = False
                res = self._solve(current.params, current.demand, act, x0=current.result.x)
                if res.total_time < current.total_time - 1e-6 and (best is None or res.total_time < best[1].total_time):
                    best = (r, res, act)
            if best is None:
                break
            r, res, act = best
            current = Scenario(current.preset, current.demand, current.params, act, res,
                               current.lane_overrides, current.removed_paths + [r], current.closed_links)
        return current

    def evaluate(self, preset: str, interventions: list[LaneIntervention], now: datetime | None = None) -> Scenario:
        base = self.baseline(preset, now)
        g = self.graph
        overrides: dict[str, list[str]] = {}
        for iv in interventions:
            if iv.link_id not in g.road_index:
                raise KeyError(iv.link_id)
            overrides[iv.link_id] = list(iv.new_lanes)
        params = g.base_params(overrides)
        active = base.active.copy()
        closed = []
        for lid, lanes in overrides.items():
            if sum(1 for l in lanes if l == CAR) == 0:
                active = self._close_link_paths(active, g.road_index[lid])
                closed.append(lid)
        res = self._solve(params, base.demand, active, x0=base.result.x)
        sc = Scenario(preset, base.demand, params, active, res, overrides, [], closed)
        for iv in interventions:
            if iv.filter_cut_through:
                sc = self._greedy_route_removal(sc, g.road_index[iv.link_id])
        return sc

    # ------------------------------------------------------------------
    @staticmethod
    def one_lane_less(lanes: list[str], replacement: str = "bus") -> list[str]:
        """Swap the inner-most car lane (or close the street if it has a single car lane)."""
        out = list(lanes)
        for i in range(len(out) - 1, -1, -1):
            if out[i] == CAR:
                out[i] = replacement
                return out
        return out

    def prescan(self, preset: str, min_flow: float = 250.0, workers: int = 4) -> dict[str, dict]:
        """Close one car lane on every busy street in turn (Leon Zhao style scan) and rank by V."""
        key = self._preset_key(preset)
        with self._lock:
            if key in self._prescan:
                return self._prescan[key]
        base = self.baseline(preset)
        g = self.graph
        z = base.result.z

        def run(i: int) -> tuple[str, dict]:
            rl = g.road_links[i]
            new_lanes = self.one_lane_less(rl.lanes)
            sc = self.evaluate(preset, [LaneIntervention(rl.id, new_lanes)])
            v = sc.total_time - base.total_time
            return rl.id, {
                "V": v,
                "I": -v / base.total_time * 100.0,
                "scenarioLanes": new_lanes,
                "mode": "full_closure" if rl.m_car <= 1 else "minus_one_car_lane",
            }

        candidates = [i for i, rl in enumerate(g.road_links) if z[i] >= min_flow and rl.m_car >= 1]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            out = dict(ex.map(run, candidates))
        with self._lock:
            self._prescan[key] = out
        return out

    # ------------------------------------------------------------------
    def co2_kg_per_hour(self, sc: Scenario) -> float:
        g = self.graph
        z = sc.result.z[: g.n_road]
        lengths = np.array([rl.length_m / 1000.0 for rl in g.road_links])
        t0 = sc.params.t0[: g.n_road]
        phi = sc.result.phi
        delay_min = float(np.dot(z, phi[: g.n_road] - t0)) + float(np.dot(sc.result.z[g.n_road:], phi[g.n_road:]))
        return float(np.dot(z, lengths)) * CO2_KG_PER_VEH_KM + delay_min * CO2_KG_PER_VEH_MIN_DELAY

    def avg_queue_sec(self, sc: Scenario) -> float:
        g = self.graph
        zq = sc.result.z[g.n_road:]
        dq = sc.result.phi[g.n_road:] * 60.0
        if zq.sum() <= 0:
            return 0.0
        return float(np.dot(zq, dq) / zq.sum())

    def link_delay_min(self, sc: Scenario, link_idx: int) -> float:
        return float(sc.result.phi[link_idx])

    def queue_delay_min(self, sc: Scenario, q_idx: int) -> float:
        return float(sc.result.phi[self.graph.n_road + q_idx])

    def edge_delays(self, sc: Scenario) -> np.ndarray:
        return delays(sc.result.z, sc.params)


_ENGINE: BraessEngine | None = None
_ENGINE_LOCK = threading.Lock()


def get_engine() -> BraessEngine:
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            _ENGINE = BraessEngine()
        return _ENGINE
