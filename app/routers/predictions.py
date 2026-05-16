from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.predictor import get_predictions

router = APIRouter(prefix="/predictions", tags=["Predictions"])


@router.get("/")
async def predictions(
    game_date: date = Query(default_factory=date.today),
    db: AsyncSession = Depends(get_db),
):
    return await get_predictions(game_date, db)
