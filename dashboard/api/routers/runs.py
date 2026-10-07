from fastapi import APIRouter, HTTPException

from .. import store

router = APIRouter(prefix="/api", tags=["runs"])


@router.get("/runs")
def list_runs(scenario_id: str | None = None, source: str | None = None):
    return store.list_runs(scenario_id, source)


@router.get("/runs/{run_id}/frames")
def get_run_frames(run_id: str, var: str = "depth"):
    data = store.get_run_frames(run_id, var)
    if data is None:
        raise HTTPException(404, f"no frames for run_id={run_id} var={var}; run `make frames` (T40) first")
    return data


@router.get("/runs/{run_id}/satellite")
def get_run_satellite(run_id: str):
    items = store.get_run_satellite(run_id)
    if not items:
        return {"items": [], "gap": "No coincident acquisition [DATA GAP]"}
    return {"items": items}
