"""FastAPI backend. See docs/VARUN_IMPLEMENTATION.md §6 T30 / §30.2.

Run with `make api` (-> uvicorn dashboard.api.main:app --reload --port 8000).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import cctv, config, domain, ingest, observations, predict, runs, scenarios, stations, validation
from .settings import get_settings

app = FastAPI(title="Bangkok Flood POC API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_settings = get_settings()
if _settings.frames_dir.exists():
    app.mount("/frames", StaticFiles(directory=str(_settings.frames_dir)), name="frames")
if _settings.cctv_thumbs_dir.exists():
    # blurred thumbnails only — never mount data/cctv/raw (rule 6: raw frames stay private)
    app.mount("/thumbs", StaticFiles(directory=str(_settings.cctv_thumbs_dir)), name="thumbs")

for router in (config.router, domain.router, scenarios.router, runs.router, stations.router,
               cctv.router, observations.router, validation.router, predict.router, ingest.router):
    app.include_router(router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "versions": {"api": "0.1.0", "model_version": None, "surrogate_version": None},
        "mode": _settings.surrogate_mode,
    }
