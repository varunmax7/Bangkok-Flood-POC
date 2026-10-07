import pytest
from fastapi.testclient import TestClient

from cctv.registry import build_registry as br
from dashboard.api.main import app
from tools.fixtures import make_fixtures as mf

SCENARIO_ID = "MOCK_BKK-S99"


@pytest.fixture(scope="module", autouse=True)
def _fixtures_and_registry():
    mf.main()
    br.build_registry()


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "mode" in body and "versions" in body


def test_config(client):
    r = client.get("/api/config")
    assert r.status_code == 200
    body = r.json()
    assert "depth_bins_m" in body
    assert "cctv_classes" in body


def test_domain(client):
    r = client.get("/api/domain")
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "Feature"
    assert body["crs"] == "EPSG:32647"
    assert body["shape"] == [704, 512]


def test_scenarios_list_and_detail(client):
    r = client.get("/api/scenarios")
    assert r.status_code == 200
    scenarios = r.json()
    assert any(s["scenario_id"] == SCENARIO_ID for s in scenarios)

    r2 = client.get(f"/api/scenarios/{SCENARIO_ID}")
    assert r2.status_code == 200
    assert r2.json()["scenario_id"] == SCENARIO_ID

    r3 = client.get("/api/scenarios/does-not-exist")
    assert r3.status_code == 404


def test_runs_list_never_500s(client):
    # Whether or not T40 has rendered anything into dashboard/static/frames,
    # this must always be a 200 + list, never a 500.
    r = client.get("/api/runs")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_run_frames_404_when_missing(client):
    r = client.get("/api/runs/does-not-exist/frames")
    assert r.status_code == 404


def test_runs_and_frames_once_t40_has_rendered(client):
    """Integration check: render a fixture run (T40), then read it back through T30."""
    from dashboard.render.render_frames import render_vars

    run_id = "MOCK_BKK-S99_M000_lfp_mock-0"
    nc_path = mf.OUT / "MOCK_BKK-S99" / "M000" / "depth.nc"
    render_vars(nc_path, run_id, "hydraulic", ["depth"])

    runs = client.get("/api/runs").json()
    assert any(r["run_id"] == run_id and r["source"] == "hydraulic" for r in runs)

    frames = client.get(f"/api/runs/{run_id}/frames").json()
    assert frames["n_frames"] == 96
    assert frames["frame_url_template"] == f"/frames/hydraulic/{run_id}/depth/{{t:03d}}.png"


def test_run_satellite_gap(client):
    r = client.get("/api/runs/anything/satellite")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert "gap" in body


def test_stations_and_timeseries(client):
    r = client.get("/api/stations")
    assert r.status_code == 200
    fc = r.json()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 8

    r2 = client.get("/api/stations?type=rain")
    assert all(f["properties"]["type"] == "rain" for f in r2.json()["features"])

    station_id = fc["features"][0]["properties"]["station_id"]
    r3 = client.get(f"/api/stations/{station_id}/timeseries")
    assert r3.status_code == 200
    body = r3.json()
    assert len(body["ts"]) == 96
    assert len(body["value"]) == 96

    r4 = client.get("/api/stations/NOPE/timeseries")
    assert r4.status_code == 404


def test_cctv_registry_has_no_url_fields(client):
    r = client.get("/api/cctv")
    assert r.status_code == 200
    fc = r.json()
    assert len(fc["features"]) == 10
    for f in fc["features"]:
        for key, value in f["properties"].items():
            assert "url" not in key.lower()
            if isinstance(value, str):
                assert "http://" not in value.lower()
                assert "https://" not in value.lower()


def test_cctv_observations_gap_before_t53(client):
    r = client.get("/api/cctv/BMAT-0000/observations")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert "gap" in body


def test_observations_for_scenario(client):
    r = client.get(f"/api/observations?scenario_id={SCENARIO_ID}")
    assert r.status_code == 200
    fc = r.json()
    kinds = {f["properties"]["kind"] for f in fc["features"]}
    assert kinds == {"road_flood", "citizen"}
    assert len(fc["features"]) == 8 + 10


def test_observations_gap_for_unknown_scenario(client):
    r = client.get("/api/observations?scenario_id=NOPE")
    assert r.status_code == 200
    body = r.json()
    assert body["features"] == []
    assert "gap" in body


def test_validation_fixture_metrics(client):
    r = client.get(f"/api/validation/{SCENARIO_ID}")
    assert r.status_code == 200
    body = r.json()
    assert body["metrics"]["wet_rmse_m"] == pytest.approx(0.08)


def test_predict_and_ingest_are_501(client):
    assert client.post("/api/predict", json={}).status_code == 501
    assert client.get("/api/predict/anything").status_code == 501
    assert client.post("/ingest/v1/observations", json=[]).status_code == 501
