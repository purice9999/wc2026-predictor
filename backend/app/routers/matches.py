"""GET /matches — full fixture list with optional filters."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Query

from app.data.fixtures import FIXTURES, FIXTURES_BY_ID
from app.schemas.match import MatchListResponse, MatchResponse

router = APIRouter(prefix="/matches", tags=["matches"])


def _status(match_date: date, match_time: str) -> str:
    """Derive a simple status from match date vs today."""
    today = datetime.utcnow().date()
    if match_date < today:
        return "finished"
    if match_date == today:
        return "live"
    return "scheduled"


def _to_response(f: dict) -> MatchResponse:
    return MatchResponse(
        match_id=f["match_id"],
        date=f["date"],
        time=f["time"],
        home_team=f["home_team"],
        away_team=f["away_team"],
        group=f.get("group"),
        stage=f["stage"],
        matchday=f.get("matchday"),
        stadium=f["stadium"],
        city=f["city"],
        status=_status(f["date"], f["time"]),
    )


@router.get("", response_model=MatchListResponse)
def list_matches(
    stage: Optional[str] = Query(None, description="Filter by stage, e.g. 'Group Stage'"),
    group: Optional[str] = Query(None, description="Filter by group letter, e.g. 'A'"),
    date_from: Optional[date] = Query(None, description="Filter: date >= date_from"),
    date_to: Optional[date] = Query(None, description="Filter: date <= date_to"),
    status: Optional[str] = Query(None, description="Filter by status: scheduled|live|finished"),
    limit: int = Query(104, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> MatchListResponse:
    """Return the full WC 2026 fixture calendar with optional filters."""
    filtered = FIXTURES

    if stage:
        filtered = [f for f in filtered if f["stage"].lower() == stage.lower()]
    if group:
        filtered = [f for f in filtered if f.get("group") == group.upper()]
    if date_from:
        filtered = [f for f in filtered if f["date"] >= date_from]
    if date_to:
        filtered = [f for f in filtered if f["date"] <= date_to]
    if status:
        filtered = [f for f in filtered if _status(f["date"], f["time"]) == status.lower()]

    total = len(filtered)
    page = filtered[offset : offset + limit]
    return MatchListResponse(matches=[_to_response(f) for f in page], total=total)


@router.get("/{match_id}", response_model=MatchResponse)
def get_match(match_id: str) -> MatchResponse:
    """Return a single match by its ID."""
    from fastapi import HTTPException

    fixture = FIXTURES_BY_ID.get(match_id)
    if not fixture:
        raise HTTPException(status_code=404, detail=f"Match '{match_id}' not found.")
    return _to_response(fixture)
