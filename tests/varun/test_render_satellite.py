"""Tests for dashboard/render/render_satellite.py. See docs/VARUN_IMPLEMENTATION.md §6 T60."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from PIL import Image

from dashboard.render import render_satellite

BBOX_4326 = (100.535, 13.775, 100.630, 13.905)


def _write_mask_tif(path: Path, ny: int = 40, nx: int = 30) -> None:
    rng = np.random.RandomState(0)
    mask = np.zeros((ny, nx), dtype="uint8")
    mask[rng.random((ny, nx)) < 0.3] = 1
    mask[rng.random((ny, nx)) < 0.02] = 255
    res_m = 20
    transform = rasterio.transform.from_origin(680000, 1537000 + ny * res_m, res_m, res_m)
    with rasterio.open(
        path, "w", driver="GTiff", height=ny, width=nx, count=1, dtype="uint8",
        crs="EPSG:32647", transform=transform, nodata=255,
    ) as dst:
        dst.write(mask, 1)


def _write_scenario_fixture(obs_dir: Path, *, usable: bool = True, missing_mask: bool = False) -> None:
    obs_dir.mkdir(parents=True, exist_ok=True)
    mask_name = "sat_floodmask_TEST_20260925T2300Z.tif"
    if not missing_mask:
        _write_mask_tif(obs_dir / mask_name)
    pd.DataFrame(
        [{"sensor": "TEST", "ts_utc": "2026-09-25T23:00:00Z", "hours_from_peak": 13.0, "usable": usable, "mask_path": mask_name, "is_mock": True}]
    ).to_csv(obs_dir / "sat_acquisitions.csv", index=False)


def test_render_scenario_writes_png_and_manifest(tmp_path):
    scenarios_root = tmp_path / "scenarios"
    out_root = tmp_path / "frames" / "satellite"
    _write_scenario_fixture(scenarios_root / "S01" / "observations")

    manifest = render_satellite.render_scenario("S01", out_root=out_root, scenarios_root=scenarios_root, fixtures_root=tmp_path / "nope")

    assert manifest is not None
    assert manifest["scenario_id"] == "S01"
    assert len(manifest["acquisitions"]) == 1
    acq = manifest["acquisitions"][0]
    assert acq["sensor"] == "TEST"
    assert acq["png_url"] == "/frames/satellite/S01/TEST_20260925T230000Z.png"

    png_path = out_root / "S01" / "TEST_20260925T230000Z.png"
    assert png_path.exists()
    img = Image.open(png_path)
    assert img.mode == "RGBA"

    # bounds are plausible lon/lat, not left as projected meters
    w, s, e, n = acq["bounds"]
    assert -180 <= w < e <= 180
    assert -90 <= s < n <= 90

    written_manifest = json.loads((out_root / "S01" / "manifest.json").read_text())
    assert written_manifest == manifest


def test_render_scenario_skips_non_usable_rows(tmp_path):
    scenarios_root = tmp_path / "scenarios"
    out_root = tmp_path / "frames" / "satellite"
    _write_scenario_fixture(scenarios_root / "S02" / "observations", usable=False)

    manifest = render_satellite.render_scenario("S02", out_root=out_root, scenarios_root=scenarios_root, fixtures_root=tmp_path / "nope")

    assert manifest is not None
    assert manifest["acquisitions"] == []


def test_render_scenario_skips_rows_whose_mask_file_is_missing(tmp_path):
    scenarios_root = tmp_path / "scenarios"
    out_root = tmp_path / "frames" / "satellite"
    _write_scenario_fixture(scenarios_root / "S03" / "observations", missing_mask=True)

    manifest = render_satellite.render_scenario("S03", out_root=out_root, scenarios_root=scenarios_root, fixtures_root=tmp_path / "nope")

    assert manifest is not None
    assert manifest["acquisitions"] == []


def test_render_scenario_returns_none_without_an_acquisitions_file():
    # no CSV at all -- callers must show the explicit gap state, not an empty manifest
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        result = render_satellite.render_scenario("NOPE", scenarios_root=Path(td) / "scenarios", fixtures_root=Path(td) / "fixtures")
    assert result is None


def test_render_all_falls_back_to_fixtures_when_no_real_scenario_exists(tmp_path):
    fixtures_root = tmp_path / "fixtures"
    out_root = tmp_path / "frames" / "satellite"
    _write_scenario_fixture(fixtures_root / "MOCK_S01" / "observations")

    results = render_satellite.render_all(scenarios_root=tmp_path / "scenarios", fixtures_root=fixtures_root, out_root=out_root)

    assert [r["scenario_id"] for r in results] == ["MOCK_S01"]
    assert len(results[0]["acquisitions"]) == 1
