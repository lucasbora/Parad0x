"""Packages: several changes at once, as a city would actually do them.

* Greedy filter package: start from the Braess search's single-segment closures (filters), add the
  one that lowers total time the most, re-solve, repeat while each step still helps (≥ 0.02 %).
* Bus add-on: on top of that package, take one car lane for a bus lane on a main-street direction.
  Kept only if the total is STILL lower than today's; the one saving buses the most time wins.
* All day: the same changes in every time window, so a filter that helps at the peak but hurts
  at midday shows up as "peak hours only".
"""
from __future__ import annotations

import threading
from typing import Any

from app.corridor import config
from app.corridor.model import CorridorModel, LaneChange
from app.corridor.osm_network import street_directions

STEP_MIN_GAIN = 0.0002      # 0.02 % of total time per added filter
MAX_FILTERS = 4

_cache: dict[tuple, dict[str, Any]] = {}
_lock = threading.Lock()


def _total(m: CorridorModel, changes: list[LaneChange], profile: str) -> float | None:
    try:
        return m.solve(changes, profile=profile).total_time
    except ValueError:      # a combination that disconnects someone
        return None


def all_day(m: CorridorModel, changes: list[LaneChange], evaporation: float = 0.0) -> dict[str, dict[str, Any]]:
    out = {}
    for p in config.PROFILES:
        base = m.solve([], profile=p).total_time
        if evaporation > 0:
            try:
                t = m.solve_evaporated(changes, 1.0, p, evaporation)[0].total_time
            except ValueError:
                t = None
        else:
            t = _total(m, changes, p)
        out[p] = None if t is None else {"changePct": round((t - base) / base * 100, 3),
                                         "vehHSaved": round((base - t) / 60, 2)}
    return out


def _closures(ids: list[str]) -> list[LaneChange]:
    return [LaneChange(i, 0, "closed") for i in ids]


def best_package(m: CorridorModel, profile: str) -> dict[str, Any]:
    key = (id(m), profile)
    with _lock:
        if key in _cache:
            return _cache[key]
    scan = m.scan(profile=profile)
    best_by_street: dict[str, dict] = {}
    for r in scan["rows"]:
        if r["kind"] == "removal" and r["braess"]:
            if r["street"] not in best_by_street or r["changePct"] < best_by_street[r["street"]]["changePct"]:
                best_by_street[r["street"]] = r
    cands = list(best_by_street.values())
    base = m.solve([], profile=profile).total_time

    chosen: list[dict] = []
    ids: list[str] = []
    cur = base
    steps = []
    while cands and len(chosen) < MAX_FILTERS:
        trials = [(t, c) for c in cands if (t := _total(m, _closures(ids + c["linkIds"]), profile)) is not None]
        if not trials:
            break
        t, c = min(trials, key=lambda x: x[0])
        if t > cur * (1 - STEP_MIN_GAIN):
            break
        chosen.append(c)
        ids += c["linkIds"]
        cands.remove(c)
        cur = t
        steps.append({"street": c["street"], "fromName": c["fromName"], "toName": c["toName"],
                      "linkIds": c["linkIds"], "cumulativeChangePct": round((t - base) / base * 100, 3)})

    filters = None
    if chosen:
        ch = _closures(ids)
        filters = {"linkIds": ids, "steps": steps, "changePct": round((cur - base) / base * 100, 3),
                   "vehHSaved": round((base - cur) / 60, 2), "allDay": all_day(m, ch)}

    # bus add-on: −1 car lane → bus on one main-street direction, on top of the filters
    with_bus = None
    dirs = street_directions(m.net)
    base_res = m.solve([], profile=profile)
    for street in config.CORRIDOR.main_streets:
        for heading, link_ids in dirs.get(street, {}).items():
            lane = [LaneChange(i, m.car_lanes(i)[0] - 1, "bus") for i in link_ids
                    if m.car_lanes(i)[0] >= 2 and not m.net.link(i).bus_lane]
            if not lane:
                continue
            ch = _closures(ids) + lane
            try:
                res = m.solve(ch, profile=profile)
            except ValueError:
                continue
            pct = (res.total_time - base) / base * 100
            if pct >= 0:
                continue        # the whole package must still beat today
            buses = [b for b in m.bus_results(ch, base_res, res, profile) if b["usesChangedStreet"]]
            if not buses:
                continue
            bus_min = max(b["minutesBefore"] - b["minutesAfter"] for b in buses)
            cand = {"street": street, "heading": heading, "laneChanges": [
                        {"linkId": c.link_id, "carLanesAfter": c.car_lanes_after, "use": c.use} for c in lane],
                    "changePct": round(pct, 3), "vehHSaved": round((base - res.total_time) / 60, 2),
                    "busLines": sorted({b["shortName"] for b in buses}), "busMinutesSaved": round(bus_min, 2)}
            if with_bus is None or (cand["busMinutesSaved"], -cand["changePct"]) > (with_bus["busMinutesSaved"], -with_bus["changePct"]):
                with_bus = cand
    if with_bus:
        ch = _closures(ids) + [LaneChange(c["linkId"], c["carLanesAfter"], c["use"]) for c in with_bus["laneChanges"]]
        with_bus["allDay"] = all_day(m, ch)

    out = {"profile": profile, "filters": filters, "withBus": with_bus,
           "rule": f"greedy: add the filter that lowers total time most, while each step gains ≥ {STEP_MIN_GAIN * 100:.2f} %"}
    with _lock:
        _cache[key] = out
    return out
