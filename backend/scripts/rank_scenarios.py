"""Rank every single-street scenario by how much it lowers total time in traffic.

Usage (from backend/):  python scripts/rank_scenarios.py [--out ../docs/scenario_ranking.csv]

Scenarios, for every time-of-day profile:
  * lane   — what the UI lane mixer produces for one street direction: remove r car lanes
             (r = 1 … max lanes − 1, keeping ≥ 1 car lane on narrower stretches), tested as BUS lanes
             so bus times are measured too (car results are the same for bike / sidewalk);
  * close  — every car lane of a street direction removed (the mixer with no car lane left);
  * segment closure — the existing Braess scan (scan.py, both directions of one segment), solved fresh.

Every scenario is solved like a click in the UI (gap 1e-5, warm start from the base state).
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.corridor.config import PROFILES  # noqa: E402
from app.corridor.model import CorridorModel, LaneChange  # noqa: E402
from app.corridor.osm_network import street_directions  # noqa: E402
from app.corridor.scan import ROUTE_MIN_DEMAND, run_scan  # noqa: E402


def ui_changes(m: CorridorModel, ids: list[str], removed: int, use: str) -> list[LaneChange]:
    """Same rule as frontend/src/App.tsx (lanes → changes)."""
    max_lanes = max(m.car_lanes(i)[0] for i in ids)
    car_after = max_lanes - removed
    out = []
    for lid in ids:
        n = m.car_lanes(lid)[0]
        after = 0 if car_after == 0 else max(1, n - removed)
        after = min(after, n)
        if after < n:
            out.append(LaneChange(lid, after, "closed" if after == 0 else use))
    return out


def evaluate(m, base, ods, changes, profile):
    try:
        res = m.solve(changes, profile=profile)
    except ValueError:
        return None
    pct = (res.total_time - base.total_time) / base.total_time * 100
    best = 0.0
    for (o, d), q in ods.items():
        tb, ta = base.od_time.get((o, d)), res.od_time.get((o, d))
        if q >= ROUTE_MIN_DEMAND and tb and ta is not None and np.isfinite(ta) and tb > 0:
            best = max(best, (tb - ta) / tb)
    buses = [b for b in m.bus_results(changes, base, res, profile) if b["usesChangedStreet"]]
    return {
        "changePct": round(pct, 3),
        "vehHSaved": round((base.total_time - res.total_time) / 60, 2),
        "bestTripGainPct": round(best * 100, 2),
        "busLines": " ".join(sorted({b["shortName"] for b in buses})),
        "busMinSaved": round(sum(b["minutesBefore"] - b["minutesAfter"] for b in buses), 2),
        "gap": res.rel_gap,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "docs" / "scenario_ranking.csv"))
    args = ap.parse_args()

    m = CorridorModel()
    dirs = street_directions(m.net)
    rows = []
    for profile in PROFILES:
        t0 = time.perf_counter()
        base = m.solve([], profile=profile)
        ods = {(o, d): q for o, d, q in m.ods(1.0, profile)}
        n_before = len(rows)
        for street, by_heading in dirs.items():
            for heading, ids in by_heading.items():
                max_lanes = max(m.car_lanes(i)[0] for i in ids)
                for removed in range(1, max_lanes + 1):
                    use = "closed" if removed == max_lanes else "bus"
                    ch = ui_changes(m, ids, removed, use)
                    if not ch:
                        continue
                    r = evaluate(m, base, ods, ch, profile)
                    if r is None:
                        continue
                    rows.append({"profile": profile, "kind": "close direction" if use == "closed" else f"-{removed} lane → bus",
                                 "street": street, "heading": heading, "from": "", "to": "",
                                 "carLanesBefore": max_lanes, "links": len(ch), **r})
        scan = run_scan(m, profile, use_disk=False)
        for s in scan["rows"]:
            if s["kind"] != "removal":
                continue      # the scan's −1 lane rows are already covered above
            ch = [LaneChange(lid, 0, "closed") for lid in s["linkIds"]]
            r = evaluate(m, base, ods, ch, profile)
            if r is None:
                continue
            rows.append({"profile": profile, "kind": "close segment (both ways)", "street": s["street"],
                         "heading": s["heading"], "from": s["fromName"], "to": s["toName"],
                         "carLanesBefore": "", "links": len(ch), **r})
        print(f"{profile}: {len(rows) - n_before} scenarios in {time.perf_counter() - t0:.0f} s", flush=True)

    rows.sort(key=lambda r: (r["changePct"], -r["bestTripGainPct"]))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
