"""Calibration helper: prints baseline equilibrium and hotspot Braess values."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from app.engine.beckmann_solver import PathSystem, solve_equilibrium
from app.engine.demand_model import od_demand
from app.engine.extended_graph import build_graph
from app.services import seed_timisoara as seed

g = build_graph()
R = g.incidence()
od = np.array([p.od_index for p in g.paths])
sysm = PathSystem(R, od, len(g.od_pairs))
print("nodes", len(g.nodes), "road", g.n_road, "queue", len(g.queue_links), "paths", len(g.paths))
preset = sys.argv[1] if len(sys.argv) > 1 else "morning_rush"
d = od_demand(g, preset)
p0 = g.base_params()
t = time.perf_counter()
base = solve_equilibrium(sysm, p0, d)
print(f"baseline Y={base.total_time:.1f} gap={base.rel_gap:.2e} it={base.iterations} {base.elapsed_ms:.1f}ms")
for k, o in enumerate(g.od_pairs):
    idx = [i for i, p in enumerate(g.paths) if p.od_index == k]
    print(f"  {o.id} d={d[k]:.0f}", " | ".join(f"{g.path_name(g.paths[i],6)}:{base.x[i]:.0f}@{base.path_cost[i]:.2f}" for i in idx if base.x[i] > 1))
for h in seed.HOTSPOTS:
    li = g.road_index[h["linkId"]]
    q = g.queue_index[h["queueId"]]
    p1 = g.base_params({h["linkId"]: h["suggestedLanes"]})
    r1 = solve_equilibrium(sysm, p1, d, x0=base.x)
    active = np.array([li not in p.road_links for p in g.paths])
    r2 = solve_equilibrium(sysm, p0, d, active=active | ~np.isin(od, list({p.od_index for p in g.paths if li in p.road_links})), x0=base.x)
    vc = base.z[li] / g.link(h["linkId"]).capacity
    zq0 = base.z[g.n_road + q]
    print(f"{h['id']}: z={base.z[li]:.0f} v/c={vc:.2f} zq={zq0:.0f}/s={p0.s[q]:.0f} "
          f"qdelay={base.phi[g.n_road+q]*60:.0f}s -> swap V={r1.total_time-base.total_time:.1f} "
          f"({(base.total_time-r1.total_time)/base.total_time*100:.2f}%) zq={r1.z[g.n_road+q]:.0f}/s={p1.s[q]:.0f} "
          f"q={r1.phi[g.n_road+q]*60:.0f}s it={r1.iterations} {r1.elapsed_ms:.0f}ms")
