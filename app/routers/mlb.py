from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.mlb_game import MLBGame
from app.models.team_elo import TeamELO
from app.schemas.mlb import MLBGameOut

router = APIRouter(prefix="/mlb", tags=["MLB"])


@router.get("/schedule", response_model=list[MLBGameOut])
async def get_schedule(
    game_date: date = Query(default_factory=date.today),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MLBGame)
        .where(MLBGame.game_date == game_date)
        .order_by(MLBGame.game_time_utc)
    )
    return result.scalars().all()


@router.get("/games/{espn_id}", response_model=MLBGameOut)
async def get_game(espn_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MLBGame).where(MLBGame.espn_id == espn_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


@router.get("/elo")
async def get_mlb_elo(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TeamELO)
        .where(TeamELO.sport == "mlb")
        .order_by(TeamELO.rating.desc())
    )
    rows = result.scalars().all()
    return [
        {
            "team": r.team,
            "rating": r.rating,
            "games_played": r.games_played,
            "last_game_date": r.last_game_date,
        }
        for r in rows
    ]
