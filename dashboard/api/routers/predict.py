from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["predict"])


@router.post("/predict")
def predict():
    raise HTTPException(501, "POST /api/predict is implemented in T71")


@router.get("/predict/{run_id}")
def predict_status(run_id: str):
    raise HTTPException(501, "GET /api/predict/{run_id} is implemented in T71")
