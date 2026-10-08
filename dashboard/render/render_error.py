"""error = surrogate - hydraulic, on the surrogate's 40 m grid. See docs/VARUN_IMPLEMENTATION.md §6 T70.

Block-averages the hydraulic depth grid x2 (20 m -> 40 m) to compare
against the surrogate's native 40 m grid, then renders the difference
with error_v1 (red = surrogate over-predicts, blue = under-predicts).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import xarray as xr

from .render_frames import render

OUT_ROOT = "dashboard/static/frames"


def block_average(arr: np.ndarray, factor: int = 2) -> np.ndarray:
    """TEMP until surrogate.dataset.block_average lands (Rishanth's module
    doesn't exist yet) -- see docs/handoff_issues.md. Plain block mean over
    the trailing two axes: (..., y, x) -> (..., y // factor, x // factor).
    """
    *lead, ny, nx = arr.shape
    ny2, nx2 = ny // factor, nx // factor
    trimmed = arr[..., : ny2 * factor, : nx2 * factor]
    reshaped = trimmed.reshape(*lead, ny2, factor, nx2, factor)
    return reshaped.mean(axis=(-3, -1))


def render_error(
    hydraulic_nc,
    surrogate_nc,
    run_id: str,
    out_root: str = OUT_ROOT,
    factor: int = 2,
) -> dict:
    """Renders error_v1 frames under the surrogate run's `error` var and
    returns the manifest. `run_id` should be the surrogate run's own id, so
    error frames live alongside its depth/extent/sigma sets."""
    hyd = xr.open_dataset(hydraulic_nc)
    sur = xr.open_dataset(surrogate_nc)
    try:
        hyd_block = block_average(hyd["depth_m"].values, factor=factor)
        sur_depth = sur["depth_m"].values

        n = min(hyd_block.shape[0], sur_depth.shape[0])
        if hyd_block.shape[1:] != sur_depth.shape[1:]:
            raise ValueError(
                f"block-averaged hydraulic grid {hyd_block.shape[1:]} doesn't match "
                f"surrogate grid {sur_depth.shape[1:]} -- check factor={factor}"
            )
        error = (sur_depth[:n] - hyd_block[:n]).astype("float32")

        da = xr.DataArray(
            error,
            dims=("time", "y", "x"),
            coords={"time": sur["time"].values[:n], "y": sur["y"].values, "x": sur["x"].values},
        )
        manifest = render(
            surrogate_nc,
            run_id,
            "surrogate",
            var_in="depth_m",
            var_out="error",
            cmap="error_v1",
            out_root=out_root,
            da_override=da,
        )
    finally:
        hyd.close()
        sur.close()
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hydraulic-nc", required=True)
    parser.add_argument("--surrogate-nc", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--factor", type=int, default=2)
    args = parser.parse_args()

    manifest = render_error(args.hydraulic_nc, args.surrogate_nc, args.run_id, factor=args.factor)
    print(f"error: wrote {manifest['n_frames']} frames -> {OUT_ROOT}/surrogate/{args.run_id}/error/")


if __name__ == "__main__":
    main()
