"""POST /api/predict, GET /api/predict/{run_id} -- what-if runs (component #16).

See docs/VARUN_IMPLEMENTATION.md §6 T71. Renders the first 8 frames
synchronously (target: <=5 s to first frames), then the rest in a
BackgroundTask. Same params -> same run_id -> cached, instant.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from dashboard.render.render_frames import render

from .. import jobs, mock_infer
from ..settings import get_settings

router = APIRouter(prefix="/api", tags=["predict"])

OUT_ROOT = Path("outputs/sur/whatif")
FRAMES_ROOT = "dashboard/static/frames"
FIRST_N_SYNC = 8

# Sampler ranges (§17.5) -- outside these, FastAPI/pydantic returns 422.
PARAM_FIELDS = {
    "rain_scale": (0.5, 1.8),
    "duration_stretch": (0.5, 2.0),
    "canal_stage_anom_m": (-0.3, 0.8),
    "outfall_stage_offset_m": (0.0, 0.6),
    "drain_multiplier": (0.3, 1.2),
}


class PredictIn(BaseModel):
    base_scenario_id: str
    rain_scale: float = Field(ge=PARAM_FIELDS["rain_scale"][0], le=PARAM_FIELDS["rain_scale"][1])
    duration_stretch: float = Field(ge=PARAM_FIELDS["duration_stretch"][0], le=PARAM_FIELDS["duration_stretch"][1])
    canal_stage_anom_m: float = Field(ge=PARAM_FIELDS["canal_stage_anom_m"][0], le=PARAM_FIELDS["canal_stage_anom_m"][1])
    outfall_stage_offset_m: float = Field(
        ge=PARAM_FIELDS["outfall_stage_offset_m"][0], le=PARAM_FIELDS["outfall_stage_offset_m"][1]
    )
    drain_multiplier: float = Field(ge=PARAM_FIELDS["drain_multiplier"][0], le=PARAM_FIELDS["drain_multiplier"][1])


def _canonical_json(params: dict) -> str:
    return json.dumps(params, sort_keys=True, separators=(",", ":"))


def _predict_fn():
    mode = get_settings().surrogate_mode
    if mode != "mock":
        try:
            from surrogate.infer import predict as real_predict  # Rishanth's module (HU6); not built yet

            return real_predict
        except ImportError:
            if mode == "real":
                raise HTTPException(503, "FG_SURROGATE_MODE=real but surrogate.infer isn't available yet")
    return mock_infer.predict


def _run_id_for(base_scenario_id: str, params: dict, version: str) -> str:
    digest = hashlib.sha1(_canonical_json(params).encode()).hexdigest()[:6]
    return f"{base_scenario_id}_X{digest}_sur_{version}"


def _finish_rendering(nc_path: Path, run_id: str, t0: float) -> None:
    try:
        render(nc_path, run_id, "surrogate", var_in="depth_m", var_out="depth", cmap="depth_v1", out_root=FRAMES_ROOT)
        jobs.set_job(run_id, status="DONE", elapsed_s=round(time.time() - t0, 3))
    except Exception as exc:  # pragma: no cover - defensive; surfaced via GET /api/predict/{run_id}
        jobs.set_job(run_id, status="FAILED", error=str(exc))


@router.post("/predict")
def predict(body: PredictIn, background_tasks: BackgroundTasks):
    t0 = time.time()
    params = {
        "rain_scale": body.rain_scale,
        "duration_stretch": body.duration_stretch,
        "canal_stage_anom_m": body.canal_stage_anom_m,
        "outfall_stage_offset_m": body.outfall_stage_offset_m,
        "drain_multiplier": body.drain_multiplier,
    }

    ds, meta = _predict_fn()(base_scenario_id=body.base_scenario_id, **params)
    version = meta.get("surrogate_version", "unknown")
    run_id = _run_id_for(body.base_scenario_id, params, version)

    cached = jobs.get_job(run_id)
    if cached and cached.get("status") == "DONE":
        ds.close()
        return cached

    nc_path = OUT_ROOT / run_id / "pred.nc"
    nc_path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(nc_path)

    n_total = ds.sizes["time"]
    first_n = min(FIRST_N_SYNC, n_total)
    render(
        nc_path,
        run_id,
        "surrogate",
        var_in="depth_m",
        var_out="depth",
        cmap="depth_v1",
        out_root=FRAMES_ROOT,
        da_override=ds["depth_m"].isel(time=slice(0, first_n)),
    )
    job = jobs.set_job(
        run_id,
        status="PARTIAL" if first_n < n_total else "DONE",
        manifest_url=f"/frames/surrogate/{run_id}/depth/manifest.json",
        ood_flag=bool(meta.get("ood_flag", False)),
        is_mock=bool(meta.get("is_mock", True)),
        elapsed_s=round(time.time() - t0, 3),
    )
    if first_n < n_total:
        background_tasks.add_task(_finish_rendering, nc_path, run_id, t0)
    ds.close()
    return job


@router.get("/predict/{run_id}")
def predict_status(run_id: str):
    job = jobs.get_job(run_id)
    if job is None:
        raise HTTPException(404, f"unknown run_id: {run_id}")
    return job
