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
from app.corridor.osm_network import CorridorNetwork, bearing_deg


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


def corridor_lines(net: CorridorNetwork) -> list[dict[str, Any]]:
    """Live STPT lines that run through the corridor, with their matched links per direction."""
    from app.services import live_data  # live SMTT feed (cached, offline-safe)

    lines = []
    for short, info in live_data.live_lines(wanted=None).items():
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


def buses_per_hour(route_id: str, stops: list[dict], links_geom: list[list[float]]) -> tuple[int | None, str]:
    """Departures in the peak hour at the line's stop nearest the matched corridor section."""
    from app.services import live_data, pmt_client

    if not stops or not links_geom:
        return None, "no live timetable"
    mid = links_geom[len(links_geom) // 2]
    stop = live_data.nearest_stop(stops, mid)
    if not stop:
        return None, "no live timetable"
    tt, prov = pmt_client.get_stop_timetable(stop["id"])
    if prov.source == "seed":
        return None, "no live timetable"
    times = [t for line in tt.get("lines", []) if line.get("routeId") == route_id for t in line.get("times", [])]
    n = sum(1 for t in times if config.CORRIDOR.peak_start <= t < config.CORRIDOR.peak_end)
    return n, f"SMTT timetable · {stop.get('name', stop['id'])} · {tt.get('date')}"
