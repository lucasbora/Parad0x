"""Land-use driven OD demand generation (§9.2).

Each of the 12 OD pairs links two centroids with a land-use mix (residential,
office, school, retail, leisure). For a demand profile, production at the origin
and attraction at the destination are the land-use-weighted trip rates
(P_o, A_d). Both directions of a corridor share one gravity constant fixed by the
calibrated morning inbound demand B_c:

    raw_k(profile) = B_c · P_o(profile)·A_d(profile) / (P_in(morning)·A_in(morning))

and the matrix is then rescaled so the total equals level(profile) × the morning
total. The morning inbound matrix therefore equals the calibration exactly, and
the evening profile mirrors it through land use rather than by hand.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np

from app.config import TIMEZONE
from app.engine.extended_graph import ExtendedGraph
from app.services import seed_timisoara as seed

PRESETS = ("morning_rush", "evening_rush", "now", "weekend", "event_rush")

# Hour-of-day weekday profile (share of the AM peak) used by the "now" preset.
_HOURLY_LEVEL = [0.08, 0.05, 0.04, 0.04, 0.07, 0.18, 0.45, 0.85, 1.00, 0.78, 0.62, 0.62,
                 0.66, 0.66, 0.68, 0.78, 0.92, 1.00, 0.90, 0.70, 0.52, 0.38, 0.25, 0.14]


def _production(node: str, profile: str) -> float:
    mix = seed.CENTROID_LAND_USE[node]
    rates = seed.TRIP_RATES[profile]["P"]
    return sum(w * rates[lu] for lu, w in mix.items())


def _attraction(node: str, profile: str) -> float:
    mix = seed.CENTROID_LAND_USE[node]
    rates = seed.TRIP_RATES[profile]["A"]
    return sum(w * rates[lu] for lu, w in mix.items())


def _raw_demand(graph: ExtendedGraph, profile: str) -> np.ndarray:
    inbound = {od.corridor: od for od in graph.od_pairs if od.inbound}
    attractors = {e["attractorNode"] for e in seed.EVENTS} if profile == "event_rush" else set()
    d = np.zeros(len(graph.od_pairs))
    for k, od in enumerate(graph.od_pairs):
        ref_od = inbound[od.corridor]
        ref = _production(ref_od.origin, "morning_rush") * _attraction(ref_od.destination, "morning_rush")
        cur = _production(od.origin, profile) * _attraction(od.destination, profile)
        m = cur / ref
        if od.destination in attractors:
            m *= seed.EVENT_ATTRACTOR_UPLIFT
        d[k] = float(ref_od.base) * m
    return d


def _profile_demand(graph: ExtendedGraph, profile: str) -> np.ndarray:
    raw = _raw_demand(graph, profile)
    morning_total = _raw_demand(graph, "morning_rush").sum()
    return raw * (seed.PROFILE_LEVEL[profile] * morning_total / raw.sum())


def now_profile_weights(now: datetime | None = None) -> dict[str, float]:
    try:
        tz = ZoneInfo(TIMEZONE)
    except Exception:  # tzdata missing → fixed EET offset
        from datetime import timedelta, timezone
        tz = timezone(timedelta(hours=2))
    now = now or datetime.now(tz)
    hour = now.hour + now.minute / 60.0
    level = _HOURLY_LEVEL[int(hour) % 24]
    if now.weekday() >= 5:
        return {"weekend": level / 0.62 * 0.62, "_level": level}
    # blend AM and PM profiles by distance to the peaks (08:15 and 17:30)
    w_am = max(0.0, 1.0 - abs(hour - 8.25) / 6.0)
    w_pm = max(0.0, 1.0 - abs(hour - 17.5) / 6.0)
    if w_am + w_pm == 0:
        w_am = w_pm = 0.5
    tot = w_am + w_pm
    return {"morning_rush": w_am / tot, "evening_rush": w_pm / tot, "_level": level}


def od_demand(graph: ExtendedGraph, preset: str, now: datetime | None = None) -> np.ndarray:
    if preset not in PRESETS:
        raise ValueError(f"unknown preset {preset}")
    if preset != "now":
        return _profile_demand(graph, preset)
    w = now_profile_weights(now)
    level = w.pop("_level")
    d = np.zeros(len(graph.od_pairs))
    for prof, weight in w.items():
        base = _profile_demand(graph, prof)
        if prof == "weekend":
            d += base * weight / seed.PROFILE_LEVEL["weekend"]
        else:
            d += base * weight
    return d * level


# ---------------------------------------------------------------------------
# FROZEN INTERFACE (owner: Lucas). The engine consumes demand only through this.
# Keys are NETWORK NODE IDS (see ExtendedGraph.node_table / snap_to_node), never link ids,
# so the demand model keeps working when the road network is replaced.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ODDemand:
    od_id: str
    origin_node: str
    destination_node: str
    veh_h: float


def build_od(graph: ExtendedGraph, preset: str, now: datetime | None = None) -> list[ODDemand]:
    """Peak-hour car OD demand for ``preset`` on ``graph``."""
    d = od_demand(graph, preset, now)
    return [ODDemand(od.id, od.origin, od.destination, float(d[k])) for k, od in enumerate(graph.od_pairs)]
