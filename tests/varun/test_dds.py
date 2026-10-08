"""Tests for the DDS snapshotter (cctv/archiver/dds_snapshot.py) and offline
parser (ingest/dds.py). See docs/VARUN_IMPLEMENTATION.md §6 T21.

Uses respx to mock HTTP so no real network call is ever made. Async entry
points are driven with asyncio.run() directly (no pytest-asyncio in this repo).
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pandas as pd
import pytest
import yaml

import ingest.dds as dds
from cctv.archiver import dds_snapshot
from cctv.legal_gate import LegalGateError

FIXTURES = Path(__file__).parent / "fixtures"
CFG = {"timeout_s": 15, "dds_snapshot_interval_s": 900}


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# snapshotter: raw capture + index
# ---------------------------------------------------------------------------


def test_snapshot_one_writes_raw_file_and_index_row(tmp_path, respx_mock):
    endpoint = {"name": "dds_road_flood", "url": "https://example.invalid/road-flood", "kind": "road_flood", "format": "json"}
    payload = b'{"points": []}'
    respx_mock.get(endpoint["url"]).respond(200, content=payload, headers={"content-type": "application/json"})

    async def go():
        async with httpx.AsyncClient() as client:
            return await dds_snapshot.snapshot_one(endpoint, client, CFG, raw_root=tmp_path)

    row = _run(go())

    assert row["status"] == 200
    assert row["bytes"] == len(payload)
    saved = Path(row["path"])
    assert saved.exists()
    assert saved.read_bytes() == payload

    day_dir = saved.parent
    index_rows = [json.loads(line) for line in (day_dir / "_index.jsonl").read_text().splitlines()]
    assert len(index_rows) == 1
    assert index_rows[0]["name"] == "dds_road_flood"
    assert index_rows[0]["sha1"]


def test_snapshot_one_handles_network_exception_without_raising(tmp_path, respx_mock):
    endpoint = {"name": "dds_road_flood", "url": "https://example.invalid/road-flood", "kind": "road_flood", "format": "json"}
    respx_mock.get(endpoint["url"]).mock(side_effect=httpx.ConnectTimeout("boom"))

    async def go():
        async with httpx.AsyncClient() as client:
            return await dds_snapshot.snapshot_one(endpoint, client, CFG, raw_root=tmp_path)

    row = _run(go())

    assert row["status"] is None
    assert "error" in row
    assert not any(tmp_path.rglob("*.json"))


def test_scheduler_respects_configured_interval():
    endpoints = [
        {"name": "dds_road_flood", "url": "https://example.invalid/a", "kind": "road_flood", "format": "json"},
        {"name": "dds_rain_gauges", "url": "https://example.invalid/b", "kind": "rain", "format": "json"},
    ]
    scheduler = dds_snapshot.build_scheduler(endpoints, client=object(), cfg=CFG)

    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert set(jobs) == {"dds-dds_road_flood", "dds-dds_rain_gauges"}
    for job in jobs.values():
        assert job.trigger.interval.total_seconds() == CFG["dds_snapshot_interval_s"]
        assert job.max_instances == 1
        assert job.coalesce is True


# ---------------------------------------------------------------------------
# legal gate
# ---------------------------------------------------------------------------


def test_legal_gate_refuses_when_source_not_go(tmp_path):
    status_path = tmp_path / "legal_status.yaml"
    status_path.write_text(
        yaml.dump({"sources": {"dds_flood": {"decision": "PENDING", "approved_by": None, "conditions_ack": False}}})
    )
    endpoints = [{"name": "dds_road_flood", "url": "https://x", "kind": "road_flood", "format": "json"}]
    with pytest.raises(LegalGateError):
        dds_snapshot.check_legal_gate(endpoints, status_path=status_path)


def test_legal_gate_passes_when_go_and_approved(tmp_path):
    status_path = tmp_path / "legal_status.yaml"
    status_path.write_text(
        yaml.dump({"sources": {"dds_scada": {"decision": "GO", "approved_by": "varun", "conditions_ack": True}}})
    )
    endpoints = [{"name": "dds_rain_gauges", "url": "https://x", "kind": "rain", "format": "json"}]
    dds_snapshot.check_legal_gate(endpoints, status_path=status_path)  # must not raise


# ---------------------------------------------------------------------------
# offline parser: schema + ICT->UTC conversion
# ---------------------------------------------------------------------------


def test_parse_road_flood_payload_matches_schema():
    raw = (FIXTURES / "dds_sample_road_flood.json").read_bytes()
    df = dds.parse_road_flood_payload(raw)

    assert list(df.columns) == dds.ROAD_FLOOD_COLUMNS
    assert len(df) == 3
    assert set(df["data_class"]) == {"OBSERVED"}

    row0 = df.iloc[0]
    assert row0["point_id"] == "RFP-001"
    assert row0["ts_utc"] == "2026-09-25T03:15:00Z"  # 10:15 ICT (UTC+7) -> 03:15 UTC
    assert row0["location_method"] == "DDS_PROVIDED"

    missing_coords_row = df[df["point_id"] == "RFP-003"].iloc[0]
    assert pd.isna(missing_coords_row["lon"])
    assert pd.isna(missing_coords_row["lat"])
    assert pd.isna(missing_coords_row["location_method"])
    assert pd.isna(missing_coords_row["loc_accuracy_m"])


def test_parse_stations_payload_matches_schema():
    raw = (FIXTURES / "dds_sample_stations.json").read_bytes()
    stations_df, timeseries_df = dds.parse_stations_payload(raw)

    assert list(stations_df.columns) == dds.STATIONS_COLUMNS
    assert list(timeseries_df.columns) == dds.TIMESERIES_COLUMNS
    assert set(stations_df["station_id"]) == {"RN-01", "LV-01"}

    rain_row = timeseries_df[(timeseries_df["station_id"] == "RN-01")].iloc[0]
    assert rain_row["unit"] == "mm"
    assert rain_row["ts_utc"] == "2026-09-25T03:00:00Z"

    level_row = timeseries_df[(timeseries_df["station_id"] == "LV-01")].iloc[0]
    assert level_row["unit"] == "m"

    lv_station = stations_df[stations_df["station_id"] == "LV-01"].iloc[0]
    assert pd.isna(lv_station["lon"]) and pd.isna(lv_station["lat"])


# ---------------------------------------------------------------------------
# offline parser: end-to-end run() against a fake snapshot dir, idempotent
# ---------------------------------------------------------------------------


def _build_fake_snapshot_dir(tmp_path: Path) -> tuple[Path, Path]:
    raw_root = tmp_path / "raw"
    day_dir = raw_root / "20260925"
    day_dir.mkdir(parents=True)

    road_flood_src = (FIXTURES / "dds_sample_road_flood.json").read_bytes()
    stations_src = (FIXTURES / "dds_sample_stations.json").read_bytes()

    road_flood_path = day_dir / "dds_road_flood_20260925T1015Z.json"
    road_flood_path.write_bytes(road_flood_src)
    stations_path = day_dir / "dds_rain_gauges_20260925T1015Z.json"
    stations_path.write_bytes(stations_src)

    index_rows = [
        {"name": "dds_road_flood", "url": "https://x/a", "ts_utc": "2026-09-25T10:15:00Z",
         "status": 200, "sha1": "deadbeef", "bytes": len(road_flood_src), "path": str(road_flood_path)},
        {"name": "dds_rain_gauges", "url": "https://x/b", "ts_utc": "2026-09-25T10:15:00Z",
         "status": 200, "sha1": "cafebabe", "bytes": len(stations_src), "path": str(stations_path)},
    ]
    with (day_dir / "_index.jsonl").open("w") as f:
        for row in index_rows:
            f.write(json.dumps(row) + "\n")

    endpoints_path = tmp_path / "dds_endpoints.yaml"
    endpoints_path.write_text(
        yaml.dump(
            {
                "endpoints": [
                    {"name": "dds_road_flood", "url": "https://x/a", "kind": "road_flood", "format": "json"},
                    {"name": "dds_rain_gauges", "url": "https://x/b", "kind": "rain", "format": "json"},
                ]
            }
        )
    )
    return raw_root, endpoints_path


def test_run_parses_fake_snapshot_dir_and_is_idempotent(tmp_path):
    raw_root, endpoints_path = _build_fake_snapshot_dir(tmp_path)
    out_road_flood = tmp_path / "out" / "dds_road_flood.parquet"
    out_stations = tmp_path / "out" / "stations.parquet"
    out_timeseries = tmp_path / "out" / "timeseries.parquet"

    result1 = dds.run(
        raw_root=raw_root,
        endpoints_path=endpoints_path,
        out_road_flood=out_road_flood,
        out_stations=out_stations,
        out_timeseries=out_timeseries,
    )
    assert result1 == {"road_flood_rows": 3, "stations_rows": 2, "timeseries_rows": 4}

    result2 = dds.run(
        raw_root=raw_root,
        endpoints_path=endpoints_path,
        out_road_flood=out_road_flood,
        out_stations=out_stations,
        out_timeseries=out_timeseries,
    )
    assert result2 == result1  # rerun over the same snapshots never duplicates rows
