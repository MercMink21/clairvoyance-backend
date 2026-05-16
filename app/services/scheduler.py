from __future__ import annotations

import logging
from datetime import date, timedelta

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler(timezone=pytz.timezone(settings.TIMEZONE))


async def _daily_pipeline() -> None:
    from app.services import pipeline

    today = date.today()
    tomorrow = today + timedelta(days=1)
    logger.info("=== Daily pipeline starting ===")
    await pipeline.run_settlement(today)
    await pipeline.run_espn_mlb(tomorrow)
    await pipeline.run_nhl_schedule(tomorrow)
    await pipeline.run_nhl_edge()
    await pipeline.run_moneypuck()
    logger.info("=== Daily pipeline complete ===")


def start_scheduler() -> None:
    denver = pytz.timezone(settings.TIMEZONE)
    _scheduler.add_job(
        _daily_pipeline,
        CronTrigger(hour=0, minute=0, timezone=denver),
        id="daily_pipeline",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    logger.info("Scheduler started — daily pipeline fires at midnight MST (America/Denver)")


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
