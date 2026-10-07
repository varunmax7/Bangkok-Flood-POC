from fastapi import APIRouter

from .. import store

router = APIRouter(prefix="/api", tags=["observations"])


@router.get("/observations")
def observations(scenario_id: str):
    fc = store.scenario_observations(scenario_id)
    if fc is None:
        return {
            "type": "FeatureCollection",
            "features": [],
            "gap": f"No observations for scenario {scenario_id} [DATA GAP]",
        }
    return fc
