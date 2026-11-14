"""Fetch everything the corridor model needs from OpenStreetMap and save it as one snapshot.

Usage (from backend/):  python scripts/fetch_osm_corridor.py

Contents:
  * roads (main roads AND side streets) in the fetch box, with lanes / maxspeed / oneway
  * traffic signals and turn-restriction relations (restrictions stored for a later phase)
  * buildings (with type and building:levels) inside the corridor box   → where people live / go
  * shops, offices, amenities, leisure (nodes and areas) inside the box  → trip destinations

The snapshot is committed so the app and the demo never depend on Overpass being up.
Data © OpenStreetMap contributors, ODbL 1.0.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import USER_AGENT  # noqa: E402
from app.corridor.config import CORRIDOR, OSM_SNAPSHOT  # noqa: E402

SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def run(query: str) -> list[dict]:
    last = None
    for url in SERVERS:
        try:
            resp = httpx.post(url, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=240)
            if resp.status_code != 200:
                print(f"  {url}: HTTP {resp.status_code}")
                last = resp.status_code
                continue
            body = resp.json()
            if "remark" in body and any(w in body["remark"] for w in ("error", "timed out", "out of memory")):
                print(f"  {url}: remark {body['remark'][:80]}")
                continue
            print(f"  {url}: ok ({len(body['elements'])} elements)")
            return body["elements"]
        except Exception as exc:  # try the next public server
            print(f"  {url}: {type(exc).__name__}")
            last = exc
    raise SystemExit(f"all Overpass servers failed: {last}")


def main() -> None:
    fs, fw, fn, fe = CORRIDOR.fetch_bbox
    s, w, n, e = CORRIDOR.bbox
    roads = "|".join(CORRIDOR.highways)
    fb = f"{fs},{fw},{fn},{fe}"
    bb = f"{s},{w},{n},{e}"
    q_network = f"""[out:json][timeout:180];
way["highway"~"^({roads})$"]({fb});
out body geom;
node["highway"="traffic_signals"]({fb});
out body;
relation["type"="restriction"]({fb});
out body;"""
    q_landuse = f"""[out:json][timeout:180];
way["building"]({bb});
out tags geom;
(
  node["shop"]({bb}); node["office"]({bb}); node["amenity"]({bb}); node["leisure"]({bb}); node["tourism"]({bb});
);
out body;
(
  way["shop"]({bb}); way["office"]({bb}); way["amenity"]({bb}); way["leisure"]({bb});
);
out tags center;"""
    print("network…")
    elements = run(q_network)
    print("land use…")
    elements += run(q_landuse)
    query = q_network + "\n\n" + q_landuse
    OSM_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    OSM_SNAPSHOT.write_text(json.dumps({
        "source": "© OpenStreetMap contributors (ODbL 1.0) via Overpass API",
        "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bbox": [s, w, n, e],
        "fetchBbox": [fs, fw, fn, fe],
        "query": query,
        "elements": elements,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    kinds = {}
    for el in elements:
        t = el.get("tags", {})
        k = ("road" if "highway" in t and el["type"] == "way" else
             "signal" if t.get("highway") == "traffic_signals" else
             "restriction" if el["type"] == "relation" else
             "building" if "building" in t and "geometry" in el else "poi")
        kinds[k] = kinds.get(k, 0) + 1
    print(f"saved {OSM_SNAPSHOT} ({OSM_SNAPSHOT.stat().st_size // 1024} KB): {kinds}")


if __name__ == "__main__":
    main()
