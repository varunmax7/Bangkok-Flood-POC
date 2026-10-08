import numpy as np
import pandas as pd
import pytest

from cctv.classifier.synth_obs import build_synth_obs
from cctv.classifier.write_obs import (
    OUT_COLUMNS,
    PROB_COLS,
    _depth_estimate_combined,
    _severe_depth_from_pixels,
    _smoothed_series,
    _water_pixel_pct,
    build_cctv_obs,
    model_version,
)
from cctv.registry import build_registry as br
from tools.fixtures import make_fixtures as mf

FRAMES_PARQUET = "data/cctv/cctv_frames.parquet"


@pytest.fixture(scope="module", autouse=True)
def _fixtures_and_registry_and_cache():
    mf.main()
    br.build_registry()
    from cctv.classifier.embed import embed_new_frames
    from cctv.classifier.zeroshot import write_zeroshot

    embed_new_frames()
    write_zeroshot()


def test_build_cctv_obs_schema_and_types(tmp_path):
    out_path = tmp_path / "cctv_obs.parquet"
    df = build_cctv_obs(out_path=out_path)
    assert list(df.columns) == OUT_COLUMNS
    assert out_path.exists()

    frames_n = len(pd.read_parquet(FRAMES_PARQUET))
    assert len(df) == frames_n

    assert df["is_mock"].dtype == bool
    assert (df["is_mock"] == False).all()  # noqa: E712
    assert (df["data_class"] == "OBSERVED").all()
    assert set(df["model_version"].unique()) == {model_version()}


def test_probs_sum_to_one_and_unusable_rule(tmp_path):
    out_path = tmp_path / "cctv_obs.parquet"
    df = build_cctv_obs(out_path=out_path)
    sums = df[PROB_COLS].sum(axis=1)
    assert np.allclose(sums, 1.0, atol=1e-4)

    unusable = df[df["class"] == "UNUSABLE"]
    if not unusable.empty:
        assert (unusable["p_unusable"] == 1.0).all()
        assert unusable["depth_proxy_bin"].isna().all()


def test_no_duplicate_cam_ts(tmp_path):
    out_path = tmp_path / "cctv_obs.parquet"
    df = build_cctv_obs(out_path=out_path)
    assert df.duplicated(subset=["cam_id", "ts_utc"]).sum() == 0


def test_smoothing_majority_with_tie_break_on_crafted_sequence():
    # cam A: N, N, W, F, F  -> smoothed at each step (window of last <=3 usable):
    #   [N] -> N
    #   [N,N] -> N
    #   [N,N,W] -> N (2 vs 1)
    #   [N,W,F] -> tie N/W/F (1 each) -> most recent = F
    #   [W,F,F] -> F (2 vs 1)
    df = pd.DataFrame(
        {
            "cam_id": ["A"] * 5,
            "class": ["NORMAL", "NORMAL", "WATERLOGGING", "FLOODING", "FLOODING"],
        }
    )
    smoothed = _smoothed_series(df)
    assert smoothed == ["NORMAL", "NORMAL", "NORMAL", "FLOODING", "FLOODING"]


def test_smoothing_skips_unusable_frames_in_window():
    # UNUSABLE frames don't enter the window, but still get a smoothed value
    # carried from the last usable window.
    df = pd.DataFrame(
        {
            "cam_id": ["A"] * 4,
            "class": ["FLOODING", "UNUSABLE", "UNUSABLE", "NORMAL"],
        }
    )
    smoothed = _smoothed_series(df)
    assert smoothed == ["FLOODING", "FLOODING", "FLOODING", "NORMAL"]


def test_severe_depth_from_pixels_monotonic_and_bounded():
    pcts = [0.0, 0.05, 0.10, 0.25, 0.40, 0.544, 0.55, 0.70, 0.85, 1.0]
    depths = [_severe_depth_from_pixels(p) for p in pcts]
    assert depths == sorted(depths)  # monotonic non-decreasing in water_pct
    assert depths[0] >= 0.30  # never below the SEVERE_FLOODING bin floor
    assert depths[-1] <= 1.50  # capped at the top breakpoint, never invented higher


def test_depth_estimate_combined_regression_submerged_car_case():
    """Regression test for the exact bug this was built to fix: a frame the
    classifier is confident is SEVERE_FLOODING (p_severe=0.88) with 54%
    water-pixel coverage must read near the car-bonnet depth (~0.80-0.95 m)
    the pixel breakpoint table targets -- not the old flat ~0.47 m bin
    midpoint a plain CLIP-weighted average alone would give."""
    bins = {"NORMAL": (0.00, 0.05), "WATERLOGGING": (0.05, 0.15), "FLOODING": (0.15, 0.30), "SEVERE_FLOODING": (0.30, None)}
    probs = {"p_normal": 0.007, "p_waterlogging": 0.004, "p_flooding": 0.113, "p_severe": 0.883, "p_unusable": 0.0}
    depth = _depth_estimate_combined(probs, bins, water_pixel_pct=0.544)
    assert depth is not None
    assert 0.80 <= depth <= 0.95


def test_depth_estimate_combined_falls_back_to_clip_without_pixels_or_confidence():
    bins = {"NORMAL": (0.00, 0.05), "WATERLOGGING": (0.05, 0.15), "FLOODING": (0.15, 0.30), "SEVERE_FLOODING": (0.30, None)}
    # High p_severe but no pixel data -> CLIP-weighted blend only, not None.
    probs = {"p_normal": 0.0, "p_waterlogging": 0.0, "p_flooding": 0.0, "p_severe": 1.0, "p_unusable": 0.0}
    depth_no_pixels = _depth_estimate_combined(probs, bins, water_pixel_pct=None)
    assert depth_no_pixels is not None

    # Mostly-dry classification (p_severe well under the 0.50 gate) ignores
    # even a high water_pixel_pct -- the pixel path only ever applies to
    # frames the classifier itself already believes are severely flooded.
    dry_probs = {"p_normal": 0.9, "p_waterlogging": 0.05, "p_flooding": 0.03, "p_severe": 0.02, "p_unusable": 0.0}
    depth_dry = _depth_estimate_combined(dry_probs, bins, water_pixel_pct=0.95)
    assert depth_dry is not None
    assert depth_dry < 0.10  # stays near the NORMAL/WATERLOGGING range, not inflated by pixels


def test_water_pixel_pct_distinguishes_blue_water_from_bright_sky(tmp_path):
    from PIL import Image

    water_path = tmp_path / "water.jpg"
    Image.new("RGB", (120, 90), (90, 110, 130)).save(water_path)  # desaturated blue-grey, like real floodwater
    sky_path = tmp_path / "sky.jpg"
    Image.new("RGB", (120, 90), (235, 235, 245)).save(sky_path)  # bright near-white

    assert _water_pixel_pct(str(water_path)) > 0.5
    assert _water_pixel_pct(str(sky_path)) < 0.2
    assert _water_pixel_pct(None) is None
    assert _water_pixel_pct(str(tmp_path / "does_not_exist.jpg")) is None


def test_build_cctv_obs_is_submerged_gated_by_severe_confidence(tmp_path):
    """Regression test for build_cctv_obs's real wiring, not just the pure
    helper functions above: is_submerged must never be True for a row the
    classifier itself doesn't believe is SEVERE_FLOODING, however high that
    row's raw water_pixel_pct happens to read (grey_water's colour mask
    can't tell turbid floodwater from plain dry pavement -- see the
    grey_water weight comment in write_obs.py)."""
    out_path = tmp_path / "cctv_obs.parquet"
    df = build_cctv_obs(out_path=out_path)
    assert "is_submerged" in df.columns
    assert "depth_proxy_m" in df.columns
    assert "water_pixel_pct" in df.columns

    submerged = df[df["is_submerged"] == True]  # noqa: E712
    if not submerged.empty:
        assert (submerged["p_severe"] >= 0.50).all()
        assert (submerged["water_pixel_pct"] >= 0.70).all()


def test_synth_obs_schema(tmp_path):
    out_path = tmp_path / "MOCK_cctv_obs.parquet"
    df = build_synth_obs(out_path=out_path)
    assert set(OUT_COLUMNS) == set(df.columns)
    assert (df["is_mock"]).all()
    assert (df["data_class"] == "SYNTHETIC").all()
    assert df.duplicated(subset=["cam_id", "ts_utc"]).sum() == 0
    sums = df[PROB_COLS].sum(axis=1)
    assert np.allclose(sums, 1.0, atol=1e-6)

    n_cams = len(set(df["cam_id"]))
    n_times = len(df) // n_cams
    assert len(df) == n_cams * n_times
