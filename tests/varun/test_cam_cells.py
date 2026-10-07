import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from pyproj import Transformer

from cctv.registry import build_registry as br
from tools.fixtures import make_fixtures as mf
from validation.cctv import compare
from validation.cctv.cam_cells import CAM_BUFFER_M, build_cam_cells

POND_CENTER_GRID = (200, 150)  # row, col -- see tools/fixtures/make_fixtures.POND_CENTERS
PEAK_TS_UTC = "2026-09-25T10:00:00Z"  # T01: T0_UTC + 40 * 900s
DEPTH_NC = "tools/fixtures/out/MOCK_BKK-S99/M000/depth.nc"


@pytest.fixture(scope="module", autouse=True)
def _fixtures_and_registry():
    mf.main()
    br.build_registry()


def _domain():
    return yaml.safe_load(Path("tools/fixtures/out/domain.yaml").read_text())


def _camera_registry_at(tmp_path, lon, lat, cam_id="TEST-POND"):
    reg = {
        "type": "FeatureCollection",
        "metadata": {"is_mock": True},
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "cam_id": cam_id,
                    "source": "BMAT",
                    "lon": lon,
                    "lat": lat,
                    "status": "ACTIVE",
                    "in_domain": True,
                },
            }
        ],
    }
    path = tmp_path / "cameras.geojson"
    path.write_text(json.dumps(reg))
    return path


def test_camera_on_pond_centre_gets_peak_depth(tmp_path):
    domain = _domain()
    ox, oy = domain["origin_x"], domain["origin_y"]
    row, col = POND_CENTER_GRID
    x = ox + (col + 0.5) * 20
    y = oy + (row + 0.5) * 20
    tf = Transformer.from_crs(domain["crs"], 4326, always_xy=True)
    lon, lat = tf.transform(x, y)

    registry_path = _camera_registry_at(tmp_path, lon, lat)
    cells = build_cam_cells(registry_path=registry_path, out_path=tmp_path / "cam_cells.parquet")

    series = compare.model_series(DEPTH_NC, cells, grid_res_m=20)
    peak_row = series[series["ts_utc"] == PEAK_TS_UTC]
    assert len(peak_row) == 1
    assert abs(float(peak_row["depth_max_m"].iloc[0]) - 0.8) < 1e-3


def test_cells_within_buffer_distance(tmp_path):
    domain = _domain()
    ox, oy = domain["origin_x"], domain["origin_y"]
    row, col = POND_CENTER_GRID
    x = ox + (col + 0.5) * 20
    y = oy + (row + 0.5) * 20
    tf = Transformer.from_crs(domain["crs"], 4326, always_xy=True)
    lon, lat = tf.transform(x, y)

    registry_path = _camera_registry_at(tmp_path, lon, lat)
    cells = build_cam_cells(registry_path=registry_path, out_path=tmp_path / "cam_cells.parquet")

    res20 = cells[cells["grid_res_m"] == 20]
    for _, cell_row in res20.iterrows():
        cx = ox + (cell_row["col"] + 0.5) * 20
        cy = oy + (cell_row["row"] + 0.5) * 20
        dist = np.hypot(cx - x, cy - y)
        assert dist <= CAM_BUFFER_M + 1.0  # +1m slack for circle polygon approximation

    assert not res20["road_clip"].any()  # no OSM roads fixture -> always falls back


def test_cam_cells_has_both_resolutions_for_real_registry():
    cells = build_cam_cells()  # real registry (T11 fixture fallback), real output path
    assert set(cells["grid_res_m"].unique()) == {20, 40}
    assert Path("validation/cctv/cam_cells.parquet").exists()
    assert cells["cam_id"].nunique() <= 10


def test_model_series_bin_matches_depth_bins_m():
    domain = _domain()
    ox, oy = domain["origin_x"], domain["origin_y"]
    row, col = POND_CENTER_GRID
    tf = Transformer.from_crs(domain["crs"], 4326, always_xy=True)
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        lon, lat = tf.transform(ox + (col + 0.5) * 20, oy + (row + 0.5) * 20)
        registry_path = _camera_registry_at(Path(d), lon, lat)
        cells = build_cam_cells(registry_path=registry_path, out_path=Path(d) / "cam_cells.parquet")
    series = compare.model_series(DEPTH_NC, cells, grid_res_m=20)
    peak_row = series[series["ts_utc"] == PEAK_TS_UTC].iloc[0]
    assert peak_row["bin"] == "0.50-1.00"


def test_confusion_kappa_one_on_identical_series():
    model = pd.DataFrame(
        {
            "cam_id": ["A"] * 5,
            "ts_utc": pd.date_range("2026-01-01", periods=5, freq="15min").strftime("%Y-%m-%dT%H:%M:%SZ"),
            "depth_max_m": [0.02, 0.08, 0.20, 0.35, 0.02],
        }
    )
    cctv = pd.DataFrame(
        {
            "cam_id": ["A"] * 5,
            "ts_utc": model["ts_utc"],
            "class_smoothed": ["NORMAL", "WATERLOGGING", "FLOODING", "SEVERE_FLOODING", "NORMAL"],
        }
    )
    result = compare.confusion(cctv, model)
    assert result["kappa"] == 1.0
    assert result["n_pairs"] == 5
    assert np.trace(np.array(result["confusion_matrix"])) == 5  # perfect diagonal
    assert result["onset_error_min"]["A"] == 0.0


def test_confusion_handles_disagreement_and_unusable_exclusion():
    model = pd.DataFrame(
        {
            "cam_id": ["A", "A"],
            "ts_utc": ["2026-01-01T00:00:00Z", "2026-01-01T00:15:00Z"],
            "depth_max_m": [0.02, 0.02],
        }
    )
    cctv = pd.DataFrame(
        {
            "cam_id": ["A", "A"],
            "ts_utc": ["2026-01-01T00:00:00Z", "2026-01-01T00:15:00Z"],
            "class_smoothed": ["FLOODING", "UNUSABLE"],
        }
    )
    result = compare.confusion(cctv, model)
    assert result["n_pairs"] == 1  # the UNUSABLE row is excluded
    assert result["kappa"] is not None


def test_confusion_empty_when_no_overlap_in_time():
    model = pd.DataFrame({"cam_id": ["A"], "ts_utc": ["2026-01-01T00:00:00Z"], "depth_max_m": [0.5]})
    cctv = pd.DataFrame({"cam_id": ["A"], "ts_utc": ["2026-06-01T00:00:00Z"], "class_smoothed": ["FLOODING"]})
    result = compare.confusion(cctv, model, tol_min=7)
    assert result["n_pairs"] == 0
    assert result["kappa"] is None
