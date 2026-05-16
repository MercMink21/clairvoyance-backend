from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, field_validator


class PickCreate(BaseModel):
    sport: Literal["mlb", "nhl"]
    espn_game_id: Optional[str] = None
    game_date: Optional[date] = None
    bet_type: Literal["moneyline", "over", "under"]
    selection: str
    odds: int
    amount: float
    over_under: Optional[float] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    notes: Optional[str] = None


class PickOut(BaseModel):
    id: int
    sport: str
    espn_game_id: Optional[str]
    game_date: Optional[date]
    bet_type: str
    selection: str
    odds: int
    amount: float
    over_under: Optional[float]
    status: str
    home_team: Optional[str]
    away_team: Optional[str]
    home_score: Optional[int]
    away_score: Optional[int]
    notes: Optional[str]
    settled_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
