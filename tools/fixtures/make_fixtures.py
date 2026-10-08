"""Deterministic mock fixtures for Varun's lane (T01).

See docs/VARUN_IMPLEMENTATION.md §6 T01 for the full spec. Run via
`make fixtures` (-> `python -m tools.fixtures.make_fixtures`).

All artefacts are seeded (SEED=42) and MOCK_-prefixed / is_mock: true so
downstream cards can run before any teammate handoff lands.

[DATA GAP] The parent docs this plan cites (BANGKOK_FLOOD_POC_REQUIREMENTS_
AND_WORKFLOW.md, SCENARIO_SCHEMA.md, TEAM_TASK_BOARD.md) are not present in
this repo, so a few field lists below (citizen_reports schema, scenario.yaml
category taxonomy, metrics.json key names) are reconstructed only from
cross-references inside VARUN_IMPLEMENTATION.md itself and flagged
[ASSUMPTION] at the point of use. See docs/assumptions.md and
docs/data_gaps.md.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import imagehash
import numpy as np
import pandas as pd
import rasterio
import rasterio.transform
import xarray as xr
import yaml
from PIL import Image, ImageDraw
from pyproj import Transformer
from shapely.geometry import box, mapping

SEED = 42
OUT = Path("tools/fixtures/out")

BBOX_4326 = (100.535, 13.775, 100.630, 13.905)  # lon_min, lat_min, lon_max, lat_max
RES_M = 20
SHAPE_YX = (704, 512)  # y, x  (height_m / RES_M, width_m / RES_M)
T0_UTC = datetime(2026, 9, 25, 0, 0, 0, tzinfo=timezone.utc)
DT_S = 900
N_STEPS = 96
PEAK_T_IDX = 40
PEAK_DEPTH_M = 0.8

SCENARIO_ID = "BKK-S99"
MEMBER_ID = "M000"
RUN_ID = f"MOCK_{SCENARIO_ID}_{MEMBER_ID}_lfp_mock-0"

# Two fixed pond centres in grid-index space (row, col, sigma_cells).
POND_CENTERS = [(200.0, 150.0, 25.0), (480.0, 340.0, 30.0)]


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _domain_origin() -> tuple[float, float]:
    tf = Transformer.from_crs(4326, 32647, always_xy=True)
    x0, y0 = tf.transform(BBOX_4326[0], BBOX_4326[1])
    ox = float(np.floor(x0 / RES_M) * RES_M)
    oy = float(np.floor(y0 / RES_M) * RES_M)
    return ox, oy


def _amplitude_curve() -> np.ndarray:
    """Triangular rise-and-recede pulse, 0 at t=0 and t=N-1, peak at PEAK_T_IDX."""
    t = np.arange(N_STEPS, dtype=np.float64)
    up = t / PEAK_T_IDX
    down = 1.0 - (t - PEAK_T_IDX) / (N_STEPS - 1 - PEAK_T_IDX)
    frac = np.clip(np.where(t <= PEAK_T_IDX, up, down), 0.0, 1.0)
    return PEAK_DEPTH_M * frac


def _pond_field(ny: int, nx: int) -> np.ndarray:
    yy, xx = np.mgrid[0:ny, 0:nx]
    field = np.zeros((ny, nx), dtype=np.float64)
    for cy, cx, sigma in POND_CENTERS:
        g = np.exp(-(((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * sigma**2)))
        field = np.maximum(field, g)
    field[field < 1e-2] = 0.0  # hard zero outside the pond footprint
    return field


def _write_fc(path: Path, features: list[dict], is_mock: bool = True) -> None:
    # [ASSUMPTION] GeoJSON has no standard top-level "metadata" key; T11 calls
    # for "is_mock: true in the FeatureCollection metadata" without defining
    # the key name (SCENARIO_SCHEMA.md unavailable), so it is set both at the
    # FeatureCollection level and on every feature for robustness.
    fc = {
        "type": "FeatureCollection",
        "metadata": {"is_mock": is_mock},
        "features": features,
    }
    path.write_text(json.dumps(fc, indent=1))


def make_domain() -> dict:
    real = Path("configs/domain.yaml")
    if real.exists():
        domain = yaml.safe_load(real.read_text())
    else:
        ox, oy = _domain_origin()
        ny, nx = SHAPE_YX
        domain = {
            "crs": "EPSG:32647",
            "res_m": RES_M,
            "shape": [ny, nx],
            "origin_x": ox,
            "origin_y": oy,
            "width_m": nx * RES_M,
            "height_m": ny * RES_M,
            "datum_offset_m": 0.0,
            "is_mock": True,
        }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "domain.yaml").write_text(yaml.safe_dump(domain, sort_keys=False))

    poly = mapping(box(*BBOX_4326))
    _write_fc(
        OUT / "analysis_polygon.geojson",
        [{"type": "Feature", "properties": {"is_mock": True}, "geometry": poly}],
    )
    return domain


def make_depth_nc(domain: dict) -> tuple[xr.Dataset, Path]:
    ny, nx = SHAPE_YX
    ox, oy = domain["origin_x"], domain["origin_y"]
    x = ox + (np.arange(nx) + 0.5) * RES_M
    y = oy + (np.arange(ny) + 0.5) * RES_M
    times = np.array(
        [np.datetime64(T0_UTC.replace(tzinfo=None)) + np.timedelta64(i * DT_S, "s") for i in range(N_STEPS)]
    )

    amp = _amplitude_curve()
    pond = _pond_field(ny, nx)
    depth = (amp[:, None, None] * pond[None, :, :]).astype("float32")

    ds = xr.Dataset(
        {"depth_m": (("time", "y", "x"), depth)},
        coords={"time": times, "y": y, "x": x},
        attrs={
            "crs": "EPSG:32647",
            "model_version": "mock-0",
            "scenario_id": f"MOCK_{SCENARIO_ID}",  # matches scenario.yaml's scenario_id, not the bare SCENARIO_ID
            "member_id": MEMBER_ID,
            "run_id": RUN_ID,
            "data_class": "SYNTHETIC",
            "is_mock": 1,  # netCDF attrs can't be bool; readers do bool(attrs["is_mock"])
        },
    )
    out_dir = OUT / "MOCK_BKK-S99" / "M000"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "depth.nc"
    path.unlink(missing_ok=True)
    ds.to_netcdf(path)
    return ds, path


def make_surrogate_nc(hydraulic_ds: xr.Dataset) -> Path:
    depth = hydraulic_ds["depth_m"].values  # (n, ny, nx)
    n, ny, nx = depth.shape
    ny2, nx2 = ny // 2, nx // 2
    block = depth.reshape(n, ny2, 2, nx2, 2).mean(axis=(2, 4))

    rng = np.random.RandomState(SEED + 1)
    noise = rng.normal(0.0, 0.01, size=block.shape)
    depth_sur = np.clip(block + noise, 0.0, None).astype("float32")
    sigma_sur = (0.1 * depth_sur + 0.01).astype("float32")

    x2 = hydraulic_ds["x"].values.reshape(nx2, 2).mean(axis=1)
    y2 = hydraulic_ds["y"].values.reshape(ny2, 2).mean(axis=1)

    ds = xr.Dataset(
        {
            "depth_m": (("time", "y", "x"), depth_sur),
            "sigma_m": (("time", "y", "x"), sigma_sur),
        },
        coords={"time": hydraulic_ds["time"].values, "y": y2, "x": x2},
        attrs={
            "crs": "EPSG:32647",
            "surrogate_version": "mock-0",
            "scenario_id": f"MOCK_{SCENARIO_ID}",  # matches scenario.yaml's scenario_id, not the bare SCENARIO_ID
            "member_id": MEMBER_ID,
            "run_id": f"MOCK_{SCENARIO_ID}_{MEMBER_ID}_sur_mock-0",
            "data_class": "SYNTHETIC",
            "ood_flag": 0,  # netCDF attrs can't be bool; readers do bool(attrs["ood_flag"])
            "is_mock": 1,
        },
    )
    out_dir = OUT / "MOCK_BKK-S99" / "surrogate"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "pred.nc"
    path.unlink(missing_ok=True)
    ds.to_netcdf(path)
    return path


def make_scenario_yaml() -> dict:
    scenario = {
        "scenario_id": f"MOCK_{SCENARIO_ID}",
        "name": "Mock synthetic scenario (T01 fixture)",
        "scenario_type": "SYNTHETIC",
        "split": "TRAIN",
        "event_group_id": "MOCK-EVENT-01",
        "confidence": 1.0,
        "data_class_summary": "SYNTHETIC",
        # [ASSUMPTION] category taxonomy not available (SCENARIO_SCHEMA.md missing)
        "categories": ["pluvial"],
        "is_mock": True,
    }
    out_dir = OUT / "MOCK_BKK-S99"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "scenario.yaml").write_text(yaml.safe_dump(scenario, sort_keys=False))
    return scenario


def make_observations(domain: dict) -> None:
    rng = np.random.RandomState(SEED + 2)
    lon_min, lat_min, lon_max, lat_max = BBOX_4326
    out_dir = OUT / "MOCK_BKK-S99" / "observations"
    out_dir.mkdir(parents=True, exist_ok=True)

    # road_flood_points.geojson (8 points) — fields per §5 cited in T21.
    feats = []
    for i in range(8):
        ts = T0_UTC + timedelta(seconds=int(rng.uniform(0, N_STEPS * DT_S)))
        feats.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(rng.uniform(lon_min, lon_max)), float(rng.uniform(lat_min, lat_max))],
                },
                "properties": {
                    "point_id": f"MOCK-RFP-{i:03d}",
                    "road_name": f"Mock Road {i}",
                    "district": "Mock District",
                    "ts_utc": _iso(ts),
                    "depth_cm": round(float(rng.uniform(5, 40)), 1),
                    "lane": "inbound" if i % 2 == 0 else "outbound",
                    "source_ref": "MOCK_FIXTURE",
                    "data_class": "SYNTHETIC",
                    "location_method": "MOCK",
                    "loc_accuracy_m": 10.0,
                    "is_mock": True,
                },
            }
        )
    _write_fc(out_dir / "road_flood_points.geojson", feats)

    # citizen_reports.geojson (10 points)
    # [ASSUMPTION] exact schema not available; fields chosen to mirror the
    # road_flood_points contract since both feed the same observations layer.
    feats = []
    for i in range(10):
        ts = T0_UTC + timedelta(seconds=int(rng.uniform(0, N_STEPS * DT_S)))
        feats.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(rng.uniform(lon_min, lon_max)), float(rng.uniform(lat_min, lat_max))],
                },
                "properties": {
                    "report_id": f"MOCK-CIT-{i:03d}",
                    "ts_utc": _iso(ts),
                    "depth_cm": round(float(rng.uniform(0, 50)), 1),
                    "description": "Mock citizen report (fixture)",
                    "source_ref": "MOCK_FIXTURE",
                    "data_class": "SYNTHETIC",
                    "is_mock": True,
                },
            }
        )
    _write_fc(out_dir / "citizen_reports.geojson", feats)

    # sat_acquisitions.csv (1 usable row)
    peak_time = T0_UTC + timedelta(seconds=PEAK_T_IDX * DT_S)
    acq_time = T0_UTC + timedelta(hours=23)
    hours_from_peak = (acq_time - peak_time).total_seconds() / 3600.0
    mask_name = "sat_floodmask_S1A_20260925T2300Z.tif"
    pd.DataFrame(
        [
            {
                "sensor": "S1A",
                "ts_utc": _iso(acq_time),
                "hours_from_peak": round(hours_from_peak, 2),
                "usable": True,
                "mask_path": mask_name,
                "is_mock": True,
            }
        ]
    ).to_csv(out_dir / "sat_acquisitions.csv", index=False)

    # sat_floodmask_*.tif on the 20 m grid: values in {0, 1, 255}
    ny, nx = SHAPE_YX
    rng2 = np.random.RandomState(SEED + 3)
    pond = _pond_field(ny, nx)
    mask = np.zeros((ny, nx), dtype=np.uint8)
    mask[pond > 0.3] = 1
    mask[rng2.random((ny, nx)) < 0.01] = 255  # sparse nodata speckle
    ox, oy = domain["origin_x"], domain["origin_y"]
    transform = rasterio.transform.from_origin(ox, oy + ny * RES_M, RES_M, RES_M)
    with rasterio.open(
        out_dir / mask_name,
        "w",
        driver="GTiff",
        height=ny,
        width=nx,
        count=1,
        dtype="uint8",
        crs="EPSG:32647",
        transform=transform,
        nodata=255,
    ) as dst:
        dst.write(np.flipud(mask), 1)  # row 0 = north, matching from_origin(north-top)


def make_cameras() -> list[str]:
    rng = np.random.RandomState(SEED + 4)
    lon_min, lat_min, lon_max, lat_max = BBOX_4326
    sources = ["BMAT", "ITIC", "LNGD"]
    feats = []
    cam_ids = []
    for i in range(10):
        src = sources[i % len(sources)]
        cam_id = f"{src}-{i:04d}"
        cam_ids.append(cam_id)
        lon = float(rng.uniform(lon_min, lon_max))
        lat = float(rng.uniform(lat_min, lat_max))
        feats.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "cam_id": cam_id,
                    "source": src,
                    "source_cam_ref": f"mock-ref-{i:04d}",
                    "name_th": f"กล้องจำลอง {i}",
                    "name_en": f"Mock Camera {i}",
                    "lon": lon,
                    "lat": lat,
                    "loc_method": "MOCK",
                    "loc_accuracy_m": 15.0,
                    "heading_deg": round(float(rng.uniform(0, 360)), 1),
                    "road_name": f"Mock Road {i}",
                    "refresh_s": 120,
                    "calib_refs": None,
                    "priority": int(rng.randint(1, 4)),
                    "in_domain": True,
                    "nearest_dds_point_id": None,
                    "dist_dds_m": None,
                    "road_roi_px": None,
                    "status": "ACTIVE",
                    "is_mock": True,
                },
            }
        )
    _write_fc(OUT / "cameras.geojson", feats)
    return cam_ids


def _synthetic_frame(frame_idx: int, is_wet: bool) -> Image.Image:
    w, h = 640, 360
    img = Image.new("RGB", (w, h), (120, 120, 120))
    draw = ImageDraw.Draw(img)
    for lane_x in (w // 3, 2 * w // 3):
        for y in range(0, h, 20):
            draw.rectangle([lane_x - 3, y, lane_x + 3, y + 10], fill=(230, 230, 230))
    if is_wet:
        frac = frame_idx / 29.0
        water_h = int(h * 0.15 * frac)
        if water_h > 0:
            draw.rectangle([0, h - water_h, w, h], fill=(40, 90, 200))
    return img


def make_cctv_frames(cam_ids: list[str]) -> pd.DataFrame:
    raw_root = Path("data/cctv/raw")
    thumb_root = Path("data/cctv/thumbs")
    wet_cams = set(cam_ids[:5])
    day = T0_UTC
    yyyymmdd = day.strftime("%Y%m%d")
    rows = []
    for cam_id in cam_ids:
        is_wet = cam_id in wet_cams
        for frame_idx in range(30):
            ts = day + timedelta(seconds=frame_idx * 120)
            ts_str = ts.strftime("%Y%m%dT%H%M%SZ")
            fname = f"{cam_id}_{ts_str}.jpg"

            img = _synthetic_frame(frame_idx, is_wet)
            raw_dir = raw_root / cam_id / yyyymmdd
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_path = raw_dir / fname
            img.save(raw_path, "JPEG", quality=85)
            raw_bytes = raw_path.read_bytes()

            thumb = img.copy()
            thumb.thumbnail((320, 320 * img.height // img.width))
            thumb_dir = thumb_root / cam_id / yyyymmdd
            thumb_dir.mkdir(parents=True, exist_ok=True)
            thumb.save(thumb_dir / fname, "JPEG", quality=85)

            sha1 = hashlib.sha1(raw_bytes).hexdigest()
            phash = str(imagehash.phash(img))
            gray = np.asarray(img.convert("L"))
            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            hsv = np.asarray(img.convert("HSV"))
            sat_mean = float(hsv[:, :, 1].mean())

            rows.append(
                {
                    "cam_id": cam_id,
                    "ts_utc": _iso(ts),
                    "http_status": 200,
                    "path": str(raw_path),
                    "sha1": sha1,
                    "phash": phash,
                    "width": img.width,
                    "height": img.height,
                    "bytes": len(raw_bytes),
                    "quality_flag": "OK",
                    "sat_mean": sat_mean,
                    "lap_var": lap_var,
                }
            )
    df = pd.DataFrame(rows)
    Path("data/cctv").mkdir(parents=True, exist_ok=True)
    df.to_parquet("data/cctv/cctv_frames.parquet", index=False)
    return df


def make_stations() -> None:
    rng = np.random.RandomState(SEED + 6)
    lon_min, lat_min, lon_max, lat_max = BBOX_4326
    stations = []
    for i in range(5):
        stations.append(
            {
                "station_id": f"MOCK-RN-{i:02d}",
                "type": "rain",
                "name": f"Mock Rain Gauge {i}",
                "lon": float(rng.uniform(lon_min, lon_max)),
                "lat": float(rng.uniform(lat_min, lat_max)),
                "source": "MOCK_FIXTURE",
            }
        )
    for i in range(3):
        stations.append(
            {
                "station_id": f"MOCK-LV-{i:02d}",
                "type": "level",
                "name": f"Mock Level Gauge {i}",
                "lon": float(rng.uniform(lon_min, lon_max)),
                "lat": float(rng.uniform(lat_min, lat_max)),
                "source": "MOCK_FIXTURE",
            }
        )
    stations_df = pd.DataFrame(stations)

    amp = _amplitude_curve()
    times = [T0_UTC + timedelta(seconds=i * DT_S) for i in range(N_STEPS)]
    rows = []
    for s in stations:
        if s["type"] == "rain":
            base = rng.uniform(0, 2, size=N_STEPS)
            rain = base + (amp / PEAK_DEPTH_M) * rng.uniform(5, 15)
            for t, v in zip(times, rain):
                rows.append(
                    {
                        "station_id": s["station_id"],
                        "ts_utc": _iso(t),
                        "value": round(float(max(v, 0.0)), 2),
                        "unit": "mm",
                        "data_class": "SYNTHETIC",
                    }
                )
        else:
            base = 1.0 + amp * 0.5
            noise = rng.normal(0.0, 0.02, size=N_STEPS)
            for t, v in zip(times, base + noise):
                rows.append(
                    {
                        "station_id": s["station_id"],
                        "ts_utc": _iso(t),
                        "value": round(float(v), 3),
                        "unit": "m",
                        "data_class": "SYNTHETIC",
                    }
                )
    timeseries_df = pd.DataFrame(rows)

    out_dir = OUT / "stations"
    out_dir.mkdir(parents=True, exist_ok=True)
    stations_df.to_parquet(out_dir / "stations.parquet", index=False)
    timeseries_df.to_parquet(out_dir / "timeseries.parquet", index=False)


def make_metrics() -> None:
    # [ASSUMPTION] exact §17.10 key names not available (parent requirements
    # doc missing); using the metric names VARUN_IMPLEMENTATION.md's T70
    # MetricsPanel spec references.
    metrics = {
        "wet_rmse_m": 0.08,
        "csi_0.10": 0.72,
        "peak_timing_error_min": 12.0,
        "volume_error_pct": 6.5,
        "b1_comparison": 0.9,
        "coverage_95": 0.93,
        "is_mock": True,
    }
    (OUT / "MOCK_metrics.json").write_text(json.dumps(metrics, indent=1))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    domain = make_domain()
    hydraulic_ds, _ = make_depth_nc(domain)
    make_surrogate_nc(hydraulic_ds)
    make_scenario_yaml()
    make_observations(domain)
    cam_ids = make_cameras()
    make_cctv_frames(cam_ids)
    make_stations()
    make_metrics()


if __name__ == "__main__":
    main()
