from __future__ import annotations

import csv
import io
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# MoneyPuck publishes season summary CSVs at predictable URLs.
# The web page (teams.htm) uses a custom JS grid — no <table> elements.
_CSV_BASE = "https://moneypuck.com/moneypuck/playerData/seasonSummary"
_SITUATIONS = ("all", "5on5", "powerPlay", "penaltyKill")
_HEADERS = {"User-Agent": "Clairvoyance/1.0 (sports-intelligence)"}


async def fetch_moneypuck_teams() -> list[dict]:
    """Fetch MoneyPuck team stats via direct CSV endpoints (fast, no JS needed)."""
    rows: list[dict] = []

    # Derive season year from NHL_SEASON setting (e.g. "20252026" → 2025)
    season_str = settings.NHL_SEASON  # "20252026"
    year = int(season_str[:4])  # 2025
    game_type = "playoffs" if settings.NHL_GAME_TYPE == 3 else "regular"

    urls = [
        f"{_CSV_BASE}/{year}/{game_type}/teams.csv",
        f"{_CSV_BASE}/{year}/regular/teams.csv",  # fallback if playoffs CSV missing
    ]

    async with httpx.AsyncClient(timeout=30, headers=_HEADERS) as client:
        for url in urls:
            try:
                resp = await client.get(url)
                if resp.status_code == 404:
                    logger.info(f"MoneyPuck CSV not found: {url}")
                    continue
                resp.raise_for_status()
                parsed = _parse_csv(resp.text)
                if parsed:
                    logger.info(f"MoneyPuck: fetched {len(parsed)} rows from {url}")
                    rows = parsed
                    break
            except httpx.HTTPError as e:
                logger.warning(f"MoneyPuck CSV fetch failed for {url}: {e}")

    if not rows:
        logger.warning("MoneyPuck: CSV fetch yielded no rows, falling back to Playwright")
        rows = await _playwright_fallback()

    return rows


async def _playwright_fallback() -> list[dict]:
    """Last-resort Playwright scrape of moneypuck.com/teams.htm."""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            page = await browser.new_page()
            try:
                await page.goto(settings.MONEYPUCK_TEAMS_URL, wait_until="networkidle", timeout=60_000)
                # Try multiple selectors — MoneyPuck has used both table and ag-grid
                for selector in ("table", "[role='grid']", ".ag-root"):
                    try:
                        await page.wait_for_selector(selector, timeout=10_000)
                        break
                    except Exception:
                        continue

                raw: list[dict] = await page.evaluate("""() => {
                    // Try standard table first
                    const table = document.querySelector('table');
                    if (table) {
                        const headers = Array.from(table.querySelectorAll('thead th')).map(h => h.innerText.trim());
                        return Array.from(table.querySelectorAll('tbody tr')).map(tr => {
                            const cells = Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim());
                            const obj = {};
                            headers.forEach((h, i) => { obj[h] = cells[i] ?? null; });
                            return obj;
                        });
                    }
                    // ag-Grid fallback
                    const rows = document.querySelectorAll('.ag-row');
                    if (rows.length) {
                        return Array.from(rows).map(row => {
                            const obj = {};
                            row.querySelectorAll('[col-id]').forEach(cell => {
                                obj[cell.getAttribute('col-id')] = cell.innerText.trim();
                            });
                            return obj;
                        });
                    }
                    return [];
                }""")
                return [r for r in (_parse_raw_row(row) for row in raw) if r]
            finally:
                await browser.close()
    except Exception as e:
        logger.error(f"MoneyPuck Playwright fallback failed: {e}")
        return []


def _parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    results = []
    for row in reader:
        parsed = _parse_raw_row(row)
        if parsed:
            results.append(parsed)
    return results


def _f(val) -> Optional[float]:
    if val is None or str(val).strip() in ("", "-", "N/A", "nan"):
        return None
    try:
        return float(str(val).replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def _i(val) -> Optional[int]:
    v = _f(val)
    return int(v) if v is not None else None


# MoneyPuck CSV column name mapping (their CSV uses camelCase)
_COL = {
    # CSV name → our field
    "team": "team",
    "situation": "situation",
    "games_played": "games_played",
    "gamesPlayed": "games_played",
    "shotsForPerHour": "shots_for_60",
    "shotsAgainstPerHour": "shots_against_60",
    "goalsForPerHour": "goals_for_60",
    "goalsAgainstPerHour": "goals_against_60",
    "xGoalsForPerHour": "x_goals_for_60",
    "xGoalsAgainstPerHour": "x_goals_against_60",
    "xGoalsPercentage": "x_goals_pct",
    "corsiPercentage": "corsi_for_pct",
    "fenwickPercentage": "fenwick_for_pct",
    "shootingPct": "shooting_pct",
    "savePct": "save_pct",
    "pdo": "pdo",
    "goalsFor": "goals_for",
    "goalsAgainst": "goals_against",
    "xGoalsFor": "x_goals_for",
    "xGoalsAgainst": "x_goals_against",
    "highDangerGoalsFor": "high_danger_goals_for",
    "highDangerGoalsAgainst": "high_danger_goals_against",
    "mediumDangerGoalsFor": "medium_danger_goals_for",
    "mediumDangerGoalsAgainst": "medium_danger_goals_against",
    "lowDangerGoalsFor": "low_danger_goals_for",
    "lowDangerGoalsAgainst": "low_danger_goals_against",
}


def _per60(stat, ice_time_min: Optional[float]) -> Optional[float]:
    """Convert a raw count to a per-60-minutes rate."""
    if stat is None or not ice_time_min:
        return None
    v = _f(stat)
    if v is None:
        return None
    return round(v / ice_time_min * 60, 4)


def _parse_raw_row(row: dict) -> Optional[dict]:
    team = row.get("team") or row.get("Team")
    if not team or str(team).strip() in ("", "team"):
        return None

    ice_min = _f(row.get("iceTime"))  # MoneyPuck CSV: total team ice time in minutes

    goals_for = _i(row.get("goalsFor") or row.get("GF"))
    goals_against = _i(row.get("goalsAgainst") or row.get("GA"))
    shots_for = _f(row.get("shotsOnGoalFor"))
    shots_against = _f(row.get("shotsOnGoalAgainst"))

    # Derived rates not provided directly in CSV
    shooting_pct = (goals_for / shots_for) if goals_for is not None and shots_for else None
    save_pct = (1 - goals_against / shots_against) if goals_against is not None and shots_against else None
    pdo = ((shooting_pct or 0) + (save_pct or 0)) if shooting_pct is not None and save_pct is not None else None

    return {
        "team": str(team).strip().upper(),
        "situation": str(row.get("situation") or "all").strip(),
        "games_played": _i(row.get("games_played") or row.get("gamesPlayed")),
        "shots_for_60": _per60(row.get("shotsOnGoalFor"), ice_min),
        "shots_against_60": _per60(row.get("shotsOnGoalAgainst"), ice_min),
        "goals_for_60": _per60(row.get("goalsFor"), ice_min),
        "goals_against_60": _per60(row.get("goalsAgainst"), ice_min),
        "x_goals_for_60": _per60(row.get("xGoalsFor"), ice_min),
        "x_goals_against_60": _per60(row.get("xGoalsAgainst"), ice_min),
        "x_goals_pct": _f(row.get("xGoalsPercentage") or row.get("xGF%")),
        "corsi_for_pct": _f(row.get("corsiPercentage") or row.get("CF%")),
        "fenwick_for_pct": _f(row.get("fenwickPercentage") or row.get("FF%")),
        "shooting_pct": round(shooting_pct, 4) if shooting_pct is not None else None,
        "save_pct": round(save_pct, 4) if save_pct is not None else None,
        "pdo": round(pdo, 4) if pdo is not None else None,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "x_goals_for": _f(row.get("xGoalsFor")),
        "x_goals_against": _f(row.get("xGoalsAgainst")),
        "high_danger_goals_for": _i(row.get("highDangerGoalsFor")),
        "high_danger_goals_against": _i(row.get("highDangerGoalsAgainst")),
        "medium_danger_goals_for": _i(row.get("mediumDangerGoalsFor")),
        "medium_danger_goals_against": _i(row.get("mediumDangerGoalsAgainst")),
        "low_danger_goals_for": _i(row.get("lowDangerGoalsFor")),
        "low_danger_goals_against": _i(row.get("lowDangerGoalsAgainst")),
    }
