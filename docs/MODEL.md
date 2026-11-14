# How the corridor model works (backend v2)

Branch `backend/landuse-braess`. Inspired by L. Zhao's Braess simulator (land-use demand, conjugate
Frank–Wolfe, closing roads in turn), extended with lane-level changes, real counts, STPT buses and
time-of-day profiles for Timișoara.

## Data flow

```
OSM snapshot (backend/data/osm/corridor_martirilor.json)
  ├─ roads (main + side streets), signals, turn restrictions   → network: 385 links, 16 gateways, banned turns
  └─ buildings + POIs                                          → land use: residents + destinations → 27 zones
profile (morning / day / evening / sunday)
  → land-use OD: homes ↔ destinations (gravity), local ↔ gateways, gateway ↔ gateway (through)
  → counts (optional): gate counts replace gateway flows, link counts scale local demand → "calibrated"
  → Wardrop equilibrium (conjugate Frank–Wolfe, exact line search, tree loading on the link graph, warm starts)
  → user change (lane → bus/bike/sidewalk, or closed)  → before/after: cars, buses, intersections
  → Braess search (every busy segment closed both ways + −1 lane on multi-lane streets), cached
held-out turn counts + GPS times → GEH / time check
```

## Modules (`backend/app/corridor/`)

| Module | Job |
|---|---|
| `config.py` | Corridor box, gateway road classes, **profiles**, every assumption (traffic + land use) |
| `osm_network.py` | Junctions, directed links, lanes/speeds (class defaults when missing), signals, gateways, strongly connected core, turn restrictions → banned movements |
| `landuse.py` | Buildings → residents, POIs/buildings → destination weights, 150 m cells → zones |
| `demand.py` | `landuse_od()` (homes, activities, gateways, gravity + Furness balancing); old gate-only `furness()` kept |
| `assignment.py` | Conjugate Frank–Wolfe; shortest paths on the **link graph** (allowed turns only); vectorised tree loading (+ turn flows); warm start |
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
| Stage 2 | best 24 (≤ 6 per street) + everything that could pass a flag (≤ 60), solved **exactly like a click in the UI** (gap 10⁻⁵, warm start from the base) — the % in the list is the % you get |
| `braess` | verified, total time ≥ 0.05 % lower **and** > 0.1 vehicle-hours saved per hour |
| `routeBraess` | verified, some trip ≥ 1.5 % faster and the total not worse |
| `lowRegret` | total time changes < 0.5 % (a lane can go to buses/bikes almost for free) |

On a one-lane street, turning its only lane into a bike lane, bus lane or sidewalk **is** the removal test.

## Turning rules

- OSM `restriction` relations at junctions inside the area: `no_*` bans that turn, `only_*` bans every other turn.
  357 relations in the snapshot → 51 have their via node in the modelled network → **39 applied**, 1 skipped because
  it would cut a zone off (its legal way round runs outside the box), 8 have a way as via (not supported).
- **No U-turns** at intersections (113 movements), except where a road dead-ends.
- Switch off in `config.TURNS`. Turn counts at the intersection are the check.

## Time of day for through-traffic

Through-traffic is 25 % of gateway capacity at the **morning** peak; other profiles scale it like local trips
(hour share × trip level): day ×0.76, evening ×1.06, Sunday ×0.66. Gate counts replace it per profile.

## Measured performance (estimated demand, laptop, 6 workers)

| Operation | Time |
|---|---|
| Base equilibrium, one profile | 0.1–0.25 s (gap < 10⁻⁵) |
| User lane change (warm start) | ≈ 0.2 s per request incl. results |
| Full Braess search, one profile (256 removals + 39 lanes) | 6–12 s with 6 workers; all four profiles warmed at startup, cached on disk |

## Current results — ESTIMATED demand, morning (not yet evidence)

- Morning: 7 verified Braess segments, all **side-street closures**: Piața Tineretului −0.30 % total time
  (one trip 6.6 % faster), Strada Craiova −0.27 %, Strada Cozia −0.17 % (one trip 10.4 % faster),
  Protopop George Dragomir. 130 low-regret changes (< 0.5 %).
- Evening: 13 Braess segments (Mitropolit Varlaam, Putna, Craiova, Piața Tineretului, Cozia, …).
- Midday and Sunday: **none** — with less traffic the shortcuts are not congested. The paradox depends on the hour.
- Demand ×1.2 (morning): Piața Tineretului still −0.2 %.

These are what the model predicts **if** traffic looks like the land-use estimate. Through-traffic is
the largest and least certain part (≈ 6,900 veh/h assumed) — gate counts fix it.

## Known limits (say them out loud)

- Static, one hour at a time; no queue spillback; no mode shift (demand does not drop when buses get faster).
- Closing a side street ignores local access (model treats it as closed to through traffic).
- Untyped OSM buildings and missing floor counts drive the resident estimate.
