# Corridor field data

Fill in the CSV files here; the app reloads them automatically.
**Full instructions: [`docs/CORRIDOR_DATA.md`](../../../docs/CORRIDOR_DATA.md).**

- `gates.csv`, `intersections.csv`, `links.csv` — generated from OpenStreetMap, do not edit.
- `gate_counts.csv` — **required**; results stay hidden until it has data.
- `turn_counts.csv`, `travel_times.csv` — to check the model (GEH, travel times).
- `signal_timings.csv`, `lane_checks.csv` — replace textbook assumptions with measured values.

Never put made-up numbers here. Every row needs a `source`.
