from __future__ import annotations

from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.daily_log import DailyLog
from app.services import pipeline

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/scrape/mlb")
async def trigger_mlb_scrape(
    background_tasks: BackgroundTasks,
    target_date: date = Query(default_factory=date.today),
):
    background_tasks.add_task(pipeline.run_espn_mlb, target_date)
    return {"message": f"ESPN MLB scrape triggered for {target_date}"}


@router.post("/scrape/nhl-schedule")
async def trigger_nhl_schedule_scrape(
    background_tasks: BackgroundTasks,
    target_date: date = Query(default_factory=date.today),
):
    background_tasks.add_task(pipeline.run_nhl_schedule, target_date)
    return {"message": f"ESPN NHL schedule scrape triggered for {target_date}"}


@router.post("/scrape/nhl")
async def trigger_nhl_scrape(background_tasks: BackgroundTasks):
    background_tasks.add_task(pipeline.run_nhl_edge)
    return {"message": "NHL Edge stats scrape triggered"}


@router.post("/scrape/moneypuck")
async def trigger_moneypuck_scrape(background_tasks: BackgroundTasks):
    background_tasks.add_task(pipeline.run_moneypuck)
    return {"message": "MoneyPuck scrape triggered"}


@router.post("/settle")
async def trigger_settlement(
    background_tasks: BackgroundTasks,
    target_date: date = Query(default_factory=date.today),
):
    background_tasks.add_task(pipeline.run_settlement, target_date)
    return {"message": f"Settlement triggered for {target_date}"}


@router.post("/pipeline")
async def trigger_full_pipeline(background_tasks: BackgroundTasks):
    """Manually trigger the complete daily pipeline (same as midnight cron)."""
    from app.services.scheduler import _daily_pipeline
    background_tasks.add_task(_daily_pipeline)
    return {"message": "Full pipeline triggered"}


@router.get("/status")
async def get_status(db: AsyncSession = Depends(get_db)):
    """Last successful run timestamp and record counts for each scraper."""
    scrapers = ["espn_mlb", "espn_nhl", "nhl_edge", "moneypuck", "settlement"]
    status_map = {}

    for scraper in scrapers:
        res = await db.execute(
            select(DailyLog)
            .where(DailyLog.scraper == scraper, DailyLog.status == "success")
            .order_by(DailyLog.created_at.desc())
            .limit(1)
        )
        last = res.scalar_one_or_none()
        if last:
            status_map[scraper] = {
                "last_success": last.created_at,
                "log_date": last.log_date,
                "records_fetched": last.records_fetched,
                "records_created": last.records_created,
                "records_updated": last.records_updated,
                "duration_ms": last.duration_ms,
            }
        else:
            status_map[scraper] = None

    from app.services.scheduler import _scheduler
    job = _scheduler.get_job("daily_pipeline")
    next_run = job.next_run_time if job else None

    return {"scrapers": status_map, "next_pipeline_run": next_run}


@router.get("/logs")
async def get_logs(
    limit: int = Query(default=50, le=500),
    scraper: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    q = select(DailyLog).order_by(DailyLog.created_at.desc()).limit(limit)
    if scraper:
        q = q.where(DailyLog.scraper == scraper)
    result = await db.execute(q)
    return result.scalars().all()
