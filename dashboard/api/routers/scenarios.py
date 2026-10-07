from fastapi import APIRouter, HTTPException

from .. import store

router = APIRouter(prefix="/api", tags=["scenarios"])


@router.get("/scenarios")
def list_scenarios(include_mock: bool = False):
    return store.list_scenarios(include_mock=include_mock)


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str):
    y = store.get_scenario(scenario_id)
    if y is None:
        raise HTTPException(404, f"scenario not found: {scenario_id}")
    return y
