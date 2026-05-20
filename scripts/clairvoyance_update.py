#!/usr/bin/env python3
from __future__ import annotations
"""
clairvoyance_update.py — Clairvoyance Automated Data Refresh Engine
Fetches live stats, odds, schedules, standings, props, and weather
across MLB, NBA, NHL, and Tennis, then pushes to GitHub Pages.

Usage:
  python3 scripts/clairvoyance_update.py                 # fetch + write data.json, no push
  python3 scripts/clairvoyance_update.py --push          # fetch + write + git push
  python3 scripts/clairvoyance_update.py --sport nba     # single sport
  python3 scripts/clairvoyance_update.py --verbose       # debug logging
  python3 scripts/clairvoyance_update.py --dry-run       # fetch only, no writes
  python3 scripts/clairvoyance_update.py --no-linemate   # skip Playwright (faster)

Cron (5x daily — aligned to game times ET):
  0 7,11,15,18,22 * * * cd /Users/reeseoliver/clairvoyance-backend && python3 scripts/clairvoyance_update.py --push >> logs/update.log 2>&1
"""

import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── dependency bootstrap ──────────────────────────────────────────────────────
try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "lxml"],
        check=True, capture_output=True,
    )
    import requests
    from bs4 import BeautifulSoup

# ── paths & config ────────────────────────────────────────────────────────────
ROOT    = Path(__file__).parent.parent
FE      = ROOT / "frontend" / "index.html"
DOCS    = ROOT / "docs"    / "index.html"
DATA    = ROOT / "data"
LOGS    = ROOT / "logs"
FE_DATA = ROOT / "frontend" / "data.json"
DC_DATA = ROOT / "docs"    / "data.json"

DATA.mkdir(exist_ok=True)
LOGS.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
NHL_API   = "https://api-web.nhle.com/v1"
MP_BASE   = "https://moneypuck.com/moneypuck/playerData/seasonSummary/2024/regular"

NOW        = datetime.now(timezone.utc)
TODAY_ET   = (NOW - timedelta(hours=5)).strftime("%Y%m%d")   # approximate ET
TODAY_ISO  = (NOW - timedelta(hours=5)).strftime("%Y-%m-%d")
TODAY_NHL  = (NOW - timedelta(hours=5)).strftime("%Y-%m-%d")
TS_DISPLAY = (NOW - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M ET")

_verbose = False
_changes: list[str] = []

# ── logging ───────────────────────────────────────────────────────────────────
def log(msg: str, level: str = "INFO") -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)

def vlog(msg: str) -> None:
    if _verbose:
        log(msg, "DEBUG")

def note(msg: str) -> None:
    _changes.append(msg)
    log(msg)

# ── HTTP helpers ──────────────────────────────────────────────────────────────
_session = requests.Session()
_session.headers.update(HEADERS)

def fetch_json(url: str, timeout: int = 15, retries: int = 2) -> dict | list | None:
    for attempt in range(retries + 1):
        try:
            r = _session.get(url, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries:
                log(f"FAILED {url}: {e}", "WARN")
                return None
            time.sleep(2 ** attempt)

def fetch_html(url: str, timeout: int = 20) -> BeautifulSoup | None:
    try:
        r = _session.get(url, timeout=timeout)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        log(f"FAILED HTML {url}: {e}", "WARN")
        return None

def fetch_csv_rows(url: str, timeout: int = 20) -> list[dict]:
    try:
        r = _session.get(url, timeout=timeout)
        r.raise_for_status()
        reader = csv.DictReader(io.StringIO(r.text))
        return list(reader)
    except Exception as e:
        log(f"FAILED CSV {url}: {e}", "WARN")
        return []

# ── ESPN helpers ──────────────────────────────────────────────────────────────
def _espn_odds(comp: dict) -> dict:
    odds = (comp.get("odds") or [{}])[0]
    return {
        "homeML": odds.get("homeTeamOdds", {}).get("moneyLine"),
        "awayML": odds.get("awayTeamOdds", {}).get("moneyLine"),
        "ou":     odds.get("overUnder"),
        "spread": odds.get("spread"),
        "provider": (odds.get("provider") or {}).get("name", ""),
    }

def _espn_game(event: dict, sport: str) -> dict:
    comp        = (event.get("competitions") or [{}])[0]
    competitors = comp.get("competitors") or []
    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), {})
    status = event.get("status") or {}
    state  = (status.get("type") or {}).get("state", "pre")  # pre | in | post

    g: dict = {
        "id":          event.get("id", ""),
        "sport":       sport,
        "home":        (home.get("team") or {}).get("abbreviation", ""),
        "away":        (away.get("team") or {}).get("abbreviation", ""),
        "homeScore":   home.get("score") if state != "pre" else None,
        "awayScore":   away.get("score") if state != "pre" else None,
        "state":       state,
        "period":      status.get("period", 0),
        "displayClock":status.get("displayClock", ""),
        "venue":       (comp.get("venue") or {}).get("fullName", ""),
        "date":        event.get("date", ""),
        "network":     ((comp.get("broadcasts") or [{}])[0].get("names") or [""])[0],
    }
    g.update(_espn_odds(comp))

    # Playoff series note
    for note_obj in comp.get("notes") or []:
        h = note_obj.get("headline", "")
        if "Game" in h or "Series" in h:
            g["seriesNote"] = h
            break

    return g

# ═══════════════════════════════════════════════════════════════════════════════
# MLB
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_mlb_scoreboard(date: str = TODAY_ET) -> list[dict]:
    log(f"MLB scoreboard {date}…")
    data = fetch_json(f"{ESPN_BASE}/baseball/mlb/scoreboard?dates={date}&limit=30")
    if not data:
        return []
    games = [_espn_game(e, "MLB") for e in (data.get("events") or [])]
    # Also fetch tomorrow for schedule context
    tom = (datetime.strptime(date, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
    data2 = fetch_json(f"{ESPN_BASE}/baseball/mlb/scoreboard?dates={tom}&limit=30")
    tomorrow = [_espn_game(e, "MLB") for e in ((data2 or {}).get("events") or [])]
    vlog(f"  MLB: {len(games)} today, {len(tomorrow)} tomorrow")
    return games, tomorrow

def fetch_mlb_standings() -> dict:
    log("MLB standings…")
    # Use the web API which returns children → standings → entries structure
    data = fetch_json(
        "https://site.web.api.espn.com/apis/v2/sports/baseball/mlb/standings"
        "?region=us&lang=en&season=2026&type=2"
    )
    if not data:
        return {}
    out: dict = {}
    for division in data.get("children") or []:
        for entry in (division.get("standings") or {}).get("entries") or []:
            team  = entry.get("team") or {}
            abbr  = team.get("abbreviation", "")
            stats = {s["name"]: s.get("displayValue", s.get("value", ""))
                     for s in (entry.get("stats") or [])}
            out[abbr] = {
                "w":      stats.get("wins", "0"),
                "l":      stats.get("losses", "0"),
                "pct":    stats.get("winPercent", ".000"),
                "gb":     stats.get("gamesBehind", "—"),
                "streak": stats.get("streak", ""),
                "rs":     stats.get("pointsFor", "0"),
                "ra":     stats.get("pointsAgainst", "0"),
                "div":    team.get("shortDisplayName", ""),
            }
    vlog(f"  MLB standings: {len(out)} teams")
    return out

def fetch_mlb_team_stats() -> dict:
    """Fetch MLB team batting/pitching stats from ESPN."""
    log("MLB team stats…")
    data = fetch_json(
        f"{ESPN_BASE}/baseball/mlb/teams?limit=30&enable=stats"
    )
    if not data:
        return {}
    out: dict = {}
    for t in (data.get("sports") or [{}])[0].get("leagues") or []:
        for team in t.get("teams") or []:
            td = team.get("team") or {}
            abbr = td.get("abbreviation", "")
            stats = {s.get("name"): s.get("displayValue")
                     for s in td.get("record", {}).get("items", [])}
            if abbr:
                out[abbr] = stats
    return out

# ═══════════════════════════════════════════════════════════════════════════════
# NBA
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_nba_scoreboard(date: str = TODAY_ET) -> tuple[list, list]:
    log(f"NBA scoreboard {date}…")
    data = fetch_json(f"{ESPN_BASE}/basketball/nba/scoreboard?dates={date}&limit=20")
    if not data:
        return [], []
    games = [_espn_game(e, "NBA") for e in (data.get("events") or [])]
    tom = (datetime.strptime(date, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
    data2 = fetch_json(f"{ESPN_BASE}/basketball/nba/scoreboard?dates={tom}&limit=20")
    tomorrow = [_espn_game(e, "NBA") for e in ((data2 or {}).get("events") or [])]
    vlog(f"  NBA: {len(games)} today, {len(tomorrow)} tomorrow")
    return games, tomorrow

def fetch_nba_standings() -> dict:
    log("NBA standings…")
    # Regular-season standings (most complete; playoffs don't have traditional standings)
    data = fetch_json(
        "https://site.web.api.espn.com/apis/v2/sports/basketball/nba/standings"
        "?region=us&lang=en&season=2026&type=2"
    )
    if not data:
        return {}
    out: dict = {}
    for conference in data.get("children") or []:
        for entry in (conference.get("standings") or {}).get("entries") or []:
            team  = entry.get("team") or {}
            abbr  = team.get("abbreviation", "")
            stats = {s["name"]: s.get("displayValue", s.get("value", ""))
                     for s in (entry.get("stats") or [])}
            out[abbr] = {
                "w":   stats.get("wins", "0"),
                "l":   stats.get("losses", "0"),
                "pct": stats.get("winPercent", ".000"),
                "gb":  stats.get("gamesBehind", "—"),
                "rs":  stats.get("avgPointsFor", "0"),
                "ra":  stats.get("avgPointsAgainst", "0"),
            }
    vlog(f"  NBA standings: {len(out)} teams")
    return out

def fetch_nba_player_stats() -> list[dict]:
    """Fetch NBA playoff scoring leaders from ESPN stats page."""
    log("NBA player stats…")
    players: dict[str, dict] = {}
    # ESPN stats API — correct endpoint for season leaders
    for stat_cat, stat_key in [
        ("points", "PTS"), ("rebounds", "REB"), ("assists", "AST"),
        ("steals", "STL"), ("blocks", "BLK"),
    ]:
        data = fetch_json(
            f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
            f"/leaders?season=2026&seasontype=3&limit=20"
        )
        if not data:
            break   # endpoint returns all categories at once
        for cat in data.get("categories") or []:
            cat_name = cat.get("name", "")
            for leader in cat.get("leaders") or []:
                athlete = (leader.get("athlete") or {})
                name = athlete.get("displayName", "")
                team = (athlete.get("team") or {}).get("abbreviation", "")
                if name not in players:
                    players[name] = {"name": name, "team": team}
                players[name][cat_name.upper()[:3]] = leader.get("displayValue", "—")
        break   # only need one call — all cats returned together
    return list(players.values())

# ═══════════════════════════════════════════════════════════════════════════════
# NHL
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_nhl_schedule(date: str = TODAY_NHL) -> tuple[list, list]:
    log(f"NHL schedule {date}…")
    data = fetch_json(f"{NHL_API}/schedule/{date}")
    if not data:
        return [], []

    def parse_games(day: dict) -> list[dict]:
        out = []
        for g in day.get("games") or []:
            home = g.get("homeTeam") or {}
            away = g.get("awayTeam") or {}
            state = g.get("gameState", "FUT")
            broadcasts = [b.get("network", "") for b in (g.get("tvBroadcasts") or [])]
            out.append({
                "id":         g.get("id"),
                "sport":      "NHL",
                "home":       home.get("abbrev", ""),
                "away":       away.get("abbrev", ""),
                "homeScore":  home.get("score") if state not in ("FUT", "PRE") else None,
                "awayScore":  away.get("score") if state not in ("FUT", "PRE") else None,
                "state":      state,
                "period":     g.get("period", 0),
                "clock":      (g.get("clock") or {}).get("timeRemaining", ""),
                "venue":      (g.get("venue") or {}).get("default", ""),
                "date":       g.get("startTimeUTC", ""),
                "network":    ", ".join(broadcasts),
                "gameType":   g.get("gameType", 2),   # 2=regular, 3=playoff
                "seriesStatus": (g.get("seriesSummary") or {}).get("seriesStatusShort", ""),
            })
        return out

    week = data.get("gameWeek") or []
    today_games    = parse_games(week[0] if week else {})
    tomorrow_games = parse_games(week[1] if len(week) > 1 else {})
    vlog(f"  NHL: {len(today_games)} today, {len(tomorrow_games)} tomorrow")
    return today_games, tomorrow_games

def fetch_nhl_standings() -> dict:
    log("NHL standings…")
    data = fetch_json(f"{NHL_API}/standings/now")
    if not data:
        return {}
    out: dict = {}
    for t in data.get("standings") or []:
        abbr = (t.get("teamAbbrev") or {}).get("default", "")
        out[abbr] = {
            "w":    t.get("wins", 0),
            "l":    t.get("losses", 0),
            "otl":  t.get("otLosses", 0),
            "pts":  t.get("points", 0),
            "gf":   t.get("goalFor", 0),
            "ga":   t.get("goalAgainst", 0),
            "gd":   t.get("goalDifferential", 0),
            "row":  t.get("regulationOrOvertimeWins", 0),
            "div":  (t.get("divisionName") or ""),
            "conf": (t.get("conferenceName") or ""),
        }
    vlog(f"  NHL standings: {len(out)} teams")
    return out

def fetch_nhl_edge() -> dict:
    """Fetch NHLEdge skater + goalie + team zone-time stats."""
    log("NHL Edge stats…")
    out: dict = {"teams": {}, "goalies": [], "skaters": []}

    # Team stats
    teams_data = fetch_json(
        "https://api.nhle.com/stats/rest/en/team/summary"
        "?isAggregate=false&isGame=false&sort=%5B%7B%22property%22:%22wins%22,"
        "%22direction%22:%22DESC%22%7D%5D&start=0&limit=50"
        "&cayenneExp=gameTypeId=3%20and%20seasonId%3E=20252026%20and%20seasonId%3C=20252026"
    )
    if teams_data:
        for t in teams_data.get("data") or []:
            abbr = t.get("teamAbbrevs", "")
            out["teams"][abbr] = {
                "gf60":     t.get("goalsForPer60", 0),
                "ga60":     t.get("goalsAgainstPer60", 0),
                "sf60":     t.get("shotsForPer60", 0),
                "sa60":     t.get("shotsAgainstPer60", 0),
                "ppPct":    t.get("powerPlayPct", 0),
                "pkPct":    t.get("penaltyKillPct", 0),
                "foPct":    t.get("faceoffWinPct", 0),
                "w":        t.get("wins", 0),
                "l":        t.get("losses", 0),
            }

    # Goalie stats
    goalies_data = fetch_json(
        "https://api.nhle.com/stats/rest/en/goalie/summary"
        "?isAggregate=false&isGame=false&sort=%5B%7B%22property%22:%22wins%22,"
        "%22direction%22:%22DESC%22%7D%5D&start=0&limit=30"
        "&cayenneExp=gameTypeId=3%20and%20seasonId%3E=20252026%20and%20seasonId%3C=20252026"
    )
    if goalies_data:
        for g in goalies_data.get("data") or []:
            out["goalies"].append({
                "name":     g.get("goalieFullName", ""),
                "team":     g.get("teamAbbrevs", ""),
                "gp":       g.get("gamesPlayed", 0),
                "w":        g.get("wins", 0),
                "l":        g.get("losses", 0),
                "savePct":  g.get("savePct", 0),
                "gaa":      g.get("goalsAgainstAverage", 0),
                "so":       g.get("shutouts", 0),
                "shots":    g.get("shotsAgainst", 0),
            })

    vlog(f"  NHL Edge: {len(out['teams'])} teams, {len(out['goalies'])} goalies")
    return out

def fetch_moneypuck() -> dict:
    """MoneyPuck advanced stats (5v5, 5v4, 4v5) via CSV."""
    log("MoneyPuck stats…")
    out: dict = {"teams": {}, "goalies": []}

    rows = fetch_csv_rows(f"{MP_BASE}/teams.csv")
    for row in rows:
        situation = row.get("situation", "")
        team = row.get("team", "")
        if not team:
            continue
        if team not in out["teams"]:
            out["teams"][team] = {}
        try:
            out["teams"][team][situation] = {
                "xgfPct":    float(row.get("xGoalsPercentage") or 0),
                "xgf":       float(row.get("xGoalsFor") or 0),
                "xga":       float(row.get("xGoalsAgainst") or 0),
                "cfPct":     float(row.get("corsiPercentage") or 0),
                "hdcfPct":   float(row.get("highDangerShotsFor") or 0),
                "gf":        float(row.get("goalsFor") or 0),
                "ga":        float(row.get("goalsAgainst") or 0),
                "shots":     float(row.get("shotsOnGoalFor") or 0),
            }
        except (ValueError, TypeError):
            pass

    rows_g = fetch_csv_rows(f"{MP_BASE}/goalies.csv")
    for row in rows_g:
        if row.get("situation", "") != "all":
            continue
        try:
            out["goalies"].append({
                "name":      row.get("name", ""),
                "team":      row.get("team", ""),
                "gp":        int(row.get("games_played") or 0),
                "gsaa":      float(row.get("goalsAboveAverage") or 0),
                "savePct":   float(row.get("savePct") or 0),
                "xSavePct":  float(row.get("xSavePct") or 0),
                "hdSavePct": float(row.get("highDangerSavePct") or 0),
                "shots":     int(row.get("shotsOnGoalAgainst") or 0),
                "ga":        float(row.get("goalsAgainst") or 0),
                "xga":       float(row.get("xGoalsAgainst") or 0),
            })
        except (ValueError, TypeError):
            pass

    out["goalies"].sort(key=lambda g: g["gsaa"], reverse=True)
    vlog(f"  MoneyPuck: {len(out['teams'])} teams, {len(out['goalies'])} goalies")
    return out

# ═══════════════════════════════════════════════════════════════════════════════
# Tennis
# ═══════════════════════════════════════════════════════════════════════════════
def _parse_tennis_table(soup: BeautifulSoup, limit: int = 100) -> list[dict]:
    """
    Parse TennisAbstract ELO report table.
    Table structure (columns): Rank | Player | Age | Elo | (spacer) |
      hElo_rank | hElo | cElo_rank | cElo | gElo_rank | gElo | ...
    Data is in <tbody> — use tbody.find_all('tr') to avoid misindexing.
    """
    # TennisAbstract has 3 tables: description, data, footer. Data table has 500+ rows.
    tables = soup.find_all("table")
    table = None
    for t in tables:
        tbody = t.find("tbody")
        if tbody and len(tbody.find_all("tr")) > 50:
            table = t
            break
    if not table:
        return []

    tbody = table.find("tbody")
    if not tbody:
        return []

    players = []
    for row in tbody.find_all("tr")[:limit]:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        def cell(n: int) -> str:
            return cells[n].get_text(strip=True).replace("\xa0", " ") if len(cells) > n else ""

        def icell(n: int) -> int:
            try:
                v = cell(n).replace(",", "").replace(" ", "")
                return int(float(v)) if v else 0
            except (ValueError, TypeError):
                return 0

        # Column layout: 0=rank, 1=name, 2=age, 3=Elo, 4=spacer,
        #   5=hElo_rank, 6=hElo, 7=cElo_rank, 8=cElo, 9=gElo_rank, 10=gElo
        players.append({
            "rank":     icell(0) or len(players) + 1,
            "name":     cell(1),
            "age":      cell(2),
            "elo":      icell(3),
            "eloHard":  icell(6),
            "eloClay":  icell(8),
            "eloGrass": icell(10),
        })
    return players

def fetch_tennis_elo(tour: str = "atp") -> list[dict]:
    log(f"TennisAbstract {tour.upper()} ELO…")
    url = f"https://tennisabstract.com/reports/{tour}_elo_ratings.html"
    soup = fetch_html(url)
    if not soup:
        return []
    players = _parse_tennis_table(soup)
    vlog(f"  {tour.upper()} ELO: {len(players)} players")
    return players

def fetch_tennis_yelo(tour: str = "atp") -> list[dict]:
    """Season-weighted yElo from TennisAbstract."""
    log(f"TennisAbstract {tour.upper()} yElo…")
    url = f"https://tennisabstract.com/reports/{tour}_season_yelo_ratings.html"
    soup = fetch_html(url)
    if not soup:
        return []

    tables = soup.find_all("table")
    table = None
    for t in tables:
        tbody = t.find("tbody")
        if tbody and len(tbody.find_all("tr")) > 50:
            table = t
            break
    if not table:
        return []

    tbody = table.find("tbody")
    if not tbody:
        return []

    players = []
    for i, row in enumerate(tbody.find_all("tr")[:100]):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        def cell(n: int) -> str:
            return cells[n].get_text(strip=True).replace("\xa0", " ") if len(cells) > n else ""

        def icell(n: int) -> int:
            try:
                v = cell(n).replace(",", "").replace(" ", "")
                return int(float(v)) if v else 0
            except (ValueError, TypeError):
                return 0

        players.append({
            "rank":     icell(0) or i + 1,
            "name":     cell(1),
            "yElo":     icell(2),
            "yEloClay": icell(3),
            "yEloHard": icell(4),
        })
    vlog(f"  {tour.upper()} yElo: {len(players)} players")
    return players

def fetch_tennis_schedule_espn(tour: str = "atp") -> list[dict]:
    """Scrape ESPN tennis schedule (may return empty if JS-rendered)."""
    suffix = "" if tour == "atp" else "/_/type/wta"
    soup = fetch_html(f"https://www.espn.com/tennis/schedule{suffix}")
    if not soup:
        return []
    # ESPN renders schedule dynamically — extract what static HTML has
    matches = []
    for row in (soup.select("tr.Table__TR") or []):
        cells = row.find_all("td")
        if len(cells) >= 3:
            matches.append({
                "tour": tour.upper(),
                "tournament": cells[0].get_text(strip=True),
                "surface": cells[1].get_text(strip=True) if len(cells) > 1 else "",
                "date": cells[2].get_text(strip=True) if len(cells) > 2 else "",
            })
    return matches

# ═══════════════════════════════════════════════════════════════════════════════
# Weather
# ═══════════════════════════════════════════════════════════════════════════════
_MLB_COORDS: dict[str, tuple[float, float, str]] = {
    "NYY": (40.8296, -73.9262, "Bronx NY"),
    "NYM": (40.7571, -73.8458, "Queens NY"),
    "BOS": (42.3467, -71.0972, "Boston MA"),
    "CHC": (41.9484, -87.6553, "Chicago IL"),
    "CHW": (41.8300, -87.6338, "Chicago IL"),
    "CLE": (41.4962, -81.6852, "Cleveland OH"),
    "DET": (42.3390, -83.0485, "Detroit MI"),
    "KC":  (39.0517, -94.4803, "Kansas City MO"),
    "LAA": (33.8003, -117.8827, "Anaheim CA"),
    "LAD": (34.0739, -118.2400, "Los Angeles CA"),
    "OAK": (37.7516, -122.2005, "Oakland CA"),
    "PHI": (39.9061, -75.1665, "Philadelphia PA"),
    "PIT": (40.4469, -80.0057, "Pittsburgh PA"),
    "CIN": (39.0975, -84.5066, "Cincinnati OH"),
    "STL": (38.6226, -90.1928, "St. Louis MO"),
    "WSH": (38.8730, -77.0074, "Washington DC"),
    "BAL": (39.2838, -76.6218, "Baltimore MD"),
    "SF":  (37.7786, -122.3893, "San Francisco CA"),
    "SD":  (32.7076, -117.1570, "San Diego CA"),
    "COL": (39.7559, -104.9942, "Denver CO"),
    "NYY": (40.8296, -73.9262, "Bronx NY"),
}
_INDOOR_TEAMS = {"MIN", "TOR", "TB", "MIA", "TEX", "HOU", "ARI", "ATL", "MIL", "SEA"}
_WMO_CODES = {
    0: "Clear", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Fog", 51: "Drizzle", 61: "Rain", 71: "Snow", 80: "Showers",
    95: "Thunderstorm",
}

def _wmo_desc(code: int) -> str:
    for k in sorted(_WMO_CODES, reverse=True):
        if code >= k:
            return _WMO_CODES[k]
    return "Unknown"

def fetch_weather(home_team: str) -> dict | None:
    if home_team in _INDOOR_TEAMS:
        return {"condition": "Dome/Retractable", "temp": None, "wind": None, "indoor": True}
    coords = _MLB_COORDS.get(home_team)
    if not coords:
        return None
    lat, lon, city = coords
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,wind_speed_10m,wind_direction_10m,weather_code"
        f"&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto"
    )
    data = fetch_json(url, timeout=10)
    if not data:
        return None
    c = data.get("current") or {}
    return {
        "condition": _wmo_desc(int(c.get("weather_code", 0))),
        "temp":      round(float(c.get("temperature_2m", 0))),
        "wind":      round(float(c.get("wind_speed_10m", 0))),
        "windDir":   round(float(c.get("wind_direction_10m", 0))),
        "city":      city,
        "indoor":    False,
    }

# ═══════════════════════════════════════════════════════════════════════════════
# Tennis schedule (ESPN — today's matches)
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_tennis_schedule() -> list[dict]:
    """Fetch today's ATP + WTA schedule from ESPN scoreboard API."""
    matches: list[dict] = []
    for tour in ("atp", "wta"):
        try:
            url = (f"https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}"
                   f"/scoreboard?dates={TODAY_ET}")
            data = fetch_json(url)
            for ev in (data.get("events") or []):
                comp = (ev.get("competitions") or [{}])[0]
                players = comp.get("competitors") or []
                p1  = players[0].get("athlete", {}).get("displayName", "TBD") if players else "TBD"
                p2  = players[1].get("athlete", {}).get("displayName", "TBD") if len(players) > 1 else "TBD"
                fl1 = players[0].get("athlete", {}).get("flag", {}).get("href", "") if players else ""
                fl2 = players[1].get("athlete", {}).get("flag", {}).get("href", "") if len(players) > 1 else ""
                st  = comp.get("status", {})
                state = st.get("type", {}).get("state", "pre")
                sc1 = players[0].get("score", "") if players else ""
                sc2 = players[1].get("score", "") if len(players) > 1 else ""
                venue = comp.get("venue", {})
                matches.append({
                    "tour":       tour.upper(),
                    "player1":    p1,
                    "player2":    p2,
                    "flag1":      fl1,
                    "flag2":      fl2,
                    "state":      state,
                    "score1":     sc1,
                    "score2":     sc2,
                    "statusText": st.get("type", {}).get("shortDetail", ""),
                    "tournament": venue.get("fullName", ""),
                    "round":      ev.get("season", {}).get("displayName", ""),
                    "date":       ev.get("date", ""),
                    "network":    (comp.get("broadcasts") or [{}])[0].get("names", [None])[0] or "",
                })
        except Exception as exc:
            log(f"Tennis schedule {tour}: {exc}", "WARN")
    log(f"Tennis schedule: {len(matches)} matches for {TODAY_ISO}")
    return matches


# ═══════════════════════════════════════════════════════════════════════════════
# Formula 1 (ESPN + Ergast)
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_f1() -> dict:
    """Fetch F1 race schedule, driver standings, and constructor standings."""
    result: dict = {"schedule": [], "driverStandings": [], "constructorStandings": [], "nextRace": None}
    year = (NOW - timedelta(hours=5)).year

    # Race schedule from Ergast
    try:
        data = fetch_json(f"http://ergast.com/api/f1/{year}.json?limit=25")
        races = (data.get("MRData", {}).get("RaceTable", {}).get("Races") or [])
        today_iso = TODAY_ISO  # YYYY-MM-DD
        for race in races:
            race_date = race.get("date", "")
            result["schedule"].append({
                "round":    int(race.get("round", 0)),
                "name":     race.get("raceName", ""),
                "circuit":  race.get("Circuit", {}).get("circuitName", ""),
                "country":  race.get("Circuit", {}).get("Location", {}).get("country", ""),
                "date":     race_date,
                "time":     race.get("time", ""),
                "past":     race_date < today_iso,
            })
            if race_date >= today_iso and result["nextRace"] is None:
                result["nextRace"] = result["schedule"][-1]
    except Exception as exc:
        log(f"F1 schedule (Ergast): {exc}", "WARN")

    # Driver standings
    try:
        data = fetch_json(f"http://ergast.com/api/f1/{year}/driverStandings.json")
        for s in (data.get("MRData", {}).get("StandingsTable", {})
                      .get("StandingsLists", [{}])[0].get("DriverStandings") or [])[:20]:
            drv = s.get("Driver", {})
            ctor = (s.get("Constructors") or [{}])[0]
            result["driverStandings"].append({
                "pos":    int(s.get("position", 99)),
                "name":   f"{drv.get('givenName','')} {drv.get('familyName','')}".strip(),
                "code":   drv.get("code", ""),
                "team":   ctor.get("name", ""),
                "pts":    float(s.get("points", 0)),
                "wins":   int(s.get("wins", 0)),
                "nat":    drv.get("nationality", ""),
            })
    except Exception as exc:
        log(f"F1 driver standings (Ergast): {exc}", "WARN")

    # Constructor standings
    try:
        data = fetch_json(f"http://ergast.com/api/f1/{year}/constructorStandings.json")
        for s in (data.get("MRData", {}).get("StandingsTable", {})
                      .get("StandingsLists", [{}])[0].get("ConstructorStandings") or [])[:10]:
            ctor = s.get("Constructor", {})
            result["constructorStandings"].append({
                "pos":  int(s.get("position", 99)),
                "name": ctor.get("name", ""),
                "pts":  float(s.get("points", 0)),
                "wins": int(s.get("wins", 0)),
            })
    except Exception as exc:
        log(f"F1 constructor standings (Ergast): {exc}", "WARN")

    # ESPN F1 standings (top 10)
    try:
        espn_data = fetch_json(f"{ESPN_BASE}/racing/f1/standings")
        if espn_data:
            espn_standings = (espn_data.get("standings", {}).get("entries") or [])[:10]
            result["espnStandings"] = [
                {
                    "pos": int(e.get("stats", [{}])[0].get("value", i + 1)),
                    "name": e.get("athlete", {}).get("displayName", ""),
                    "team": e.get("team", {}).get("displayName", ""),
                    "pts": float((next((s for s in e.get("stats", []) if s.get("name") == "points"), {}) or {}).get("value", 0)),
                }
                for i, e in enumerate(espn_standings)
            ]
    except Exception as exc:
        log(f"F1 ESPN standings: {exc}", "WARN")
        result["espnStandings"] = []

    log(f"F1: {len(result['schedule'])} races | {len(result['driverStandings'])} drivers | next: {result['nextRace'] and result['nextRace']['name']}")
    return result


def fetch_f1_analytics() -> dict:
    """Fetch F1 race analysis data from f1datastop.com."""
    url = "https://f1datastop.com/race-analysis"
    result: dict = {"source": "f1datastop.com", "fetchedAt": TODAY_ISO, "data": [], "error": None}
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        r = requests.get(url, headers=headers, timeout=20)
        if r.ok:
            soup = BeautifulSoup(r.text, "html.parser")
            # Extract race analysis cards/sections
            cards = soup.find_all(["article", "section", "div"], class_=lambda c: c and any(
                k in c for k in ["race", "analysis", "driver", "lap", "pace"]
            ))
            for card in cards[:20]:
                txt = card.get_text(separator=" ", strip=True)
                if len(txt) > 30:
                    result["data"].append({"text": txt[:300], "tag": card.name})
            # Also grab any tables
            tables = soup.find_all("table")
            for tbl in tables[:5]:
                rows = tbl.find_all("tr")
                for row in rows[:15]:
                    cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                    if cells:
                        result["data"].append({"row": cells})
        else:
            result["error"] = f"HTTP {r.status_code}"
    except Exception as exc:
        result["error"] = str(exc)
        log(f"F1 analytics (f1datastop.com): {exc}", "WARN")
    log(f"F1 analytics: {len(result['data'])} items | error: {result['error']}")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Linemate cheatsheet (recent-form — Playwright optional)
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_linemate_cheatsheet(sport: str) -> list[dict]:
    """Scrape Linemate recent-form cheatsheet for prop trend context."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    url = f"https://linemate.io/{sport}/cheatsheets/recent-form"
    items: list[dict] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = browser.new_context(user_agent=HEADERS["User-Agent"],
                                      viewport={"width": 1280, "height": 900})
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle", timeout=45_000)
            page.wait_for_timeout(3_000)
            for sel in ["[class*='Row']", "[class*='row']", "table tr", "li", "article"]:
                rows = page.query_selector_all(sel)
                if len(rows) > 3:
                    for row in rows[:80]:
                        txt = row.inner_text().strip()
                        if len(txt) > 8:
                            items.append({"raw": txt, "sport": sport.upper(), "src": "Linemate/form"})
                    break
            browser.close()
        log(f"Linemate cheatsheet {sport}: {len(items)} rows")
    except Exception as exc:
        log(f"Linemate cheatsheet {sport}: {exc}", "WARN")
    return items


def fetch_linemate_trends(sport: str) -> list[dict]:
    """Scrape Linemate trends page for player and team trend data."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    url = f"https://linemate.io/{sport}/trends"
    trends: list[dict] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = browser.new_context(user_agent=HEADERS["User-Agent"],
                                      viewport={"width": 1280, "height": 900})
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle", timeout=45_000)
            page.wait_for_timeout(4_000)
            # Try multiple selectors for trend rows
            selectors = [
                "[class*='TrendRow']", "[class*='trend-row']", "[class*='PlayerRow']",
                "[class*='player-row']", "table tr", "li[class*='trend']", "article",
            ]
            rows = []
            for sel in selectors:
                rows = page.query_selector_all(sel)
                if len(rows) > 3:
                    break
            for row in rows[:100]:
                try:
                    txt = row.inner_text().strip()
                    if len(txt) < 8:
                        continue
                    # Parse raw text into structured fields
                    parts = [p.strip() for p in txt.split("\n") if p.strip()]
                    player = parts[0] if parts else txt[:40]
                    category = parts[1] if len(parts) > 1 else ""
                    # Detect trend direction from keywords
                    txt_lower = txt.lower()
                    if any(k in txt_lower for k in ["hot", "fire", "🔥", "streak"]):
                        direction = "hot"
                    elif any(k in txt_lower for k in ["cold", "slump", "❄"]):
                        direction = "cold"
                    elif any(k in txt_lower for k in ["up", "↑", "rising", "over"]):
                        direction = "up"
                    elif any(k in txt_lower for k in ["down", "↓", "falling", "under"]):
                        direction = "down"
                    else:
                        direction = "neutral"
                    # Try to extract L5/L10 hit rates from numeric tokens
                    nums = re.findall(r'(\d+)/(\d+)', txt)
                    l5 = f"{nums[0][0]}/{nums[0][1]}" if nums else ""
                    l10 = f"{nums[1][0]}/{nums[1][1]}" if len(nums) > 1 else ""
                    # Line movement
                    line_move = "up" if "line up" in txt_lower or "moved up" in txt_lower else \
                                "down" if "line down" in txt_lower or "moved down" in txt_lower else ""
                    trends.append({
                        "player": player,
                        "category": category,
                        "direction": direction,
                        "l5": l5,
                        "l10": l10,
                        "lineMove": line_move,
                        "raw": txt[:200],
                        "sport": sport.upper(),
                        "src": "Linemate/trends",
                    })
                except Exception:
                    pass
            browser.close()
        log(f"Linemate trends {sport}: {len(trends)} entries")
    except Exception as exc:
        log(f"Linemate trends {sport}: {exc}", "WARN")
    return trends


# ═══════════════════════════════════════════════════════════════════════════════
# Linemate props (Playwright — optional)
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_linemate_props(sport: str) -> list[dict]:
    """
    Scrape linemate.io prop cards using Playwright (headless Chromium).
    Requires: pip install playwright && playwright install chromium
    Falls back gracefully if Playwright is not installed.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        vlog("Playwright not installed — skipping Linemate. Run: pip install playwright && playwright install chromium")
        return []

    url = f"https://linemate.io/{sport}"
    props: list[dict] = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 900},
            )
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle", timeout=45_000)
            page.wait_for_timeout(4_000)   # let JS hydrate

            # Try multiple selectors — linemate changes class names
            selectors = [
                "[class*='PlayerPropCard']",
                "[class*='prop-card']",
                "[class*='PropCard']",
                "[data-testid*='prop']",
                "article",
            ]
            cards = []
            for sel in selectors:
                cards = page.query_selector_all(sel)
                if cards:
                    break

            for card in cards[:60]:
                try:
                    text = card.inner_text().strip()
                    if len(text) < 10:
                        continue
                    props.append({
                        "raw":   text,
                        "sport": sport.upper(),
                        "src":   "Linemate",
                    })
                except Exception:
                    continue

            browser.close()
        log(f"Linemate {sport.upper()}: {len(props)} prop cards scraped")
    except Exception as e:
        log(f"Linemate {sport} error: {e}", "WARN")

    return props

# ═══════════════════════════════════════════════════════════════════════════════
# Best bets calculator
# ═══════════════════════════════════════════════════════════════════════════════
def _ml_to_prob(ml) -> float | None:
    try:
        ml = int(ml)
        return abs(ml) / (abs(ml) + 100) if ml < 0 else 100 / (ml + 100)
    except (TypeError, ValueError):
        return None

def _ml_to_dec(ml) -> float:
    try:
        ml = int(ml)
        return (100 / abs(ml) + 1) if ml < 0 else (ml / 100 + 1)
    except (TypeError, ValueError):
        return 1.91

def _ev(prob: float, dec_odds: float) -> float:
    return prob * dec_odds - 1

def calculate_best_bets(
    nba_today: list, mlb_today: list, nhl_today: list, weather: dict
) -> list[dict]:
    log("Calculating best bets…")
    picks: list[dict] = []

    def add(sport, game_str, pick_str, prob, ml, grade, note=""):
        dec = _ml_to_dec(ml)
        ev = round(_ev(prob, dec) * 100, 1)
        picks.append({
            "sport":   sport,
            "game":    game_str,
            "pick":    pick_str,
            "prob":    round(prob * 100, 1),
            "ev":      ev,
            "ml":      f"+{ml}" if isinstance(ml, int) and ml > 0 else str(ml),
            "grade":   grade,
            "note":    note,
        })

    # NBA moneylines — find +EV favorites
    for g in nba_today:
        if g.get("state") != "pre":
            continue
        hml, aml = g.get("homeML"), g.get("awayML")
        hprob, aprob = _ml_to_prob(hml), _ml_to_prob(aml)
        home, away = g.get("home", ""), g.get("away", "")
        game_str = f"{away} @ {home}"

        if hprob and hprob > 0.62:
            add("NBA", game_str, f"{home} ML {hml}", hprob,
                hml, "LOCK" if hprob > 0.67 else "GOOD",
                note=g.get("seriesNote", ""))
        elif aprob and aprob > 0.62:
            add("NBA", game_str, f"{away} ML {aml}", aprob,
                aml, "LOCK" if aprob > 0.67 else "GOOD",
                note=g.get("seriesNote", ""))

        # O/U: flag if lines are available
        ou = g.get("ou")
        if ou and hml and aml:
            picks.append({
                "sport": "NBA", "game": game_str,
                "pick": f"O/U {ou}", "prob": 52.0, "ev": 0.0,
                "ml": "-110", "grade": "INFO",
                "note": f"Line: {home} {hml} / {away} {aml}",
            })

    # MLB — wind-adjusted O/U + moneylines
    for g in mlb_today:
        if g.get("state") != "pre":
            continue
        home, away = g.get("home", ""), g.get("away", "")
        game_str = f"{away} @ {home}"
        w = weather.get(home, {})
        hml, aml = g.get("homeML"), g.get("awayML")
        ou = g.get("ou")

        # Wind factor
        if w and not w.get("indoor"):
            wind = w.get("wind", 0) or 0
            wind_dir = w.get("windDir", 0) or 0
            blowing_out = 45 <= wind_dir <= 135
            if wind >= 12 and ou:
                pick_dir = "OVER" if blowing_out else "UNDER"
                prob = 0.58 if wind >= 18 else 0.54
                add("MLB", game_str,
                    f"{pick_dir} {ou} (wind {wind}mph {'out' if blowing_out else 'in'})",
                    prob, -110, "GOOD" if prob > 0.56 else "INFO",
                    note=f"{w.get('condition')}, {w.get('temp')}°F")

        # Heavy ML favorites
        hprob, aprob = _ml_to_prob(hml), _ml_to_prob(aml)
        if hprob and hprob > 0.65:
            add("MLB", game_str, f"{home} ML {hml}", hprob,
                hml, "LOCK" if hprob > 0.70 else "GOOD")
        elif aprob and aprob > 0.65:
            add("MLB", game_str, f"{away} ML {aml}", aprob,
                aml, "LOCK" if aprob > 0.70 else "GOOD")

    # NHL moneylines
    for g in nhl_today:
        if g.get("state") not in ("FUT", "PRE"):
            continue
        # NHL odds come from ESPN overlay or embedded — only if present
        hml, aml = g.get("homeML"), g.get("awayML")
        home, away = g.get("home", ""), g.get("away", "")
        game_str = f"{away} @ {home}"
        hprob, aprob = _ml_to_prob(hml), _ml_to_prob(aml)
        if hprob and hprob > 0.60:
            add("NHL", game_str, f"{home} ML {hml}", hprob,
                hml, "GOOD", note=g.get("seriesStatus", ""))

    # Sort by grade then EV
    grade_order = {"LOCK": 0, "GOOD": 1, "INFO": 2}
    picks.sort(key=lambda p: (grade_order.get(p["grade"], 9), -p["ev"]))
    top = picks[:12]

    (DATA / "best_bets.json").write_text(json.dumps(top, indent=2))
    log(f"Best bets: {len(top)} picks generated")
    return top

# ═══════════════════════════════════════════════════════════════════════════════
# Auto-settle (server-side)
# ═══════════════════════════════════════════════════════════════════════════════
def auto_settle(
    nba_final: list, mlb_final: list, nhl_final: list
) -> list[dict]:
    """
    Compare locked bets against final scores.
    Reads data/locked_props.json (exported by frontend via exportBets()),
    writes data/settled.json for the frontend to import on next load.
    """
    locked_path  = DATA / "locked_props.json"
    settled_path = DATA / "settled.json"

    if not locked_path.exists():
        vlog("No locked_props.json — skipping server-side auto-settle")
        return []

    locked: list[dict] = json.loads(locked_path.read_text())
    existing: list[dict] = json.loads(settled_path.read_text()) if settled_path.exists() else []
    settled_ids = {s["id"] for s in existing}
    new_settled = list(existing)

    # Build final-score lookup: (home, away) → game
    def game_index(games: list) -> dict:
        idx = {}
        for g in games:
            h, a = g.get("home", ""), g.get("away", "")
            state = str(g.get("state", ""))
            if state in ("post", "FINAL", "OFF", "7") and h and a:
                idx[(h, a)] = g
                idx[(a, h)] = g
        return idx

    all_idx: dict = {}
    all_idx.update(game_index(nba_final))
    all_idx.update(game_index(mlb_final))
    all_idx.update(game_index(nhl_final))

    settled_count = 0
    for bet in locked:
        if bet.get("outcome") != "pending":
            continue
        if bet.get("id", "") in settled_ids:
            continue

        hA, awA = bet.get("hA", ""), bet.get("awA", "")
        game = all_idx.get((hA, awA))
        if not game:
            continue

        hs = int(game.get("homeScore") or 0)
        as_ = int(game.get("awayScore") or 0)
        bet_type = bet.get("betType", "ML")
        outcome = None

        if bet_type == "ML":
            winner = game.get("home") if hs > as_ else game.get("away")
            outcome = "win" if bet.get("team", "") == winner else "loss"

        elif bet_type in ("RL", "PL"):
            line = float(str(bet.get("line", "1.5")).replace("+", "").replace("−", "-") or 1.5)
            is_home = bet.get("team") == game.get("home")
            diff = (hs - as_) if is_home else (as_ - hs)
            if diff + line > 0:
                outcome = "win"
            elif diff + line == 0:
                outcome = "push"
            else:
                outcome = "loss"

        elif bet_type == "OU":
            total = hs + as_
            line_val = float(bet.get("ou") or bet.get("line") or 0)
            over = "OVER" in str(bet.get("betOn", "")).upper() or bet.get("over", True)
            if over:
                outcome = "win" if total > line_val else ("push" if total == line_val else "loss")
            else:
                outcome = "win" if total < line_val else ("push" if total == line_val else "loss")

        elif bet_type == "PROP":
            # Props cannot be settled from final game score alone — skip
            continue

        if outcome:
            sb = {**bet, "outcome": outcome,
                  "settledAt": NOW.isoformat(),
                  "hScore": hs, "aScore": as_}
            new_settled.append(sb)
            settled_ids.add(bet.get("id", ""))
            settled_count += 1
            log(f"  SETTLED: {bet.get('betOn', '')} → {outcome.upper()}")

    settled_path.write_text(json.dumps(new_settled, indent=2))
    log(f"Auto-settle: +{settled_count} new, {len(new_settled)} total")
    return new_settled

# ═══════════════════════════════════════════════════════════════════════════════
# Bundle + data.json writer
# ═══════════════════════════════════════════════════════════════════════════════
def write_data_json(bundle: dict) -> None:
    payload = json.dumps(bundle, indent=2)
    FE_DATA.write_text(payload)
    DC_DATA.write_text(payload)
    note(f"data.json written ({len(payload)//1024} KB) → frontend/ + docs/")

# ═══════════════════════════════════════════════════════════════════════════════
# HTML timestamp patch
# ═══════════════════════════════════════════════════════════════════════════════
def patch_html_timestamp() -> None:
    html = FE.read_text(encoding="utf-8")
    original = html

    # Pattern: LAST_AUTO_UPDATE = 'YYYY-MM-DD HH:MM ET'
    ts_pat = r"(LAST_AUTO_UPDATE\s*=\s*['\"])([^'\"]*?)(['\"])"
    if re.search(ts_pat, html):
        html = re.sub(ts_pat, rf"\g<1>{TS_DISPLAY}\g<3>", html)
    else:
        # Inject declaration near the top of the first <script> block
        html = html.replace(
            "<script>",
            f"<script>\n  const LAST_AUTO_UPDATE = '{TS_DISPLAY}';",
            1,
        )

    # Cache-bust the data.json fetch query param
    cb = int(time.time())
    cb_pat = r"(data\.json\?)\d+"
    if re.search(cb_pat, html):
        html = re.sub(cb_pat, rf"\g<1>{cb}", html)

    if html != original:
        FE.write_text(html, encoding="utf-8")
        DOCS.write_text(html, encoding="utf-8")
        note("HTML timestamp updated")

# ═══════════════════════════════════════════════════════════════════════════════
# Git push
# ═══════════════════════════════════════════════════════════════════════════════
def git_push(summary: str) -> bool:
    try:
        os.chdir(ROOT)
        # Stage data outputs
        subprocess.run(
            ["git", "add",
             "frontend/index.html", "docs/index.html",
             "frontend/data.json",  "docs/data.json",
             "data/"],
            check=True, capture_output=True,
        )
        result = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            capture_output=True, text=True,
        )
        if not result.stdout.strip():
            log("Git: nothing to commit")
            return False

        msg = (
            f"auto: data refresh {TS_DISPLAY}\n\n"
            f"{summary}\n\n"
            "Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
        )
        subprocess.run(["git", "commit", "-m", msg], check=True, capture_output=True)
        subprocess.run(["git", "push", "origin", "main"], check=True, capture_output=True)
        log("Git: pushed to origin/main ✓")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Git error: {e.stderr.decode()}", "ERROR")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# Main orchestrator
# ═══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    global _verbose

    parser = argparse.ArgumentParser(description="Clairvoyance daily data refresh")
    parser.add_argument("--push",        action="store_true", help="Commit + push to GitHub")
    parser.add_argument("--dry-run",     action="store_true", help="Fetch only, skip writes")
    parser.add_argument("--no-linemate", action="store_true", help="Skip Linemate (no Playwright)")
    parser.add_argument("--sport",       choices=["nba","mlb","nhl","tennis","f1","all"], default="all")
    parser.add_argument("--verbose","-v",action="store_true")
    args = parser.parse_args()
    _verbose = args.verbose

    log(f"{'='*60}")
    log(f"Clairvoyance Update — {TS_DISPLAY}")
    log(f"Sport filter: {args.sport}")
    log(f"{'='*60}")

    # ── fetch phase ───────────────────────────────────────────────────────────
    mlb_today, mlb_tom     = fetch_mlb_scoreboard()   if args.sport in ("mlb","all") else ([], [])
    mlb_standings          = fetch_mlb_standings()     if args.sport in ("mlb","all") else {}
    nba_today, nba_tom     = fetch_nba_scoreboard()    if args.sport in ("nba","all") else ([], [])
    nba_standings          = fetch_nba_standings()     if args.sport in ("nba","all") else {}
    nba_players            = fetch_nba_player_stats()  if args.sport in ("nba","all") else []
    nhl_today, nhl_tom     = fetch_nhl_schedule()      if args.sport in ("nhl","all") else ([], [])
    nhl_standings          = fetch_nhl_standings()     if args.sport in ("nhl","all") else {}
    nhl_edge               = fetch_nhl_edge()          if args.sport in ("nhl","all") else {}
    mp                     = fetch_moneypuck()         if args.sport in ("nhl","all") else {}
    atp_elo                = fetch_tennis_elo("atp")      if args.sport in ("tennis","all") else []
    wta_elo                = fetch_tennis_elo("wta")      if args.sport in ("tennis","all") else []
    atp_yelo               = fetch_tennis_yelo("atp")     if args.sport in ("tennis","all") else []
    wta_yelo               = fetch_tennis_yelo("wta")     if args.sport in ("tennis","all") else []
    tennis_schedule        = fetch_tennis_schedule()      if args.sport in ("tennis","all") else []
    f1_data                = fetch_f1()                   if args.sport in ("f1","all") else {}
    f1_analytics           = fetch_f1_analytics()         if args.sport in ("f1","all") else {}

    # Weather for MLB home teams
    weather: dict = {}
    if args.sport in ("mlb", "all"):
        log("Fetching MLB weather…")
        for g in mlb_today:
            home = g.get("home", "")
            if home and home not in weather:
                w = fetch_weather(home)
                if w:
                    weather[home] = w
                time.sleep(0.3)   # rate-limit Open-Meteo

    # Linemate props + cheatsheets + trends (optional, requires Playwright)
    lm_props: dict = {"nba": [], "mlb": [], "nhl": []}
    lm_cheatsheets: dict = {"nba": [], "mlb": [], "nhl": []}
    lm_trends: dict = {"mlb": [], "nhl": []}
    if not args.no_linemate:
        for sport in ["nba", "mlb", "nhl"]:
            if args.sport in (sport, "all"):
                lm_props[sport] = fetch_linemate_props(sport)
                time.sleep(1)
                lm_cheatsheets[sport] = fetch_linemate_cheatsheet(sport)
                time.sleep(1)
        # Fetch trends for MLB and NHL
        for sport in ["mlb", "nhl"]:
            if args.sport in (sport, "all"):
                lm_trends[sport] = fetch_linemate_trends(sport)
                time.sleep(2)

    # ── calculate ─────────────────────────────────────────────────────────────
    best_bets = calculate_best_bets(nba_today, mlb_today, nhl_today, weather)
    settled   = auto_settle(nba_today + nba_tom, mlb_today + mlb_tom, nhl_today + nhl_tom)

    # ── bundle ────────────────────────────────────────────────────────────────
    bundle = {
        "generated":    NOW.isoformat(),
        "generatedET":  TS_DISPLAY,
        "mlb": {
            "today":     mlb_today,
            "tomorrow":  mlb_tom,
            "standings": mlb_standings,
        },
        "nba": {
            "today":     nba_today,
            "tomorrow":  nba_tom,
            "standings": nba_standings,
            "players":   nba_players,
        },
        "nhl": {
            "today":     nhl_today,
            "tomorrow":  nhl_tom,
            "standings": nhl_standings,
            "edge":      nhl_edge,
        },
        "mp":      mp,
        "weather": weather,
        "tennis": {
            "atpElo":    atp_elo[:100],
            "wtaElo":    wta_elo[:100],
            "atpYelo":   atp_yelo[:100],
            "wtaYelo":   wta_yelo[:100],
            "schedule":  tennis_schedule,
            "scheduleDate": TODAY_ISO,
        },
        "f1": {**f1_data, "analytics": f1_analytics},
        "linemate":      lm_props,
        "linemateForm":  {**lm_cheatsheets, "mlbTrends": lm_trends.get("mlb", []), "nhlTrends": lm_trends.get("nhl", [])},
        "bestBets":  best_bets,
        "settled":   settled,
    }

    # Save full bundle for debugging
    (DATA / "bundle.json").write_text(json.dumps(bundle, indent=2))

    if args.dry_run:
        log("Dry run — skipping writes and push")
        return

    # ── write data.json ───────────────────────────────────────────────────────
    write_data_json(bundle)
    patch_html_timestamp()

    # ── generate social content ───────────────────────────────────────────────
    try:
        from content_generator import generate_content, write_social_copy
        from generate_card import generate_card
        social = generate_content(bundle, verbose=_verbose)
        if social:
            write_social_copy(social)
            note("social_copy.json written")
            # Generate card image
            img = generate_card(bundle, social)
            fe_card = ROOT / "frontend" / "card.png"
            dc_card = ROOT / "docs"     / "card.png"
            img.save(str(fe_card), format="PNG", optimize=True)
            img.save(str(dc_card), format="PNG", optimize=True)
            note(f"card.png written ({fe_card.stat().st_size//1024} KB)")
    except Exception as exc:
        log(f"Content generation skipped: {exc}", "WARN")

    # ── git push ──────────────────────────────────────────────────────────────
    if args.push:
        summary_lines = [
            f"MLB: {len(mlb_today)} games today",
            f"NBA: {len(nba_today)} games today",
            f"NHL: {len(nhl_today)} games today",
            f"ATP ELO: {len(atp_elo)} players | WTA ELO: {len(wta_elo)} players",
            f"Best bets: {len(best_bets)} | Settled: {len(settled)}",
        ]
        if any(lm_props.values()):
            summary_lines.append(f"Linemate: {sum(len(v) for v in lm_props.values())} props")
        git_push("\n".join(summary_lines))

    log(f"{'='*60}")
    log(f"Update complete. Changes: {len(_changes)}")
    for c in _changes:
        log(f"  • {c}")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
