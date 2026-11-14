"""Corridor model: OSM network + land-use demand (+ counts) → equilibrium, scenarios, results.

Demand per time-of-day profile is ESTIMATED from OpenStreetMap buildings and points of
interest (app.corridor.landuse / demand.landuse_od). Field counts CALIBRATE it:
gate counts replace the gateway estimate, link counts scale local demand. Turn counts and
travel times are kept apart to CHECK the model (calibration.py).
"""
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
from app.corridor.config import ASSUMPTIONS, DEFAULT_PROFILE, LANDUSE, PROFILES, SIDE_STREET_CLASSES
from app.corridor.demand import ODTable, landuse_od
from app.corridor.landuse import LandUse, load_landuse
from app.corridor.osm_network import CorridorNetwork, compass, load_network

USES = ("bus", "bike", "sidewalk", "closed")
BASE_GAP = 1e-5          # base state and user edits
BASE_MAX_ITER = 400


@dataclass
class LaneChange:
    link_id: str
    car_lanes_after: int
    use: str            # what the removed lane becomes: bus | bike | sidewalk | closed


class NeedsData(Exception):
    """Raised only where field data is indispensable (e.g. a calibration report)."""

    def __init__(self, status: dict[str, Any]):
        super().__init__("field data missing")
        self.status = status


def check_profile(profile: str | None) -> str:
    p = profile or DEFAULT_PROFILE
    if p not in PROFILES:
        raise ValueError(f"unknown profile {p!r}; use one of {', '.join(PROFILES)}")
    return p


class CorridorModel:
    def __init__(self, input_dir: Path | None = None):
        self.input_dir = input_dir or config.INPUT_DIR
        self.net: CorridorNetwork = load_network()
        self.landuse: LandUse = load_landuse()
        ids = list(self.net.nodes)
        self.node_idx = {nid: i for i, nid in enumerate(ids)}
        self.solver_net = Network(len(ids), [self.node_idx[l.from_node] for l in self.net.links],
                                  [self.node_idx[l.to_node] for l in self.net.links])
        self.fd = inputs.load_field_data(self.net, self.input_dir)
        self.status = inputs.data_status(self.net, self.fd, self.input_dir)
        self._cache: dict[Any, Any] = {}
        self._incoming: dict[str, np.ndarray] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ network inputs
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
                per_lane = (ASSUMPTIONS["side_street_capacity_veh_h_per_lane"] if l.highway in SIDE_STREET_CLASSES
                            else ASSUMPTIONS["unsignalized_capacity_veh_h_per_lane"])
            fixed[i] = t0 + uniform_delay_min
            k[i] = ASSUMPTIONS["bpr_alpha"] * t0
            cap[i] = lanes * per_lane if lanes > 0 else 1.0
            if lanes <= 0:
                usable[i] = False
        return LinkCosts(fixed, k, cap, beta), usable

    def _free_dist(self) -> dict[int, np.ndarray]:
        """Free-flow travel time (min) from every zone/gate node to every node."""
        if "free_dist" not in self._cache:
            costs, usable = self.costs([])
            g = csr_matrix((costs.fixed[usable], (self.solver_net.link_from[usable], self.solver_net.link_to[usable])),
                           shape=(self.solver_net.n_nodes,) * 2)
            src = sorted({self.node_idx[z.node] for z in self.landuse.zones} |
                         {self.node_idx[gt.node] for gt in self.net.gates})
            dist = dijkstra(g, directed=True, indices=src)
            self._cache["free_dist"] = {s: dist[i] for i, s in enumerate(src)}
        return self._cache["free_dist"]

    # ------------------------------------------------------------------ demand
    def demand_source(self, profile: str) -> str:
        return "calibrated" if self.fd.calibrated(profile) else "estimated"

    def _od_table(self, profile: str, local_multiplier: float) -> ODTable:
        cap = self.costs([])[0].cap
        dist = self._free_dist()
        return landuse_od(
            self.landuse.zones, self.net.gates, self.node_idx, lambda a, b: float(dist[a][b]),
            {g.id: float(cap[self.net.link_index[g.in_link]]) for g in self.net.gates if g.in_link},
            {g.id: float(cap[self.net.link_index[g.out_link]]) for g in self.net.gates if g.out_link},
            PROFILES[profile], LANDUSE,
            counted_in=self.fd.gate_in.get(profile), counted_out=self.fd.gate_out.get(profile),
            local_multiplier=local_multiplier)

    def od_table(self, profile: str = DEFAULT_PROFILE) -> ODTable:
        profile = check_profile(profile)
        key = ("od", profile)
        if key not in self._cache:
            k = self.calibrate_local(profile) if self.fd.link_counts.get(profile) else 1.0
            self._cache[key] = self._od_table(profile, k)
        return self._cache[key]

    def calibrate_local(self, profile: str, iterations: int = 4) -> float:
        """Scale local (land-use) demand so modelled flow matches link_counts.csv on those links."""
        counts = self.fd.link_counts[profile]
        idx = [self.net.link_index[l] for l in counts]
        target = sum(counts.values())
        k = 1.0
        for _ in range(iterations):
            od = self._od_table(profile, k)
            costs, usable = self.costs([])
            res = assign(self.solver_net, costs, self._ods_from(od, 1.0), usable=usable, rel_gap=1e-4, max_iter=200)
            modelled = float(res.flow[idx].sum())
            if modelled <= 1e-6:
                break
            k = float(np.clip(k * target / modelled, 0.2, 5.0))
        return k

    @staticmethod
    def _ods_from(od: ODTable, scale: float) -> list[tuple[int, int, float]]:
        acc: dict[tuple[int, int], float] = {}
        for i, r in enumerate(od.rows):
            for j, c in enumerate(od.cols):
                q = float(od.trips[i, j])
                if q > 1e-6 and r.node != c.node:
                    acc[(r.node, c.node)] = acc.get((r.node, c.node), 0.0) + q * scale
        return [(o, d, q) for (o, d), q in acc.items()]

    def ods(self, scale: float = 1.0, profile: str = DEFAULT_PROFILE, test: bool = False) -> list[tuple[int, int, float]]:
        return self._ods_from(self.od_table(profile), scale)

    # ------------------------------------------------------------------ solving
    def solve(self, changes: list[LaneChange], scale: float = 1.0, test: bool = False, profile: str = DEFAULT_PROFILE,
              rel_gap: float = BASE_GAP, max_iter: int = BASE_MAX_ITER,
              x0: tuple[np.ndarray, np.ndarray] | None = None) -> AssignmentResult:
        """Equilibrium for a set of lane changes. ``test`` is accepted for old callers and ignored."""
        profile = check_profile(profile)
        key = (tuple((c.link_id, c.car_lanes_after) for c in sorted(changes, key=lambda c: c.link_id)),
               round(scale, 4), profile, rel_gap)
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        costs, usable = self.costs(changes)
        if x0 is None and changes:
            base = self.solve([], scale, profile=profile)
            x0 = (base.flow, base.movement_flow)
        res = assign(self.solver_net, costs, self.ods(scale, profile), usable=usable, rel_gap=rel_gap,
                     max_iter=max_iter, x0=x0)
        with self._lock:
            self._cache[key] = res
        return res

    # ------------------------------------------------------------------ helpers for the map
    def junction_delays(self, res: AssignmentResult) -> dict[str, float]:
        """Flow-weighted extra wait (s) on the approaches of every intersection."""
        out = {}
        t0 = np.array([l.t0_min for l in self.net.links])
        for n in self.net.junctions:
            inc = self._incoming.get(n.id)
            if inc is None:
                inc = np.array([i for i, l in enumerate(self.net.links) if l.to_node == n.id], dtype=int)
                self._incoming[n.id] = inc
            f = res.flow[inc]
            out[n.id] = float(np.dot(f, (res.cost[inc] - t0[inc]) * 60) / f.sum()) if f.sum() > 1 else 0.0
        return out

    def path_coords(self, cost: np.ndarray, usable: np.ndarray, o: int, d: int) -> list[list[float]]:
        """Geometry of the shortest path o → d at the given link costs."""
        _, pred = self.solver_net.shortest_paths(cost, [o], usable)
        nodes = [d]
        while nodes[-1] != o:
            u = int(pred[0, nodes[-1]])
            if u < 0:
                return []
            nodes.append(u)
        nodes.reverse()
        coords: list[list[float]] = []
        for u, v in zip(nodes[:-1], nodes[1:]):
            g = self.net.links[self.solver_net.edge_link[(u, v)]].geometry
            coords.extend(g if not coords else g[1:])
        return coords

    # ------------------------------------------------------------------ results
    def scan(self, test: bool = False, profile: str = DEFAULT_PROFILE, workers: int | None = None) -> dict[str, Any]:
        from app.corridor.scan import run_scan

        return run_scan(self, check_profile(profile), workers=workers)

    def baseline(self, test: bool = False, profile: str = DEFAULT_PROFILE) -> dict[str, Any]:
        """Current-state equilibrium: what the coloured map shows before any change."""
        profile = check_profile(profile)
        res = self.solve([], 1.0, profile=profile)
        free = self.costs([])[0].fixed
        jd = self.junction_delays(res)
        od = self.od_table(profile)
        return {
            "testData": False,
            "profile": profile,
            "demandSource": self.demand_source(profile),
            "demandSummary": od.summary,
            "totalVehMin": round(res.total_time, 0),
            "solver": {"gap": res.rel_gap, "iterations": res.iterations, "ms": round(res.elapsed_ms, 1)},
            "junctions": [{"nodeId": k, "delaySec": round(v, 1)} for k, v in jd.items()],
            "links": [{"id": l.id, "flow": round(float(res.flow[i]), 1), "timeSec": round(float(res.cost[i]) * 60, 1),
                       "freeTimeSec": round(float(free[i]) * 60, 1)} for i, l in enumerate(self.net.links)],
        }

    def compare(self, changes: list[LaneChange], scale: float = 1.0, test: bool = False,
                profile: str = DEFAULT_PROFILE) -> dict[str, Any]:
        profile = check_profile(profile)
        for c in changes:
            if c.link_id not in self.net.link_index:
                raise KeyError(c.link_id)
            if c.use not in USES:
                raise ValueError(f"use must be one of {USES}")
        before = self.solve([], scale, profile=profile)
        after = self.solve(changes, scale, profile=profile)
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
        jb, ja = self.junction_delays(before), self.junction_delays(after)
        inter = [{"nodeId": n.id, "name": n.name, "signalized": n.signalized, "delayBeforeSec": round(jb[n.id], 1),
                  "delayAfterSec": round(ja[n.id], 1), "lng": n.lng, "lat": n.lat} for n in net.junctions]
        inter.sort(key=lambda x: -abs(x["delayAfterSec"] - x["delayBeforeSec"]))
        # car travel time for the busiest origin–destination pairs
        od = self.od_table(profile)
        pairs = sorted(((float(od.trips[i, j]), r, c) for i, r in enumerate(od.rows) for j, c in enumerate(od.cols)
                        if r.node != c.node), key=lambda t: -t[0])[:6]
        _, usable_before = self.costs([])
        _, usable_after = self.costs(changes)
        routes = []
        for q, r, c in pairs:
            key = (r.node, c.node)
            if key not in before.od_time or key not in after.od_time:
                continue
            routes.append({"from": r.label, "to": c.label, "fromGate": r.id, "toGate": c.id,
                           "vehH": round(q * scale, 0),
                           "minutesBefore": round(before.od_time[key], 2), "minutesAfter": round(after.od_time[key], 2),
                           "pathBefore": self.path_coords(before.cost, usable_before, *key),
                           "pathAfter": self.path_coords(after.cost, usable_after, *key)})
        removed = any(c.car_lanes_after < self.car_lanes(c.link_id)[0] for c in changes)
        change_pct = (after.total_time - before.total_time) / before.total_time * 100
        return {
            "testData": False,
            "profile": profile,
            "demandSource": self.demand_source(profile),
            "totals": {
                "vehMinBefore": round(before.total_time, 0), "vehMinAfter": round(after.total_time, 0),
                "changePct": round(change_pct, 2),
                "demandVehH": round(sum(q for _, _, q in self.ods(scale, profile)), 0),
            },
            # Braess's paradox: car capacity was taken away, yet total time in traffic went DOWN.
            "braess": {"detected": bool(removed and change_pct < -0.05), "carCapacityRemoved": removed,
                       "totalChangePct": round(change_pct, 2)},
            "carRoutes": routes,
            "junctions": [{"nodeId": k, "delayBeforeSec": round(jb[k], 1), "delayAfterSec": round(ja[k], 1)} for k in jb],
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
        lanes_assumed = sum(1 for l in self.net.links if l.lanes_source == "assumed" and l.id not in self.fd.lanes)
        speed_assumed = sum(1 for l in self.net.links if l.speed_source.startswith("assumed"))
        lu = self.landuse.summary
        car_share = f"{LANDUSE['car_share']:.0%}" + ("" if LANDUSE["car_share_verified"] else " (PMUD, unverified)")
        return [
            {"what": "Demand (where trips start and end)", "value": "OSM buildings + POIs → gravity model",
             "appliesTo": "all profiles without counts", "replaceWith": "gate_counts.csv / link_counts.csv"},
            {"what": "Residents per building", "value": f"{LANDUSE['m2_floor_per_resident']:.0f} m² floor / resident; "
                     f"untyped buildings {LANDUSE['yes_building_residential_share']:.0%} housing",
             "appliesTo": f"{lu.get('residentialBuildings', 0)} buildings ({lu.get('levelsFromOsm', 0)} with floors in OSM)",
             "replaceWith": "INS census / link_counts.csv"},
            {"what": "Car trips per resident", "value": f"{LANDUSE['trips_per_resident_day']} trips/day × car share "
                     f"{car_share} ÷ {LANDUSE['car_occupancy']} people/car",
             "appliesTo": "local demand", "replaceWith": "PMUD Timișoara / link_counts.csv"},
            {"what": "Through traffic at gateways", "value": f"{LANDUSE['through_share_of_capacity']:.0%} of the road's capacity",
             "appliesTo": f"{len(self.net.gates)} gateways", "replaceWith": "gate_counts.csv"},
            {"what": "Signal timings", "value": f"cycle {ASSUMPTIONS['signal_cycle_s']:.0f} s, green {ASSUMPTIONS['green_ratio']:.0%}",
             "appliesTo": f"{sig_assumed}/{sig_total} signalized approaches", "replaceWith": "signal_timings.csv"},
            {"what": "Lane counts", "value": f"OpenStreetMap ({lanes_assumed} from road-class defaults)",
             "appliesTo": f"{lanes_unverified}/{len(self.net.links)} links not checked on site", "replaceWith": "lane_checks.csv"},
            {"what": "Speed limit missing in OSM", "value": "road-class default",
             "appliesTo": f"{speed_assumed}/{len(self.net.links)} links", "replaceWith": "OSM edit / lane_checks"},
            {"what": "Saturation flow", "value": f"{ASSUMPTIONS['saturation_flow_veh_h_per_lane']:.0f} veh/h/lane (HCM); "
                     f"side streets {ASSUMPTIONS['side_street_capacity_veh_h_per_lane']:.0f}",
             "appliesTo": "all links", "replaceWith": "calibration"},
            {"what": "Congestion curve", "value": f"BPR α={ASSUMPTIONS['bpr_alpha']}, β={ASSUMPTIONS['bpr_beta']}",
             "appliesTo": "all links", "replaceWith": "calibration"},
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
