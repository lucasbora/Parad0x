"""Corridor definition, time-of-day profiles and every modelling ASSUMPTION.

Every value in ASSUMPTIONS / LANDUSE / PROFILES is a stated default, not a Timișoara
measurement. The API lists them, and counts in backend/data/corridor/ replace or correct
them (calibration). Change a number here and the whole model follows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
OSM_SNAPSHOT = DATA_DIR / "osm" / "corridor_martirilor.json"
INPUT_DIR = DATA_DIR / "corridor"
CACHE_DIR = Path(__file__).resolve().parents[1] / "cache"

# Road classes that may become GATEWAYS (through-traffic in/out of the box). Side streets that
# cross the box edge are cut at the edge instead (they only serve the neighbourhood).
GATEWAY_CLASSES = ("primary", "secondary", "tertiary", "primary_link", "secondary_link", "tertiary_link")


@dataclass(frozen=True)
class Corridor:
    id: str
    name: str
    # (south, west, north, east) — area that is modelled; main roads crossing it become gateways
    bbox: tuple[float, float, float, float]
    # slightly larger area fetched from OSM so boundary roads are complete
    fetch_bbox: tuple[float, float, float, float]
    main_streets: tuple[str, ...]
    peak_label: str = "07:30–08:30"
    peak_start: str = "07:30"
    peak_end: str = "08:30"
    highways: tuple[str, ...] = field(default=(
        "primary", "secondary", "tertiary", "primary_link", "secondary_link", "tertiary_link",
        "unclassified", "residential", "living_street",
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


@dataclass(frozen=True)
class Profile:
    id: str
    label_ro: str
    label_en: str
    start: str               # count window — counts must be taken in this hour
    end: str
    day: str                 # "weekday" | "sunday"
    hour_share: float        # share of the day's trips that happen in this hour
    trip_level: float        # trips per resident relative to a weekday (Sunday < 1)
    direction: float         # +1 everyone leaves home … −1 everyone returns home
    gravity_beta: float      # how strongly trips prefer nearby places (per minute)
    activity: dict           # how much each destination type attracts in this hour


PROFILES: dict[str, Profile] = {
    "morning": Profile("morning", "Dimineață", "Morning", "07:30", "08:30", "weekday", 0.085, 1.0, 0.7, 0.10,
                       {"office": 1.0, "school": 1.0, "retail": 0.5, "leisure": 0.2, "health": 1.0}),
    "day": Profile("day", "Zi", "Day", "12:30", "13:30", "weekday", 0.065, 1.0, 0.0, 0.12,
                   {"office": 0.6, "school": 0.6, "retail": 1.0, "leisure": 0.8, "health": 1.0}),
    "evening": Profile("evening", "Seară", "End of day", "17:00", "18:00", "weekday", 0.090, 1.0, -0.7, 0.10,
                       {"office": 0.8, "school": 0.3, "retail": 1.0, "leisure": 0.8, "health": 0.6}),
    "sunday": Profile("sunday", "Duminică", "Sunday", "11:00", "12:00", "sunday", 0.075, 0.75, 0.2, 0.12,
                      {"office": 0.1, "school": 0.05, "retail": 1.2, "leisure": 1.5, "health": 0.4}),
}
DEFAULT_PROFILE = "morning"

# Network / traffic engineering defaults (HCM / Webster / BPR)
ASSUMPTIONS = {
    "saturation_flow_veh_h_per_lane": 1800.0,   # HCM base saturation flow
    "signal_cycle_s": 90.0,                       # typical urban cycle
    "green_ratio": 0.45,                          # g/C for an approach without measured timing
    "unsignalized_capacity_veh_h_per_lane": 1200.0,
    "side_street_capacity_veh_h_per_lane": 600.0, # residential / living street (parked cars, give-way)
    "bpr_alpha": 0.15,
    "bpr_beta": 4.0,
    "default_speed_kmh": 50.0,                    # RO:urban legal limit
    "bus_speed_factor": 1.15,                     # bus vs car free-flow time
    "gravity_beta_per_min": 0.10,                 # kept for the gate-only fallback
}

# Default speed (km/h) and lanes per direction by road class when OSM has no tag
CLASS_DEFAULTS = {
    "primary": (50, 2), "secondary": (50, 1), "tertiary": (50, 1),
    "primary_link": (40, 1), "secondary_link": (40, 1), "tertiary_link": (40, 1),
    "unclassified": (40, 1), "residential": (30, 1), "living_street": (20, 1),
}
SIDE_STREET_CLASSES = ("residential", "living_street", "unclassified")

# Turning rules at intersections
TURNS = {
    "apply_osm_restrictions": True,   # no_left_turn, only_straight_on, … relations from the OSM snapshot
    "ban_u_turns": True,              # no U-turns at intersections (allowed only where a road dead-ends)
}

# bump when the model changes in a way that invalidates cached Braess searches
MODEL_VERSION = "v3-turns"

# Land use → trips. Sources: typical European urban values; replace when PMT data is found.
LANDUSE = {
    "m2_floor_per_resident": 30.0,       # gross floor area per resident (useful area ≈ 20 m², +walls/stairs)
    "default_levels": {"apartments": 4, "residential": 3, "dormitory": 5, "house": 1.5, "detached": 1.5,
                       "semidetached_house": 2, "terrace": 2, "yes": 2},
    "yes_building_residential_share": 0.5,   # untyped "building=yes": half counted as housing
    "trips_per_resident_day": 2.3,
    "car_share": 0.44,                   # PMUD Timișoara figure — UNVERIFIED until someone checks the PDF
    "car_share_verified": False,
    "car_occupancy": 1.3,
    "external_share": 0.6,               # share of local trips that leave the box (small area)
    "through_share_of_capacity": 0.25,   # gateway through-traffic in the REFERENCE profile, until counted
    # other profiles scale through-traffic like local trips: hour share × trip level relative to it
    "through_reference_profile": "morning",
    "zone_cell_m": 150.0,
    "max_zones": 32,
}

# Destination weights per OSM feature, grouped into activity categories (inspired by L. Zhao's
# land-use demand; our own values). Building weights are per 100 m² of floor area.
POI_WEIGHTS = {
    "office": ("office", 3.0),
    "shop": ("retail", 1.0),
    "amenity:school": ("school", 6.0), "amenity:college": ("school", 6.0), "amenity:university": ("school", 8.0),
    "amenity:kindergarten": ("school", 3.0),
    "amenity:hospital": ("health", 8.0), "amenity:clinic": ("health", 4.0), "amenity:doctors": ("health", 1.5),
    "amenity:pharmacy": ("health", 1.0),
    "amenity:restaurant": ("leisure", 1.5), "amenity:cafe": ("leisure", 1.2), "amenity:fast_food": ("leisure", 1.2),
    "amenity:bar": ("leisure", 1.0), "amenity:pub": ("leisure", 1.0),
    "amenity:cinema": ("leisure", 3.0), "amenity:theatre": ("leisure", 3.0), "amenity:library": ("leisure", 2.0),
    "amenity:bank": ("office", 1.5), "amenity:post_office": ("office", 1.5), "amenity:townhall": ("office", 3.0),
    "amenity:marketplace": ("retail", 4.0), "amenity:place_of_worship": ("leisure", 1.0),
    "leisure": ("leisure", 0.8),
}
BUILDING_WEIGHTS = {   # building type → (category, weight per 100 m² floor)
    "office": ("office", 1.5), "commercial": ("retail", 1.0), "retail": ("retail", 1.2), "supermarket": ("retail", 1.5),
    "university": ("school", 1.0), "school": ("school", 1.0), "college": ("school", 1.0), "kindergarten": ("school", 0.8),
    "hospital": ("health", 1.0), "industrial": ("office", 0.3), "warehouse": ("office", 0.2),
}
