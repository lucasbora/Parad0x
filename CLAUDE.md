# CLAUDE.md — Timișoara Green Mobility & Braess Paradox Urban Simulator ("TM-BraessGreen")

## 1. ROLE & MISSION
You are building a full-stack, production-grade **Interactive Urban Mobility & Lane Reallocation Simulator** for **Primăria Municipiului Timișoara (PMT)** — specifically tailored for **Direcția Generală de Investiții și Mentenanță (Urban Planning)** and **SMTT (Societatea Metropolitană de Transport Timișoara)**.

The application combines:
1. **The Mathematical Engine of Braess's Paradox in Traffic Networks** (based on Burov et al., *Braess's Paradox in Traffic Networks: Avoiding Delays by Removing Roads*, using an Extended Graph with BPR road links + piecewise-linear Phantom Intersection Queue Links solved via Beckmann Potentials, plus interactive inspiration from `leonzhao.dev/science/braess/`).
2. **Interactive Green Mobility Reallocation ("Street Mixer")**: Instead of only bulldozing/closing whole streets, planners and citizens can click any street in Timișoara and visually swap a **Car Lane** (or **Timpark Curb Parking Lane**) into a:
   - **Dedicated STPT Bus / Trolleybus Lane** (`bus`)
   - **Protected Two-Way Bike Lane** (`bike`)
   - **Extended Sidewalk + Urban Tree Canopy** (`pedestrian_trees`)
3. **Dual-Mode Route Recommender**: Whenever a lane is swapped or a cut-through route is filtered, the simulator recalculates Wardrop User Equilibrium in real time and visually renders on the map:
   - **Re-equilibrated Car Routes**: The throttled Braess cut-through route (dashed red) vs. the faster alternative arterial routes (solid blue) that absorb flow without saturating downstream signal queues.
   - **Empowered Green Routes**: Official STPT transit lines (buses, trolleybuses, trams) accelerated by the new bus lane + connected OpenStreetMap cycling corridors bridging i'velo bike-share stations.
4. **Full Integration with the Timișoara City Data & Services Guide**: Live server-side caching proxy for PMT/SMTT APIs + deterministic pre-seeded fallback data for central Timișoara so the app works 100% offline or if City Hall APIs rate-limit during the hackathon demo.

---

## 2. MONOREPO STRUCTURE (4-PERSON PARALLEL WORKFLOW)
Scaffold this exact repository structure so 4 developers (Rareș, Lucas, Laura, Adriana) can work concurrently with zero merge conflicts:

```text
tm-braess-green/
├── docker-compose.yml
├── README.md                        # Setup, architecture, API provenance, MIT License
├── backend/                         # Python 3.11+ / FastAPI (Owned by Rareș & Lucas)
│   ├── pyproject.toml / requirements.txt
│   ├── app/
│   │   ├── main.py                  # FastAPI entry, CORS middleware, API routes
│   │   ├── config.py                # Env vars, custom User-Agent, cache TTLs
│   │   ├── models/
│   │   │   └── schemas.py           # Strict Pydantic v2 request/response contracts
│   │   ├── engine/                  # OWNED BY RAREȘ: Math & Braess Solver
│   │   │   ├── extended_graph.py    # Road links + Phantom intersection queue links
│   │   │   ├── beckmann_solver.py   # Wardrop equilibrium via SciPy / Frank-Wolfe
│   │   │   ├── braess_detector.py   # Lane capacity scaling, greedy route removal, V = Y_new - Y
│   │   │   └── route_recommender.py # Top car arterial routes + STPT transit + OSM bike A*
│   │   ├── services/                # OWNED BY LUCAS: PMT APIs, Caching & Green Scoring
│   │   │   ├── pmt_client.py        # Cached HTTP client with User-Agent for City Hall APIs
│   │   │   ├── osm_overpass.py      # Road network + cycleways + i'velo fetcher
│   │   │   ├── green_scorer.py      # Multi-criteria Bus / Bike / Tree suitability engine
│   │   │   └── seed_timisoara.py    # Rich realistic Timișoara fallback dataset (always works!)
│   │   └── cache/                   # Local JSON/SQLite cache for PMT endpoints
└── frontend/                        # React 18 + TypeScript + Vite + Tailwind (Owned by Laura & Adriana)
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── types/
        │   └── simulator.ts         # Mirrors backend/app/models/schemas.py
        ├── i18n/
        │   └── translations.ts      # Complete RO (default) and EN dictionaries
        ├── components/
        │   ├── map/                 # OWNED BY LAURA: MapLibre GL JS & Deck/GeoJSON Layers
        │   │   ├── TrafficMapCanvas.tsx
        │   │   ├── LayerToggles.tsx
        │   │   ├── RouteOverlayLegend.tsx
        │   │   └── IntersectionQueueMarkers.tsx
        │   └── studio/              # OWNED BY ADRIANA: UX, Street Mixer, Telemetry & Decidem
        │       ├── TopNavbar.tsx
        │       ├── HotspotPresetBar.tsx
        │       ├── StreetCrossSectionMixer.tsx
        │       ├── TelemetryCards.tsx
        │       ├── RecommendedRoutesTabs.tsx
        │       ├── CitizenBraessExplainerModal.tsx
        │       ├── DecidemExportModal.tsx
        │       └── DataProvenanceBadge.tsx
```

---

## 3. MATHEMATICAL ENGINE SPECIFICATION (BUROV ET AL. + LANE REALLOCATION)

Implement the exact mathematical model in `backend/app/engine/`:

### 3.1 Extended Graph Construction ($G = (N, L_{\text{road}} \cup L_{\text{queue}})$)
1. **Road Links ($i \in L_{\text{road}}$):**
   - Attributes: `length_m`, `free_flow_speed_kmh`, `lanes_car`, `lane_capacity_veh_h` (default `900` veh/h per urban lane), `t0` (free-flow travel time in hours or minutes: $t_{0,i} = \text{length}_i / v_{0,i}$), total car capacity $\text{cap}_i = \text{lanes}_{\text{car}, i} \times \text{lane\_capacity}$, and BPR parameters $a_i = 0.15, b_i = 4.0$ (calibrated on the Cluj/Eroilor traffic sensor dataset).
   - **BPR Delay Function:**
     $$\Phi_i(z_i) = t_{0,i} \left( 1 + a_i \left( \frac{z_i}{\max(\text{cap}_i, 1)} \right)^{b_i} \right)$$
   - **Road Beckmann Potential (Analytical Integral):**
     $$\phi_i(z_i) = t_{0,i} \left( z_i + \frac{a_i \, \text{cap}_i}{b_i + 1} \left( \frac{z_i}{\max(\text{cap}_i, 1)} \right)^{b_i + 1} \right)$$

2. **Phantom Intersection Queue Links ($q \in L_{\text{queue}}$):**
   - Inserted between incoming road link $A$ and outgoing road link $B$ at signalized intersections or stop signs.
   - Parameters:
     - Cycle length $D$ (e.g., $90\text{ s}$), red phase duration $L_{\text{red}}$ (e.g., $45\text{ s}$), max vehicles passing per green cycle $n$ (scaled by number of approaching car lanes!).
     - Expected low-flow waiting time:
       $$d_0 = \frac{L_{\text{red}}(1 + L_{\text{red}})}{2D}$$
     - Queue saturation threshold (in $\text{veh/h}$):
       $$s = \frac{3600 \cdot n}{D} \quad \text{(or } s = \frac{3600}{w} \text{ for stop signs)}$$
     - Linear queue growth slope $\alpha > 0$ and intercept $\beta = d_0 - \alpha s$ (so $\Phi_q(s) = d_0$ is continuous at $z_q = s$).
   - **Piecewise-Linear Queue Delay Function:**
     $$\Phi_q(z_q) = \begin{cases} d_0 & \text{if } z_q < s \\ \alpha z_q + \beta & \text{if } z_q \ge s \end{cases}$$
   - **Queue Beckmann Potential (Analytical Integral):**
     $$\phi_q(z_q) = \begin{cases} d_0 z_q & \text{if } z_q < s \\ d_0 s + \frac{\alpha}{2}(z_q^2 - s^2) + \beta(z_q - s) & \text{if } z_q \ge s \end{cases}$$

### 3.2 Wardrop User Equilibrium Solver
- Given Origin-Destination (OD) pairs $k \in O$ with demand $d_k$ ($\text{veh/h}$) and candidate acyclic paths $P^k$ (represented by path-link incidence matrix $R$ where $z = R^T x$):
  $$\min_{x \ge 0} F(x) = \sum_{i \in L_{\text{road}}} \phi_i(z_i) + \sum_{q \in L_{\text{queue}}} \phi_q(z_q) \quad \text{subject to} \quad \sum_{r \in P^k} x_r = d_k \;\;\forall k \in O$$
- Solve using vectorized SciPy SLSQP or Conjugate Frank-Wolfe using the exact gradient $\nabla_x F(x) = R \, \Phi(R^T x)$. Execution time must be $< 100\text{ ms}$ per simulation request.
- Compute **Total System Travel Time**:
  $$Y(z^*) = \sum_{e \in L_{\text{road}} \cup L_{\text{queue}}} z_e^* \Phi_e(z_e^*)$$

### 3.3 Interactive Lane Reallocation & Braess Value ($V$)
When a user changes a street's lane configuration from baseline `original_lanes` (e.g., `["car", "car"]`) to `new_lanes` (e.g., `["car", "bus"]` or `["bus", "bike"]`):
1. Update remaining car lanes $m_{\text{car}}$.
   - If $m_{\text{car}} > 0$: scale road car capacity $\text{cap}_i^{\text{new}} = \text{cap}_i \cdot \frac{m_{\text{car}}}{m_{\text{orig}}}$ and scale downstream phantom queue saturation $s_q^{\text{new}}$.
   - If $m_{\text{car}} == 0$ (full car closure / bus- & bike-only mall): remove routes containing link $i$ from $P^k$ (or set $\text{cap}_i^{\text{new}} = 0.01$).
2. Also support **Greedy Single Route Removal** (filtering a specific cut-through route $r \in P^k$ via turn restrictions/navigation filtering without closing the physical link to local access).
3. Solve for new equilibrium $z_{\text{new}}^*$ and calculate:
   - **Braess Value:** $V = Y_{\text{new}} - Y_{\text{baseline}}$ (when $V < 0$, removing car capacity **reduces** city-wide travel delay!).
   - **Relative Delay Improvement:** $I_{\text{th}} = \frac{Y_{\text{baseline}} - Y_{\text{new}}}{Y_{\text{baseline}}} \times 100\%$.
   - **Bus Travel Time Gain:** If `"bus"` is added to link $i$, STPT buses on link $i$ bypass both the road BPR congestion $\Phi_i(z_i) - t_{0,i}$ and the phantom intersection queue delay $\Phi_q(z_q) - d_0$, traveling at free-flow $t_{0,i}$.

---

## 4. TIMIȘOARA CITY HALL DATA & SERVICES GUIDE RULES (CRITICAL COMPLIANCE)

Implement `backend/app/services/pmt_client.py` and `seed_timisoara.py` adhering strictly to these City Hall rules:

1. **Polite Caching & Custom User-Agent:**
   - Every outgoing HTTP request to `*.primariatm.ro` or `overpass-api.de` MUST include header:
     `User-Agent: TM-BraessGreen-UniHack/1.0 (Timisoara Green Mobility Simulator)`
   - Cache all fetched payloads in `backend/app/cache/*.json` on startup or first request. Never hammer live endpoints in loops.
   - **Offline-First Resilience:** If any external API fails, times out (`> 4s`), or returns non-200, seamlessly fall back to `seed_timisoara.py` so the app never crashes during a live demo.

2. **Official Endpoints & Datasets to Integrate:**
   - **Official Street Register (`Server-side only, no CORS`):**
     - `GET [https://sesizari.primariatm.ro/api/nomenclator/strazi](https://sesizari.primariatm.ro/api/nomenclator/strazi)` (or `[https://cont.primariatm.ro/api/nomenclator/strazi](https://cont.primariatm.ro/api/nomenclator/strazi)`)
     - Maps streets to `codGis`, `denumireCompleta`, `denumireCompletaFaraDiacritice`, `tipStrada`, `cartier`. Match streets using diacritic-free normalization (`...FaraDiacritice`).
   - **Neighbourhood Polygons (`Browser/Server OK`):**
     - `GET [https://sesizari.primariatm.ro/api/zones](https://sesizari.primariatm.ro/api/zones)`
     - Returns 40 official Timișoara `cartiere` as GeoJSON `MultiPolygon`. **Coordinate Order Warning:** GeoJSON is `[lng, lat]`.
   - **Public Transport Network, Lines & Timetables (SMTT / STPT):**
     - `GET [https://cont.primariatm.ro/api/mobile/transit/network](https://cont.primariatm.ro/api/mobile/transit/network)` (routes, stops, `feedVersion`: `"4.31-4"`, valid Nov–Dec 2026).
     - `GET [https://cont.primariatm.ro/api/mobile/transit/lines/](https://cont.primariatm.ro/api/mobile/transit/lines/){routeId}` (route `polyline`, ordered `stops`, `type`: `0` = tram, `3` = bus, `11` = trolleybus, hex `color`).
     - `GET [https://cont.primariatm.ro/api/mobile/transit/stops/](https://cont.primariatm.ro/api/mobile/transit/stops/){stopId}/timetable` (scheduled departures).
     - `GET [https://cont.primariatm.ro/api/mobile/wallet/types?category=transport](https://cont.primariatm.ro/api/mobile/wallet/types?category=transport)` (STPT ticket fares: e.g., `5 RON` 60-min ticket, `18 RON` day pass).
   - **Timpark Paid Parking Zones:**
     - `GET [https://cont.primariatm.ro/api/mobile/parking](https://cont.primariatm.ro/api/mobile/parking)`
     - 710 street segments with zone tariffs: `green` (€0.91/h), `red` (€0.61/h), `yellow` (€0.42/h), `blue` (€0.30/h), SMS short number `7406`. Used to calculate curbside trade-offs and driver vs. transit trip cost comparisons.
   - **Resident Reports / Sesizări (`Server-side only, STRICT GDPR`):**
     - `GET [https://sesizari.primariatm.ro/api/sesizari?startDate=2026-10-14&lat=](https://sesizari.primariatm.ro/api/sesizari?startDate=2026-10-14&lat=){lat}&lng={lng}&radiusMeters=500`
     - **GDPR Rule:** Strip all personal descriptions, citizen names, and photo URLs on the backend immediately! Only return aggregated counts by category (`"Trafic rutier și semne de circulație"`, `"Străzi și trotuare"`, `"Transport public"`) and status (`Inregistrata`, `In lucru`, `Finalizata`).
   - **Landmarks (POIs) & City Events:**
     - `GET [https://cont.primariatm.ro/api/mobile/pois](https://cont.primariatm.ro/api/mobile/pois)` (20 landmarks including `catedrala-mitropolitana`)
     - `GET [https://cont.primariatm.ro/api/mobile/events](https://cont.primariatm.ro/api/mobile/events)` (used to trigger the `"event_rush"` simulation preset).
   - **Open Data (`data.primariatm.ro`) & OpenStreetMap (`Overpass API`):**
     - **Cluj / Eroilor Traffic Counts:** FIWARE NGSI-LD traffic sensor dataset (`July 2026`). **Coordinate Order Warning:** NGSI-LD uses `[lat, lng]` — flip to `[lng, lat]` for MapLibre!
     - **Air Quality & Pollen:** `Justiției` and `Parcul Botanic` stations (`data.primariatm.ro/dataset/air-quality-forecast`).
     - **OSM Cycling Network:** ~150 cycleways, ~80 bike parking spots, 49 i'velo stations. Always display attribution `© OpenStreetMap contributors` and explicitly badge coverage as `"Completeness unverified / Acoperire incompletă"`.

---

## 5. PRE-LOADED TIMIȘOARA BRAESS SCENARIOS (MUST WORK OUT OF THE BOX)

In `backend/app/services/seed_timisoara.py`, build a realistic, self-contained Extended Graph of Central Timișoara (~45 nodes, ~85 directed road links, ~24 phantom intersection queue links, and 12 OD pairs across Cetate, Complexul Studențesc, Iosefin, Fabric, and Circumvalațiunii) with real WGS84 coordinates `[lng, lat]` so the map and math solver work immediately on startup. Highlight these **4 Featured Braess Hotspots**:

1. **`HOTSPOT_CLUJ_EROILOR` — Strada Cluj & Bd. Eroilor de la Tisa (Cartier: Complexul Studențesc / Elisabetin)**
   - `codGis`: `"1042"`, Baseline lanes: `["car", "car", "parking_blue"]`
   - **Braess Physics:** Selfish cut-through traffic from Calea Martirilor / Complexul Studențesc floods Str. Cluj into the signalized intersection at Bd. Mihai Viteazul / Podul Eroilor, pushing phantom queue $z_q = 1180\text{ veh/h} > s = 920\text{ veh/h}$.
   - **Result of Swapping 1 Car Lane $\rightarrow$ Dedicated STPT Bus/Trolleybus Lane + Protected Bike Lane:**
     - Braess Value $V = -148.5\text{ veh}\cdot\text{min}$ ($I_{\text{th}} = +9.4\%$ network travel time reduction!).
     - Downstream queue drops from $58\text{ s}$ to $14\text{ s}$ ($z_q < s$).
     - Accelerates STPT Trolleybus lines **`15`**, **`16`**, and **`M11`** (trip time along corridor drops from `13.5 min` to `7.8 min`).
     - Bridges the missing OSM cycleway gap between Complexul Studențesc and Parcul Justiției (3 i'velo stations connected).
   - **Calibrated Data Badge:** `FIWARE Traffic Sensor · Cluj/Eroilor · Jul 2026`.

2. **`HOTSPOT_FERDINAND_CATEDRALA` — Bd. Regele Ferdinand I (Cartier: Cetate)**
   - `codGis`: `"0218"`, Baseline lanes: `["car", "car"]`
   - **Result of Swapping 1 Car Lane $\rightarrow$ STPT Bus/Tram Priority + Extended Tree Promenade:**
     - Braess Value $V = -92.0\text{ veh}\cdot\text{min}$ ($I_{\text{th}} = +6.8\%$ reduction).
     - Re-routes through-traffic onto Bd. Mihai Viteazul / Bd. Republicii while speeding up STPT lines **`E1`**, **`E2`**, **`33`**, and Trams **`1`**, **`2`**.
     - Directly borders `catedrala-mitropolitana` (`/api/mobile/pois`) and `Parcul Justiției` air-quality station.

3. **`HOTSPOT_CIRCUMVALATIUNII` — Calea Circumvalațiunii / Str. Gheorghe Lazăr (Cartier: Circumvalațiunii)**
   - `codGis`: `"0389"`, Baseline lanes: `["car", "car", "car"]`
   - **Result of Swapping 1 Car Lane $\rightarrow$ Protected Bidirectional Velo Highway:**
     - Braess Value $V = -64.2\text{ veh}\cdot\text{min}$ ($I_{\text{th}} = +5.1\%$ reduction by eliminating merge queue bottlenecks at Gh. Lazăr).
     - Connects dense residential blocks in Dacia/Circumvalațiunii to Piața Unirii cycleways.

4. **`HOTSPOT_SESIZARI_IOSEFIN` — Bd. 16 Decembrie 1989 / Piața Iosefin (Cartier: Iosefin)**
   - `codGis`: `"0815"`, Baseline lanes: `["car", "car", "parking_red"]`
   - **Resident-Validated Hotspot:** Flagged by 19 anonymized citizen reports in `/api/sesizari` (`"Trafic rutier și semne de circulație"` & `"Străzi și trotuare"`).
   - **Result of Swapping 1 Lane $\rightarrow$ Dedicated Transit & Widened Sidewalk:** Eliminates tram/bus mixing bottleneck and reduces corridor delay by $+7.2\%$.

---

## 6. BACKEND API ENDPOINTS (`FastAPI`)

Expose these exact endpoints in `backend/app/main.py` with full CORS enabled for the Vite frontend:

1. `GET /api/health` — Returns status, cache state, and SMTT GTFS `feedVersion` (`"4.31-4"`).
2. `GET /api/network?preset=morning_rush|evening_rush|event_rush`
   - Returns:
     - Full GeoJSON `FeatureCollection` of Timișoara road links (`id`, `codGis`, `streetName`, `cartier`, `lanes`, `baselineFlow`, `capacity`, `vOverC`, `bprDelaySec`, `braessValueV`, `isBraessCandidate`, `greenSuitabilityScores`: `{bus, bike, trees}`, `timparkZone`, `sesizariSummary`).
     - GeoJSON `FeatureCollection` of Phantom Intersection Queue nodes (`id`, `intersectionName`, `flow`, `saturationS`, `isSaturated`, `queueDelaySec`, `d0Sec`).
     - GeoJSON overlays for `zones` (40 cartiere), `stptLines`, `osmCycleways`, `iveloStations`, `pois`, and `events`.
3. `POST /api/simulate`
   - Request body:
     ```json
     {
       "preset": "morning_rush",
       "interventions": [
         {
           "linkId": "LINK_CLUJ_01",
           "codGis": "1042",
           "newLaneAllocation": ["car", "bus", "bike"],
           "filterCutThroughRoute": true
         }
       ]
     }
     ```
   - Response body:
     - `baselineMetrics` vs. `simulatedMetrics` (`totalSystemDelayVehMin`, `braessValueV`, `delayReductionPct`, `avgIntersectionQueueSec`, `co2SavedKgPerHour`, `stptRidersBenefitingPerHour`, `timparkSpacesDelta`, `timparkHourlyRevenueDeltaEur`).
     - `updatedLinks`: Array of updated link flows, speeds, and delays for smooth map transition.
     - `updatedQueues`: Array of updated intersection queue delays and saturation states (`z_q < s`).
     - `recommendedRoutes`:
       - `carRoutes`: List of re-equilibrated car routes (`id`, `name`, `role`: `"recommended_arterial" | "throttled_braess_cut_through"`, `oldTimeMin`, `newTimeMin`, `flowSharePct`, `deltaFlowVehH`, `coordinates`: `[[lng, lat], ...]`).
       - `stptRoutes`: List of STPT routes traversing the corridor (`routeId`, `shortName`, `type`, `color`, `headsign`, `oldCorridorTimeMin`, `newCorridorTimeMin`, `frequencyPerHour`, `nextDepartures`, `ticketCostRon`: `5`, `coordinates`, `stops`).
       - `bikeRoutes`: List of connected cycling routes (`routeId`, `name`, `origin`, `destination`, `lengthKm`, `timeMin`, `protectedPctBefore`, `protectedPctAfter`, `iveloStationsOnRoute`, `coordinates`).
4. `POST /api/decidem-brief`
   - Generates a structured Romanian & English policy consultation brief ready to copy/paste into `[https://decidem.primariatm.ro](https://decidem.primariatm.ro)` and linked to `[https://sesizari.primariatm.ro](https://sesizari.primariatm.ro)`, citing the exact `codGis`, named municipal owners (*Direcția Generală de Investiții și Mentenanță* & *SMTT*), and mathematical Braess metrics.

---

## 7. FRONTEND UX & VISUAL DESIGN SPECIFICATION (`React + MapLibre GL JS + Tailwind`)

### 7.1 Official PMT Visual Identity & Accessibility
- **Color Palette:** Primary PMT Blue `#005BBC`, Dark Slate `#0F172A`, Background `#F8FAFC`, Braess/Velo Emerald `#059669`, Warning Amber `#D97706`, Queue Saturation Red `#DC2626`.
- **Typography:** Load Google Fonts `Inter` (UI) and `JetBrains Mono` (all numbers, equations, `codGis`, timestamps, and badges).
- **WCAG 2.1 AA & i18n:** High contrast, keyboard navigable, instant `RO` (default) / `EN` toggle in the top navbar.

### 7.2 Interactive Map Canvas (`TrafficMapCanvas.tsx`)
- Render using `maplibre-gl` with free vector tiles: `[https://tiles.openfreemap.org/styles/positron](https://tiles.openfreemap.org/styles/positron)` (zero API keys required, works immediately).
- Center on Timișoara (`[21.2285, 45.7537]`, zoom `13.6`, pitch `35°`).
- **Visual Map Layers (with floating `LayerToggles.tsx`):**
  1. **Road Network & Braess Hotspots:** Colored by congestion or Braess status (Glowing Emerald outline on links where $V < 0$). Width proportional to traffic flow $z_i$.
  2. **Animated Flow Particles / Dashes:** Animate flow along active links and highlighted recommended routes (`requestAnimationFrame` dash-array or point interpolation) so users visually see cars re-route and buses/bikes speed up when a lane is swapped!
  3. **Intersection Queue Pillars (`IntersectionQueueMarkers.tsx`):** pulsing red badges at saturated intersections ($z_q \ge s$) that shrink and turn green when the lane swap resolves the Braess bottleneck.
  4. **Recommended Route Polylines:** When a user hovers or clicks a route in the `RecommendedRoutesTabs` drawer, highlight its exact polyline on the map with start/end pins and travel-time callouts.
  5. **Optional Context Layers:** 40 Neighbourhood Polygons (`cartiere`), STPT Transit Network, OSM Cycleways + i'velo pins, Timpark Paid Parking segments, and anonymized Sesizări heat clusters.

### 7.3 Interactive Street Cross-Section Mixer (`StreetCrossSectionMixer.tsx`)
This is the centerpiece UX component on the right-hand studio panel when a street is selected:
- Render an interactive **Top-Down & Cross-Section Street Diagram** with animated lane strips, road markings, directional arrows, and vehicle/tree SVG icons (`[Sidewalk] [Lane 1] [Lane 2] [Curb/Parking] [Sidewalk]`).
- Clicking any lane lets the user switch it live between:
  - `🚗 Bandă Auto` (`car`)
  - `🚌 Bandă Unică STPT` (`bus`)
  - `🚲 Pistă Velo Protejată` (`bike`)
  - `🌳 Trotuar Extins & Arbori` (`pedestrian_trees`)
- Include a toggle switch for **"Filtrează Traseul Scurtătură (Eliminare Rută Braess din Navigație)"** (`filterCutThroughRoute`).
- Every click triggers `POST /api/simulate` and smoothly updates the cross-section illustration, the map flows, the telemetry cards, and the recommended routes.

### 7.4 Recommended Routes & Multimodal Comparison (`RecommendedRoutesTabs.tsx`)
Display 3 clean tabs below the Street Mixer:
1. **Rute Verzi (STPT & Velo):**
   - Shows the accelerated STPT Trolleybus/Bus/Tram lines with official route badges, old vs. new travel times (e.g., `13.5 min → 7.8 min`), real next departure times, and `5 lei` ticket vs. Timpark parking cost comparison.
   - Shows the connected cycling route with distance, travel time, `% protected lane`, and nearby i'velo stations.
   - Clicking any route zooms/highlights it on the map.
2. **Rute Auto Re-echilibrate (Pentru Șoferi):**
   - Shows the **Throttled Braess Cut-Through** (dashed red) vs. the **2–3 Faster Recommended Arterial Routes** (solid blue, e.g., *Via Bd. Mihai Viteazul → Calea Martirilor*) with exact time saved per trip and % of traffic absorbed.
3. **Analiză Matematică & Sesizări (Braess Proof):**
   - Displays the exact BPR $\Phi_i(z_i)$ and Phantom Queue $\Phi_q(z_q)$ saturation chart (showing $z_q$ dropping below $s$), anonymized citizen Sesizări counts within `500m`, and a 1-click **"Explică Paradoxul Braess (Mod Cetățean)"** interactive diamond-network mini-simulator modal.

### 7.5 Data Honesty & Provenance Badges (`DataProvenanceBadge.tsx`)
Every data card MUST display a compact monospace provenance pill showing source and date (e.g., `SMTT GTFS v4.31 · Nov 2026`, `PMT Nomenclator Străzi · codGis #1042`, `Sesizări API · Anonimizat GDPR`, `© OpenStreetMap · Acoperire Velo Incompletă`).

---

## 8. EXECUTION INSTRUCTIONS FOR CLAUDE CODE
Execute the following steps autonomously without stopping for confirmation:
1. Create the full directory structure for `backend/` and `frontend/`.
2. Implement the Python backend (`requirements.txt` with `fastapi`, `uvicorn`, `pydantic`, `numpy`, `scipy`, `networkx`, `httpx`), including the complete extended graph + Beckmann solver (`engine/`), the PMT live-fetch + fallback seed generator (`services/`), and all FastAPI endpoints.
3. Test the backend solver and endpoints via Python CLI or `pytest` to verify that swapping a car lane to a bus/bike lane on `HOTSPOT_CLUJ_EROILOR` produces $V < 0$ and returns valid GeoJSON + route recommendations.
4. Scaffold and implement the React + TypeScript + Vite + Tailwind + MapLibre GL JS + Lucide React frontend (`frontend/`). Ensure zero TypeScript compilation errors (`npm run build` must pass cleanly).
5. Create `docker-compose.yml` and a comprehensive `README.md` documenting the mathematical model, the Timișoara City Hall data sources, the named municipal owners (*Direcția Generală de Investiții și Mentenanță* and *SMTT*), and 1-command startup instructions.

## 9. REFERENCE ARCHITECTURE & UX BLUEPRINT: https://leonzhao.dev/science/braess/

IMPORTANT: Before scaffolding the frontend and solver, use your WebFetch tool (if available) to inspect `https://leonzhao.dev/science/braess/`. You must faithfully replicate the core visual identity, map ergonomics, and solver pipeline of Leon Zhao's Braess's Paradox Traffic Simulator, adapted for Timișoara's Green Mobility transformation:

### 9.1 Leon Zhao's Visual & Cartographic Layout (Full-Bleed Map + Floating HUD)
Do NOT build a clunky, boxed admin template. Replicate Leon Zhao's full-viewport interactive map experience:
1. **Full-Screen Light MapLibre Canvas (`100vw x 100vh`):**
   - Use `MapLibre GL JS` with `https://tiles.openfreemap.org/styles/positron` (OpenFreeMap vector tiles).
   - Apply a clean, ultra-light custom style tuning: mute background buildings, parks, and minor labels into soft slate/grey tones (`#f1f5f9` / `#cbd5e1`) so the road network and Braess paradox highlights have maximum visual contrast.
2. **Floating Top-Left Control Island (Leon Zhao Style):**
   - **Search & Place Jump:** A compact search input (backed by `/api/nomenclator/strazi` diacritic-free street search) to jump to any street in Timișoara.
   - **"Paradox Hotspots" Quick-Select Row:** Pre-computed Timișoara hotspots (sorted busiest/highest-impact first: *Str. Cluj / Eroilor*, *Bd. Regele Ferdinand I*, *Calea Circumvalațiunii*, *Piața Iosefin*) that open and render instantaneously without waiting for Overpass downloads.
   - **Time-of-Day Demand Pills:** One-click horizontal pill selector matching Leon Zhao's exact presets plus Timișoara City Events:
     - `Morning rush` (07:30–09:00: Residential cartiere → Center / Offices / Schools)
     - `Evening rush` (16:30–18:30: Offices / Universities → Residential cartiere)
     - `Now` (Live time-of-day profile weighted by current hour)
     - `Weekend` (Leisure / Shopping / Parks / POIs demand profile)
     - `Event rush` (Driven by `/api/mobile/events` venue attractors)
3. **Floating Bottom-Left Layer & Legend Pill:**
   - Toggle checkboxes for:
     - `Simulated traffic` with a continuous color gradient bar labeled `Fast` (emerald/teal `#10b981` → `#3b82f6`) to `Slow` (amber `#f59e0b` → crimson `#ef4444`).
     - `Braess road` (highlighted with a pulsing magenta/emerald halo or bold distinct casing so users immediately spot every street where removing a car lane speeds up the city).
     - `Green Mobility Overlays` (STPT Transit Lines, OSM Cycleways & i'velo stations, Timpark Curb Zones, Intersection Queue Bottlenecks).

### 9.2 Leon Zhao's Solver Mechanics + Burov et al. Extended Queue Graph
Combine Leon Zhao's solver pipeline with the Burov et al. intersection queue model:
1. **Land-Use Driven OD Demand Generation:**
   - Just like `leonzhao.dev/science/braess/` builds hourly travel demand from OpenStreetMap shops, offices, schools, and residential footprints, weight Timișoara's 40 official neighbourhood polygons (`/api/zones`) and POIs (`/api/mobile/pois`) by land-use trip generation rates for the selected hour (`Morning rush`, `Evening rush`, `Now`, `Weekend`, `Event rush`).
2. **Conjugate Frank-Wolfe + Newton Line Search + Web Worker / Fast Backend Parallelism:**
   - Solve the Wardrop user equilibrium using **Conjugate Frank-Wolfe (CFW)** with **exact Newton line search** on the Beckmann potential objective (supporting both BPR road delay curves and Burov et al. piecewise-linear intersection queue links) to a tight relative gap.
   - Pre-scan all busy candidate streets in parallel (closing a car lane / converting it to Bus or Bike) and rank every street where total system travel time decreases ($Y_{\text{new}} < Y_{\text{baseline}}$, i.e., $V < 0$) or stays virtually unchanged ($|I_{\text{th}}| < 0.5\%$) while unlocking massive green mobility capacity.

### 9.3 Direct Map Interaction: Click-to-Toggle + Differential Flow View
- When a user clicks any street directly on the map:
  1. Immediately show the **Before vs. After Delta** across the entire road network (color-coding surrounding streets by whether their flow/delay decreased in cool green/blue or increased in warm orange, alongside the absolute `Fast → Slow` view).
  2. Slide open the **floating right-hand Street Reallocation & Route Card** (never blocking the center of the map) where the user can:
     - Toggle the street's lanes between **Full Closure (Leon Zhao classic mode)**, **-1 Car Lane → STPT Bus Lane**, **-1 Car Lane → Protected Bike Lane**, or **-1 Car Lane → Extended Sidewalk & Trees**.
     - Inspect the **Recommended Alternative Car Routes** (which absorb the diverted drivers faster) and the **Empowered STPT / Cycling Routes** created by the intervention.