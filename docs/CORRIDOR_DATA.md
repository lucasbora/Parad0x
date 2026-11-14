# Field data for the Calea Martirilor / Strada Cluj corridor

The model runs on the **real street network** (main roads + side streets) and **estimates demand from
OpenStreetMap buildings and points of interest**, so it always produces results — labelled
**"estimated"**. Field counts make a profile **"calibrated"** and let us **prove** the model works.
Nothing in `backend/data/corridor/` may ever be invented: every row needs a `source`.

All files live in `backend/data/corridor/`. The app reloads them automatically when they change.

## Time-of-day profiles — count in the right window

| `profile` | Window | Day | Notes |
|---|---|---|---|
| `morning` | 07:30–08:30 | weekday | home → work/school |
| `day` | 12:30–13:30 | weekday | balanced, lower level |
| `evening` | 17:00–18:00 | weekday | work/school → home |
| `sunday` | **11:00–12:00** | Sunday | shopping / leisure — **use this for Sunday counts** |

Every count row has a `profile` column (missing = `morning`). Counts outside the window are accepted but
flagged with a warning. Sunday counts calibrate **only** the Sunday profile; weekday profiles stay "estimated".

## What OpenStreetMap already tells us (check these on site)

- **Strada Cluj is one-way southbound** (3–4 lanes) and is tagged as **already having a bus lane**.
  Inbound traffic to the centre uses **Aleea F.C. Ripensia** (northbound) and Calea Martirilor.
- STPT lines on Strada Cluj southbound (live SMTT feed): **15, 16, E2, E3, M3, M24**.
- Network: **385 directed links** (176 side-street links), 163 intersections (30 with traffic lights),
  **16 gateways** on main roads where traffic enters/leaves the area.
- Land use: **~24,500 residents** estimated from 1,345 housing buildings (289 with floor counts in OSM;
  1,096 buildings are untyped and counted as half housing), **336 POIs**, grouped into 27 zones.

## Reference lists (generated from OSM — do not edit)

| File | What it is |
|---|---|
| `gates.csv` | The 16 gateways: gate id, street, side, which counts are needed (`in`, `out`), Google Maps link |
| `intersections.csv` | Every movement at every intersection: node id, from-link id, to-link id, street names and headings |
| `links.csv` | Every directed link: street, heading, length, lanes and speed from OSM (and whether assumed) |

Regenerate after changing the corridor box: `cd backend && python scripts/write_corridor_templates.py`.
Refetch OSM: `python scripts/fetch_osm_corridor.py`.

## Counting on site: the app's counter

Menu → **Numărătoare teren**: pick a gate / street / turn (gates are listed busiest first by the model
estimate), type your name, press **Start 15 minutes** and tap **+1** for every car (Space/Enter also count,
Backspace undoes). **Stop** saves a row with the real start/end time, the current profile and
`source = tally <name> <date>`. Rows stay on the phone until you download the CSV and put it here.
Count in the profile's window (shown in the counter) — rows outside it are accepted with a warning.

## What to collect

### 1. `gate_counts.csv` — calibrates through-traffic (most important)

Cars entering and leaving at the gates in `gates.csv`, in 15-minute intervals, inside the profile's window.

```
gate_id,direction,profile,start,end,vehicles,source,notes
<gate id from gates.csv>,in,sunday,11:00,11:15,<cars counted>,video Laura 2026-11-15,
<gate id from gates.csv>,out,sunday,11:00,11:15,<cars counted>,video Laura 2026-11-15,
```

- `direction`: `in` = entering the area, `out` = leaving it. Only directions listed in `gates.csv` are valid.
- Count cars + vans. Buses and trucks go in `notes`, not in `vehicles`.
- 15 minutes only? Enter that interval — the app scales it to veh/h and shows a warning.
- Gates you don't count **keep the land-use estimate** (listed as a warning). Prioritise the big ones:
  Calea Martirilor, Bd. Liviu Rebreanu, Bd. Eroilor de la Tisa, the Bega bridges.
- Published source (e.g. SIDU table)? Put document, page and **year** in `source`.

### 2. `link_counts.csv` — calibrates local demand

Cars per hour on a street **inside** the area (mid-block, one direction), e.g. a side street or Calea Martirilor
between two junctions. The model scales its land-use estimate so these streets match.

```
link_id,profile,start,end,vehicles,source,notes
<link id from links.csv>,sunday,11:00,11:15,<cars>,video Adriana 2026-11-15,
```

### 3. `turn_counts.csv` — the PROOF (never used for fitting)

At 2–3 key intersections, how many cars make each movement. Link ids from `intersections.csv`.

```
node_id,from_link_id,to_link_id,profile,start,end,vehicles,source
<node id>,<from link id>,<to link id>,sunday,11:00,11:15,<cars>,video Laura 2026-11-15
```

The app compares them with the model using **GEH** (target: GEH < 5 on ≥ 85 % of counts).

### 4. `travel_times.csv` — the PROOF (never used for fitting)

GPS runs (phone / Strava) between two gates in the profile window, along the corridor and its alternative.

```
route,from_gate_id,to_gate_id,profile,start,minutes,source
Martirilor → Bega via Ripensia,<gate id>,<gate id>,sunday,11:20,<minutes>,GPS run Rareș 2026-11-15
```

### 5. `signal_timings.csv` — replaces the textbook signal assumption

From the same videos: stopwatch 3–4 full cycles. `cycle_s` = start of green to next start of green,
`green_s` = green time for that approach.

```
node_id,approach_link_id,cycle_s,green_s,source
<node id>,<link id arriving at that node>,<seconds>,<seconds>,stopwatch video 2026-11-15
```

### 6. `lane_checks.csv` — corrects OpenStreetMap

```
link_id,car_lanes,bus_lane,source
<link id>,<number of car lanes>,yes|no,Street View 2026-11-14
```

## How the counts are used

| Data | Role | Effect |
|---|---|---|
| `gate_counts` | **fitted** | replaces the estimated gateway flow for that gate and profile |
| `link_counts` | **fitted** | one multiplier on local (land-use) demand so counted streets match |
| `turn_counts`, `travel_times` | **checked** (held out) | GEH / time difference = evidence the model works |
| `signal_timings`, `lane_checks` | network | replace assumptions directly |

`GET /api/corridor/calibration?profile=sunday` returns the fitted values and the held-out checks separately.

## Assumptions still in the model (listed by the API until replaced)

| Assumption | Value | Replaced by |
|---|---|---|
| Residents per building | 30 m² floor / resident; untyped buildings 50 % housing; default floors by type | census / `link_counts` |
| Car trips per resident | 2.3 trips/day × hour share × car share 44 % (**PMUD, unverified**) ÷ 1.3 people/car | PMUD / `link_counts` |
| Destinations | OSM POI + building weights per activity, scaled per profile | `link_counts` |
| Through-traffic | 25 % of each gateway road's capacity at the morning peak; other profiles × hour share × trip level (day 0.76, evening 1.06, Sunday 0.66) | `gate_counts` |
| Share of local trips leaving the area | 60 % | `gate_counts` |
| Signal timing | cycle 90 s, green 45 % | `signal_timings.csv` |
| Saturation flow | 1800 veh/h/lane (HCM); side streets 600 | calibration |
| Congestion curve | BPR α 0.15, β 4 | calibration |
| Bus vs car free-flow time | ×1.15 | — |
| People per car (people-hours) | 1.3 | survey / PMUD |
| Turning rules | OSM restrictions (39 applied) + no U-turns except dead ends | `turn_counts` (check) |
