"""Model vs. field data, per time-of-day profile (OWNER: Lucas).

Two kinds of comparison, kept strictly apart:
  * FITTED  — gate counts (replace the gateway estimate) and link counts (scale local demand).
              Shown so you can see the fit, but they are NOT evidence: the model was told them.
  * CHECKED — turn counts and GPS travel times. Never used for fitting → this is the proof.

GEH = sqrt(2 (M − C)² / (M + C)) for hourly flows M (model) and C (count).
Rule of thumb used by transport agencies: GEH < 5 on at least 85 % of counted flows.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from app.corridor.assignment import _all_or_nothing
from app.corridor.config import DEFAULT_PROFILE
from app.corridor.model import CorridorModel, NeedsData


def geh(model: float, count: float) -> float:
    if model + count <= 0:
        return 0.0
    return math.sqrt(2 * (model - count) ** 2 / (model + count))


def calibration_report(m: CorridorModel, scale: float = 1.0, profile: str = DEFAULT_PROFILE) -> dict[str, Any]:
    fd = m.fd
    has_any = (fd.gate_in.get(profile) or fd.gate_out.get(profile) or fd.link_counts.get(profile)
               or any(t["profile"] == profile for t in fd.turns)
               or any(t["profile"] == profile for t in fd.travel_times))
    if not has_any:
        raise NeedsData(m.status)
    res = m.solve([], scale, profile=profile)
    net, sn = m.net, m.solver_net
    od = m.od_table(profile)

    # ---------------------------------------------------------------- fitted (not evidence)
    fitted_links = []
    for lid, c in fd.link_counts.get(profile, {}).items():
        mod = float(res.flow[net.link_index[lid]])
        fitted_links.append({"linkId": lid, "street": net.link(lid).street, "counted": round(c), "model": round(mod),
                             "geh": round(geh(mod, c), 2)})
    fitted_gates = []
    for direction, store, attr in (("in", fd.gate_in, "in_link"), ("out", fd.gate_out, "out_link")):
        for gid, c in store.get(profile, {}).items():
            g = next(x for x in net.gates if x.id == gid)
            mod = float(res.flow[net.link_index[getattr(g, attr)]])
            fitted_gates.append({"gateId": gid, "street": g.street, "direction": direction, "counted": round(c),
                                 "model": round(mod), "geh": round(geh(mod, c), 2)})

    # ---------------------------------------------------------------- checked (held out)
    turns = []
    for t in fd.turns:
        if t["profile"] != profile:
            continue
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
    for tt in fd.travel_times:
        if tt["profile"] != profile:
            continue
        a, b = gates.get(tt["from_gate_id"]), gates.get(tt["to_gate_id"])
        if not a or not b:
            continue
        key = (m.node_idx[a.node], m.node_idx[b.node])
        model_min = res.od_time.get(key)
        if model_min is None:  # pair carries no demand: shortest time at equilibrium link costs
            _, _, odt = _all_or_nothing(sn, res.cost, [(key[0], key[1], 0.0)], np.ones(sn.n_links, dtype=bool))
            model_min = odt[key]
        times.append({"route": tt["route"], "observedMin": tt["minutes"], "modelMin": round(model_min, 2),
                      "diffPct": round((model_min - tt["minutes"]) / tt["minutes"] * 100, 1)})
    ok = sum(1 for t in turns if t["geh"] < 5)
    return {
        "profile": profile,
        "demandSource": m.demand_source(profile),
        "localMultiplier": od.summary.get("localMultiplier", 1.0),
        "fitted": {"gates": fitted_gates, "links": fitted_links,
                   "note": "These counts were given to the model — a good fit here is expected, not proof."},
        "turns": turns,
        "travelTimes": times,
        "summary": {
            "turnsCounted": len(turns),
            "gehUnder5": ok,
            "gehUnder5Pct": round(ok / len(turns) * 100, 0) if turns else None,
            "travelTimesChecked": len(times),
            "target": "GEH < 5 on ≥ 85 % of counted flows (held-out turn counts)",
        },
    }
