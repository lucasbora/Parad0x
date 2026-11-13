"""Polite, cached, offline-first client for Primăria Municipiului Timișoara APIs.

Data & Services Guide compliance:
  * every request sends ``User-Agent: TM-BraessGreen-UniHack/1.0 (...)``;
  * payloads are cached in ``app/cache/*.json`` with per-dataset TTLs — live
    endpoints are hit at most once per TTL, never in loops;
  * any failure, timeout (> 4 s) or non-200 falls back to ``seed_timisoara``;
  * Sesizări are sanitised server-side: only aggregated counts by category and
    status ever leave this module (no descriptions, names or photo URLs), and raw
    reports are never written to disk.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from app import config
from app.services import seed_timisoara as seed

log = logging.getLogger("tmbg.pmt")

SESIZARI_CATEGORIES = ("Trafic rutier și semne de circulație", "Străzi și trotuare", "Transport public")
SESIZARI_STATUSES = ("Inregistrata", "In lucru", "Finalizata")


@dataclass
class Provenance:
    dataset: str
    source: str            # "live" | "cache" | "seed"
    endpoint: str
    fetched_at: float | None = None
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "source": self.source,
            "endpoint": self.endpoint,
            "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.fetched_at)) if self.fetched_at else None,
            "note": self.note,
        }


_status: dict[str, Provenance] = {}
_mem: dict[str, Any] = {}
_lock = threading.Lock()


CACHE_SCHEMA_VERSION = 2  # bump when a validator's output shape changes


def _cache_path(name: str):
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return config.CACHE_DIR / f"{name}.v{CACHE_SCHEMA_VERSION}.json"


def _read_cache(name: str, ttl: float) -> tuple[Any, float] | None:
    path = _cache_path(name)
    if not path.exists():
        return None
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
        ts = float(blob["fetchedAt"])
        if time.time() - ts > ttl:
            return None
        return blob["payload"], ts
    except Exception:  # corrupt cache → ignore
        return None


def _write_cache(name: str, payload: Any) -> None:
    try:
        _cache_path(name).write_text(json.dumps({"fetchedAt": time.time(), "payload": payload}, ensure_ascii=False),
                                     encoding="utf-8")
    except OSError as exc:  # read-only FS in some containers
        log.warning("cache write failed for %s: %s", name, exc)


def http_get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    """Single polite GET. Raises on timeout / non-200 / invalid JSON."""
    headers = {"User-Agent": config.USER_AGENT, "Accept": "application/json"}
    with httpx.Client(timeout=config.HTTP_TIMEOUT_S, headers=headers, follow_redirects=True) as client:
        resp = client.get(url, params=params)
        if resp.status_code != 200:
            raise httpx.HTTPStatusError(f"HTTP {resp.status_code}", request=resp.request, response=resp)
        return resp.json()


def _fetch(name: str, url: str, ttl_key: str, validate: Callable[[Any], Any], fallback: Callable[[], Any],
           params: dict[str, Any] | None = None, cache: bool = True) -> tuple[Any, Provenance]:
    """cache → live → seed. ``validate`` normalises the live payload or raises."""
    ttl = config.CACHE_TTL_S.get(ttl_key, 3600)
    with _lock:
        if name in _mem:
            payload, prov = _mem[name]
            if prov.source == "seed" or (prov.fetched_at and time.time() - prov.fetched_at < ttl):
                return payload, prov
    if cache:
        hit = _read_cache(name, ttl)
        if hit is not None:
            payload, ts = hit
            prov = Provenance(name, "cache", url, ts)
            with _lock:
                _mem[name] = (payload, prov)
                _status[name] = prov
            return payload, prov
    if not config.OFFLINE:
        try:
            raw = http_get_json(url, params)
            payload = validate(raw)
            if cache:
                _write_cache(name, payload)
            prov = Provenance(name, "live", url, time.time())
            with _lock:
                _mem[name] = (payload, prov)
                _status[name] = prov
            return payload, prov
        except Exception as exc:  # timeout, DNS, non-200, schema drift …
            log.info("live fetch %s failed (%s) → seed fallback", url, type(exc).__name__)
            note = f"fallback: {type(exc).__name__}"
    else:
        note = "offline mode"
    payload = fallback()
    prov = Provenance(name, "seed", url, None, note)
    with _lock:
        _mem[name] = (payload, prov)
        _status[name] = prov
    return payload, prov


# ---------------------------------------------------------------------------
# Validators (defensive: live schemas may drift)
# ---------------------------------------------------------------------------

def _as_list(raw: Any, *keys: str) -> list:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for k in keys:
            if isinstance(raw.get(k), list):
                return raw[k]
    raise ValueError("unexpected payload shape")


def _validate_nomenclator(raw: Any) -> list[dict]:
    out = []
    for s in _as_list(raw, "data", "items", "strazi"):
        name = s.get("denumireCompleta") or s.get("denumire")
        if not name:
            continue
        out.append({
            "codGis": str(s.get("codGis", "")),
            "denumireCompleta": name,
            "denumireCompletaFaraDiacritice": s.get("denumireCompletaFaraDiacritice") or seed.strip_diacritics(name),
            "tipStrada": s.get("tipStrada"),
            "cartier": s.get("cartier"),
        })
    if not out:
        raise ValueError("empty nomenclator")
    return out


def _validate_zones(raw: Any) -> dict:
    if isinstance(raw, dict) and raw.get("type") == "FeatureCollection" and raw.get("features"):
        return raw
    raise ValueError("zones not a FeatureCollection")


def _validate_any_list(*keys: str):
    def v(raw: Any) -> list:
        lst = _as_list(raw, *keys)
        if not lst:
            raise ValueError("empty list")
        return lst
    return v


def _validate_transit_network(raw: Any) -> dict:
    if isinstance(raw, dict) and isinstance(raw.get("routes"), list) and raw["routes"]:
        return {
            "feedVersion": raw.get("feedVersion", config.GTFS_FEED_VERSION),
            "routes": raw["routes"],
            "stops": raw.get("stops", []) if isinstance(raw.get("stops"), list) else [],
            "paths": raw.get("paths", []) if isinstance(raw.get("paths"), list) else [],
        }
    raise ValueError("bad transit network")


def _validate_parking(raw: Any) -> dict:
    if isinstance(raw, dict) and isinstance(raw.get("features"), list) and raw["features"]:
        return {"features": raw["features"], "tariffs": raw.get("tariffs", {})}
    raise ValueError("bad parking payload")


def _validate_timetable(raw: Any) -> dict:
    if isinstance(raw, dict) and isinstance(raw.get("lines"), list):
        return {"date": raw.get("date"), "lines": raw["lines"]}
    raise ValueError("bad timetable")


def decode_polyline(encoded: str, precision: int = 5) -> list[list[float]]:
    """Google encoded polyline → [[lng, lat], ...]."""
    coords, index, lat, lng = [], 0, 0, 0
    factor = 10 ** precision
    while index < len(encoded):
        for which in (0, 1):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if which == 0:
                lat += delta
            else:
                lng += delta
        coords.append([round(lng / factor, 6), round(lat / factor, 6)])
    return coords


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_nomenclator() -> tuple[list[dict], Provenance]:
    return _fetch("nomenclator", f"{config.PMT_SESIZARI_BASE}/api/nomenclator/strazi", "nomenclator",
                  _validate_nomenclator, seed.nomenclator_streets)


def get_zones() -> tuple[dict, Provenance]:
    return _fetch("zones", f"{config.PMT_SESIZARI_BASE}/api/zones", "zones", _validate_zones, seed.cartiere_geojson)


def get_transit_network() -> tuple[dict, Provenance]:
    return _fetch("transit_network", f"{config.PMT_CONT_BASE}/api/mobile/transit/network", "transit_network",
                  _validate_transit_network, seed.transit_network_payload)


def get_wallet_types() -> tuple[list[dict], Provenance]:
    return _fetch("wallet_transport", f"{config.PMT_CONT_BASE}/api/mobile/wallet/types", "wallet",
                  _validate_any_list("data", "types", "items"), lambda: seed.STPT_FARES,
                  params={"category": "transport"})


def get_parking() -> tuple[dict, Provenance]:
    return _fetch("parking", f"{config.PMT_CONT_BASE}/api/mobile/parking", "parking", _validate_parking,
                  lambda: {"features": [], "tariffs": {"smsNumber": seed.TIMPARK_SMS, "hourly": {
                      k: {"eur": v} for k, v in seed.TIMPARK_TARIFFS_EUR_H.items()}}})


def get_stop_timetable(stop_id: str) -> tuple[dict, Provenance]:
    safe = "".join(c for c in str(stop_id) if c.isalnum() or c in "-_")
    return _fetch(f"timetable_{safe}", f"{config.PMT_CONT_BASE}/api/mobile/transit/stops/{safe}/timetable",
                  "events", _validate_timetable, lambda: {"date": None, "lines": []})


def timpark_tariffs() -> dict[str, float]:
    """€/h by zone colour — live Timpark tariffs when available, seed otherwise."""
    data, _ = get_parking()
    hourly = (data.get("tariffs") or {}).get("hourly") or {}
    out = dict(seed.TIMPARK_TARIFFS_EUR_H)
    for zone, val in hourly.items():
        try:
            out[zone] = float(val["eur"] if isinstance(val, dict) else val)
        except (KeyError, TypeError, ValueError):
            pass
    return out


def get_pois() -> tuple[list[dict], Provenance]:
    return _fetch("pois", f"{config.PMT_CONT_BASE}/api/mobile/pois", "pois",
                  _validate_any_list("data", "pois", "items"), lambda: seed.POIS)


def get_events() -> tuple[list[dict], Provenance]:
    return _fetch("events", f"{config.PMT_CONT_BASE}/api/mobile/events", "events",
                  _validate_any_list("data", "events", "items"), lambda: seed.EVENTS)


def sanitize_sesizari(reports: list[dict], radius_m: int = 500) -> dict[str, Any]:
    """GDPR: reduce raw reports to aggregated counts. Nothing personal survives."""
    by_cat = {c: 0 for c in SESIZARI_CATEGORIES}
    by_status = {s: 0 for s in SESIZARI_STATUSES}
    total = 0
    for r in reports:
        if not isinstance(r, dict):
            continue
        cat = r.get("categorie") or r.get("category") or (r.get("categorie_obj") or {}).get("denumire")
        status = r.get("status") or r.get("stare")
        if isinstance(cat, dict):
            cat = cat.get("denumire") or cat.get("name")
        if isinstance(status, dict):
            status = status.get("denumire") or status.get("name")
        total += 1
        if cat in by_cat:
            by_cat[cat] += 1
        if status in by_status:
            by_status[status] += 1
    return {"radiusMeters": radius_m, "total": total, "byCategory": by_cat, "byStatus": by_status}


def get_sesizari_summary(lat: float, lng: float, radius_m: int = 500, start_date: str = "2026-10-14") -> tuple[dict, Provenance]:
    """Aggregated (never raw) resident reports within ``radius_m`` of a point."""
    key = f"sesizari_{round(lat, 4)}_{round(lng, 4)}_{radius_m}"
    url = f"{config.PMT_SESIZARI_BASE}/api/sesizari"

    def validate(raw: Any) -> dict:
        reports = _as_list(raw, "data", "items", "sesizari")
        return sanitize_sesizari(reports, radius_m)  # aggregate BEFORE anything is cached

    return _fetch(key, url, "sesizari", validate, lambda: seed.sesizari_for_point(lng, lat, radius_m),
                  params={"startDate": start_date, "lat": lat, "lng": lng, "radiusMeters": radius_m})


def warm_cache() -> None:
    """Fetch each dataset once (background thread on startup)."""
    for fn in (get_nomenclator, get_zones, get_transit_network, get_wallet_types, get_parking, get_pois, get_events):
        try:
            fn()
        except Exception as exc:  # never crash the app on warm-up
            log.warning("warm-up %s failed: %s", fn.__name__, exc)


def cache_status() -> dict[str, dict]:
    with _lock:
        return {k: v.as_dict() for k, v in _status.items() if not k.startswith("sesizari_")}


def ngsi_point_to_lnglat(lat_lng: list[float]) -> list[float]:
    """NGSI-LD (data.primariatm.ro FIWARE) uses [lat, lng]; MapLibre wants [lng, lat]."""
    lat, lng = lat_lng[0], lat_lng[1]
    return [lng, lat]
