from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NHLGame(Base):
    __tablename__ = "nhl_games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    espn_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    game_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    game_time_utc: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="STATUS_SCHEDULED")
    home_team: Mapped[str] = mapped_column(String(10), nullable=False)
    away_team: Mapped[str] = mapped_column(String(10), nullable=False)
    home_score: Mapped[Optional[int]] = mapped_column(Integer)
    away_score: Mapped[Optional[int]] = mapped_column(Integer)
    home_moneyline: Mapped[Optional[int]] = mapped_column(Integer)
    away_moneyline: Mapped[Optional[int]] = mapped_column(Integer)
    over_under: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
