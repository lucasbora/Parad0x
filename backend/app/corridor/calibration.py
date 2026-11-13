"""Model vs. field data (OWNER: Lucas).

GEH = sqrt(2 (M − C)² / (M + C)) for hourly flows M (model) and C (count).
Rule of thumb used by transport agencies: GEH < 5 on at least 85 % of counted flows.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from app.corridor.assignment import _all_or_nothing
from app.corridor.model import CorridorModel


def geh(model: float, count: float) -> float:
    if model + count <= 0:
        return 0.0
    return math.sqrt(2 * (model - count) ** 2 / (model + count))


def calibration_report(m: CorridorModel, scale: float = 1.0) -> dict[str, Any]:
    res = m.solve([], scale)
    net, sn = m.net, m.solver_net
    turns = []
    for t in m.fd.turns:
        i, j = net.link_index[t["from_link_id"]], net.link_index[t["to_link_id"]]
        mi = sn.movements.get((i, j))
        model = float(res.movement_flow[mi]) if mi is not None else 0.0
        turns.append({
            "nodeId": t["node_id"], "intersection": net.nodes[t["node_id"]].name if t["node_id"] in net.nodes else t["node_id"],
            "from": net.link(t["from_link_id"]).street, "to": net.link(t["to_link_id"]).street,
            "counted": round(t["veh_h"], 0), "model": round(model, 0), "geh": round(geh(model, t["veh_h"]), 2),
        })
    gates = {g.id: g for g in net.gates}
    times = []
    for tt in m.fd.travel_times:
        a, b = gates.get(tt["from_gate_id"]), gates.get(tt["to_gate_id"])
        if not a or not b:
            continue
        key = (m.node_idx[a.node], m.node_idx[b.node])
        model_min = res.od_time.get(key)
        if model_min is None:  # pair carries no demand: shortest time at equilibrium link costs
            _, _, od = _all_or_nothing(sn, res.cost, [(key[0], key[1], 0.0)], np.ones(sn.n_links, dtype=bool))
            model_min = od[key]
        times.append({"route": tt["route"], "observedMin": tt["minutes"], "modelMin": round(model_min, 2),
                      "diffPct": round((model_min - tt["minutes"]) / tt["minutes"] * 100, 1)})
    ok = sum(1 for t in turns if t["geh"] < 5)
    return {
        "turns": turns,
        "travelTimes": times,
        "summary": {
            "turnsCounted": len(turns),
            "gehUnder5": ok,
            "gehUnder5Pct": round(ok / len(turns) * 100, 0) if turns else None,
            "target": "GEH < 5 on ≥ 85 % of counted flows",
        },
    }
