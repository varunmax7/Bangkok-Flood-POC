"""Env-backed settings for the dashboard API. See docs/VARUN_IMPLEMENTATION.md §6 T30."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        self.frames_dir = Path(os.environ.get("FG_FRAMES_DIR", "dashboard/static/frames"))
        self.surrogate_mode = os.environ.get("FG_SURROGATE_MODE", "auto")
        self.contact_email = os.environ.get("FG_CONTACT_EMAIL", "")
        self.ingest_api_key = os.environ.get("FG_API_KEY_INGEST", "")
        self.fixtures_dir = Path("tools/fixtures/out")
        self.cctv_thumbs_dir = Path("data/cctv/thumbs")


@lru_cache
def get_settings() -> Settings:
    return Settings()
