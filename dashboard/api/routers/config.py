from fastapi import APIRouter

from .. import store

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def get_config():
    return store.load_thresholds()
