"""Enrich the seed model with live PMT / SMTT data whenever it is reachable.

Everything here degrades to the seed values: if a dataset came from the seed,
the helpers simply return seed-equivalent structures.
"""
from __future__ import annotations

import math
import re
import threading
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app import config
from app.engine.extended_graph import ExtendedGraph
from app.services import pmt_client
from app.services import seed_timisoara as seed

_ABBREV = [(r"^bd\.?\s+", "bulevardul "), (r"^str\.?\s+", "strada "), (r"^p-?ta\.?\s+", "piata ")]
_lock = threading.Lock()
_cod_cache: dict[int, dict[str, dict]] = {}


def normalize_street(name: str) -> str:
    n = seed.strip_diacritics(name).lower().strip()
    n = re.sub(r"\s*\(.*?\)\s*", " ", n).strip()
    n = n.split(" / ")[0].strip()
    for pat, rep in _ABBREV:
        n = re.sub(pat, rep, n)
    return re.sub(r"\s+", " ", n)


def official_streets(graph: ExtendedGraph) -> dict[str, dict]:
    """link id → official register entry (codGis, denumireCompleta, cartier) matched by diacritic-free name."""
    streets, prov = pmt_client.get_nomenclator()
    key = id(streets)
    with _lock:
        if key in _cod_cache:
            return _cod_cache[key]
    if prov.source == "seed":
        out: dict[str, dict] = {}
    else:
        by_norm: dict[str, dict] = {}
        for s in streets:
            by_norm.setdefault(normalize_street(s.get("denumireCompletaFaraDiacritice") or s["denumireCompleta"]), s)
        out = {}
        for rl in graph.road_links:
            n = normalize_street(rl.street_name)
            hit = by_norm.get(n)
            if hit is None:
                cands = [v for k, v in by_norm.items() if k.startswith(n + " ") or n.startswith(k + " ")]
                hit = min(cands, key=lambda v: len(v["denumireCompleta"])) if cands else None
            if hit:
                out[rl.id] = {"codGis": str(hit["codGis"]), "denumireCompleta": hit["denumireCompleta"],
                              "cartier": hit.get("cartier")}
    with _lock:
        _cod_cache.clear()
        _cod_cache[key] = out
    return out


# ---------------------------------------------------------------------------
# Transit
# ---------------------------------------------------------------------------

def live_lines() -> dict[str, dict]:
    """shortName → live route info (id, color, polyline per direction, stops)."""
    net, prov = pmt_client.get_transit_network()
    if prov.source == "seed" or not net.get("routes"):
        return {}
    wanted = {l["shortName"] for l in seed.STPT_LINES}
    stops_by_route: dict[str, list[dict]] = {}
    for st in net.get("stops", []):
        for rid in st.get("routeIds", []) or []:
            stops_by_route.setdefault(rid, []).append(st)
    paths: dict[str, dict[int, list[list[float]]]] = {}
    for pth in net.get("paths", []):
        try:
            paths.setdefault(pth["routeId"], {})[int(pth.get("directionId", 0))] = pmt_client.decode_polyline(pth["polyline"])
        except Exception:
            continue
    out = {}
    for r in net["routes"]:
        if r.get("shortName") not in wanted:
            continue
        rid = r["id"]
        color = str(r.get("color") or "")
        out[r["shortName"]] = {
            "routeId": rid,
            "type": int(r.get("type", 3)),
            "color": ("#" + color) if color and not color.startswith("#") else (color or None),
            "longName": r.get("longName"),
            "polylines": paths.get(rid, {}),
            "stops": stops_by_route.get(rid, []),
        }
    return out


def _now() -> datetime:
    try:
        return datetime.now(ZoneInfo(config.TIMEZONE))
    except Exception:
        from datetime import timezone
        return datetime.now(timezone(timedelta(hours=2)))


def nearest_stop(stops: list[dict], point: list[float]) -> dict | None:
    best = None
    for st in stops:
        try:
            d = seed.haversine_m((float(st["lon"]), float(st["lat"])), tuple(point))
        except (KeyError, TypeError, ValueError):
            continue
        if best is None or d < best[0]:
            best = (d, st)
    return best[1] if best else None


def live_next_departures(route_id: str, stop: dict, n: int = 3) -> list[str] | None:
    tt, prov = pmt_client.get_stop_timetable(stop["id"])
    if prov.source == "seed":
        return None
    now = _now().strftime("%H:%M")
    times: list[str] = []
    for line in tt.get("lines", []):
        if line.get("routeId") == route_id:
            times.extend(t for t in line.get("times", []) if isinstance(t, str))
    upcoming = sorted(t for t in times if t >= now)
    if not upcoming and times:
        upcoming = sorted(times)  # service over → tomorrow's first departures
    return upcoming[:n] or None


def stops_along(stops: list[dict], polyline: list[list[float]], max_m: float = 120.0) -> list[dict]:
    from app.engine.route_recommender import dist_to_polyline_m

    out = []
    for st in stops:
        try:
            pt = [float(st["lon"]), float(st["lat"])]
        except (KeyError, TypeError, ValueError):
            continue
        if dist_to_polyline_m(pt, polyline) <= max_m:
            out.append(st)
    if len(polyline) >= 2:  # order along the line
        out.sort(key=lambda st: _progress([float(st["lon"]), float(st["lat"])], polyline))
    return out


def _progress(p: list[float], line: list[list[float]]) -> float:
    best, acc, best_acc = 1e18, 0.0, 0.0
    for a, b in zip(line[:-1], line[1:]):
        d = math.hypot(p[0] - a[0], p[1] - a[1])
        if d < best:
            best, best_acc = d, acc
        acc += math.hypot(b[0] - a[0], b[1] - a[1])
    return best_acc


# ---------------------------------------------------------------------------
# Fares, POIs, events, Timpark
# ---------------------------------------------------------------------------

def fares() -> tuple[float, float]:
    items, prov = pmt_client.get_wallet_types()
    ticket, day = 5.0, 18.0
    for it in items:
        price = it.get("priceLei", it.get("priceRon"))
        if price is None:
            continue
        name = seed.strip_diacritics(str(it.get("name", "")) + " " + str(it.get("nameEn", ""))).lower()
        if "60" in name and ("min" in name or "bilet" in name):
            ticket = float(price)
        elif "zi" in name.split() or "day" in name or "24" in name:
            day = float(price)
    return ticket, day


def normalized_pois() -> list[dict]:
    items, _ = pmt_client.get_pois()
    out = []
    for p in items:
        lng = p.get("longitude", p.get("lng", p.get("lon")))
        lat = p.get("latitude", p.get("lat"))
        coords = p.get("coordinates") or ([lng, lat] if lng is not None and lat is not None else None)
        if not coords:
            continue
        out.append({"id": p.get("id"), "name": p.get("name"), "nameEn": p.get("nameEn"),
                    "category": p.get("category"), "address": p.get("address"), "coordinates": coords})
    return out


def normalized_events() -> list[dict]:
    items, prov = pmt_client.get_events()
    out = []
    for e in items:
        lng = e.get("venueLng", e.get("lng"))
        lat = e.get("venueLat", e.get("lat"))
        coords = e.get("coordinates") or ([lng, lat] if lng is not None and lat is not None else None)
        if not coords:
            continue
        start = e.get("start") or e.get("dateStart")
        if isinstance(start, (int, float)):
            start = datetime.fromtimestamp(start, tz=_now().tzinfo).isoformat()
        out.append({"id": e.get("id"), "title": e.get("title"), "venue": e.get("venue"),
                    "start": start, "category": e.get("category"), "coordinates": coords,
                    "source": prov.source})
    if not out:  # live feed without geocoded venues → seeded venue attractors used by event_rush
        out = [{**e, "source": "seed"} for e in seed.EVENTS]
    return out


def timpark_features(graph: ExtendedGraph) -> list[dict]:
    data, prov = pmt_client.get_parking()
    tariffs = pmt_client.timpark_tariffs()
    feats = []
    if prov.source != "seed" and data.get("features"):
        for f in data["features"]:
            coords = f.get("coordinates")
            if not coords or not isinstance(coords, list) or len(coords) < 2:
                continue
            zone = f.get("tariff")
            closed = coords[0] == coords[-1] and len(coords) >= 4
            geom = {"type": "Polygon", "coordinates": [coords]} if closed else {"type": "LineString", "coordinates": coords}
            feats.append({"type": "Feature", "geometry": geom, "properties": {
                "id": f.get("id"), "name": f.get("name"), "zone": zone, "kind": f.get("kind"),
                "eurPerHour": tariffs.get(zone), "source": "live"}})
        return feats
    for rl in graph.road_links:
        if rl.timpark_zone and rl.id.endswith("_01"):
            feats.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": rl.coords},
                          "properties": {"id": rl.id, "name": rl.street_name, "zone": rl.timpark_zone,
                                         "kind": "segment", "eurPerHour": tariffs[rl.timpark_zone],
                                         "spaces": int(rl.length_m // seed.CURB_SPACE_LENGTH_M), "source": "seed"}})
    return feats
