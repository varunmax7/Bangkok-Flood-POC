"""Read-only data loaders for the dashboard API. See docs/VARUN_IMPLEMENTATION.md §6 T30.

Every loader here checks the real artefact path first and falls back to
the T01 fixtures when it's missing, so the API always works even before
a teammate handoff lands — fixture-sourced responses carry `is_mock: true`.

Never writes anything; never raises on missing *optional* data (callers
turn `None` into an empty response + a `gap` note instead of a 500).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb
import yaml

from .settings import get_settings

_cache: dict[tuple[str, float], object] = {}


def _cached(path: Path, loader):
    """mtime-keyed cache: reloads only when the underlying file changes."""
    if not path.exists():
        return None
    key = (str(path), path.stat().st_mtime)
    if key not in _cache:
        _cache[key] = loader(path)
    return _cache[key]


def _read_yaml(path: Path):
    return yaml.safe_load(path.read_text())


def _read_json(path: Path):
    return json.loads(path.read_text())


# ---------------------------------------------------------------- config ---


def load_thresholds() -> dict:
    data = _cached(Path("configs/thresholds.yaml"), _read_yaml)
    return data or {}


# ---------------------------------------------------------------- domain ---


def load_domain():
    """Returns (domain: dict | None, polygon: dict | None, is_mock: bool)."""
    settings = get_settings()
    real = Path("configs/domain.yaml")
    if real.exists():
        domain = _cached(real, _read_yaml)
        poly_path = Path("configs/analysis_polygon.geojson")
        is_mock = bool(domain.get("is_mock", False)) if domain else False
    else:
        domain = _cached(settings.fixtures_dir / "domain.yaml", _read_yaml)
        poly_path = settings.fixtures_dir / "analysis_polygon.geojson"
        is_mock = True

    if domain is None:
        return None, None, False

    polygon = _cached(poly_path, _read_json) if poly_path.exists() else None
    return domain, polygon, is_mock


# ------------------------------------------------------------- scenarios ---


def _scenario_summary(y: dict, is_mock: bool) -> dict:
    return {
        "scenario_id": y.get("scenario_id"),
        "name": y.get("name"),
        "categories": y.get("categories"),
        "split": y.get("split"),
        "event_group_id": y.get("event_group_id"),
        "confidence": y.get("confidence"),
        "data_class_summary": y.get("data_class_summary"),
        "is_mock": bool(y.get("is_mock", is_mock)),
    }


def _real_scenario_paths() -> list[Path]:
    root = Path("scenarios")
    return sorted(root.glob("BKK-S*/scenario.yaml")) if root.exists() else []


def _fixture_scenario_paths() -> list[Path]:
    return sorted(get_settings().fixtures_dir.glob("*/scenario.yaml"))


def list_scenarios(include_mock: bool = False) -> list[dict]:
    real_paths = _real_scenario_paths()
    items = [_scenario_summary(_cached(p, _read_yaml), is_mock=False) for p in real_paths]
    if not real_paths or include_mock:
        items += [_scenario_summary(_cached(p, _read_yaml), is_mock=True) for p in _fixture_scenario_paths()]
    return items


def get_scenario(scenario_id: str) -> dict | None:
    for p in _real_scenario_paths() + _fixture_scenario_paths():
        y = _cached(p, _read_yaml)
        if y and y.get("scenario_id") == scenario_id:
            return y
    return None


# ------------------------------------------------------------------ runs ---

_MEMBER_RE = re.compile(r"^M\d+$")


def _member_id_from_run_id(run_id: str) -> str | None:
    for token in run_id.split("_"):
        if _MEMBER_RE.match(token):
            return token
    return None


def _iter_depth_manifests():
    base = get_settings().frames_dir
    if not base.exists():
        return
    yield from base.glob("*/*/depth/manifest.json")


def list_runs(scenario_id: str | None = None, source: str | None = None) -> list[dict]:
    out = []
    for m in _iter_depth_manifests():
        data = _cached(m, _read_json)
        if not data:
            continue
        if scenario_id and data.get("scenario_id") != scenario_id:
            continue
        if source and data.get("source") != source:
            continue
        out.append(
            {
                "run_id": data.get("run_id"),
                "source": data.get("source"),
                "member_id": _member_id_from_run_id(data.get("run_id", "")),
                "model_version": data.get("model_version"),
                "is_mock": bool(data.get("is_mock", False)),
            }
        )
    return out


def get_run_frames(run_id: str, var: str = "depth") -> dict | None:
    base = get_settings().frames_dir
    if not base.exists():
        return None
    for manifest_path in base.glob(f"*/{run_id}/{var}/manifest.json"):
        data = dict(_cached(manifest_path, _read_json) or {})
        data["frame_url_template"] = f"/frames/{data.get('source')}/{run_id}/{var}/{{t:03d}}.png"
        return data
    return None


def _scenario_id_for_run(run_id: str) -> str | None:
    """A satellite acquisition is tied to a scenario, not a run -- the
    same acquisition can be shown against that scenario's hydraulic,
    surrogate, or what-if runs. Look up which scenario this run_id's own
    frame manifest says it belongs to."""
    base = get_settings().frames_dir
    if not base.exists():
        return None
    for manifest_path in base.glob(f"*/{run_id}/*/manifest.json"):
        data = _cached(manifest_path, _read_json) or {}
        scenario_id = data.get("scenario_id")
        if scenario_id:
            return scenario_id
    return None


def get_run_satellite(run_id: str) -> list[dict]:
    # Rendered in T60 (render_satellite.py, keyed by scenario_id); nothing
    # to show before that's run for this run's scenario.
    scenario_id = _scenario_id_for_run(run_id)
    if scenario_id is None:
        return []
    manifest_path = get_settings().frames_dir / "satellite" / scenario_id / "manifest.json"
    data = _cached(manifest_path, _read_json)
    if not data:
        return []
    return data.get("acquisitions", [])


# -------------------------------------------------------------- stations ---


def _stations_paths() -> tuple[Path, Path, bool]:
    settings = get_settings()
    real_st = Path("data/interim/stations/stations.parquet")
    real_ts = Path("data/interim/stations/timeseries.parquet")
    if real_st.exists() and real_ts.exists():
        return real_st, real_ts, False
    return settings.fixtures_dir / "stations" / "stations.parquet", settings.fixtures_dir / "stations" / "timeseries.parquet", True


def stations_geojson(type_filter: str | None = None) -> dict | None:
    st_path, _, is_mock = _stations_paths()
    if not st_path.exists():
        return None
    query = f"SELECT * FROM read_parquet('{st_path.as_posix()}')"
    if type_filter:
        query += f" WHERE type = '{type_filter}'"
    df = duckdb.sql(query).df()
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
            "properties": {
                "station_id": row["station_id"],
                "type": row["type"],
                "name": row["name"],
                "source": row["source"],
                "is_mock": is_mock,
            },
        }
        for _, row in df.iterrows()
    ]
    return {"type": "FeatureCollection", "features": features}


def station_timeseries(station_id: str, start: str | None = None, end: str | None = None) -> dict | None:
    st_path, ts_path, _ = _stations_paths()
    if not st_path.exists() or not ts_path.exists():
        return None
    ids = duckdb.sql(
        f"SELECT station_id FROM read_parquet('{st_path.as_posix()}') WHERE station_id = ?", params=[station_id]
    ).df()
    if ids.empty:
        return None

    query = f"SELECT * FROM read_parquet('{ts_path.as_posix()}') WHERE station_id = ?"
    params = [station_id]
    if start:
        query += " AND ts_utc >= ?"
        params.append(start)
    if end:
        query += " AND ts_utc <= ?"
        params.append(end)
    query += " ORDER BY ts_utc"
    df = duckdb.sql(query, params=params).df()
    unit = df["unit"].iloc[0] if not df.empty else None
    data_class = df["data_class"].iloc[0] if not df.empty else None
    return {
        "ts": df["ts_utc"].tolist(),
        "value": df["value"].tolist(),
        "unit": unit,
        "data_class": data_class,
    }


# ------------------------------------------------------------------ cctv ---

_CCTV_PUBLIC_FIELDS = (
    "cam_id",
    "source",
    "name_th",
    "name_en",
    "lon",
    "lat",
    "heading_deg",
    "road_name",
    "priority",
    "in_domain",
    "status",
    "is_mock",
)


def cctv_registry_public() -> dict:
    path = Path("cctv/registry/cameras.geojson")
    fc = _cached(path, _read_json)
    if not fc:
        return {"type": "FeatureCollection", "features": [], "metadata": {"is_mock": True}}
    features = [
        {
            "type": "Feature",
            "geometry": f["geometry"],
            "properties": {k: f["properties"].get(k) for k in _CCTV_PUBLIC_FIELDS},
        }
        for f in fc.get("features", [])
    ]
    return {"type": "FeatureCollection", "features": features, "metadata": fc.get("metadata", {})}


def cctv_observations(cam_id: str, start: str | None = None, end: str | None = None) -> list[dict]:
    path = Path("data/cctv/cctv_obs.parquet")
    if not path.exists():
        return []
    query = f"SELECT * FROM read_parquet('{path.as_posix()}') WHERE cam_id = ?"
    params = [cam_id]
    if start:
        query += " AND ts_utc >= ?"
        params.append(start)
    if end:
        query += " AND ts_utc <= ?"
        params.append(end)
    query += " ORDER BY ts_utc"
    df = duckdb.sql(query, params=params).df()
    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
                "ts_utc": row["ts_utc"],
                "class": row["class"],
                "class_smoothed": row.get("class_smoothed"),
                "probs": {
                    k: row[k]
                    for k in ("p_normal", "p_waterlogging", "p_flooding", "p_severe", "p_unusable")
                    if k in row
                },
                "quality_flag": row["quality_flag"],
                "thumb_url": f"/thumbs/{row['cam_id']}/{row['ts_utc'][:10].replace('-', '')}/"
                f"{row['cam_id']}_{row['ts_utc'].replace('-', '').replace(':', '')}.jpg",
            }
        )
    return rows


# ------------------------------------------------------------ observations ---


def _observations_dir(scenario_id: str) -> Path | None:
    real = Path("scenarios") / scenario_id / "observations"
    if real.exists():
        return real
    fixture = get_settings().fixtures_dir / scenario_id / "observations"
    return fixture if fixture.exists() else None


def scenario_observations(scenario_id: str) -> dict | None:
    directory = _observations_dir(scenario_id)
    if directory is None:
        return None
    features = []
    for fname, kind in (("road_flood_points.geojson", "road_flood"), ("citizen_reports.geojson", "citizen")):
        path = directory / fname
        if not path.exists():
            continue
        fc = _cached(path, _read_json)
        for f in fc.get("features", []):
            feat = dict(f)
            feat["properties"] = {**f["properties"], "kind": kind}
            features.append(feat)
    return {"type": "FeatureCollection", "features": features}


# ------------------------------------------------------------- validation ---


def validation_for_run(run_id: str) -> dict:
    real = Path("reports/surrogate") / run_id / "metrics.json"
    fixture = get_settings().fixtures_dir / "MOCK_metrics.json"
    path = real if real.exists() else (fixture if run_id.startswith("MOCK") and fixture.exists() else None)
    if path is None:
        return {
            "metrics": None,
            "targets": None,
            "points": {"type": "FeatureCollection", "features": []},
            "gap": f"No validation metrics available for run_id={run_id} [DATA GAP]",
        }
    metrics = _cached(path, _read_json)
    return {"metrics": metrics, "targets": None, "points": {"type": "FeatureCollection", "features": []}}
