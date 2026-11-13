"""Fetch the OSM main-road network around the corridor and save it as a snapshot.

Usage (from backend/):  python scripts/fetch_osm_corridor.py

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

HIGHWAYS = "primary|secondary|tertiary|primary_link|secondary_link|tertiary_link|unclassified"


def main() -> None:
    s, w, n, e = CORRIDOR.fetch_bbox
    query = f"""[out:json][timeout:120];
(
  way["highway"~"^({HIGHWAYS})$"]({s},{w},{n},{e});
);
out body geom;
node["highway"="traffic_signals"]({s},{w},{n},{e});
out body;"""
    resp = httpx.post("https://overpass-api.de/api/interpreter", data={"data": query},
                      headers={"User-Agent": USER_AGENT}, timeout=180)
    resp.raise_for_status()
    elements = resp.json()["elements"]
    OSM_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    OSM_SNAPSHOT.write_text(json.dumps({
        "source": "© OpenStreetMap contributors (ODbL 1.0) via overpass-api.de",
        "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bbox": [s, w, n, e],
        "query": query,
        "elements": elements,
    }, ensure_ascii=False), encoding="utf-8")
    ways = sum(1 for el in elements if el["type"] == "way")
    print(f"saved {OSM_SNAPSHOT} — {ways} ways, {len(elements) - ways} signal nodes")


if __name__ == "__main__":
    main()
