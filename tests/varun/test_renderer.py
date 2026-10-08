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


def test_render_with_sliced_da_override_manifest_matches_pngs_written(tmp_path, nc_path):
    """T71 renders a time-sliced da_override ("first 8 frames synchronously");
    the manifest's n_frames must match what was actually written, not the
    full source NetCDF's time length."""
    import xarray as xr

    out_root = tmp_path / "frames"
    ds = xr.open_dataset(nc_path)
    manifest = render(
        str(nc_path), RUN_ID, SOURCE, da_override=ds["depth_m"].isel(time=slice(0, 8)), out_root=str(out_root)
    )
    pngs = list((out_root / SOURCE / RUN_ID / "depth").glob("*.png"))
    assert manifest["n_frames"] == 8
    assert len(pngs) == 8


def test_render_all_handles_no_real_outputs_yet():
    # outputs/sim and outputs/sur exist (T00) but are empty until H2/H5 land.
    assert render_all() == []


def _make_synthetic_hydraulic_surrogate_nc(tmp_path):
    """8x8 @ 20m hydraulic (uniform 0.1) + 4x4 @ 40m surrogate with three
    deliberately-controlled cells, for checking error_v1's sign/transparency
    against known values -- the real fixture's surrogate noise (std=0.01) is
    far too small to reliably cross error_v1's 0.05 m threshold."""
    import xarray as xr

    ox, oy = 665000.0, 1520000.0
    nx, ny = 8, 8
    x = ox + (np.arange(nx) + 0.5) * 20
    y = oy + (np.arange(ny) + 0.5) * 20
    times = np.array([np.datetime64("2026-01-01T00:00:00")])

    hyd_depth = np.full((1, ny, nx), 0.1, dtype="float32")
    hyd_ds = xr.Dataset(
        {"depth_m": (("time", "y", "x"), hyd_depth)},
        coords={"time": times, "y": y, "x": x},
        attrs={"crs": "EPSG:32647", "data_class": "SYNTHETIC", "is_mock": 1},
    )
    hyd_path = tmp_path / "hydraulic.nc"
    hyd_ds.to_netcdf(hyd_path)

    x2 = x.reshape(4, 2).mean(axis=1)
    y2 = y.reshape(4, 2).mean(axis=1)
    sur_depth = np.full((1, 4, 4), 0.1, dtype="float32")
    sur_depth[0, 0, 0] = 0.5  # error = +0.4 -> strong positive (over-prediction)
    sur_depth[0, 1, 1] = -0.3  # error = -0.4 -> strong negative (under-prediction)
    sur_depth[0, 2, 2] = 0.11  # error = +0.01 -> below threshold, stays transparent
    sur_ds = xr.Dataset(
        {"depth_m": (("time", "y", "x"), sur_depth)},
        coords={"time": times, "y": y2, "x": x2},
        attrs={"crs": "EPSG:32647", "surrogate_version": "test-0", "data_class": "SYNTHETIC", "is_mock": 1},
    )
    sur_path = tmp_path / "surrogate.nc"
    sur_ds.to_netcdf(sur_path)
    return hyd_path, sur_path


def test_render_error_sign_and_transparency(tmp_path):
    from dashboard.render.render_error import render_error

    hyd_path, sur_path = _make_synthetic_hydraulic_surrogate_nc(tmp_path)
    out_root = tmp_path / "frames"
    manifest = render_error(hyd_path, sur_path, "TEST_ERROR_RUN", out_root=str(out_root))
    assert manifest["colormap"] == "error_v1"
    assert manifest["var"] == "error"

    img = Image.open(out_root / "surrogate" / "TEST_ERROR_RUN" / "error" / "000.png").convert("RGBA")
    arr = np.array(img)

    strong_positive = (*cm._hex_to_rgb("cb181d"), 200)  # |e| >= 0.30, over-prediction -> darkest red
    strong_negative = (*cm._hex_to_rgb("2171b5"), 200)  # |e| >= 0.30, under-prediction -> darkest blue
    assert np.any(np.all(arr == strong_positive, axis=-1)), "expected a strong positive-error red pixel"
    assert np.any(np.all(arr == strong_negative, axis=-1)), "expected a strong negative-error blue pixel"
    assert (arr[:, :, 3] == 0).sum() > 0  # untouched/near-zero-error cells stay transparent


def test_block_average_matches_expected_reshape_mean():
    """The TEMP local block_average() (docs/handoff_issues.md) must do a
    plain block mean, since that's what the error calc -- and the fixture
    generator's own surrogate grid -- assume."""
    from dashboard.render.render_error import block_average

    arr = np.arange(64, dtype="float64").reshape(1, 8, 8)
    out = block_average(arr, factor=2)
    assert out.shape == (1, 4, 4)
    assert out[0, 0, 0] == pytest.approx(arr[0, 0:2, 0:2].mean())
    assert out[0, 3, 3] == pytest.approx(arr[0, 6:8, 6:8].mean())
