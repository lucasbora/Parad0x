"""Polite, cached client for the Primăria Municipiului Timișoara APIs the app uses.

Data & Services Guide compliance:
  * every request sends ``User-Agent: TM-BraessGreen-UniHack/1.0 (...)``;
  * payloads are cached in ``app/cache/*.json`` with per-dataset TTLs, so live endpoints are hit
    at most once per TTL, never in loops;
  * when a live call fails (timeout > 4 s, non-200, schema change, no internet), the last saved
    copy is used even if it is older than its TTL; with no saved copy the dataset is reported as
    "unavailable" and returned empty. Nothing is ever invented.
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

log = logging.getLogger("tmbg.pmt")


@dataclass
class Provenance:
    dataset: str
    source: str            # "live" | "cache" | "cache (stale)" | "unavailable"
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


def _read_cache(name: str, ttl: float | None) -> tuple[Any, float] | None:
    """Saved payload and its timestamp; ``ttl=None`` accepts a copy of any age."""
    path = _cache_path(name)
    if not path.exists():
        return None
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
        ts = float(blob["fetchedAt"])
        if ttl is not None and time.time() - ts > ttl:
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


def _remember(name: str, payload: Any, prov: Provenance) -> tuple[Any, Provenance]:
    with _lock:
        _mem[name] = (payload, prov)
        _status[name] = prov
    return payload, prov


def _fetch(name: str, url: str, ttl_key: str, validate: Callable[[Any], Any], empty: Callable[[], Any],
           params: dict[str, Any] | None = None) -> tuple[Any, Provenance]:
    """fresh cache → live → stale cache → unavailable (empty payload). ``validate`` normalises or raises."""
    ttl = config.CACHE_TTL_S.get(ttl_key, 3600)
    with _lock:
        if name in _mem:
            payload, prov = _mem[name]
            if prov.fetched_at and time.time() - prov.fetched_at < ttl:
                return payload, prov
    hit = _read_cache(name, ttl)
    if hit is not None:
        return _remember(name, hit[0], Provenance(name, "cache", url, hit[1]))
    note = "offline mode"
    if not config.OFFLINE:
        try:
            payload = validate(http_get_json(url, params))
            _write_cache(name, payload)
            return _remember(name, payload, Provenance(name, "live", url, time.time()))
        except Exception as exc:  # timeout, DNS, non-200, schema drift …
            note = f"live fetch failed: {type(exc).__name__}"
            log.info("live fetch %s failed (%s)", url, type(exc).__name__)
    stale = _read_cache(name, None)
    if stale is not None:
        return _remember(name, stale[0], Provenance(name, "cache (stale)", url, stale[1], note))
    return _remember(name, empty(), Provenance(name, "unavailable", url, None, note))


def available(prov: Provenance) -> bool:
    return prov.source != "unavailable"


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


def _validate_list(*keys: str):
    def v(raw: Any) -> list:
        lst = _as_list(raw, *keys)
        if not lst:
            raise ValueError("empty list")
        return lst
    return v


def _validate_transit_network(raw: Any) -> dict:
    if isinstance(raw, dict) and isinstance(raw.get("routes"), list) and raw["routes"]:
        return {
            "feedVersion": raw.get("feedVersion"),
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
# The four datasets the app uses
# ---------------------------------------------------------------------------

def get_transit_network() -> tuple[dict, Provenance]:
    return _fetch("transit_network", f"{config.PMT_CONT_BASE}/api/mobile/transit/network", "transit_network",
                  _validate_transit_network, lambda: {"feedVersion": None, "routes": [], "stops": [], "paths": []})


def get_stop_timetable(stop_id: str) -> tuple[dict, Provenance]:
    safe = "".join(c for c in str(stop_id) if c.isalnum() or c in "-_")
    return _fetch(f"timetable_{safe}", f"{config.PMT_CONT_BASE}/api/mobile/transit/stops/{safe}/timetable",
                  "timetable", _validate_timetable, lambda: {"date": None, "lines": []})


def get_wallet_types() -> tuple[list[dict], Provenance]:
    return _fetch("wallet_transport", f"{config.PMT_CONT_BASE}/api/mobile/wallet/types", "wallet",
                  _validate_list("data", "types", "items"), list, params={"category": "transport"})


def get_parking() -> tuple[dict, Provenance]:
    return _fetch("parking", f"{config.PMT_CONT_BASE}/api/mobile/parking", "parking", _validate_parking,
                  lambda: {"features": [], "tariffs": {}})


def cache_status() -> dict[str, dict]:
    with _lock:
        return {k: v.as_dict() for k, v in _status.items()}
