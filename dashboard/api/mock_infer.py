"""Mock what-if predictor used when FG_SURROGATE_MODE != "real" (T71).

See docs/VARUN_IMPLEMENTATION.md §6 T71. Real contract (Rishanth owns
`surrogate/infer.py::predict`, not built yet -- HU6):

    def predict(base_scenario_id, rain_scale, duration_stretch,
                canal_stage_anom_m, outfall_stage_offset_m, drain_multiplier
               ) -> tuple[xr.Dataset, dict]:
        ds: depth_m, sigma_m (time, y, x) on 40 m grid, CF time UTC, attrs crs.
        meta: {ood_flag: bool, mahalanobis: float, surrogate_version: str}

This mock scales the nearest fixture surrogate run's depth by rain_scale
and recomputes sigma from it, so the shape/contract match exactly without
needing a trained model.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

FIXTURES_DIR = Path("tools/fixtures/out")
SURROGATE_VERSION = "mock-whatif-0"

# [ASSUMPTION] Sampler ranges (§17.5) -- also enforced as the request-body
# validation bounds in predict.py.
PARAM_RANGES = {
    "rain_scale": (0.5, 1.8),
    "duration_stretch": (0.5, 2.0),
    "canal_stage_anom_m": (-0.3, 0.8),
    "outfall_stage_offset_m": (0.0, 0.6),
    "drain_multiplier": (0.3, 1.2),
}


def _nearest_fixture_surrogate(base_scenario_id: str) -> Path:
    candidates = [
        FIXTURES_DIR / base_scenario_id / "surrogate" / "pred.nc",
        FIXTURES_DIR / f"MOCK_{base_scenario_id}" / "surrogate" / "pred.nc",
    ]
    for p in candidates:
        if p.exists():
            return p
    found = sorted(FIXTURES_DIR.glob("*/surrogate/pred.nc"))
    if found:
        return found[0]
    raise FileNotFoundError(f"no fixture surrogate run found for base_scenario_id={base_scenario_id!r}")


def _edge_distance(params: dict) -> float:
    """[ASSUMPTION] No real training distribution to compute a true
    Mahalanobis distance against, so this is a lightweight proxy: each
    param normalized to [-1, 1] over its sampler range, combined as a
    Euclidean norm. >1 means at least one param is outside its range
    (caught by validation before this runs); the OOD threshold below is a
    judgement call, not a measured one."""
    total = 0.0
    for name, (lo, hi) in PARAM_RANGES.items():
        mid, half = (lo + hi) / 2, (hi - lo) / 2
        total += ((params[name] - mid) / half) ** 2
    return float(np.sqrt(total))


def predict(
    base_scenario_id: str,
    rain_scale: float,
    duration_stretch: float,
    canal_stage_anom_m: float,
    outfall_stage_offset_m: float,
    drain_multiplier: float,
) -> tuple[xr.Dataset, dict]:
    nc_path = _nearest_fixture_surrogate(base_scenario_id)
    base = xr.open_dataset(nc_path)

    depth = (base["depth_m"].values * rain_scale).astype("float32")
    sigma = (0.1 * depth + 0.01).astype("float32")

    ds = xr.Dataset(
        {"depth_m": (("time", "y", "x"), depth), "sigma_m": (("time", "y", "x"), sigma)},
        coords={"time": base["time"].values, "y": base["y"].values, "x": base["x"].values},
        attrs={
            "crs": base.attrs.get("crs", "EPSG:32647"),
            "surrogate_version": SURROGATE_VERSION,
            "scenario_id": base.attrs.get("scenario_id"),
            "data_class": "SYNTHETIC",
            "is_mock": 1,
        },
    )
    base.close()

    params = {
        "rain_scale": rain_scale,
        "duration_stretch": duration_stretch,
        "canal_stage_anom_m": canal_stage_anom_m,
        "outfall_stage_offset_m": outfall_stage_offset_m,
        "drain_multiplier": drain_multiplier,
    }
    mahalanobis = _edge_distance(params)
    meta = {
        # [ASSUMPTION] threshold is a judgement call: max possible distance is
        # sqrt(5)=2.236 (every param at its extreme simultaneously); 1.5 means
        # params need to be collectively well outside the middle of their
        # ranges across multiple dimensions, not just one param near an edge.
        "ood_flag": mahalanobis > 1.5,
        "mahalanobis": mahalanobis,
        "surrogate_version": SURROGATE_VERSION,
        "is_mock": True,
    }
    return ds, meta
