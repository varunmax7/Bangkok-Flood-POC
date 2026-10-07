import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import xarray as xr
import yaml

from tools.fixtures import make_fixtures as mf

OUT = mf.OUT


def _hash_tree(root: Path) -> dict[str, str]:
    hashes = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            hashes[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes


def test_fixtures_regenerate_byte_identically(tmp_path):
    mf.main()
    first = _hash_tree(OUT)
    first_frames = hashlib.sha256(Path("data/cctv/cctv_frames.parquet").read_bytes()).hexdigest()

    mf.main()
    second = _hash_tree(OUT)
    second_frames = hashlib.sha256(Path("data/cctv/cctv_frames.parquet").read_bytes()).hexdigest()

    assert first == second
    assert first_frames == second_frames


def test_domain_shape_and_crs():
    mf.main()
    domain = yaml.safe_load((OUT / "domain.yaml").read_text())
    assert domain["crs"] == "EPSG:32647"
    assert domain["res_m"] == 20
    assert domain["shape"] == [704, 512]
    assert domain["origin_x"] % 20 == 0
    assert domain["origin_y"] % 20 == 0
    assert domain["is_mock"] is True

    poly = json.loads((OUT / "analysis_polygon.geojson").read_text())
    assert poly["type"] == "FeatureCollection"
    assert poly["features"][0]["geometry"]["type"] == "Polygon"


def test_depth_nc_shape_attrs_coords_and_peak():
    mf.main()
    ds = xr.open_dataset(OUT / "MOCK_BKK-S99" / "M000" / "depth.nc")
    assert ds["depth_m"].shape == (96, 704, 512)
    assert ds["depth_m"].dtype == np.float32

    for key in ("crs", "model_version", "scenario_id", "member_id", "run_id", "data_class"):
        assert key in ds.attrs, key
    assert bool(ds.attrs["is_mock"])
    assert ds.attrs["data_class"] == "SYNTHETIC"

    times = ds["time"].values
    assert np.all(times[1:] > times[:-1])
    assert (times[1] - times[0]) == np.timedelta64(900, "s")

    assert float(ds["depth_m"].isel(time=0).max()) == 0.0
    assert float(ds["depth_m"].isel(time=-1).max()) == 0.0
    peak = float(ds["depth_m"].isel(time=40).max())
    assert abs(peak - 0.8) < 1e-5

    # outside the two pond footprints it must be exactly zero at the peak frame
    frame = ds["depth_m"].isel(time=40).values
    assert float(frame[0, 0]) == 0.0
    assert float(frame[-1, -1]) == 0.0


def test_surrogate_nc_block_average_and_sigma_relation():
    mf.main()
    sur = xr.open_dataset(OUT / "MOCK_BKK-S99" / "surrogate" / "pred.nc")
    assert sur["depth_m"].shape == (96, 352, 256)
    assert sur["sigma_m"].shape == (96, 352, 256)
    assert sur.attrs["surrogate_version"] == "mock-0"
    assert bool(sur.attrs["is_mock"])
    assert not bool(sur.attrs["ood_flag"])

    depth = sur["depth_m"].values
    sigma = sur["sigma_m"].values
    # sigma_m = 0.1 * depth_m + 0.01 (fixture spec), allow for the added noise
    assert np.allclose(sigma, 0.1 * depth + 0.01, atol=1e-6)


def test_scenario_yaml_required_fields():
    mf.main()
    scenario = yaml.safe_load((OUT / "MOCK_BKK-S99" / "scenario.yaml").read_text())
    for key in (
        "scenario_id",
        "name",
        "scenario_type",
        "split",
        "event_group_id",
        "confidence",
        "data_class_summary",
        "is_mock",
    ):
        assert key in scenario, key
    assert scenario["split"] == "TRAIN"
    assert scenario["scenario_type"] == "SYNTHETIC"
    assert scenario["is_mock"] is True


def test_observations_counts_and_schema():
    mf.main()
    obs_dir = OUT / "MOCK_BKK-S99" / "observations"

    road = json.loads((obs_dir / "road_flood_points.geojson").read_text())
    assert len(road["features"]) == 8
    for f in road["features"]:
        for key in ("point_id", "ts_utc", "depth_cm", "source_ref", "data_class"):
            assert key in f["properties"]

    citizen = json.loads((obs_dir / "citizen_reports.geojson").read_text())
    assert len(citizen["features"]) == 10

    sat = pd.read_csv(obs_dir / "sat_acquisitions.csv")
    assert len(sat) == 1
    assert bool(sat.iloc[0]["usable"])

    with rasterio.open(obs_dir / "sat_floodmask_S1A_20260925T2300Z.tif") as src:
        arr = src.read(1)
        assert arr.shape == (704, 512)
        assert set(np.unique(arr).tolist()) <= {0, 1, 255}
        assert str(src.crs) == "EPSG:32647"


def test_cameras_geojson():
    mf.main()
    fc = json.loads((OUT / "cameras.geojson").read_text())
    assert fc["metadata"]["is_mock"] is True
    assert len(fc["features"]) == 10
    cam_ids = [f["properties"]["cam_id"] for f in fc["features"]]
    assert len(cam_ids) == len(set(cam_ids))  # unique
    required = {
        "cam_id",
        "source",
        "source_cam_ref",
        "name_th",
        "name_en",
        "lon",
        "lat",
        "loc_method",
        "loc_accuracy_m",
        "heading_deg",
        "road_name",
        "refresh_s",
        "calib_refs",
        "priority",
        "in_domain",
        "nearest_dds_point_id",
        "dist_dds_m",
        "road_roi_px",
        "status",
    }
    for f in fc["features"]:
        assert required <= set(f["properties"].keys())
        # never leak a snapshot URL into the registry
        for v in f["properties"].values():
            assert not (isinstance(v, str) and v.startswith("http"))


def test_cctv_frames_parquet_schema_and_counts():
    mf.main()
    df = pd.read_parquet("data/cctv/cctv_frames.parquet")
    assert len(df) == 10 * 30
    assert df["cam_id"].nunique() == 10
    expected_cols = {
        "cam_id",
        "ts_utc",
        "http_status",
        "path",
        "sha1",
        "phash",
        "width",
        "height",
        "bytes",
        "quality_flag",
        "sat_mean",
        "lap_var",
    }
    assert expected_cols <= set(df.columns)
    assert (df["quality_flag"] == "OK").all()
    assert (df["width"] == 640).all() and (df["height"] == 360).all()
    assert df.duplicated(subset=["cam_id", "ts_utc"]).sum() == 0

    for p in df["path"].sample(min(5, len(df)), random_state=0):
        assert Path(p).exists()


def test_stations_counts_and_schema():
    mf.main()
    st = pd.read_parquet(OUT / "stations" / "stations.parquet")
    ts = pd.read_parquet(OUT / "stations" / "timeseries.parquet")
    assert (st["type"] == "rain").sum() == 5
    assert (st["type"] == "level").sum() == 3
    assert len(ts) == 8 * 96
    assert set(ts["station_id"]) == set(st["station_id"])


def test_metrics_json():
    mf.main()
    metrics = json.loads((OUT / "MOCK_metrics.json").read_text())
    assert metrics["is_mock"] is True
    assert "wet_rmse_m" in metrics
