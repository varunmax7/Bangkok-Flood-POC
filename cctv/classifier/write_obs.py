"""Writes data/cctv/cctv_obs.parquet — handoff H6 to Rishanth. See docs/VARUN_IMPLEMENTATION.md §6 T53.

Run via `make cctv-classify` (embeds + zero-shot-scores any new frames,
then builds the observation table).
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from pathlib import Path

import pandas as pd
import yaml

FRAMES_PARQUET = Path("data/cctv/cctv_frames.parquet")
ZEROSHOT_CACHE = Path("cctv/classifier/cache/zeroshot_v0.parquet")
PROBE_CHOSEN = Path("cctv/classifier/models/CHOSEN.txt")
THRESHOLDS_PATH = Path("configs/thresholds.yaml")
OUT_PATH = Path("data/cctv/cctv_obs.parquet")

PROB_COLS = ["p_normal", "p_waterlogging", "p_flooding", "p_severe", "p_unusable"]
OUT_COLUMNS = [
    "cam_id",
    "ts_utc",
    "class",
    "p_normal",
    "p_waterlogging",
    "p_flooding",
    "p_severe",
    "p_unusable",
    "class_smoothed",
    "depth_proxy_bin",
    "quality_flag",
    "frame_sha1",
    "model_version",
    "data_class",
    "is_mock",
]


def model_version() -> str:
    # T52 hasn't landed yet (no labelled probe), so this is always clip-zs-v0
    # today; switches automatically once cctv/classifier/models/CHOSEN.txt exists.
    return "clip-probe-v1" if PROBE_CHOSEN.exists() else "clip-zs-v0"


def _depth_proxy_bins() -> dict:
    if not THRESHOLDS_PATH.exists():
        return {}
    return (yaml.safe_load(THRESHOLDS_PATH.read_text()) or {}).get("cctv_depth_proxy_bins_m", {})


def _depth_proxy_bin_for_class(cls: str, bins: dict) -> str | None:
    if cls == "UNUSABLE" or cls not in bins or bins[cls] is None:
        return None
    lo, hi = bins[cls]
    return f"{lo:.2f}-{hi:.2f}" if hi is not None else f"{lo:.2f}-"


def _smoothed_series(df: pd.DataFrame) -> list[str | None]:
    """Majority of the last <=3 USABLE frames per camera, in ts order; ties -> most recent.

    Assumes `df` is sorted by (cam_id, ts_utc) with a plain RangeIndex.
    """
    out: list[str | None] = [None] * len(df)
    for _cam_id, idx in df.groupby("cam_id").groups.items():
        window: deque[str] = deque(maxlen=3)
        for i in idx:
            row_class = df.at[i, "class"]
            if row_class != "UNUSABLE":
                window.append(row_class)
            if not window:
                continue
            counts = Counter(window)
            top = max(counts.values())
            tied = {c for c, n in counts.items() if n == top}
            if len(tied) == 1:
                out[i] = next(iter(tied))
            else:
                for c in reversed(window):
                    if c in tied:
                        out[i] = c
                        break
    return out


def build_cctv_obs(
    frames_parquet: Path = FRAMES_PARQUET,
    zeroshot_cache: Path = ZEROSHOT_CACHE,
    out_path: Path = OUT_PATH,
) -> pd.DataFrame:
    frames = pd.read_parquet(frames_parquet).sort_values(["cam_id", "ts_utc"]).reset_index(drop=True)
    zs = (
        pd.read_parquet(zeroshot_cache)
        if zeroshot_cache.exists()
        else pd.DataFrame(columns=["sha1", *PROB_COLS, "argmax_class"])
    )
    zs = zs.drop_duplicates(subset="sha1").set_index("sha1")

    bins = _depth_proxy_bins()
    version = model_version()

    rows = []
    for _, row in frames.iterrows():
        if row["quality_flag"] == "OK" and row["sha1"] in zs.index:
            zrow = zs.loc[row["sha1"]]
            cls = zrow["argmax_class"]
            probs = {c: float(zrow[c]) for c in PROB_COLS}
        else:
            # not OK, or OK but not embedded yet -> treated as unusable (never invented)
            cls = "UNUSABLE"
            probs = {c: 0.0 for c in PROB_COLS}
            probs["p_unusable"] = 1.0

        rows.append(
            {
                "cam_id": row["cam_id"],
                "ts_utc": row["ts_utc"],
                "class": cls,
                **probs,
                "depth_proxy_bin": _depth_proxy_bin_for_class(cls, bins),
                "quality_flag": row["quality_flag"],
                "frame_sha1": row["sha1"],
                "model_version": version,
                "data_class": "OBSERVED",
                "is_mock": False,
            }
        )

    out = pd.DataFrame(rows)
    out["class_smoothed"] = _smoothed_series(out)
    out = out[OUT_COLUMNS]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(out_path, index=False)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="auto", choices=["auto", "zs", "probe"])
    args = parser.parse_args()

    if args.model == "probe" and not PROBE_CHOSEN.exists():
        raise SystemExit("no probe chosen yet (T52 hasn't run) -- use --model zs/auto")

    # make cctv-classify is the one-shot entry point: embed + score + write.
    from .embed import embed_new_frames
    from .zeroshot import write_zeroshot

    embed_new_frames()
    write_zeroshot()

    df = build_cctv_obs()
    print(f"wrote {len(df)} rows -> {OUT_PATH} (model_version={model_version()})")


if __name__ == "__main__":
    main()
