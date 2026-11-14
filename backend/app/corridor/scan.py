"""Braess search: what happens if a street loses car capacity? (after L. Zhao, plus lane removal)

Two kinds of test per candidate, both re-solving the full Wardrop equilibrium:
  * REMOVAL  — a street segment (junction to junction) closed to cars in BOTH directions
              (L. Zhao's "Braess road" test; on a one-lane street this is exactly what turning
              its only lane into a bike lane, bus lane or sidewalk does);
  * LANE     — one car lane taken from every multi-lane link of a street direction.

Stage 1 solves every candidate quickly (warm start from the base state); stage 2 re-solves the
best 24 (at most 6 per street) precisely. Flags:
  * braess       total time in traffic ≥ 0.05 % lower and > 0.1 vehicle-hours saved per hour
  * routeBraess  some origin→destination trip ≥ 1.5 % faster while the total is not worse
  * lowRegret    total time changes by less than 0.5 % (a lane can go to buses/bikes almost for free)

Results are cached in memory and on disk per profile and per data version.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from typing import Any

import numpy as np

from app.corridor import config
from app.corridor.osm_network import compass, street_directions

QUICK_GAP, QUICK_ITER = 3e-4, 80
PRECISE_GAP, PRECISE_ITER = 2e-5, 400
VERIFY_TOP, PER_STREET = 24, 6
VERIFY_KEEP_IMP = -0.0008      # stage 1 keeps anything not clearly worse (L. Zhao's cut-off)
VERIFY_MAX = 60
BRAESS_MIN_IMP, BRAESS_MIN_VEH_H = 0.0005, 0.1
ROUTE_MIN_GAIN, ROUTE_MIN_DEMAND = 0.015, 5.0
LOW_REGRET_PCT = 0.5
MAX_CANDIDATES = 300


# ---------------------------------------------------------------------------
# candidates
# ---------------------------------------------------------------------------

def candidates(m, base) -> list[dict[str, Any]]:
    """Removal candidates = inside street segments with traffic; lane candidates = multi-lane directions."""
    from app.corridor.model import LaneChange

    net = m.net
    costs, _ = m.costs([])
    vc = base.flow / costs.cap
    heading_of = {lid: h for dirs in street_directions(net).values() for h, ids in dirs.items() for lid in ids}
    segs: dict[frozenset, list[int]] = {}
    for i, l in enumerate(net.links):
        if net.nodes[l.from_node].inside and net.nodes[l.to_node].inside:
            segs.setdefault(frozenset((l.from_node, l.to_node)), []).append(i)
    out = []
    for key, idx in segs.items():
        flow = float(base.flow[idx].sum())
        if flow <= 5.0:
            continue
        # congestion carried (L. Zhao): free-flow time × flow × (v/c)^4 — busy AND congested first
        score = float(sum(net.links[i].t0_min * base.flow[i] * vc[i] ** 4 for i in idx)) + 1e-6 * flow
        first = net.links[idx[0]]
        out.append({
            "kind": "removal", "scope": "both", "street": first.street,
            "heading": heading_of.get(first.id, compass(first.bearing)),
            "linkIds": [net.links[i].id for i in idx],
            "fromName": net.nodes[first.from_node].name, "toName": net.nodes[first.to_node].name,
            "changes": [LaneChange(net.links[i].id, 0, "closed") for i in idx],
            "score": score, "baseFlow": round(flow, 0),
            "at": first.geometry[len(first.geometry) // 2],
        })
    out.sort(key=lambda c: -c["score"])
    n_links = len(net.links)
    limit = MAX_CANDIDATES if n_links <= 3000 else max(60, round(MAX_CANDIDATES * 3000 / n_links))
    out = out[:limit]
    for street, dirs in street_directions(net).items():
        for heading, ids in dirs.items():
            multi = [lid for lid in ids if m.car_lanes(lid)[0] >= 2]
            if not multi:
                continue
            first = net.link(multi[0])
            out.append({
                "kind": "lane", "scope": "one", "street": street, "heading": heading, "linkIds": ids,
                "fromName": net.nodes[first.from_node].name, "toName": net.nodes[net.link(multi[-1]).to_node].name,
                "changes": [LaneChange(lid, m.car_lanes(lid)[0] - 1, "bike") for lid in multi],
                "score": 0.0, "baseFlow": round(float(sum(base.flow[net.link_index[x]] for x in multi)), 0),
                "at": first.geometry[len(first.geometry) // 2],
            })
    return out


def _evaluate(m, base, ods_demand, cand, profile, gap, max_iter) -> dict[str, Any] | None:
    try:
        res = m.solve(cand["changes"], profile=profile, rel_gap=gap, max_iter=max_iter,
                      x0=(base.flow, base.movement_flow))
    except ValueError:          # closing it would cut a zone or gateway off → not a valid scenario
        return None
    imp = (base.total_time - res.total_time) / base.total_time
    best_gain = 0.0
    for (o, d), q in ods_demand.items():
        if q < ROUTE_MIN_DEMAND or (o, d) not in res.od_time:
            continue
        tb, ta = base.od_time.get((o, d)), res.od_time[(o, d)]
        if tb and np.isfinite(ta) and tb > 0:
            best_gain = max(best_gain, (tb - ta) / tb)
    return {"imp": imp, "vehMinDelta": res.total_time - base.total_time, "bestRouteGain": best_gain,
            "gap": res.rel_gap}


# ---------------------------------------------------------------------------
# parallel workers (spawn-safe on Windows)
# ---------------------------------------------------------------------------

_W: dict[str, Any] = {}


def _init_worker(input_dir: str, profile: str) -> None:
    from app.corridor.model import CorridorModel

    m = CorridorModel(input_dir=__import__("pathlib").Path(input_dir))
    base = m.solve([], profile=profile)
    _W.update(m=m, base=base, profile=profile,
              ods={(o, d): q for o, d, q in m.ods(1.0, profile)})


def _work(args: tuple[int, dict, float, int]) -> tuple[int, dict | None]:
    i, cand, gap, max_iter = args
    return i, _evaluate(_W["m"], _W["base"], _W["ods"], cand, _W["profile"], gap, max_iter)


def _run_all(m, base, ods_demand, cands, profile, gap, max_iter, workers) -> list[dict | None]:
    if workers <= 1 or len(cands) < 8:
        return [_evaluate(m, base, ods_demand, c, profile, gap, max_iter) for c in cands]
    results: list[dict | None] = [None] * len(cands)
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn"),
                             initializer=_init_worker, initargs=(str(m.input_dir), profile)) as ex:
        for i, r in ex.map(_work, [(i, c, gap, max_iter) for i, c in enumerate(cands)], chunksize=4):
            results[i] = r
    return results


# ---------------------------------------------------------------------------
# main entry
# ---------------------------------------------------------------------------

def _signature(m, profile: str) -> str:
    h = hashlib.sha1()
    h.update(m.net.source["fetchedAt"].encode())
    h.update(repr(sorted((p.name, p.stat().st_mtime_ns) for p in m.input_dir.glob("*.csv"))).encode()
             if m.input_dir.exists() else b"")
    h.update(repr((config.ASSUMPTIONS, config.LANDUSE, config.PROFILES[profile], config.POI_WEIGHTS,
                   config.BUILDING_WEIGHTS)).encode())
    h.update(repr((QUICK_GAP, PRECISE_GAP, VERIFY_TOP, BRAESS_MIN_IMP, LOW_REGRET_PCT)).encode())
    return h.hexdigest()[:16]


def default_workers() -> int:
    env = os.getenv("TMBG_SCAN_WORKERS")
    if env:
        return max(1, int(env))
    return max(1, min(6, (os.cpu_count() or 2) - 1))


def run_scan(m, profile: str, workers: int | None = None, use_disk: bool = True) -> dict[str, Any]:
    key = ("scan", profile)
    if key in m._cache:
        return m._cache[key]
    sig = _signature(m, profile)
    path = config.CACHE_DIR / f"scan_{profile}_{sig}.json"
    if use_disk and path.exists():
        out = json.loads(path.read_text(encoding="utf-8"))
        m._cache[key] = out
        return out

    t_start = time.perf_counter()
    workers = default_workers() if workers is None else workers
    base = m.solve([], profile=profile)
    ods_demand = {(o, d): q for o, d, q in m.ods(1.0, profile)}
    cands = candidates(m, base)

    quick = _run_all(m, base, ods_demand, cands, profile, QUICK_GAP, QUICK_ITER, workers)
    scored = [(c, r) for c, r in zip(cands, quick) if r is not None]
    # stage 2: the best VERIFY_TOP (at most PER_STREET per street name) plus every
    # candidate that could still pass a flag, up to VERIFY_MAX — flags come only from precise solves
    per_street: dict[str, int] = {}
    shortlist = []
    ranked = sorted(scored, key=lambda cr: -max(cr[1]["imp"], cr[1]["bestRouteGain"] * 0.1))
    for c, r in ranked:
        could_flag = r["imp"] >= BRAESS_MIN_IMP * 0.5 or r["bestRouteGain"] >= ROUTE_MIN_GAIN * 0.7
        top = len(shortlist) < VERIFY_TOP and per_street.get(c["street"], 0) < PER_STREET
        if (top or could_flag) and r["imp"] > VERIFY_KEEP_IMP and len(shortlist) < VERIFY_MAX:
            per_street[c["street"]] = per_street.get(c["street"], 0) + 1
            shortlist.append(c)
    precise = _run_all(m, base, ods_demand, shortlist, profile, PRECISE_GAP, PRECISE_ITER, workers)
    verified = {id(c): r for c, r in zip(shortlist, precise) if r is not None}

    base_veh_h = base.total_time / 60.0
    rows = []
    for c, r in scored:
        rr = verified.get(id(c), r)
        imp = rr["imp"]
        pct = -imp * 100.0
        saved_veh_h = imp * base_veh_h
        precise = id(c) in verified
        braess = precise and imp >= BRAESS_MIN_IMP and saved_veh_h > BRAESS_MIN_VEH_H
        route_braess = precise and rr["bestRouteGain"] >= ROUTE_MIN_GAIN and imp >= -0.0002
        rows.append({
            # fields the current UI already reads
            "street": c["street"], "heading": c["heading"], "linkIds": c["linkIds"],
            "mode": "closure" if c["kind"] == "removal" else "minus_one_lane",
            "changePct": round(pct, 3), "vehMinDelta": round(rr["vehMinDelta"], 1),
            "braess": bool(braess), "lowRegret": bool(abs(pct) < LOW_REGRET_PCT),
            # new fields
            "kind": c["kind"], "scope": c["scope"], "fromName": c["fromName"], "toName": c["toName"],
            "vehHSaved": round(saved_veh_h, 2), "routeBraess": bool(route_braess),
            "bestRouteGainPct": round(rr["bestRouteGain"] * 100.0, 2),
            "stage": "verified" if id(c) in verified else "quick", "baseFlow": c["baseFlow"], "at": c["at"],
        })
    rows.sort(key=lambda r: (r["changePct"], -r["bestRouteGainPct"]))
    out = {
        "testData": False, "profile": profile, "demandSource": m.demand_source(profile),
        "rows": rows,
        "braessCount": sum(r["braess"] for r in rows),
        "routeBraessCount": sum(r["routeBraess"] for r in rows),
        "lowRegretCount": sum(r["lowRegret"] for r in rows),
        "tested": {"removal": sum(c["kind"] == "removal" for c in cands), "lane": sum(c["kind"] == "lane" for c in cands),
                   "verified": len(verified), "skippedDisconnecting": len(cands) - len(scored)},
        "seconds": round(time.perf_counter() - t_start, 1), "workers": workers,
        "thresholds": {"braessMinImprovementPct": BRAESS_MIN_IMP * 100, "braessMinVehH": BRAESS_MIN_VEH_H,
                       "routeMinGainPct": ROUTE_MIN_GAIN * 100, "lowRegretPct": LOW_REGRET_PCT},
        "signature": sig,
    }
    m._cache[key] = out
    if use_disk:
        try:
            config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return out
