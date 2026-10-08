import json

import pytest
from fastapi.testclient import TestClient

from dashboard.api.routers import ingest as ingest_module
from dashboard.api.main import app

API_KEY = "test-ingest-key"


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_module, "SEEN_PATH", tmp_path / "seen.txt")
    monkeypatch.setattr(ingest_module, "OBS_DIR", tmp_path / "ingest")
    monkeypatch.setenv("FG_API_KEY_INGEST", API_KEY)
    ingest_module.get_settings.cache_clear()
    yield
    ingest_module.get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)


def _obs(**overrides) -> dict:
    base = {
        "site_id": "BKK-WL-0001",
        "sensor_type": "wl",
        "ts": "2026-01-01T00:00:00Z",
        "value": 1.23,
        "unit": "m",
        "quality": "raw",
    }
    base.update(overrides)
    return base


def test_missing_api_key_401(client):
    r = client.post("/ingest/v1/observations", json=[_obs()])
    assert r.status_code == 401


def test_wrong_api_key_401(client):
    r = client.post("/ingest/v1/observations", json=[_obs()], headers={"X-API-Key": "nope"})
    assert r.status_code == 401


def test_valid_observation_accepted(client):
    r = client.post("/ingest/v1/observations", json=[_obs()], headers={"X-API-Key": API_KEY})
    assert r.status_code == 200
    body = r.json()
    assert body == {"accepted": 1, "rejected": []}

    out_files = list(ingest_module.OBS_DIR.glob("obs_*.jsonl"))
    assert len(out_files) == 1
    stored = json.loads(out_files[0].read_text().splitlines()[0])
    assert stored["site_id"] == "BKK-WL-0001"


@pytest.mark.parametrize(
    "overrides,expected_reason_substr",
    [
        ({"site_id": "NOT-VALID"}, "does not match"),
        ({"sensor_type": "temperature"}, "is not one of"),
        ({"unit": "bananas"}, "is not one of"),
        ({"quality": "bad"}, "is not one of"),
        ({"value": "not-a-number"}, "is not of type"),
        ({"ts": "not-a-timestamp"}, "date-time"),
    ],
)
def test_invalid_observations_rejected_with_reason(client, overrides, expected_reason_substr):
    r = client.post("/ingest/v1/observations", json=[_obs(**overrides)], headers={"X-API-Key": API_KEY})
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] == 0
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["index"] == 0
    assert expected_reason_substr in body["rejected"][0]["reason"]


def test_missing_required_field_rejected(client):
    obs = _obs()
    del obs["value"]
    r = client.post("/ingest/v1/observations", json=[obs], headers={"X-API-Key": API_KEY})
    assert r.json()["accepted"] == 0
    assert "rejected" in r.json()


def test_optional_fields_accepted(client):
    obs = _obs(battery_v=3.7, fw="1.2.0", seq=42, datum="MSL")
    r = client.post("/ingest/v1/observations", json=[obs], headers={"X-API-Key": API_KEY})
    assert r.json() == {"accepted": 1, "rejected": []}


def test_idempotency_duplicate_within_same_batch_rejected(client):
    obs = _obs()
    r = client.post("/ingest/v1/observations", json=[obs, obs], headers={"X-API-Key": API_KEY})
    body = r.json()
    assert body["accepted"] == 1
    assert len(body["rejected"]) == 1
    assert "duplicate" in body["rejected"][0]["reason"]


def test_idempotency_duplicate_across_requests_rejected(client):
    obs = _obs()
    r1 = client.post("/ingest/v1/observations", json=[obs], headers={"X-API-Key": API_KEY})
    assert r1.json()["accepted"] == 1

    r2 = client.post("/ingest/v1/observations", json=[obs], headers={"X-API-Key": API_KEY})
    assert r2.json() == {"accepted": 0, "rejected": [{"index": 0, "reason": "duplicate (site_id+ts+sensor_type already ingested)"}]}


def test_same_site_different_sensor_type_not_duplicate(client):
    obs_a = _obs(sensor_type="wl")
    obs_b = _obs(sensor_type="rain", unit="mm")
    r = client.post("/ingest/v1/observations", json=[obs_a, obs_b], headers={"X-API-Key": API_KEY})
    assert r.json()["accepted"] == 2


def test_partial_rejection_mixed_batch(client):
    good = _obs(site_id="BKK-WL-0001")
    bad = _obs(site_id="INVALID")
    good2 = _obs(site_id="BKK-RN-0002", sensor_type="rain", unit="mm")
    r = client.post("/ingest/v1/observations", json=[good, bad, good2], headers={"X-API-Key": API_KEY})
    body = r.json()
    assert body["accepted"] == 2
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["index"] == 1


def test_batch_over_1000_rejected(client):
    batch = [_obs(site_id=f"BKK-WL-{i:04d}") for i in range(1001)]
    r = client.post("/ingest/v1/observations", json=batch, headers={"X-API-Key": API_KEY})
    assert r.status_code == 422
