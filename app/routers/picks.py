from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.mlb_game import MLBGame
from app.models.nhl_game import NHLGame
from app.models.pick import Pick
from app.schemas.picks import PickCreate, PickOut

router = APIRouter(prefix="/picks", tags=["Picks"])


async def _enrich_from_game(pick_data: dict, db: AsyncSession) -> dict:
    """Fill game_date, home_team, away_team, over_under from stored game if espn_game_id given."""
    espn_id = pick_data.get("espn_game_id")
    if not espn_id:
        return pick_data

    sport = pick_data.get("sport", "")
    game = None

    if sport == "mlb":
        res = await db.execute(select(MLBGame).where(MLBGame.espn_id == espn_id))
        game = res.scalar_one_or_none()
    elif sport == "nhl":
        res = await db.execute(select(NHLGame).where(NHLGame.espn_id == espn_id))
        game = res.scalar_one_or_none()

    if not game:
        return pick_data

    if not pick_data.get("game_date"):
        pick_data["game_date"] = game.game_date
    if not pick_data.get("home_team"):
        pick_data["home_team"] = game.home_team
    if not pick_data.get("away_team"):
        pick_data["away_team"] = game.away_team
    if pick_data.get("over_under") is None and game.over_under is not None:
        pick_data["over_under"] = game.over_under

    return pick_data


@router.get("/stats")
async def get_pick_stats(
    sport: str | None = Query(default=None),
    bet_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Win rate, P&L, ROI — overall and broken down by sport/bet_type."""
    q = select(Pick).where(Pick.status.in_(["won", "lost", "push"]))
    if sport:
        q = q.where(Pick.sport == sport.lower())
    if bet_type:
        q = q.where(Pick.bet_type == bet_type.lower())
    result = await db.execute(q)
    picks = result.scalars().all()

    def _payout(p: Pick) -> float:
        if p.status == "push":
            return 0.0
        if p.status == "lost":
            return -p.amount
        odds = p.odds
        if odds >= 0:
            return p.amount * odds / 100
        return p.amount * 100 / abs(odds)

    won = sum(1 for p in picks if p.status == "won")
    lost = sum(1 for p in picks if p.status == "lost")
    push = sum(1 for p in picks if p.status == "push")
    decided = won + lost
    total_wagered = sum(p.amount for p in picks)
    total_pnl = sum(_payout(p) for p in picks)
    roi = (total_pnl / total_wagered * 100) if total_wagered else 0.0

    by_sport: dict[str, dict] = {}
    by_bet_type: dict[str, dict] = {}

    for p in picks:
        for key, group in [(p.sport, by_sport), (p.bet_type, by_bet_type)]:
            bucket = group.setdefault(key, {"won": 0, "lost": 0, "push": 0, "pnl": 0.0, "wagered": 0.0})
            bucket[p.status] = bucket.get(p.status, 0) + 1
            bucket["pnl"] += _payout(p)
            bucket["wagered"] += p.amount

    def _fmt(b: dict) -> dict:
        d = b["won"] + b["lost"]
        return {
            "won": b["won"],
            "lost": b["lost"],
            "push": b["push"],
            "win_rate": round(b["won"] / d * 100, 1) if d else None,
            "pnl": round(b["pnl"], 2),
            "roi": round(b["pnl"] / b["wagered"] * 100, 1) if b["wagered"] else None,
        }

    return {
        "summary": {
            "won": won,
            "lost": lost,
            "push": push,
            "win_rate": round(won / decided * 100, 1) if decided else None,
            "pnl": round(total_pnl, 2),
            "roi": round(roi, 1),
            "total_wagered": round(total_wagered, 2),
        },
        "by_sport": {k: _fmt(v) for k, v in by_sport.items()},
        "by_bet_type": {k: _fmt(v) for k, v in by_bet_type.items()},
    }


@router.get("/", response_model=list[PickOut])
async def list_picks(
    status: str | None = Query(default=None),
    sport: str | None = Query(default=None),
    game_date: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    q = select(Pick)
    if status:
        q = q.where(Pick.status == status)
    if sport:
        q = q.where(Pick.sport == sport.lower())
    if game_date:
        q = q.where(Pick.game_date == game_date)
    q = q.order_by(Pick.created_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/", response_model=PickOut, status_code=201)
async def create_pick(pick_in: PickCreate, db: AsyncSession = Depends(get_db)):
    data = await _enrich_from_game(pick_in.model_dump(), db)
    pick = Pick(**data)
    db.add(pick)
    await db.flush()
    await db.refresh(pick)
    return pick


@router.get("/{pick_id}", response_model=PickOut)
async def get_pick(pick_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Pick).where(Pick.id == pick_id))
    pick = result.scalar_one_or_none()
    if not pick:
        raise HTTPException(status_code=404, detail="Pick not found")
    return pick


@router.patch("/{pick_id}/void", response_model=PickOut)
async def void_pick(pick_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Pick).where(Pick.id == pick_id))
    pick = result.scalar_one_or_none()
    if not pick:
        raise HTTPException(status_code=404, detail="Pick not found")
    if pick.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending picks can be voided")
    pick.status = "void"
    await db.flush()
    await db.refresh(pick)
    return pick
