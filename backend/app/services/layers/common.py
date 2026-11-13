"""Small shared GeoJSON helpers (no owner-specific logic)."""
from __future__ import annotations

from typing import Any


def feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def point_features(items: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    """Items with ``coordinates`` ([lng, lat]) or lat/lng(lon) keys → Point features."""
    feats = []
    for it in items:
        c = it.get("coordinates")
        if not c and "lat" in it and ("lng" in it or "lon" in it):
            c = [it.get("lng", it.get("lon")), it["lat"]]
        if not c:
            continue
        props = {k: v for k, v in it.items() if k != "coordinates"}
        props["kind"] = kind
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": c}, "properties": props})
    return feats
