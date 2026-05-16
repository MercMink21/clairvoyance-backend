from __future__ import annotations

"""
Model-driven pick suggestions using ELO, NHL Edge stats, and MoneyPuck data.

MLB: ELO differential + pitcher advantage → implied probability → edge vs moneyline
NHL: ELO differential + MoneyPuck xGoals% + goalie save% → implied probability → edge
"""

import logging
import math
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mlb_game import MLBGame
from app.models.moneypuck import MoneyPuckTeam
from app.models.nhl_game import NHLGame
from app.models.nhl_stat import NHLGoalieStat, NHLTeamStat
from app.models.team_elo import TeamELO
from app.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_ELO = 1500.0
_MIN_EDGE = 3.0  # minimum % edge to recommend a bet


# ---------------------------------------------------------------------------
# American odds helpers
# ---------------------------------------------------------------------------

def american_to_implied(odds: int) -> float:
    """Convert American moneyline to implied probability (0–1)."""
    if odds >= 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def implied_to_american(prob: float) -> int:
    """Convert win probability to American moneyline."""
    prob = max(0.01, min(0.99, prob))
    if prob >= 0.5:
        return -round(prob / (1 - prob) * 100)
    return round((1 - prob) / prob * 100)


def edge_pct(model_prob: float, market_odds: int) -> float:
    """Edge = model implied probability minus market implied probability (percentage points)."""
    return (model_prob - american_to_implied(market_odds)) * 100


# ---------------------------------------------------------------------------
# ELO win probability
# ---------------------------------------------------------------------------

def elo_win_prob(home_elo: float, away_elo: float, home_advantage: float = 35.0) -> float:
    """Expected win probability for home team given ELO ratings."""
    return 1 / (1 + 10 ** ((away_elo - (home_elo + home_advantage)) / 400))


# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------

async def _get_elo(db: AsyncSession, team: str, sport: str) -> float:
    res = await db.execute(
        select(TeamELO).where(TeamELO.team == team, TeamELO.sport == sport)
    )
    elo = res.scalar_one_or_none()
    return elo.rating if elo else _DEFAULT_ELO


async def _get_moneypuck(db: AsyncSession, team: str) -> Optional[MoneyPuckTeam]:
    res = await db.execute(
        select(MoneyPuckTeam).where(
            MoneyPuckTeam.team == team,
            MoneyPuckTeam.situation == "all",
        ).order_by(MoneyPuckTeam.id.desc()).limit(1)
    )
    return res.scalar_one_or_none()


async def _get_nhl_team_stat(db: AsyncSession, team: str) -> Optional[NHLTeamStat]:
    res = await db.execute(
        select(NHLTeamStat).where(
            NHLTeamStat.team_abbrev == team,
            NHLTeamStat.season == settings.NHL_SEASON,
            NHLTeamStat.game_type_id == settings.NHL_GAME_TYPE,
        )
    )
    return res.scalar_one_or_none()


async def _get_starting_goalie_save_pct(db: AsyncSession, team: str) -> Optional[float]:
    """Best overall_save_pct among goalies with most games played for this team."""
    res = await db.execute(
        select(NHLGoalieStat)
        .where(
            NHLGoalieStat.team_abbrev == team,
            NHLGoalieStat.season == settings.NHL_SEASON,
            NHLGoalieStat.game_type_id == settings.NHL_GAME_TYPE,
        )
        .order_by(NHLGoalieStat.games_played.desc())
        .limit(1)
    )
    g = res.scalar_one_or_none()
    return g.overall_save_pct if g else None


# ---------------------------------------------------------------------------
# MLB prediction
# ---------------------------------------------------------------------------

async def predict_mlb_game(game: MLBGame, db: AsyncSession) -> dict:
    home_elo = await _get_elo(db, game.home_team, "mlb")
    away_elo = await _get_elo(db, game.away_team, "mlb")

    home_win_prob = elo_win_prob(home_elo, away_elo)

    result: dict = {
        "espn_id": game.espn_id,
        "sport": "mlb",
        "home_team": game.home_team,
        "away_team": game.away_team,
        "game_date": game.game_date,
        "game_time_utc": game.game_time_utc,
        "home_pitcher": game.home_pitcher,
        "away_pitcher": game.away_pitcher,
        "home_elo": round(home_elo),
        "away_elo": round(away_elo),
        "model_home_win_prob": round(home_win_prob, 3),
        "model_away_win_prob": round(1 - home_win_prob, 3),
        "model_home_ml": implied_to_american(home_win_prob),
        "model_away_ml": implied_to_american(1 - home_win_prob),
        "market_home_ml": game.home_moneyline,
        "market_away_ml": game.away_moneyline,
        "over_under": game.over_under,
        "recommendation": None,
        "edge_pct": None,
    }

    if game.home_moneyline and game.away_moneyline:
        home_edge = edge_pct(home_win_prob, game.home_moneyline)
        away_edge = edge_pct(1 - home_win_prob, game.away_moneyline)

        if home_edge >= _MIN_EDGE:
            result["recommendation"] = f"{game.home_team} ML"
            result["edge_pct"] = round(home_edge, 1)
        elif away_edge >= _MIN_EDGE:
            result["recommendation"] = f"{game.away_team} ML"
            result["edge_pct"] = round(away_edge, 1)

    return result


# ---------------------------------------------------------------------------
# NHL prediction
# ---------------------------------------------------------------------------

async def predict_nhl_game(game: NHLGame, db: AsyncSession) -> dict:
    home_elo = await _get_elo(db, game.home_team, "nhl")
    away_elo = await _get_elo(db, game.away_team, "nhl")

    home_win_prob = elo_win_prob(home_elo, away_elo, home_advantage=25.0)

    # Adjust with MoneyPuck xGoals%
    home_mp = await _get_moneypuck(db, game.home_team)
    away_mp = await _get_moneypuck(db, game.away_team)

    xg_adjustment = 0.0
    if home_mp and away_mp and home_mp.x_goals_pct and away_mp.x_goals_pct:
        xg_diff = (home_mp.x_goals_pct - away_mp.x_goals_pct) / 100
        xg_adjustment = xg_diff * 0.3  # blend 30% weight to xGoals signal

    # Adjust with goalie save%
    home_sv = await _get_starting_goalie_save_pct(db, game.home_team)
    away_sv = await _get_starting_goalie_save_pct(db, game.away_team)

    sv_adjustment = 0.0
    if home_sv and away_sv:
        sv_diff = (home_sv - away_sv) * 10  # scale: 0.01 sv% → ~0.1 prob shift
        sv_adjustment = sv_diff * 0.2  # 20% weight

    adjusted_prob = max(0.05, min(0.95, home_win_prob + xg_adjustment + sv_adjustment))

    result: dict = {
        "espn_id": game.espn_id,
        "sport": "nhl",
        "home_team": game.home_team,
        "away_team": game.away_team,
        "game_date": game.game_date,
        "game_time_utc": game.game_time_utc,
        "home_elo": round(home_elo),
        "away_elo": round(away_elo),
        "home_xgoals_pct": home_mp.x_goals_pct if home_mp else None,
        "away_xgoals_pct": away_mp.x_goals_pct if away_mp else None,
        "home_goalie_sv_pct": home_sv,
        "away_goalie_sv_pct": away_sv,
        "model_home_win_prob": round(adjusted_prob, 3),
        "model_away_win_prob": round(1 - adjusted_prob, 3),
        "model_home_ml": implied_to_american(adjusted_prob),
        "model_away_ml": implied_to_american(1 - adjusted_prob),
        "market_home_ml": game.home_moneyline,
        "market_away_ml": game.away_moneyline,
        "over_under": game.over_under,
        "recommendation": None,
        "edge_pct": None,
    }

    if game.home_moneyline and game.away_moneyline:
        home_edge = edge_pct(adjusted_prob, game.home_moneyline)
        away_edge = edge_pct(1 - adjusted_prob, game.away_moneyline)

        if home_edge >= _MIN_EDGE:
            result["recommendation"] = f"{game.home_team} ML"
            result["edge_pct"] = round(home_edge, 1)
        elif away_edge >= _MIN_EDGE:
            result["recommendation"] = f"{game.away_team} ML"
            result["edge_pct"] = round(away_edge, 1)

    return result


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

async def get_predictions(target_date: date, db: AsyncSession) -> dict:
    mlb_res = await db.execute(
        select(MLBGame)
        .where(MLBGame.game_date == target_date, MLBGame.status == "STATUS_SCHEDULED")
        .order_by(MLBGame.game_time_utc)
    )
    mlb_games = mlb_res.scalars().all()

    nhl_res = await db.execute(
        select(NHLGame)
        .where(NHLGame.game_date == target_date, NHLGame.status == "STATUS_SCHEDULED")
        .order_by(NHLGame.game_time_utc)
    )
    nhl_games = nhl_res.scalars().all()

    mlb_preds = [await predict_mlb_game(g, db) for g in mlb_games]
    nhl_preds = [await predict_nhl_game(g, db) for g in nhl_games]

    all_preds = mlb_preds + nhl_preds
    recommendations = [p for p in all_preds if p["recommendation"]]

    return {
        "date": target_date,
        "mlb": mlb_preds,
        "nhl": nhl_preds,
        "recommendations": sorted(recommendations, key=lambda x: x["edge_pct"] or 0, reverse=True),
    }
