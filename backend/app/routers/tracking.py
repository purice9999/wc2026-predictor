"""
GET /tracking  — predicții înghețate vs. rezultate reale.
POST /tracking/refresh — reîncarcă rezultatele din openfootball.
POST /tracking/freeze  — îngheață predicțiile pentru meciurile cu echipe cunoscute.
"""

from __future__ import annotations

import logging
import math
from datetime import date

from fastapi import APIRouter, Request

from app.data.fixtures import FIXTURES_BY_ID
from app.data.results_fetcher import get_real_results, match_real_to_fixture
from app.services.result_service import ResultService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tracking", tags=["tracking"])

_EPS = 1e-9


def _log_loss_one(ph: float, pd: float, pa: float, winner: str) -> float:
    probs = {"home": max(ph, _EPS), "draw": max(pd, _EPS), "away": max(pa, _EPS)}
    return -math.log(probs.get(winner, _EPS))


def _brier_one(ph: float, pd: float, pa: float, winner: str) -> float:
    y = {"home": [1, 0, 0], "draw": [0, 1, 0], "away": [0, 0, 1]}[winner]
    p = [ph, pd, pa]
    return sum((pi - yi) ** 2 for pi, yi in zip(p, y))


def _merge_real_results(state) -> dict:
    """
    Combină rezultatele din două surse:
    1. openfootball (automatic, fetched la startup/refresh)
    2. result_service (admin panel entries — sursă primară cu precedență)
    Format: {match_id: {home_score, away_score, actual_winner}}
    """
    merged: dict = dict(getattr(state, "real_results", {}))

    svc: ResultService = getattr(state, "result_service", None)
    if svc:
        for entry in svc.all():
            mid = entry.get("match_id")
            if not mid:
                continue
            hs = entry.get("home_score")
            as_ = entry.get("away_score")
            if hs is None or as_ is None:
                continue
            winner = "home" if hs > as_ else ("draw" if hs == as_ else "away")
            merged[mid] = {"home_score": hs, "away_score": as_, "actual_winner": winner}

    return merged


@router.get("")
def get_tracking(request: Request) -> dict:
    """
    Returnează:
    - completed: meciuri jucate cu predicție înghețată + rezultat real + ✓/✗
    - pending: meciuri viitoare cu predicție înghețată
    - without_prediction: meciuri jucate fără predicție înghețată (gap)
    - metrics: acuratețe, log-loss, Brier, BTTS, Over/Under (doar pe completed)
    """
    fps: dict = request.app.state.frozen_predictions.all()
    real_results: dict = _merge_real_results(request.app.state)

    today = date.today()
    completed = []
    pending = []
    without_prediction = []

    for fid, fx in FIXTURES_BY_ID.items():
        fh, fa = fx.get("home_team"), fx.get("away_team")
        fdate = fx.get("date")
        is_tbd = fh == "TBD" or fa == "TBD"
        is_past = fdate and fdate <= today

        real = real_results.get(fid)
        frozen = fps.get(fid)

        if real:  # meci jucat (avem scor real)
            entry = {
                "match_id": fid,
                "home_team": fh,
                "away_team": fa,
                "date": str(fdate) if fdate else None,
                "stage": fx.get("stage"),
                "group": fx.get("group"),
                "result": real,
            }
            if frozen:
                ph, pd, pa = frozen["prob_home"], frozen["prob_draw"], frozen["prob_away"]
                winner = real["actual_winner"]
                correct = frozen["predicted_winner"] == winner
                btts_actual = real["home_score"] > 0 and real["away_score"] > 0
                over_2_5_actual = (real["home_score"] + real["away_score"]) > 2
                entry.update({
                    "frozen": frozen,
                    "correct": correct,
                    "log_loss": round(_log_loss_one(ph, pd, pa, winner), 4),
                    "brier": round(_brier_one(ph, pd, pa, winner), 4),
                    "btts_correct": (frozen["btts_yes"] >= 0.5) == btts_actual,
                    "over_2_5_correct": (frozen["over_2_5"] >= 0.5) == over_2_5_actual,
                })
                completed.append(entry)
            else:
                without_prediction.append(entry)

        elif not is_tbd:  # meci viitor cu echipe cunoscute
            entry = {
                "match_id": fid,
                "home_team": fh,
                "away_team": fa,
                "date": str(fdate) if fdate else None,
                "stage": fx.get("stage"),
                "group": fx.get("group"),
                "frozen": frozen,
            }
            pending.append(entry)

    # Sort cronologic
    completed.sort(key=lambda x: x["date"] or "")
    pending.sort(key=lambda x: x["date"] or "")

    # Metrici (doar pe meciurile cu predicție înghețată)
    n = len(completed)
    correct_n = sum(1 for c in completed if c.get("correct"))
    ll_sum = sum(c["log_loss"] for c in completed if "log_loss" in c)
    br_sum = sum(c["brier"] for c in completed if "brier" in c)
    btts_n = sum(1 for c in completed if c.get("btts_correct"))
    o25_n = sum(1 for c in completed if c.get("over_2_5_correct"))

    metrics = {
        "matches_played": n,
        "correct_picks": correct_n,
        "accuracy": round(correct_n / n, 4) if n else None,
        "log_loss": round(ll_sum / n, 4) if n else None,
        "brier": round(br_sum / n, 4) if n else None,
        "btts_hit_rate": round(btts_n / n, 4) if n else None,
        "over_2_5_hit_rate": round(o25_n / n, 4) if n else None,
        "without_prediction": len(without_prediction),
        "pending": len(pending),
        "small_sample_warning": n < 20,
    }

    return {
        "completed": completed,
        "pending": pending,
        "without_prediction": without_prediction,
        "metrics": metrics,
    }


@router.post("/refresh")
def refresh_results(request: Request) -> dict:
    """Reîncarcă rezultatele reale din openfootball (ignoră cache TTL)."""
    real_matches = get_real_results(force=True)
    real_results = match_real_to_fixture(real_matches, FIXTURES_BY_ID)
    request.app.state.real_results = real_results
    logger.info("Tracking refresh: %d rezultate reale încărcate.", len(real_results))
    return {"status": "ok", "matches_with_results": len(real_results)}


@router.post("/freeze")
def freeze_predictions(request: Request) -> dict:
    """
    Îngheață predicțiile pentru toate meciurile cu echipe cunoscute
    care nu au predicție înghețată deja.
    """
    fps = request.app.state.frozen_predictions
    ensemble = request.app.state.ensemble
    frozen_new = 0
    skipped = 0
    errors = 0

    for fid, fx in FIXTURES_BY_ID.items():
        if fx.get("home_team") == "TBD" or fx.get("away_team") == "TBD":
            continue
        if fps.has(fid):
            skipped += 1
            continue
        try:
            pred = ensemble.predict(fx["home_team"], fx["away_team"], neutral=True)
            if fps.freeze(fid, fx, pred):
                frozen_new += 1
        except Exception as exc:
            logger.warning("Freeze failed for %s: %s", fid, exc)
            errors += 1

    logger.info("Freeze: %d noi, %d existente, %d erori.", frozen_new, skipped, errors)
    return {
        "status": "ok",
        "newly_frozen": frozen_new,
        "already_frozen": skipped,
        "errors": errors,
        "total": fps.count(),
    }
