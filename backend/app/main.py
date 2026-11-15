"""TM-BraessGreen FastAPI application: the corridor simulator API (/api/corridor/*)."""
from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app import config
from app.corridor.api import router as corridor_router
from app.services import pmt_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("tmbg")


def _warm() -> None:
    """City Hall data the app shows (lines, tickets, Timpark), then every profile's base state and
    Braess search (cached on disk)."""
    t = time.perf_counter()
    for fn in (pmt_client.get_transit_network, pmt_client.get_wallet_types, pmt_client.get_parking):
        try:
            fn()
        except Exception as exc:  # never take the API down because of warm-up
            log.warning("warm-up %s failed: %s", fn.__name__, exc)
    try:
        from app.corridor.model import get_model

        m = get_model()
        for profile in ("morning", "day", "evening"):
            m.baseline(profile=profile)
        for profile in ("morning", "evening", "day"):   # busiest first
            m.scan(profile=profile)
        log.info("warm-up complete in %.1fs", time.perf_counter() - t)
    except Exception:
        log.exception("corridor warm-up failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.getenv("TMBG_OFFLINE", "0") not in ("1", "true", "yes"):
        threading.Thread(target=_warm, name="tmbg-warmup", daemon=True).start()
    yield


app = FastAPI(
    title="TM-BraessGreen API",
    version=config.APP_VERSION,
    description="Timișoara traffic simulator on the Calea Martirilor / Strada Cluj corridor: OpenStreetMap network, "
                "land-use demand, Wardrop equilibrium, Braess search, lane reallocation.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.include_router(corridor_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": config.APP_VERSION, "cache": pmt_client.cache_status()}


@app.get("/")
def root() -> dict:
    return {"name": config.APP_NAME, "docs": "/docs", "health": "/api/health", "api": "/api/corridor"}
