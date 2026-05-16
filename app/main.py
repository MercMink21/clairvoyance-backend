from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register all models then create tables (Alembic handles migrations in prod)
    import app.models  # noqa: F401 — side-effect import to populate Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.services.scheduler import start_scheduler, stop_scheduler

    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Clairvoyance Sports Intelligence API",
    description="MLB + NHL betting intelligence — schedules, odds, stats, picks, ELO",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to your frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import admin, mlb, nhl, picks, predictions  # noqa: E402

app.include_router(mlb.router)
app.include_router(nhl.router)
app.include_router(picks.router)
app.include_router(predictions.router)
app.include_router(admin.router)


@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok"}
