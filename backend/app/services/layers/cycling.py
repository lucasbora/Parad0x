"""Cycling layers: OSM cycleways + i'velo stations. OWNER: Laura."""
from __future__ import annotations

from typing import Any

from app.services import osm_overpass
from app.services.layers.common import feature_collection, point_features


def cycling_geojson() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Returns (cycleways FC, i'velo FC, provenance entries)."""
    cycling, prov = osm_overpass.get_cycling_layers()
    cycleways = [{
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": c["coordinates"]},
        "properties": {"id": c["id"], "name": c.get("name"), "source": prov.source},
    } for c in cycling["cycleways"]]
    ivelo = point_features(cycling["iveloStations"], "ivelo")
    return feature_collection(cycleways), feature_collection(ivelo), [prov.as_dict()]


def osm_badges() -> dict[str, str]:
    return {"attribution": osm_overpass.ATTRIBUTION, "badge": osm_overpass.COMPLETENESS_BADGE}
