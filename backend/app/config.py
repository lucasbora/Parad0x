"""Runtime configuration: env vars, polite User-Agent and cache TTLs."""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "TM-BraessGreen"
APP_VERSION = "1.0.0"

# City Hall Data & Services Guide rule: every outgoing request carries this header.
USER_AGENT = "TM-BraessGreen-UniHack/1.0 (Timisoara Green Mobility Simulator)"

# External request timeout (seconds). Anything slower falls back to the last saved copy.
HTTP_TIMEOUT_S = float(os.getenv("TMBG_HTTP_TIMEOUT_S", "4.0"))

# OFFLINE=1 skips every live call (tests, airplane-mode demos).
OFFLINE = os.getenv("TMBG_OFFLINE", "0").lower() in ("1", "true", "yes")

CACHE_DIR = Path(os.getenv("TMBG_CACHE_DIR", Path(__file__).resolve().parent / "cache"))
CACHE_TTL_S = {
    "transit_network": 24 * 3600,
    "timetable": 3600,
    "parking": 24 * 3600,
    "wallet": 24 * 3600,
}

PMT_CONT_BASE = os.getenv("TMBG_CONT_BASE", "https://cont.primariatm.ro")
OVERPASS_URL = os.getenv("TMBG_OVERPASS_URL", "https://overpass-api.de/api/interpreter")

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "TMBG_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://localhost:8080",
    ).split(",")
    if o.strip()
]

