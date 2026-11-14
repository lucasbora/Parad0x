# How the corridor model works (backend v2)

Branch `backend/landuse-braess`. Inspired by L. Zhao's Braess simulator (land-use demand, conjugate
Frank–Wolfe, closing roads in turn), extended with lane-level changes, real counts, STPT buses and
time-of-day profiles for Timișoara.

## Data flow

```
OSM snapshot (backend/data/osm/corridor_martirilor.json)
  ├─ roads (main + side streets), signals, turn restrictions*  → network: 385 links, 16 gateways
  └─ buildings + POIs                                          → land use: residents + destinations → 27 zones
profile (morning / day / evening / sunday)
  → land-use OD: homes ↔ destinations (gravity), local ↔ gateways, gateway ↔ gateway (through)
  → counts (optional): gate counts replace gateway flows, link counts scale local demand → "calibrated"
  → Wardrop equilibrium (conjugate Frank–Wolfe, exact line search, tree loading, warm starts)
  → user change (lane → bus/bike/sidewalk, or closed)  → before/after: cars, buses, intersections
  → Braess search (every busy segment closed both ways + −1 lane on multi-lane streets), cached
held-out turn counts + GPS times → GEH / time check
```
*stored, not yet used by the model.

## Modules (`backend/app/corridor/`)

| Module | Job |
|---|---|
| `config.py` | Corridor box, gateway road classes, **profiles**, every assumption (traffic + land use) |
| `osm_network.py` | Junctions, directed links, lanes/speeds (class defaults when missing), signals, gateways, strongly connected core |
| `landuse.py` | Buildings → residents, POIs/buildings → destination weights, 150 m cells → zones |
| `demand.py` | `landuse_od()` (homes, activities, gateways, gravity + Furness balancing); old gate-only `furness()` kept |
| `assignment.py` | Conjugate Frank–Wolfe; **tree-based all-or-nothing loading** (+ turn flows); warm start |
| `model.py` | Costs (BPR + Webster uniform signal delay), demand per profile, calibration multiplier, compare, baseline |
| `scan.py` | Braess search: removal (both directions) + −1 lane, two stages, parallel workers, disk cache |
| `calibration.py` | Fitted vs held-out comparison, GEH |
| `api.py` | `/api/corridor` (+ `/demand`, `/baseline`, `/simulate`, `/sensitivity`, `/scan`, `/calibration`) |

## Braess search

| Step | Detail |
|---|---|
| Removal candidates | inside street segments with traffic, ranked by congestion carried (t₀ · flow · (v/c)⁴) |
| Lane candidates | each street direction with ≥ 2 car lanes: one lane removed along the whole street |
| Stage 1 | every candidate, warm-started from the base, gap 3·10⁻⁴ |
| Stage 2 | best 24 (≤ 6 per street) + everything that could pass a flag (≤ 60), gap 2·10⁻⁵ |
| `braess` | verified, total time ≥ 0.05 % lower **and** > 0.1 vehicle-hours saved per hour |
| `routeBraess` | verified, some trip ≥ 1.5 % faster and the total not worse |
| `lowRegret` | total time changes < 0.5 % (a lane can go to buses/bikes almost for free) |

On a one-lane street, turning its only lane into a bike lane, bus lane or sidewalk **is** the removal test.

## Measured performance (estimated demand, laptop, 6 workers)

| Operation | Time |
|---|---|
| Base equilibrium, one profile | 0.05–0.08 s (gap < 10⁻⁵) |
| User lane change (warm start) | ≈ 0.02 s solve; ≈ 0.3 s per request incl. results |
| Full Braess search, one profile (250 removals + 39 lanes) | ≈ 5 s (≈ 13 s on 1 core); cached on disk |

## Current results — ESTIMATED demand, morning (not yet evidence)

- 7 verified Braess segments, all **side-street closures** (e.g. Strada Cozia −0.20 % total time,
  one trip 7.8 % faster; Strada Putna, Mitropolit Varlaam, Piața Tineretului, Craiova).
- 133 low-regret changes (< 0.5 % total time).
- Making Strada Cozia car-free in both directions: −0.22 % total time → `braess: true`.

These are what the model predicts **if** traffic looks like the land-use estimate. Through-traffic is
the largest and least certain part (≈ 6,900 veh/h assumed) — gate counts fix it.

## Known limits (say them out loud)

- Static, one hour at a time; no queue spillback; no mode shift (demand does not drop when buses get faster).
- Closing a side street ignores local access (model treats it as closed to through traffic).
- Untyped OSM buildings and missing floor counts drive the resident estimate.
- Turn restrictions (357 relations) are stored but not yet applied.
