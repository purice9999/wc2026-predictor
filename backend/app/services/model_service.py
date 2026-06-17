"""Load or train the three prediction models at startup."""

from __future__ import annotations

import logging
import math
import pickle
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import Settings
from app.data.historical import download_results, preprocess_data
from app.data.tournament_config import TIME_DECAY_RATE, TOURNAMENT_TEAMS
from app.model.ensemble import EnsembleModel
from app.models.calibration import CalibratorType, build_calibrator
from app.models.dixon_coles import DixonColesModel
from app.models.elo import EloModel
from app.models.xgboost_model import XGBoostPredictor

logger = logging.getLogger(__name__)

ELO_K_WC = 40.0


# ──────────────────────────────────────────────
# WC result injection
# ──────────────────────────────────────────────

def inject_wc_results(df: pd.DataFrame, wc_results: list[dict]) -> pd.DataFrame:
    """Append real WC 2026 results to training data with 2× competition boost."""
    if not wc_results:
        return df

    from app.data.fixtures import FIXTURES_BY_ID

    today = date.today()
    rows = []
    for r in wc_results:
        fixture = FIXTURES_BY_ID.get(r.get("match_id", ""), {})
        match_date = fixture.get("date", today)
        days_ago = max((today - match_date).days, 0)
        w_time = math.exp(-TIME_DECAY_RATE * days_ago)
        rows.append({
            "date": pd.Timestamp(match_date),
            "date_dt": match_date,
            "home_team": r["home_team"],
            "away_team": r["away_team"],
            "home_score": int(r["home_score"]),
            "away_score": int(r["away_score"]),
            "tournament": "FIFA World Cup",
            "neutral": 1.0,
            "w_time": w_time,
            "w_comp": 5.0,
            "weight": w_time * 5.0 * 2.0,
        })

    extra = pd.DataFrame(rows)
    combined = pd.concat([df, extra], ignore_index=True)
    combined["weight"] = combined["weight"] / combined["weight"].mean()
    logger.info("Injected %d WC 2026 results. Dataset: %d → %d rows.",
                len(rows), len(df), len(combined))
    return combined


# ──────────────────────────────────────────────
# Post-hoc Elo updates from WC results
# ──────────────────────────────────────────────

def apply_wc_elo_updates(elo: EloModel, wc_results: list[dict]) -> EloModel:
    """Direct Elo updates from actual WC 2026 results (after full historical fit)."""
    for r in sorted(wc_results, key=lambda x: x.get("recorded_at", "")):
        h, a = r["home_team"], r["away_team"]
        hs, as_ = int(r["home_score"]), int(r["away_score"])
        rh = elo._get_rating(h)
        ra = elo._get_rating(a)
        expected_h = 1.0 / (1.0 + 10.0 ** (-(rh - ra) / 400.0))
        actual_h = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)
        gd = abs(hs - as_)
        importance = 1.0 + min(gd - 1, 3) * 0.1 if gd > 0 else 1.0
        delta = ELO_K_WC * importance * (actual_h - expected_h)
        elo.ratings[h] = rh + delta
        elo.ratings[a] = ra - delta
        logger.debug("EloWC: %s %.0f→%.0f  %s %.0f→%.0f  (%d-%d)",
                     h, rh, elo.ratings[h], a, ra, elo.ratings[a], hs, as_)
    logger.info("Applied %d WC 2026 Elo updates.", len(wc_results))
    return elo


# ──────────────────────────────────────────────
# Train all three models
# ──────────────────────────────────────────────

def load_or_train(
    settings: Settings,
    wc_results: list[dict] | None = None,
    force_retrain: bool = False,
) -> tuple[DixonColesModel, EloModel, XGBoostPredictor]:
    """Return (DC, Elo, XGB).  Cache all three; any forced retrain rebuilds all."""
    dc_path = settings.dc_model_cache_path
    elo_path = settings.elo_model_cache_path
    xgb_path = settings.xgb_model_cache_path

    use_cache = (
        not settings.retrain
        and not force_retrain
        and wc_results is None
        and Path(dc_path).exists()
        and Path(elo_path).exists()
        and Path(xgb_path).exists()
    )

    if use_cache:
        try:
            logger.info("Loading cached models (DC + Elo + XGB)…")
            dc = DixonColesModel.load(dc_path)
            elo = EloModel.load(elo_path)
            xgb = XGBoostPredictor.load(xgb_path)
            logger.info("All three models loaded from cache.")
            _log_unmatched(dc)
            return dc, elo, xgb
        except Exception as exc:
            logger.warning("Cache load failed (%s); retraining…", exc)

    fresh = force_retrain or bool(wc_results)
    logger.info("Training DC + Elo + XGBoost from scratch (fresh_data=%s)…", fresh)

    raw = download_results(settings.data_cache_path, force=fresh)
    df = preprocess_data(raw)

    if wc_results:
        df = inject_wc_results(df, wc_results)

    # 1 — Dixon-Coles
    logger.info("=== Dixon-Coles ===")
    dc = DixonColesModel()
    dc.fit(df)
    dc.save(dc_path)

    # 2 — Elo
    logger.info("=== Elo ===")
    elo = EloModel()
    elo.fit(df)
    if wc_results:
        apply_wc_elo_updates(elo, wc_results)
    elo.save(elo_path)

    # 3 — XGBoost
    logger.info("=== XGBoost ===")
    xgb = XGBoostPredictor()
    try:
        xgb.fit(df, dc, elo)
        xgb.save(xgb_path)
        logger.info("XGBoost fitted and saved.")
    except Exception as exc:
        logger.error("XGBoost training FAILED: %s — will use DC+Elo only.", exc)
        xgb.is_fitted = False

    _log_unmatched(dc)
    return dc, elo, xgb


def build_ensemble(
    dc: DixonColesModel,
    elo: EloModel,
    w_dc: float = 1.0,
    w_elo: float = 0.0,
    w_xgb: float = 0.0,
    xgb: XGBoostPredictor | None = None,
    calibrator: CalibratorType = None,
) -> EnsembleModel:
    return EnsembleModel(dc, elo, w_dc=w_dc, w_elo=w_elo, w_xgb=w_xgb, xgb=xgb, calibrator=calibrator)


def load_or_train_calibrator(
    dc: DixonColesModel,
    settings: Settings,
    force_retrain: bool = False,
) -> CalibratorType:
    """Incarca sau antreneaza calibratorul isotonic/platt pe un holdout temporal.

    Strategia anti-leakage (documentata):
      - DC este antrenat pe toate datele historice (comportament neschimbat).
      - Calibratorul se antreneaza pe predictiile DC pentru ultimele
        calibration_holdout_months luni din datele de antrenament.
      - Leakage minor: DC a vazut acele meciuri in training, deci estimarile
        de probabilitate au o usoara bias spre outcome-ul real. Isotonic
        corecteaza sistematic distributia, nu memoreaza meciuri individuale.
      - Alternativa zero-leakage (shadow DC) nu e implementata implicit
        din motive de viteza (~20s extra la startup).
    """
    mode = settings.calibration
    if mode == "none":
        logger.info("Calibrare dezactivata (CALIBRATION=none).")
        return None

    path = settings.calibrator_cache_path
    if not force_retrain and not settings.retrain and Path(path).exists():
        try:
            with open(path, "rb") as f:
                cal = pickle.load(f)
            logger.info("Calibrator incarcat din cache: %s", path)
            return cal
        except Exception as exc:
            logger.warning("Calibrator cache corupt (%s); reantrenare.", exc)

    logger.info("Antrenare calibrator %s pe holdout temporal (%d luni)...",
                mode, settings.calibration_holdout_months)

    raw = download_results(settings.data_cache_path, force=False)
    df = preprocess_data(raw)

    max_date = df["date_dt"].max()
    holdout_start = max_date - timedelta(days=settings.calibration_holdout_months * 30)
    df_holdout = df[df["date_dt"] >= holdout_start].copy()

    logger.info(
        "Holdout calibrator: %s -> %s  (%d meciuri)",
        holdout_start, max_date, len(df_holdout),
    )

    y_pred_rows, y_true_rows = [], []
    failed = 0
    for row in df_holdout.itertuples(index=False):
        hs, as_ = int(row.home_score), int(row.away_score)
        cls = 0 if hs > as_ else (1 if hs == as_ else 2)
        y_true_rows.append([int(cls == k) for k in range(3)])
        try:
            r = dc.predict_match_full(row.home_team, row.away_team, bool(row.neutral))
            y_pred_rows.append([r["prob_home"], r["prob_draw"], r["prob_away"]])
        except Exception:
            y_pred_rows.append([1 / 3, 1 / 3, 1 / 3])
            failed += 1

    if failed:
        logger.warning("Calibrator: %d predictii esualte (echipe fara date).", failed)

    y_pred = np.array(y_pred_rows, dtype=np.float64)
    y_true = np.array(y_true_rows, dtype=np.float64)

    cal = build_calibrator(mode)
    cal.fit(y_pred, y_true)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(cal, f)
    logger.info("Calibrator %s salvat la %s", type(cal).__name__, path)
    return cal


def _log_unmatched(dc: DixonColesModel) -> None:
    unmatched = [t for t in TOURNAMENT_TEAMS if t not in dc.team_to_idx]
    if unmatched:
        logger.warning("%d WC 2026 teams without training data: %s",
                       len(unmatched), unmatched)
    else:
        logger.info("All %d WC 2026 teams have training data ✓", len(TOURNAMENT_TEAMS))
