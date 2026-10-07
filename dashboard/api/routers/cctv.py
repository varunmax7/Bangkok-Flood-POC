from fastapi import APIRouter

from .. import store

router = APIRouter(prefix="/api", tags=["cctv"])


@router.get("/cctv")
def list_cameras():
    return store.cctv_registry_public()


@router.get("/cctv/{cam_id}/observations")
def cam_observations(cam_id: str, start: str | None = None, end: str | None = None):
    rows = store.cctv_observations(cam_id, start, end)
    if not rows:
        return {"items": [], "gap": "No CCTV classifications available yet (T53 not run) [DATA GAP]"}
    return {"items": rows}
