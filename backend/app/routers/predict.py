"""GET /predict/{match_id} — ensemble model prediction for a single fixture."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.data.fixtures import FIXTURES_BY_ID
from app.model.ensemble import EnsembleModel
from app.schemas.prediction import PredictionResponse

router = APIRouter(prefix="/predict", tags=["predict"])


@router.get("/{match_id}", response_model=PredictionResponse)
def predict_match(match_id: str, request: Request) -> PredictionResponse:
    if match_id not in FIXTURES_BY_ID:
        raise HTTPException(status_code=404, detail=f"Match '{match_id}' not found.")

    match = FIXTURES_BY_ID[match_id]

    if match["home_team"] == "TBD" or match["away_team"] == "TBD":
        raise HTTPException(
            status_code=422,
            detail="Teams not yet determined for this knockout fixture.",
        )

    # Return cached prediction if available
    cache: dict = request.app.state.prediction_cache
    if match_id in cache:
        return PredictionResponse(**cache[match_id])

    ensemble: EnsembleModel = request.app.state.ensemble
    raw = ensemble.predict(match["home_team"], match["away_team"], neutral=True)

    payload = {
        **raw,
        "match_id": match_id,
        "home_team": match["home_team"],
        "away_team": match["away_team"],
    }
    cache[match_id] = payload
    return PredictionResponse(**payload)
