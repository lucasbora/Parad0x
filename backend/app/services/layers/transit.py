"""STPT line layer (live SMTT polylines when available). OWNER: Rareș."""
from __future__ import annotations

from typing import Any

from app.seed.transit import STPT_LINES
from app.services import live_data, pmt_client
from app.services.layers.common import feature_collection


def stpt_lines_geojson(g: Any) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Returns (FeatureCollection, provenance entries, transit network payload)."""
    transit, prov = pmt_client.get_transit_network()
    lines_live = live_data.live_lines()
    feats = []
    for l in STPT_LINES:
        live = lines_live.get(l["shortName"], {})
        poly = (live.get("polylines") or {}).get(0)
        feats.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": poly or [g.nodes[n]["coordinates"] for n in l["nodes"]]},
            "properties": {
                "routeId": live.get("routeId", l["routeId"]), "shortName": l["shortName"],
                "type": live.get("type", l["type"]), "color": live.get("color") or l["color"],
                "headsign": l["headsign"], "longName": live.get("longName"),
                "frequencyPerHour": l["frequencyPerHour"],
                "geometrySource": "SMTT GTFS (live)" if poly else "schematic",
            },
        })
    return feature_collection(feats), [prov.as_dict()], transit
