"""STPT lines on the corridor: live SMTT polylines map-matched to corridor links.

A link belongs to a line when its start, middle and end points all lie within 30 m of the
line's polyline and the polyline runs the same way (bearing within 50°). Buses per hour
come from the real SMTT timetable at the matched stop nearest the corridor, when the
live feed is reachable; otherwise they are left empty (never guessed).
"""
from __future__ import annotations

import math
from typing import Any

from app.corridor import config
from app.corridor.osm_network import CorridorNetwork, bearing_deg, haversine_m
from app.services import pmt_client


def _seg_dist_m(p, a, b) -> float:
    kx = 111_320 * math.cos(math.radians(p[1]))
    ax, ay = (a[0] - p[0]) * kx, (a[1] - p[1]) * 110_540
    bx, by = (b[0] - p[0]) * kx, (b[1] - p[1]) * 110_540
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / L2))
    return math.hypot(ax + t * dx, ay + t * dy)


def _nearest_seg(p, line):
    best = (1e18, 0)
    for i in range(len(line) - 1):
        d = _seg_dist_m(p, line[i], line[i + 1])
        if d < best[0]:
            best = (d, i)
    return best


def match_links(net: CorridorNetwork, polyline: list[list[float]], tol_m: float = 30.0) -> list[str]:
    s, w, n, e = net.source["bbox"]
    pts = [p for p in polyline if s - 0.003 <= p[1] <= n + 0.003 and w - 0.003 <= p[0] <= e + 0.003]
    if len(pts) < 2:
        return []
    out = []
    for l in net.links:
        g = l.geometry
        samples = [g[0], g[len(g) // 2], g[-1]]
        ok = True
        for p in samples:
            d, i = _nearest_seg(p, pts)
            if d > tol_m:
                ok = False
                break
        if not ok:
            continue
        _, i = _nearest_seg(g[len(g) // 2], pts)
        lb, pb = l.bearing, bearing_deg(tuple(pts[i]), tuple(pts[i + 1]))
        if abs((lb - pb + 180) % 360 - 180) <= 50:
            out.append(l.id)
    return out


def live_lines() -> dict[str, dict]:
    """shortName → SMTT route info (id, colour, polyline per direction, stops) from the transit API."""
    net, prov = pmt_client.get_transit_network()
    if not pmt_client.available(prov) or not net.get("routes"):
        return {}
    stops_by_route: dict[str, list[dict]] = {}
    for st in net.get("stops", []):
        for rid in st.get("routeIds", []) or []:
            stops_by_route.setdefault(rid, []).append(st)
    paths: dict[str, dict[int, list[list[float]]]] = {}
    for pth in net.get("paths", []):
        try:
            paths.setdefault(pth["routeId"], {})[int(pth.get("directionId", 0))] = pmt_client.decode_polyline(pth["polyline"])
        except Exception:
            continue
    out = {}
    for r in net["routes"]:
        rid = r["id"]
        color = str(r.get("color") or "")
        out[r["shortName"]] = {
            "routeId": rid,
            "type": int(r.get("type", 3)),
            "color": ("#" + color) if color and not color.startswith("#") else (color or None),
            "longName": r.get("longName"),
            "polylines": paths.get(rid, {}),
            "stops": stops_by_route.get(rid, []),
        }
    return out


def nearest_stop(stops: list[dict], point: list[float]) -> dict | None:
    best = None
    for st in stops:
        try:
            d = haversine_m((float(st["lon"]), float(st["lat"])), (float(point[0]), float(point[1])))
        except (KeyError, TypeError, ValueError):
            continue
        if best is None or d < best[0]:
            best = (d, st)
    return best[1] if best else None


def corridor_lines(net: CorridorNetwork) -> list[dict[str, Any]]:
    """Live STPT lines that run through the corridor, with their matched links per direction."""
    lines = []
    for short, info in live_lines().items():
        for direction, poly in (info.get("polylines") or {}).items():
            links = match_links(net, poly)
            if len(links) < 3:
                continue
            lines.append({
                "routeId": info["routeId"], "shortName": short, "type": info["type"], "color": info["color"],
                "longName": info.get("longName"), "direction": direction, "links": links,
                "stops": info.get("stops", []), "polyline": poly,
            })
    return lines


def buses_per_hour(route_id: str, stops: list[dict], links_geom: list[list[float]],
                   start: str | None = None, end: str | None = None) -> tuple[int | None, str, str | None]:
    """Departures in the simulated hour [start, end) at the line's stop nearest the matched corridor section."""
    if not stops or not links_geom:
        return None, "no live timetable", None
    mid = links_geom[len(links_geom) // 2]
    stop = nearest_stop(stops, mid)
    if not stop:
        return None, "no live timetable", None
    tt, prov = pmt_client.get_stop_timetable(stop["id"])
    if not pmt_client.available(prov):
        return None, "no live timetable", None
    times = [t for line in tt.get("lines", []) if line.get("routeId") == route_id for t in line.get("times", [])]
    start, end = start or config.CORRIDOR.peak_start, end or config.CORRIDOR.peak_end
    n = sum(1 for t in times if start <= t < end)
    name = stop.get("name", stop["id"])
    return n, f"SMTT timetable · {name} · {tt.get('date')}", name
