"""Pydantic schemas for match-related API responses."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class MatchResponse(BaseModel):
    match_id: str
    date: date
    time: str
    home_team: str
    away_team: str
    group: Optional[str] = None
    stage: str
    matchday: Optional[int] = None
    stadium: str
    city: str
    status: str  # "scheduled" | "live" | "finished"

    model_config = {"from_attributes": True}


class MatchListResponse(BaseModel):
    matches: list[MatchResponse]
    total: int
