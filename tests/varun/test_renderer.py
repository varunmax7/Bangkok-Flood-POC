import numpy as np
import pytest
from PIL import Image

from dashboard.render import colormaps as cm
from dashboard.render.render_all import render_all
from dashboard.render.render_frames import render, render_vars
from tools.fixtures import make_fixtures as mf

RUN_ID = "MOCK_BKK-S99_M000_lfp_mock-0"
SOURCE = "hydraulic"


@pytest.fixture(autouse=True)
def _fixtures():
    mf.main()


@pytest.fixture
def nc_path():
    return mf.OUT / "MOCK_BKK-S99" / "M000" / "depth.nc"


def test_depth_v1_alpha_zero_below_threshold():
    rgba = cm.depth_v1(np.array([[0.02, 0.8]]))
    assert rgba[0, 0, 3] == 0
    assert rgba[0, 1, 3] == 200


def test_depth_v1_class_colour_at_pond_peak():
    rgba = cm.depth_v1(np.array([[0.8]]))
    assert tuple(rgba[0, 0, :3]) == cm._hex_to_rgb("08519c")


@pytest.mark.parametrize("name", ["depth_v1", "extent_v1", "sigma_v1", "error_v1"])
def test_nan_is_transparent(name):
    rgba = cm.CMAPS[name](np.array([[np.nan]]))
    assert rgba[0, 0, 3] == 0


def test_render_frame_count_matches_manifest(tmp_path, nc_path):
    out_root = tmp_path / "frames"
    manifest = render(str(nc_path), RUN_ID, SOURCE, out_root=str(out_root))
    pngs = sorted((out_root / SOURCE / RUN_ID / "depth").glob("*.png"))
    assert len(pngs) == manifest["n_frames"] == 96


def test_render_bounds_within_bbox(tmp_path, nc_path):
    out_root = tmp_path / "frames"
    manifest = render(str(nc_path), RUN_ID, SOURCE, out_root=str(out_root))
    w, s, e, n = manifest["bounds_wgs84"]
    assert abs(w - 100.535) < 0.01
    assert abs(s - 13.775) < 0.01
    assert abs(e - 100.630) < 0.01
    assert abs(n - 13.905) < 0.01


def test_manifest_keys_match_spec(tmp_path, nc_path):
    out_root = tmp_path / "frames"
    manifest = render(str(nc_path), RUN_ID, SOURCE, out_root=str(out_root))
    expected = {
        "run_id",
        "source",
        "var",
        "bounds_wgs84",
        "crs_native",
        "t0_utc",
        "dt_s",
        "n_frames",
        "colormap",
        "thresholds_m",
        "data_class",
        "is_mock",
        "model_version",
        "scenario_id",
        "max_defensible_dt_s",
    }
    assert expected == set(manifest.keys())
    assert manifest["is_mock"] is True
    assert manifest["dt_s"] == 900
    assert manifest["data_class"] == "SYNTHETIC"
    assert manifest["model_version"] == "mock-0"


def test_known_pond_peak_pixel_renders_class_colour(tmp_path, nc_path):
    out_root = tmp_path / "frames"
    render(str(nc_path), RUN_ID, SOURCE, out_root=str(out_root))
    img = Image.open(out_root / SOURCE / RUN_ID / "depth" / "040.png").convert("RGBA")
    arr = np.array(img)
    target = (*cm._hex_to_rgb("08519c"), 200)
    assert np.any(np.all(arr == target, axis=-1))


def test_rerun_is_skipped_unless_force(tmp_path, nc_path):
    out_root = tmp_path / "frames"
    first = render_vars(nc_path, RUN_ID, SOURCE, ["depth"], out_root=str(out_root))
    assert first["depth"] is not None

    second = render_vars(nc_path, RUN_ID, SOURCE, ["depth"], out_root=str(out_root))
    assert second["depth"] is None  # manifest is newer than the (unchanged) NetCDF

    third = render_vars(nc_path, RUN_ID, SOURCE, ["depth"], out_root=str(out_root), force=True)
    assert third["depth"] is not None


def test_extent_var_produces_separate_output(tmp_path, nc_path):
    out_root = tmp_path / "frames"
    results = render_vars(nc_path, RUN_ID, SOURCE, ["depth", "extent"], out_root=str(out_root))
    assert (out_root / SOURCE / RUN_ID / "depth" / "manifest.json").exists()
    assert (out_root / SOURCE / RUN_ID / "extent" / "manifest.json").exists()
    assert results["extent"]["colormap"] == "extent_v1"


def test_render_all_handles_no_real_outputs_yet():
    # outputs/sim and outputs/sur exist (T00) but are empty until H2/H5 land.
    assert render_all() == []
