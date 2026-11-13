"""Context overlays: cartiere, POIs, events, Timpark, sesizări, air quality, FIWARE. OWNER: Adriana."""
from __future__ import annotations

from typing import Any

from app.seed import context as ctx
from app.services import live_data, pmt_client
from app.services.layers.common import feature_collection, point_features


def context_overlays(g: Any, hotspots: list[dict]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Returns (overlays dict, FIWARE sensor dict, provenance entries)."""
    zones, zones_prov = pmt_client.get_zones()
    _, pois_prov = pmt_client.get_pois()
    _, events_prov = pmt_client.get_events()
    _, parking_prov = pmt_client.get_parking()
    _, nomen_prov = pmt_client.get_nomenclator()

    sesizari = []
    for h in hotspots:
        summ, _ = pmt_client.get_sesizari_summary(h["center"][1], h["center"][0], 500)
        sesizari.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": h["center"]},
                         "properties": {"hotspotId": h["id"], **summ}})

    overlays = {
        "zones": zones,
        "pois": feature_collection(point_features(live_data.normalized_pois(), "poi")),
        "events": feature_collection(point_features(live_data.normalized_events(), "event")),
        "timparkSegments": feature_collection(live_data.timpark_features(g)),
        "sesizariClusters": feature_collection(sesizari),
        "airQuality": feature_collection(point_features(ctx.AIR_QUALITY, "air_quality")),
    }
    sensor = {
        **{k: v for k, v in ctx.FIWARE_SENSOR.items() if k != "location_lat_lng"},
        "coordinates": pmt_client.ngsi_point_to_lnglat(ctx.FIWARE_SENSOR["location_lat_lng"]),
    }
    provenance = [p.as_dict() for p in (zones_prov, pois_prov, events_prov, nomen_prov, parking_prov)]
    return overlays, sensor, provenance
