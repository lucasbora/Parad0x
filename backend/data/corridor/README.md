# Corridor field data

Fill in the CSV files here; the app reloads them automatically.
**Full instructions: [`docs/CORRIDOR_DATA.md`](../../../docs/CORRIDOR_DATA.md).**

- `gates.csv`, `intersections.csv`, `links.csv` — generated from OpenStreetMap, do not edit.
- Every count row has a `profile`: `morning` 07:30–08:30, `day` 12:30–13:30, `evening` 17:00–18:00, `sunday` 11:00–12:00.
- `gate_counts.csv`, `link_counts.csv` — **calibrate** the land-use estimate for that profile.
- `turn_counts.csv`, `travel_times.csv` — **check** the model (never used for fitting).
- `signal_timings.csv`, `lane_checks.csv` — replace textbook assumptions / correct OSM.

Without counts the model still runs on demand estimated from OSM buildings and POIs, labelled "estimated".
Never put made-up numbers here. Every row needs a `source`.
