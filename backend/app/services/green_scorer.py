"""Multi-criteria suitability of each street for Bus / Bike / Tree reallocation (0–100).

bus   = 45 % STPT frequency on the street (both directions, saturating at 20 veh/h)
      + 35 % car congestion v/c (a bus lane pays off where cars queue)
      + 20 % spare width (≥ 2 car lanes)
bike  = 35 % gap-filling (no protected lane yet but one within 300 m)
      + 25 % i'velo station density within 400 m
      + 20 % calm traffic speed (≤ 40 km/h)
      + 20 % spare capacity (1 − v/c)
trees = 30 % landmark/POI density within 400 m
      + 25 % "Străzi și trotuare" resident reports nearby (normalised)
      + 25 % PM10 at the nearest air-quality station (normalised to 40 µg/m³)
      + 20 % curb parking that can become sidewalk
"""
from __future__ import annotations

import math

import numpy as np

from app.engine.extended_graph import ExtendedGraph
from app.services import seed_timisoara as seed


def _mid(coords: list[list[float]]) -> list[float]:
    return [(coords[0][0] + coords[-1][0]) / 2, (coords[0][1] + coords[-1][1]) / 2]


def _near(p: list[float], pts: list[list[float]], r: float) -> int:
    return sum(1 for q in pts if seed.haversine_m(tuple(p), tuple(q)) <= r)


def score_links(graph: ExtendedGraph, z: np.ndarray) -> dict[str, dict[str, int]]:
    freq_by_link: dict[tuple[str, str], float] = {}
    for line in seed.STPT_LINES:
        for a, b in zip(line["nodes"][:-1], line["nodes"][1:]):
            key = tuple(sorted((a, b)))
            freq_by_link[key] = freq_by_link.get(key, 0.0) + line["frequencyPerHour"]
    ivelo = [s["coordinates"] for s in seed.ivelo_stations()]
    pois = [p["coordinates"] for p in seed.POIS]
    cycle_mids = [_mid(graph.road_links[i].coords) for i, rl in enumerate(graph.road_links) if rl.cycleway]
    cycle_pts = [pt for cw in seed.OSM_CYCLEWAYS for pt in cw["coordinates"]] + cycle_mids

    out: dict[str, dict[str, int]] = {}
    for i, rl in enumerate(graph.road_links):
        mid = _mid(rl.coords)
        vc = float(z[i]) / max(rl.capacity, 1.0)
        freq = freq_by_link.get(tuple(sorted((rl.from_node, rl.to_node))), 0.0)
        bus = 0.45 * min(freq / 20.0, 1.0) + 0.35 * min(vc, 1.0) + 0.20 * (1.0 if rl.m_car >= 2 else 0.3)

        near_cycle = any(seed.haversine_m(tuple(mid), tuple(q)) <= 300 for q in cycle_pts)
        gap = 1.0 if (not rl.cycleway and near_cycle) else (0.4 if not rl.cycleway else 0.1)
        bike = (0.35 * gap + 0.25 * min(_near(mid, ivelo, 400) / 4.0, 1.0)
                + 0.20 * (1.0 if rl.speed_kmh <= 40 else 0.5) + 0.20 * max(0.0, 1.0 - min(vc, 1.0)))

        ses = seed.sesizari_for_point(mid[0], mid[1], 500)
        trot = ses["byCategory"].get("Străzi și trotuare", 0)
        aq = min(seed.AIR_QUALITY, key=lambda s: seed.haversine_m(tuple(mid), tuple(s["coordinates"])))
        trees = (0.30 * min(_near(mid, pois, 400) / 4.0, 1.0) + 0.25 * min(trot / 6.0, 1.0)
                 + 0.25 * min(aq["pm10"] / 40.0, 1.0) + 0.20 * (1.0 if rl.timpark_zone else 0.0))
        out[rl.id] = {"bus": int(round(100 * bus)), "bike": int(round(100 * bike)), "trees": int(round(100 * trees))}
    return out


def recommend_reallocation(scores: dict[str, int]) -> str:
    best = max(("bus", "bike", "trees"), key=lambda k: scores[k])
    return {"bus": "bus", "bike": "bike", "trees": "pedestrian_trees"}[best]


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v)) if not math.isnan(v) else lo
