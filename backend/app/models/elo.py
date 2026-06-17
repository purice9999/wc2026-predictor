"""Elo rating model + Dixon-Coles/Elo ensemble."""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_K = 32.0
ELO_DIVISOR = 400.0
INITIAL_RATING = 1500.0
DRAW_MARGIN = 0.12
# Cap normalized weight for Elo so k_eff stays in [K*0.2, K*2.5].
# Normalization can inflate competitive-match weights 5-10x when friendlies
# are heavily discounted; without this cap Elo swings become unrealistic.
ELO_WEIGHT_CAP = 2.5


class EloModel:
    def __init__(self, k: float = DEFAULT_K) -> None:
        self.k = k
        self.ratings: dict[str, float] = {}
        self.is_fitted = False

    def _get_rating(self, team: str) -> float:
        return self.ratings.get(team, INITIAL_RATING)

    def fit(self, matches: pd.DataFrame) -> "EloModel":
        self.ratings = {}
        for _, row in matches.sort_values("date_dt").iterrows():
            h, a = row["home_team"], row["away_team"]
            rh, ra = self._get_rating(h), self._get_rating(a)
            hfa = 0.0 if bool(row.get("neutral", True)) else 100.0
            expected_h = 1.0 / (1.0 + 10.0 ** (-(rh + hfa - ra) / ELO_DIVISOR))

            hs, as_ = int(row["home_score"]), int(row["away_score"])
            actual_h = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)
            # Cap weight to prevent extreme K swings from normalization artefacts
            w = min(float(row.get("weight", 1.0)), ELO_WEIGHT_CAP)
            delta = self.k * w * (actual_h - expected_h)
            self.ratings[h] = rh + delta
            self.ratings[a] = ra - delta

        self.is_fitted = True
        logger.info("Elo model fitted. %d teams rated.", len(self.ratings))
        return self

    def predict(self, team1: str, team2: str, neutral: bool = True) -> dict:
        r1 = self._get_rating(team1)
        r2 = self._get_rating(team2)
        hfa = 0.0 if neutral else 100.0
        e1 = 1.0 / (1.0 + 10.0 ** (-(r1 + hfa - r2) / ELO_DIVISOR))
        draw_p = max(DRAW_MARGIN * (1.0 - abs(e1 - 0.5) * 2.0), 0.0)
        remaining = 1.0 - draw_p
        return {
            "prob_home": round(remaining * e1, 4),
            "prob_draw": round(draw_p, 4),
            "prob_away": round(remaining * (1.0 - e1), 4),
            "elo_home": round(r1, 1),
            "elo_away": round(r2, 1),
        }

    def ratings_table(self) -> list[dict]:
        return sorted(
            [{"team": t, "elo": round(r, 1)} for t, r in self.ratings.items()],
            key=lambda x: x["elo"], reverse=True,
        )

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path: str) -> "EloModel":
        with open(path, "rb") as f:
            return pickle.load(f)
