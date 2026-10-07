"""NetCDF -> EPSG:3857-aligned RGBA PNG frames + manifest. See docs/VARUN_IMPLEMENTATION.md §6 T40 / §20.3."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rioxarray  # noqa: F401  (registers the .rio accessor)
import xarray as xr
from PIL import Image
from pyproj import Transformer
from rasterio.enums import Resampling

from .colormaps import CMAPS

# var_out -> (source netCDF variable, colormap). Only variables present on
# the hydraulic/surrogate NetCDFs; error_v1/satmask_v1 are rendered by
# render_error.py (T70) / render_satellite.py (T60) directly from CMAPS.
VAR_SPECS = {
    "depth": {"var_in": "depth_m", "cmap": "depth_v1"},
    "extent": {"var_in": "depth_m", "cmap": "extent_v1"},
    "sigma": {"var_in": "sigma_m", "cmap": "sigma_v1"},
}


def render(
    nc_path,
    run_id,
    source,
    var_in="depth_m",
    var_out="depth",
    cmap="depth_v1",
    out_root="dashboard/static/frames",
    da_override=None,
):
    ds = xr.open_dataset(nc_path)
    da = da_override if da_override is not None else ds[var_in]
    da = da.rio.set_spatial_dims(x_dim="x", y_dim="y").rio.write_crs(ds.attrs.get("crs", "EPSG:32647"))
    merc = da.rio.reproject("EPSG:3857", resampling=Resampling.nearest, nodata=np.nan)
    l, b, r, t = merc.rio.bounds()
    tf = Transformer.from_crs(3857, 4326, always_xy=True)
    (w, s), (e, n) = tf.transform(l, b), tf.transform(r, t)
    out = Path(out_root) / source / run_id / var_out
    out.mkdir(parents=True, exist_ok=True)
    for i in range(merc.sizes["time"]):
        Image.fromarray(CMAPS[cmap](merc.isel(time=i).values), "RGBA").save(out / f"{i:03d}.png", optimize=True)
    # from merc (what was actually rendered), not ds, so a sliced da_override
    # (T71's "first 8 frames" partial render) gets a manifest matching reality.
    times = merc["time"].values
    manifest = {
        "run_id": run_id,
        "source": source,
        "var": var_out,
        "bounds_wgs84": [w, s, e, n],
        "crs_native": str(da.rio.crs),
        "t0_utc": np.datetime_as_string(times[0], unit="s") + "Z",
        "dt_s": int((times[1] - times[0]) / np.timedelta64(1, "s")) if len(times) > 1 else None,
        "n_frames": int(len(times)),
        "colormap": cmap,
        "thresholds_m": [0.05, 0.15, 0.30, 0.50, 1.0],
        "data_class": ds.attrs.get("data_class", "SYNTHETIC"),
        "is_mock": run_id.startswith("MOCK_") or bool(ds.attrs.get("is_mock", False)),
        "model_version": ds.attrs.get("model_version") or ds.attrs.get("surrogate_version"),
        "scenario_id": ds.attrs.get("scenario_id"),
        "max_defensible_dt_s": ds.attrs.get("max_defensible_dt_s"),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    ds.close()
    return manifest


def _needs_render(nc_path: Path, out_dir: Path, force: bool) -> bool:
    if force:
        return True
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.exists():
        return True
    return nc_path.stat().st_mtime > manifest_path.stat().st_mtime


def render_vars(nc_path, run_id, source, variables, out_root="dashboard/static/frames", force=False):
    """Render each requested variable, skipping ones whose manifest is already
    newer than the source NetCDF (unless force=True). Returns {var_out: manifest|None}."""
    nc_path = Path(nc_path)
    results: dict[str, dict | None] = {}
    for var_out in variables:
        spec = VAR_SPECS[var_out]
        out_dir = Path(out_root) / source / run_id / var_out
        if not _needs_render(nc_path, out_dir, force):
            results[var_out] = None
            continue
        results[var_out] = render(
            nc_path, run_id, source, var_in=spec["var_in"], var_out=var_out, cmap=spec["cmap"], out_root=out_root
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--nc", required=True)
    parser.add_argument("--vars", default="depth")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    variables = [v.strip() for v in args.vars.split(",") if v.strip()]
    results = render_vars(args.nc, args.run_id, args.source, variables, force=args.force)
    for var_out, manifest in results.items():
        if manifest is None:
            print(f"{var_out}: skipped (up to date)")
        else:
            print(f"{var_out}: wrote {manifest['n_frames']} frames -> dashboard/static/frames/{args.source}/{args.run_id}/{var_out}/")


if __name__ == "__main__":
    main()
