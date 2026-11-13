"""Dual-mode route recommendations after an intervention.

* Car: re-equilibrated routes of every OD pair that touched the edited street —
  the throttled Braess cut-through vs. the arterials that absorbed the flow.
* STPT: lines along the corridor, with corridor run time before/after (a bus
  lane lets buses bypass BPR congestion and the phantom queue, running at t0).
* Bike: A* over the street graph between corridor endpoints, preferring
  protected infrastructure; protected share before/after.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import networkx as nx
import numpy as np

from app.config import TIMEZONE
from app.engine.braess_detector import BraessEngine, Scenario
from app.engine.extended_graph import CAR
from app.services import seed_timisoara as seed

BUS_SPEED_FACTOR = {0: 1.0, 3: 1.12, 11: 1.10}      # vehicle slower than car at free flow
CONGESTION_EXPOSURE = {0: 0.45, 3: 1.0, 11: 1.0}    # trams partly run on own track
DWELL_MIN_PER_STOP = 0.35
BIKE_SPEED_PROTECTED_KMH = 17.0
BIKE_SPEED_MIXED_KMH = 13.0


# ---------------------------------------------------------------------------
def _now() -> datetime:
    try:
        return datetime.now(ZoneInfo(TIMEZONE))
    except Exception:
        from datetime import timezone
        return datetime.now(timezone(timedelta(hours=2)))


def next_departures(first: str, freq_per_hour: float, n: int = 3, now: datetime | None = None) -> list[str]:
    now = now or _now()
    h, m = map(int, first.split(":"))
    start = now.replace(hour=h, minute=m, second=0, microsecond=0)
    last = now.replace(hour=23, minute=15, second=0, microsecond=0)
    headway = 60.0 / max(freq_per_hour, 0.1)
    if now < start:
        t = start
    else:
        k = math.ceil((now - start).total_seconds() / 60.0 / headway)
        t = start + timedelta(minutes=k * headway)
    out = []
    while len(out) < n:
        if t > last:  # service over → tomorrow's first departures
            start = start + timedelta(days=1)
            t = start
        out.append(t.strftime("%H:%M"))
        t += timedelta(minutes=headway)
    return out


def _point_seg_dist_m(p: list[float], a: list[float], b: list[float]) -> float:
    lat0 = math.radians(p[1])
    kx, ky = 111_320 * math.cos(lat0), 110_540

    def xy(q):
        return ((q[0] - p[0]) * kx, (q[1] - p[1]) * ky)

    ax, ay = xy(a)
    bx, by = xy(b)
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / L2))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(cx, cy)


def dist_to_polyline_m(p: list[float], coords: list[list[float]]) -> float:
    if len(coords) == 1:
        return seed.haversine_m(tuple(p), tuple(coords[0]))
    return min(_point_seg_dist_m(p, a, b) for a, b in zip(coords[:-1], coords[1:]))


# ---------------------------------------------------------------------------
class RouteRecommender:
    def __init__(self, engine: BraessEngine):
        self.engine = engine
        self.g = engine.graph
        self.ivelo = seed.ivelo_stations()
        # (from_node, to_node) → road link index
        self.link_by_nodes = {(rl.from_node, rl.to_node): i for i, rl in enumerate(self.g.road_links)}
        self.lines = []
        for line in seed.STPT_LINES:
            links = [self.link_by_nodes[(a, b)] for a, b in zip(line["nodes"][:-1], line["nodes"][1:])]
            self.lines.append({**line, "links": links})

    # ------------------------------------------------------------------ car
    def car_routes(self, base: Scenario, new: Scenario, link_ids: list[str], max_arterials: int = 3) -> list[dict]:
        g, eng = self.g, self.engine
        idxs = [g.road_index[l] for l in link_ids]
        touched = np.zeros(len(g.paths), dtype=bool)
        for li in idxs:
            touched |= eng.path_uses_road[:, li]
        ods = sorted({int(eng.od_of_path[r]) for r in np.where(touched & (base.result.x > 1.0))[0]})
        routes: list[dict] = []
        throttled: list[dict] = []
        arterials: list[dict] = []
        for k in ods:
            od = g.od_pairs[k]
            dem = max(float(base.demand[k]), 1e-9)
            s, n = eng.system.starts[k], eng.system.counts[k]
            for r in range(s, s + n):
                path = g.paths[r]
                old_x, new_x = float(base.result.x[r]), float(new.result.x[r]) if new.active[r] else 0.0
                old_t = float(base.result.path_cost[r])
                new_t = float(new.result.path_cost[r])
                item = {
                    "id": f"{od.id}_R{r - s + 1}",
                    "name": g.path_name(path),
                    "odLabel": od.label,
                    "oldTimeMin": round(old_t, 2),
                    "newTimeMin": round(new_t, 2),
                    "timeSavedMin": round(old_t - new_t, 2),
                    "flowSharePct": round(new_x / dem * 100.0, 1),
                    "oldFlowSharePct": round(old_x / dem * 100.0, 1),
                    "deltaFlowVehH": round(new_x - old_x, 1),
                    "filteredFromNavigation": bool(not new.active[r]),
                    "coordinates": g.path_coordinates(path),
                }
                if touched[r]:
                    item["role"] = "throttled_braess_cut_through"
                    if old_x > 1.0:
                        throttled.append(item)
                elif new_x > 1.0 or old_x > 1.0:
                    item["role"] = "recommended_arterial"
                    arterials.append(item)
        throttled.sort(key=lambda r: r["deltaFlowVehH"])
        arterials.sort(key=lambda r: (-r["deltaFlowVehH"], r["newTimeMin"]))
        routes.extend(throttled[:2])
        routes.extend(arterials[:max_arterials])
        return routes

    # ------------------------------------------------------------------ STPT
    def _line_time(self, line: dict, sc: Scenario) -> float:
        g = self.g
        typ = line["type"]
        exposure = CONGESTION_EXPOSURE[typ]
        speed = BUS_SPEED_FACTOR[typ]
        t = 0.0
        links = line["links"]
        for j, li in enumerate(links):
            rl = g.road_links[li]
            lanes = sc.lane_overrides.get(rl.id, rl.lanes)
            t0 = rl.t0_min
            phi = float(sc.result.phi[li])
            has_bus_lane = "bus" in lanes
            # Bus lane: bypass BPR congestion Φ_i(z_i) − t0 and run at free flow.
            t += t0 * speed + (0.0 if has_bus_lane else exposure * (phi - t0))
            if j + 1 < len(links):
                q = g.movement_queue.get((li, links[j + 1]))
                if q is not None:
                    d0 = float(sc.params.d0[q])
                    dq = float(sc.result.phi[g.n_road + q])
                    # Bus lane on the approach: queue jump → only the low-flow wait d0.
                    t += d0 + (0.0 if has_bus_lane else exposure * (dq - d0))
        t += DWELL_MIN_PER_STOP * (len(line["nodes"]) - 1)
        return t

    def stpt_routes(self, base: Scenario, new: Scenario, link_ids: list[str], limit: int = 5) -> list[dict]:
        g = self.g
        idx = {g.road_index[l] for l in link_ids}
        twins = {g.road_index[g.link(l).twin_id] for l in link_ids if g.link(l).twin_id in g.road_index}
        nodes = {g.road_links[i].from_node for i in idx} | {g.road_links[i].to_node for i in idx}

        def score(line):
            on = len(idx & set(line["links"]))
            near = len(nodes & set(line["nodes"]))
            twin = len(twins & set(line["links"]))
            return (on, twin, near)

        ranked = sorted(self.lines, key=score, reverse=True)
        chosen = [l for l in ranked if score(l) != (0, 0, 0)][:limit] or ranked[:2]
        from app.services import live_data  # local import: services depend on engine, not vice versa

        live = live_data.live_lines()
        ticket, _ = live_data.fares()
        c = g.link(link_ids[0]).coords if link_ids else [[21.2285, 45.7537]]
        mid = [(c[0][0] + c[-1][0]) / 2, (c[0][1] + c[-1][1]) / 2]
        out = []
        now = _now()
        for line in chosen:
            old_t = self._line_time(line, base)
            new_t = self._line_time(line, new)
            info = live.get(line["shortName"], {})
            schematic = [g.nodes[n]["coordinates"] for n in line["nodes"]]
            poly = (info.get("polylines") or {}).get(0)
            stops = [
                {"stopId": f"{line['routeId']}_S{i + 1:02d}", "name": g.nodes[n]["name"],
                 "coordinates": g.nodes[n]["coordinates"]}
                for i, n in enumerate(line["nodes"])
            ]
            departures, dep_src = None, "schedule model"
            if info.get("stops"):
                live_stops = live_data.stops_along(info["stops"], poly) if poly else info["stops"]
                if live_stops:
                    stops = [{"stopId": str(st["id"]), "name": st.get("name", ""),
                              "coordinates": [float(st["lon"]), float(st["lat"])]} for st in live_stops]
                near = live_data.nearest_stop(live_stops or info["stops"], mid)
                if near:
                    departures = live_data.live_next_departures(info["routeId"], near)
                    if departures:
                        dep_src = f"SMTT timetable · {near.get('name', near['id'])}"
            out.append({
                "routeId": info.get("routeId", line["routeId"]),
                "shortName": line["shortName"],
                "type": info.get("type", line["type"]),
                "color": info.get("color") or line["color"],
                "headsign": line["headsign"],
                "longName": info.get("longName"),
                "oldCorridorTimeMin": round(old_t, 1),
                "newCorridorTimeMin": round(new_t, 1),
                "frequencyPerHour": line["frequencyPerHour"],
                "nextDepartures": departures or next_departures(line["firstDeparture"], line["frequencyPerHour"], 3, now),
                "departuresSource": dep_src,
                "ticketCostRon": ticket,
                "usesEditedStreet": bool(idx & set(line["links"])),
                "coordinates": poly or schematic,
                "geometrySource": "SMTT GTFS (live)" if poly else "schematic",
                "stops": stops,
            })
        return out

    def line_gain_summary(self, base: Scenario, new: Scenario) -> tuple[int, list[dict]]:
        riders = 0
        gains = []
        for line in self.lines:
            old_t, new_t = self._line_time(line, base), self._line_time(line, new)
            if old_t - new_t > 0.05:
                riders += int(line["frequencyPerHour"] * seed.VEHICLE_CAPACITY[line["type"]])
                gains.append({"shortName": line["shortName"], "oldMin": old_t, "newMin": new_t})
        return riders, gains

    # ------------------------------------------------------------------ bike
    def _bike_graph(self, sc: Scenario) -> nx.Graph:
        g = self.g
        G = nx.Graph()
        z = sc.result.z
        for i, rl in enumerate(g.road_links):
            lanes = sc.lane_overrides.get(rl.id, rl.lanes)
            protected = rl.cycleway or "bike" in lanes
            vc = z[i] / max(rl.capacity, 1.0)
            # stress-weighted length: protected lanes are preferred, busy mixed traffic avoided
            w = rl.length_m * (0.65 if protected else 1.0 + 0.8 * min(vc, 1.5))
            key = (rl.from_node, rl.to_node) if rl.from_node < rl.to_node else (rl.to_node, rl.from_node)
            if G.has_edge(*key):
                e = G.edges[key]
                e["protected"] = e["protected"] or protected
                e["w"] = min(e["w"], w)
            else:
                G.add_edge(*key, w=w, protected=protected, length=rl.length_m, links=[i])
        return G

    def _astar(self, G: nx.Graph, o: str, d: str) -> list[str]:
        coords = {n: self.g.nodes[n]["coordinates"] for n in G.nodes}

        def h(a, b):
            return seed.haversine_m(tuple(coords[a]), tuple(coords[b])) * 0.65

        return nx.astar_path(G, o, d, heuristic=h, weight="w")

    def _bike_metrics(self, G: nx.Graph, nodes: list[str]) -> dict[str, Any]:
        length = prot = time_h = 0.0
        for a, b in zip(nodes[:-1], nodes[1:]):
            e = G.edges[a, b]
            length += e["length"]
            if e["protected"]:
                prot += e["length"]
                time_h += e["length"] / 1000.0 / BIKE_SPEED_PROTECTED_KMH
            else:
                time_h += e["length"] / 1000.0 / BIKE_SPEED_MIXED_KMH
        coords = [self.g.nodes[n]["coordinates"] for n in nodes]
        return {"length": length, "protected_pct": prot / length * 100 if length else 0.0,
                "time_min": time_h * 60.0, "coords": coords}

    def bike_routes(self, base: Scenario, new: Scenario, link_ids: list[str], preferred: str | None = None,
                    limit: int = 2) -> list[dict]:
        g = self.g
        Gb, Ga = self._bike_graph(base), self._bike_graph(new)
        mids = []
        for l in link_ids:
            c = g.link(l).coords
            mids.append([(c[0][0] + c[-1][0]) / 2, (c[0][1] + c[-1][1]) / 2])
        ranked = []
        for corr in seed.BIKE_CORRIDORS:
            before = self._bike_metrics(Gb, self._astar(Gb, corr["origin"], corr["destination"]))
            after = self._bike_metrics(Ga, self._astar(Ga, corr["origin"], corr["destination"]))
            dist = min((dist_to_polyline_m(m, after["coords"]) for m in mids), default=1e9)
            dist = min(dist, min((dist_to_polyline_m(m, before["coords"]) for m in mids), default=1e9))
            pri = 0 if corr["id"] == preferred else 1
            ranked.append((pri, dist, corr, before, after))
        ranked.sort(key=lambda t: (t[0], t[1]))
        out = []
        for pri, dist, corr, before, after in ranked[:limit]:
            stations = [s["name"] for s in self.ivelo if dist_to_polyline_m(s["coordinates"], after["coords"]) <= 220]
            out.append({
                "routeId": corr["id"],
                "name": corr["name"],
                "origin": corr["originName"],
                "destination": corr["destinationName"],
                "lengthKm": round(after["length"] / 1000.0, 2),
                "timeMin": round(after["time_min"], 1),
                "oldTimeMin": round(before["time_min"], 1),
                "protectedPctBefore": round(before["protected_pct"], 1),
                "protectedPctAfter": round(after["protected_pct"], 1),
                "iveloStationsOnRoute": stations,
                "distanceToEditedStreetM": round(dist, 0),
                "coordinates": after["coords"],
            })
        return out


def lanes_car_count(lanes: list[str]) -> int:
    return sum(1 for l in lanes if l == CAR)
