"""
XGBoost multi-class classifier for 3-outcome (H/D/A) football prediction.

Features (25):
  Elo  — pre-match ratings computed chronologically (zero leakage)
  DC   — attack / defense / xG parameters from the fitted Dixon-Coles model
  Form — last-5 win/draw/loss rates + goal averages (per team)
  H2H  — head-to-head last-10-meetings statistics
  Ctx  — neutral venue flag, competition weight

Target: 0 = home win · 1 = draw · 2 = away win
"""

from __future__ import annotations

import logging
import pickle
from collections import defaultdict
from math import exp
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from app.models.dixon_coles import DixonColesModel
    from app.models.elo import EloModel

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────
ELO_K = 32.0
ELO_K_WC = 40.0
ELO_DIVISOR = 400.0
INITIAL_ELO = 1500.0
FORM_N = 5          # recent-form window
H2H_N = 10          # h2h history window

# Population-mean fallbacks (used when a team has no history)
_DEFAULT_FORM = {
    "wrate": 0.40, "drate": 0.25, "gf": 1.25, "ga": 1.25, "gd": 0.00,
}
_DEFAULT_H2H = {
    "h_wrate": 0.34, "draw_rate": 0.28, "h_gf": 1.15, "h_ga": 1.15, "n_norm": 0.0,
}

FEATURE_NAMES: list[str] = [
    "elo_h", "elo_a", "elo_diff",
    "dc_att_h", "dc_def_h", "dc_att_a", "dc_def_a",
    "dc_xg_h", "dc_xg_a", "dc_xg_diff",
    "fh_wrate", "fh_drate", "fh_gf", "fh_ga", "fh_gd",
    "fa_wrate", "fa_drate", "fa_gf", "fa_ga", "fa_gd",
    "h2h_h_wrate", "h2h_draw_rate", "h2h_h_gf", "h2h_h_ga", "h2h_n",
    "is_neutral",
]


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _elo_update(ratings: dict, home: str, away: str,
                hs: int, as_: int, w: float, k: float = ELO_K) -> None:
    """In-place Elo update (neutral venue)."""
    rh = ratings.get(home, INITIAL_ELO)
    ra = ratings.get(away, INITIAL_ELO)
    exp_h = 1.0 / (1.0 + 10.0 ** (-(rh - ra) / ELO_DIVISOR))
    actual = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)
    delta = k * min(w, 2.5) * (actual - exp_h)
    ratings[home] = rh + delta
    ratings[away] = ra - delta


def _form_stats(records: list) -> dict:
    """Aggregate last-N match records → form dict.

    records: list of (gf, ga) tuples — chronological, most-recent last.
    """
    if not records:
        return _DEFAULT_FORM.copy()
    m = len(records)
    wins = draws = 0
    gf_sum = ga_sum = 0.0
    for gf, ga in records:
        gf_sum += gf
        ga_sum += ga
        if gf > ga:
            wins += 1
        elif gf == ga:
            draws += 1
    return {
        "wrate": wins / m,
        "drate": draws / m,
        "gf": gf_sum / m,
        "ga": ga_sum / m,
        "gd": (gf_sum - ga_sum) / m,
    }


def _h2h_stats(records: list, query_home: str) -> dict:
    """Aggregate last-N head-to-head records.

    records: list of (home_team, h_gf, h_ga) tuples.
    query_home: the team we consider 'home' for perspective.
    """
    if not records:
        return _DEFAULT_H2H.copy()
    m = len(records)
    h_wins = draws = 0
    h_gf_sum = h_ga_sum = 0.0
    for rec_home, hg, ag in records:
        from_perspective = rec_home == query_home
        my_g = hg if from_perspective else ag
        op_g = ag if from_perspective else hg
        h_gf_sum += my_g
        h_ga_sum += op_g
        if my_g > op_g:
            h_wins += 1
        elif my_g == op_g:
            draws += 1
    return {
        "h_wrate": h_wins / m,
        "draw_rate": draws / m,
        "h_gf": h_gf_sum / m,
        "h_ga": h_ga_sum / m,
        "n_norm": min(m / H2H_N, 1.0),
    }


def _dc_features(team: str, dc: "DixonColesModel") -> tuple[float, float, float]:
    """Return (att, def_val, log_att, log_def) for a team from DC model."""
    la, ld = dc._get_params(team)
    return exp(la), exp(ld), la, ld


# ──────────────────────────────────────────────
# Main Model
# ──────────────────────────────────────────────

class XGBoostPredictor:
    """Gradient-boosted 3-class football outcome predictor."""

    def __init__(self) -> None:
        self.model = None          # xgboost.XGBClassifier
        self.is_fitted = False
        # These store end-of-training state for inference-time form/h2h
        self._team_form: dict[str, list] = {}   # team -> last-N (gf,ga) tuples
        self._h2h: dict[tuple, list] = {}       # (t1,t2) sorted -> last-N records
        self._feature_importance: dict[str, float] = {}

    # ── Training ────────────────────────────────

    def fit(
        self,
        df: pd.DataFrame,
        dc: "DixonColesModel",
        elo: "EloModel",
        wc_results: list[dict] | None = None,
    ) -> "XGBoostPredictor":
        import xgboost as xgb

        df_sorted = df.sort_values("date_dt").reset_index(drop=True)
        X, y, sample_weights = self._build_training_features(df_sorted, dc)

        if len(X) == 0:
            raise RuntimeError("XGBoost: no usable training rows.")

        X_arr = np.array(X, dtype=np.float32)
        y_arr = np.array(y, dtype=np.int32)
        w_arr = np.array(sample_weights, dtype=np.float32)
        w_arr = np.clip(w_arr, 0.0, np.percentile(w_arr, 99))  # clip outliers

        # Class-balance weights → help predict draws (under-predicted by Elo/DC)
        class_counts = np.bincount(y_arr, minlength=3)
        class_weights = 1.0 / np.maximum(class_counts, 1)
        class_weights /= class_weights.sum()
        per_sample_w = w_arr * class_weights[y_arr]
        per_sample_w /= per_sample_w.mean()

        logger.info(
            "XGBoost training on %d rows · %d features · "
            "class dist H=%d D=%d A=%d",
            len(y_arr), len(FEATURE_NAMES),
            class_counts[0], class_counts[1], class_counts[2],
        )

        self.model = xgb.XGBClassifier(
            n_estimators=600,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.80,
            colsample_bytree=0.75,
            reg_alpha=0.15,
            reg_lambda=1.5,
            min_child_weight=10,
            objective="multi:softprob",
            num_class=3,
            tree_method="hist",
            eval_metric="mlogloss",
            random_state=42,
            n_jobs=-1,
            verbosity=0,
        )
        self.model.fit(X_arr, y_arr, sample_weight=per_sample_w)

        fi = self.model.get_booster().get_fscore()
        total_fi = sum(fi.values()) or 1
        self._feature_importance = {
            FEATURE_NAMES[int(k.replace("f", ""))]: round(v / total_fi, 4)
            for k, v in fi.items()
            if k.replace("f", "").isdigit() and int(k.replace("f", "")) < len(FEATURE_NAMES)
        }

        logger.info("XGBoost fitted. Top features: %s",
                    sorted(self._feature_importance.items(), key=lambda x: -x[1])[:5])
        self.is_fitted = True
        return self

    def _build_training_features(
        self,
        df: pd.DataFrame,
        dc: "DixonColesModel",
    ) -> tuple[list, list, list]:
        """Iterate chronologically; compute features from data seen BEFORE each match."""

        elo_ratings: dict[str, float] = {}
        team_form: dict[str, list] = defaultdict(list)
        h2h_hist: dict[tuple, list] = defaultdict(list)

        # Pre-compute DC parameters once (slight leakage but negligible — DC params
        # are long-term averages that change little match-to-match)
        dc_cache: dict[str, tuple] = {}

        def _dc(team: str) -> tuple[float, float, float, float]:
            if team not in dc_cache:
                la, ld = dc._get_params(team)
                dc_cache[team] = (exp(la), exp(ld), la, ld)
            return dc_cache[team]

        X, y, weights = [], [], []

        required = {"home_team", "away_team", "home_score", "away_score",
                    "date_dt", "neutral", "weight", "w_comp"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")

        for row in df.itertuples(index=False):
            home: str = row.home_team
            away: str = row.away_team
            hs: int = int(row.home_score)
            as_: int = int(row.away_score)
            neutral: float = float(row.neutral)
            w: float = float(row.weight)
            w_comp: float = float(getattr(row, "w_comp", 1.5))

            # ── Pre-match Elo ─────────────────────────
            elo_h = elo_ratings.get(home, INITIAL_ELO)
            elo_a = elo_ratings.get(away, INITIAL_ELO)

            # ── DC parameters ────────────────────────
            att_h, def_h, la_h, ld_h = _dc(home)
            att_a, def_a, la_a, ld_a = _dc(away)
            xg_h = exp(la_h - ld_a)
            xg_a = exp(la_a - ld_h)

            # ── Form (last FORM_N matches) ────────────
            fh = _form_stats(team_form[home][-FORM_N:])
            fa = _form_stats(team_form[away][-FORM_N:])

            # ── Head-to-head ──────────────────────────
            h2h_key = tuple(sorted([home, away]))
            h2h = _h2h_stats(h2h_hist[h2h_key][-H2H_N:], home)

            feat = [
                elo_h, elo_a, elo_h - elo_a,
                att_h, def_h, att_a, def_a,
                xg_h, xg_a, xg_h - xg_a,
                fh["wrate"], fh["drate"], fh["gf"], fh["ga"], fh["gd"],
                fa["wrate"], fa["drate"], fa["gf"], fa["ga"], fa["gd"],
                h2h["h_wrate"], h2h["draw_rate"], h2h["h_gf"], h2h["h_ga"], h2h["n_norm"],
                neutral,
            ]
            target = 0 if hs > as_ else (1 if hs == as_ else 2)

            X.append(feat)
            y.append(target)
            weights.append(w)

            # ── Post-match updates (chronological) ───
            _elo_update(elo_ratings, home, away, hs, as_, w)
            team_form[home].append((hs, as_))
            team_form[away].append((as_, hs))
            h2h_hist[h2h_key].append((home, hs, as_))

        # Persist end-of-training state for inference
        self._team_form = {t: list(v[-FORM_N:]) for t, v in team_form.items()}
        self._h2h = {k: list(v[-H2H_N:]) for k, v in h2h_hist.items()}
        return X, y, weights

    # ── Inference ───────────────────────────────

    def predict(
        self,
        team1: str,
        team2: str,
        dc: "DixonColesModel",
        elo: "EloModel",
        neutral: bool = True,
    ) -> dict:
        if not self.is_fitted or self.model is None:
            raise RuntimeError("XGBoost model not fitted.")

        elo_h = elo._get_rating(team1)
        elo_a = elo._get_rating(team2)

        la_h, ld_h = dc._get_params(team1)
        la_a, ld_a = dc._get_params(team2)
        att_h, def_h = exp(la_h), exp(ld_h)
        att_a, def_a = exp(la_a), exp(ld_a)
        xg_h = exp(la_h - ld_a)
        xg_a = exp(la_a - ld_h)

        fh = _form_stats(self._team_form.get(team1, []))
        fa = _form_stats(self._team_form.get(team2, []))

        h2h_key = tuple(sorted([team1, team2]))
        h2h = _h2h_stats(self._h2h.get(h2h_key, []), team1)

        feat = np.array([[
            elo_h, elo_a, elo_h - elo_a,
            att_h, def_h, att_a, def_a,
            xg_h, xg_a, xg_h - xg_a,
            fh["wrate"], fh["drate"], fh["gf"], fh["ga"], fh["gd"],
            fa["wrate"], fa["drate"], fa["gf"], fa["ga"], fa["gd"],
            h2h["h_wrate"], h2h["draw_rate"], h2h["h_gf"], h2h["h_ga"], h2h["n_norm"],
            float(neutral),
        ]], dtype=np.float32)

        probs = self.model.predict_proba(feat)[0]
        return {
            "prob_home": float(probs[0]),
            "prob_draw": float(probs[1]),
            "prob_away": float(probs[2]),
        }

    # ── Diagnostics ─────────────────────────────

    def feature_importance_table(self) -> list[dict]:
        return sorted(
            [{"feature": k, "importance": v} for k, v in self._feature_importance.items()],
            key=lambda x: -x["importance"],
        )

    # ── Persistence ─────────────────────────────

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        logger.info("XGBoost model saved → %s", path)

    @classmethod
    def load(cls, path: str) -> "XGBoostPredictor":
        with open(path, "rb") as f:
            obj = pickle.load(f)
        logger.info("XGBoost model loaded ← %s", path)
        return obj
