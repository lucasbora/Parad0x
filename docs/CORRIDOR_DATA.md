# Field data for the Calea Martirilor / Strada Cluj corridor

The model uses the **real street network** from OpenStreetMap (snapshot in `backend/data/osm/`)
and **never invents traffic**. Results stay hidden until `gate_counts.csv` is filled in.

All files live in `backend/data/corridor/`. The app reloads them automatically when they change.

## What OpenStreetMap already tells us (check these on site)

- **Strada Cluj is one-way southbound** (3–4 lanes) and is tagged as **already having a bus lane**.
  Inbound traffic to the centre uses **Aleea F.C. Ripensia** (northbound) and Calea Martirilor.
- STPT lines that run along Strada Cluj southbound (from the live SMTT feed): **15, 16, E2, E3, M3, M24**.
- 164 directed road links, 67 intersections, 25 with traffic lights, **16 gate points** where traffic enters or leaves the area.

If any of this is wrong on the ground, record it in `lane_checks.csv`.

## Reference lists (generated from OSM — do not edit)

| File | What it is |
|---|---|
| `gates.csv` | Every place traffic enters/leaves the area: gate id, street, side, which counts are needed (`in`, `out`), Google Maps link |
| `intersections.csv` | Every movement at every intersection: node id, from-link id, to-link id, street names and headings |
| `links.csv` | Every directed link: street, heading, length, lanes and speed from OSM (and whether they were assumed) |

Regenerate after changing the corridor box: `cd backend && python scripts/write_corridor_templates.py`.

## What to collect

### 1. `gate_counts.csv` — REQUIRED

Cars entering and leaving at **every gate in `gates.csv`**, morning peak **07:30–08:30**, in 15-minute intervals.

```
gate_id,direction,start,end,vehicles,source,notes
<gate id from gates.csv>,in,07:30,07:45,<cars counted>,video Laura 2026-11-17,
<gate id from gates.csv>,out,07:30,07:45,<cars counted>,video Laura 2026-11-17,
```

- `direction`: `in` = entering the area, `out` = leaving it.
- Count cars + vans. Count buses and trucks separately in `notes` (not in `vehicles`).
- If you could only film 15 minutes, enter that one interval — the app scales it to veh/h and shows a warning.
- Gates you don't count are treated as 0 veh/h and listed as a warning. Prioritise the big ones
  (Calea Martirilor, Bd. Liviu Rebreanu, Bd. Eroilor de la Tisa, the Bega bridges).
- From a published source (e.g. SIDU table)? Put the document, page and **year** in `source`.

**How:** phone on a tripod or wall, landscape, both directions visible, 15 min per gate. Four people can cover
all gates in one peak hour (≈ 4 gates each, walking between nearby ones), or spread over 2 mornings.

### 2. `turn_counts.csv` — to prove the model (calibration)

At 2–3 key intersections (e.g. Calea Martirilor / Bd. Liviu Rebreanu, Piața Leonardo da Vinci), how many cars
make each movement. Take the link ids from `intersections.csv`.

```
node_id,from_link_id,to_link_id,start,end,vehicles,source
<node id>,<from link id>,<to link id>,07:30,07:45,<cars>,video Laura 2026-11-17
```

The app compares these with the model using the **GEH** statistic (target: GEH < 5 on ≥ 85 % of counts).

### 3. `signal_timings.csv` — recommended

From the same videos: stopwatch 3–4 full cycles. `cycle_s` = time between two starts of green, `green_s` = green
time for that approach. Without this the model uses 90 s / 45 % green and labels it as an assumption.

```
node_id,approach_link_id,cycle_s,green_s,source
<node id>,<link id arriving at that node>,<seconds>,<seconds>,stopwatch video 2026-11-17
```

### 4. `lane_checks.csv` — recommended

Car lanes per direction as they really are (Street View or on site), where OSM is wrong or unsure.

```
link_id,car_lanes,bus_lane,source
<link id>,<number of car lanes>,yes|no,site visit 2026-11-17
```

### 5. `travel_times.csv` — to prove the model

GPS runs (phone / Strava) between two gates in the peak hour, along the corridor and its alternative.

```
route,from_gate_id,to_gate_id,start,minutes,source
Martirilor → Bega via Ripensia,<gate id>,<gate id>,07:50,<minutes>,GPS run Rareș 2026-11-17
```

## Assumptions still in the model (shown in the app until replaced)

| Assumption | Value | Replaced by |
|---|---|---|
| Signal timing | cycle 90 s, green 45 % | `signal_timings.csv` |
| Saturation flow | 1800 veh/h/lane (HCM) | calibration |
| Congestion curve | BPR α 0.15, β 4 | calibration |
| Missing speed limits | 50 km/h (RO urban) | `lane_checks.csv` / OSM fix |
| Which gate entering cars leave by | gravity model, β 0.1/min | calibration against `turn_counts.csv` |
| Bus vs car free-flow time | ×1.15 | — |
