"""OpenStreetMap cycling layers via Overpass (cycleways, bike parking, i'velo).

Cached for a week; falls back to the seed layers. OSM coverage of Timișoara's
cycling network is not verified, so every response carries the badge
"Completeness unverified / Acoperire incompletă" and the ODbL attribution.
"""
from __future__ import annotations

from typing import Any

from app import config
from app.services import seed_timisoara as seed
from app.services.pmt_client import Provenance, _fetch

ATTRIBUTION = "© OpenStreetMap contributors"
COMPLETENESS_BADGE = "Completeness unverified / Acoperire incompletă"

# Central Timișoara bbox (south, west, north, east)
BBOX = (45.725, 21.190, 45.780, 21.265)

QUERY = f"""
[out:json][timeout:25];
(
  way["highway"="cycleway"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
  way["cycleway"~"track|lane"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
  node["amenity"="bicycle_parking"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
  node["amenity"="bicycle_rental"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
);
out geom;
"""


def _seed_layers() -> dict[str, Any]:
    return {
        "cycleways": seed.OSM_CYCLEWAYS,
        "bikeParking": [],
        "iveloStations": seed.ivelo_stations(),
    }


def _validate(raw: Any) -> dict[str, Any]:
    elements = raw.get("elements") if isinstance(raw, dict) else None
    if not elements:
        raise ValueError("no elements")
    cycleways, parking, rental = [], [], []
    for el in elements:
        tags = el.get("tags", {})
        if el.get("type") == "way" and el.get("geometry"):
            cycleways.append({
                "id": f"osm_way_{el['id']}",
                "name": tags.get("name", "Pistă de biciclete"),
                "coordinates": [[g["lon"], g["lat"]] for g in el["geometry"]],
            })
        elif el.get("type") == "node":
            item = {"id": f"osm_node_{el['id']}", "coordinates": [el["lon"], el["lat"]], "name": tags.get("name")}
            if tags.get("amenity") == "bicycle_rental":
                item["name"] = f"i'velo — {tags.get('name', 'stație')}"
                item["capacity"] = int(tags.get("capacity", 10)) if str(tags.get("capacity", "")).isdigit() else 10
                rental.append(item)
            else:
                parking.append(item)
    if not cycleways:
        raise ValueError("no cycleways")
    return {"cycleways": cycleways, "bikeParking": parking, "iveloStations": rental or seed.ivelo_stations()}


def get_cycling_layers() -> tuple[dict[str, Any], Provenance]:
    # Overpass expects the query in the ``data`` parameter.
    return _fetch("overpass_cycling", config.OVERPASS_URL, "overpass", _validate, _seed_layers,
                  params={"data": QUERY})
