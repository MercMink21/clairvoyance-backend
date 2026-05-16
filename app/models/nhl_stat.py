from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NHLTeamStat(Base):
    __tablename__ = "nhl_team_stats"
    __table_args__ = (
        UniqueConstraint("team_id", "season", "game_type_id", name="uq_nhl_team_season"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(Integer, nullable=False)
    team_abbrev: Mapped[str] = mapped_column(String(10), nullable=False)
    team_name: Mapped[Optional[str]] = mapped_column(String(60))
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    game_type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    games_played: Mapped[Optional[int]] = mapped_column(Integer)
    wins: Mapped[Optional[int]] = mapped_column(Integer)
    losses: Mapped[Optional[int]] = mapped_column(Integer)
    ot_losses: Mapped[Optional[int]] = mapped_column(Integer)
    goals_for: Mapped[Optional[int]] = mapped_column(Integer)
    goals_against: Mapped[Optional[int]] = mapped_column(Integer)
    goals_for_per_game: Mapped[Optional[float]] = mapped_column(Float)
    goals_against_per_game: Mapped[Optional[float]] = mapped_column(Float)
    pp_pct: Mapped[Optional[float]] = mapped_column(Float)
    pk_pct: Mapped[Optional[float]] = mapped_column(Float)
    shots_for_per_game: Mapped[Optional[float]] = mapped_column(Float)
    shots_against_per_game: Mapped[Optional[float]] = mapped_column(Float)
    offensive_zone_time_pct: Mapped[Optional[float]] = mapped_column(Float)
    defensive_zone_time_pct: Mapped[Optional[float]] = mapped_column(Float)
    neutral_zone_time_pct: Mapped[Optional[float]] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class NHLGoalieStat(Base):
    __tablename__ = "nhl_goalie_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "game_type_id", name="uq_nhl_goalie_season"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(Integer, nullable=False)
    player_name: Mapped[Optional[str]] = mapped_column(String(100))
    team_abbrev: Mapped[Optional[str]] = mapped_column(String(10))
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    game_type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    games_played: Mapped[Optional[int]] = mapped_column(Integer)
    saves_even_strength: Mapped[Optional[int]] = mapped_column(Integer)
    shots_against_even_strength: Mapped[Optional[int]] = mapped_column(Integer)
    save_pct_even_strength: Mapped[Optional[float]] = mapped_column(Float)
    saves_power_play: Mapped[Optional[int]] = mapped_column(Integer)
    shots_against_power_play: Mapped[Optional[int]] = mapped_column(Integer)
    save_pct_power_play: Mapped[Optional[float]] = mapped_column(Float)
    saves_short_handed: Mapped[Optional[int]] = mapped_column(Integer)
    shots_against_short_handed: Mapped[Optional[int]] = mapped_column(Integer)
    save_pct_short_handed: Mapped[Optional[float]] = mapped_column(Float)
    overall_save_pct: Mapped[Optional[float]] = mapped_column(Float)
    goals_against_avg: Mapped[Optional[float]] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class NHLSkaterStat(Base):
    __tablename__ = "nhl_skater_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "game_type_id", name="uq_nhl_skater_season"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(Integer, nullable=False)
    player_name: Mapped[Optional[str]] = mapped_column(String(100))
    team_abbrev: Mapped[Optional[str]] = mapped_column(String(10))
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    game_type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    shots_wrist: Mapped[Optional[int]] = mapped_column(Integer)
    shots_snap: Mapped[Optional[int]] = mapped_column(Integer)
    shots_slap: Mapped[Optional[int]] = mapped_column(Integer)
    shots_backhand: Mapped[Optional[int]] = mapped_column(Integer)
    shots_tip: Mapped[Optional[int]] = mapped_column(Integer)
    shots_deflected: Mapped[Optional[int]] = mapped_column(Integer)
    shots_wrap_around: Mapped[Optional[int]] = mapped_column(Integer)
    avg_speed: Mapped[Optional[float]] = mapped_column(Float)
    top_speed: Mapped[Optional[float]] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
