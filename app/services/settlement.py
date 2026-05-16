from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.pick import Pick
from app.models.team_elo import TeamELO
from app.scrapers.espn import fetch_mlb_final_scores, fetch_nhl_final_scores
from app.services.elo import DEFAULT_RATING, update_ratings

logger = logging.getLogger(__name__)


async def settle_pending_picks(target_date: date) -> dict:
    """Settle all pending picks (MLB + NHL) whose game_date matches target_date."""
    mlb_scores = await fetch_mlb_final_scores(target_date)
    nhl_scores = await fetch_nhl_final_scores(target_date)

    scores_by_id: dict[str, dict] = {s["espn_id"]: s for s in mlb_scores + nhl_scores}
    if not scores_by_id:
        logger.info(f"Settlement: no final scores for {target_date}")
        return {"settled": 0, "errors": 0}

    settled = errors = 0

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Pick).where(
                Pick.status == "pending",
                Pick.game_date == target_date,
            )
        )
        picks = result.scalars().all()

        for pick in picks:
            try:
                score = scores_by_id.get(pick.espn_game_id)
                if not score:
                    continue
                pick.status = _outcome(pick, score)
                pick.home_score = score["home_score"]
                pick.away_score = score["away_score"]
                pick.settled_at = datetime.now(timezone.utc)
                settled += 1

                if pick.bet_type == "moneyline":
                    await _update_elo(session, score, pick.sport)
            except Exception as e:
                logger.error(f"Settlement error on pick {pick.id}: {e}")
                errors += 1

        await session.commit()

    return {"settled": settled, "errors": errors}


def _outcome(pick: Pick, score: dict) -> str:
    home = score["home_score"]
    away = score["away_score"]
    total = home + away

    if pick.bet_type == "moneyline":
        if home == away:
            return "push"
        winner = score["home_team"] if home > away else score["away_team"]
        return "won" if pick.selection == winner else "lost"

    if pick.bet_type in ("over", "under"):
        line = pick.over_under
        if line is None:
            return "void"
        if total == line:
            return "push"
        over_wins = total > line
        return "won" if (pick.bet_type == "over") == over_wins else "lost"

    return "void"


async def _update_elo(session: AsyncSession, score: dict, sport: str) -> None:
    home, away = score["home_score"], score["away_score"]
    if home == away:
        return

    winner_team = score["home_team"] if home > away else score["away_team"]
    loser_team = score["away_team"] if winner_team == score["home_team"] else score["home_team"]

    winner_elo = await _get_or_create(session, winner_team, sport)
    loser_elo = await _get_or_create(session, loser_team, sport)

    winner_elo.rating, loser_elo.rating = update_ratings(winner_elo.rating, loser_elo.rating)
    winner_elo.games_played += 1
    loser_elo.games_played += 1


async def _get_or_create(session: AsyncSession, team: str, sport: str) -> TeamELO:
    result = await session.execute(
        select(TeamELO).where(TeamELO.team == team, TeamELO.sport == sport)
    )
    elo = result.scalar_one_or_none()
    if not elo:
        elo = TeamELO(team=team, sport=sport, rating=DEFAULT_RATING)
        session.add(elo)
        await session.flush()
    return elo
