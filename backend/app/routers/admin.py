"""Admin endpoints: retrain triple ensemble, ELO ratings, XGBoost feature importance."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from app.config import settings
from app.services.model_service import build_ensemble, load_or_train, load_or_train_calibrator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/retrain")
def retrain_model(request: Request) -> dict:
    """Retrain DC + Elo + XGBoost using all stored WC 2026 results."""
    svc = request.app.state.result_service
    wc_results = svc.all()

    if not wc_results:
        return {
            "status": "skipped",
            "message": "No results recorded yet — add match scores first.",
            "trained_on": 0,
        }

    logger.info("Admin retrain triggered with %d WC results.", len(wc_results))
    try:
        dc, elo, xgb = load_or_train(settings, wc_results=wc_results, force_retrain=True)
    except Exception as exc:
        logger.exception("Retrain failed.")
        return {"status": "error", "message": str(exc)}

    calibrator = load_or_train_calibrator(dc, settings, force_retrain=True)
    request.app.state.dc_model = dc
    request.app.state.elo_model = elo
    request.app.state.xgb_model = xgb
    request.app.state.calibrator = calibrator
    request.app.state.ensemble = build_ensemble(
        dc, elo,
        w_dc=settings.w_dc, w_elo=settings.w_elo, w_xgb=settings.w_xgb,
        xgb=xgb,
        calibrator=calibrator,
    )
    request.app.state.prediction_cache.clear()

    acc = svc.accuracy()
    xgb_ok = getattr(xgb, "is_fitted", False)
    logger.info("Retrain complete. XGB=%s  Accuracy=%s", xgb_ok, acc)
    return {
        "status": "ok",
        "model": "DC+Elo+XGB" if xgb_ok else "DC+Elo",
        "trained_on": len(wc_results),
        "cache_cleared": True,
        "accuracy": acc,
        "xgb_fitted": xgb_ok,
    }


@router.get("/elo-ratings")
def elo_ratings(request: Request) -> list[dict]:
    """Elo ratings for all teams, sorted best → worst."""
    return request.app.state.elo_model.ratings_table()


@router.get("/team-strengths")
def team_strengths(request: Request) -> list[dict]:
    """Dixon-Coles attack/defense/overall strengths."""
    return request.app.state.dc_model.team_strengths()


@router.get("/xgb-features")
def xgb_feature_importance(request: Request) -> list[dict]:
    """XGBoost feature importances sorted by relevance."""
    xgb = getattr(request.app.state, "xgb_model", None)
    if xgb is None or not getattr(xgb, "is_fitted", False):
        return [{"feature": "model_not_fitted", "importance": 0.0}]
    return xgb.feature_importance_table()


@router.get("/model-info")
def model_info(request: Request) -> dict:
    """Active ensemble configuration summary."""
    ens = request.app.state.ensemble
    xgb = getattr(request.app.state, "xgb_model", None)
    xgb_ok = getattr(xgb, "is_fitted", False)
    cal = getattr(request.app.state, "calibrator", None)
    cal_mode = type(cal).__name__.replace("Calibrator", "").lower() if cal is not None else "none"
    return {
        "ensemble": ens.model_label,
        "weights": {
            "dixon_coles": round(ens.w_dc, 3),
            "elo": round(ens.w_elo, 3),
            "xgboost": round(ens.w_xgb, 3),
        },
        "calibration": cal_mode,
        "calibrated": ens._calibrated,
        "xgb_fitted": xgb_ok,
        "xgb_n_features": len(getattr(xgb, "_feature_importance", {})),
    }
