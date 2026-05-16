from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Clairvoyance/1.0 (sports-intelligence)"}


# ---------------------------------------------------------------------------
# Raw fetchers
# ---------------------------------------------------------------------------

async def _get(endpoint: str, extra_params: dict | None = None) -> list[dict]:
    cayenne = f"seasonId={settings.NHL_SEASON} and gameTypeId={settings.NHL_GAME_TYPE}"
    params: dict = {"cayenneExp": cayenne, "limit": 500, "start": 0}
    if extra_params:
        params.update(extra_params)

    url = f"{settings.NHL_EDGE_BASE}/{endpoint}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params, headers=_HEADERS)
        resp.raise_for_status()
    return resp.json().get("data", [])


async def fetch_team_id_map() -> dict[int, str]:
    """Return {teamId: triCode} for all NHL franchises."""
    url = f"{settings.NHL_EDGE_BASE}/team"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params={"limit": 100}, headers=_HEADERS)
            resp.raise_for_status()
        teams = resp.json().get("data", [])
        return {t["id"]: t.get("triCode", "") for t in teams if t.get("triCode")}
    except Exception as e:
        logger.warning(f"Could not fetch NHL team map: {e}")
        return {}


async def fetch_team_summary() -> list[dict]:
    return await _get("team/summary", {"sort": "wins", "dir": "DESC"})


async def fetch_team_zone_time() -> list[dict]:
    try:
        return await _get("team/zonetime")
    except httpx.HTTPStatusError as e:
        logger.warning(f"NHL zone-time unavailable ({e.response.status_code}), skipping")
        return []


async def fetch_goalie_save_pct_by_strength() -> list[dict]:
    try:
        return await _get("goalie/savePctByStrength")
    except httpx.HTTPStatusError as e:
        logger.warning(f"NHL goalie/savePctByStrength unavailable ({e.response.status_code}), skipping")
        return []


async def fetch_skater_shot_type() -> list[dict]:
    return await _get("skater/shottype")


async def fetch_skater_skating() -> list[dict]:
    try:
        return await _get("skater/skating")
    except httpx.HTTPStatusError as e:
        logger.warning(f"NHL skater/skating unavailable ({e.response.status_code}), skipping")
        return []


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _abbrev_field(row: dict) -> str:
    """Extract team abbreviation from any of the field name variants NHL uses."""
    for key in ("teamAbbrev", "teamAbbrevs", "teamCode"):
        val = row.get(key)
        if val is None:
            continue
        if isinstance(val, dict):
            return val.get("default", "")
        if isinstance(val, str) and val:
            return val
    return ""


def parse_team_stats(
    summary_rows: list[dict],
    zone_rows: list[dict],
    team_id_map: dict[int, str] | None = None,
) -> list[dict]:
    zone_by_id = {r["teamId"]: r for r in zone_rows}
    id_map = team_id_map or {}
    results = []
    for row in summary_rows:
        tid = row.get("teamId")
        zone = zone_by_id.get(tid, {})
        # Prefer abbrev from the row itself; fall back to id→triCode map
        abbrev = _abbrev_field(row) or id_map.get(tid, "")
        results.append({
            "team_id": tid,
            "team_abbrev": abbrev,
            "team_name": row.get("teamFullName", ""),
            "season": settings.NHL_SEASON,
            "game_type_id": settings.NHL_GAME_TYPE,
            "games_played": row.get("gamesPlayed"),
            "wins": row.get("wins"),
            "losses": row.get("losses"),
            "ot_losses": row.get("otLosses"),
            "goals_for": row.get("goalsFor"),
            "goals_against": row.get("goalsAgainst"),
            "goals_for_per_game": row.get("goalsForPerGame"),
            "goals_against_per_game": row.get("goalsAgainstPerGame"),
            "pp_pct": row.get("powerPlayPct"),
            "pk_pct": row.get("penaltyKillPct"),
            "shots_for_per_game": row.get("shotsForPerGame"),
            "shots_against_per_game": row.get("shotsAgainstPerGame"),
            "offensive_zone_time_pct": zone.get("offensiveZoneTimePct"),
            "defensive_zone_time_pct": zone.get("defensiveZoneTimePct"),
            "neutral_zone_time_pct": zone.get("neutralZoneTimePct"),
        })
    return results


def parse_goalie_stats(rows: list[dict]) -> list[dict]:
    return [
        {
            "player_id": r.get("playerId"),
            "player_name": r.get("goalieFullName", ""),
            "team_abbrev": _abbrev_field(r),
            "season": settings.NHL_SEASON,
            "game_type_id": settings.NHL_GAME_TYPE,
            "games_played": r.get("gamesPlayed"),
            "saves_even_strength": r.get("evSaves"),
            "shots_against_even_strength": r.get("evShotsAgainst"),
            "save_pct_even_strength": r.get("evSavePct"),
            "saves_power_play": r.get("ppSaves"),
            "shots_against_power_play": r.get("ppShotsAgainst"),
            "save_pct_power_play": r.get("ppSavePct"),
            "saves_short_handed": r.get("shSaves"),
            "shots_against_short_handed": r.get("shShotsAgainst"),
            "save_pct_short_handed": r.get("shSavePct"),
            "overall_save_pct": r.get("savePct"),
            "goals_against_avg": r.get("goalsAgainstAverage"),
        }
        for r in rows
    ]


def parse_skater_stats(shot_rows: list[dict], skating_rows: list[dict]) -> list[dict]:
    skating_by_id = {r["playerId"]: r for r in skating_rows}
    results = []
    for row in shot_rows:
        pid = row.get("playerId")
        sk = skating_by_id.get(pid, {})
        results.append({
            "player_id": pid,
            "player_name": row.get("skaterFullName", ""),
            "team_abbrev": row.get("teamAbbrevs", ""),  # plain string in this endpoint
            "season": settings.NHL_SEASON,
            "game_type_id": settings.NHL_GAME_TYPE,
            "shots_wrist": row.get("shotsOnNetWrist"),
            "shots_snap": row.get("shotsOnNetSnap"),
            "shots_slap": row.get("shotsOnNetSlap"),
            "shots_backhand": row.get("shotsOnNetBackhand"),
            "shots_tip": row.get("shotsOnNetTipIn"),
            "shots_deflected": row.get("shotsOnNetDeflected"),
            "shots_wrap_around": row.get("shotsOnNetWrapAround"),
            "avg_speed": sk.get("avgSpeed"),
            "top_speed": sk.get("topSpeed"),
        })
    return results
