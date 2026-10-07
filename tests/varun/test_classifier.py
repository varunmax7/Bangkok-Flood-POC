import warnings

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from cctv.classifier.clip_model import CLASSES, embed_and_zeroshot
from cctv.classifier.embed import embed_new_frames
from cctv.classifier.zeroshot import write_zeroshot
from cctv.registry import build_registry as br
from tools.fixtures import make_fixtures as mf

FRAMES_PARQUET = "data/cctv/cctv_frames.parquet"


@pytest.fixture(scope="module", autouse=True)
def _fixtures_and_registry():
    mf.main()
    br.build_registry()


def test_embed_and_zeroshot_shapes_and_probs_sum():
    df = pd.read_parquet(FRAMES_PARQUET)
    imgs = [Image.open(p).convert("RGB") for p in df["path"].head(5)]
    emb, probs = embed_and_zeroshot(imgs)
    assert emb.shape == (5, 512)
    assert probs.shape == (5, len(CLASSES))
    assert np.allclose(probs.sum(axis=1), 1.0, atol=1e-4)


def test_embed_new_frames_builds_cache(tmp_path):
    cache_path = tmp_path / "embeddings.parquet"
    n = embed_new_frames(cache_path=cache_path)
    assert n > 0
    df = pd.read_parquet(cache_path)
    assert len(df) == n
    assert set(df.columns) >= {"cam_id", "ts_utc", "sha1", "emb"}
    assert df["sha1"].is_unique  # dedup by sha1 (identical frames aren't re-embedded)
    for vec in df["emb"].head(5):
        assert len(vec) == 512


def test_embed_cache_resumes_without_recompute(tmp_path):
    cache_path = tmp_path / "embeddings.parquet"
    first = embed_new_frames(cache_path=cache_path)
    assert first > 0

    second = embed_new_frames(cache_path=cache_path)
    assert second == 0  # every sha1 already cached -> nothing new

    df = pd.read_parquet(cache_path)
    assert len(df) == first  # unchanged


def test_zeroshot_probs_sum_to_one_and_resumes(tmp_path):
    emb_cache = tmp_path / "embeddings.parquet"
    zs_cache = tmp_path / "zeroshot.parquet"
    embed_new_frames(cache_path=emb_cache)

    n = write_zeroshot(embeddings_cache=emb_cache, zeroshot_cache=zs_cache)
    assert n > 0
    df = pd.read_parquet(zs_cache)
    prob_cols = ["p_normal", "p_waterlogging", "p_flooding", "p_severe", "p_unusable"]
    assert set(prob_cols) <= set(df.columns)
    sums = df[prob_cols].sum(axis=1)
    assert np.allclose(sums, 1.0, atol=1e-4)

    second = write_zeroshot(embeddings_cache=emb_cache, zeroshot_cache=zs_cache)
    assert second == 0
    assert len(pd.read_parquet(zs_cache)) == n


def test_wet_frames_score_higher_flood_probability_on_average(tmp_path):
    """Soft check (per the card): warn, don't fail, if this doesn't hold —
    it's a sanity signal on the zero-shot prompts, not a hard contract."""
    emb_cache = tmp_path / "embeddings.parquet"
    zs_cache = tmp_path / "zeroshot.parquet"
    embed_new_frames(cache_path=emb_cache)
    write_zeroshot(embeddings_cache=emb_cache, zeroshot_cache=zs_cache)

    frames = pd.read_parquet(FRAMES_PARQUET)
    zs = pd.read_parquet(zs_cache)
    zs["flood_prob"] = zs["p_flooding"] + zs["p_severe"]
    merged = frames.merge(zs[["sha1", "flood_prob"]].drop_duplicates("sha1"), on="sha1")

    wet_cams = set(frames["cam_id"].unique()[:5])
    is_wet_frame = merged["cam_id"].isin(wet_cams) & (merged["ts_utc"] > merged.groupby("cam_id")["ts_utc"].transform("min"))
    wet_mean = merged.loc[is_wet_frame, "flood_prob"].mean()
    dry_mean = merged.loc[~merged["cam_id"].isin(wet_cams), "flood_prob"].mean()

    if not (wet_mean > dry_mean):
        warnings.warn(
            f"expected wet fixture frames to score a higher mean flood probability than dry ones "
            f"(wet={wet_mean:.4f}, dry={dry_mean:.4f}); zero-shot CLIP prompts may need tuning",
            stacklevel=1,
        )
