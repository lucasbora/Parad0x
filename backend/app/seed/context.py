"""Context seed: POIs, events, Timpark, Sesizări, air quality, FIWARE, cartiere, street register.

OWNER: Adriana. Several values here are ILLUSTRATIVE (see docs/TEAM_PLAN.md, honesty pass).
"""
from __future__ import annotations

import math
from typing import Any

from app.seed.common import haversine_m, strip_diacritics
from app.seed.hotspots import HOTSPOTS
from app.seed.network import NODES, SEGMENTS


# ---------------------------------------------------------------------------
# POIs (/api/mobile/pois) and events (/api/mobile/events)
# ---------------------------------------------------------------------------

POIS: list[dict[str, Any]] = [
    {"id": "catedrala-mitropolitana", "name": "Catedrala Mitropolitană", "category": "landmark", "coordinates": [21.2243, 45.7505]},
    {"id": "opera-nationala", "name": "Opera Națională Română", "category": "culture", "coordinates": [21.2262, 45.7545]},
    {"id": "piata-unirii", "name": "Piața Unirii", "category": "landmark", "coordinates": [21.2290, 45.7578]},
    {"id": "piata-victoriei", "name": "Piața Victoriei", "category": "landmark", "coordinates": [21.2253, 45.7527]},
    {"id": "bastionul-theresia", "name": "Bastionul Theresia", "category": "culture", "coordinates": [21.2340, 45.7565]},
    {"id": "muzeul-de-arta", "name": "Muzeul Național de Artă", "category": "culture", "coordinates": [21.2296, 45.7584]},
    {"id": "castelul-huniade", "name": "Castelul Huniade", "category": "culture", "coordinates": [21.2265, 45.7522]},
    {"id": "sinagoga-cetate", "name": "Sinagoga din Cetate", "category": "landmark", "coordinates": [21.2278, 45.7568]},
    {"id": "parcul-rozelor", "name": "Parcul Rozelor", "category": "park", "coordinates": [21.2330, 45.7500]},
    {"id": "parcul-justitiei", "name": "Parcul Justiției", "category": "park", "coordinates": [21.2302, 45.7444]},
    {"id": "parcul-botanic", "name": "Parcul Botanic", "category": "park", "coordinates": [21.2245, 45.7612]},
    {"id": "parcul-central", "name": "Parcul Central", "category": "park", "coordinates": [21.2215, 45.7530]},
    {"id": "universitatea-politehnica", "name": "Universitatea Politehnica Timișoara", "category": "education", "coordinates": [21.2300, 45.7470]},
    {"id": "universitatea-de-vest", "name": "Universitatea de Vest", "category": "education", "coordinates": [21.2310, 45.7475]},
    {"id": "stadion-dan-paltinisanu", "name": "Stadionul Dan Păltinișanu", "category": "sport", "coordinates": [21.2450, 45.7400]},
    {"id": "gara-de-nord", "name": "Gara Timișoara Nord", "category": "transport", "coordinates": [21.2068, 45.7506]},
    {"id": "piata-traian", "name": "Piața Traian", "category": "landmark", "coordinates": [21.2462, 45.7584]},
    {"id": "biserica-millenium", "name": "Biserica Millenium", "category": "landmark", "coordinates": [21.2468, 45.7578]},
    {"id": "iulius-town", "name": "Iulius Town", "category": "retail", "coordinates": [21.2287, 45.7668]},
    {"id": "piata-maria", "name": "Piața Maria (Biserica Reformată)", "category": "landmark", "coordinates": [21.2172, 45.7500]},
]


EVENTS: list[dict[str, Any]] = [
    {"id": "evt-poli-meci", "title": "SSU Poli Timișoara — meci de campionat", "venue": "Stadionul Dan Păltinișanu",
     "poiId": "stadion-dan-paltinisanu", "attractorNode": "N_COMPLEX", "start": "2026-11-21T18:00:00+02:00",
     "expectedAttendance": 9000, "coordinates": [21.2450, 45.7400]},
    {"id": "evt-concert-victoriei", "title": "Concert în Piața Victoriei", "venue": "Piața Victoriei",
     "poiId": "piata-victoriei", "attractorNode": "N_OPERA", "start": "2026-11-28T19:00:00+02:00",
     "expectedAttendance": 12000, "coordinates": [21.2253, 45.7527]},
    {"id": "evt-targ-craciun", "title": "Târgul de Crăciun Timișoara", "venue": "Piața Victoriei",
     "poiId": "piata-victoriei", "attractorNode": "N_CATEDRALA", "start": "2026-11-27T10:00:00+02:00",
     "expectedAttendance": 15000, "coordinates": [21.2255, 45.7535]},
]


# ---------------------------------------------------------------------------
# Timpark parking tariffs (€/h) + SMS short number
# ---------------------------------------------------------------------------

TIMPARK_TARIFFS_EUR_H = {"green": 0.91, "red": 0.61, "yellow": 0.42, "blue": 0.30}


TIMPARK_SMS = "7406"


TIMPARK_OCCUPANCY = 0.72  # peak-hour occupancy used for revenue estimates


CURB_SPACE_LENGTH_M = 5.5


EUR_TO_RON = 4.97


# ---------------------------------------------------------------------------
# Sesizări — already aggregated (GDPR: no descriptions, names or photos).
# ---------------------------------------------------------------------------

SESIZARI_AGGREGATES: dict[str, dict[str, Any]] = {
    "HOTSPOT_SESIZARI_IOSEFIN": {
        "radiusMeters": 500, "total": 19,
        "byCategory": {"Trafic rutier și semne de circulație": 11, "Străzi și trotuare": 6, "Transport public": 2},
        "byStatus": {"Inregistrata": 7, "In lucru": 8, "Finalizata": 4},
    },
    "HOTSPOT_CLUJ_EROILOR": {
        "radiusMeters": 500, "total": 12,
        "byCategory": {"Trafic rutier și semne de circulație": 7, "Străzi și trotuare": 3, "Transport public": 2},
        "byStatus": {"Inregistrata": 4, "In lucru": 5, "Finalizata": 3},
    },
    "HOTSPOT_FERDINAND_CATEDRALA": {
        "radiusMeters": 500, "total": 9,
        "byCategory": {"Trafic rutier și semne de circulație": 4, "Străzi și trotuare": 4, "Transport public": 1},
        "byStatus": {"Inregistrata": 3, "In lucru": 3, "Finalizata": 3},
    },
    "HOTSPOT_CIRCUMVALATIUNII": {
        "radiusMeters": 500, "total": 8,
        "byCategory": {"Trafic rutier și semne de circulație": 5, "Străzi și trotuare": 2, "Transport public": 1},
        "byStatus": {"Inregistrata": 2, "In lucru": 4, "Finalizata": 2},
    },
}


def sesizari_for_point(lng: float, lat: float, radius_m: float = 500) -> dict[str, Any]:
    """Deterministic aggregated counts for an arbitrary point (fallback)."""
    best = None
    for h in HOTSPOTS:
        d = haversine_m((lng, lat), tuple(h["center"]))
        if d <= radius_m * 1.6 and (best is None or d < best[0]):
            best = (d, h["id"])
    if best:
        agg = dict(SESIZARI_AGGREGATES[best[1]])
        agg["source"] = "seed"
        return agg
    seed = int(abs(lng * 10_000) + abs(lat * 10_000)) % 7
    total = 2 + seed
    a = max(1, total // 2)
    b = max(0, total - a - 1)
    return {
        "radiusMeters": int(radius_m), "total": total, "source": "seed",
        "byCategory": {"Trafic rutier și semne de circulație": a, "Străzi și trotuare": b, "Transport public": total - a - b},
        "byStatus": {"Inregistrata": total // 3, "In lucru": total // 3, "Finalizata": total - 2 * (total // 3)},
    }


# ---------------------------------------------------------------------------
# Air quality (data.primariatm.ro air-quality-forecast) — seed snapshot
# ---------------------------------------------------------------------------

AIR_QUALITY = [
    {"station": "Justiției", "coordinates": [21.2302, 45.7444], "pm10": 31.0, "pm25": 18.0, "no2": 38.0,
     "pollen": "scăzut", "aqiLabel": "Moderat"},
    {"station": "Parcul Botanic", "coordinates": [21.2245, 45.7612], "pm10": 22.0, "pm25": 12.0, "no2": 24.0,
     "pollen": "scăzut", "aqiLabel": "Bun"},
]


FIWARE_SENSOR = {
    "id": "urn:ngsi-ld:TrafficFlowObserved:cluj-eroilor-01",
    "name": "Cluj / Eroilor",
    # NGSI-LD convention used by the dataset is [lat, lng]; flipped when exported.
    "location_lat_lng": [45.7444, 21.2349],
    "intensity_veh_h_peak": 1180,
    "dateObserved": "2026-07",
}


# ---------------------------------------------------------------------------
# Cartiere (40 official neighbourhoods) — approximate polygons via clipped
# Voronoi tessellation of neighbourhood centroids.
# ---------------------------------------------------------------------------

CARTIERE_CENTROIDS: list[tuple[str, float, float]] = [
    ("Cetate", 21.2275, 45.7560), ("Iosefin", 21.2080, 45.7475), ("Elisabetin", 21.2235, 45.7430),
    ("Fabric", 21.2470, 45.7595), ("Complexul Studențesc", 21.2395, 45.7455), ("Circumvalațiunii", 21.2120, 45.7650),
    ("Dacia", 21.2225, 45.7735), ("Calea Aradului", 21.2330, 45.7740), ("Mehala", 21.1950, 45.7640),
    ("Ronaț", 21.1860, 45.7740), ("Calea Torontalului", 21.1990, 45.7740), ("Blașcovici", 21.2100, 45.7790),
    ("Ion Ionescu de la Brad", 21.2380, 45.7840), ("Tipografilor", 21.2420, 45.7750), ("Calea Lipovei", 21.2510, 45.7690),
    ("Bucovina", 21.2640, 45.7700), ("Kuntz", 21.2690, 45.7610), ("Calea Lugojului", 21.2710, 45.7520),
    ("Ciarda Roșie", 21.2730, 45.7390), ("Calea Buziașului", 21.2560, 45.7440), ("Calea Martirilor", 21.2430, 45.7330),
    ("Soarelui", 21.2380, 45.7230), ("Calea Girocului", 21.2260, 45.7280), ("Odobescu", 21.2320, 45.7365),
    ("Steaua", 21.2100, 45.7300), ("Fratelia", 21.1990, 45.7320), ("Calea Șagului", 21.2150, 45.7375),
    ("Freidorf", 21.1830, 45.7380), ("Plopi", 21.2760, 45.7710), ("Ghiroda Nouă", 21.2860, 45.7620),
    ("Badea Cârțan", 21.2400, 45.7655), ("Dâmbovița", 21.1980, 45.7460), ("Dorobanților", 21.1880, 45.7500),
    ("Modern", 21.2560, 45.7525), ("Popa Șapcă", 21.2190, 45.7335), ("Mircea cel Bătrân", 21.2040, 45.7390),
    ("Antenei", 21.2470, 45.7790), ("Kogălniceanu", 21.2190, 45.7820), ("Lunei", 21.2490, 45.7270),
    ("Aeroport Vest", 21.1760, 45.7620),
]


_ZONE_BBOX = (21.165, 45.712, 21.300, 45.795)


def _clip_polygon(poly: list[tuple[float, float]], bbox: tuple[float, float, float, float]) -> list[tuple[float, float]]:
    """Sutherland–Hodgman clip of a convex polygon to an axis-aligned bbox."""
    xmin, ymin, xmax, ymax = bbox

    def clip(points, inside, intersect):
        out = []
        for i, cur in enumerate(points):
            prev = points[i - 1]
            if inside(cur):
                if not inside(prev):
                    out.append(intersect(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(intersect(prev, cur))
        return out

    def ix(x0):
        return lambda p, q: (x0, p[1] + (q[1] - p[1]) * (x0 - p[0]) / ((q[0] - p[0]) or 1e-12))

    def iy(y0):
        return lambda p, q: (p[0] + (q[0] - p[0]) * (y0 - p[1]) / ((q[1] - p[1]) or 1e-12), y0)

    pts = poly
    for inside, inter in (
        (lambda p: p[0] >= xmin, ix(xmin)), (lambda p: p[0] <= xmax, ix(xmax)),
        (lambda p: p[1] >= ymin, iy(ymin)), (lambda p: p[1] <= ymax, iy(ymax)),
    ):
        pts = clip(pts, inside, inter)
        if not pts:
            break
    return pts


def cartiere_geojson() -> dict[str, Any]:
    """40 approximate neighbourhood polygons as GeoJSON MultiPolygons ([lng, lat])."""
    import numpy as np
    from scipy.spatial import Voronoi

    pts = np.array([[lng, lat] for _, lng, lat in CARTIERE_CENTROIDS])
    xmin, ymin, xmax, ymax = _ZONE_BBOX
    # Mirror points across the bbox edges so every original region is bounded.
    mirrored = np.vstack([
        pts,
        np.column_stack([2 * xmin - pts[:, 0], pts[:, 1]]),
        np.column_stack([2 * xmax - pts[:, 0], pts[:, 1]]),
        np.column_stack([pts[:, 0], 2 * ymin - pts[:, 1]]),
        np.column_stack([pts[:, 0], 2 * ymax - pts[:, 1]]),
    ])
    vor = Voronoi(mirrored)
    features = []
    for idx, (name, lng, lat) in enumerate(CARTIERE_CENTROIDS):
        region = vor.regions[vor.point_region[idx]]
        if not region or -1 in region:
            continue
        poly = [tuple(vor.vertices[v]) for v in region]
        # order counter-clockwise around centroid
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        poly.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
        poly = _clip_polygon(poly, _ZONE_BBOX)
        if len(poly) < 3:
            continue
        ring = [[round(x, 6), round(y, 6)] for x, y in poly]
        ring.append(ring[0])
        features.append({
            "type": "Feature",
            "id": idx + 1,
            "properties": {"id": idx + 1, "name": name, "nameFaraDiacritice": strip_diacritics(name),
                           "centroid": [lng, lat], "source": "seed"},
            "geometry": {"type": "MultiPolygon", "coordinates": [[ring]]},
        })
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Street register (Nomenclator) fallback
# ---------------------------------------------------------------------------

_EXTRA_STREETS: list[tuple[str, str, str, str]] = [
    # (codGis, denumire, tipStrada, cartier) — streets outside the simulated graph
    ("0100", "Piața Libertății", "Piață", "Cetate"),
    ("0103", "Str. Alba Iulia", "Stradă", "Cetate"),
    ("0104", "Str. Eugeniu de Savoya", "Stradă", "Cetate"),
    ("0105", "Str. Lucian Blaga", "Stradă", "Cetate"),
    ("0510B", "Bd. Vasile Pârvan", "Bulevard", "Elisabetin"),
    ("0905", "Str. Iosif Vulcan", "Stradă", "Iosefin"),
    ("1110", "Calea Bogdăneștilor", "Calea", "Calea Torontalului"),
    ("1120", "Bd. Simion Bărnuțiu", "Bulevard", "Complexul Studențesc"),
    ("1130", "Str. Paul Morand", "Stradă", "Calea Martirilor"),
    ("1140", "Bd. Iuliu Maniu", "Bulevard", "Dâmbovița"),
]


def _street_type(name: str) -> str:
    low = name.lower()
    if low.startswith("bd."):
        return "Bulevard"
    if low.startswith("calea"):
        return "Calea"
    if low.startswith("piața"):
        return "Piață"
    if low.startswith("splaiul"):
        return "Splai"
    if low.startswith("podul"):
        return "Pod"
    return "Stradă"


def nomenclator_streets() -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for tag, a, b, name, cod, lanes, speed, opts in SEGMENTS:
        if cod in seen:
            continue
        cartier = NODES[a][3]
        seen[cod] = {
            "codGis": cod,
            "denumireCompleta": name,
            "denumireCompletaFaraDiacritice": strip_diacritics(name),
            "tipStrada": _street_type(name),
            "cartier": cartier,
            "linkId": f"LINK_{tag}_01",
        }
    for cod, name, tip, cartier in _EXTRA_STREETS:
        seen.setdefault(cod, {
            "codGis": cod, "denumireCompleta": name,
            "denumireCompletaFaraDiacritice": strip_diacritics(name),
            "tipStrada": tip, "cartier": cartier, "linkId": None,
        })
    return sorted(seen.values(), key=lambda s: s["denumireCompletaFaraDiacritice"])
