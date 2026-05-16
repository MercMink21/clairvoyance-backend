from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MLB — schedule, pitchers, scores
# ---------------------------------------------------------------------------

async def fetch_mlb_schedule(target_date: date) -> list[dict]:
    return await _fetch_schedule(settings.ESPN_MLB_BASE, target_date, sport="mlb")


async def fetch_mlb_final_scores(target_date: date) -> list[dict]:
    return await _fetch_final_scores(settings.ESPN_MLB_BASE, target_date)


async def fetch_game_pitchers(espn_id: str) -> dict:
    """Fetch probable starters from the ESPN summary endpoint."""
    url = f"{settings.ESPN_MLB_BASE}/summary"
    result = {"home_pitcher": None, "away_pitcher": None}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params={"event": espn_id})
            resp.raise_for_status()
            data = resp.json()

        competitions = data.get("header", {}).get("competitions", [])
        if not competitions:
            return result

        for competitor in competitions[0].get("competitors", []):
            probables = competitor.get("probables", [])
            starter = next(
                (p for p in probables if p.get("name") == "probableStartingPitcher"),
                probables[0] if probables else None,
            )
            if not starter:
                continue
            name = (
                starter.get("athlete", {}).get("fullName")
                or starter.get("athlete", {}).get("displayName")
                or starter.get("displayName")
            )
            if name:
                side = "home_pitcher" if competitor.get("homeAway") == "home" else "away_pitcher"
                result[side] = name
    except Exception as e:
        logger.warning(f"Could not fetch pitchers for game {espn_id}: {e}")
    return result


# ---------------------------------------------------------------------------
# NHL — schedule and scores (uses same ESPN scoreboard structure as MLB)
# ---------------------------------------------------------------------------

async def fetch_nhl_schedule(target_date: date) -> list[dict]:
    return await _fetch_schedule(settings.ESPN_NHL_BASE, target_date, sport="nhl")


async def fetch_nhl_final_scores(target_date: date) -> list[dict]:
    return await _fetch_final_scores(settings.ESPN_NHL_BASE, target_date)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def _fetch_schedule(base_url: str, target_date: date, sport: str) -> list[dict]:
    date_str = target_date.strftime("%Y%m%d")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{base_url}/scoreboard", params={"dates": date_str, "limit": 30})
        resp.raise_for_status()
        data = resp.json()

    games = []
    for event in data.get("events", []):
        try:
            game = _parse_event(event)
            if game:
                games.append(game)
        except Exception as e:
            logger.warning(f"ESPN {sport} parse error event {event.get('id')}: {e}")
    return games


async def _fetch_final_scores(base_url: str, target_date: date) -> list[dict]:
    date_str = target_date.strftime("%Y%m%d")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{base_url}/scoreboard", params={"dates": date_str, "limit": 30})
        resp.raise_for_status()
        data = resp.json()

    scores = []
    for event in data.get("events", []):
        try:
            competition = event["competitions"][0]
            if competition["status"]["type"]["name"] != "STATUS_FINAL":
                continue
            home = next((c for c in competition["competitors"] if c["homeAway"] == "home"), None)
            away = next((c for c in competition["competitors"] if c["homeAway"] == "away"), None)
            if not home or not away:
                continue
            scores.append({
                "espn_id": event["id"],
                "home_team": home["team"]["abbreviation"],
                "away_team": away["team"]["abbreviation"],
                "home_score": int(home.get("score") or 0),
                "away_score": int(away.get("score") or 0),
            })
        except Exception as e:
            logger.warning(f"ESPN score parse error {event.get('id')}: {e}")
    return scores


def _parse_moneylines(odds: dict) -> tuple[Optional[int], Optional[int]]:
    """
    ESPN returns odds in two shapes depending on the provider:
      New: odds.moneyline.home.close.odds  (string like "-136")
      Old: odds.homeTeamOdds.moneyLine     (int)
    """
    moneyline = odds.get("moneyline")
    if moneyline:
        try:
            home_ml = int(moneyline.get("home", {}).get("close", {}).get("odds", "") or "")
        except (ValueError, TypeError):
            home_ml = None
        try:
            away_ml = int(moneyline.get("away", {}).get("close", {}).get("odds", "") or "")
        except (ValueError, TypeError):
            away_ml = None
        return home_ml, away_ml

    # Flat legacy shape
    home_ml = odds.get("homeTeamOdds", {}).get("moneyLine")
    away_ml = odds.get("awayTeamOdds", {}).get("moneyLine")
    return (
        int(home_ml) if home_ml is not None else None,
        int(away_ml) if away_ml is not None else None,
    )


def _parse_event(event: dict) -> Optional[dict]:
    competition = event["competitions"][0]
    competitors = competition["competitors"]

    home = next((c for c in competitors if c["homeAway"] == "home"), None)
    away = next((c for c in competitors if c["homeAway"] == "away"), None)
    if not home or not away:
        return None

    odds_list = competition.get("odds") or []
    odds = odds_list[0] if odds_list else {}

    home_ml, away_ml = _parse_moneylines(odds)
    over_under = odds.get("overUnder")

    game_time_utc: Optional[datetime] = None
    raw_date = event.get("date", "")
    if raw_date:
        try:
            game_time_utc = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except ValueError:
            pass

    venue = None
    if competition.get("venue"):
        venue = competition["venue"].get("fullName")

    status = competition.get("status", {}).get("type", {}).get("name", "STATUS_SCHEDULED")

    home_score = away_score = None
    if status in ("STATUS_FINAL", "STATUS_IN_PROGRESS"):
        try:
            home_score = int(home.get("score") or 0)
            away_score = int(away.get("score") or 0)
        except (ValueError, TypeError):
            pass

    return {
        "espn_id": event["id"],
        "game_date": game_time_utc.date() if game_time_utc else None,
        "game_time_utc": game_time_utc,
        "status": status,
        "home_team": home["team"]["abbreviation"],
        "away_team": away["team"]["abbreviation"],
        "home_score": home_score,
        "away_score": away_score,
        "home_moneyline": home_ml,
        "away_moneyline": away_ml,
        "over_under": float(over_under) if over_under is not None else None,
        "venue": venue,
    }
