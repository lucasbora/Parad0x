# Team plan — TM-BraessGreen

**The claim to prove:** "Change any street on Timișoara's real network and see, in under 1 s, the effect on cars, buses and bikes — with a validated solver and one corridor checked against real counts."

Times are hours from now (T+).

## T+0 to T+1: everyone

- [x] **Split the code so everyone can work in parallel** (done on `main`; see "File ownership" below).
- [x] Freeze the network-node format and the demand interface (see "Frozen interfaces").
- [ ] Pick **one demo corridor**: central, with a real debate, somewhere you can count traffic.
- [ ] Choose **2 count intersections** on that corridor.
- [ ] Lucas sends emails asking for the OD matrix, signal timings, FIWARE counts and the `/api/sesizari` parameters.
- [ ] Everyone branches from `main` (`git switch -c <name>/<task>`); code freeze at T−6h before judging.

## File ownership: only the owner edits these

| Person | Owns |
|---|---|
| **Rareș** | `backend/app/engine/extended_graph.py`, `beckmann_solver.py`, `braess_detector.py`, `route_recommender.py` · `backend/app/seed/network.py`, `seed/transit.py`, `seed/hotspots.py` · `backend/app/services/layers/roads.py`, `layers/transit.py` · `backend/app/models/schemas.py` · `frontend/src/types/simulator.ts` · `backend/tests/test_solver.py` |
| **Lucas** | `backend/app/engine/demand_model.py` · new `backend/app/engine/calibration.py` · `backend/app/seed/demand.py` · new `backend/data/counts/` · calibration tests |
| **Laura** | `frontend/src/components/map/*` · `backend/app/services/osm_overpass.py` · `backend/app/seed/cycling.py` · `backend/app/services/layers/cycling.py` · field videos and GPS logs |
| **Adriana** | `backend/app/seed/context.py` · `backend/app/services/layers/context.py` · `backend/app/services/pmt_client.py`, `live_data.py` · `frontend/src/components/studio/*` · `frontend/src/i18n/translations.ts` · `docs/`, the deck |

**Shared files, edited only by small coordinated PRs:** `backend/app/services/simulator.py` (it only assembles layers now), `backend/app/main.py`, `frontend/src/App.tsx`, `backend/app/services/seed_timisoara.py` (a re-export facade; never add data to it).

## Frozen interfaces: code against these, never against internals

1. **Network → everyone** (Rareș keeps these stable when he swaps in the OSM network):
   - `graph.node_table() -> [{id, name, coordinates: [lng, lat], cartier}]`
   - `graph.snap_to_node(lng, lat) -> node_id`
2. **Demand → engine** (Lucas): `build_od(graph, preset, now=None) -> [ODDemand(od_id, origin_node, destination_node, veh_h)]` in `engine/demand_model.py`. Use **node IDs only, never link IDs**.
3. **Hotspots are locations, not link IDs:** each has an `anchor` (from → to coordinates) and a `streetHint`; `seed.hotspots.resolve_hotspots(graph)` finds the link in whatever network is loaded. `linkId`/`queueId` are hints only.
4. **API schema:** only add fields, never rename or remove them. Schema changes go to Rareș as a small PR that updates both `schemas.py` and `types/simulator.ts`.

**Heads-up for the network swap (Rareș):** link IDs (`LINK_CLUJ_01`…), the curated route sets in `seed/demand.py` and the STPT node lists in `seed/transit.py` are specific to the current seed network. Link-based assignment drops the curated routes. `tests/test_interfaces.py` checks the interfaces above; keep it green.

## Git workflow

- `git pull --rebase` before starting any task; small PRs merged at least every 3–4 hours.
- Run `pytest -q` (backend) and `npm run build` (frontend) before every merge. Both must pass.
- Need to change a file you don't own? Say so in the team chat first and keep the change minimal.

## Lucas: demand, calibration and robustness

| When | Task | Done when |
|---|---|---|
| T+1–6 | Demand model: census population per cartier → OSM/PMT attractors, gravity model, centroids snapped to nodes | Produces an OD matrix for any network |
| T+6–8 | Run it on the current graph for the corridor | The corridor solves with your demand |
| T+8–12 | Switch it to Rareș's real network | Same, on the real network |
| After counts | Calibrate the corridor to Laura's counts; report GEH and travel times | The "model vs. observed" numbers are ready |
| Then | Sensitivity at −20%, normal and +20% demand | The "conclusion holds" table is ready |

## Rareș: network and solver

| When | Task | Done when |
|---|---|---|
| T+1–8 | Import the OSM network for the centre (lanes, speeds, one-ways, signals); commit a snapshot file | The network loads offline |
| T+8–14 | Link-based CFW with shortest-path all-or-nothing loading | A scenario solves in under 1 s |
| T+14–16 | Benchmark tests: Braess (65 vs 80 min) and Sioux Falls | Both pass |
| T+16–22 | Map the real SMTT lines, stops and frequencies onto links; re-run the scan | The transit panel uses only real data |

## Laura: field evidence and map

| When | Task | Done when |
|---|---|---|
| Next rush hour | Film 15 min at each of the 2 intersections; do GPS travel-time runs on the corridor | Videos and GPS logs saved |
| After | Count vehicles per movement from the videos | Counts table goes to Lucas |
| Then | Load real OSM cycleways and i'velo stations; adapt the map to the real network | No invented cycling data left |
| Then | "Model vs. observed" chart | Slide-ready |

## Adriana: honesty pass and pitch

| When | Task | Done when |
|---|---|---|
| T+1–4 | Remove the fabricated values (sesizări counts, FIWARE/air/events, random i'velo, fake cycleways, wrong codGis); add "estimated / illustrative" labels | Every number has a source or a label |
| T+4–10 | Talk to 2–3 people: a planner, an STPT rider, a resident | Real quotes collected |
| T+10–20 | Deck: problem, demo, 5 evidence slides (solver, counts, live data, sensitivity, limits), next steps | Deck is complete |
| After freeze | Demo script, judge Q&A sheet, backup video | Ready to present |

## Checkpoints

| When | Check | If it fails |
|---|---|---|
| T+8 | Is the real network loading? | Keep the current graph; calibrate the corridor only |
| T+14 | Does Lucas's demand run on the real network? | Present the corridor on the current graph |
| Freeze | Is the calibration done? | Present the sensitivity and state the gap honestly |

## T−6h to judging: everyone

- [ ] Code freeze: bug fixes only.
- [ ] Demo runs from the snapshot in offline mode; live APIs are a bonus, not a dependency.
- [ ] Record the backup video.
- [ ] Rehearse 3 times. Question owners: maths (Rareș), demand (Lucas), data (Laura), product and limits (Adriana).

**Demo order (3.5 min):** Braess explainer (30 s) → corridor lane swap with its routes and buses (90 s) → evidence slides (60 s) → the ask: the city's OD matrix and signal plans (30 s).
