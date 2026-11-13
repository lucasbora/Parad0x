"""Corridor definition and the modelling ASSUMPTIONS used until field data replaces them.

Every value in ASSUMPTIONS is a textbook default, not a Timișoara measurement. The UI
lists them and marks each one "assumption" until the matching CSV in
backend/data/corridor/ provides a measured value.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
OSM_SNAPSHOT = DATA_DIR / "osm" / "corridor_martirilor.json"
INPUT_DIR = DATA_DIR / "corridor"


@dataclass(frozen=True)
class Corridor:
    id: str
    name: str
    # (south, west, north, east) — area that is modelled; links crossing it become gates
    bbox: tuple[float, float, float, float]
    # slightly larger area fetched from OSM so boundary links are complete
    fetch_bbox: tuple[float, float, float, float]
    # the street(s) the scenario is about, in travel order south → north
    main_streets: tuple[str, ...]
    peak_label: str = "07:30–08:30"
    peak_start: str = "07:30"
    peak_end: str = "08:30"
    highways: tuple[str, ...] = field(default=(
        "primary", "secondary", "tertiary", "primary_link", "secondary_link", "tertiary_link", "unclassified",
    ))


CORRIDOR = Corridor(
    id="martirilor-cluj",
    name="Calea Martirilor 1989 / Strada Cluj",
    # Bega bridges (north) → just south of Bd. Liviu Rebreanu (south);
    # Bd. Mihai Viteazu (west alternative) → Aleea F.C. Ripensia / Str. Arieș (east alternative).
    bbox=(45.7380, 21.2240, 45.7500, 21.2440),
    fetch_bbox=(45.7280, 21.2180, 45.7580, 21.2620),
    main_streets=("Calea Martirilor 1989", "Strada Cluj"),
)

# Textbook defaults (HCM / Webster / BPR). Replaced per intersection or link by field data.
ASSUMPTIONS = {
    "saturation_flow_veh_h_per_lane": 1800.0,   # HCM base saturation flow
    "signal_cycle_s": 90.0,                       # typical urban cycle
    "green_ratio": 0.45,                          # g/C for an approach without measured timing
    "unsignalized_capacity_veh_h_per_lane": 1200.0,
    "bpr_alpha": 0.15,
    "bpr_beta": 4.0,
    "default_speed_kmh": 50.0,                    # RO:urban legal limit
    "bus_speed_factor": 1.15,                     # bus vs car free-flow time (acceleration, no stops)
    "gravity_beta_per_min": 0.10,                 # OD distribution impedance (calibrated by Lucas)
}
