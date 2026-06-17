"""Pydantic response schemas for the /predict endpoint."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class MostLikelyScore(BaseModel):
    home: int
    away: int


class Scoreline(BaseModel):
    home: int
    away: int
    prob: float


class PredictionResponse(BaseModel):
    match_id: str
    home_team: str
    away_team: str

    # Ensemble-blended win probabilities
    prob_home: float
    prob_draw: float
    prob_away: float

    # Dixon-Coles expected goals
    xg_home: float
    xg_away: float
    most_likely_score: MostLikelyScore
    top_scorelines: list[Scoreline]

    # Goal markets
    btts_yes: float
    btts_no: float
    over_1_5: float
    under_1_5: float
    over_2_5: float
    under_2_5: float
    over_3_5: float
    under_3_5: float

    # Defensive markets
    cs_home: float
    cs_away: float

    # Shots on target (proxy via xG / conversion rate)
    sot_home: float
    sot_away: float

    # Elo context
    elo_home: float
    elo_away: float

    # Meta
    model_used: str
    value_bet: Optional[str] = None
    explanation: str
