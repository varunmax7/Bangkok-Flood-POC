"""What-if job tracking. See docs/VARUN_IMPLEMENTATION.md §6 T71.

In-memory job dict (fine for a single-process POC demo) plus an
append-only jobs.jsonl log of every status transition.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

JOBS_LOG = Path("dashboard/api/jobs.jsonl")

_lock = threading.Lock()
_jobs: dict[str, dict] = {}


def get_job(run_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(run_id)
        return dict(job) if job is not None else None


def set_job(run_id: str, **fields) -> dict:
    with _lock:
        job = _jobs.setdefault(run_id, {"run_id": run_id})
        job.update(fields)
        snapshot = dict(job)
    _append_log(snapshot)
    return snapshot


def _append_log(snapshot: dict) -> None:
    JOBS_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {**snapshot, "logged_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    with JOBS_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def clear_jobs() -> None:
    """Test-only: resets the in-memory job registry (not the log file)."""
    with _lock:
        _jobs.clear()
