from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.moneypuck import MoneyPuckTeam
from app.models.nhl_game import NHLGame
from app.models.nhl_stat import NHLGoalieStat, NHLSkaterStat, NHLTeamStat
from app.schemas.nhl import NHLGameOut, NHLGoalieStatOut, NHLSkaterStatOut, NHLTeamStatOut

router = APIRouter(prefix="/nhl", tags=["NHL"])


@router.get("/schedule", response_model=list[NHLGameOut])
async def get_nhl_schedule(
    game_date: date = Query(default_factory=date.today),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NHLGame)
        .where(NHLGame.game_date == game_date)
        .order_by(NHLGame.game_time_utc)
    )
    return result.scalars().all()


@router.get("/teams", response_model=list[NHLTeamStatOut])
async def get_team_stats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(NHLTeamStat)
        .where(
            NHLTeamStat.season == settings.NHL_SEASON,
            NHLTeamStat.game_type_id == settings.NHL_GAME_TYPE,
        )
        .order_by(NHLTeamStat.wins.desc())
    )
    return result.scalars().all()


@router.get("/goalies", response_model=list[NHLGoalieStatOut])
async def get_goalie_stats(
    min_games: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NHLGoalieStat)
        .where(
            NHLGoalieStat.season == settings.NHL_SEASON,
            NHLGoalieStat.game_type_id == settings.NHL_GAME_TYPE,
            NHLGoalieStat.games_played >= min_games,
        )
        .order_by(NHLGoalieStat.overall_save_pct.desc())
    )
    return result.scalars().all()


@router.get("/skaters", response_model=list[NHLSkaterStatOut])
async def get_skater_stats(
    team: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    q = select(NHLSkaterStat).where(
        NHLSkaterStat.season == settings.NHL_SEASON,
        NHLSkaterStat.game_type_id == settings.NHL_GAME_TYPE,
    )
    if team:
        q = q.where(NHLSkaterStat.team_abbrev == team.upper())
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/moneypuck")
async def get_moneypuck_teams(
    situation: str = Query(default="all"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MoneyPuckTeam)
        .where(MoneyPuckTeam.situation == situation.lower())
        .order_by(MoneyPuckTeam.x_goals_pct.desc())
    )
    return result.scalars().all()
