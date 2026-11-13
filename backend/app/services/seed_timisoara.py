"""Backward-compatible facade over the per-owner seed modules in ``app.seed``.

New code should import from the owning module directly (``app.seed.network``,
``app.seed.demand``, ``app.seed.transit``, ``app.seed.hotspots``, ``app.seed.cycling``,
``app.seed.context``). Do not add data here — this file only re-exports.
"""
from __future__ import annotations

from app.seed.common import haversine_m, strip_diacritics  # noqa: F401
from app.seed.context import (  # noqa: F401
    AIR_QUALITY, CARTIERE_CENTROIDS, CURB_SPACE_LENGTH_M, EUR_TO_RON, EVENTS, FIWARE_SENSOR, POIS,
    SESIZARI_AGGREGATES, TIMPARK_OCCUPANCY, TIMPARK_SMS, TIMPARK_TARIFFS_EUR_H, cartiere_geojson,
    nomenclator_streets, sesizari_for_point,
)
from app.seed.cycling import BIKE_CORRIDORS, OSM_CYCLEWAYS, ivelo_stations  # noqa: F401
from app.seed.demand import (  # noqa: F401
    CENTROID_LAND_USE, EVENT_ATTRACTOR_UPLIFT, OD_PAIRS, PROFILE_LEVEL, TRIP_RATES,
)
from app.seed.hotspots import HOTSPOTS, resolve_hotspots, resolve_link_id  # noqa: F401
from app.seed.network import NODES, QUEUE_MOVEMENTS, SEGMENTS  # noqa: F401
from app.seed.transit import STPT_FARES, STPT_LINES, VEHICLE_CAPACITY, transit_network_payload  # noqa: F401
