from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Pick(Base):
    __tablename__ = "picks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sport: Mapped[str] = mapped_column(String(10), nullable=False)
    espn_game_id: Mapped[Optional[str]] = mapped_column(String(20))
    game_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    bet_type: Mapped[str] = mapped_column(String(20), nullable=False)  # moneyline, over, under
    selection: Mapped[str] = mapped_column(String(50), nullable=False)
    odds: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    over_under: Mapped[Optional[float]] = mapped_column(Float)  # line stored at bet creation
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending, won, lost, push, void
    home_team: Mapped[Optional[str]] = mapped_column(String(10))
    away_team: Mapped[Optional[str]] = mapped_column(String(10))
    home_score: Mapped[Optional[int]] = mapped_column(Integer)
    away_score: Mapped[Optional[int]] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
