from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class NHLGameOut(BaseModel):
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

    model_config = {"from_attributes": True}


class NHLTeamStatOut(BaseModel):
    id: int
    team_id: int
    team_abbrev: str
    team_name: Optional[str]
    season: str
    game_type_id: int
    games_played: Optional[int]
    wins: Optional[int]
    losses: Optional[int]
    ot_losses: Optional[int]
    goals_for: Optional[int]
    goals_against: Optional[int]
    goals_for_per_game: Optional[float]
    goals_against_per_game: Optional[float]
    pp_pct: Optional[float]
    pk_pct: Optional[float]
    shots_for_per_game: Optional[float]
    shots_against_per_game: Optional[float]
    offensive_zone_time_pct: Optional[float]
    defensive_zone_time_pct: Optional[float]
    neutral_zone_time_pct: Optional[float]

    model_config = {"from_attributes": True}


class NHLGoalieStatOut(BaseModel):
    id: int
    player_id: int
    player_name: Optional[str]
    team_abbrev: Optional[str]
    games_played: Optional[int]
    saves_even_strength: Optional[int]
    save_pct_even_strength: Optional[float]
    saves_power_play: Optional[int]
    save_pct_power_play: Optional[float]
    saves_short_handed: Optional[int]
    save_pct_short_handed: Optional[float]
    overall_save_pct: Optional[float]
    goals_against_avg: Optional[float]

    model_config = {"from_attributes": True}


class NHLSkaterStatOut(BaseModel):
    id: int
    player_id: int
    player_name: Optional[str]
    team_abbrev: Optional[str]
    shots_wrist: Optional[int]
    shots_snap: Optional[int]
    shots_slap: Optional[int]
    shots_backhand: Optional[int]
    shots_tip: Optional[int]
    shots_deflected: Optional[int]
    shots_wrap_around: Optional[int]
    avg_speed: Optional[float]
    top_speed: Optional[float]

    model_config = {"from_attributes": True}
