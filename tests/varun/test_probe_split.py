"""Tests for cctv/classifier/probe.py. See docs/VARUN_IMPLEMENTATION.md §6 T52.

No real HU5 labels exist yet, so every test builds its own small synthetic
labels.csv + embedding cache (clearly-separable clusters, not real CLIP
output) to exercise the split/CV/report logic deterministically.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cctv.classifier import probe

CLASSES = probe.TRAIN_CLASSES
EMB_DIM = 8
RNG = np.random.RandomState(0)

_CENTERS = {cls: np.eye(EMB_DIM)[i] * 3.0 for i, cls in enumerate(CLASSES)}


def _embedding_for(label: str) -> list[float]:
    return (_CENTERS[label] + RNG.normal(0, 0.05, EMB_DIM)).astype("float32").tolist()


def _write_labels_csv(path, rows, labeller="a"):
    df = pd.DataFrame(
        [
            {
                "cam_id": r["cam_id"],
                "ts_utc": f"2026-09-25T10:{i:02d}:00Z",
                "sha1": r["sha1"],
                "label": r["label"],
                "labeller": r.get("labeller", labeller),
                "labelled_utc": "2026-09-26T00:00:00Z",
            }
            for i, r in enumerate(rows)
        ]
    )
    df.to_csv(path, index=False)
    return df


def _write_embeddings_cache(path, sha1_to_label: dict[str, str], cam_of: dict[str, str]):
    rows = [
        {"cam_id": cam_of[sha1], "ts_utc": "2026-09-25T10:00:00Z", "sha1": sha1, "emb": _embedding_for(label)}
        for sha1, label in sha1_to_label.items()
    ]
    pd.DataFrame(rows).to_parquet(path, index=False)


def _write_zeroshot_cache(path, sha1_to_argmax: dict[str, str]):
    rows = [{"sha1": sha1, "cam_id": "x", "ts_utc": "t", "argmax_class": cls} for sha1, cls in sha1_to_argmax.items()]
    pd.DataFrame(rows).to_parquet(path, index=False)


def _synthetic_dataset(n_cams: int = 6, per_cam: int = 7, thin_class: str | None = None):
    """Returns (labels_rows, sha1_to_label, cam_of) balanced across n_cams
    cameras and CLASSES, optionally thinning one class to < 10 total."""
    rows, sha1_to_label, cam_of = [], {}, {}
    counter = 0
    for cam_i in range(n_cams):
        cam_id = f"CAM-{cam_i:02d}"
        for j in range(per_cam):
            label = CLASSES[(cam_i * per_cam + j) % len(CLASSES)]
            if thin_class and label == thin_class and counter % 3 != 0:
                label = CLASSES[0]  # keep thin_class rare without shrinking the dataset
            sha1 = f"sha-{counter:04d}"
            rows.append({"cam_id": cam_id, "sha1": sha1, "label": label})
            sha1_to_label[sha1] = label
            cam_of[sha1] = cam_id
            counter += 1
    return rows, sha1_to_label, cam_of


# ---------------------------------------------------------------------------
# grouped_split
# ---------------------------------------------------------------------------


def test_grouped_split_is_disjoint_by_camera():
    rows, sha1_to_label, cam_of = _synthetic_dataset()
    frame = pd.DataFrame(
        [{"cam_id": cam_of[s], "sha1": s, "label": lbl, "emb": _embedding_for(lbl)} for s, lbl in sha1_to_label.items()]
    )
    train, test = probe.grouped_split(frame)
    assert not train.empty and not test.empty
    assert set(train["cam_id"]).isdisjoint(set(test["cam_id"]))


# ---------------------------------------------------------------------------
# inter-rater kappa
# ---------------------------------------------------------------------------


def test_inter_rater_kappa_perfect_agreement():
    primary = pd.DataFrame({"sha1": ["a", "b", "c"], "label": ["NORMAL", "FLOODING", "WATERLOGGING"]})
    secondary = pd.DataFrame({"sha1": ["a", "b", "c"], "label": ["NORMAL", "FLOODING", "WATERLOGGING"]})
    assert probe.inter_rater_kappa(primary, secondary) == pytest.approx(1.0)


def test_inter_rater_kappa_none_without_overlap():
    primary = pd.DataFrame({"sha1": ["a"], "label": ["NORMAL"]})
    secondary = pd.DataFrame(columns=["sha1", "label"])
    assert probe.inter_rater_kappa(primary, secondary) is None


# ---------------------------------------------------------------------------
# run(): insufficient-labels path
# ---------------------------------------------------------------------------


def test_run_reports_insufficient_labels_explicitly(tmp_path):
    labels_csv = tmp_path / "labels.csv"
    rows = [{"cam_id": "CAM-00", "sha1": f"sha-{i}", "label": "NORMAL"} for i in range(5)]
    _write_labels_csv(labels_csv, rows)

    result = probe.run(
        labels_csv=labels_csv,
        embeddings_cache=tmp_path / "missing_embeddings.parquet",
        zeroshot_cache=tmp_path / "missing_zeroshot.parquet",
        model_path=tmp_path / "models" / "probe_v1.joblib",
        chosen_path=tmp_path / "models" / "CHOSEN.txt",
        report_path=tmp_path / "report.md",
    )

    assert result["status"] == "insufficient_labels"
    assert result["n_total"] == 0  # no embeddings cache -> nothing joins
    report_text = (tmp_path / "report.md").read_text()
    assert "insufficient labels: 0" in report_text
    assert not (tmp_path / "models" / "CHOSEN.txt").exists()


# ---------------------------------------------------------------------------
# run(): full pipeline, enough labels across enough cameras
# ---------------------------------------------------------------------------


def test_run_trains_and_ships_v1_when_it_beats_a_weak_v0(tmp_path):
    rows, sha1_to_label, cam_of = _synthetic_dataset(n_cams=6, per_cam=7, thin_class="SEVERE_FLOODING")
    labels_csv = tmp_path / "labels.csv"
    _write_labels_csv(labels_csv, rows)

    embeddings_cache = tmp_path / "embeddings.parquet"
    _write_embeddings_cache(embeddings_cache, sha1_to_label, cam_of)

    # deliberately bad v0: every frame "predicted" as the same wrong class
    zeroshot_cache = tmp_path / "zeroshot.parquet"
    wrong_class = CLASSES[1]
    _write_zeroshot_cache(zeroshot_cache, {s: wrong_class for s in sha1_to_label})

    model_path = tmp_path / "models" / "probe_v1.joblib"
    chosen_path = tmp_path / "models" / "CHOSEN.txt"
    report_path = tmp_path / "report.md"

    result = probe.run(
        labels_csv=labels_csv,
        embeddings_cache=embeddings_cache,
        zeroshot_cache=zeroshot_cache,
        model_path=model_path,
        chosen_path=chosen_path,
        report_path=report_path,
    )

    assert result["status"] == "trained"
    assert result["v1"]["macro_f1"] > result["v0"]["macro_f1"]
    assert result["shipped"] == "v1"
    assert model_path.exists()
    assert chosen_path.read_text().strip() == "probe_v1"
    assert result["three_class"] is not None  # SEVERE_FLOODING was thinned below 10

    report_text = report_path.read_text()
    assert "Shipped model: v1" in report_text
    assert "3-class variant" in report_text


def test_run_does_not_ship_when_v0_already_beats_v1(tmp_path, monkeypatch):
    rows, sha1_to_label, cam_of = _synthetic_dataset(n_cams=6, per_cam=7)
    labels_csv = tmp_path / "labels.csv"
    _write_labels_csv(labels_csv, rows)

    embeddings_cache = tmp_path / "embeddings.parquet"
    _write_embeddings_cache(embeddings_cache, sha1_to_label, cam_of)
    zeroshot_cache = tmp_path / "zeroshot.parquet"
    _write_zeroshot_cache(zeroshot_cache, {s: lbl for s, lbl in sha1_to_label.items()})  # perfect v0

    model_path = tmp_path / "models" / "probe_v1.joblib"
    chosen_path = tmp_path / "models" / "CHOSEN.txt"

    # force v1 to look worse than a perfect v0, without depending on exactly
    # how well a real classifier happens to score on clean synthetic clusters
    class _AlwaysWrong:
        def predict(self, X):
            wrong = CLASSES[1]
            return np.array([wrong] * len(X))

    monkeypatch.setattr(probe, "train_probe", lambda train, c: _AlwaysWrong())

    result = probe.run(
        labels_csv=labels_csv,
        embeddings_cache=embeddings_cache,
        zeroshot_cache=zeroshot_cache,
        model_path=model_path,
        chosen_path=chosen_path,
        report_path=tmp_path / "report.md",
    )

    assert result["shipped"] == "v0"
    assert not model_path.exists()
    assert not chosen_path.exists()
