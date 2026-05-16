from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MoneyPuckTeam(Base):
    __tablename__ = "moneypuck_teams"
    __table_args__ = (
        UniqueConstraint("team", "season", "situation", name="uq_mp_team_season_situation"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team: Mapped[str] = mapped_column(String(10), nullable=False)
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    situation: Mapped[str] = mapped_column(String(20), default="all")
    games_played: Mapped[Optional[int]] = mapped_column(Integer)
    shots_for_60: Mapped[Optional[float]] = mapped_column(Float)
    shots_against_60: Mapped[Optional[float]] = mapped_column(Float)
    goals_for_60: Mapped[Optional[float]] = mapped_column(Float)
    goals_against_60: Mapped[Optional[float]] = mapped_column(Float)
    x_goals_for_60: Mapped[Optional[float]] = mapped_column(Float)
    x_goals_against_60: Mapped[Optional[float]] = mapped_column(Float)
    x_goals_pct: Mapped[Optional[float]] = mapped_column(Float)
    corsi_for_pct: Mapped[Optional[float]] = mapped_column(Float)
    fenwick_for_pct: Mapped[Optional[float]] = mapped_column(Float)
    shooting_pct: Mapped[Optional[float]] = mapped_column(Float)
    save_pct: Mapped[Optional[float]] = mapped_column(Float)
    pdo: Mapped[Optional[float]] = mapped_column(Float)
    goals_for: Mapped[Optional[int]] = mapped_column(Integer)
    goals_against: Mapped[Optional[int]] = mapped_column(Integer)
    x_goals_for: Mapped[Optional[float]] = mapped_column(Float)
    x_goals_against: Mapped[Optional[float]] = mapped_column(Float)
    high_danger_goals_for: Mapped[Optional[int]] = mapped_column(Integer)
    high_danger_goals_against: Mapped[Optional[int]] = mapped_column(Integer)
    medium_danger_goals_for: Mapped[Optional[int]] = mapped_column(Integer)
    medium_danger_goals_against: Mapped[Optional[int]] = mapped_column(Integer)
    low_danger_goals_for: Mapped[Optional[int]] = mapped_column(Integer)
    low_danger_goals_against: Mapped[Optional[int]] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
