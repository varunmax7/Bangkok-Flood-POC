from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["ingest"])


@router.post("/ingest/v1/observations")
def ingest_observations():
    raise HTTPException(501, "POST /ingest/v1/observations is implemented in T80")
