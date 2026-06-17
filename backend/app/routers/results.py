"""POST/GET/DELETE /results — record and retrieve match results."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.data.fixtures import FIXTURES_BY_ID
from app.schemas.result import AccuracyResponse, ResultCreate, ResultResponse

router = APIRouter(prefix="/results", tags=["results"])


def _get_service(request: Request):
    return request.app.state.result_service


@router.post("/{match_id}", response_model=ResultResponse)
def record_result(match_id: str, body: ResultCreate, request: Request) -> ResultResponse:
    """Record (or overwrite) the actual score for a match."""
    fixture = FIXTURES_BY_ID.get(match_id)
    if not fixture:
        raise HTTPException(status_code=404, detail=f"Match '{match_id}' not found.")
    if fixture["home_team"] == "TBD" or fixture["away_team"] == "TBD":
        raise HTTPException(status_code=422, detail="Teams not yet determined.")

    # Fetch the cached prediction if available
    pred_cache: dict = request.app.state.prediction_cache
    prediction = pred_cache.get(match_id)

    # If not cached, try to generate it on the fly
    if prediction is None:
        try:
            from app.model.ensemble import EnsembleModel
            ensemble: EnsembleModel = request.app.state.ensemble
            raw = ensemble.predict(fixture["home_team"], fixture["away_team"], neutral=True)
            prediction = raw
            pred_cache[match_id] = raw
        except Exception:
            prediction = None

    svc = _get_service(request)
    entry = svc.record(
        match_id=match_id,
        home_team=fixture["home_team"],
        away_team=fixture["away_team"],
        stage=fixture["stage"],
        home_score=body.home_score,
        away_score=body.away_score,
        prediction=prediction,
    )
    return ResultResponse(**entry)


@router.get("/accuracy", response_model=AccuracyResponse)
def get_accuracy(request: Request) -> AccuracyResponse:
    """Return overall prediction accuracy statistics."""
    return AccuracyResponse(**_get_service(request).accuracy())


@router.get("", response_model=list[ResultResponse])
def list_results(request: Request) -> list[ResultResponse]:
    """Return all recorded match results."""
    return [ResultResponse(**e) for e in _get_service(request).all()]


@router.get("/{match_id}", response_model=ResultResponse)
def get_result(match_id: str, request: Request) -> ResultResponse:
    """Return the recorded result for a specific match."""
    entry = _get_service(request).get(match_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"No result recorded for '{match_id}'.")
    return ResultResponse(**entry)


@router.delete("/{match_id}")
def delete_result(match_id: str, request: Request) -> dict:
    """Remove a recorded result."""
    deleted = _get_service(request).delete(match_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No result found for '{match_id}'.")
    return {"deleted": match_id}
