"""POST /ingest/v1/observations -- sensor observation ingest stub (O11).

See docs/VARUN_IMPLEMENTATION.md §6 T80 / §19 and docs/sensor_ingestion_spec.md.
No hardware exists in this POC; this validates and stores whatever's posted
to it (manually, or eventually by an MQTT bridge per the spec doc).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
from fastapi import APIRouter, Body, Header, HTTPException

from ..settings import get_settings

router = APIRouter(tags=["ingest"])

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "observation.schema.json"
SEEN_PATH = Path("data/interim/ingest/seen.txt")
OBS_DIR = Path("data/interim/ingest")
MAX_BATCH = 1000

_schema = json.loads(SCHEMA_PATH.read_text())
_validator = jsonschema.Draft7Validator(_schema)


def _validate(obs: object) -> str | None:
    """Returns an error message, or None if `obs` is a valid observation."""
    if not isinstance(obs, dict):
        return "observation must be a JSON object"
    errors = sorted(_validator.iter_errors(obs), key=lambda e: list(e.path))
    if errors:
        return errors[0].message
    # jsonschema's "format": "date-time" isn't enforced without the optional
    # rfc3339-validator dependency; check it directly instead.
    try:
        datetime.fromisoformat(str(obs["ts"]).replace("Z", "+00:00"))
    except ValueError:
        return f"ts is not a valid ISO-8601 date-time: {obs.get('ts')!r}"
    return None


def _idempotency_key(obs: dict) -> str:
    return f"{obs['site_id']}|{obs['ts']}|{obs['sensor_type']}"


def _load_seen(seen_path: Path) -> set[str]:
    if not seen_path.exists():
        return set()
    return set(seen_path.read_text().splitlines())


def _append_seen(seen_path: Path, keys: list[str]) -> None:
    seen_path.parent.mkdir(parents=True, exist_ok=True)
    with seen_path.open("a") as f:
        for k in keys:
            f.write(k + "\n")


@router.post("/ingest/v1/observations")
def ingest_observations(
    body: list[dict] = Body(...),
    x_api_key: str | None = Header(default=None),
):
    settings = get_settings()
    if not settings.ingest_api_key or x_api_key != settings.ingest_api_key:
        raise HTTPException(401, "invalid or missing X-API-Key")
    if len(body) > MAX_BATCH:
        raise HTTPException(422, f"batch too large: {len(body)} observations > {MAX_BATCH}")

    seen = _load_seen(SEEN_PATH)
    accepted: list[dict] = []
    rejected: list[dict] = []
    new_keys: list[str] = []

    for i, obs in enumerate(body):
        error = _validate(obs)
        if error:
            rejected.append({"index": i, "reason": error})
            continue
        key = _idempotency_key(obs)
        if key in seen or key in new_keys:
            rejected.append({"index": i, "reason": "duplicate (site_id+ts+sensor_type already ingested)"})
            continue
        accepted.append(obs)
        new_keys.append(key)

    if accepted:
        OBS_DIR.mkdir(parents=True, exist_ok=True)
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        out_path = OBS_DIR / f"obs_{day}.jsonl"
        with out_path.open("a") as f:
            for obs in accepted:
                f.write(json.dumps(obs) + "\n")
        _append_seen(SEEN_PATH, new_keys)

    return {"accepted": len(accepted), "rejected": rejected}
