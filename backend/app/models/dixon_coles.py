"""Dixon-Coles bivariate Poisson model with shrinkage regularisation."""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy.stats import poisson

from app.data.tournament_config import (
    MAX_GOALS,
    SHOTS_CONVERSION_RATE,
    SHRINKAGE_BASE,
    SHRINKAGE_BONUS,
    SHRINKAGE_MIN_WEIGHT,
)

logger = logging.getLogger(__name__)


def _dc_tau(x, y, lam, mu, rho):
    tau = np.ones(len(x), dtype=np.float64)
    m00 = (x == 0) & (y == 0)
    m01 = (x == 0) & (y == 1)
    m10 = (x == 1) & (y == 0)
    m11 = (x == 1) & (y == 1)
    tau[m00] = 1.0 - lam[m00] * mu[m00] * rho
    tau[m01] = 1.0 + lam[m01] * rho
    tau[m10] = 1.0 + mu[m10] * rho
    tau[m11] = 1.0 - rho
    return np.maximum(tau, 1e-10)


def _neg_log_likelihood(params, home_idx, away_idx, home_g, away_g,
                        is_neutral, weights, n_teams, shrinkage_weights):
    log_att = params[:n_teams]
    log_def = params[n_teams: 2 * n_teams]
    log_hfa = params[2 * n_teams]
    rho = params[2 * n_teams + 1]

    log_lam = log_att[home_idx] - log_def[away_idx] + log_hfa * (1.0 - is_neutral)
    log_mu = log_att[away_idx] - log_def[home_idx]
    lam = np.exp(log_lam)
    mu = np.exp(log_mu)

    ll_h = home_g * log_lam - lam - gammaln(home_g + 1)
    ll_a = away_g * log_mu - mu - gammaln(away_g + 1)
    tau = _dc_tau(home_g, away_g, lam, mu, rho)
    total_ll = np.sum(weights * (np.log(tau) + ll_h + ll_a))
    reg = np.dot(shrinkage_weights, log_att ** 2) + np.dot(shrinkage_weights, log_def ** 2)
    return -(total_ll - reg)


class DixonColesModel:
    def __init__(self, max_goals: int = MAX_GOALS) -> None:
        self.max_goals = max_goals
        self.teams: list[str] = []
        self.team_to_idx: dict[str, int] = {}
        self.log_attack: np.ndarray = np.array([])
        self.log_defense: np.ndarray = np.array([])
        self.log_home_adv: float = float(np.log(1.15))
        self.rho: float = -0.1
        self.is_fitted: bool = False
        self._avg_log_att: float = 0.0
        self._avg_log_def: float = 0.0
        self.team_match_weights: dict[str, float] = {}

    def fit(self, matches: pd.DataFrame) -> "DixonColesModel":
        teams = sorted(set(matches["home_team"]) | set(matches["away_team"]))
        self.teams = teams
        self.team_to_idx = {t: i for i, t in enumerate(teams)}
        n = len(teams)

        home_idx = np.array([self.team_to_idx[t] for t in matches["home_team"]])
        away_idx = np.array([self.team_to_idx[t] for t in matches["away_team"]])
        # home_g_dc / away_g_dc sunt setate de apply_xg_hybrid (Sub-faza B).
        # Cand lipsesc, comportamentul e identic cu DC pur.
        if "home_g_dc" in matches.columns:
            home_g = matches["home_g_dc"].values.astype(np.float64)
            away_g = matches["away_g_dc"].values.astype(np.float64)
        else:
            home_g = matches["home_score"].values.astype(np.float64)
            away_g = matches["away_score"].values.astype(np.float64)
        neutral = matches["neutral"].values.astype(np.float64)
        weights = matches["weight"].values.astype(np.float64)

        home_w = matches.groupby("home_team")["weight"].sum()
        away_w = matches.groupby("away_team")["weight"].sum()
        total_w = home_w.add(away_w, fill_value=0.0)
        self.team_match_weights = total_w.to_dict()
        team_w_arr = np.array([self.team_match_weights.get(t, 0.0) for t in teams])
        shrinkage = SHRINKAGE_BASE + SHRINKAGE_BONUS / np.maximum(team_w_arr, SHRINKAGE_MIN_WEIGHT)

        x0 = np.zeros(2 * n + 2)
        x0[2 * n] = np.log(1.15)
        x0[2 * n + 1] = -0.1
        bounds = [(-3.0, 3.0)] * n + [(-3.0, 3.0)] * n + [(np.log(0.8), np.log(2.0))] + [(-1.0, 0.5)]

        logger.info("Fitting Dixon-Coles on %d matches, %d teams…", len(matches), n)
        result = minimize(
            _neg_log_likelihood, x0,
            args=(home_idx, away_idx, home_g, away_g, neutral, weights, n, shrinkage),
            method="L-BFGS-B", bounds=bounds,
            options={"maxiter": 3000, "maxfun": 100_000, "ftol": 1e-9, "gtol": 1e-6},
        )
        if not result.success:
            logger.warning("Optimiser did not fully converge: %s", result.message)

        self.log_attack = result.x[:n]
        self.log_defense = result.x[n: 2 * n]
        self.log_home_adv = float(result.x[2 * n])
        self.rho = float(result.x[2 * n + 1])
        self._avg_log_att = float(np.mean(self.log_attack))
        self._avg_log_def = float(np.mean(self.log_defense))
        self.is_fitted = True
        logger.info("Fitting complete. rho=%.4f  home_adv=%.3f", self.rho, np.exp(self.log_home_adv))
        return self

    def _get_params(self, team: str) -> tuple[float, float]:
        idx = self.team_to_idx.get(team)
        if idx is not None:
            return float(self.log_attack[idx]), float(self.log_defense[idx])
        return self._avg_log_att, self._avg_log_def

    def _get_lambdas(self, team1: str, team2: str, neutral: bool = True) -> tuple[float, float]:
        if not self.is_fitted:
            raise RuntimeError("Model not fitted.")
        la1, ld1 = self._get_params(team1)
        la2, ld2 = self._get_params(team2)
        hfa = 0.0 if neutral else self.log_home_adv
        return float(np.exp(la1 - ld2 + hfa)), float(np.exp(la2 - ld1))

    def score_matrix(self, lam1: float, lam2: float) -> np.ndarray:
        g = np.arange(self.max_goals + 1)
        mat = np.outer(poisson.pmf(g, lam1), poisson.pmf(g, lam2))
        mat[0, 0] *= max(1.0 - lam1 * lam2 * self.rho, 1e-10)
        mat[0, 1] *= max(1.0 + lam1 * self.rho, 1e-10)
        mat[1, 0] *= max(1.0 + lam2 * self.rho, 1e-10)
        mat[1, 1] *= max(1.0 - self.rho, 1e-10)
        mat /= mat.sum()
        return mat

    def predict_match_full(self, team1: str, team2: str, neutral: bool = True) -> dict:
        lam1, lam2 = self._get_lambdas(team1, team2, neutral)
        mat = self.score_matrix(lam1, lam2)

        prob1 = float(np.sum(np.tril(mat, -1)))
        prob_draw = float(np.trace(mat))
        prob2 = float(np.sum(np.triu(mat, 1)))
        row, col = np.unravel_index(np.argmax(mat), mat.shape)

        p_no_t1 = float(mat[:, 0].sum())
        p_no_t2 = float(mat[0, :].sum())
        btts_yes = max(1.0 - (p_no_t1 + p_no_t2 - float(mat[0, 0])), 0.0)

        n = mat.shape[0]
        over_15 = float(np.clip(sum(mat[i, j] for i in range(n) for j in range(n) if i + j > 1.5), 0, 1))
        over_25 = float(np.clip(sum(mat[i, j] for i in range(n) for j in range(n) if i + j > 2.5), 0, 1))
        over_35 = float(np.clip(sum(mat[i, j] for i in range(n) for j in range(n) if i + j > 3.5), 0, 1))

        flat = mat.ravel()
        top_idx = np.argsort(flat)[::-1][:5]
        size = mat.shape[0]
        top_scorelines = [(int(i // size), int(i % size), float(flat[i])) for i in top_idx]

        return {
            "prob_home": prob1,
            "prob_draw": prob_draw,
            "prob_away": prob2,
            "xg_home": round(lam1, 3),
            "xg_away": round(lam2, 3),
            "most_likely_score": {"home": int(row), "away": int(col)},
            "top_scorelines": [{"home": h, "away": a, "prob": round(p, 4)} for h, a, p in top_scorelines],
            "btts_yes": round(btts_yes, 4),
            "btts_no": round(1 - btts_yes, 4),
            "over_1_5": round(over_15, 4),
            "under_1_5": round(1 - over_15, 4),
            "over_2_5": round(over_25, 4),
            "under_2_5": round(1 - over_25, 4),
            "over_3_5": round(over_35, 4),
            "under_3_5": round(1 - over_35, 4),
            "cs_home": round(float(mat[:, 0].sum()), 4),
            "cs_away": round(float(mat[0, :].sum()), 4),
            "sot_home": round(lam1 / SHOTS_CONVERSION_RATE, 2),
            "sot_away": round(lam2 / SHOTS_CONVERSION_RATE, 2),
        }

    def simulate_match(self, team1: str, team2: str, neutral: bool = True,
                       is_knockout: bool = False, rng=None) -> tuple[int, int, str]:
        if rng is None:
            rng = np.random.default_rng()
        lam1, lam2 = self._get_lambdas(team1, team2, neutral)
        mat = self.score_matrix(lam1, lam2)
        probs = mat.ravel()
        probs = probs / probs.sum()
        idx = rng.choice(len(probs), p=probs)
        g1, g2 = divmod(idx, self.max_goals + 1)

        if g1 != g2 or not is_knockout:
            if g1 > g2:
                return g1, g2, team1
            elif g2 > g1:
                return g1, g2, team2
            return g1, g2, "draw"

        et_g1 = rng.poisson(lam1 / 3.0)
        et_g2 = rng.poisson(lam2 / 3.0)
        t1, t2 = g1 + et_g1, g2 + et_g2
        if t1 != t2:
            return t1, t2, (team1 if t1 > t2 else team2)
        pen_p1 = lam1 / (lam1 + lam2)
        winner = team1 if rng.random() < pen_p1 else team2
        return t1, t2, winner

    def team_strengths(self) -> list[dict]:
        rows = []
        for team in self.teams:
            idx = self.team_to_idx[team]
            att = float(np.exp(self.log_attack[idx]))
            deff = float(np.exp(self.log_defense[idx]))
            rows.append({
                "team": team,
                "attack": round(att, 3),
                "defense": round(deff, 3),
                "overall": round(att / deff, 3),
                "weighted_matches": round(self.team_match_weights.get(team, 0.0), 1),
            })
        return sorted(rows, key=lambda r: r["overall"], reverse=True)

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        logger.info("DC model saved to %s", path)

    @classmethod
    def load(cls, path: str) -> "DixonColesModel":
        with open(path, "rb") as f:
            return pickle.load(f)
