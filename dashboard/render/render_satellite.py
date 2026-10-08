"""Renders satellite flood-mask GeoTIFFs into dashboard-served PNGs + a
small per-scenario manifest. See docs/VARUN_IMPLEMENTATION.md §6 T60.

Unlike render_frames.py (a NetCDF with a time dimension, tied to one
run_id), a satellite acquisition is a single 2D raster tied to a
*scenario*, not a model run -- it may be compared against several runs
(hydraulic, surrogate, what-if) of the same scenario. So these are
grouped under frames/satellite/{scenario_id}/, and the API
(dashboard/api/store.py::get_run_satellite) looks them up by first
mapping the requested run_id to its own frame manifest's scenario_id.

Reprojects to EPSG:3857 first (same as render_frames.py) so the saved
PNG's pixel grid lines up proportionally with the lon/lat bounds the
frontend's BitmapLayer stretches it across -- skipping that step would
visibly skew the image at this latitude.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import rioxarray
from PIL import Image
from pyproj import Transformer
from rasterio.enums import Resampling

from .colormaps import CMAPS

OUT_ROOT = Path("dashboard/static/frames/satellite")
SCENARIOS_ROOT = Path("scenarios")
FIXTURES_ROOT = Path("tools/fixtures/out")


def _observations_dir(scenario_id: str, scenarios_root: Path = SCENARIOS_ROOT, fixtures_root: Path = FIXTURES_ROOT) -> Path | None:
    real = scenarios_root / scenario_id / "observations"
    if real.exists():
        return real
    fixture = fixtures_root / scenario_id / "observations"
    return fixture if fixture.exists() else None


def render_one(mask_tif: Path, cmap: str = "satmask_v1") -> tuple[np.ndarray, list[float]]:
    """Returns (rgba array, [w, s, e, n] bounds in EPSG:4326)."""
    da = rioxarray.open_rasterio(mask_tif)
    if "band" in da.dims:
        da = da.squeeze("band", drop=True)
    merc = da.rio.reproject("EPSG:3857", resampling=Resampling.nearest, nodata=255)
    l, b, r, t = merc.rio.bounds()
    tf = Transformer.from_crs(3857, 4326, always_xy=True)
    (w, s), (e, n) = tf.transform(l, b), tf.transform(r, t)
    rgba = CMAPS[cmap](merc.values)
    return rgba, [w, s, e, n]


def render_scenario(
    scenario_id: str,
    out_root: Path = OUT_ROOT,
    scenarios_root: Path = SCENARIOS_ROOT,
    fixtures_root: Path = FIXTURES_ROOT,
) -> dict | None:
    """Renders every usable row of {scenario_id}/observations/sat_acquisitions.csv.
    Returns None (writes nothing) when there's no acquisitions file at all --
    callers show the explicit "No coincident acquisition [DATA GAP]" state
    instead of a manifest with zero acquisitions."""
    obs_dir = _observations_dir(scenario_id, scenarios_root, fixtures_root)
    if obs_dir is None:
        return None
    csv_path = obs_dir / "sat_acquisitions.csv"
    if not csv_path.exists():
        return None

    out_dir = out_root / scenario_id
    acquisitions = []
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            if row.get("usable", "True").strip().lower() not in ("true", "1"):
                continue
            mask_path = obs_dir / row["mask_path"]
            if not mask_path.exists():
                continue
            rgba, bounds = render_one(mask_path)
            ts_compact = row["ts_utc"].replace("-", "").replace(":", "")
            fname = f"{row['sensor']}_{ts_compact}.png"
            out_dir.mkdir(parents=True, exist_ok=True)
            Image.fromarray(rgba, "RGBA").save(out_dir / fname, optimize=True)
            acquisitions.append(
                {
                    "sensor": row["sensor"],
                    "ts_utc": row["ts_utc"],
                    "hours_from_peak": float(row["hours_from_peak"]),
                    "png_url": f"/frames/satellite/{scenario_id}/{fname}",
                    "bounds": bounds,
                }
            )

    manifest = {"scenario_id": scenario_id, "acquisitions": acquisitions}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest


def render_all(
    scenarios_root: Path = SCENARIOS_ROOT,
    fixtures_root: Path = FIXTURES_ROOT,
    out_root: Path = OUT_ROOT,
) -> list[dict]:
    scenario_ids: set[str] = set()
    if scenarios_root.exists():
        scenario_ids.update(p.name for p in scenarios_root.iterdir() if p.is_dir())
    if fixtures_root.exists():
        scenario_ids.update(p.name for p in fixtures_root.iterdir() if p.is_dir() and (p / "observations").exists())

    results = []
    for scenario_id in sorted(scenario_ids):
        manifest = render_scenario(scenario_id, out_root, scenarios_root, fixtures_root)
        if manifest is not None:
            results.append(manifest)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario-id", default=None, help="render just this scenario; default: scan scenarios/ + fixtures")
    args = parser.parse_args()

    if args.scenario_id:
        manifest = render_scenario(args.scenario_id)
        print(f"{args.scenario_id}: {len(manifest['acquisitions']) if manifest else 0} acquisition(s)")
    else:
        for manifest in render_all():
            print(f"{manifest['scenario_id']}: {len(manifest['acquisitions'])} acquisition(s)")


if __name__ == "__main__":
    main()
