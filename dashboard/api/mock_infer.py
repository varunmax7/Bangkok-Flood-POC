"""Mock what-if predictor. Filled in by T71 — see docs/VARUN_IMPLEMENTATION.md §6 T71.

`POST /api/predict` is 501 until then, so nothing calls this yet.
"""
from __future__ import annotations


def predict(
    base_scenario_id: str,
    rain_scale: float,
    duration_stretch: float,
    canal_stage_anom_m: float,
    outfall_stage_offset_m: float,
    drain_multiplier: float,
):
    # TODO(T71): nearest fixture/hydraulic run x rain_scale, is_mock: true.
    raise NotImplementedError("mock_infer.predict is implemented in T71")
