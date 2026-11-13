"""Real road network: offline OpenStreetMap snapshot of central Timișoara.

OWNER: Rareș (network). Built by ``scripts/import_osm_network.py``; committed as
``backend/data/network/timisoara_centre.json`` so the demo runs with no network access.
Loaded by ``app.engine.extended_graph.build_osm_graph()``.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "data" / "network" / "timisoara_centre.json"


@lru_cache(maxsize=2)
def load_snapshot(path: str | None = None) -> dict[str, Any]:
    """Parsed snapshot ``{meta, nodes, links}``. Raises FileNotFoundError if not built yet."""
    p = Path(path) if path else SNAPSHOT_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    for key in ("meta", "nodes", "links"):
        if key not in data:
            raise ValueError(f"{p}: missing '{key}'")
    return data


def snapshot_available(path: str | None = None) -> bool:
    return (Path(path) if path else SNAPSHOT_PATH).is_file()
