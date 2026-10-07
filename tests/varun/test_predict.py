import time

import pytest
from fastapi.testclient import TestClient

from cctv.registry import build_registry as br
from dashboard.api import jobs
from dashboard.api.main import app
from tools.fixtures import make_fixtures as mf

VALID_PARAMS = {
    "base_scenario_id": "MOCK_BKK-S99",
    "rain_scale": 1.2,
    "duration_stretch": 1.0,
    "canal_stage_anom_m": 0.1,
    "outfall_stage_offset_m": 0.1,
    "drain_multiplier": 1.0,
}


@pytest.fixture(scope="module", autouse=True)
def _fixtures_and_registry():
    mf.main()
    br.build_registry()


@pytest.fixture(autouse=True)
def _clear_jobs():
    jobs.clear_jobs()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.parametrize(
    "field,value",
    [
        ("rain_scale", 0.4),
        ("rain_scale", 1.9),
        ("duration_stretch", 0.4),
        ("duration_stretch", 2.1),
        ("canal_stage_anom_m", -0.4),
        ("canal_stage_anom_m", 0.9),
        ("outfall_stage_offset_m", -0.1),
        ("outfall_stage_offset_m", 0.7),
        ("drain_multiplier", 0.2),
        ("drain_multiplier", 1.3),
    ],
)
def test_out_of_range_params_422(client, field, value):
    body = {**VALID_PARAMS, field: value}
    r = client.post("/api/predict", json=body)
    assert r.status_code == 422


def test_valid_params_runs_in_mock_mode_end_to_end(client):
    r = client.post("/api/predict", json=VALID_PARAMS)
    assert r.status_code == 200
    body = r.json()
    assert body["is_mock"] is True
    assert body["status"] in ("PARTIAL", "DONE")
    assert body["run_id"].startswith(VALID_PARAMS["base_scenario_id"])
    assert "_sur_" in body["run_id"]
    assert "manifest_url" in body


def test_first_frames_available_within_5_seconds(client):
    t0 = time.time()
    r = client.post("/api/predict", json=VALID_PARAMS)
    elapsed = time.time() - t0
    assert r.status_code == 200
    assert elapsed < 5.0, f"took {elapsed:.2f}s to return first frames (target <= 5s)"


def test_partial_then_done_via_polling(client):
    r = client.post("/api/predict", json=VALID_PARAMS)
    run_id = r.json()["run_id"]
    first_status = r.json()["status"]

    # Poll until DONE (background task finishes rendering the rest).
    deadline = time.time() + 10
    status = first_status
    while status != "DONE" and time.time() < deadline:
        time.sleep(0.1)
        poll = client.get(f"/api/predict/{run_id}")
        assert poll.status_code == 200
        status = poll.json()["status"]
    assert status == "DONE"


def test_same_params_are_cached_and_instant(client):
    first = client.post("/api/predict", json=VALID_PARAMS)
    run_id = first.json()["run_id"]

    # wait for the background render to finish so the job is DONE
    deadline = time.time() + 10
    while client.get(f"/api/predict/{run_id}").json()["status"] != "DONE" and time.time() < deadline:
        time.sleep(0.1)

    t0 = time.time()
    second = client.post("/api/predict", json=VALID_PARAMS)
    elapsed = time.time() - t0
    assert second.json()["run_id"] == run_id
    assert second.json()["status"] == "DONE"
    assert elapsed < 0.5  # cache hit -- no re-render


def test_different_params_get_different_run_ids(client):
    a = client.post("/api/predict", json=VALID_PARAMS).json()
    b = client.post("/api/predict", json={**VALID_PARAMS, "rain_scale": 1.3}).json()
    assert a["run_id"] != b["run_id"]


def test_ood_flag_true_for_extreme_params_false_for_moderate(client):
    extreme = {
        "base_scenario_id": "MOCK_BKK-S99",
        "rain_scale": 1.8,
        "duration_stretch": 2.0,
        "canal_stage_anom_m": 0.8,
        "outfall_stage_offset_m": 0.6,
        "drain_multiplier": 1.2,
    }
    r_extreme = client.post("/api/predict", json=extreme)
    r_moderate = client.post("/api/predict", json=VALID_PARAMS)
    assert r_extreme.json()["ood_flag"] is True
    assert r_moderate.json()["ood_flag"] is False


def test_unknown_run_id_404s(client):
    r = client.get("/api/predict/does-not-exist")
    assert r.status_code == 404
