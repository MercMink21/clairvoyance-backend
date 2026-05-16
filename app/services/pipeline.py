from __future__ import annotations

"""Orchestrates scraper runs and database writes for the daily pipeline."""

import logging
import time
from datetime import date

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.daily_log import DailyLog
from app.models.mlb_game import MLBGame
from app.models.moneypuck import MoneyPuckTeam
from app.models.nhl_game import NHLGame
from app.models.nhl_stat import NHLGoalieStat, NHLSkaterStat, NHLTeamStat
from app.scrapers import espn, nhl_edge
from app.scrapers import moneypuck as mp_scraper
from app.services.settlement import settle_pending_picks

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Logging helper
# ---------------------------------------------------------------------------

async def _write_log(
    scraper: str,
    log_date: date,
    status: str,
    fetched: int = 0,
    created: int = 0,
    updated: int = 0,
    error: Exception | None = None,
    duration_ms: int = 0,
) -> None:
    async with AsyncSessionLocal() as session:
        session.add(
            DailyLog(
                log_date=log_date,
                scraper=scraper,
                status=status,
                records_fetched=fetched,
                records_created=created,
                records_updated=updated,
                error_message=str(error)[:2000] if error else None,
                duration_ms=duration_ms,
            )
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Generic upsert helper
# ---------------------------------------------------------------------------

def _upsert(existing, data: dict):
    for k, v in data.items():
        setattr(existing, k, v)


# ---------------------------------------------------------------------------
# Per-scraper pipeline steps
# ---------------------------------------------------------------------------

async def run_espn_mlb(target_date: date) -> None:
    start = time.monotonic()
    logger.info(f"ESPN MLB: fetching schedule for {target_date}")

    try:
        games = await espn.fetch_mlb_schedule(target_date)
        created = updated = 0

        async with AsyncSessionLocal() as session:
            for game_data in games:
                pitchers = await espn.fetch_game_pitchers(game_data["espn_id"])
                game_data.update(pitchers)

                res = await session.execute(
                    select(MLBGame).where(MLBGame.espn_id == game_data["espn_id"])
                )
                existing = res.scalar_one_or_none()
                if existing:
                    _upsert(existing, game_data)
                    updated += 1
                else:
                    session.add(MLBGame(**game_data))
                    created += 1

            await session.commit()

        ms = int((time.monotonic() - start) * 1000)
        await _write_log("espn_mlb", target_date, "success",
                         fetched=len(games), created=created, updated=updated, duration_ms=ms)
        logger.info(f"ESPN MLB: {created} created, {updated} updated")

    except Exception as e:
        ms = int((time.monotonic() - start) * 1000)
        logger.error(f"ESPN MLB scraper failed: {e}")
        await _write_log("espn_mlb", target_date, "failed", error=e, duration_ms=ms)


async def run_nhl_schedule(target_date: date) -> None:
    start = time.monotonic()
    logger.info(f"ESPN NHL: fetching schedule for {target_date}")

    try:
        games = await espn.fetch_nhl_schedule(target_date)
        created = updated = 0

        _NHL_FIELDS = {c.key for c in NHLGame.__table__.columns}

        async with AsyncSessionLocal() as session:
            for game_data in games:
                nhl_data = {k: v for k, v in game_data.items() if k in _NHL_FIELDS}
                res = await session.execute(
                    select(NHLGame).where(NHLGame.espn_id == nhl_data["espn_id"])
                )
                existing = res.scalar_one_or_none()
                if existing:
                    _upsert(existing, nhl_data)
                    updated += 1
                else:
                    session.add(NHLGame(**nhl_data))
                    created += 1

            await session.commit()

        ms = int((time.monotonic() - start) * 1000)
        await _write_log("espn_nhl", target_date, "success",
                         fetched=len(games), created=created, updated=updated, duration_ms=ms)
        logger.info(f"ESPN NHL: {created} created, {updated} updated")

    except Exception as e:
        ms = int((time.monotonic() - start) * 1000)
        logger.error(f"ESPN NHL scraper failed: {e}")
        await _write_log("espn_nhl", target_date, "failed", error=e, duration_ms=ms)


async def run_nhl_edge() -> None:
    start = time.monotonic()
    today = date.today()
    logger.info("NHL Edge: fetching all stat categories")

    try:
        team_id_map = await nhl_edge.fetch_team_id_map()
        summary = await nhl_edge.fetch_team_summary()
        zone_time = await nhl_edge.fetch_team_zone_time()
        team_stats = nhl_edge.parse_team_stats(summary, zone_time, team_id_map)

        goalie_rows = await nhl_edge.fetch_goalie_save_pct_by_strength()
        goalie_stats = nhl_edge.parse_goalie_stats(goalie_rows)

        shot_rows = await nhl_edge.fetch_skater_shot_type()
        skating_rows = await nhl_edge.fetch_skater_skating()
        skater_stats = nhl_edge.parse_skater_stats(shot_rows, skating_rows)

        created = updated = 0

        async with AsyncSessionLocal() as session:
            for ts in team_stats:
                res = await session.execute(
                    select(NHLTeamStat).where(
                        NHLTeamStat.team_id == ts["team_id"],
                        NHLTeamStat.season == ts["season"],
                        NHLTeamStat.game_type_id == ts["game_type_id"],
                    )
                )
                existing = res.scalar_one_or_none()
                if existing:
                    _upsert(existing, ts)
                    updated += 1
                else:
                    session.add(NHLTeamStat(**ts))
                    created += 1

            for gs in goalie_stats:
                res = await session.execute(
                    select(NHLGoalieStat).where(
                        NHLGoalieStat.player_id == gs["player_id"],
                        NHLGoalieStat.season == gs["season"],
                        NHLGoalieStat.game_type_id == gs["game_type_id"],
                    )
                )
                existing = res.scalar_one_or_none()
                if existing:
                    _upsert(existing, gs)
                    updated += 1
                else:
                    session.add(NHLGoalieStat(**gs))
                    created += 1

            for ss in skater_stats:
                res = await session.execute(
                    select(NHLSkaterStat).where(
                        NHLSkaterStat.player_id == ss["player_id"],
                        NHLSkaterStat.season == ss["season"],
                        NHLSkaterStat.game_type_id == ss["game_type_id"],
                    )
                )
                existing = res.scalar_one_or_none()
                if existing:
                    _upsert(existing, ss)
                    updated += 1
                else:
                    session.add(NHLSkaterStat(**ss))
                    created += 1

            await session.commit()

        total = len(team_stats) + len(goalie_stats) + len(skater_stats)
        ms = int((time.monotonic() - start) * 1000)
        await _write_log("nhl_edge", today, "success",
                         fetched=total, created=created, updated=updated, duration_ms=ms)
        logger.info(f"NHL Edge: {total} records, {created} created, {updated} updated")

    except Exception as e:
        ms = int((time.monotonic() - start) * 1000)
        logger.error(f"NHL Edge scraper failed: {e}")
        await _write_log("nhl_edge", today, "failed", error=e, duration_ms=ms)


async def run_moneypuck() -> None:
    start = time.monotonic()
    today = date.today()
    season = str(today.year)
    logger.info("MoneyPuck: fetching teams page")

    try:
        teams = await mp_scraper.fetch_moneypuck_teams()
        created = updated = 0

        async with AsyncSessionLocal() as session:
            for td in teams:
                td["season"] = season
                res = await session.execute(
                    select(MoneyPuckTeam).where(
                        MoneyPuckTeam.team == td["team"],
                        MoneyPuckTeam.season == season,
                        MoneyPuckTeam.situation == td.get("situation", "all"),
                    )
                )
                existing = res.scalar_one_or_none()
                if existing:
                    _upsert(existing, td)
                    updated += 1
                else:
                    session.add(MoneyPuckTeam(**td))
                    created += 1
            await session.commit()

        ms = int((time.monotonic() - start) * 1000)
        await _write_log("moneypuck", today, "success",
                         fetched=len(teams), created=created, updated=updated, duration_ms=ms)
        logger.info(f"MoneyPuck: {created} created, {updated} updated")

    except Exception as e:
        ms = int((time.monotonic() - start) * 1000)
        logger.error(f"MoneyPuck scraper failed: {e}")
        await _write_log("moneypuck", today, "failed", error=e, duration_ms=ms)


async def run_settlement(target_date: date) -> None:
    start = time.monotonic()
    logger.info(f"Settlement: settling picks for {target_date}")
    try:
        result = await settle_pending_picks(target_date)
        ms = int((time.monotonic() - start) * 1000)
        await _write_log("settlement", target_date, "success",
                         updated=result["settled"], duration_ms=ms)
        logger.info(f"Settlement: {result['settled']} settled, {result['errors']} errors")
    except Exception as e:
        ms = int((time.monotonic() - start) * 1000)
        logger.error(f"Settlement failed: {e}")
        await _write_log("settlement", target_date, "failed", error=e, duration_ms=ms)
