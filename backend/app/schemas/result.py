"""Pydantic schemas for match results."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ResultCreate(BaseModel):
    home_score: int = Field(..., ge=0, le=30)
    away_score: int = Field(..., ge=0, le=30)


class ResultResponse(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    stage: str
    home_score: int
    away_score: int
    actual_winner: str       # "home" | "draw" | "away"
    predicted_winner: Optional[str] = None
    correct: Optional[bool] = None
    prob_home: float = 0.0
    prob_draw: float = 0.0
    prob_away: float = 0.0
    recorded_at: str


class AccuracyResponse(BaseModel):
    total: int
    with_prediction: int
    correct: int
    accuracy: float
