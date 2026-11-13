# TM-BraessGreen — Timișoara Green Mobility & Braess Paradox Simulator

> **Branch `corridor-mvp`:** the app is being narrowed to one real corridor (Calea Martirilor / Strada Cluj) on the
> real OpenStreetMap network, with results only from field counts. See [`docs/TEAM_PLAN.md`](docs/TEAM_PLAN.md) and
> [`docs/CORRIDOR_DATA.md`](docs/CORRIDOR_DATA.md). The new API is `/api/corridor` (+ `/simulate`, `/sensitivity`,
> `/calibration`); the older city-wide demo endpoints below still exist but the frontend no longer uses them.

Interactive lane-reallocation simulator for **Primăria Municipiului Timișoara (PMT)**, built for the
**Direcția Generală de Investiții și Mentenanță** (urban planning) and **SMTT — Societatea Metropolitană de
Transport Timișoara**. Click any street, swap a car lane for an STPT bus lane, a protected bike lane or a
wider sidewalk with trees, and the Wardrop user equilibrium is re-solved in milliseconds. You see where
removing car capacity *reduces* city-wide delay (Braess's paradox), which car routes absorb the traffic, and
which STPT lines and cycling corridors get faster.

UX inspired by Leon Zhao's [Braess's Paradox Simulator](https://leonzhao.dev/science/braess/): a full-bleed
light map, a floating control island, time-of-day demand pills, a "Simulated traffic: Fast → Slow" legend and
"Braess road" halos. The maths follows Burov et al., *Braess's Paradox in Traffic Networks: Avoiding Delays by
Removing Roads* (BPR road links + phantom intersection queue links, Beckmann potentials).

---

## 1-command start

```bash
docker compose up --build          # UI → http://localhost:8080   API → http://localhost:8000/docs
```

Offline demo (never calls PMT, SMTT or Overpass): `TMBG_OFFLINE=1 docker compose up --build`.

### Local development

```bash
# backend (Python 3.11+)
cd backend
python -m venv .venv && .venv/Scripts/activate        # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest -q                                             # 26 tests, hermetic (offline + temp cache)

# frontend (Node 20+)
cd frontend
npm install
npm run dev                                           # http://localhost:5173  (proxies /api → :8000)
npm run build                                         # tsc -b && vite build — zero TS errors
```

---

## Repository layout (4-person parallel workflow)

```text
backend/  (Rareș & Lucas)          FastAPI · Python
  app/main.py                      routes, CORS, gzip, background cache warm-up
  app/config.py                    env vars, polite User-Agent, cache TTLs, solver tolerances
  app/models/schemas.py            strict Pydantic v2 contracts (camelCase)
  app/engine/                      extended_graph · beckmann_solver · braess_detector · route_recommender (Rareș) · demand_model (Lucas)
  app/seed/                        per-owner seed data: network, transit, hotspots (Rareș) · demand (Lucas) · cycling (Laura) · context (Adriana)
  app/services/                    pmt_client · live_data · osm_overpass · green_scorer · simulator (assembler) · seed_timisoara (re-export facade)
  app/services/layers/             /api/network layer builders: roads, transit (Rareș) · cycling (Laura) · context (Adriana)
  tests/                           solver, API and frozen-interface tests
frontend/ (Laura & Adriana)        React 18 · TypeScript · Vite · Tailwind · MapLibre GL JS · lucide-react
  src/types/simulator.ts           mirrors schemas.py
  src/i18n/translations.ts         RO (default) + EN
  src/components/map/   (Laura)    TrafficMapCanvas · LayerToggles · RouteOverlayLegend · IntersectionQueueMarkers
  src/components/studio/(Adriana)  TopNavbar · HotspotPresetBar · StreetCrossSectionMixer · TelemetryCards ·
                                   RecommendedRoutesTabs · CitizenBraessExplainerModal · DecidemExportModal · DataProvenanceBadge
```

---

## Mathematical model

**Extended graph** G = (N, L_road ∪ L_queue): 46 nodes, 134 directed road links, 34 phantom queue links,
12 OD pairs, 32 candidate routes.

| Element | Delay Φ | Beckmann potential φ = ∫Φ |
|---|---|---|
| Road (BPR, a = 0.15, b = 4) | t₀(1 + a(z/cap)ᵇ), cap = lanes_car × 900 veh/h | t₀(z + a·cap/(b+1)·(z/cap)^(b+1)) |
| Phantom queue (Burov) | d₀ if z < s; αz + β otherwise, β = d₀ − αs | d₀z; or d₀s + α/2(z² − s²) + β(z − s) |

where d₀ = L(1+L)/(2D), s = 3600·n/D, and n scales with the number of approaching car lanes.

**Equilibrium.** min_{x≥0} Σφ(Rᵀx) subject to Σ_{r∈Pᵏ} x_r = d_k. It is solved by **Conjugate Frank–Wolfe**
(Mitradjieva & Lindberg) with an **exact Newton line search** (bisection-safeguarded) down to a relative gap
of 2·10⁻³. A **path-based Newton (gradient-projection) polish** then finishes the run to **10⁻⁶**, matching the
reference simulator's one-in-a-million check. Typical run: about 20 iterations in 3–7 ms (spec limit: 100 ms).
`pytest` checks that pure CFW converges to the same equilibrium.

**Lane reallocation.** When a lane changes, cap is multiplied by m_car/m_orig, and the saturation s of every
queue fed by that link is scaled the same way. With m_car = 0 the street is closed to cars: its routes are
removed, keeping at least one route per OD. **filterCutThroughRoute** runs Burov's **greedy single-route
removal** restricted to routes over the edited link. Outputs: **V = Y_new − Y_baseline** and
**I_th = (Y_b − Y_new)/Y_b**, where Y = Σ z·Φ in veh·min/h. Buses on a link with a bus lane run at t₀ and only
wait d₀ at the next queue.

**Demand (§9.2).** Each OD centroid has a land-use mix (residential, office, school, retail, leisure). The
trip-production and attraction rates per profile (`morning_rush`, `evening_rush`, `weekend`, `event_rush`, and
`now` as an hour-weighted blend) drive a corridor gravity model. Event attractors come from
`/api/mobile/events`.

**Parallel scan.** On first load of a preset, every street carrying at least 250 veh/h loses one car lane in
turn (a full closure if it has only one). The streets are ranked by V on a thread pool; those with V < 0 get
the emerald/magenta "Braess road" halo.

### Featured hotspots — actual solver output (morning rush, suggested swap)

| Hotspot | Swap | V (veh·min/h) | I_th | Shared downstream queue |
|---|---|---|---|---|
| Str. Cluj / Bd. Eroilor (`LINK_CLUJ_01`) | car,car,parking → car,bus,bike | **−668** | +0.95 % | 77 s → 51 s |
| + filter cut-through route | greedy removal | **−1 232** | +1.74 % | |
| Bd. Regele Ferdinand I | car,car → car,bus | **−385** | +0.54 % | 87 s → 73 s |
| Calea Circumvalațiunii / Gh. Lazăr | 3 car → 2 car + bike | **−729** | +1.03 % | 88 s → 64 s |
| Bd. 16 Decembrie 1989 / Iosefin | car,car,parking → car,bus,trees | **−551** | +0.78 % | 79 s → 60 s |

These numbers are computed live, not hard-coded. The design brief's illustrative targets (for example
V = −148.5, I_th = +9.4 % for Cluj) are **not** reproduced exactly: I_th here is measured over the whole
network's travel time, so the percentages are smaller. The hotspots are calibrated as morning (inbound)
Braess cut-throughs. In the evening and weekend profiles the traffic runs the other way and the solver
honestly reports V ≥ 0 for them; the scan finds other evening candidates instead.

---

## Timișoara City Hall data (Data & Services Guide compliance)

* Every outgoing request sends `User-Agent: TM-BraessGreen-UniHack/1.0 (Timisoara Green Mobility Simulator)`
  with a 4 s timeout. Payloads are cached in `backend/app/cache/*.json` with per-dataset TTLs.
* Offline-first: any failure, timeout or non-200 falls back to `services/seed_timisoara.py`. The UI shows
  `live`, `cache` or `seed` provenance pills on every card.
* **GDPR:** Sesizări are reduced to counts by category and status before anything is cached or returned. Names,
  descriptions and photo URLs never leave `pmt_client.sanitize_sesizari` (covered by a test).

| Dataset | Endpoint | Status observed (13 Nov 2026) |
|---|---|---|
| Street register | `sesizari.primariatm.ro/api/nomenclator/strazi` | **live**: 1 370 streets, matched by diacritic-free name |
| Transit network | `cont.primariatm.ro/api/mobile/transit/network` | **live**: feed `4.31-4`, 58 routes, 890 stops, encoded polylines → real line geometry and colours |
| Stop timetables | `/api/mobile/transit/stops/{id}/timetable` | **live**: real next departures at the stop nearest the edited street |
| Fares | `/api/mobile/wallet/types?category=transport` | **live**: 5 lei / 60 min |
| Timpark | `/api/mobile/parking` | **live**: 795 features; tariffs green €0.89, red €0.60, yellow €0.42, blue €0.30 · SMS 7406 |
| POIs / events | `/api/mobile/pois`, `/api/mobile/events` | **live**: 20 POIs; events shown only when the venue is geocoded |
| Neighbourhoods | `sesizari.primariatm.ro/api/zones` | 404 → seed: 40 approximate Voronoi cartiere |
| Sesizări | `sesizari.primariatm.ro/api/sesizari?...` | 400 with the documented params → seed aggregates |
| OSM cycling | Overpass API | 502 at test time → seed cycleways + 49 i'velo stations (badged *Completeness unverified / Acoperire incompletă*, © OpenStreetMap contributors) |
| FIWARE Cluj/Eroilor, air quality | data.primariatm.ro | seed snapshot; NGSI-LD `[lat, lng]` flipped to `[lng, lat]` |

**codGis note.** The live register's codes differ from those in the design brief. For example Strada Cluj is
**193** (brief: 1042), Bd. Regele Ferdinand I is **1175** (brief: 0218), Calea Circumvalațiunii is **182**
(brief: 0389) and Bd. 16 Decembrie 1989 is **928** (brief: 0815). The UI and the Decidem brief show the
official code whenever the register is reachable. `/api/simulate` accepts either code.

**Geometry note.** The traffic graph is a schematic of central Timișoara: intersections are placed
approximately and links are straight lines. STPT lines are drawn on their real SMTT polylines when the feed
is live.

---

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | status, cache provenance, feedVersion `4.31-4`, solver info |
| GET | `/api/network?preset=` | roads and queues GeoJSON plus overlays (zones, STPT, cycleways, i'velo, POIs, events, Timpark, sesizări, air), hotspots, baseline metrics |
| POST | `/api/simulate` | `{preset, interventions:[{linkId, codGis, newLaneAllocation, filterCutThroughRoute}]}` → metrics, updated links and queues, car / STPT / bike routes, Φ charts |
| POST | `/api/decidem-brief` | RO + EN consultation brief citing codGis, the owners and the Braess metrics |
| GET | `/api/streets/search?q=` | diacritic-free Nomenclator search |
| GET | `/api/hotspots`, `/api/nomenclator/strazi`, `/api/sesizari/summary` | helpers |

---

## License

MIT. See [LICENSE](LICENSE). Map data © OpenStreetMap contributors (ODbL); tiles by OpenFreeMap.
