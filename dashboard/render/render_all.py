"""Render frames for every real hydraulic/surrogate run found on disk.

See docs/VARUN_IMPLEMENTATION.md §6 T40. Scans `outputs/sim/*/*/depth.nc`
(source hydraulic) and `outputs/sur/*/pred.nc` (source surrogate); each
variable is skipped if its manifest is already newer than the NetCDF
(render_frames.render_vars handles that). This never touches the T01
fixtures — those are rendered directly via `make frames` with an explicit
--nc path, since they don't live under outputs/.
"""
from __future__ import annotations

from pathlib import Path

import xarray as xr

from .render_frames import render_vars

HYDRAULIC_GLOB = "outputs/sim/*/*/depth.nc"
SURROGATE_GLOB = "outputs/sur/*/pred.nc"


def _run_id_for(nc_path: Path, source: str) -> str:
    with xr.open_dataset(nc_path) as ds:
        run_id = ds.attrs.get("run_id")
    if run_id:
        return run_id
    if source == "hydraulic":
        # outputs/sim/{scenario_id}/{member_id}/depth.nc
        member_id = nc_path.parent.name
        scenario_id = nc_path.parent.parent.name
        return f"{scenario_id}_{member_id}"
    # outputs/sur/{run_id}/pred.nc
    return nc_path.parent.name


def render_all(force: bool = False) -> list[dict]:
    done = []
    for nc_path in sorted(Path().glob(HYDRAULIC_GLOB)):
        run_id = _run_id_for(nc_path, "hydraulic")
        results = render_vars(nc_path, run_id, "hydraulic", ["depth", "extent"], force=force)
        done.append({"nc": str(nc_path), "run_id": run_id, "source": "hydraulic", "rendered": list(results)})
    for nc_path in sorted(Path().glob(SURROGATE_GLOB)):
        run_id = _run_id_for(nc_path, "surrogate")
        results = render_vars(nc_path, run_id, "surrogate", ["depth", "extent", "sigma"], force=force)
        done.append({"nc": str(nc_path), "run_id": run_id, "source": "surrogate", "rendered": list(results)})
    return done


def main() -> None:
    for entry in render_all():
        print(entry)


if __name__ == "__main__":
    main()
