"""Where trips start and end, from OpenStreetMap buildings and points of interest.

Homes: residential buildings → floor area (footprint × levels) → estimated residents.
Destinations: offices, shops, schools, health, leisure (POIs + typed buildings), each with a
weight and an activity category whose importance depends on the time-of-day profile.

The box is cut into ~150 m cells; the strongest cells become ZONES, each attached to the
nearest street node in the network's strongly connected core. Every constant is in
config.LANDUSE / POI_WEIGHTS / BUILDING_WEIGHTS and is listed by the API as an assumption.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.corridor.config import BUILDING_WEIGHTS, CORRIDOR, LANDUSE, OSM_SNAPSHOT, POI_WEIGHTS
from app.corridor.osm_network import CorridorNetwork, haversine_m, load_network

RESIDENTIAL_TYPES = {"apartments", "residential", "dormitory", "house", "detached", "semidetached_house", "terrace"}
CATEGORIES = ("office", "school", "retail", "leisure", "health")


@dataclass
class Zone:
    id: str
    node: str                         # network node the zone's trips start/end at
    lng: float
    lat: float
    residents: float
    activity: dict[str, float]        # category → weight
    label: str = ""


@dataclass
class LandUse:
    zones: list[Zone]
    summary: dict[str, Any] = field(default_factory=dict)


def _area_centroid(geom: list[dict]) -> tuple[float, float, float]:
    """Polygon area (m²) and centroid (lng, lat) with a local equirectangular projection."""
    pts = [(g["lon"], g["lat"]) for g in geom]
    if len(pts) < 3:
        return 0.0, pts[0][0], pts[0][1]
    lat0 = math.radians(sum(p[1] for p in pts) / len(pts))
    kx, ky = 111_320 * math.cos(lat0), 110_540
    xy = [(p[0] * kx, p[1] * ky) for p in pts]
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(xy, xy[1:] + xy[:1]):
        c = x1 * y2 - x2 * y1
        a += c
        cx += (x1 + x2) * c
        cy += (y1 + y2) * c
    if abs(a) < 1e-9:
        return 0.0, pts[0][0], pts[0][1]
    a *= 0.5
    return abs(a), cx / (6 * a) / kx, cy / (6 * a) / ky


def _levels(tags: dict[str, str], btype: str) -> tuple[float, bool]:
    raw = tags.get("building:levels", "")
    try:
        v = float(raw.replace(",", "."))
        if 0 < v < 40:
            return v, True
    except ValueError:
        pass
    return float(LANDUSE["default_levels"].get(btype, LANDUSE["default_levels"]["yes"])), False


def _poi_key(tags: dict[str, str]) -> str | None:
    if "office" in tags:
        return "office"
    if "shop" in tags:
        return "shop"
    if "amenity" in tags:
        k = f"amenity:{tags['amenity']}"
        return k if k in POI_WEIGHTS else None
    if "leisure" in tags:
        return "leisure"
    return None


@lru_cache(maxsize=1)
def load_landuse() -> LandUse:
    net: CorridorNetwork = load_network()
    raw = json.loads(OSM_SNAPSHOT.read_text(encoding="utf-8"))
    s, w, n, e = CORRIDOR.bbox
    cell = LANDUSE["zone_cell_m"]
    kx = 111_320 * math.cos(math.radians((s + n) / 2))
    ky = 110_540

    cells: dict[tuple[int, int], dict] = {}

    def cell_of(lng: float, lat: float) -> dict | None:
        if not (s <= lat <= n and w <= lng <= e):
            return None
        key = (int((lng - w) * kx // cell), int((lat - s) * ky // cell))
        c = cells.setdefault(key, {"res": 0.0, "act": {k: 0.0 for k in CATEGORIES}, "sx": 0.0, "sy": 0.0, "sw": 0.0})
        return c

    def add_point(c: dict, lng: float, lat: float, weight: float) -> None:
        c["sx"] += lng * weight
        c["sy"] += lat * weight
        c["sw"] += weight

    stats = {"buildings": 0, "residentialBuildings": 0, "levelsFromOsm": 0, "residents": 0.0, "pois": 0,
             "untypedBuildings": 0}
    for el in raw["elements"]:
        tags = el.get("tags", {})
        if el["type"] == "way" and "building" in tags and "geometry" in el:
            area, lng, lat = _area_centroid(el["geometry"])
            c = cell_of(lng, lat)
            if c is None or area < 20:
                continue
            btype = tags["building"]
            levels, from_osm = _levels(tags, btype)
            floor = area * levels
            stats["buildings"] += 1
            stats["levelsFromOsm"] += from_osm
            res_share = 1.0 if btype in RESIDENTIAL_TYPES else \
                LANDUSE["yes_building_residential_share"] if btype == "yes" else 0.0
            if btype == "yes":
                stats["untypedBuildings"] += 1
            if res_share > 0:
                residents = floor * res_share / LANDUSE["m2_floor_per_resident"]
                c["res"] += residents
                stats["residents"] += residents
                stats["residentialBuildings"] += 1
                add_point(c, lng, lat, residents)
            if btype in BUILDING_WEIGHTS:
                cat, wgt = BUILDING_WEIGHTS[btype]
                c["act"][cat] += floor / 100.0 * wgt
                add_point(c, lng, lat, floor / 100.0 * wgt)
        elif el["type"] in ("node", "way") and "highway" not in tags:
            key = _poi_key(tags)
            if key is None:
                continue
            lng = el.get("lon", el.get("center", {}).get("lon"))
            lat = el.get("lat", el.get("center", {}).get("lat"))
            if lng is None or lat is None:
                continue
            c = cell_of(lng, lat)
            if c is None:
                continue
            cat, wgt = POI_WEIGHTS[key]
            c["act"][cat] += wgt
            add_point(c, lng, lat, wgt)
            stats["pois"] += 1

    # rank cells by their share of homes + share of activity, keep the strongest as zones
    tot_r = sum(c["res"] for c in cells.values()) or 1.0
    tot_a = sum(sum(c["act"].values()) for c in cells.values()) or 1.0
    ranked = sorted(cells.items(), key=lambda kv: -(kv[1]["res"] / tot_r + sum(kv[1]["act"].values()) / tot_a))
    keep = [kv for kv in ranked if kv[1]["sw"] > 0][: LANDUSE["max_zones"]]
    centres = []
    for _, c in keep:
        centres.append([c["sx"] / c["sw"], c["sy"] / c["sw"], c["res"], dict(c["act"])])
    # merge the remaining cells into the nearest kept zone
    for key, c in ranked[len(keep):]:
        if c["sw"] <= 0 or not centres:
            continue
        lng, lat = c["sx"] / c["sw"], c["sy"] / c["sw"]
        best = min(centres, key=lambda z: haversine_m((lng, lat), (z[0], z[1])))
        best[2] += c["res"]
        for k, v in c["act"].items():
            best[3][k] += v

    core = [nd for nid, nd in net.nodes.items() if nid in net.core_nodes]
    by_node: dict[str, Zone] = {}
    for lng, lat, res, act in centres:
        nd = min(core, key=lambda x: haversine_m((lng, lat), (x.lng, x.lat)))
        z = by_node.get(nd.id)
        if z is None:
            by_node[nd.id] = Zone(f"Z{nd.id}", nd.id, nd.lng, nd.lat, res, act, f"Zona {nd.name}")
        else:  # two cells snapped to the same street node → one zone
            z.residents += res
            for k, v in act.items():
                z.activity[k] += v
    zones = sorted(by_node.values(), key=lambda z: z.id)
    stats["residents"] = round(stats["residents"])
    stats["zones"] = len(zones)
    stats["activityByCategory"] = {k: round(sum(z.activity[k] for z in zones), 1) for k in CATEGORIES}
    return LandUse(zones, stats)
