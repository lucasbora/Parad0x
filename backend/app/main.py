"""TM-BraessGreen FastAPI application."""
from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app import config
from app.engine.braess_detector import get_engine
from app.corridor.api import router as corridor_router
from app.models import schemas
from app.services import live_data, osm_overpass, pmt_client
from app.services import seed_timisoara as seed
from app.services.simulator import get_simulator, search_streets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("tmbg")


def _warm() -> None:
    t = time.perf_counter()
    try:
        pmt_client.warm_cache()
        osm_overpass.get_cycling_layers()
        # pre-fetch timetables at the stops nearest each hotspot (one request per stop, cached 1 h)
        lines = live_data.live_lines()
        for h in seed.HOTSPOTS:
            for short in h["stptLines"]:
                info = lines.get(short)
                if info and info.get("stops"):
                    st = live_data.nearest_stop(info["stops"], h["center"])
                    if st:
                        pmt_client.get_stop_timetable(st["id"])
        for h in seed.HOTSPOTS:
            pmt_client.get_sesizari_summary(h["center"][1], h["center"][0], 500)
        sim = get_simulator()
        sim.network("morning_rush")
        log.info("warm-up complete in %.1fs", time.perf_counter() - t)
    except Exception:  # never take the API down because of warm-up
        log.exception("warm-up failed")


def _warm_corridor() -> None:
    """Corridor: base state for every profile, then every profile's Braess search (cached on disk)."""
    t = time.perf_counter()
    try:
        from app.corridor.model import get_model

        m = get_model()
        for profile in ("morning", "day", "evening", "sunday"):
            m.baseline(profile=profile)
        for profile in ("morning", "evening", "day", "sunday"):   # busiest first
            m.scan(profile=profile)
        log.info("corridor warm-up complete in %.1fs", time.perf_counter() - t)
    except Exception:  # never take the API down because of warm-up
        log.exception("corridor warm-up failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_engine()  # build graph + path system synchronously (fast)
    threading.Thread(target=_warm, name="tmbg-warmup", daemon=True).start()
    if os.getenv("TMBG_OFFLINE", "0") not in ("1", "true", "yes"):
        threading.Thread(target=_warm_corridor, name="tmbg-corridor-warmup", daemon=True).start()
    yield


app = FastAPI(
    title="TM-BraessGreen API",
    version=config.APP_VERSION,
    description="Timișoara Green Mobility & Braess Paradox Urban Simulator — Burov et al. extended graph, "
                "Wardrop equilibrium via Beckmann potentials, interactive lane reallocation.",
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

PresetQ = Literal["morning_rush", "evening_rush", "now", "weekend", "event_rush"]


@app.get("/api/health", response_model=schemas.HealthResponse)
def health() -> schemas.HealthResponse:
    eng = get_engine()
    g = eng.graph
    transit, _ = pmt_client.get_transit_network()
    return schemas.HealthResponse(
        status="ok",
        version=config.APP_VERSION,
        feed_version=str(transit.get("feedVersion", config.GTFS_FEED_VERSION)),
        offline_mode=config.OFFLINE,
        cache=pmt_client.cache_status(),
        solver={
            "method": "Conjugate Frank-Wolfe + exact Newton line search (+ path-based Newton polish)",
            "relativeGapTarget": config.SOLVER_REL_GAP,
            "nodes": len(g.nodes), "roadLinks": g.n_road, "queueLinks": len(g.queue_links),
            "odPairs": len(g.od_pairs), "paths": len(g.paths),
        },
    )


@app.get("/api/network")
def network(preset: PresetQ = Query("morning_rush")) -> dict:
    return get_simulator().network(preset)


@app.get("/api/hotspots")
def hotspots(preset: PresetQ = Query("morning_rush")) -> list[dict]:
    return get_simulator().hotspots(preset)


@app.post("/api/simulate", response_model=schemas.SimulateResponse)
def simulate(req: schemas.SimulateRequest) -> schemas.SimulateResponse:
    sim = get_simulator()
    for iv in req.interventions:
        if iv.link_id not in sim.g.road_index:
            raise HTTPException(status_code=404, detail=f"unknown linkId {iv.link_id}")
        rl = sim.g.link(iv.link_id)
        official = live_data.official_streets(sim.g).get(iv.link_id, {}).get("codGis")
        if iv.cod_gis and iv.cod_gis not in {rl.cod_gis, official}:
            raise HTTPException(status_code=422,
                                detail=f"codGis {iv.cod_gis} does not match {iv.link_id} ({official or rl.cod_gis})")
    return sim.simulate(req)


@app.post("/api/decidem-brief", response_model=schemas.DecidemBriefResponse)
def decidem_brief(req: schemas.DecidemBriefRequest) -> schemas.DecidemBriefResponse:
    sim = get_simulator()
    if not req.interventions:
        raise HTTPException(status_code=422, detail="at least one intervention is required")
    for iv in req.interventions:
        if iv.link_id not in sim.g.road_index:
            raise HTTPException(status_code=404, detail=f"unknown linkId {iv.link_id}")
    return sim.decidem_brief(req)


@app.get("/api/streets/search")
def streets_search(q: str = Query("", max_length=80), limit: int = Query(12, ge=1, le=50)) -> dict:
    _, prov = pmt_client.get_nomenclator()
    return {"results": search_streets(q, limit), "provenance": prov.as_dict()}


@app.get("/api/nomenclator/strazi")
def nomenclator() -> dict:
    streets, prov = pmt_client.get_nomenclator()
    return {"streets": streets, "provenance": prov.as_dict()}


@app.get("/api/sesizari/summary")
def sesizari_summary(lat: float = Query(..., ge=45.6, le=45.9), lng: float = Query(..., ge=21.0, le=21.4),
                     radius: int = Query(500, ge=50, le=2000)) -> dict:
    summary, prov = pmt_client.get_sesizari_summary(lat, lng, radius)
    return {"summary": summary, "provenance": prov.as_dict()}


@app.get("/")
def root() -> dict:
    return {"name": config.APP_NAME, "docs": "/docs", "health": "/api/health"}
