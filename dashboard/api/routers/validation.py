from fastapi import APIRouter

from .. import store

router = APIRouter(prefix="/api", tags=["validation"])


@router.get("/validation/{run_id}")
def validation(run_id: str):
    return store.validation_for_run(run_id)
