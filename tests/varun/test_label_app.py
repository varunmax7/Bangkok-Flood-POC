import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from cctv.classifier.embed import embed_new_frames
from cctv.classifier.zeroshot import write_zeroshot
from cctv.labelling import label_app
from cctv.registry import build_registry as br
from tools.fixtures import make_fixtures as mf

LABELLER = "test_labeller"


@pytest.fixture(scope="module", autouse=True)
def _fixtures_and_registry_and_cache():
    mf.main()
    br.build_registry()
    embed_new_frames()
    write_zeroshot()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(label_app, "LABELS_CSV", tmp_path / "labels.csv")
    monkeypatch.setattr(label_app, "ROI_OVERRIDES", tmp_path / "roi_overrides.json")
    return TestClient(label_app.app)


def test_index_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "CCTV Labelling" in r.text


def test_next_frame_serves_only_blurred_archive_paths(client):
    r = client.get("/api/next", params={"labeller": LABELLER})
    assert r.status_code == 200
    body = r.json()
    assert body["frame_url"].startswith("/label_frames/")
    # the mount only ever points at data/cctv/raw -- never thumbs/meta/secrets/raw http urls
    assert label_app.BLURRED_FRAMES_DIR == label_app.Path("data/cctv/raw")
    assert "http://" not in body["frame_url"] and "https://" not in body["frame_url"]


def test_label_post_persists(client):
    next_res = client.get("/api/next", params={"labeller": LABELLER}).json()
    r = client.post(
        "/api/label",
        json={
            "cam_id": next_res["cam_id"],
            "ts_utc": next_res["ts_utc"],
            "sha1": next_res["sha1"],
            "label": "FLOODING",
            "labeller": LABELLER,
        },
    )
    assert r.status_code == 200
    df = pd.read_csv(label_app.LABELS_CSV)
    assert len(df) == 1
    assert df.iloc[0]["sha1"] == next_res["sha1"]
    assert df.iloc[0]["label"] == "FLOODING"


def test_label_post_rejects_invalid_label(client):
    next_res = client.get("/api/next", params={"labeller": LABELLER}).json()
    r = client.post(
        "/api/label",
        json={**{k: next_res[k] for k in ("cam_id", "ts_utc", "sha1")}, "label": "NOT_A_CLASS", "labeller": LABELLER},
    )
    assert r.status_code == 422


def test_relabel_same_frame_overwrites_last_write_wins(client):
    next_res = client.get("/api/next", params={"labeller": LABELLER}).json()
    body = {**{k: next_res[k] for k in ("cam_id", "ts_utc", "sha1")}, "labeller": LABELLER}
    client.post("/api/label", json={**body, "label": "NORMAL"})
    client.post("/api/label", json={**body, "label": "SEVERE_FLOODING"})
    df = pd.read_csv(label_app.LABELS_CSV)
    assert len(df) == 1  # not duplicated
    assert df.iloc[0]["label"] == "SEVERE_FLOODING"


def test_undo_removes_most_recent_label(client):
    # Label frames one at a time (realistic usage) so each /api/next excludes
    # what's already labelled, guaranteeing two distinct frames.
    fr1 = client.get("/api/next", params={"labeller": LABELLER}).json()
    client.post(
        "/api/label",
        json={"cam_id": fr1["cam_id"], "ts_utc": fr1["ts_utc"], "sha1": fr1["sha1"], "label": "NORMAL", "labeller": LABELLER},
    )
    fr2 = client.get("/api/next", params={"labeller": LABELLER}).json()
    assert fr2["sha1"] != fr1["sha1"]
    client.post(
        "/api/label",
        json={"cam_id": fr2["cam_id"], "ts_utc": fr2["ts_utc"], "sha1": fr2["sha1"], "label": "FLOODING", "labeller": LABELLER},
    )

    before = pd.read_csv(label_app.LABELS_CSV)
    assert len(before) == 2

    r = client.post("/api/undo", json={"labeller": LABELLER})
    assert r.status_code == 200
    assert r.json()["removed"]["sha1"] == fr2["sha1"]  # the most recently written one

    after = pd.read_csv(label_app.LABELS_CSV)
    assert len(after) == 1
    assert after.iloc[0]["sha1"] == fr1["sha1"]


def test_undo_with_nothing_to_undo_404s(client):
    r = client.post("/api/undo", json={"labeller": "nobody-has-labelled-anything"})
    assert r.status_code == 404


def test_second_labeller_can_see_frames_already_labelled_by_first(client):
    fr = client.get("/api/next", params={"labeller": "a"}).json()
    client.post(
        "/api/label",
        json={"cam_id": fr["cam_id"], "ts_utc": fr["ts_utc"], "sha1": fr["sha1"], "label": "NORMAL", "labeller": "a"},
    )
    # labeller "a" won't see this sha1 again...
    frames = pd.read_parquet(label_app.FRAMES_PARQUET)
    ok = frames[frames["quality_flag"] == "OK"]
    assert fr["sha1"] in set(ok["sha1"])  # sanity: frame genuinely exists
    pool_a = label_app._candidate_pool("a")
    assert fr["sha1"] not in set(pool_a["sha1"])
    # ...but labeller "b" still can, enabling double-labelling for kappa.
    pool_b = label_app._candidate_pool("b")
    assert fr["sha1"] in set(pool_b["sha1"])


def test_progress_counts_by_label(client):
    fr1 = client.get("/api/next", params={"labeller": LABELLER}).json()
    client.post(
        "/api/label",
        json={"cam_id": fr1["cam_id"], "ts_utc": fr1["ts_utc"], "sha1": fr1["sha1"], "label": "NORMAL", "labeller": LABELLER},
    )
    fr2 = client.get("/api/next", params={"labeller": LABELLER}).json()
    client.post(
        "/api/label",
        json={"cam_id": fr2["cam_id"], "ts_utc": fr2["ts_utc"], "sha1": fr2["sha1"], "label": "NORMAL", "labeller": LABELLER},
    )
    r = client.get("/api/progress", params={"labeller": LABELLER})
    assert r.json() == {"NORMAL": 2}


def test_roi_saved_and_merged_into_registry(client, tmp_path):
    points = [[10, 10], [100, 10], [100, 80], [10, 80]]
    r = client.post("/api/roi", json={"cam_id": "BMAT-0000", "points": points})
    assert r.status_code == 200

    saved = json.loads(label_app.ROI_OVERRIDES.read_text())
    assert saved["BMAT-0000"] == points

    out_path = tmp_path / "cameras_with_roi.geojson"
    fc = br.build_registry(output_path=out_path, roi_overrides_path=label_app.ROI_OVERRIDES)
    cam = next(f for f in fc["features"] if f["properties"]["cam_id"] == "BMAT-0000")
    assert cam["properties"]["road_roi_px"] == points
