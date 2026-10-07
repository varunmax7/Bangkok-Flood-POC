import numpy as np
import pandas as pd
import pytest

from cctv.classifier.synth_obs import build_synth_obs
from cctv.classifier.write_obs import OUT_COLUMNS, PROB_COLS, _smoothed_series, build_cctv_obs, model_version
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
