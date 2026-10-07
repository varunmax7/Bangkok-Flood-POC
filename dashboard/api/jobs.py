"""What-if job tracking. Filled in by T71 — see docs/VARUN_IMPLEMENTATION.md §6 T71.

`POST /api/predict` / `GET /api/predict/{run_id}` are 501 until then, so
nothing uses this registry yet; it exists now so T71 doesn't have to touch
dashboard/api/main.py's router wiring.
"""
from __future__ import annotations

# TODO(T71): {run_id: {status: RUNNING|PARTIAL|DONE|FAILED, manifest_url, ood_flag, elapsed_s, is_mock}}
_jobs: dict[str, dict] = {}
