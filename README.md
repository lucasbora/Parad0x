# Timișoara Traffic Stress Tester (TM-BraessGreen)

A screening tool for **Primăria Municipiului Timișoara**: change a street around **Calea Martirilor / Strada Cluj**
(close it to cars, or give a car lane to a bus, a bike lane or a sidewalk) and see in under a second what happens to
traffic in the whole area. It finds the streets where taking capacity away from cars makes traffic **faster**
(Braess's paradox), the changes that cost drivers almost nothing, and the ones that would be a disaster.

Intended owners: **Direcția Generală de Investiții și Mentenanță** (street changes) and **SMTT / STPT** (bus lanes).
It doesn't replace a traffic study. It tells the city which ideas deserve one.

## How it works

1. **Street network** from OpenStreetMap (snapshot 14 Nov 2026): 385 directed segments, 163 intersections
   (30 with traffic lights), lanes, speed limits, 39 turn restrictions, U-turn bans. A lane tagged for buses
   (`lanes:psv`, `busway=lane`) is not counted as a car lane.
2. **Demand** estimated from OpenStreetMap buildings and points of interest: ≈ 24,500 residents (homes) and schools,
   offices, shops, clinics (destinations), weighted by the hour of the day, connected by a gravity model, plus
   traffic passing through the 16 entry points. Morning 07:30–08:30, midday 12:30–13:30, evening 17:00–18:00.
3. **Route choice**: every driver takes their fastest route (Wardrop user equilibrium, conjugate Frank-Wolfe).
   Travel time per segment = BPR congestion curve + Webster signal delay. Capacity = lanes × 1,800 veh/h × green share.
4. **Search**: every busy segment closed, and one lane removed from every multi-lane street, each re-solved.
   The app lists Braess cases, near-free changes, a recommended package and the effect in every time window.
5. **What a change does**: total time in traffic, the routes it affects (seconds), where traffic moves, the waits at
   intersections, STPT lines on the street, and the break-even (how many drivers must switch mode to compensate).
   Optional *traffic evaporation* (0 / 5 / 11 % of the street's drivers leave the car; 11 % is the median of
   Cairns, Atkins & Goodwin 2002) is shown separately, with the time change for the drivers who keep driving.

**Demand is estimated, not measured.** The app says so. Traffic counts in `backend/data/corridor/` (see
[`docs/CORRIDOR_DATA.md`](docs/CORRIDOR_DATA.md)) calibrate it per time window and are checked with the GEH statistic.
Model details and results: [`docs/MODEL.md`](docs/MODEL.md).

## Data sources

| Source | Used for |
|---|---|
| OpenStreetMap (Overpass API, © OpenStreetMap contributors, ODbL) | Streets, lanes, signals, turn rules, buildings, points of interest |
| `cont.primariatm.ro/api/mobile/transit/network` | STPT lines and their routes on the corridor |
| `cont.primariatm.ro/api/mobile/transit/stops/{id}/timetable` | Buses per hour in the simulated hour |
| `cont.primariatm.ro/api/mobile/wallet/types?category=transport` | Ticket prices |
| `cont.primariatm.ro/api/mobile/parking` | Timpark tariffs and paid street segments in the area |
| PMUD Timișoara (car share 44 %, not yet checked against the document) | Car trips per resident |
| Citizen survey, 31 anonymous answers (`backend/data/survey/`) | Reported in the app; replaces the PMUD figures only from 100 answers |

City Hall endpoints are called from the backend only, with a User-Agent naming the project, and cached. If one is
down, that part is left out; nothing is invented.

## Run it

```bash
# backend (Python 3.11+)
cd backend
python -m venv .venv && .venv/Scripts/activate      # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000                    # warms the Braess search for every time window (~1 min)

# frontend (Node 20+), in another terminal
cd frontend
npm install
npm run dev                                         # http://localhost:5173 (proxies /api to :8000)
```

Docker: `docker compose up --build` (UI on http://localhost:8080, API docs on http://localhost:8000/docs).

## Tests

```bash
cd backend && pytest -q        # 64 tests, offline
```

They check the textbook Braess example (65 → 80 min), Wardrop equilibrium on two routes, tree vs path loading, flow
conservation, turn bans, Furness balancing, GEH, calibration from counts, and on the real network: convergence in
every time window, total time = Σ flow × time, the demand and through-traffic formulas, bus lanes not counted as car
lanes, capacity following the lane count, that taking a lane slows that street and the area, that a closed segment
carries no traffic, the Braess case at Piața Tineretului, bus times on a new bus lane, evaporation, the survey parser
and the API end to end.

## Limits

- Demand is estimated from land use; no traffic counts yet.
- Static peak-hour model: queues at traffic lights don't grow with traffic (time-dependent signal delay is the next
  step), so bus lanes barely change bus times in the model.
- Trams, cycling demand and local access for residents are not modelled.

## Licence

MIT. See [`LICENSE`](LICENSE).
