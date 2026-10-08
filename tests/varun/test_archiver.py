"""Tests for cctv/archiver/archiver.py. See docs/VARUN_IMPLEMENTATION.md §6 T20.

Uses respx to mock HTTP so no real network call is ever made. Async entry
points are driven with asyncio.run() directly (no pytest-asyncio in this repo).
"""
from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

import httpx
import pytest
import respx
import yaml
from PIL import Image

from cctv.archiver import archiver
from cctv.legal_gate import LegalGateError

CFG = {
    "max_cameras": 50,
    "min_interval_s": 120,
    "jitter_s": 20,
    "timeout_s": 15,
    "max_width_px": 640,
    "thumb_width_px": 320,
    "quality": {"stale_consecutive": 3, "night_mean_saturation": 12, "blur_laplacian_var": 40},
}


def _jpeg_bytes(width: int, height: int, color=(128, 60, 60)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (width, height), color).save(buf, "JPEG")
    return buf.getvalue()


def _run(coro):
    return asyncio.run(coro)


def test_oversized_frame_is_downscaled_and_saved(tmp_path):
    raw_root, thumbs_root, meta_root = tmp_path / "raw", tmp_path / "thumbs", tmp_path / "meta"
    url = "https://example.invalid/cam1.jpg"

    with respx.mock:
        respx.get(url).respond(200, content=_jpeg_bytes(1280, 720), headers={"content-type": "image/jpeg"})
        async def go():
            async with httpx.AsyncClient() as client:
                return await archiver.fetch_and_process(
                    "BMAT-0001", url, client, CFG,
                    raw_root=raw_root, thumbs_root=thumbs_root, meta_root=meta_root,
                )
        meta = _run(go())

    assert meta["quality_flag"] in ("OK", "NIGHT_IR", "BLUR")
    assert meta["width"] <= CFG["max_width_px"]
    saved = Image.open(meta["path"])
    assert saved.width <= CFG["max_width_px"]


def test_http_404_is_handled_and_nothing_is_saved(tmp_path):
    raw_root, thumbs_root, meta_root = tmp_path / "raw", tmp_path / "thumbs", tmp_path / "meta"
    url = "https://example.invalid/cam1.jpg"

    with respx.mock:
        respx.get(url).respond(404)
        async def go():
            async with httpx.AsyncClient() as client:
                return await archiver.fetch_and_process(
                    "BMAT-0001", url, client, CFG,
                    raw_root=raw_root, thumbs_root=thumbs_root, meta_root=meta_root,
                )
        meta = _run(go())

    assert meta["quality_flag"] == "HTTP_ERROR"
    assert meta["http_status"] == 404
    assert not raw_root.exists() or not any(raw_root.rglob("*.jpg"))


def test_non_image_content_type_is_handled(tmp_path):
    raw_root, thumbs_root, meta_root = tmp_path / "raw", tmp_path / "thumbs", tmp_path / "meta"
    url = "https://example.invalid/cam1.jpg"

    with respx.mock:
        respx.get(url).respond(200, content=b"<html>not an image</html>", headers={"content-type": "text/html"})
        async def go():
            async with httpx.AsyncClient() as client:
                return await archiver.fetch_and_process(
                    "BMAT-0001", url, client, CFG,
                    raw_root=raw_root, thumbs_root=thumbs_root, meta_root=meta_root,
                )
        meta = _run(go())

    assert meta["quality_flag"] == "HTTP_ERROR"
    assert not raw_root.exists() or not any(raw_root.rglob("*.jpg"))


def test_decode_failure_writes_no_file(tmp_path):
    raw_root, thumbs_root, meta_root = tmp_path / "raw", tmp_path / "thumbs", tmp_path / "meta"
    url = "https://example.invalid/cam1.jpg"

    with respx.mock:
        # 200 + image content-type, but the bytes are garbage -> PIL decode must fail
        respx.get(url).respond(200, content=b"not-really-a-jpeg", headers={"content-type": "image/jpeg"})
        async def go():
            async with httpx.AsyncClient() as client:
                return await archiver.fetch_and_process(
                    "BMAT-0001", url, client, CFG,
                    raw_root=raw_root, thumbs_root=thumbs_root, meta_root=meta_root,
                )
        meta = _run(go())

    assert meta["quality_flag"] == "EXCEPTION"
    assert "error" in meta
    assert not raw_root.exists() or not any(raw_root.rglob("*.jpg"))


def test_network_exception_is_handled_without_raising(tmp_path):
    raw_root, thumbs_root, meta_root = tmp_path / "raw", tmp_path / "thumbs", tmp_path / "meta"
    url = "https://example.invalid/cam1.jpg"

    with respx.mock:
        respx.get(url).mock(side_effect=httpx.ConnectTimeout("boom"))
        async def go():
            async with httpx.AsyncClient() as client:
                return await archiver.fetch_and_process(
                    "BMAT-0001", url, client, CFG,
                    raw_root=raw_root, thumbs_root=thumbs_root, meta_root=meta_root,
                )
        meta = _run(go())

    assert meta["quality_flag"] == "EXCEPTION"
    assert meta["http_status"] is None


def test_stale_frame_detected_after_repeats(tmp_path):
    from collections import defaultdict

    raw_root, thumbs_root = tmp_path / "raw", tmp_path / "thumbs"
    img = Image.new("RGB", (640, 360), (10, 20, 30))
    history: dict[str, list[str]] = defaultdict(list)
    import datetime as dt

    flags = []
    for _ in range(CFG["quality"]["stale_consecutive"] + 1):
        result = archiver.process_and_save(
            img, "BMAT-0001", dt.datetime.now(dt.timezone.utc), CFG,
            phash_history=history, raw_root=raw_root, thumbs_root=thumbs_root,
        )
        flags.append(result["quality_flag"])

    assert flags[-1] == "STALE"


def test_legal_gate_refuses_when_source_not_go(tmp_path):
    status_path = tmp_path / "legal_status.yaml"
    status_path.write_text(
        yaml.dump({"sources": {"bmatraffic": {"decision": "PENDING", "approved_by": None, "conditions_ack": False}}})
    )
    with pytest.raises(LegalGateError):
        archiver.check_legal_gate([{"source": "BMAT"}], status_path=status_path)


def test_legal_gate_passes_when_go_and_approved(tmp_path):
    status_path = tmp_path / "legal_status.yaml"
    status_path.write_text(
        yaml.dump(
            {"sources": {"bmatraffic": {"decision": "GO", "approved_by": "varun", "conditions_ack": True}}}
        )
    )
    archiver.check_legal_gate([{"source": "BMAT"}], status_path=status_path)  # must not raise


def test_scheduler_respects_configured_interval_and_jitter():
    cameras_with_urls = [("BMAT-0001", "https://example.invalid/1.jpg"), ("BMAT-0002", "https://example.invalid/2.jpg")]
    scheduler = archiver.build_scheduler(cameras_with_urls, client=object(), cfg=CFG)

    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert set(jobs) == {"fetch-BMAT-0001", "fetch-BMAT-0002"}
    for job in jobs.values():
        assert job.trigger.interval.total_seconds() == CFG["min_interval_s"]
        assert job.trigger.jitter == CFG["jitter_s"]
        assert job.max_instances == 1
        assert job.coalesce is True
