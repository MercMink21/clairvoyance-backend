from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class MLBGameOut(BaseModel):
    id: int
    espn_id: str
    game_date: Optional[date]
    game_time_utc: Optional[datetime]
    status: str
    home_team: str
    away_team: str
    home_score: Optional[int]
    away_score: Optional[int]
    home_moneyline: Optional[int]
    away_moneyline: Optional[int]
    over_under: Optional[float]
    home_pitcher: Optional[str]
    away_pitcher: Optional[str]
    venue: Optional[str]

    model_config = {"from_attributes": True}
