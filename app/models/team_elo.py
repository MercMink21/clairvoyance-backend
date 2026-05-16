from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TeamELO(Base):
    __tablename__ = "team_elo"
    __table_args__ = (
        UniqueConstraint("team", "sport", name="uq_team_sport_elo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team: Mapped[str] = mapped_column(String(10), nullable=False)
    sport: Mapped[str] = mapped_column(String(10), nullable=False)
    rating: Mapped[float] = mapped_column(Float, default=1500.0, nullable=False)
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    last_game_date: Mapped[Optional[date]] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
