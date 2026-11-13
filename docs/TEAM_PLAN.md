# Team plan — TM-BraessGreen (corridor MVP, branch `corridor-mvp`)

**The claim to prove:** "For one real Timișoara corridor — Calea Martirilor / Strada Cluj — change a car lane and see,
on real streets with real traffic counts, where the cars go, how driving time changes and how the buses are affected."

Scope is deliberately small: **one corridor, morning peak, real data only.** Braess's paradox is a possible result,
not a promise.

## Done (on this branch)

- [x] Real network from OpenStreetMap: 164 directed links, 67 intersections, 25 traffic lights, 16 gates
      (snapshot `backend/data/osm/corridor_martirilor.json`, refetch with `scripts/fetch_osm_corridor.py`).
- [x] Link-based Wardrop equilibrium (Conjugate Frank–Wolfe + exact line search); reproduces the textbook
      Braess example exactly (65 vs 80 min) — `tests/test_corridor.py`.
- [x] Demand from gate counts (Furness / doubly-constrained gravity) — no counts, no results.
- [x] Live STPT lines map-matched to the corridor; buses/hour from real SMTT timetables.
- [x] GEH calibration report and ±20 % sensitivity endpoints.
- [x] UI: sidebar (search a street → pick direction → one dropdown per lane: car / bus / bike / sidewalk) and a
      coloured congestion map (free-flowing → congested, width = traffic, animated flow, before/after toggle).
      Every lane change re-runs the simulation automatically; travel-time pins on the map update live; a toast
      fires when taking car capacity away lowers total time in traffic (Braess's paradox).
- [x] Test mode (clearly labelled "TEST DATA — not real measurements"): demand = half the capacity of each entry
      road, so the app can be tried before counts exist. It switches off by itself once `gate_counts.csv` has data.
- [x] Field-data templates and reference lists in `backend/data/corridor/`; protocol in `docs/CORRIDOR_DATA.md`.

## Real-data findings so far (verify on site!)

- **Strada Cluj is one-way southbound**, 3–4 lanes, and OSM says it **already has a bus lane**.
- Inbound traffic (towards the centre) uses **Aleea F.C. Ripensia** northbound and Calea Martirilor.
- Lines on Strada Cluj southbound: **15, 16, E2, E3, M3, M24** (live SMTT feed).

→ The demo question is probably *not* "add a bus lane on Cluj" (it may exist already) but, e.g.,
"take one lane from Strada Cluj / Calea Martirilor / Ripensia for a protected bike lane — where does the traffic go?"
Decide after the site visit.

## Next — who does what

| Person | Owns (only they edit) | Task | Done when |
|---|---|---|---|
| **Laura** | field videos, GPS logs; `frontend/src/components/CorridorMap.tsx` | Film all 16 gates (15 min each, 07:30–08:30) + 2–3 key intersections; GPS runs | `gate_counts.csv`, `turn_counts.csv`, `travel_times.csv` filled with `source` on every row |
| **Lucas** | `backend/app/corridor/demand.py`, `calibration.py`; the CSVs in `backend/data/corridor/` | Enter counts, calibrate β / capacities against turn counts (GEH), run ±20 % | GEH table + sensitivity table for the slides |
| **Rareș** | `backend/app/corridor/osm_network.py`, `assignment.py`, `model.py`, `transit.py`, `api.py`; `frontend/src/types/corridor.ts` | Signal timings from videos → `signal_timings.csv`; check lanes → `lane_checks.csv`; solver benchmarks (Sioux Falls optional) | Assumptions list in the app is mostly replaced by measured values |
| **Adriana** | `frontend/src/components/*` (except the map), `frontend/src/i18n/translations.ts`, `docs/` | Read SIDU/PMUD PDFs for real corridor volumes (with page + year); talk to 2–3 people; deck, script, backup video | Deck with evidence slides; every number traceable to a source |

**Shared files (small coordinated PRs only):** `frontend/src/App.tsx`, `backend/app/main.py`, `backend/app/corridor/config.py`.

**API rule:** only add fields, never rename/remove. Changes to `backend/app/corridor/api.py` must update
`frontend/src/types/corridor.ts` in the same PR.

## Checkpoints

| When | Check | If it fails |
|---|---|---|
| After first counting morning | ≥ the 6 biggest gates counted (Martirilor, Rebreanu ×2, Eroilor, bridges) | Present a partial count honestly; the app lists uncounted gates |
| After calibration | GEH < 5 on most turn counts | Show the table anyway and explain the gap |
| Code freeze (T−6 h) | Demo runs offline from the snapshot + CSVs | Live SMTT data is a bonus, not a dependency |

## Git workflow

- Branch from `corridor-mvp`; `git pull --rebase` before each task; small PRs every 3–4 hours.
- Before every merge: `pytest -q` (backend) and `npm run build` (frontend) must pass.
- **Never commit invented numbers into `backend/data/corridor/`.** Test data lives only inside `tests/`.

**Demo (3 min):** the corridor on the map + where we counted (30 s) → pick a street, take a lane, run (60 s) →
where traffic goes + buses + intersections (45 s) → model vs. counts (GEH) and ±20 % (30 s) → limits and what we'd
need from the city (15 s).
