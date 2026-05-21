#!/usr/bin/env python3
from __future__ import annotations
"""
clairvoyance_update.py — Clairvoyance Master Data Refresh Engine v5.0
Fetches live stats, odds, schedules, standings, props, injuries, advanced
analytics across MLB, NBA, NHL, Tennis, F1 then pushes to GitHub Pages.

Usage:
  python3 scripts/clairvoyance_update.py                  # full fetch + write
  python3 scripts/clairvoyance_update.py --push           # + git push
  python3 scripts/clairvoyance_update.py --mode live      # live-window loop (17:00–23:00 MT)
  python3 scripts/clairvoyance_update.py --mode props     # Linemate only
  python3 scripts/clairvoyance_update.py --sport nhl      # single sport
  python3 scripts/clairvoyance_update.py --no-linemate    # skip Playwright
  python3 scripts/clairvoyance_update.py --no-reference   # skip Baseball/Basketball/Hockey Ref
  python3 scripts/clairvoyance_update.py --verbose

Cron (MT times — TZ=America/Denver):
  0 8,12,16,20,0 * * *  full refresh + push
  0 17           * * *  live-window mode (self-terminates 23:00 MT)
"""

import argparse, csv, io, json, os, re, shutil, subprocess, sys, time
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

# ── dependency bootstrap ──────────────────────────────────────────────────────
try:
    import requests
    from bs4 import BeautifulSoup, Comment
except ImportError:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "lxml"],
        check=True, capture_output=True,
    )
    import requests
    from bs4 import BeautifulSoup, Comment

# ── paths & config ────────────────────────────────────────────────────────────
ROOT     = Path(__file__).parent.parent
FE       = ROOT / "frontend" / "index.html"   # SPA — local only, never pushed to docs/
FE_DATA  = ROOT / "frontend" / "data.json"    # engine data stays in frontend/ only
DATA     = ROOT / "data"
LOGS     = ROOT / "logs"

for _d in (DATA, LOGS):
    _d.mkdir(exist_ok=True)

BET_HISTORY_JSON = DATA / "bet_history.json"
BET_HISTORY_CSV  = DATA / "bet_history.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}
REF_HEADERS = {          # Sports-Reference sites want a real browser UA
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.google.com/",
}

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
NHL_API   = "https://api-web.nhle.com/v1"
NHL_STATS = "https://api.nhle.com/stats/rest/en"
MP_BASE_REG     = "https://moneypuck.com/moneypuck/playerData/seasonSummary/2025/regular"
MP_BASE_PLAYOFF = "https://moneypuck.com/moneypuck/playerData/seasonSummary/2024/playoff"  # fallback
SEASON    = "20252026"
YEAR      = 2026

NOW        = datetime.now(timezone.utc)
try:
    import zoneinfo
    _MT = zoneinfo.ZoneInfo("America/Denver")
    NOW_MT = datetime.now(_MT)
except Exception:
    NOW_MT = NOW - timedelta(hours=6)

TODAY_MT   = NOW_MT.strftime("%Y%m%d")
TODAY_ISO  = NOW_MT.strftime("%Y-%m-%d")
TS_DISPLAY = NOW_MT.strftime("%Y-%m-%d %H:%M MT")

_verbose  = False
_changes: list[str] = []

# ── logging ───────────────────────────────────────────────────────────────────
def log(msg: str, level: str = "INFO") -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{level}] {msg}", flush=True)

def vlog(msg: str) -> None:
    if _verbose: log(msg, "DEBUG")

def note(msg: str) -> None:
    _changes.append(msg); log(msg)

# ── HTTP helpers ──────────────────────────────────────────────────────────────
_session = requests.Session()
_session.headers.update(HEADERS)
_ref_session = requests.Session()
_ref_session.headers.update(REF_HEADERS)

def fetch_json(url: str, timeout: int = 15, retries: int = 2, params: dict | None = None) -> dict | list | None:
    for attempt in range(retries + 1):
        try:
            r = _session.get(url, timeout=timeout, params=params)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries:
                log(f"FAILED {url}: {e}", "WARN"); return None
            time.sleep(2 ** attempt)

def fetch_html(url: str, timeout: int = 25, ref: bool = False) -> BeautifulSoup | None:
    sess = _ref_session if ref else _session
    try:
        r = sess.get(url, timeout=timeout)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        log(f"FAILED HTML {url}: {e}", "WARN"); return None

def fetch_csv_rows(url: str, timeout: int = 20) -> list[dict]:
    try:
        r = _session.get(url, timeout=timeout)
        r.raise_for_status()
        return list(csv.DictReader(io.StringIO(r.text)))
    except Exception as e:
        log(f"FAILED CSV {url}: {e}", "WARN"); return []

def _table_to_rows(soup: BeautifulSoup, table_id: str, limit: int = 60) -> list[dict]:
    """Extract a BeautifulSoup <table> (including commented-out SR tables) into row dicts."""
    table = soup.find("table", id=table_id)
    if not table:
        # Sports-Reference embeds tables in HTML comments
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            if table_id in comment:
                fragment = BeautifulSoup(comment, "lxml")
                table = fragment.find("table", id=table_id)
                if table:
                    break
    if not table:
        return []
    thead = table.find("thead")
    cols  = [th.get("data-stat", th.get_text(strip=True)) for th in thead.find_all("th")] if thead else []
    rows  = []
    for tr in (table.find("tbody") or table).find_all("tr")[:limit]:
        if "thead" in (tr.get("class") or []):
            continue
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        row = {}
        for i, td in enumerate(cells):
            key = cols[i] if i < len(cols) else f"c{i}"
            row[key] = td.get_text(strip=True)
        if any(v for v in row.values()):
            rows.append(row)
    return rows

# ── ESPN generic helpers ──────────────────────────────────────────────────────
def _espn_odds(comp: dict) -> dict:
    odds = (comp.get("odds") or [{}])[0]
    return {
        "homeML":   odds.get("homeTeamOdds", {}).get("moneyLine"),
        "awayML":   odds.get("awayTeamOdds", {}).get("moneyLine"),
        "ou":       odds.get("overUnder"),
        "spread":   odds.get("spread"),
        "provider": (odds.get("provider") or {}).get("name", ""),
    }

def _espn_game(event: dict, sport: str) -> dict:
    comp  = (event.get("competitions") or [{}])[0]
    comps = comp.get("competitors") or []
    home  = next((c for c in comps if c.get("homeAway") == "home"), {})
    away  = next((c for c in comps if c.get("homeAway") == "away"), {})
    status = event.get("status") or {}
    state  = (status.get("type") or {}).get("state", "pre")
    g: dict = {
        "id":          event.get("id", ""),
        "sport":       sport,
        "home":        (home.get("team") or {}).get("abbreviation", ""),
        "away":        (away.get("team") or {}).get("abbreviation", ""),
        "homeScore":   home.get("score") if state != "pre" else None,
        "awayScore":   away.get("score") if state != "pre" else None,
        "state":       state,
        "period":      status.get("period", 0),
        "displayClock": status.get("displayClock", ""),
        "venue":       (comp.get("venue") or {}).get("fullName", ""),
        "date":        event.get("date", ""),
        "network":     ((comp.get("broadcasts") or [{}])[0].get("names") or [""])[0],
    }
    g.update(_espn_odds(comp))
    for note_obj in comp.get("notes") or []:
        h = note_obj.get("headline", "")
        if "Game" in h or "Series" in h:
            g["seriesNote"] = h; break
    return g

def fetch_espn_injuries(sport_path: str, sport_key: str) -> list[dict]:
    """Fetch ESPN injury report for a sport (e.g. 'baseball/mlb')."""
    log(f"ESPN injuries {sport_key}…")
    url  = f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/injuries"
    data = fetch_json(url)
    items: list[dict] = []
    for team in (data or {}).get("injuries") or []:
        abbr = (team.get("team") or {}).get("abbreviation", "")
        for inj in team.get("injuries") or []:
            ath = inj.get("athlete") or {}
            items.append({
                "team":   abbr,
                "name":   ath.get("displayName", ""),
                "pos":    (ath.get("position") or {}).get("abbreviation", ""),
                "status": inj.get("status", ""),
                "detail": inj.get("details", {}).get("detail", ""),
                "return": inj.get("details", {}).get("returnDate", ""),
                "sport":  sport_key,
            })
    vlog(f"  {sport_key} injuries: {len(items)}")
    return items

# ═══════════════════════════════════════════════════════════════════════════════
# MLB
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_mlb_scoreboard(date: str = TODAY_MT) -> tuple[list, list]:
    log(f"MLB scoreboard {date}…")
    data = fetch_json(f"{ESPN_BASE}/baseball/mlb/scoreboard?dates={date}&limit=30")
    if not data: return [], []
    games = [_espn_game(e, "MLB") for e in (data.get("events") or [])]
    tom   = (datetime.strptime(date, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
    data2 = fetch_json(f"{ESPN_BASE}/baseball/mlb/scoreboard?dates={tom}&limit=30")
    tomorrow = [_espn_game(e, "MLB") for e in ((data2 or {}).get("events") or [])]
    vlog(f"  MLB: {len(games)} today, {len(tomorrow)} tomorrow")
    return games, tomorrow

def fetch_mlb_standings() -> dict:
    log("MLB standings…")
    data = fetch_json(
        "https://site.web.api.espn.com/apis/v2/sports/baseball/mlb/standings"
        "?region=us&lang=en&season=2026&type=2"
    )
    if not data: return {}
    out: dict = {}
    for division in data.get("children") or []:
        for entry in (division.get("standings") or {}).get("entries") or []:
            team  = entry.get("team") or {}
            abbr  = team.get("abbreviation", "")
            stats = {s["name"]: s.get("displayValue", s.get("value", ""))
                     for s in (entry.get("stats") or [])}
            out[abbr] = {
                "w": stats.get("wins","0"), "l": stats.get("losses","0"),
                "pct": stats.get("winPercent",".000"), "gb": stats.get("gamesBehind","—"),
                "streak": stats.get("streak",""), "rs": stats.get("pointsFor","0"),
                "ra": stats.get("pointsAgainst","0"),
                "div": (division.get("name") or team.get("shortDisplayName","")),
            }
    vlog(f"  MLB standings: {len(out)} teams")
    return out

def fetch_mlb_schedule_week() -> list[dict]:
    """Fetch MLB schedule for next 7 days."""
    log("MLB week schedule…")
    games: list[dict] = []
    for offset in range(7):
        d = (NOW_MT + timedelta(days=offset)).strftime("%Y%m%d")
        data = fetch_json(f"{ESPN_BASE}/baseball/mlb/scoreboard?dates={d}&limit=30")
        for e in (data or {}).get("events") or []:
            g = _espn_game(e, "MLB")
            g["schedDate"] = d
            games.append(g)
    vlog(f"  MLB week: {len(games)} games")
    return games

def fetch_baseball_reference() -> dict:
    """Scrape MLB batting & pitching leaders from Baseball Reference."""
    log("Baseball Reference stats…")
    result: dict = {"batting": [], "pitching": [], "fetchedAt": TODAY_ISO}
    pairs = [
        ("batting",  "https://www.baseball-reference.com/leagues/majors/2026-standard-batting.shtml",   "players_standard_batting"),
        ("pitching", "https://www.baseball-reference.com/leagues/majors/2026-standard-pitching.shtml",  "players_standard_pitching"),
    ]
    for key, url, tbl_id in pairs:
        try:
            time.sleep(2)    # rate-limit SR
            soup = fetch_html(url, timeout=25, ref=True)
            if not soup: continue
            rows = _table_to_rows(soup, tbl_id, limit=50)
            if not rows:   # fallback: first big table
                for tbl in soup.find_all("table"):
                    r = _table_to_rows(soup, tbl.get("id",""), limit=50) if tbl.get("id") else []
                    if len(r) > 10: rows = r; break
            result[key] = rows[:50]
            vlog(f"  Baseball Ref {key}: {len(rows)} rows")
        except Exception as exc:
            log(f"Baseball Ref {key}: {exc}", "WARN")
    return result

def fetch_mlb_nrfi_data(mlb_today: list) -> list[dict]:
    """Build NRFI entries from today's MLB game list + any weather data."""
    return [
        {"game": f"{g['away']} @ {g['home']}", "home": g["home"], "away": g["away"],
         "ou": g.get("ou"), "homeML": g.get("homeML"), "awayML": g.get("awayML"),
         "state": g.get("state","pre"), "venue": g.get("venue","")}
        for g in mlb_today
    ]

# ═══════════════════════════════════════════════════════════════════════════════
# NBA
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_nba_scoreboard(date: str = TODAY_MT) -> tuple[list, list]:
    log(f"NBA scoreboard {date}…")
    data = fetch_json(f"{ESPN_BASE}/basketball/nba/scoreboard?dates={date}&limit=20")
    if not data: return [], []
    games    = [_espn_game(e, "NBA") for e in (data.get("events") or [])]
    tom      = (datetime.strptime(date, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
    data2    = fetch_json(f"{ESPN_BASE}/basketball/nba/scoreboard?dates={tom}&limit=20")
    tomorrow = [_espn_game(e, "NBA") for e in ((data2 or {}).get("events") or [])]
    vlog(f"  NBA: {len(games)} today, {len(tomorrow)} tomorrow")
    return games, tomorrow

def fetch_nba_standings() -> dict:
    log("NBA standings…")
    data = fetch_json(
        "https://site.web.api.espn.com/apis/v2/sports/basketball/nba/standings"
        "?region=us&lang=en&season=2026&type=2"
    )
    if not data: return {}
    out: dict = {}
    for conf in data.get("children") or []:
        for entry in (conf.get("standings") or {}).get("entries") or []:
            team  = entry.get("team") or {}
            abbr  = team.get("abbreviation", "")
            stats = {s["name"]: s.get("displayValue", s.get("value",""))
                     for s in (entry.get("stats") or [])}
            out[abbr] = {
                "w": stats.get("wins","0"), "l": stats.get("losses","0"),
                "pct": stats.get("winPercent",".000"), "gb": stats.get("gamesBehind","—"),
                "rs": stats.get("avgPointsFor","0"), "ra": stats.get("avgPointsAgainst","0"),
            }
    vlog(f"  NBA standings: {len(out)} teams")
    return out

def fetch_nba_playoff_bracket() -> dict:
    """Fetch NBA playoff bracket from ESPN."""
    log("NBA playoff bracket…")
    data = fetch_json(f"{ESPN_BASE}/basketball/nba/playoffs?season=2026")
    if not data: return {}
    return {"raw": data, "fetchedAt": TODAY_ISO}

def fetch_nba_player_stats() -> list[dict]:
    log("NBA player stats…")
    players: dict[str, dict] = {}
    data = fetch_json(
        f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
        f"/leaders?season=2026&seasontype=3&limit=20"
    )
    if not data: return []
    for cat in data.get("categories") or []:
        for leader in cat.get("leaders") or []:
            ath  = leader.get("athlete") or {}
            name = ath.get("displayName", "")
            team = (ath.get("team") or {}).get("abbreviation", "")
            if name not in players:
                players[name] = {"name": name, "team": team}
            players[name][(cat.get("name","")).upper()[:3]] = leader.get("displayValue","—")
    return list(players.values())

def fetch_basketball_reference() -> dict:
    """Scrape NBA playoff stats: per-game, per-100 possessions, advanced, shooting."""
    log("Basketball Reference playoff stats…")
    result: dict = {"perGame": [], "per100": [], "advanced": [], "shooting": [], "opponentPerGame": [], "fetchedAt": TODAY_ISO}
    base = "https://www.basketball-reference.com/playoffs/NBA_2026.html"
    table_map = [
        ("perGame",        "playoffs_per_game"),
        ("per100",         "playoffs_per_poss"),
        ("advanced",       "playoffs_advanced"),
        ("shooting",       "playoffs_shooting"),
        ("opponentPerGame","playoffs_opponent_per_game"),
    ]
    try:
        time.sleep(2)
        soup = fetch_html(base, ref=True)
        if soup:
            for key, tbl_id in table_map:
                rows = _table_to_rows(soup, tbl_id, limit=60)
                result[key] = rows
                vlog(f"  BBRef {key}: {len(rows)} rows")
    except Exception as exc:
        log(f"Basketball Reference: {exc}", "WARN")

    # Series-level stats
    series_urls = [
        ("east_finals", "https://www.basketball-reference.com/playoffs/2026-nba-eastern-conference-finals-cavaliers-vs-knicks.html"),
        ("west_finals", "https://www.basketball-reference.com/playoffs/2026-nba-western-conference-finals-spurs-vs-thunder.html"),
    ]
    result["series"] = {}
    for label, url in series_urls:
        try:
            time.sleep(2)
            soup2 = fetch_html(url, ref=True)
            if soup2:
                series_data: dict = {}
                for key, tbl_id in [("perGame","per_game"),("advanced","advanced")]:
                    rows = _table_to_rows(soup2, tbl_id, limit=20)
                    if rows: series_data[key] = rows
                result["series"][label] = series_data
                vlog(f"  BBRef series {label}: {len(series_data)} tables")
        except Exception as exc:
            log(f"Basketball Reference series {label}: {exc}", "WARN")

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# NHL
# ═══════════════════════════════════════════════════════════════════════════════
def _fetch_nhl_game_odds(event_id: str) -> dict:
    """Fetch NHL game odds from ESPN Core API (returns ML, puck line, O/U)."""
    try:
        url  = (f"http://sports.core.api.espn.com/v2/sports/hockey/leagues/nhl"
                f"/events/{event_id}/competitions/{event_id}/odds")
        data = fetch_json(url, timeout=10)
        items = (data or {}).get("items", [])
        if not items: return {}
        ref = items[0].get("$ref", "")
        if not ref: return {}
        o = fetch_json(ref, timeout=10) or {}
        home = o.get("homeTeamOdds", {})
        away = o.get("awayTeamOdds", {})
        return {
            "homeML":      home.get("moneyLine"),
            "awayML":      away.get("moneyLine"),
            "ou":          o.get("overUnder"),
            "spread":      o.get("spread"),
            "homePL":      home.get("spreadOdds"),   # puck line odds
            "awayPL":      away.get("spreadOdds"),
            "details":     o.get("details", ""),
            "provider":    o.get("provider", {}).get("name", ""),
        }
    except Exception as exc:
        vlog(f"NHL odds {event_id}: {exc}")
        return {}

def _espn_nhl_event_ids(date: str) -> dict[str, str]:
    """Return {home_abbr: event_id} for NHL games on a given date (YYYYMMDD)."""
    try:
        data = fetch_json(
            f"https://sports.core.api.espn.com/v2/sports/hockey/leagues/nhl"
            f"/events?dates={date}&limit=20"
        )
        ids: dict[str, str] = {}
        for item in (data or {}).get("items", []):
            ref = item.get("$ref", "")
            eid = ref.split("/events/")[-1].split("?")[0] if "/events/" in ref else ""
            if eid: ids[eid] = eid   # we'll resolve home team after fetching
        return ids
    except Exception:
        return {}

def fetch_nhl_schedule(date: str = TODAY_ISO) -> tuple[list, list]:
    log(f"NHL schedule {date}…")
    data = fetch_json(f"{NHL_API}/schedule/{date}")
    if not data: return [], []

    def parse_games(day: dict) -> list[dict]:
        out = []
        for g in day.get("games") or []:
            home  = g.get("homeTeam") or {}
            away  = g.get("awayTeam") or {}
            state = g.get("gameState", "FUT")
            out.append({
                "id":         g.get("id"),
                "sport":      "NHL",
                "home":       home.get("abbrev",""),
                "away":       away.get("abbrev",""),
                "homeScore":  home.get("score") if state not in ("FUT","PRE") else None,
                "awayScore":  away.get("score") if state not in ("FUT","PRE") else None,
                "state":      state,
                "period":     g.get("period", 0),
                "clock":      (g.get("clock") or {}).get("timeRemaining",""),
                "venue":      (g.get("venue") or {}).get("default",""),
                "date":       g.get("startTimeUTC",""),
                "network":    ", ".join(b.get("network","") for b in (g.get("tvBroadcasts") or [])),
                "gameType":   g.get("gameType", 2),
                "seriesStatus": (g.get("seriesSummary") or {}).get("seriesStatusShort",""),
            })
        return out

    week = data.get("gameWeek") or []
    today_games    = parse_games(week[0] if week else {})
    tomorrow_games = parse_games(week[1] if len(week) > 1 else {})

    # Enrich today's games with odds from ESPN Core API
    today_str = date.replace("-", "")
    event_ids = _espn_nhl_event_ids(today_str)
    if event_ids and today_games:
        # Map event IDs to games by fetching each event
        for eid in list(event_ids.keys())[:len(today_games)]:
            odds = _fetch_nhl_game_odds(eid)
            if not odds: continue
            # Match by the "details" field which has "HOME -175" style text
            detail = odds.get("details", "")
            fav_abbr = detail.split()[0] if detail else ""
            for g in today_games:
                if g.get("homeML") is not None: continue   # already has odds
                if fav_abbr in (g.get("home",""), g.get("away","")):
                    g.update(odds); break
            else:
                # Fallback: attach to first game without odds
                for g in today_games:
                    if g.get("homeML") is None:
                        g.update(odds); break

    vlog(f"  NHL: {len(today_games)} today, {len(tomorrow_games)} tomorrow")
    return today_games, tomorrow_games

def fetch_nhl_standings() -> dict:
    log("NHL standings…")
    data = fetch_json(f"{NHL_API}/standings/now")
    if not data: return {}
    out: dict = {}
    for t in data.get("standings") or []:
        abbr = (t.get("teamAbbrev") or {}).get("default","")
        out[abbr] = {
            "w": t.get("wins",0), "l": t.get("losses",0), "otl": t.get("otLosses",0),
            "pts": t.get("points",0), "gf": t.get("goalFor",0), "ga": t.get("goalAgainst",0),
            "gd": t.get("goalDifferential",0), "row": t.get("regulationOrOvertimeWins",0),
            "div": t.get("divisionName",""), "conf": t.get("conferenceName",""),
        }
    vlog(f"  NHL standings: {len(out)} teams")
    return out

def fetch_nhl_playoff_bracket() -> dict:
    """Fetch NHL playoff bracket from ESPN."""
    log("NHL playoff bracket…")
    data = fetch_json(f"{ESPN_BASE}/hockey/nhl/playoffs?season=2026")
    if not data: return {}
    return {"raw": data, "fetchedAt": TODAY_ISO}

def _nhl_api_stats(endpoint: str, cayenne: str, limit: int = 50) -> list[dict]:
    url = (f"{NHL_STATS}/{endpoint}?isAggregate=false&isGame=false"
           f"&sort=%5B%7B%22property%22:%22points%22,%22direction%22:%22DESC%22%7D%5D"
           f"&start=0&limit={limit}&cayenneExp={requests.utils.quote(cayenne)}")
    data = fetch_json(url)
    return (data or {}).get("data") or []

def fetch_nhl_edge() -> dict:
    """NHL Edge — team zone-time, shot locations, save %, skaters, goalies — all strengths."""
    log("NHL Edge stats…")
    out: dict = {"teams": {}, "teams5v5": {}, "teams5v4": {}, "teams4v5": {},
                 "goalies": [], "skaters": [], "shotLoc": {}}

    cayenne_base = f"gameTypeId=3 and seasonId>={SEASON} and seasonId<={SEASON}"

    # Team summary — all situations
    for situation, key in [("all","teams"), ("5on5","teams5v5"), ("5on4","teams5v4"), ("4on5","teams4v5")]:
        cay = f"{cayenne_base} and situationCode={situation}" if situation != "all" else cayenne_base
        rows = _nhl_api_stats("team/summary", cay, limit=50)
        for t in rows:
            abbr = t.get("teamAbbrevs","")
            out[key][abbr] = {
                "gf60":   t.get("goalsForPer60",0),
                "ga60":   t.get("goalsAgainstPer60",0),
                "sf60":   t.get("shotsForPer60",0),
                "sa60":   t.get("shotsAgainstPer60",0),
                "ppPct":  t.get("powerPlayPct",0),
                "pkPct":  t.get("penaltyKillPct",0),
                "foPct":  t.get("faceoffWinPct",0),
                "w":      t.get("wins",0),
                "l":      t.get("losses",0),
                "xgf":    t.get("xGoalsFor",0),
                "xga":    t.get("xGoalsAgainst",0),
            }

    # Goalie stats — all situations
    goalie_rows = _nhl_api_stats("goalie/summary", cayenne_base, limit=40)
    for g in goalie_rows:
        out["goalies"].append({
            "name":     g.get("goalieFullName",""),
            "team":     g.get("teamAbbrevs",""),
            "gp":       g.get("gamesPlayed",0),
            "w":        g.get("wins",0),
            "l":        g.get("losses",0),
            "savePct":  g.get("savePct",0),
            "gaa":      g.get("goalsAgainstAverage",0),
            "so":       g.get("shutouts",0),
            "shots":    g.get("shotsAgainst",0),
            "gsaa":     g.get("goalsAboveAverage", g.get("goalsAgainstAverage",0)),
        })

    # Skater stats
    skater_rows = _nhl_api_stats("skater/summary", cayenne_base, limit=50)
    for s in skater_rows:
        out["skaters"].append({
            "name":  s.get("skaterFullName",""),
            "team":  s.get("teamAbbrevs",""),
            "pos":   s.get("positionCode",""),
            "gp":    s.get("gamesPlayed",0),
            "g":     s.get("goals",0),
            "a":     s.get("assists",0),
            "pts":   s.get("points",0),
            "toi":   s.get("timeOnIcePerGame",""),
            "pm":    s.get("plusMinus",0),
        })

    vlog(f"  NHL Edge: {len(out['teams'])} teams, {len(out['goalies'])} goalies, {len(out['skaters'])} skaters")
    return out

def fetch_moneypuck() -> dict:
    """MoneyPuck advanced stats — 5v5, 5v4, 4v5, all — teams and goalies."""
    log("MoneyPuck stats…")
    out: dict = {"teams": {}, "goalies": [], "skaters": []}

    # Teams CSV — current regular season (playoff CSV not published mid-season)
    rows = fetch_csv_rows(f"{MP_BASE_REG}/teams.csv")
    for row in rows:
        situation = row.get("situation","")
        team = row.get("team","")
        if not team: continue
        if team not in out["teams"]: out["teams"][team] = {}
        try:
            out["teams"][team][situation] = {
                "xgfPct":    float(row.get("xGoalsPercentage") or 0),
                "xgf60":     float(row.get("xGoalsForPer60") or row.get("xGoalsFor") or 0),
                "xga60":     float(row.get("xGoalsAgainstPer60") or row.get("xGoalsAgainst") or 0),
                "cfPct":     float(row.get("corsiPercentage") or 0),
                "hdcfPct":   float(row.get("highDangerShotsForPercentage") or row.get("highDangerShotsFor") or 0),
                "gf":        float(row.get("goalsFor") or 0),
                "ga":        float(row.get("goalsAgainst") or 0),
                "shots":     float(row.get("shotsOnGoalFor") or 0),
                "hdgf":      float(row.get("highDangerGoalsFor") or 0),
                "hdga":      float(row.get("highDangerGoalsAgainst") or 0),
                "scgf":      float(row.get("scoreAdjustedShotsAttemptsFor") or 0),
                "scga":      float(row.get("scoreAdjustedShotsAttemptsAgainst") or 0),
            }
        except (ValueError, TypeError):
            pass

    # Goalies CSV
    rows_g = fetch_csv_rows(f"{MP_BASE_REG}/goalies.csv")
    for row in rows_g:
        try:
            out["goalies"].append({
                "name":      row.get("name",""),
                "team":      row.get("team",""),
                "situation": row.get("situation","all"),
                "gp":        int(row.get("games_played") or 0),
                "gsaa":      float(row.get("goalsAboveAverage") or 0),
                "savePct":   float(row.get("savePct") or 0),
                "xSavePct":  float(row.get("xSavePct") or 0),
                "hdSavePct": float(row.get("highDangerSavePct") or 0),
                "mdSavePct": float(row.get("mediumDangerSavePct") or 0),
                "ldSavePct": float(row.get("lowDangerSavePct") or 0),
                "shots":     int(row.get("shotsOnGoalAgainst") or 0),
                "ga":        float(row.get("goalsAgainst") or 0),
                "xga":       float(row.get("xGoalsAgainst") or 0),
            })
        except (ValueError, TypeError):
            pass

    out["goalies"].sort(key=lambda g: g["gsaa"], reverse=True)
    vlog(f"  MoneyPuck: {len(out['teams'])} teams, {len(out['goalies'])} goalies")
    return out

def fetch_hockeyviz() -> dict:
    """Scrape HockeyViz team-level shot rate and zone data."""
    log("HockeyViz stats…")
    result: dict = {"teams": {}, "fetchedAt": TODAY_ISO}
    try:
        soup = fetch_html("https://hockeyviz.com/txt/shotRatesByScore4", timeout=20)
        if soup:
            for tbl in soup.find_all("table")[:3]:
                headers_row = tbl.find("tr")
                col_names = [th.get_text(strip=True) for th in headers_row.find_all(["th","td"])] if headers_row else []
                for tr in tbl.find_all("tr")[1:35]:
                    cells = tr.find_all(["td","th"])
                    if not cells: continue
                    row = {col_names[i] if i < len(col_names) else f"c{i}": cells[i].get_text(strip=True)
                           for i in range(len(cells))}
                    team = row.get("Team","") or row.get("team","") or row.get(col_names[0] if col_names else "","")
                    if team:
                        result["teams"][team] = row
    except Exception as exc:
        log(f"HockeyViz: {exc}", "WARN")

    # Try individual stat endpoints
    for endpoint, label in [
        ("/txt/teamStats4", "teamStats"),
    ]:
        try:
            soup2 = fetch_html(f"https://hockeyviz.com{endpoint}", timeout=20)
            if soup2:
                rows: list[dict] = []
                for tbl in soup2.find_all("table")[:2]:
                    hdrs = [th.get_text(strip=True) for th in (tbl.find("tr") or BeautifulSoup("","lxml")).find_all(["th","td"])]
                    for tr in tbl.find_all("tr")[1:35]:
                        cells = tr.find_all(["td","th"])
                        if not cells: continue
                        rows.append({hdrs[i] if i < len(hdrs) else f"c{i}": cells[i].get_text(strip=True)
                                     for i in range(len(cells))})
                if rows: result[label] = rows
        except Exception as exc:
            log(f"HockeyViz {label}: {exc}", "WARN")

    vlog(f"  HockeyViz: {len(result['teams'])} teams")
    return result

def fetch_hockey_reference() -> dict:
    """Scrape Hockey Reference conference finals series stats."""
    log("Hockey Reference series stats…")
    result: dict = {"series": {}, "fetchedAt": TODAY_ISO}
    series_urls = {
        "east_finals": "https://www.hockey-reference.com/playoffs/2026-carolina-hurricanes-vs-montreal-canadiens-eastern-conference-finals.html",
        "west_finals": "https://www.hockey-reference.com/playoffs/2026-colorado-avalanche-vs-vegas-golden-knights-western-conference-finals.html",
    }
    for label, url in series_urls.items():
        try:
            time.sleep(2)
            soup = fetch_html(url, ref=True)
            if not soup: continue
            tables_data: dict = {}
            for tbl in soup.find_all("table")[:6]:
                tbl_id = tbl.get("id","")
                rows = _table_to_rows(soup, tbl_id, limit=30) if tbl_id else []
                if rows: tables_data[tbl_id or f"tbl{len(tables_data)}"] = rows
            result["series"][label] = tables_data
            vlog(f"  Hockey Ref {label}: {len(tables_data)} tables")
        except Exception as exc:
            log(f"Hockey Reference {label}: {exc}", "WARN")
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# Tennis
# ═══════════════════════════════════════════════════════════════════════════════
def _parse_tennis_abstract_table(soup: BeautifulSoup, limit: int = 100) -> list[dict]:
    tables = soup.find_all("table")
    table  = next((t for t in tables if t.find("tbody") and len(t.find("tbody").find_all("tr")) > 50), None)
    if not table: return []
    tbody = table.find("tbody")
    players = []
    for i, row in enumerate(tbody.find_all("tr")[:limit]):
        cells = row.find_all("td")
        if len(cells) < 4: continue
        def cell(n): return cells[n].get_text(strip=True).replace("\xa0"," ") if len(cells)>n else ""
        def icell(n):
            try: return int(float(cell(n).replace(",","").replace(" ",""))) if cell(n) else 0
            except: return 0
        players.append({
            "rank": icell(0) or i+1, "name": cell(1), "age": cell(2),
            "elo": icell(3), "eloHard": icell(6), "eloClay": icell(8), "eloGrass": icell(10),
        })
    return players

def fetch_tennis_elo(tour: str = "atp") -> list[dict]:
    log(f"TennisAbstract {tour.upper()} ELO…")
    soup = fetch_html(f"https://tennisabstract.com/reports/{tour}_elo_ratings.html")
    if not soup: return []
    players = _parse_tennis_abstract_table(soup, 100)
    vlog(f"  {tour.upper()} ELO: {len(players)} players")
    return players

def fetch_tennis_yelo(tour: str = "atp") -> list[dict]:
    log(f"TennisAbstract {tour.upper()} yElo…")
    url  = f"https://tennisabstract.com/reports/{tour}_season_yelo_ratings.html"
    soup = fetch_html(url)
    if not soup: return []
    tables = soup.find_all("table")
    table  = next((t for t in tables if t.find("tbody") and len(t.find("tbody").find_all("tr")) > 50), None)
    if not table: return []
    players = []
    for i, row in enumerate(table.find("tbody").find_all("tr")[:100]):
        cells = row.find_all("td")
        if len(cells) < 3: continue
        def cell(n): return cells[n].get_text(strip=True).replace("\xa0"," ") if len(cells)>n else ""
        def icell(n):
            try: return int(float(cell(n).replace(",","").replace(" ",""))) if cell(n) else 0
            except: return 0
        players.append({
            "rank": icell(0) or i+1, "name": cell(1),
            "yElo": icell(2), "yEloClay": icell(3), "yEloHard": icell(4),
        })
    vlog(f"  {tour.upper()} yElo: {len(players)} players")
    return players

def fetch_tennis_schedule() -> list[dict]:
    """Fetch today's ATP + WTA matches from ESPN scoreboard API."""
    matches: list[dict] = []
    for tour in ("atp","wta"):
        try:
            data = fetch_json(
                f"https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}"
                f"/scoreboard?dates={TODAY_MT}"
            )
            for ev in (data or {}).get("events") or []:
                comp    = (ev.get("competitions") or [{}])[0]
                players = comp.get("competitors") or []
                p1  = (players[0].get("athlete") or {}).get("displayName","TBD") if players else "TBD"
                p2  = (players[1].get("athlete") or {}).get("displayName","TBD") if len(players)>1 else "TBD"
                st  = comp.get("status",{})
                state = st.get("type",{}).get("state","pre")
                matches.append({
                    "tour":       tour.upper(),
                    "player1":    p1, "player2": p2,
                    "state":      state,
                    "score1":     players[0].get("score","") if players else "",
                    "score2":     players[1].get("score","") if len(players)>1 else "",
                    "statusText": st.get("type",{}).get("shortDetail",""),
                    "tournament": (comp.get("venue") or {}).get("fullName",""),
                    "date":       ev.get("date",""),
                    "network":    ((comp.get("broadcasts") or [{}])[0].get("names") or [""])[0],
                })
        except Exception as exc:
            log(f"Tennis schedule {tour}: {exc}", "WARN")
    log(f"Tennis schedule: {len(matches)} matches")
    return matches

def fetch_tennis_rankings_espn() -> dict:
    """Fetch ATP + WTA top-100 rankings from ESPN."""
    log("ESPN tennis rankings…")
    result: dict = {"atp": [], "wta": []}
    for tour, path in [("atp","tennis/rankings"),("wta","tennis/rankings/_/type/wta")]:
        try:
            soup = fetch_html(f"https://www.espn.com/{path}")
            if not soup: continue
            for row in soup.select("tr.Table__TR"):
                cells = row.find_all("td")
                if len(cells) >= 3:
                    result[tour].append({
                        "rank":   cells[0].get_text(strip=True),
                        "name":   cells[1].get_text(strip=True),
                        "points": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                    })
        except Exception as exc:
            log(f"ESPN tennis rankings {tour}: {exc}", "WARN")
    vlog(f"  ATP rankings: {len(result['atp'])} | WTA: {len(result['wta'])}")
    return result

def fetch_tennis_schedule_full() -> dict:
    """Fetch full ATP + WTA tournament schedule from ESPN."""
    log("Tennis full schedule…")
    result: dict = {"atp": [], "wta": []}
    for tour, path in [("atp","tennis/schedule"),("wta","tennis/schedule/_/type/wta")]:
        try:
            soup = fetch_html(f"https://www.espn.com/{path}")
            if not soup: continue
            for row in soup.select("tr.Table__TR"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    result[tour].append({
                        "tournament": cells[0].get_text(strip=True),
                        "surface":    cells[1].get_text(strip=True) if len(cells) > 1 else "",
                        "dates":      cells[2].get_text(strip=True) if len(cells) > 2 else "",
                    })
        except Exception as exc:
            log(f"Tennis full schedule {tour}: {exc}", "WARN")
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# F1
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_f1() -> dict:
    result: dict = {"schedule":[], "driverStandings":[], "constructorStandings":[], "nextRace":None}
    year = NOW_MT.year

    # Ergast schedule
    try:
        data  = fetch_json(f"http://ergast.com/api/f1/{year}.json?limit=25")
        races = (data.get("MRData",{}).get("RaceTable",{}).get("Races") or [])
        for race in races:
            rd = race.get("date","")
            entry = {
                "round":   int(race.get("round",0)),
                "name":    race.get("raceName",""),
                "circuit": race.get("Circuit",{}).get("circuitName",""),
                "country": race.get("Circuit",{}).get("Location",{}).get("country",""),
                "date":    rd, "time": race.get("time",""),
                "past":    rd < TODAY_ISO,
            }
            result["schedule"].append(entry)
            if rd >= TODAY_ISO and result["nextRace"] is None:
                result["nextRace"] = entry
    except Exception as exc: log(f"F1 schedule: {exc}", "WARN")

    # Driver standings
    try:
        data = fetch_json(f"http://ergast.com/api/f1/{year}/driverStandings.json")
        for s in (data.get("MRData",{}).get("StandingsTable",{})
                      .get("StandingsLists",[{}])[0].get("DriverStandings") or [])[:20]:
            drv  = s.get("Driver",{})
            ctor = (s.get("Constructors") or [{}])[0]
            result["driverStandings"].append({
                "pos":  int(s.get("position",99)),
                "name": f"{drv.get('givenName','')} {drv.get('familyName','')}".strip(),
                "code": drv.get("code",""), "team": ctor.get("name",""),
                "pts":  float(s.get("points",0)), "wins": int(s.get("wins",0)),
            })
    except Exception as exc: log(f"F1 driver standings: {exc}", "WARN")

    # Constructor standings
    try:
        data = fetch_json(f"http://ergast.com/api/f1/{year}/constructorStandings.json")
        for s in (data.get("MRData",{}).get("StandingsTable",{})
                      .get("StandingsLists",[{}])[0].get("ConstructorStandings") or [])[:10]:
            ctor = s.get("Constructor",{})
            result["constructorStandings"].append({
                "pos":  int(s.get("position",99)),
                "name": ctor.get("name",""),
                "pts":  float(s.get("points",0)), "wins": int(s.get("wins",0)),
            })
    except Exception as exc: log(f"F1 constructor standings: {exc}", "WARN")

    log(f"F1: {len(result['schedule'])} races | next: {result['nextRace'] and result['nextRace']['name']}")
    return result

def fetch_f1_analytics() -> dict:
    """Fetch F1 race analysis from f1datastop.com."""
    url    = "https://f1datastop.com/race-analysis"
    result = {"source":"f1datastop.com", "fetchedAt":TODAY_ISO, "data":[], "error":None}
    try:
        r = _ref_session.get(url, timeout=20)
        if r.ok:
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all(["article","section","div"],
                                  class_=lambda c: c and any(k in c for k in ["race","analysis","driver","lap","pace"]))
            for card in cards[:20]:
                txt = card.get_text(separator=" ", strip=True)
                if len(txt) > 30: result["data"].append({"text": txt[:300], "tag": card.name})
            for tbl in soup.find_all("table")[:5]:
                for row in tbl.find_all("tr")[:15]:
                    cells = [td.get_text(strip=True) for td in row.find_all(["td","th"])]
                    if cells: result["data"].append({"row": cells})
        else:
            result["error"] = f"HTTP {r.status_code}"
    except Exception as exc:
        result["error"] = str(exc)
        log(f"F1 analytics: {exc}", "WARN")
    return result

def fetch_f1_tracing_insights() -> dict:
    """Fetch race data index from TracingInsights/2026 GitHub repo."""
    log("F1 TracingInsights GitHub…")
    result: dict = {"source":"TracingInsights/2026", "races":[], "fetchedAt":TODAY_ISO}
    try:
        api   = "https://api.github.com/repos/TracingInsights/2026/contents"
        hdrs  = {"Accept": "application/vnd.github.v3+json", "User-Agent": "clairvoyance-engine"}
        r     = requests.get(api, headers=hdrs, timeout=15)
        if r.ok:
            contents = r.json()
            for item in contents:
                if item.get("type") == "dir":
                    race_r = requests.get(item["url"], headers=hdrs, timeout=10)
                    files  = [f["name"] for f in (race_r.json() if race_r.ok else [])
                              if f.get("type") == "file"]
                    result["races"].append({"race": item["name"], "files": files})
        else:
            result["error"] = f"HTTP {r.status_code}"
    except Exception as exc:
        log(f"TracingInsights: {exc}", "WARN")
        result["error"] = str(exc)
    log(f"F1 TracingInsights: {len(result['races'])} race dirs found")
    return result

def fetch_f1_calendar_datastop() -> list[dict]:
    """Fetch F1 calendar from f1datastop.com."""
    log("F1 datastop calendar…")
    items: list[dict] = []
    try:
        soup = fetch_html("https://f1datastop.com/calendar", timeout=15)
        if soup:
            for row in soup.select("tr"):
                cells = row.find_all(["td","th"])
                if len(cells) >= 2:
                    items.append({
                        "event": cells[0].get_text(strip=True),
                        "date":  cells[1].get_text(strip=True) if len(cells)>1 else "",
                        "venue": cells[2].get_text(strip=True) if len(cells)>2 else "",
                    })
    except Exception as exc: log(f"F1 calendar datastop: {exc}", "WARN")
    return items[:25]

# ═══════════════════════════════════════════════════════════════════════════════
# Weather
# ═══════════════════════════════════════════════════════════════════════════════
_MLB_COORDS: dict[str, tuple[float, float, str]] = {
    "NYY":(40.8296,-73.9262,"Bronx NY"), "NYM":(40.7571,-73.8458,"Queens NY"),
    "BOS":(42.3467,-71.0972,"Boston MA"), "CHC":(41.9484,-87.6553,"Chicago IL"),
    "CHW":(41.8300,-87.6338,"Chicago IL"), "CLE":(41.4962,-81.6852,"Cleveland OH"),
    "DET":(42.3390,-83.0485,"Detroit MI"), "KC":(39.0517,-94.4803,"Kansas City MO"),
    "LAA":(33.8003,-117.8827,"Anaheim CA"), "LAD":(34.0739,-118.2400,"Los Angeles CA"),
    "PHI":(39.9061,-75.1665,"Philadelphia PA"), "PIT":(40.4469,-80.0057,"Pittsburgh PA"),
    "CIN":(39.0975,-84.5066,"Cincinnati OH"), "STL":(38.6226,-90.1928,"St. Louis MO"),
    "WSH":(38.8730,-77.0074,"Washington DC"), "BAL":(39.2838,-76.6218,"Baltimore MD"),
    "SF":(37.7786,-122.3893,"San Francisco CA"), "SD":(32.7076,-117.1570,"San Diego CA"),
    "COL":(39.7559,-104.9942,"Denver CO"), "OAK":(37.7516,-122.2005,"Oakland CA"),
    "ATH":(37.7516,-122.2005,"Oakland CA"),
}
_INDOOR = {"MIN","TOR","TB","MIA","TEX","HOU","ARI","ATL","MIL","SEA"}
_WMO = {0:"Clear",1:"Mainly Clear",2:"Partly Cloudy",3:"Overcast",
         45:"Fog",51:"Drizzle",61:"Rain",71:"Snow",80:"Showers",95:"Thunderstorm"}

def _wmo_desc(code: int) -> str:
    for k in sorted(_WMO, reverse=True):
        if code >= k: return _WMO[k]
    return "Unknown"

def fetch_weather(home_team: str) -> dict | None:
    if home_team in _INDOOR:
        return {"condition":"Dome/Retractable","temp":None,"wind":None,"indoor":True}
    coords = _MLB_COORDS.get(home_team)
    if not coords: return None
    lat, lon, city = coords
    data = fetch_json(
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,wind_speed_10m,wind_direction_10m,weather_code"
        f"&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto",
        timeout=10
    )
    if not data: return None
    c = data.get("current") or {}
    return {
        "condition": _wmo_desc(int(c.get("weather_code",0))),
        "temp":      round(float(c.get("temperature_2m",0))),
        "wind":      round(float(c.get("wind_speed_10m",0))),
        "windDir":   round(float(c.get("wind_direction_10m",0))),
        "city":      city, "indoor": False,
    }

# ═══════════════════════════════════════════════════════════════════════════════
# Linemate props / trends / cheatsheets  (Playwright)
# ═══════════════════════════════════════════════════════════════════════════════
def _linemate_playwright(url: str, selectors: list[str], limit: int = 100) -> list[str]:
    """Generic Playwright scraper — returns list of raw inner_text strings."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("Playwright not installed — skipping", "WARN"); return []
    items: list[str] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx     = browser.new_context(user_agent=HEADERS["User-Agent"],
                                          viewport={"width":1280,"height":900})
            page    = ctx.new_page()
            page.goto(url, wait_until="networkidle", timeout=45_000)
            page.wait_for_timeout(4_000)
            for sel in selectors:
                rows = page.query_selector_all(sel)
                if len(rows) > 3:
                    for row in rows[:limit]:
                        txt = row.inner_text().strip()
                        if len(txt) > 8: items.append(txt)
                    break
            browser.close()
    except Exception as exc:
        log(f"Playwright {url}: {exc}", "WARN")
    return items

def fetch_linemate_props(sport: str) -> list[dict]:
    log(f"Linemate props {sport.upper()}…")
    raw = _linemate_playwright(
        f"https://linemate.io/{sport}",
        ["[class*='PlayerPropCard']","[class*='PropCard']","[class*='prop-card']","[data-testid*='prop']","article"],
    )
    props = [{"raw":t, "sport":sport.upper(), "src":"Linemate"} for t in raw]
    log(f"  Linemate {sport.upper()}: {len(props)} cards")
    return props

def fetch_linemate_trends(sport: str) -> list[dict]:
    log(f"Linemate trends {sport.upper()}…")
    raw = _linemate_playwright(
        f"https://linemate.io/{sport}/trends",
        ["[class*='TrendRow']","[class*='trend-row']","[class*='PlayerRow']","table tr","article"],
    )
    trends: list[dict] = []
    for txt in raw:
        parts     = [p.strip() for p in txt.split("\n") if p.strip()]
        txt_lower = txt.lower()
        direction = ("hot" if any(k in txt_lower for k in ["hot","fire","streak"]) else
                     "cold" if any(k in txt_lower for k in ["cold","slump"]) else
                     "up"   if any(k in txt_lower for k in ["up","↑","over"]) else
                     "down" if any(k in txt_lower for k in ["down","↓","under"]) else "neutral")
        nums = re.findall(r'(\d+)/(\d+)', txt)
        trends.append({
            "player":    parts[0] if parts else txt[:40],
            "category":  parts[1] if len(parts)>1 else "",
            "direction": direction,
            "l5":        f"{nums[0][0]}/{nums[0][1]}" if nums else "",
            "l10":       f"{nums[1][0]}/{nums[1][1]}" if len(nums)>1 else "",
            "lineMove":  "up" if "line up" in txt_lower else ("down" if "line down" in txt_lower else ""),
            "raw":       txt[:200], "sport": sport.upper(), "src": "Linemate/trends",
        })
    log(f"  Linemate trends {sport.upper()}: {len(trends)} entries")
    return trends

def fetch_linemate_cheatsheet(sport: str) -> list[dict]:
    log(f"Linemate cheatsheet {sport.upper()}…")
    raw = _linemate_playwright(
        f"https://linemate.io/{sport}/cheatsheets/recent-form",
        ["[class*='Row']","[class*='row']","table tr","li","article"],
    )
    return [{"raw":t, "sport":sport.upper(), "src":"Linemate/form"} for t in raw]

# ═══════════════════════════════════════════════════════════════════════════════
# Sports news + injuries
# ═══════════════════════════════════════════════════════════════════════════════
_INJURY_KEYWORDS = [
    "injured","out","doubtful","questionable","day-to-day","IR","scratch",
    "suspended","illness","flu","knee","ankle","shoulder","back","concussion",
    "unavailable","game-time","sidelined","hamstring","wrist","hand","elbow",
]

def fetch_sports_news() -> dict:
    news: dict = {}
    sport_map = {
        "mlb":    "baseball/mlb",
        "nhl":    "hockey/nhl",
        "nba":    "basketball/nba",
        "tennis": "tennis/atp",
    }
    for sport_key, espn_path in sport_map.items():
        try:
            url      = f"https://site.api.espn.com/apis/site/v2/sports/{espn_path}/news"
            articles = (fetch_json(url) or {}).get("articles",[])
            items    = []
            for a in articles[:30]:
                title = a.get("headline","")
                desc  = a.get("description","")
                combined = (title + " " + desc).lower()
                if any(kw in combined for kw in _INJURY_KEYWORDS):
                    items.append({
                        "headline":  title,
                        "summary":   desc[:200],
                        "published": a.get("published",""),
                        "link":      a.get("links",{}).get("web",{}).get("href",""),
                    })
            news[sport_key] = items[:10]
        except Exception as exc:
            log(f"News {sport_key}: {exc}", "WARN"); news[sport_key] = []
    return news

def fetch_injuries_all() -> dict:
    """Dedicated injury fetcher for all sports."""
    log("ESPN injury reports…")
    return {
        "mlb":  fetch_espn_injuries("baseball/mlb",    "mlb"),
        "nba":  fetch_espn_injuries("basketball/nba",  "nba"),
        "nhl":  fetch_espn_injuries("hockey/nhl",      "nhl"),
    }

# ═══════════════════════════════════════════════════════════════════════════════
# Best Bets Calculator  (EV + Confidence scoring)
# ═══════════════════════════════════════════════════════════════════════════════
def _ml_to_prob(ml) -> float | None:
    try:
        ml = int(ml)
        return abs(ml)/(abs(ml)+100) if ml < 0 else 100/(ml+100)
    except: return None

def _ml_to_dec(ml) -> float:
    try:
        ml = int(ml)
        return (100/abs(ml)+1) if ml < 0 else (ml/100+1)
    except: return 1.91

def _ev(prob: float, dec: float) -> float:
    return prob * dec - 1

def _ev_grade(ev_pct: float) -> str:
    if ev_pct >= 12: return "A+"
    if ev_pct >= 8:  return "A"
    if ev_pct >= 4:  return "B"
    if ev_pct >= 1:  return "C"
    return "D"

def _confidence(prob: float, ev_pct: float, extra_signals: int = 0) -> int:
    """Return 0–100 confidence score."""
    base = int(prob * 70)             # max 70 from implied prob
    ev_bonus = min(20, int(ev_pct))   # max 20 from EV
    signal_bonus = min(10, extra_signals * 3)
    return min(100, base + ev_bonus + signal_bonus)

def calculate_best_bets(
    nba_today: list, mlb_today: list, nhl_today: list,
    weather: dict, mp: dict | None = None, nhl_edge: dict | None = None,
) -> list[dict]:
    log("Calculating best bets…")
    picks: list[dict] = []

    def add(sport, game_str, pick_str, prob, ml, grade, note="", extra_signals=0):
        dec     = _ml_to_dec(ml)
        ev_pct  = round(_ev(prob, dec) * 100, 1)
        conf    = _confidence(prob, ev_pct, extra_signals)
        ev_letter = _ev_grade(ev_pct)
        picks.append({
            "sport":      sport,
            "game":       game_str,
            "pick":       pick_str,
            "prob":       round(prob * 100, 1),
            "ev":         ev_pct,
            "evGrade":    ev_letter,
            "confidence": conf,
            "ml":         f"+{ml}" if isinstance(ml,int) and ml>0 else str(ml),
            "grade":      grade,
            "note":       note,
            "date":       TODAY_ISO,
        })

    # NBA moneylines
    for g in nba_today:
        if g.get("state") != "pre": continue
        hml, aml  = g.get("homeML"), g.get("awayML")
        hprob, aprob = _ml_to_prob(hml), _ml_to_prob(aml)
        home, away = g.get("home",""), g.get("away","")
        game_str   = f"{away} @ {home}"
        if hprob and hprob > 0.62:
            add("NBA", game_str, f"{home} ML {hml}", hprob, hml,
                "LOCK" if hprob>0.67 else "GOOD", note=g.get("seriesNote",""))
        elif aprob and aprob > 0.62:
            add("NBA", game_str, f"{away} ML {aml}", aprob, aml,
                "LOCK" if aprob>0.67 else "GOOD", note=g.get("seriesNote",""))
        # O/U info
        ou = g.get("ou")
        if ou and hml and aml:
            picks.append({
                "sport":"NBA","game":game_str,"pick":f"O/U {ou}","prob":52.0,
                "ev":0.0,"evGrade":"D","confidence":52,"ml":"-110","grade":"INFO",
                "note":f"Line: {home} {hml} / {away} {aml}","date":TODAY_ISO,
            })

    # MLB — wind-adjusted O/U + ML favorites
    for g in mlb_today:
        if g.get("state") != "pre": continue
        home, away = g.get("home",""), g.get("away","")
        game_str   = f"{away} @ {home}"
        w          = weather.get(home,{})
        hml, aml   = g.get("homeML"), g.get("awayML")
        ou         = g.get("ou")
        if w and not w.get("indoor"):
            wind     = w.get("wind",0) or 0
            wind_dir = w.get("windDir",0) or 0
            blowing_out = 45 <= wind_dir <= 135
            if wind >= 12 and ou:
                pick_dir = "OVER" if blowing_out else "UNDER"
                prob     = 0.58 if wind >= 18 else 0.54
                add("MLB", game_str,
                    f"{pick_dir} {ou} (wind {wind}mph {'out' if blowing_out else 'in'})",
                    prob, -110, "GOOD" if prob > 0.56 else "INFO",
                    note=f"{w.get('condition')}, {w.get('temp')}°F", extra_signals=1)
        hprob, aprob = _ml_to_prob(hml), _ml_to_prob(aml)
        if hprob and hprob > 0.65:
            add("MLB", game_str, f"{home} ML {hml}", hprob, hml,
                "LOCK" if hprob>0.70 else "GOOD")
        elif aprob and aprob > 0.65:
            add("MLB", game_str, f"{away} ML {aml}", aprob, aml,
                "LOCK" if aprob>0.70 else "GOOD")

    # NHL — moneyline + puck line + O/U (pre-game and live)
    mp_teams = (mp or {}).get("teams",{}) if mp else {}
    nhl_edge_teams = (nhl_edge or {}).get("teams",{}) if nhl_edge else {}
    for g in nhl_today:
        if g.get("state") not in ("FUT","PRE","LIVE","CRIT"): continue
        hml, aml    = g.get("homeML"), g.get("awayML")
        home, away  = g.get("home",""), g.get("away","")
        game_str    = f"{away} @ {home}"
        series_note = g.get("seriesStatus","") or g.get("details","")
        is_live     = g.get("state") in ("LIVE","CRIT")
        live_tag    = " [LIVE]" if is_live else ""

        # MoneyPuck 5v5 xGF% → model win probability (home-adjusted)
        home_xgf_raw = float((mp_teams.get(home,{}).get("5on5") or {}).get("xgfPct") or 0.50)
        away_xgf_raw = float((mp_teams.get(away,{}).get("5on5") or {}).get("xgfPct") or 0.50)
        # Normalize so they sum to 1, then apply small home-ice bump (+3%)
        total_xgf   = home_xgf_raw + away_xgf_raw if (home_xgf_raw + away_xgf_raw) > 0 else 1
        model_home  = min(0.80, max(0.20, home_xgf_raw / total_xgf + 0.03))
        model_away  = 1.0 - model_home
        xgf_edge    = 1 if abs(home_xgf_raw - away_xgf_raw) > 0.04 else 0
        xgf_note    = (f"xGF%: {home} {home_xgf_raw*100:.1f} / {away} {away_xgf_raw*100:.1f}"
                       f"  model: {model_home*100:.1f}% / {model_away*100:.1f}%")

        # Market-implied probs
        hprob, aprob = _ml_to_prob(hml), _ml_to_prob(aml)

        # ── Moneyline — pick side with highest positive EV ───────────────
        h_ev = _ev(model_home, _ml_to_dec(hml)) * 100 if hml else -99
        a_ev = _ev(model_away, _ml_to_dec(aml)) * 100 if aml else -99
        if h_ev > a_ev and h_ev > 1.0:
            grade = "LOCK" if h_ev > 8 else "GOOD" if h_ev > 4 else "INFO"
            add("NHL", game_str, f"{home} ML {hml}{live_tag}",
                model_home, hml, grade,
                note=f"{series_note}  {xgf_note}".strip(), extra_signals=xgf_edge)
        elif a_ev > 1.0:
            grade = "LOCK" if a_ev > 8 else "GOOD" if a_ev > 4 else "INFO"
            add("NHL", game_str, f"{away} ML {aml}{live_tag}",
                model_away, aml, grade,
                note=f"{series_note}  {xgf_note}".strip(), extra_signals=xgf_edge)

        # ── Puck Line ────────────────────────────────────────────────────
        hpl_odds = g.get("homePL")   # e.g. +142 for COL -1.5
        apl_odds = g.get("awayPL")   # e.g. -170 for VGK +1.5
        spread   = g.get("spread")   # e.g. -1.5 (home favored)
        if spread is not None and hprob:
            # Underdog puck line (+1.5) is worth flagging when favourite is heavy
            if apl_odds and _ml_to_prob(-abs(int(apl_odds or 110))) and hprob > 0.60:
                apl_prob = _ml_to_prob(-abs(int(apl_odds)))
                add("NHL", game_str, f"{away} +1.5 ({apl_odds}){live_tag}",
                    apl_prob or 0.55, int(apl_odds or -170), "GOOD",
                    note=f"Puck line · {series_note}".strip(), extra_signals=xgf_edge)
            # Favourite -1.5 only if very strong
            if hpl_odds and hprob > 0.68:
                add("NHL", game_str, f"{home} -1.5 ({hpl_odds}){live_tag}",
                    0.45, int(hpl_odds or 140), "INFO",
                    note=f"Puck line · {series_note}".strip())

        # ── Over / Under ─────────────────────────────────────────────────
        ou = g.get("ou")
        if ou:
            # Pull goalie save% from MoneyPuck to tilt O/U
            mp_goalies = (mp or {}).get("goalies",[])
            def best_goalie_sv(team):
                gl = [g2 for g2 in mp_goalies if g2.get("team") == team]
                return max((g2.get("savePct",0) for g2 in gl), default=0)
            h_sv = best_goalie_sv(home)
            a_sv = best_goalie_sv(away)
            avg_sv = (h_sv + a_sv) / 2 if (h_sv and a_sv) else 0
            # High combined save% → lean UNDER
            if avg_sv > 0.915:
                add("NHL", game_str, f"UNDER {ou}{live_tag}", 0.56, -115, "GOOD",
                    note=f"Goalie SV%: {home} {h_sv:.3f} / {away} {a_sv:.3f}")
            elif avg_sv < 0.900 and avg_sv > 0:
                add("NHL", game_str, f"OVER {ou}{live_tag}", 0.54, -115, "INFO",
                    note=f"Goalie SV%: {home} {h_sv:.3f} / {away} {a_sv:.3f}")
            else:
                picks.append({
                    "sport":"NHL","game":game_str,"pick":f"O/U {ou}{live_tag}",
                    "prob":52.0,"ev":0.0,"evGrade":"D","confidence":52,
                    "ml":"-110","grade":"INFO",
                    "note":f"Line: {home} {hml} / {away} {aml}","date":TODAY_ISO,
                })

    grade_order = {"LOCK":0,"GOOD":1,"INFO":2}
    picks.sort(key=lambda p: (grade_order.get(p["grade"],9), -p.get("confidence",0)))
    top = picks[:15]
    (DATA / "best_bets.json").write_text(json.dumps(top, indent=2))
    log(f"Best bets: {len(top)} picks | top EV grade: {top[0]['evGrade'] if top else '—'}")
    return top

# ═══════════════════════════════════════════════════════════════════════════════
# Auto-settle (enhanced — checks ML, RL, OU, Spread, Puck Line, Run Line)
# ═══════════════════════════════════════════════════════════════════════════════
def auto_settle(nba_final: list, mlb_final: list, nhl_final: list) -> list[dict]:
    locked_path  = DATA / "locked_props.json"
    settled_path = DATA / "settled.json"
    if not locked_path.exists():
        vlog("No locked_props.json — skipping server-side auto-settle"); return []

    locked:   list[dict] = json.loads(locked_path.read_text())
    existing: list[dict] = json.loads(settled_path.read_text()) if settled_path.exists() else []
    settled_ids = {s.get("id","") for s in existing}
    new_settled  = list(existing)

    def game_index(games: list) -> dict:
        idx = {}
        for g in games:
            h, a  = g.get("home",""), g.get("away","")
            state = str(g.get("state",""))
            if state in ("post","FINAL","OFF","7","F","OT","SO") and h and a:
                idx[(h,a)] = g; idx[(a,h)] = g
        return idx

    all_idx: dict = {}
    all_idx.update(game_index(nba_final))
    all_idx.update(game_index(mlb_final))
    all_idx.update(game_index(nhl_final))

    for bet in locked:
        if bet.get("outcome","pending") != "pending": continue
        bet_id = bet.get("id","")
        if bet_id in settled_ids: continue
        hA, awA = bet.get("hA","") or bet.get("home",""), bet.get("awA","") or bet.get("away","")
        game = all_idx.get((hA, awA))
        if not game: continue
        hs, as_ = int(game.get("homeScore") or 0), int(game.get("awayScore") or 0)
        bet_type = str(bet.get("betType","ML")).upper()
        outcome  = None

        if bet_type == "ML":
            winner  = game.get("home") if hs > as_ else game.get("away")
            outcome = "win" if bet.get("team","") == winner else "loss"

        elif bet_type in ("RL","PL","RUNLINE","PUCKLINE","SPREAD"):
            line    = float(str(bet.get("line","1.5")).replace("+","").replace("−","-") or 1.5)
            is_home = bet.get("team","") == game.get("home","")
            diff    = (hs - as_) if is_home else (as_ - hs)
            outcome = "win" if diff+line > 0 else ("push" if diff+line == 0 else "loss")

        elif bet_type in ("OU","OVER_UNDER","TOTAL"):
            total   = hs + as_
            lv      = float(bet.get("ou") or bet.get("line") or 0)
            over    = "OVER" in str(bet.get("betOn","")).upper() or bet.get("over", True)
            outcome = ("win" if total > lv else ("push" if total == lv else "loss")) if over else \
                      ("win" if total < lv else ("push" if total == lv else "loss"))

        elif bet_type == "PROP":
            continue   # props need player stat data — skip server-side settle

        if outcome:
            sb = {**bet, "outcome": outcome, "settledAt": NOW.isoformat(),
                  "hScore": hs, "aScore": as_}
            new_settled.append(sb)
            settled_ids.add(bet_id)
            log(f"  SETTLED: {bet.get('betOn',bet.get('pick',''))} → {outcome.upper()}")

    settled_path.write_text(json.dumps(new_settled, indent=2))
    log(f"Auto-settle: {len(new_settled)} total settled")
    return new_settled

# ═══════════════════════════════════════════════════════════════════════════════
# Bet History (persistent log + CSV export)
# ═══════════════════════════════════════════════════════════════════════════════
def load_bet_history() -> list[dict]:
    if BET_HISTORY_JSON.exists():
        return json.loads(BET_HISTORY_JSON.read_text())
    return []

def merge_settled_to_history(settled: list[dict]) -> list[dict]:
    history     = load_bet_history()
    existing_ids = {b.get("id","") for b in history}
    new_bets    = [b for b in settled if b.get("id","") and b.get("id","") not in existing_ids]
    history.extend(new_bets)
    BET_HISTORY_JSON.write_text(json.dumps(history, indent=2))
    if new_bets: note(f"Bet history: +{len(new_bets)} new records ({len(history)} total)")
    return history

def export_bet_history_csv(history: list[dict]) -> None:
    if not history: return
    fields = [
        "id","sport","game","betOn","betType","pick","line","ou","prob",
        "ev","evGrade","confidence","ml","grade","outcome","settledAt",
        "hScore","aScore","note","date",
    ]
    with open(BET_HISTORY_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(history)
    docs_csv = ROOT / "docs" / "bet_history.csv"
    shutil.copy(BET_HISTORY_CSV, docs_csv)
    note(f"Bet history CSV: {len(history)} rows → docs/bet_history.csv")

def build_overall_stats(history: list[dict]) -> dict:
    """Aggregate win/loss/push from bet history for Overall tab."""
    from collections import defaultdict
    total: dict = {"w":0,"l":0,"push":0,"total":0}
    by_sport: dict = defaultdict(lambda: {"w":0,"l":0,"push":0,"total":0})
    by_type:  dict = defaultdict(lambda: {"w":0,"l":0,"push":0,"total":0})
    by_date:  dict = defaultdict(lambda: {"w":0,"l":0,"push":0,"total":0})

    for b in history:
        o = b.get("outcome","pending")
        if o not in ("win","loss","push"): continue
        sport = b.get("sport","?")
        btype = b.get("betType","ML")
        day   = (b.get("settledAt","") or b.get("date",""))[:10]
        for bucket in (total, by_sport[sport], by_type[btype], by_date[day]):
            bucket[o if o!="win" else "w"] = bucket.get(o if o!="win" else "w",0) + 1
            bucket["total"] = bucket.get("total",0) + 1

    def pct(d): return round(d["w"]/d["total"]*100,1) if d["total"] else 0
    return {
        "total":     {**total, "pct": pct(total)},
        "bySport":   {k: {**v,"pct":pct(v)} for k,v in by_sport.items()},
        "byBetType": {k: {**v,"pct":pct(v)} for k,v in by_type.items()},
        "byDate":    dict(sorted(by_date.items())[-30:]),   # last 30 days
        "fetchedAt": TODAY_ISO,
    }

# ═══════════════════════════════════════════════════════════════════════════════
# data.json writer + HTML timestamp patcher
# ═══════════════════════════════════════════════════════════════════════════════
def write_data_json(bundle: dict) -> None:
    payload = json.dumps(bundle, indent=2)
    FE_DATA.write_text(payload)
    note(f"data.json written ({len(payload)//1024} KB) → frontend/ (engine data stays private)")

def patch_html_timestamp() -> None:
    # Only patch the local SPA — docs/ is the public landing page, engine stays private
    if not FE.exists(): return
    html   = FE.read_text(encoding="utf-8")
    ts_pat = r"(LAST_AUTO_UPDATE\s*=\s*['\"])([^'\"]*?)(['\"])"
    if re.search(ts_pat, html):
        html = re.sub(ts_pat, rf"\g<1>{TS_DISPLAY}\g<3>", html)
    else:
        html = html.replace("<script>",
            f'<script>\nconst LAST_AUTO_UPDATE = "{TS_DISPLAY}";\n', 1)
    FE.write_text(html, encoding="utf-8")
    vlog(f"HTML timestamp patched → {TS_DISPLAY}")

# ═══════════════════════════════════════════════════════════════════════════════
# Git push
# ═══════════════════════════════════════════════════════════════════════════════
def git_push(summary: str = "") -> bool:
    try:
        subprocess.run(["git","-C",str(ROOT),"add",
            # engine data — frontend/ only, never pushed to docs/
            "frontend/data.json",
            "frontend/index.html",
            "frontend/live_data.json",
            "frontend/card.png",
            "frontend/social_copy.json",
            # persistent records
            "data/bet_history.json",
            # public domain — landing page assets only
            "docs/index.html",
            "docs/landing.html",
            "docs/CNAME",
            "docs/card.png",
            "docs/pinned_card.png",
            "docs/clairvoyance-logo.svg",
        ], capture_output=True, check=False)
        diff = subprocess.run(["git","-C",str(ROOT),"diff","--cached","--quiet"],
                              capture_output=True)
        if diff.returncode == 0:
            log("git: nothing to commit"); return True
        msg = f"data: {TS_DISPLAY} auto-refresh\n\n{summary}"
        subprocess.run(["git","-C",str(ROOT),"commit","-m",msg], check=True, capture_output=True)
        subprocess.run(["git","-C",str(ROOT),"push","origin","main"], check=True, capture_output=True)
        note("git push → main ✓")
        return True
    except Exception as exc:
        log(f"git push failed: {exc}", "WARN"); return False

# ═══════════════════════════════════════════════════════════════════════════════
# Live Window  (17:00–23:00 MT continuous refresh)
# ═══════════════════════════════════════════════════════════════════════════════
def run_live_window(push: bool = True, interval_sec: int = 90) -> None:
    log("=== LIVE WINDOW MODE STARTED ===")
    live_data_fe   = ROOT / "frontend" / "live_data.json"   # engine stays private

    while True:
        try:
            now_mt = datetime.now().astimezone()  # uses system TZ (set to America/Denver in cron)
        except Exception:
            now_mt = datetime.now()
        hour = now_mt.hour
        if hour >= 23 or hour < 1:
            log("=== LIVE WINDOW END ==="); break

        log(f"Live refresh {now_mt.strftime('%H:%M')}…")
        try:
            mlb_t, _  = fetch_mlb_scoreboard()
            nba_t, _  = fetch_nba_scoreboard()
            nhl_t, _  = fetch_nhl_schedule()
            tennis    = fetch_tennis_schedule()
            live_bundle = {
                "generatedMT": now_mt.isoformat(),
                "ts":          now_mt.strftime("%H:%M MT"),
                "mlbLive":     [g for g in mlb_t  if g.get("state") == "in"],
                "nbaLive":     [g for g in nba_t  if g.get("state") == "in"],
                "nhlLive":     [g for g in nhl_t  if g.get("state") in ("LIVE","CRIT","IN")],
                "tennisLive":  [m for m in tennis if m.get("state") == "in"],
                "mlbAll":      mlb_t,
                "nbaAll":      nba_t,
                "nhlAll":      nhl_t,
            }
            live_data_fe.write_text(json.dumps(live_bundle, indent=2))

            if push:
                subprocess.run(["git","-C",str(ROOT),"add",
                    "frontend/live_data.json"], capture_output=True)
                diff = subprocess.run(["git","-C",str(ROOT),"diff","--cached","--quiet"],
                                      capture_output=True)
                if diff.returncode != 0:
                    subprocess.run(["git","-C",str(ROOT),"commit","-m",
                        f"live: {now_mt.strftime('%H:%M')} MT scores"], capture_output=True)
                    subprocess.run(["git","-C",str(ROOT),"push","origin","main"],
                                   capture_output=True)
        except Exception as exc:
            log(f"Live refresh error: {exc}", "WARN")
        time.sleep(interval_sec)

# ═══════════════════════════════════════════════════════════════════════════════
# Main orchestrator
# ═══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    global _verbose

    parser = argparse.ArgumentParser(description="Clairvoyance v5.0 data refresh")
    parser.add_argument("--push",          action="store_true", help="Commit + push to GitHub")
    parser.add_argument("--dry-run",       action="store_true", help="Fetch only, no writes")
    parser.add_argument("--no-linemate",   action="store_true", help="Skip Playwright/Linemate")
    parser.add_argument("--no-reference",  action="store_true", help="Skip Baseball/Basketball/Hockey Reference")
    parser.add_argument("--mode",          choices=["full","live","props"], default="full")
    parser.add_argument("--sport",         choices=["nba","mlb","nhl","tennis","f1","all"], default="all")
    parser.add_argument("--verbose","-v",  action="store_true")
    args    = parser.parse_args()
    _verbose = args.verbose

    # ── live-window short-circuit ────────────────────────────────────────────
    if args.mode == "live":
        run_live_window(push=args.push)
        return

    log("=" * 60)
    log(f"Clairvoyance v5.0 — {TS_DISPLAY}")
    log(f"Mode: {args.mode} | Sport: {args.sport}")
    log("=" * 60)

    S = args.sport  # shorthand

    # ── props-only mode ──────────────────────────────────────────────────────
    if args.mode == "props":
        lm: dict = {}
        for sport in ["mlb","nba","nhl"]:
            if S in (sport,"all"):
                lm[sport] = {
                    "props":  fetch_linemate_props(sport),
                    "trends": fetch_linemate_trends(sport),
                    "form":   fetch_linemate_cheatsheet(sport),
                }
                time.sleep(1)
        (DATA / "linemate.json").write_text(json.dumps(lm, indent=2))
        if args.push: git_push("props-only refresh")
        return

    # ── full fetch phase ─────────────────────────────────────────────────────
    mlb_today, mlb_tom   = fetch_mlb_scoreboard()         if S in ("mlb","all") else ([],[])
    mlb_standings        = fetch_mlb_standings()          if S in ("mlb","all") else {}
    mlb_week             = fetch_mlb_schedule_week()      if S in ("mlb","all") else []
    mlb_ref              = (fetch_baseball_reference()    if not args.no_reference else {}) if S in ("mlb","all") else {}
    mlb_nrfi             = fetch_mlb_nrfi_data(mlb_today) if S in ("mlb","all") else []

    nba_today, nba_tom   = fetch_nba_scoreboard()         if S in ("nba","all") else ([],[])
    nba_standings        = fetch_nba_standings()          if S in ("nba","all") else {}
    nba_players          = fetch_nba_player_stats()       if S in ("nba","all") else []
    nba_bracket          = fetch_nba_playoff_bracket()    if S in ("nba","all") else {}
    nba_ref              = (fetch_basketball_reference()  if not args.no_reference else {}) if S in ("nba","all") else {}

    nhl_today, nhl_tom   = fetch_nhl_schedule()           if S in ("nhl","all") else ([],[])
    nhl_standings        = fetch_nhl_standings()          if S in ("nhl","all") else {}
    nhl_bracket          = fetch_nhl_playoff_bracket()    if S in ("nhl","all") else {}
    nhl_edge             = fetch_nhl_edge()               if S in ("nhl","all") else {}
    mp                   = fetch_moneypuck()              if S in ("nhl","all") else {}
    hockeyviz            = fetch_hockeyviz()              if S in ("nhl","all") else {}
    hockey_ref           = (fetch_hockey_reference()      if not args.no_reference else {}) if S in ("nhl","all") else {}

    atp_elo   = fetch_tennis_elo("atp")      if S in ("tennis","all") else []
    wta_elo   = fetch_tennis_elo("wta")      if S in ("tennis","all") else []
    atp_yelo  = fetch_tennis_yelo("atp")     if S in ("tennis","all") else []
    wta_yelo  = fetch_tennis_yelo("wta")     if S in ("tennis","all") else []
    tennis_schedule   = fetch_tennis_schedule()       if S in ("tennis","all") else []
    tennis_sched_full = fetch_tennis_schedule_full()  if S in ("tennis","all") else {}
    tennis_rankings   = fetch_tennis_rankings_espn()  if S in ("tennis","all") else {}

    f1_data          = fetch_f1()               if S in ("f1","all") else {}
    f1_analytics     = fetch_f1_analytics()     if S in ("f1","all") else {}
    f1_tracing       = fetch_f1_tracing_insights() if S in ("f1","all") else {}
    f1_calendar      = fetch_f1_calendar_datastop() if S in ("f1","all") else []

    # Weather for MLB home teams
    weather: dict = {}
    if S in ("mlb","all"):
        log("Fetching MLB weather…")
        for g in mlb_today:
            home = g.get("home","")
            if home and home not in weather:
                w = fetch_weather(home)
                if w: weather[home] = w
                time.sleep(0.3)

    # Linemate
    lm_props:  dict = {"nba":[],"mlb":[],"nhl":[]}
    lm_trends: dict = {"nba":[],"mlb":[],"nhl":[]}
    lm_form:   dict = {"nba":[],"mlb":[],"nhl":[]}
    if not args.no_linemate:
        for sport in ["nba","mlb","nhl"]:
            if S in (sport,"all"):
                lm_props[sport]  = fetch_linemate_props(sport);     time.sleep(1)
                lm_trends[sport] = fetch_linemate_trends(sport);    time.sleep(1)
                lm_form[sport]   = fetch_linemate_cheatsheet(sport); time.sleep(1)

    # News + injuries
    sports_news = fetch_sports_news()
    injuries    = fetch_injuries_all()

    # Best bets + auto-settle
    best_bets = calculate_best_bets(nba_today, mlb_today, nhl_today, weather, mp, nhl_edge)
    settled   = auto_settle(
        nba_today + nba_tom,
        mlb_today + mlb_tom,
        nhl_today + nhl_tom,
    )

    # Bet history
    history = merge_settled_to_history(settled)
    export_bet_history_csv(history)
    overall_stats = build_overall_stats(history)

    # ── bundle ───────────────────────────────────────────────────────────────
    bundle: dict = {
        "generated":    NOW.isoformat(),
        "generatedMT":  TS_DISPLAY,
        "version":      "5.0",
        "mlb": {
            "today":     mlb_today,
            "tomorrow":  mlb_tom,
            "standings": mlb_standings,
            "weekSchedule": mlb_week,
            "nrfi":      mlb_nrfi,
            "reference": mlb_ref,
        },
        "nba": {
            "today":     nba_today,
            "tomorrow":  nba_tom,
            "standings": nba_standings,
            "players":   nba_players,
            "bracket":   nba_bracket,
            "reference": nba_ref,
        },
        "nhl": {
            "today":     nhl_today,
            "tomorrow":  nhl_tom,
            "standings": nhl_standings,
            "bracket":   nhl_bracket,
            "edge":      nhl_edge,
            "hockeyviz": hockeyviz,
            "hockeyRef": hockey_ref,
        },
        "mp":      mp,
        "weather": weather,
        "tennis": {
            "atpElo":        atp_elo[:100],
            "wtaElo":        wta_elo[:100],
            "atpYelo":       atp_yelo[:100],
            "wtaYelo":       wta_yelo[:100],
            "schedule":      tennis_schedule,
            "scheduleFull":  tennis_sched_full,
            "rankings":      tennis_rankings,
            "scheduleDate":  TODAY_ISO,
        },
        "f1": {
            **f1_data,
            "analytics":  f1_analytics,
            "tracing":    f1_tracing,
            "calendar":   f1_calendar,
        },
        "linemate": {
            "props":  lm_props,
            "trends": lm_trends,
            "form":   lm_form,
        },
        "bestBets":      best_bets,
        "settled":       settled,
        "betHistory":    history[-200:],  # last 200 for frontend
        "overallStats":  overall_stats,
        "news":          sports_news,
        "injuries":      injuries,
    }

    (DATA / "bundle.json").write_text(json.dumps(bundle, indent=2))

    if args.dry_run:
        log("Dry run — skipping writes and push"); return

    write_data_json(bundle)
    patch_html_timestamp()

    # Social content + card
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from content_generator import generate_content, write_social_copy
        from generate_card import generate_card
        social = generate_content(bundle, verbose=_verbose)
        if social:
            write_social_copy(social)
            note("social_copy.json written")
            img = generate_card(bundle, social)
            for p in (ROOT/"frontend"/"card.png", ROOT/"docs"/"card.png"):
                img.save(str(p), format="PNG", optimize=True)
            note("card.png written")
    except Exception as exc:
        log(f"Content generation skipped: {exc}", "WARN")

    # Always push
    if args.push:
        summary = (
            f"MLB: {len(mlb_today)} games | NBA: {len(nba_today)} games | "
            f"NHL: {len(nhl_today)} games\n"
            f"Best bets: {len(best_bets)} | Settled: {len(settled)} | "
            f"History: {len(history)} total\n"
            f"ATP ELO: {len(atp_elo)} | WTA ELO: {len(wta_elo)}"
        )
        git_push(summary)

    log("=" * 60)
    log(f"Done. {len(_changes)} changes.")
    for c in _changes: log(f"  • {c}")
    log("=" * 60)


if __name__ == "__main__":
    main()
