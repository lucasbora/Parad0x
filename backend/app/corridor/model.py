"""Corridor model: real OSM network + field data → before/after results for one lane change."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from app.corridor import config, inputs
from app.corridor.assignment import AssignmentResult, LinkCosts, Network, assign
from app.corridor.config import ASSUMPTIONS
from app.corridor.demand import GateMatrix, furness
from app.corridor.osm_network import CorridorNetwork, compass, load_network

USES = ("bus", "bike", "sidewalk", "closed")


@dataclass
class LaneChange:
    link_id: str
    car_lanes_after: int
    use: str            # what the removed lane becomes: bus | bike | sidewalk | closed


class NeedsData(Exception):
    def __init__(self, status: dict[str, Any]):
        super().__init__("field data missing")
        self.status = status


class CorridorModel:
    def __init__(self, input_dir: Path | None = None):
        self.input_dir = input_dir or config.INPUT_DIR
        self.net: CorridorNetwork = load_network()
        ids = list(self.net.nodes)
        self.node_idx = {nid: i for i, nid in enumerate(ids)}
        self.solver_net = Network(len(ids), [self.node_idx[l.from_node] for l in self.net.links],
                                  [self.node_idx[l.to_node] for l in self.net.links])
        self.fd = inputs.load_field_data(self.net, self.input_dir)
        self.status = inputs.data_status(self.net, self.fd, self.input_dir)
        self._cache: dict[Any, Any] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ inputs
    def car_lanes(self, link_id: str) -> tuple[int, str]:
        if link_id in self.fd.lanes:
            return self.fd.lanes[link_id][0], "field check"
        l = self.net.link(link_id)
        return l.car_lanes, l.lanes_source

    def signal(self, link_id: str) -> tuple[float, float, str] | None:
        """(cycle_s, green_ratio, source) for the signal at the END of ``link_id``, or None."""
        l = self.net.link(link_id)
        node = self.net.nodes[l.to_node]
        if not node.signalized:
            return None
        if (node.id, link_id) in self.fd.signals:
            c, g, src = self.fd.signals[(node.id, link_id)]
            return c, g / c, src or "field timing"
        return ASSUMPTIONS["signal_cycle_s"], ASSUMPTIONS["green_ratio"], "assumption"

    def costs(self, changes: list[LaneChange]) -> tuple[LinkCosts, np.ndarray]:
        ch = {c.link_id: c for c in changes}
        n = len(self.net.links)
        fixed, k, cap, beta = np.zeros(n), np.zeros(n), np.zeros(n), np.full(n, ASSUMPTIONS["bpr_beta"])
        usable = np.ones(n, dtype=bool)
        for i, l in enumerate(self.net.links):
            lanes = ch[l.id].car_lanes_after if l.id in ch else self.car_lanes(l.id)[0]
            t0 = l.t0_min
            sig = self.signal(l.id)
            if sig:
                cycle, g, _ = sig
                uniform_delay_min = cycle * (1 - g) ** 2 / 2 / 60.0      # Webster uniform delay (x → 0)
                per_lane = ASSUMPTIONS["saturation_flow_veh_h_per_lane"] * g
            else:
                uniform_delay_min = 0.0
                per_lane = ASSUMPTIONS["unsignalized_capacity_veh_h_per_lane"]
            fixed[i] = t0 + uniform_delay_min
            k[i] = ASSUMPTIONS["bpr_alpha"] * t0
            cap[i] = max(lanes, 0) * per_lane if lanes > 0 else 1.0
            if lanes <= 0:
                usable[i] = False
        return LinkCosts(fixed, k, cap, beta), usable

    def free_flow_gate_times(self) -> dict[tuple[str, str], float]:
        costs, usable = self.costs([])
        w = costs.fixed
        g = csr_matrix((w[usable], (self.solver_net.link_from[usable], self.solver_net.link_to[usable])),
                       shape=(self.solver_net.n_nodes,) * 2)
        gates = self.net.gates
        dist = dijkstra(g, directed=True, indices=[self.node_idx[x.node] for x in gates])
        return {(a.id, b.id): float(dist[i, self.node_idx[b.node]]) for i, a in enumerate(gates) for b in gates}

    def test_gate_flows(self) -> tuple[dict[str, float], dict[str, float]]:
        """TEST DATA ONLY: half the capacity of every gate's entering/leaving road.

        Used to try the app before field counts exist. Every response built on it carries
        ``testData: true`` and the UI shows a "not real measurements" banner.
        """
        cap = self.costs([])[0].cap
        g_in = {g.id: 0.5 * float(cap[self.net.link_index[g.in_link]]) for g in self.net.gates if g.in_link}
        g_out = {g.id: 0.5 * float(cap[self.net.link_index[g.out_link]]) for g in self.net.gates if g.out_link}
        return g_in, g_out

    def gate_matrix(self, test: bool = False) -> GateMatrix:
        if test and not self.status["ready"]:
            if "matrix_test" not in self._cache:
                g_in, g_out = self.test_gate_flows()
                self._cache["matrix_test"] = furness(g_in, g_out, self.free_flow_gate_times(),
                                                     ASSUMPTIONS["gravity_beta_per_min"])
            return self._cache["matrix_test"]
        if not self.status["ready"]:
            raise NeedsData(self.status)
        if "matrix" not in self._cache:
            self._cache["matrix"] = furness(self.fd.gate_in, self.fd.gate_out, self.free_flow_gate_times(),
                                            ASSUMPTIONS["gravity_beta_per_min"])
        return self._cache["matrix"]

    def is_test(self, test: bool) -> bool:
        """Test data is used only when asked for AND no real counts exist."""
        return test and not self.status["ready"]

    def ods(self, scale: float = 1.0, test: bool = False) -> list[tuple[int, int, float]]:
        m = self.gate_matrix(test)
        gnode = {g.id: self.node_idx[g.node] for g in self.net.gates}
        return [(gnode[o], gnode[d], float(m.trips[i, j]) * scale)
                for i, o in enumerate(m.origins) for j, d in enumerate(m.destinations) if m.trips[i, j] > 1e-6]

    def solve(self, changes: list[LaneChange], scale: float = 1.0, test: bool = False) -> AssignmentResult:
        test = self.is_test(test)
        key = (tuple((c.link_id, c.car_lanes_after) for c in sorted(changes, key=lambda c: c.link_id)),
               round(scale, 4), test)
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        costs, usable = self.costs(changes)
        res = assign(self.solver_net, costs, self.ods(scale, test), usable=usable, rel_gap=1e-5, max_iter=400)
        with self._lock:
            self._cache[key] = res
        return res

    # ------------------------------------------------------------------ results
    def baseline(self, test: bool = False) -> dict[str, Any]:
        """Current-state equilibrium: what the coloured map shows before any change."""
        res = self.solve([], 1.0, test)
        free = self.costs([])[0].fixed
        return {
            "testData": self.is_test(test),
            "totalVehMin": round(res.total_time, 0),
            "links": [{"id": l.id, "flow": round(float(res.flow[i]), 1), "timeSec": round(float(res.cost[i]) * 60, 1),
                       "freeTimeSec": round(float(free[i]) * 60, 1)} for i, l in enumerate(self.net.links)],
        }

    def compare(self, changes: list[LaneChange], scale: float = 1.0, test: bool = False) -> dict[str, Any]:
        for c in changes:
            if c.link_id not in self.net.link_index:
                raise KeyError(c.link_id)
            if c.use not in USES:
                raise ValueError(f"use must be one of {USES}")
        test = self.is_test(test)
        before = self.solve([], scale, test)
        after = self.solve(changes, scale, test)
        free = self.costs([])[0].fixed
        net = self.net
        links = []
        for i, l in enumerate(net.links):
            links.append({
                "id": l.id, "flowBefore": round(float(before.flow[i]), 1), "flowAfter": round(float(after.flow[i]), 1),
                "deltaFlow": round(float(after.flow[i] - before.flow[i]), 1),
                "timeBeforeSec": round(float(before.cost[i]) * 60, 1), "timeAfterSec": round(float(after.cost[i]) * 60, 1),
                "freeTimeSec": round(float(free[i]) * 60, 1),
            })
        # where traffic goes: biggest change per street + heading
        by_street: dict[tuple[str, str], dict] = {}
        for i, l in enumerate(net.links):
            d = float(after.flow[i] - before.flow[i])
            key = (l.street, compass(l.bearing))
            if key not in by_street or abs(d) > abs(by_street[key]["deltaFlow"]):
                by_street[key] = {"street": l.street, "heading": key[1], "deltaFlow": round(d, 0),
                                  "flowBefore": round(float(before.flow[i]), 0), "flowAfter": round(float(after.flow[i]), 0),
                                  "linkId": l.id}
        shifts = sorted((v for v in by_street.values() if abs(v["deltaFlow"]) >= 20), key=lambda v: -abs(v["deltaFlow"]))
        # intersections: flow-weighted extra delay on approaches
        inter = []
        for n in net.junctions:
            inc = [i for i, l in enumerate(net.links) if l.to_node == n.id]
            def avg(res):
                f = res.flow[inc]
                extra = (res.cost[inc] - np.array([net.links[i].t0_min for i in inc])) * 60
                return float(np.dot(f, extra) / f.sum()) if f.sum() > 1 else 0.0
            b, a = avg(before), avg(after)
            inter.append({"nodeId": n.id, "name": n.name, "signalized": n.signalized, "delayBeforeSec": round(b, 1),
                          "delayAfterSec": round(a, 1), "lng": n.lng, "lat": n.lat})
        inter.sort(key=lambda x: -abs(x["delayAfterSec"] - x["delayBeforeSec"]))
        # car travel time between the busiest gate pairs
        m = self.gate_matrix(test)
        gates = {g.id: g for g in net.gates}
        pairs = sorted(((m.trips[i, j], o, d) for i, o in enumerate(m.origins) for j, d in enumerate(m.destinations)),
                       reverse=True)[:6]
        routes = []
        for q, o, d in pairs:
            key = (self.node_idx[gates[o].node], self.node_idx[gates[d].node])
            routes.append({"from": f"{gates[o].street} ({gates[o].side})", "to": f"{gates[d].street} ({gates[d].side})",
                           "fromGate": o, "toGate": d, "vehH": round(float(q) * scale, 0),
                           "minutesBefore": round(before.od_time[key], 2), "minutesAfter": round(after.od_time[key], 2)})
        removed = any(c.car_lanes_after < self.car_lanes(c.link_id)[0] for c in changes)
        change_pct = (after.total_time - before.total_time) / before.total_time * 100
        return {
            "testData": test,
            "totals": {
                "vehMinBefore": round(before.total_time, 0), "vehMinAfter": round(after.total_time, 0),
                "changePct": round(change_pct, 2),
                "demandVehH": round(sum(q for _, _, q in self.ods(scale, test)), 0),
            },
            # Braess's paradox: car capacity was taken away, yet total time in traffic went DOWN.
            "braess": {"detected": bool(removed and change_pct < -0.05), "carCapacityRemoved": removed,
                       "totalChangePct": round(change_pct, 2)},
            "carRoutes": routes,
            "trafficShifts": shifts[:8],
            "intersections": inter[:6],
            "buses": self.bus_results(changes, before, after),
            "links": links,
            "solver": {"gapBefore": before.rel_gap, "gapAfter": after.rel_gap, "iterationsAfter": after.iterations,
                       "msAfter": round(after.elapsed_ms, 1)},
            "demandScale": scale,
        }

    def bus_results(self, changes: list[LaneChange], before: AssignmentResult, after: AssignmentResult) -> list[dict]:
        from app.corridor import transit

        if "lines" not in self._cache:
            main = {l.id for l in self.net.links if l.street in config.CORRIDOR.main_streets}
            # only lines that actually run along the corridor's main streets
            self._cache["lines"] = [ln for ln in transit.corridor_lines(self.net) if len(main & set(ln["links"])) >= 1]
            self._cache["free_fixed"] = self.costs([])[0].fixed
        bus_links = {c.link_id for c in changes if c.use == "bus"}
        factor = ASSUMPTIONS["bus_speed_factor"]
        free_fixed = self._cache["free_fixed"]
        out = []
        for line in self._cache["lines"]:
            idx = [self.net.link_index[x] for x in line["links"]]

            def t(res, with_lane):
                total = 0.0
                for i in idx:
                    l = self.net.links[i]
                    has_lane = l.bus_lane or (with_lane and l.id in bus_links)
                    # bus lane: no congestion, signal wait only (fixed part); else same time as cars
                    total += (free_fixed[i] if has_lane else res.cost[i]) * factor
                return float(total)

            before_min, after_min = t(before, False), t(after, True)
            geom = [p for i in idx for p in self.net.links[i].geometry]
            per_hour, src = transit.buses_per_hour(line["routeId"], line["stops"], geom)
            out.append({"shortName": line["shortName"], "routeId": line["routeId"], "type": int(line["type"]),
                        "color": line["color"], "longName": line["longName"], "direction": line["direction"],
                        "minutesBefore": round(before_min, 2), "minutesAfter": round(after_min, 2),
                        "usesChangedStreet": bool(bus_links & set(line["links"])),
                        "busesPerHour": per_hour, "busesPerHourSource": src, "linkIds": line["links"]})
        out.sort(key=lambda b: (not b["usesChangedStreet"], b["minutesAfter"] - b["minutesBefore"]))
        return out

    def assumptions_in_use(self) -> list[dict[str, Any]]:
        sig_assumed = sum(1 for l in self.net.links if (s := self.signal(l.id)) and s[2] == "assumption")
        sig_total = sum(1 for l in self.net.links if self.signal(l.id))
        lanes_unverified = sum(1 for l in self.net.links if l.id not in self.fd.lanes)
        speed_assumed = sum(1 for l in self.net.links if l.speed_source != "osm")
        return [
            {"what": "Signal timings", "value": f"cycle {ASSUMPTIONS['signal_cycle_s']:.0f} s, green {ASSUMPTIONS['green_ratio']:.0%}",
             "appliesTo": f"{sig_assumed}/{sig_total} signalized approaches", "replaceWith": "signal_timings.csv"},
            {"what": "Lane counts not checked on site", "value": "OpenStreetMap",
             "appliesTo": f"{lanes_unverified}/{len(self.net.links)} links", "replaceWith": "lane_checks.csv"},
            {"what": "Speed limit missing in OSM", "value": "50 km/h (RO urban)",
             "appliesTo": f"{speed_assumed}/{len(self.net.links)} links", "replaceWith": "OSM edit / lane_checks"},
            {"what": "Saturation flow", "value": f"{ASSUMPTIONS['saturation_flow_veh_h_per_lane']:.0f} veh/h/lane (HCM)",
             "appliesTo": "all signalized approaches", "replaceWith": "calibration"},
            {"what": "Congestion curve", "value": f"BPR α={ASSUMPTIONS['bpr_alpha']}, β={ASSUMPTIONS['bpr_beta']}",
             "appliesTo": "all links", "replaceWith": "calibration"},
            {"what": "Which gate cars leave by", "value": f"gravity model, β={ASSUMPTIONS['gravity_beta_per_min']}/min",
             "appliesTo": "OD split between counted gates", "replaceWith": "turn_counts.csv (calibration)"},
        ]


_MODEL: CorridorModel | None = None
_MODEL_KEY: tuple | None = None
_MODEL_LOCK = threading.Lock()


def _input_signature(d: Path) -> tuple:
    return tuple(sorted((p.name, p.stat().st_mtime_ns) for p in d.glob("*.csv"))) if d.exists() else ()


def get_model() -> CorridorModel:
    """Model is rebuilt automatically when any CSV in the input folder changes."""
    global _MODEL, _MODEL_KEY
    with _MODEL_LOCK:
        key = _input_signature(config.INPUT_DIR)
        if _MODEL is None or key != _MODEL_KEY:
            _MODEL = CorridorModel()
            _MODEL_KEY = key
        return _MODEL
