#!/usr/bin/env python3
from __future__ import annotations
"""
clairvoyance_update.py — Clairvoyance Master Data Refresh Engine v6.0
Fetches live stats, odds, schedules, standings, props, injuries, advanced
analytics across MLB, NBA, NHL, Tennis (Roland Garros), F1 then pushes to
GitHub Pages.

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

Data sources (v6.0):
  ESPN APIs, NHL API, MoneyPuck, HockeyViz, TennisAbstract Elo, Ergast F1,
  ESPN F1 scoreboard/standings, TennisAbstract Roland Garros, Sports-Reference
  (Baseball/Basketball/Hockey-Reference), Open-Meteo weather, Linemate Playwright
"""

import argparse, csv, io, json, os, re, shutil, subprocess, sys, time
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

# ── load .env early (before any os.environ reads) ────────────────────────────
def _load_dotenv(path: Path) -> None:
    """Minimal .env loader — no external deps required."""
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:   # don't override shell env
                os.environ[key] = val
    except Exception:
        pass

_load_dotenv(Path(__file__).parent.parent / ".env")

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
FE       = ROOT / "docs" / "index.html"       # Engine SPA — served at github.io/clairvoyance-backend/
FE_DATA  = ROOT / "docs" / "data.json"        # Engine data pushed to docs/ → github.io
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
    _ET = zoneinfo.ZoneInfo("America/New_York")
    NOW_MT = datetime.now(_MT)
    NOW_ET = datetime.now(_ET)
except Exception:
    NOW_MT = NOW - timedelta(hours=6)
    NOW_ET = NOW - timedelta(hours=4)

TODAY_MT   = NOW_MT.strftime("%Y%m%d")
TODAY_ET   = NOW_ET.strftime("%Y%m%d")   # MLB uses Eastern Time for scheduling
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

def _notify(title: str, msg: str) -> None:
    """macOS system notification via osascript."""
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{msg}" with title "Clairvoyance ⚡ {title}" sound name "Glass"'],
            capture_output=True, timeout=5
        )
    except Exception:
        pass  # non-macOS or osascript unavailable — silent fail

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
def _espn_odds(comp: dict, sport: str = "", league: str = "", event_id: str = "") -> dict:
    """Extract odds from ESPN competition dict.  Falls back to ESPN Core odds API when
    the scoreboard response has no odds (sport/league/event_id required for fallback)."""
    odds = (comp.get("odds") or [{}])[0]
    result = {
        "homeML":   odds.get("homeTeamOdds", {}).get("moneyLine"),
        "awayML":   odds.get("awayTeamOdds", {}).get("moneyLine"),
        "ou":       odds.get("overUnder"),
        "spread":   odds.get("spread"),
        "provider": (odds.get("provider") or {}).get("name", ""),
    }
    # If no odds came from scoreboard and we have sport/league/event info, try Core API fallback
    if (result["homeML"] is None and result["awayML"] is None
            and sport and league and event_id):
        try:
            url = (f"https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}"
                   f"/events/{event_id}/competitions/{event_id}/odds")
            fallback = fetch_json(url, timeout=10)
            items = (fallback or {}).get("items", [])
            if items:
                ref = items[0].get("$ref", "")
                if ref:
                    o = fetch_json(ref, timeout=10) or {}
                    home_o = o.get("homeTeamOdds", {})
                    away_o = o.get("awayTeamOdds", {})
                    if home_o.get("moneyLine") or away_o.get("moneyLine"):
                        result.update({
                            "homeML":   home_o.get("moneyLine"),
                            "awayML":   away_o.get("moneyLine"),
                            "ou":       o.get("overUnder"),
                            "spread":   o.get("spread"),
                            "provider": (o.get("provider") or {}).get("name", "ESPN-Core"),
                        })
                        vlog(f"  ESPN odds fallback used for event {event_id}")
        except Exception as exc:
            vlog(f"  ESPN odds fallback failed {event_id}: {exc}")
    return result

_ESPN_SPORT_LEAGUE: dict[str, tuple[str, str]] = {
    "MLB": ("baseball", "mlb"),
    "NBA": ("basketball", "nba"),
    "NHL": ("hockey", "nhl"),
}

def _espn_game(event: dict, sport: str) -> dict:
    comp  = (event.get("competitions") or [{}])[0]
    comps = comp.get("competitors") or []
    home  = next((c for c in comps if c.get("homeAway") == "home"), {})
    away  = next((c for c in comps if c.get("homeAway") == "away"), {})
    status = event.get("status") or {}
    state  = (status.get("type") or {}).get("state", "pre")
    event_id = event.get("id", "")
    espn_sport, espn_league = _ESPN_SPORT_LEAGUE.get(sport, ("", ""))
    g: dict = {
        "id":          event_id,
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
    g.update(_espn_odds(comp, sport=espn_sport, league=espn_league, event_id=event_id))
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
def fetch_mlb_scoreboard(date: str = TODAY_ET) -> tuple[list, list]:
    """Fetch MLB scoreboard. Uses Eastern Time date since MLB schedules games in ET.
    Deduplicates by event ID and filters to only include today's games (ET date)."""
    log(f"MLB scoreboard {date} (ET)…")
    data = fetch_json(f"{ESPN_BASE}/baseball/mlb/scoreboard?dates={date}&limit=30")
    if not data: return [], []
    seen_ids: set = set()
    games = []
    for e in (data.get("events") or []):
        eid = e.get("id", "")
        # Only include events whose date matches today (ET) — event date is YYYYMMDD-prefixed in UTC
        event_date_raw = e.get("date", "")  # ISO string e.g. "2026-05-23T18:05Z"
        try:
            event_date_et = datetime.fromisoformat(event_date_raw.replace("Z", "+00:00")).astimezone(
                _ET if "zoneinfo" in sys.modules else timezone(timedelta(hours=-4))
            ).strftime("%Y%m%d")
        except Exception:
            event_date_et = date  # default to requested date if parse fails
        if event_date_et != date:
            vlog(f"  MLB skip stale/future event {eid} dated {event_date_et}")
            continue
        if eid in seen_ids:
            vlog(f"  MLB skip duplicate event {eid}")
            continue
        seen_ids.add(eid)
        games.append(_espn_game(e, "MLB"))
    tom   = (datetime.strptime(date, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
    data2 = fetch_json(f"{ESPN_BASE}/baseball/mlb/scoreboard?dates={tom}&limit=30")
    seen_tom: set = set()
    tomorrow = []
    for e in ((data2 or {}).get("events") or []):
        eid = e.get("id", "")
        if eid in seen_tom: continue
        seen_tom.add(eid)
        tomorrow.append(_espn_game(e, "MLB"))
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
    """Fetch MLB schedule for next 7 days (using Eastern Time base)."""
    log("MLB week schedule…")
    games: list[dict] = []
    for offset in range(7):
        d = (NOW_ET + timedelta(days=offset)).strftime("%Y%m%d")
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

def fetch_mlb_team_sabermetrics() -> dict:
    """
    Fetch team-level sabermetrics from Baseball Reference 2026 team batting/pitching.
    Returns dict keyed by team abbreviation with wOBA, ISO, FIP, ERA-.
    """
    log("MLB team sabermetrics…")
    result: dict = {}
    try:
        # Team batting — OPS+, ISO, wOBA proxy
        time.sleep(2)
        soup = fetch_html("https://www.baseball-reference.com/leagues/majors/2026-standard-batting.shtml",
                          timeout=25, ref=True)
        if soup:
            tbl = soup.find("table", {"id": "teams_standard_batting"})
            if tbl:
                for tr in tbl.find_all("tr")[1:]:
                    cells = tr.find_all(["th","td"])
                    if len(cells) < 18: continue
                    tm = cells[0].get_text(strip=True)
                    if tm in ("","Tm","LgAvg","--"): continue
                    try:
                        ops_plus = float(cells[15].get_text(strip=True) or 100)
                    except: ops_plus = 100.0
                    try:
                        iso = float(cells[17].get_text(strip=True) or 0.15)
                    except: iso = 0.15
                    result[tm] = result.get(tm, {})
                    result[tm].update({"ops_plus": ops_plus, "iso": iso})
    except Exception as exc:
        log(f"MLB team batting sabermetrics: {exc}", "WARN")
    try:
        # Team pitching — FIP, ERA-
        time.sleep(2)
        soup = fetch_html("https://www.baseball-reference.com/leagues/majors/2026-standard-pitching.shtml",
                          timeout=25, ref=True)
        if soup:
            tbl = soup.find("table", {"id": "teams_standard_pitching"})
            if tbl:
                for tr in tbl.find_all("tr")[1:]:
                    cells = tr.find_all(["th","td"])
                    if len(cells) < 20: continue
                    tm = cells[0].get_text(strip=True)
                    if tm in ("","Tm","LgAvg","--"): continue
                    try:
                        fip = float(cells[18].get_text(strip=True) or 4.20)
                    except: fip = 4.20
                    try:
                        era_minus = float(cells[19].get_text(strip=True) or 100)
                    except: era_minus = 100.0
                    result[tm] = result.get(tm, {})
                    result[tm].update({"fip": fip, "era_minus": era_minus})
    except Exception as exc:
        log(f"MLB team pitching sabermetrics: {exc}", "WARN")
    log(f"MLB team sabermetrics: {len(result)} teams")
    return result


def fetch_nba_team_advanced() -> dict:
    """
    Fetch team-level NBA playoff advanced stats from Basketball Reference.
    Returns dict keyed by team abbreviation with ortg, drtg, pace, efg_pct, ts_pct.
    Used for probability adjustment in calculate_best_bets.
    """
    log("NBA team advanced stats…")
    result: dict = {}
    # BBRef abbreviation → ESPN abbreviation mapping (common playoff teams 2026)
    ABBR_MAP = {
        "NYK":"NY","CLE":"CLE","OKC":"OKC","SAS":"SA","BOS":"BOS","MIA":"MIA",
        "MIN":"MIN","DEN":"DEN","GSW":"GS","PHX":"PHX","LAL":"LAL","LAC":"LAC",
        "MIL":"MIL","PHI":"PHI","TOR":"TOR","CHI":"CHI","ATL":"ATL","MEM":"MEM",
    }
    try:
        time.sleep(2)
        soup = fetch_html(
            "https://www.basketball-reference.com/playoffs/NBA_2026.html",
            timeout=25, ref=True
        )
        if not soup:
            return result
        # Team misc stats table: team_misc
        tbl = soup.find("table", {"id": "misc_stats"})
        if not tbl:
            # Sometimes embedded in HTML comments
            from bs4 import Comment
            for cmt in soup.find_all(string=lambda t: isinstance(t, Comment)):
                if "misc_stats" in cmt:
                    frag = BeautifulSoup(cmt, "lxml")
                    tbl = frag.find("table", {"id": "misc_stats"})
                    if tbl: break
        if tbl:
            headers = [th.get("data-stat","") for th in tbl.find_all("th") if th.get("data-stat")]
            for tr in tbl.find_all("tr"):
                cells = {td.get("data-stat",""): td.get_text(strip=True)
                         for td in tr.find_all(["td","th"])}
                tm = cells.get("team_id","").upper()
                if not tm or tm in ("TEAM","",): continue
                espn_abbr = ABBR_MAP.get(tm, tm)
                try:
                    ortg = float(cells.get("off_rtg","") or 0)
                    drtg = float(cells.get("def_rtg","") or 0)
                    pace = float(cells.get("pace","") or 0)
                    efg  = float(cells.get("efg_pct","") or 0)
                    ts   = float(cells.get("ts_pct","") or 0)
                    if ortg > 0:
                        result[espn_abbr] = {
                            "ortg": ortg, "drtg": drtg, "pace": pace,
                            "efg_pct": efg, "ts_pct": ts,
                            "net_rtg": ortg - drtg,
                        }
                except (ValueError, TypeError):
                    continue
    except Exception as exc:
        log(f"NBA team advanced: {exc}", "WARN")
    log(f"NBA team advanced: {len(result)} teams")
    return result


_TEAM_NAME_TO_ABBR: dict[str, str] = {
    # MLB
    "Arizona Diamondbacks":"ARI","Atlanta Braves":"ATL","Baltimore Orioles":"BAL",
    "Boston Red Sox":"BOS","Chicago Cubs":"CHC","Chicago White Sox":"CWS",
    "Cincinnati Reds":"CIN","Cleveland Guardians":"CLE","Colorado Rockies":"COL",
    "Detroit Tigers":"DET","Houston Astros":"HOU","Kansas City Royals":"KC",
    "Los Angeles Angels":"LAA","Los Angeles Dodgers":"LAD","Miami Marlins":"MIA",
    "Milwaukee Brewers":"MIL","Minnesota Twins":"MIN","New York Mets":"NYM",
    "New York Yankees":"NYY","Oakland Athletics":"OAK","Athletics":"OAK",
    "Philadelphia Phillies":"PHI","Pittsburgh Pirates":"PIT","San Diego Padres":"SD",
    "San Francisco Giants":"SF","Seattle Mariners":"SEA","St. Louis Cardinals":"STL",
    "Tampa Bay Rays":"TB","Texas Rangers":"TEX","Toronto Blue Jays":"TOR",
    "Washington Nationals":"WSH",
    # NBA
    "Atlanta Hawks":"ATL","Boston Celtics":"BOS","Brooklyn Nets":"BKN",
    "Charlotte Hornets":"CHA","Chicago Bulls":"CHI","Cleveland Cavaliers":"CLE",
    "Dallas Mavericks":"DAL","Denver Nuggets":"DEN","Detroit Pistons":"DET",
    "Golden State Warriors":"GSW","Houston Rockets":"HOU","Indiana Pacers":"IND",
    "Los Angeles Clippers":"LAC","Los Angeles Lakers":"LAL","Memphis Grizzlies":"MEM",
    "Miami Heat":"MIA","Milwaukee Bucks":"MIL","Minnesota Timberwolves":"MIN",
    "New Orleans Pelicans":"NOP","New York Knicks":"NYK","Oklahoma City Thunder":"OKC",
    "Orlando Magic":"ORL","Philadelphia 76ers":"PHI","Phoenix Suns":"PHX",
    "Portland Trail Blazers":"POR","Sacramento Kings":"SAC","San Antonio Spurs":"SAS",
    "Toronto Raptors":"TOR","Utah Jazz":"UTA","Washington Wizards":"WSH",
    # NHL
    "Anaheim Ducks":"ANA","Arizona Coyotes":"ARI","Boston Bruins":"BOS",
    "Buffalo Sabres":"BUF","Calgary Flames":"CGY","Carolina Hurricanes":"CAR",
    "Chicago Blackhawks":"CHI","Colorado Avalanche":"COL","Columbus Blue Jackets":"CBJ",
    "Dallas Stars":"DAL","Detroit Red Wings":"DET","Edmonton Oilers":"EDM",
    "Florida Panthers":"FLA","Los Angeles Kings":"LAK","Minnesota Wild":"MIN",
    "Montreal Canadiens":"MTL","Nashville Predators":"NSH","New Jersey Devils":"NJD",
    "New York Islanders":"NYI","New York Rangers":"NYR","Ottawa Senators":"OTT",
    "Philadelphia Flyers":"PHI","Pittsburgh Penguins":"PIT","San Jose Sharks":"SJS",
    "Seattle Kraken":"SEA","St. Louis Blues":"STL","Tampa Bay Lightning":"TB",
    "Toronto Maple Leafs":"TOR","Utah Hockey Club":"UTA","Vancouver Canucks":"VAN",
    "Vegas Golden Knights":"VGK","Washington Capitals":"WSH","Winnipeg Jets":"WPG",
}

def _name_to_abbr(name: str) -> str:
    """Convert Odds API team name → ESPN abbreviation. Falls back to first 3 chars."""
    return _TEAM_NAME_TO_ABBR.get(name, name[:3].upper())

def fetch_best_odds(sport: str, game_list: list) -> dict:
    """
    Fetch best available moneyline + O/U odds from The Odds API (free tier).
    Falls back to ESPN odds already in game_list if no API key.
    Returns dict keyed by 'home_abbr:away_abbr' → {homeML, awayML, ou, book}.
    """
    api_key = os.environ.get("ODDS_API_KEY", "")
    best: dict = {}
    if not api_key:
        for g in game_list:
            key = f"{g.get('home','')}:{g.get('away','')}"
            best[key] = {"homeML": g.get("homeML"), "awayML": g.get("awayML"),
                         "ou": g.get("ou"), "book": "ESPN"}
        return best

    sport_key = {"mlb": "baseball_mlb", "nba": "basketball_nba",
                 "nhl": "icehockey_nhl"}.get(sport, "")
    if not sport_key:
        return best

    try:
        url  = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        data = fetch_json(url, params={
            "apiKey": api_key, "regions": "us",
            "markets": "h2h,totals",       # moneyline + over/under
            "oddsFormat": "american", "dateFormat": "iso",
        }) or []

        remaining = None
        log(f"Odds API {sport}: {len(data)} events")

        for event in data:
            home_name = event.get("home_team", "")
            away_name = event.get("away_team", "")
            home_abbr = _name_to_abbr(home_name)
            away_abbr = _name_to_abbr(away_name)
            key = f"{home_abbr}:{away_abbr}"

            best_home_ml: int | None = None
            best_away_ml: int | None = None
            best_home_book = ""
            best_away_book = ""
            best_ou: float | None  = None

            for bk in (event.get("bookmakers") or []):
                bk_title = bk.get("title", "")
                for market in (bk.get("markets") or []):
                    mkey = market.get("key", "")
                    for outcome in (market.get("outcomes") or []):
                        p   = outcome.get("price")
                        nm  = outcome.get("name", "")
                        pt  = outcome.get("point")          # for totals
                        if p is None: continue

                        if mkey == "h2h":
                            if nm == home_name:
                                if best_home_ml is None or int(p) > best_home_ml:
                                    best_home_ml   = int(p)
                                    best_home_book = bk_title
                            elif nm == away_name:
                                if best_away_ml is None or int(p) > best_away_ml:
                                    best_away_ml   = int(p)
                                    best_away_book = bk_title
                        elif mkey == "totals" and nm == "Over" and pt is not None:
                            # Take the highest (most favorable) total line
                            if best_ou is None or float(pt) > best_ou:
                                best_ou = float(pt)

            if best_home_ml or best_away_ml:
                book_str = best_home_book or best_away_book or "Odds API"
                best[key] = {
                    "homeML":   best_home_ml,
                    "awayML":   best_away_ml,
                    "ou":       best_ou,
                    "book":     book_str,
                    "homeBook": best_home_book,
                    "awayBook": best_away_book,
                }
                vlog(f"  {key}: home {best_home_ml} ({best_home_book}) / "
                     f"away {best_away_ml} ({best_away_book}) O/U {best_ou}")

    except Exception as exc:
        log(f"Odds API fetch ({sport}): {exc}", "WARN")
    return best


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
def fetch_nba_scoreboard(date: str = TODAY_ET) -> tuple[list, list]:
    """Fetch NBA scoreboard. Uses Eastern Time date since NBA game times are listed in ET."""
    log(f"NBA scoreboard {date} (ET)…")
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

def fetch_basketball_reference_series(series_url: str) -> dict:
    """Fetch a single Basketball Reference playoff series page and parse game log + per-game stats.
    series_url example:
      https://www.basketball-reference.com/playoffs/2026-nba-eastern-conference-finals-cavaliers-vs-knicks.html
    Returns dict with gameLog, perGame, advanced, seriesStatus."""
    log(f"Basketball Reference series: {series_url.split('/')[-1]}…")
    result: dict = {"url": series_url, "gameLog": [], "perGame": [], "advanced": [], "seriesStatus": "", "fetchedAt": TODAY_ISO}
    try:
        time.sleep(2)
        soup = fetch_html(series_url, ref=True)
        if not soup:
            return result
        # Game log — usually a "games" table or "schedule"
        game_log_rows = _table_to_rows(soup, "games", limit=7)
        if not game_log_rows:
            game_log_rows = _table_to_rows(soup, "schedule", limit=7)
        result["gameLog"] = game_log_rows
        # Per-game stats
        for key, tbl_id in [("perGame","per_game"),("advanced","advanced")]:
            rows = _table_to_rows(soup, tbl_id, limit=20)
            result[key] = rows
        # Series status from page title
        h1 = soup.find("h1")
        if h1: result["seriesStatus"] = h1.get_text(strip=True)[:120]
        vlog(f"  BBRef series: {len(game_log_rows)} games, {len(result['perGame'])} per-game rows")
    except Exception as exc:
        log(f"Basketball Reference series {series_url}: {exc}", "WARN")
        result["error"] = str(exc)
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

def fetch_nhl_today() -> tuple[list, list]:
    """Fetch NHL schedule for today, trying both MT and ET dates to avoid empty results."""
    mt_date = NOW_MT.strftime("%Y-%m-%d")
    et_date = NOW_ET.strftime("%Y-%m-%d")
    result = fetch_nhl_schedule(mt_date)
    today_games, tom_games = result
    if not today_games and mt_date != et_date:
        log(f"NHL: MT date {mt_date} returned no games, trying ET date {et_date}…")
        result = fetch_nhl_schedule(et_date)
        today_games, tom_games = result
    return today_games, tom_games

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

def fetch_nhl_edge_enhanced() -> dict:
    """
    Enhanced NHL Edge — shot location, zone time, save locations, 5v5 details.
    Scrapes nhl.com/nhl-edge for team-level and goalie-level advanced shot data.
    """
    log("NHL Edge enhanced (shot location, zone time, save %)…")
    out: dict = {"teams": {}, "goalies": {}, "shotMaps": {}}
    base = "https://www.nhl.com"

    def _nhl_edge_api(path: str, params: dict = None) -> list:
        url = f"https://api.nhle.com{path}"
        try:
            resp = fetch_json(url, params=params)
            if isinstance(resp, dict):
                for key in ("data","skaterStats","goalieStats","teamStats"):
                    if isinstance(resp.get(key), list):
                        return resp[key]
            elif isinstance(resp, list):
                return resp
        except Exception:
            pass
        return []

    # Team 5v5 stats from NHL API
    try:
        season = "20252026"
        team_stats = _nhl_edge_api(f"/stats/rest/en/team/summary?cayenneExp=seasonId={season}%20and%20gameTypeId=3")
        for t in team_stats:
            abbr = t.get("teamAbbrevName","")
            if not abbr: continue
            out["teams"][abbr] = {
                "gp": t.get("gamesPlayed",0),
                "w": t.get("wins",0), "l": t.get("losses",0),
                "gf": t.get("goalsFor",0), "ga": t.get("goalsAgainst",0),
                "gf60": round(t.get("goalsFor",0) / max(t.get("gamesPlayed",1),1) * 60 / 60, 2),
                "pp_pct": t.get("powerPlayPct",0),
                "pk_pct": t.get("penaltyKillPct",0),
                "shots_for": t.get("shotsForPerGame",0),
                "shots_ag": t.get("shotsAgainstPerGame",0),
                "faceoff_pct": t.get("faceoffWinPct",0),
            }
    except Exception as e:
        log(f"NHL Edge team stats error: {e}", "WARN")

    # Goalie save % by zone / shot type from NHL Edge skaters API
    try:
        goalie_data = _nhl_edge_api(
            f"/stats/rest/en/goalie/savesByStrength?cayenneExp=seasonId={season}%20and%20gameTypeId=3&limit=50"
        )
        for g in goalie_data:
            name = f"{g.get('skaterFirstName','')} {g.get('skaterLastName','')}".strip()
            if not name: continue
            out["goalies"][name] = {
                "team": g.get("teamAbbrevs",""),
                "gp": g.get("gamesPlayed",0),
                "sv5v5": g.get("savePctg5v5",0),
                "sv5v4": g.get("savePctg5v4",0),
                "sv4v5": g.get("savePctg4v5",0),
                "svPct": g.get("savePctg",0),
                "gaa": g.get("goalsAgainstAverage",0),
                "hdSvPct": g.get("highDangerSavePct",0),
                "shots": g.get("shotsAgainst",0),
            }
    except Exception as e:
        log(f"NHL Edge goalie save % error: {e}", "WARN")

    vlog(f"  NHL Edge enhanced: {len(out['teams'])} teams, {len(out['goalies'])} goalies")
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

def fetch_hockey_reference_series(series_url: str) -> dict:
    """Fetch a single Hockey Reference playoff series page and parse game log.
    series_url example:
      https://www.hockey-reference.com/playoffs/2026-carolina-hurricanes-vs-montreal-canadiens-eastern-conference-finals.html
    Returns dict with gameLog, scorers, seriesStatus."""
    log(f"Hockey Reference series: {series_url.split('/')[-1]}…")
    result: dict = {"url": series_url, "gameLog": [], "scorers": [], "seriesStatus": "", "fetchedAt": TODAY_ISO}
    try:
        time.sleep(2)
        soup = fetch_html(series_url, ref=True)
        if not soup:
            return result
        # Parse game log table (id="games" or first substantial table)
        game_log_rows = _table_to_rows(soup, "games", limit=10)
        if not game_log_rows:
            for tbl in soup.find_all("table")[:4]:
                tbl_id = tbl.get("id","")
                rows = _table_to_rows(soup, tbl_id, limit=10) if tbl_id else []
                if rows and len(rows) > 1:
                    game_log_rows = rows; break
        result["gameLog"] = game_log_rows
        # Series status from page title or header
        h1 = soup.find("h1")
        if h1: result["seriesStatus"] = h1.get_text(strip=True)[:120]
        # Top scorers
        scorer_rows = _table_to_rows(soup, "skaters", limit=10)
        if not scorer_rows:
            scorer_rows = _table_to_rows(soup, "stats", limit=10)
        result["scorers"] = scorer_rows
        vlog(f"  Hockey Ref series: {len(game_log_rows)} games, {len(scorer_rows)} scorers")
    except Exception as exc:
        log(f"Hockey Reference series {series_url}: {exc}", "WARN")
        result["error"] = str(exc)
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

def fetch_tennis_ratio(player1: str = "", player2: str = "") -> dict:
    """TennisRatio — player comparison, surface stats, serve/return, H2H."""
    log("TennisRatio stats…")
    result: dict = {"players": {}, "comparisons": [], "surfaceStats": {}, "serveReturn": {}}
    try:
        base = "https://www.tennisratio.com"
        soup = fetch_html(base)
        if not soup:
            # Return enriched static data from ATP_DB / WTA_DB elo entries if scrape fails
            return result
        # Scrape any available player stats tables
        tables = soup.find_all("table")
        for tbl in tables[:5]:
            headers = [th.get_text(strip=True) for th in tbl.find_all("th")]
            if not headers:
                continue
            for row in tbl.find_all("tr")[1:100]:
                cells = row.find_all(["td","th"])
                if len(cells) < len(headers):
                    continue
                entry = {headers[i]: cells[i].get_text(strip=True) for i in range(min(len(headers), len(cells)))}
                name = entry.get("Player", entry.get("Name", ""))
                if name:
                    result["players"][name] = entry
        # Try to get surface win rates from dedicated pages
        for surface in ["hard", "clay", "grass"]:
            try:
                s_soup = fetch_html(f"{base}/surface/{surface}")
                if not s_soup:
                    continue
                for tbl in s_soup.find_all("table")[:2]:
                    hdrs = [th.get_text(strip=True) for th in tbl.find_all("th")]
                    if not hdrs:
                        continue
                    for row in tbl.find_all("tr")[1:50]:
                        cells = row.find_all(["td","th"])
                        if len(cells) < len(hdrs):
                            continue
                        entry = {hdrs[i]: cells[i].get_text(strip=True) for i in range(min(len(hdrs), len(cells)))}
                        name = entry.get("Player", entry.get("Name", ""))
                        if name:
                            if name not in result["surfaceStats"]:
                                result["surfaceStats"][name] = {}
                            result["surfaceStats"][name][surface] = entry
            except Exception:
                pass
        # Try serve/return stats page
        try:
            srv_soup = fetch_html(f"{base}/serve")
            if srv_soup:
                for tbl in srv_soup.find_all("table")[:2]:
                    hdrs = [th.get_text(strip=True) for th in tbl.find_all("th")]
                    if not hdrs:
                        continue
                    for row in tbl.find_all("tr")[1:50]:
                        cells = row.find_all(["td","th"])
                        if len(cells) < len(hdrs):
                            continue
                        entry = {hdrs[i]: cells[i].get_text(strip=True) for i in range(min(len(hdrs), len(cells)))}
                        name = entry.get("Player", entry.get("Name", ""))
                        if name:
                            result["serveReturn"][name] = entry
        except Exception:
            pass
        vlog(f"  TennisRatio: {len(result['players'])} player entries, {len(result['surfaceStats'])} surface entries")
    except Exception as e:
        log(f"TennisRatio fetch error: {e}", "WARN")
    return result

def fetch_tennis_odds() -> dict:
    """
    Fetch ATP/WTA French Open (Roland Garros) match odds from The Odds API.
    Returns {matches: [{p1, p2, p1ml, p2ml, tour, commence, book}], source, remaining}.
    """
    api_key = os.environ.get("ODDS_API_KEY", "")
    result: dict = {"matches": [], "source": "none", "remaining": None}
    if not api_key:
        return result
    all_matches: list[dict] = []
    for sport_key, tour_label in [
        ("tennis_atp_french_open", "ATP"),
        ("tennis_wta_french_open", "WTA"),
    ]:
        try:
            url  = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
            resp = fetch_json(url, params={
                "apiKey": api_key, "regions": "us",
                "markets": "h2h", "oddsFormat": "american", "dateFormat": "iso",
            })
            if not isinstance(resp, list):
                continue
            for ev in resp:
                p1_name = ev.get("home_team", "")
                p2_name = ev.get("away_team", "")
                commence = ev.get("commence_time", "")
                best_p1_ml: int | None = None
                best_p2_ml: int | None = None
                best_book = ""
                for bk in (ev.get("bookmakers") or []):
                    for mkt in (bk.get("markets") or []):
                        if mkt.get("key") != "h2h": continue
                        for o in (mkt.get("outcomes") or []):
                            p, nm = o.get("price"), o.get("name","")
                            if p is None: continue
                            if nm == p1_name and (best_p1_ml is None or int(p) > best_p1_ml):
                                best_p1_ml = int(p); best_book = bk.get("title","")
                            elif nm == p2_name and (best_p2_ml is None or int(p) > best_p2_ml):
                                best_p2_ml = int(p)
                if best_p1_ml is not None or best_p2_ml is not None:
                    all_matches.append({
                        "tour":    tour_label,
                        "p1":      p1_name,
                        "p2":      p2_name,
                        "p1ml":    best_p1_ml,
                        "p2ml":    best_p2_ml,
                        "book":    best_book,
                        "commence": commence,
                        "surface": "clay",
                        "tournament": f"Roland Garros 2026 {tour_label}",
                    })
            log(f"Tennis Odds API {tour_label}: {len([m for m in all_matches if m['tour']==tour_label])} matches")
        except Exception as exc:
            log(f"Tennis Odds API {sport_key}: {exc}", "WARN")
    result["matches"] = all_matches
    result["source"]  = "The Odds API" if all_matches else "none"
    return result


def fetch_futures_odds() -> dict:
    """
    Fetch championship futures odds from The Odds API.
    Covers: MLB WS, NBA Title, NHL Cup, golf majors.
    Returns {mlb, nba, nhl, golf} — each a list of {team/player, ml, book}.
    """
    api_key = os.environ.get("ODDS_API_KEY", "")
    result: dict = {"mlb": [], "nba": [], "nhl": [], "golf": [], "source": "none"}
    if not api_key:
        return result
    markets = [
        ("baseball_mlb_world_series_winner", "mlb", "World Series"),
        ("basketball_nba_championship_winner", "nba", "NBA Championship"),
        ("icehockey_nhl_championship_winner", "nhl", "Stanley Cup"),
        ("golf_us_open_winner", "golf", "US Open"),
    ]
    any_found = False
    for sport_key, sport_cat, label in markets:
        try:
            resp = fetch_json(
                f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
                params={"apiKey": api_key, "regions": "us", "markets": "outrights",
                        "oddsFormat": "american", "dateFormat": "iso"},
            )
            if not isinstance(resp, list) or not resp:
                continue
            # Take first event (the futures market)
            ev = resp[0]
            picks: dict[str, dict] = {}  # name → {ml, book}
            for bk in (ev.get("bookmakers") or []):
                for mkt in (bk.get("markets") or []):
                    if mkt.get("key") != "outrights": continue
                    for o in (mkt.get("outcomes") or []):
                        nm, p = o.get("name",""), o.get("price")
                        if not nm or p is None: continue
                        ml = int(p)
                        if nm not in picks or ml > picks[nm]["ml"]:
                            picks[nm] = {"ml": ml, "book": bk.get("title",""), "label": label}
            # Sort by best odds (ascending ml = biggest favorite first)
            sorted_picks = sorted(picks.items(), key=lambda x: x[1]["ml"])
            result[sport_cat] = [{"name": k, **v} for k, v in sorted_picks[:20]]
            log(f"Futures {label}: {len(sorted_picks)} picks")
            any_found = True
        except Exception as exc:
            log(f"Futures odds {sport_key}: {exc}", "WARN")
    if any_found:
        result["source"] = "The Odds API"
    return result


def _enrich_rg_bets(bets: list[dict], tennis_odds: dict) -> list[dict]:
    """
    Re-score Roland Garros ELO bets using real Odds API ML lines.
    Falls back to original bet if no Odds API line found.
    """
    if not bets:
        return []
    odds_matches = tennis_odds.get("matches", [])
    # Build lookup: lowercase player name → match
    name_map: dict[str, dict] = {}
    for m in odds_matches:
        for field in ("p1", "p2"):
            name_map[m[field].lower()] = m
            # Last name only fallback
            parts = m[field].split()
            if parts:
                name_map[parts[-1].lower()] = m

    enriched = []
    for bet in bets:
        pick = bet.get("pick", "")
        match = name_map.get(pick.lower()) or name_map.get(pick.split()[-1].lower() if pick else "")
        if match:
            is_p1 = pick.lower() in match["p1"].lower() or match["p1"].lower().endswith(pick.split()[-1].lower() if pick else "")
            real_ml = match["p1ml"] if is_p1 else match["p2ml"]
            if real_ml is not None:
                dec = real_ml / 100 + 1 if real_ml > 0 else 100 / abs(real_ml) + 1
                prob = bet.get("prob", 0.5) / 100
                ev_new = round((prob * dec - 1) * 100, 1)
                bet = {**bet, "ml": f"+{real_ml}" if real_ml > 0 else str(real_ml),
                       "ev": ev_new, "book": match.get("book", ""), "oddsSource": "OddsAPI"}
        enriched.append(bet)
    return enriched


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
    """Return comprehensive 2026 ATP/WTA tournament calendar (hardcoded + ESPN live)."""
    log("Tennis full schedule (2026 calendar)…")

    def _active(start_iso: str, end_iso: str) -> bool:
        try:
            return start_iso <= TODAY_ISO <= end_iso
        except Exception:
            return False

    def _status(start_iso: str, end_iso: str) -> str:
        if TODAY_ISO < start_iso:
            return "upcoming"
        if TODAY_ISO > end_iso:
            return "completed"
        return "active"

    ATP_2026 = [
        {"name":"Australian Open","dates":"Jan 12–26","startDate":"2026-01-12","endDate":"2026-01-26","location":"Melbourne","surface":"Hard","category":"Grand Slam"},
        {"name":"French Open (Roland Garros)","dates":"May 25–Jun 8","startDate":"2026-05-25","endDate":"2026-06-08","location":"Paris","surface":"Clay","category":"Grand Slam"},
        {"name":"Wimbledon","dates":"Jun 30–Jul 13","startDate":"2026-06-30","endDate":"2026-07-13","location":"London","surface":"Grass","category":"Grand Slam"},
        {"name":"US Open","dates":"Aug 24–Sep 7","startDate":"2026-08-24","endDate":"2026-09-07","location":"New York","surface":"Hard","category":"Grand Slam"},
        {"name":"Indian Wells Masters","dates":"Mar 5–16","startDate":"2026-03-05","endDate":"2026-03-16","location":"Indian Wells","surface":"Hard","category":"ATP Masters 1000"},
        {"name":"Miami Open","dates":"Mar 19–30","startDate":"2026-03-19","endDate":"2026-03-30","location":"Miami","surface":"Hard","category":"ATP Masters 1000"},
        {"name":"Madrid Open","dates":"Apr 25–May 4","startDate":"2026-04-25","endDate":"2026-05-04","location":"Madrid","surface":"Clay","category":"ATP Masters 1000"},
        {"name":"Italian Open (Rome)","dates":"May 6–18","startDate":"2026-05-06","endDate":"2026-05-18","location":"Rome","surface":"Clay","category":"ATP Masters 1000"},
        {"name":"Canadian Open (Montreal)","dates":"Jul 24–Aug 3","startDate":"2026-07-24","endDate":"2026-08-03","location":"Montreal","surface":"Hard","category":"ATP Masters 1000"},
        {"name":"Cincinnati Masters","dates":"Aug 6–17","startDate":"2026-08-06","endDate":"2026-08-17","location":"Cincinnati","surface":"Hard","category":"ATP Masters 1000"},
        {"name":"Shanghai Masters","dates":"Oct 6–13","startDate":"2026-10-06","endDate":"2026-10-13","location":"Shanghai","surface":"Hard","category":"ATP Masters 1000"},
        {"name":"Paris Masters","dates":"Oct 26–Nov 2","startDate":"2026-10-26","endDate":"2026-11-02","location":"Paris","surface":"Indoor Hard","category":"ATP Masters 1000"},
        {"name":"ATP Finals","dates":"Nov 9–16","startDate":"2026-11-09","endDate":"2026-11-16","location":"Turin","surface":"Indoor Hard","category":"ATP Finals"},
    ]

    WTA_2026 = [
        {"name":"Australian Open","dates":"Jan 12–26","startDate":"2026-01-12","endDate":"2026-01-26","location":"Melbourne","surface":"Hard","category":"Grand Slam"},
        {"name":"French Open","dates":"May 25–Jun 8","startDate":"2026-05-25","endDate":"2026-06-08","location":"Paris","surface":"Clay","category":"Grand Slam"},
        {"name":"Wimbledon","dates":"Jun 30–Jul 13","startDate":"2026-06-30","endDate":"2026-07-13","location":"London","surface":"Grass","category":"Grand Slam"},
        {"name":"US Open","dates":"Aug 24–Sep 7","startDate":"2026-08-24","endDate":"2026-09-07","location":"New York","surface":"Hard","category":"Grand Slam"},
        {"name":"Indian Wells","dates":"Mar 5–16","startDate":"2026-03-05","endDate":"2026-03-16","location":"Indian Wells","surface":"Hard","category":"WTA 1000"},
        {"name":"Miami Open","dates":"Mar 19–30","startDate":"2026-03-19","endDate":"2026-03-30","location":"Miami","surface":"Hard","category":"WTA 1000"},
        {"name":"Madrid Open","dates":"Apr 23–May 4","startDate":"2026-04-23","endDate":"2026-05-04","location":"Madrid","surface":"Clay","category":"WTA 1000"},
        {"name":"Italian Open (Rome)","dates":"May 6–17","startDate":"2026-05-06","endDate":"2026-05-17","location":"Rome","surface":"Clay","category":"WTA 1000"},
        {"name":"Bad Homburg/Berlin","dates":"Jun 16–22","startDate":"2026-06-16","endDate":"2026-06-22","location":"Germany","surface":"Grass","category":"WTA 500"},
        {"name":"Eastbourne","dates":"Jun 21–28","startDate":"2026-06-21","endDate":"2026-06-28","location":"Eastbourne","surface":"Grass","category":"WTA 500"},
        {"name":"Canadian Open (Toronto)","dates":"Jul 24–Aug 3","startDate":"2026-07-24","endDate":"2026-08-03","location":"Toronto","surface":"Hard","category":"WTA 1000"},
        {"name":"Cincinnati","dates":"Aug 6–17","startDate":"2026-08-06","endDate":"2026-08-17","location":"Cincinnati","surface":"Hard","category":"WTA 1000"},
        {"name":"Beijing","dates":"Sep 22–Oct 5","startDate":"2026-09-22","endDate":"2026-10-05","location":"Beijing","surface":"Hard","category":"WTA 1000"},
        {"name":"WTA Finals","dates":"Oct 26–Nov 2","startDate":"2026-10-26","endDate":"2026-11-02","location":"Riyadh","surface":"Indoor Hard","category":"WTA Finals"},
    ]

    for ev in ATP_2026:
        ev["active"] = _active(ev["startDate"], ev["endDate"])
        ev["status"] = _status(ev["startDate"], ev["endDate"])
    for ev in WTA_2026:
        ev["active"] = _active(ev["startDate"], ev["endDate"])
        ev["status"] = _status(ev["startDate"], ev["endDate"])

    result: dict = {"atp": ATP_2026, "wta": WTA_2026}

    # Also try ESPN for live schedule supplement
    for tour, path in [("atp","tennis/schedule"),("wta","tennis/schedule/_/type/wta")]:
        try:
            soup = fetch_html(f"https://www.espn.com/{path}")
            if not soup: continue
            espn_events = []
            for row in soup.select("tr.Table__TR"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    espn_events.append({
                        "tournament": cells[0].get_text(strip=True),
                        "surface":    cells[1].get_text(strip=True) if len(cells) > 1 else "",
                        "dates":      cells[2].get_text(strip=True) if len(cells) > 2 else "",
                    })
            if espn_events:
                result[f"{tour}_espn"] = espn_events
        except Exception as exc:
            log(f"Tennis full schedule {tour}: {exc}", "WARN")

    log(f"Tennis calendar: {len(ATP_2026)} ATP, {len(WTA_2026)} WTA events")
    return result

# ── Roland Garros ─────────────────────────────────────────────────────────────
# Clay specialists that get +0.05 Elo surface bonus
_CLAY_SPECIALISTS: set = {
    "Novak Djokovic", "Rafael Nadal", "Carlos Alcaraz", "Casper Ruud",
    "Jannik Sinner", "Stefanos Tsitsipas", "Holger Rune", "Andrey Rublev",
    "Lorenzo Musetti", "Grigor Dimitrov", "Alexander Zverev", "Hubert Hurkacz",
    "Iga Swiatek", "Marketa Vondrousova", "Barbora Krejcikova", "Elena Rybakina",
    "Coco Gauff", "Aryna Sabalenka", "Simona Halep", "Petra Kvitova",
}

def _elo_win_prob(elo_a: float, elo_b: float,
                  player_a: str = "", player_b: str = "") -> float:
    """Win probability for player A vs player B using Elo formula.
    Applies clay surface adjustment (+0.05 raw prob) for known specialists."""
    prob = 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))
    clay_adj = 0.0
    if player_a in _CLAY_SPECIALISTS: clay_adj += 0.025
    if player_b in _CLAY_SPECIALISTS: clay_adj -= 0.025
    return min(0.97, max(0.03, prob + clay_adj))

def fetch_roland_garros() -> dict:
    """Fetch Roland Garros 2026 data: ESPN scoreboard, draws, and TennisAbstract Elo bets."""
    log("Roland Garros 2026…")
    result: dict = {
        "atpMatches": [], "wtaMatches": [],
        "atpElo": [], "wtaElo": [],
        "draw": {"atp": [], "wta": []},
        "tournament": {"name": "Roland Garros 2026", "surface": "Clay", "location": "Paris"},
        "bets": [],
        "fetchedAt": TODAY_ISO,
    }

    # 1. ESPN tennis scoreboard
    try:
        data = fetch_json("https://site.api.espn.com/apis/site/v2/sports/tennis/scoreboard")
        for ev in (data or {}).get("events") or []:
            comp    = (ev.get("competitions") or [{}])[0]
            players = comp.get("competitors") or []
            p1  = (players[0].get("athlete") or {}).get("displayName", "TBD") if players else "TBD"
            p2  = (players[1].get("athlete") or {}).get("displayName", "TBD") if len(players)>1 else "TBD"
            st  = comp.get("status", {})
            state = st.get("type", {}).get("state", "pre")
            tour_val = ""
            for note_obj in (comp.get("notes") or []):
                t = note_obj.get("headline", "")
                if t: tour_val = t; break
            entry = {
                "player1": p1, "player2": p2,
                "state": state,
                "score1": players[0].get("score","") if players else "",
                "score2": players[1].get("score","") if len(players)>1 else "",
                "statusText": st.get("type",{}).get("shortDetail",""),
                "tournament": (comp.get("venue") or {}).get("fullName","") or tour_val,
                "date": ev.get("date",""),
            }
            # Classify ATP vs WTA by league/gender metadata
            is_wta = any("wta" in str(v).lower() for v in ev.values())
            if is_wta:
                result["wtaMatches"].append(entry)
            else:
                result["atpMatches"].append(entry)
    except Exception as exc:
        log(f"Roland Garros ESPN scoreboard: {exc}", "WARN")

    # 2. TennisAbstract Elo (top 50 for bet generation)
    atp_elo_list = fetch_tennis_elo("atp")[:50]
    wta_elo_list = fetch_tennis_elo("wta")[:50]
    result["atpElo"] = atp_elo_list
    result["wtaElo"] = wta_elo_list

    # 3. Generate Roland Garros R1 bets using Elo clay model
    elo_map_atp: dict[str, float] = {p["name"]: float(p.get("eloClay") or p.get("elo") or 1500)
                                      for p in atp_elo_list}
    elo_map_wta: dict[str, float] = {p["name"]: float(p.get("eloClay") or p.get("elo") or 1500)
                                      for p in wta_elo_list}

    all_matches = result["atpMatches"] + result["wtaMatches"]
    for match in all_matches:
        p1, p2 = match.get("player1",""), match.get("player2","")
        if not p1 or not p2 or p1 == "TBD" or p2 == "TBD": continue
        # Determine ATP vs WTA elo map
        elo_map = elo_map_atp if match in result["atpMatches"] else elo_map_wta
        elo_p1 = elo_map.get(p1, 1500.0)
        elo_p2 = elo_map.get(p2, 1500.0)
        prob = _elo_win_prob(elo_p1, elo_p2, p1, p2)
        # Implied market prob (assume -120 line for favourite as baseline)
        # Only emit if we have strong edge (prob > 65% and would be EV > 4% at -120)
        if prob > 0.65:
            fav_dec = 1.833  # -120 implied decimal
            ev_pct = round((prob * fav_dec - 1) * 100, 1)
            if ev_pct > 4.0:
                result["bets"].append({
                    "sport": "TENNIS",
                    "game":  f"{p1} vs {p2}",
                    "pick":  f"{p1} ML",
                    "prob":  round(prob * 100, 1),
                    "ev":    ev_pct,
                    "evGrade": _ev_grade(ev_pct),
                    "confidence": _confidence(prob, ev_pct, 1),
                    "ml":    "-120",
                    "grade": "LOCK" if prob > 0.72 else "GOOD",
                    "note":  f"Clay Elo: {p1} {elo_p1:.0f} vs {p2} {elo_p2:.0f}",
                    "date":  TODAY_ISO,
                    "tour":  "ATP" if match in result["atpMatches"] else "WTA",
                    "surface": "Clay",
                })

    log(f"Roland Garros: {len(result['atpMatches'])} ATP, {len(result['wtaMatches'])} WTA, {len(result['bets'])} bets")
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# F1
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_f1() -> dict:
    result: dict = {"schedule":[], "driverStandings":[], "constructorStandings":[], "nextRace":None}
    year = NOW_MT.year

    # Ergast schedule (short timeout — site often slow/down)
    try:
        data  = fetch_json(f"https://api.jolpi.ca/ergast/f1/{year}.json?limit=25", timeout=6)
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
        data = fetch_json(f"https://api.jolpi.ca/ergast/f1/{year}/driverStandings.json", timeout=6)
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
        data = fetch_json(f"https://api.jolpi.ca/ergast/f1/{year}/constructorStandings.json", timeout=6)
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

def fetch_f1_data() -> dict:
    """Fetch comprehensive F1 data: ESPN scoreboard/standings + Ergast.
    Returns nextRace, driverStandings, constructorStandings, recentResults,
    qualifyingGrid, raceBets."""
    log("F1 comprehensive data (ESPN + Ergast)…")
    result: dict = {
        "nextRace": None,
        "driverStandings": [],
        "constructorStandings": [],
        "recentResults": [],
        "qualifyingGrid": [],
        "raceBets": [],
        "schedule": [],
        "fetchedAt": TODAY_ISO,
    }

    # ESPN F1 scoreboard
    try:
        sb = fetch_json("https://site.api.espn.com/apis/site/v2/sports/racing/f1/scoreboard")
        for ev in (sb or {}).get("events") or []:
            comp  = (ev.get("competitions") or [{}])[0]
            comps = comp.get("competitors") or []
            st    = ev.get("status") or {}
            state = (st.get("type") or {}).get("state", "pre")
            entry = {
                "id":      ev.get("id",""),
                "name":    ev.get("name",""),
                "date":    ev.get("date",""),
                "state":   state,
                "results": [],
            }
            for c in comps[:10]:
                athlete = (c.get("athlete") or c.get("team") or {})
                entry["results"].append({
                    "pos":  c.get("order") or c.get("position",""),
                    "name": athlete.get("displayName","") or athlete.get("name",""),
                    "team": (c.get("team") or {}).get("displayName",""),
                    "time": c.get("displayValue",""),
                })
            if state == "pre" and result["nextRace"] is None:
                result["nextRace"] = {"name": ev.get("name",""), "date": ev.get("date",""),
                                       "shortName": ev.get("shortName",""), "id": ev.get("id","")}
            if state == "post":
                result["recentResults"].append(entry)
                # Try to get qualifying grid from same event
                for note_obj in (comp.get("notes") or []):
                    h = note_obj.get("headline","")
                    if "qual" in h.lower() or "grid" in h.lower():
                        entry["qualNote"] = h
        # Qualifying grid: check if scoreboard has a separate qualifying event
        for ev in (sb or {}).get("events") or []:
            if "qualifying" in str(ev.get("name","")).lower():
                comp  = (ev.get("competitions") or [{}])[0]
                for c in (comp.get("competitors") or [])[:10]:
                    athlete = (c.get("athlete") or c.get("team") or {})
                    result["qualifyingGrid"].append({
                        "pos":  c.get("order") or c.get("position",""),
                        "name": athlete.get("displayName","") or athlete.get("name",""),
                        "team": (c.get("team") or {}).get("displayName",""),
                        "time": c.get("displayValue",""),
                    })
    except Exception as exc:
        log(f"F1 ESPN scoreboard: {exc}", "WARN")

    # ESPN F1 standings
    try:
        st_data = fetch_json("https://site.api.espn.com/apis/site/v2/sports/racing/f1/standings")
        for entry in (st_data or {}).get("standings", {}).get("entries") or []:
            stats = {s.get("name",""): s.get("displayValue","") for s in (entry.get("stats") or [])}
            ath = entry.get("athlete") or {}
            ctor = entry.get("team") or {}
            result["driverStandings"].append({
                "pos":   stats.get("rank",""),
                "name":  ath.get("displayName",""),
                "code":  ath.get("abbreviation",""),
                "team":  ctor.get("displayName","") or ctor.get("abbreviation",""),
                "pts":   stats.get("points",""),
                "wins":  stats.get("wins","0"),
            })
    except Exception as exc:
        log(f"F1 ESPN standings: {exc}", "WARN")

    # Fall back to Ergast if ESPN standings is empty
    if not result["driverStandings"]:
        ergast = fetch_f1()
        result["driverStandings"]     = ergast.get("driverStandings", [])
        result["constructorStandings"] = ergast.get("constructorStandings", [])
        if not result["schedule"]:
            result["schedule"]  = ergast.get("schedule", [])
        if not result["nextRace"]:
            result["nextRace"]  = ergast.get("nextRace")
    else:
        # Also grab constructor standings and schedule from Ergast
        try:
            ergast = fetch_f1()
            result["constructorStandings"] = ergast.get("constructorStandings", [])
            result["schedule"]  = ergast.get("schedule", [])
            if not result["nextRace"]:
                result["nextRace"] = ergast.get("nextRace")
        except Exception as exc:
            log(f"F1 Ergast fallback: {exc}", "WARN")

    # Generate race bets from championship standings + pole position model
    standings = result["driverStandings"]
    if standings and result["nextRace"]:
        race_name = result["nextRace"].get("name", "Next Race")
        qual_grid = result["qualifyingGrid"]
        # Pole sitter wins ~35% of races
        pole = qual_grid[0] if qual_grid else None
        if pole:
            pole_name = pole.get("name", "")
            # Adjust by championship position
            champ_pos = next((int(s.get("pos",99)) for s in standings
                              if s.get("name","") == pole_name), 10)
            pole_prob = 0.35 * (1.0 + max(0, (10 - champ_pos)) * 0.02)
            pole_prob = min(0.55, pole_prob)
            ev_pct = round((pole_prob * 2.50 - 1) * 100, 1)  # assume +150 winner market
            if ev_pct > 0:
                result["raceBets"].append({
                    "sport":      "F1",
                    "game":       race_name,
                    "pick":       f"{pole_name} Race Winner",
                    "prob":       round(pole_prob * 100, 1),
                    "ev":         ev_pct,
                    "evGrade":    _ev_grade(ev_pct),
                    "confidence": _confidence(pole_prob, ev_pct, 2),
                    "ml":         "+150",
                    "grade":      "GOOD" if ev_pct > 4 else "INFO",
                    "note":       f"Pole position · P{champ_pos} in championship",
                    "date":       TODAY_ISO,
                })
        # Top-3 finish bets for P2/P3 in championship if strong
        for i, drv in enumerate(standings[:3]):
            pos = int(str(drv.get("pos","99")))
            if pos > 3: continue
            prob = max(0.50, 0.70 - pos * 0.08)
            ev_pct = round((prob * 1.60 - 1) * 100, 1)  # assume -167 podium
            if ev_pct > 2:
                result["raceBets"].append({
                    "sport":      "F1",
                    "game":       race_name,
                    "pick":       f"{drv.get('name','')} Podium Finish",
                    "prob":       round(prob * 100, 1),
                    "ev":         ev_pct,
                    "evGrade":    _ev_grade(ev_pct),
                    "confidence": _confidence(prob, ev_pct, 1),
                    "ml":         "-167",
                    "grade":      "INFO",
                    "note":       f"P{pos} championship · strong form",
                    "date":       TODAY_ISO,
                })

    log(f"F1 comprehensive: {len(result['driverStandings'])} drivers, "
        f"{len(result['qualifyingGrid'])} grid, {len(result['raceBets'])} bets")
    return result

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

def fetch_f1_unchained() -> dict:
    """F1 Unchained track guides — overtaking spots, DRS zones, racing lines."""
    log("F1 Unchained track guide…")
    result: dict = {"tracks": {}, "source": "unchained"}
    try:
        soup = fetch_html("https://www.unchainedmediainc.com/track-guide")
        if not soup:
            return result
        articles = soup.find_all(["article","div"], class_=re.compile(r"track|guide|circuit", re.I))
        for a in articles[:20]:
            title_el = a.find(["h1","h2","h3","h4"])
            if not title_el: continue
            title = title_el.get_text(strip=True)
            text_el = a.find("p")
            text = text_el.get_text(strip=True) if text_el else ""
            if title and len(title) < 60:
                result["tracks"][title] = {"description": text[:300]}
        vlog(f"  F1 Unchained: {len(result['tracks'])} tracks")
    except Exception as e:
        log(f"F1 Unchained error: {e}", "WARN")
    return result

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

def fetch_ncaa_baseball() -> dict:
    """Fetch NCAA Men's Baseball scoreboard, rankings, standings, 14-day schedule from ESPN."""
    log("NCAA Baseball scoreboard…")
    result = {"today": [], "rankings": [], "schedule": [], "weekSchedule": [], "standings": [], "conferenceStandings": {}}
    try:
        data = fetch_json(f"https://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/scoreboard?dates={TODAY_ET}&limit=25")
        for ev in (data or {}).get("events", []):
            g = _espn_game(ev, "NCAAB")
            if g: result["today"].append(g)
        log(f"NCAA Baseball today: {len(result['today'])} games")
    except Exception as e: log(f"NCAA Baseball scoreboard: {e}", "WARN")
    try:
        rdata = fetch_json("https://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/rankings")
        for poll in ((rdata or {}).get("rankings") or [])[:1]:
            for r in (poll.get("ranks") or [])[:25]:
                t = r.get("team", {})
                result["rankings"].append({
                    "rank": r.get("current", 0),
                    "team": t.get("displayName", ""),
                    "abbr": t.get("abbreviation", ""),
                    "record": r.get("recordSummary", ""),
                    "logo": (t.get("logos") or [{}])[0].get("href","") if t.get("logos") else "",
                })
        log(f"NCAA Baseball rankings: {len(result['rankings'])}")
    except Exception as e: log(f"NCAA Baseball rankings: {e}", "WARN")
    try:
        # Conference standings
        sdata = fetch_json("https://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/standings")
        for conf in ((sdata or {}).get("children") or []):
            cname = conf.get("name","")
            entries = []
            for entry in (conf.get("standings",{}).get("entries") or []):
                t = entry.get("team",{})
                stats = {s["name"]:s.get("displayValue","") for s in entry.get("stats",[])}
                entries.append({
                    "team": t.get("displayName",""), "abbr": t.get("abbreviation",""),
                    "w": stats.get("wins","0"), "l": stats.get("losses","0"),
                    "pct": stats.get("winPercent",""), "confW": stats.get("conferenceWins",""),
                    "confL": stats.get("conferenceLosses",""),
                })
            if entries:
                result["conferenceStandings"][cname] = entries
                result["standings"].extend(entries)
        log(f"NCAA Baseball conf standings: {len(result['conferenceStandings'])} conferences")
    except Exception as e: log(f"NCAA Baseball standings: {e}", "WARN")
    try:
        # 14-day schedule
        from datetime import datetime, timedelta
        for i in range(14):
            d = (datetime.now() + timedelta(days=i)).strftime("%Y%m%d")
            sdata = fetch_json(f"https://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/scoreboard?dates={d}&limit=15")
            for ev in (sdata or {}).get("events", [])[:8]:
                comp = (ev.get("competitions") or [{}])[0]
                comps = comp.get("competitors") or []
                h = next((c for c in comps if c.get("homeAway")=="home"), {})
                a = next((c for c in comps if c.get("homeAway")=="away"), {})
                ht = h.get("team") or {}; at = a.get("team") or {}
                entry = {
                    "date": d,
                    "home": ht.get("displayName",""), "homeAbbr": ht.get("abbreviation",""),
                    "homeRecord": (h.get("records") or [{}])[0].get("summary","") if h.get("records") else "",
                    "away": at.get("displayName",""), "awayAbbr": at.get("abbreviation",""),
                    "awayRecord": (a.get("records") or [{}])[0].get("summary","") if a.get("records") else "",
                    "state": ev.get("status",{}).get("type",{}).get("state","pre"),
                    "homeScore": h.get("score",""), "awayScore": a.get("score",""),
                    "venue": (comp.get("venue") or {}).get("fullName",""),
                    "network": (comp.get("broadcasts") or [{}])[0].get("names",[""])[0] if comp.get("broadcasts") else "",
                }
                result["weekSchedule"].append(entry)
                if i < 7:
                    result["schedule"].append(entry)
            time.sleep(0.15)
        log(f"NCAA Baseball 14d schedule: {len(result['weekSchedule'])} games")
    except Exception as e: log(f"NCAA Baseball schedule: {e}", "WARN")
    return result


def fetch_wnba() -> dict:
    """Fetch WNBA scoreboard, standings, schedule from ESPN."""
    log("WNBA scoreboard…")
    result = {"today": [], "standings": {}, "schedule": []}
    try:
        data = fetch_json(f"https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard?dates={TODAY_ET}&limit=15")
        for ev in (data or {}).get("events", []):
            g = _espn_game(ev, "WNBA")
            if g: result["today"].append(g)
        log(f"WNBA today: {len(result['today'])} games")
    except Exception as e: log(f"WNBA scoreboard: {e}", "WARN")
    try:
        sdata = fetch_json("https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/standings")
        for conf in ((sdata or {}).get("children") or []):
            cname = conf.get("name","")
            for entry in (conf.get("standings",{}).get("entries") or []):
                t = entry.get("team",{})
                stats = {s["name"]:s.get("displayValue","") for s in entry.get("stats",[])}
                result["standings"][t.get("abbreviation","")] = {
                    "name": t.get("displayName",""), "conf": cname,
                    "w": stats.get("wins","0"), "l": stats.get("losses","0"),
                    "pct": stats.get("winPercent",""),
                }
    except Exception as e: log(f"WNBA standings: {e}", "WARN")
    try:
        from datetime import datetime, timedelta
        for i in range(7):
            d = (datetime.now() + timedelta(days=i)).strftime("%Y%m%d")
            sdata = fetch_json(f"https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard?dates={d}&limit=8")
            for ev in (sdata or {}).get("events", [])[:4]:
                comp = (ev.get("competitions") or [{}])[0]
                comps = comp.get("competitors") or []
                h = next((c for c in comps if c.get("homeAway")=="home"), {})
                a = next((c for c in comps if c.get("homeAway")=="away"), {})
                odds = (comp.get("odds") or [{}])[0]
                result["schedule"].append({
                    "date": d,
                    "home": (h.get("team") or {}).get("abbreviation",""),
                    "away": (a.get("team") or {}).get("abbreviation",""),
                    "homeName": (h.get("team") or {}).get("displayName",""),
                    "awayName": (a.get("team") or {}).get("displayName",""),
                    "homeML": (odds.get("homeTeamOdds") or {}).get("moneyLine"),
                    "awayML": (odds.get("awayTeamOdds") or {}).get("moneyLine"),
                    "state": ev.get("status",{}).get("type",{}).get("state","pre"),
                })
            time.sleep(0.2)
    except Exception as e: log(f"WNBA schedule: {e}", "WARN")
    return result


def fetch_pwhl() -> dict:
    """Fetch PWHL scoreboard and standings from ESPN."""
    log("PWHL data…")
    result = {"today": [], "standings": {}, "schedule": []}
    try:
        data = fetch_json(f"https://site.api.espn.com/apis/site/v2/sports/hockey/pwhl/scoreboard?dates={TODAY_ET}&limit=10")
        for ev in (data or {}).get("events", []):
            g = _espn_game(ev, "PWHL")
            if g: result["today"].append(g)
    except Exception as e: log(f"PWHL scoreboard: {e}", "WARN")
    try:
        sdata = fetch_json("https://site.api.espn.com/apis/site/v2/sports/hockey/pwhl/standings")
        for conf in ((sdata or {}).get("children") or []):
            for entry in (conf.get("standings",{}).get("entries") or []):
                t = entry.get("team",{})
                stats = {s["name"]:s.get("displayValue","") for s in entry.get("stats",[])}
                result["standings"][t.get("abbreviation","")] = {
                    "name": t.get("displayName",""),
                    "w": stats.get("wins","0"), "l": stats.get("losses","0"),
                    "otl": stats.get("otLosses","0"), "pts": stats.get("points","0"),
                }
    except Exception as e: log(f"PWHL standings: {e}", "WARN")
    try:
        from datetime import datetime, timedelta
        for i in range(7):
            d = (datetime.now() + timedelta(days=i)).strftime("%Y%m%d")
            sdata = fetch_json(f"https://site.api.espn.com/apis/site/v2/sports/hockey/pwhl/scoreboard?dates={d}&limit=5")
            for ev in (sdata or {}).get("events",[])[:3]:
                comp=(ev.get("competitions") or [{}])[0]; comps=comp.get("competitors") or []
                h=next((c for c in comps if c.get("homeAway")=="home"),{}); a=next((c for c in comps if c.get("homeAway")=="away"),{})
                result["schedule"].append({"date":d,"home":(h.get("team") or {}).get("abbreviation",""),"away":(a.get("team") or {}).get("abbreviation",""),"homeName":(h.get("team") or {}).get("displayName",""),"awayName":(a.get("team") or {}).get("displayName",""),"state":ev.get("status",{}).get("type",{}).get("state","pre")})
            time.sleep(0.2)
    except Exception as e: log(f"PWHL schedule: {e}", "WARN")
    return result

def fetch_week_schedule(sport_path: str, sport_key: str, limit_per_day: int = 8) -> list[dict]:
    """Fetch 7-day schedule for any ESPN sport."""
    from datetime import datetime, timedelta
    schedule = []
    for i in range(7):
        d = (datetime.now() + timedelta(days=i)).strftime("%Y%m%d")
        try:
            data = fetch_json(f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard?dates={d}&limit={limit_per_day}")
            for ev in (data or {}).get("events", [])[:limit_per_day]:
                comp = (ev.get("competitions") or [{}])[0]
                comps = comp.get("competitors") or []
                h = next((c for c in comps if c.get("homeAway")=="home"), {})
                a = next((c for c in comps if c.get("homeAway")=="away"), {})
                odds = (comp.get("odds") or [{}])[0]
                schedule.append({
                    "date": d, "sport": sport_key,
                    "home": (h.get("team") or {}).get("abbreviation",""),
                    "away": (a.get("team") or {}).get("abbreviation",""),
                    "homeName": (h.get("team") or {}).get("displayName",""),
                    "awayName": (a.get("team") or {}).get("displayName",""),
                    "time": ev.get("date",""),
                    "network": ((comp.get("broadcasts") or [{}])[0].get("names") or [""])[0],
                    "homeML": (odds.get("homeTeamOdds") or {}).get("moneyLine"),
                    "awayML": (odds.get("awayTeamOdds") or {}).get("moneyLine"),
                    "ou": odds.get("overUnder"),
                    "state": ev.get("status",{}).get("type",{}).get("state","pre"),
                    "venue": (comp.get("venue") or {}).get("fullName",""),
                })
            time.sleep(0.15)
        except Exception as e:
            log(f"Week schedule {sport_key} {d}: {e}", "WARN")
    return schedule


def fetch_sports_news() -> dict:
    """Fetch latest news articles for all sports from ESPN."""
    news: dict = {}
    sport_map = {
        "mlb":    "baseball/mlb",
        "nhl":    "hockey/nhl",
        "nba":    "basketball/nba",
        "wnba":   "basketball/wnba",
        "ncaab":  "baseball/college-baseball",
        "tennis": "tennis/atp",
        "f1":     "racing/f1",
        "football": "football/nfl",
    }
    for sport_key, espn_path in sport_map.items():
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/{espn_path}/news"
            articles = (fetch_json(url) or {}).get("articles", [])
            items = []
            for a in articles[:20]:
                title = a.get("headline", "")
                if not title: continue
                pub = a.get("published", "")
                items.append({
                    "headline": title,
                    "summary": (a.get("description") or a.get("story",""))[:250],
                    "published": pub,
                    "date": pub[:10] if pub else TODAY_ISO,
                    "link": a.get("links", {}).get("web", {}).get("href", ""),
                    "image": ((a.get("images") or [{}])[0]).get("url",""),
                    "sport": sport_key,
                    "category": a.get("categories", [{}])[0].get("description","") if a.get("categories") else "",
                })
            news[sport_key] = items[:15]
            log(f"News {sport_key}: {len(items)} articles")
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

def _pyth_win_pct(rs: float, ra: float, exp: float = 1.83) -> float:
    """Pythagorean win expectation from runs scored/allowed."""
    try:
        if rs + ra == 0: return 0.5
        return rs**exp / (rs**exp + ra**exp)
    except: return 0.5

def _estimate_prob_from_standings(home: str, away: str, standings: dict,
                                   hfa: float = 0.04) -> tuple[float, float, int]:
    """
    Estimate win probabilities from standings when no book odds available.
    Uses Pythagorean expectation (RS/RA) + home field advantage.
    Returns (home_prob, away_prob, ml_estimate) — ml_estimate for home.
    """
    hs = standings.get(home, {})
    as_ = standings.get(away, {})
    if not hs or not as_:
        return 0.5 + hfa, 0.5 - hfa, -110
    try:
        h_pyth = _pyth_win_pct(float(hs.get("rs", 200)), float(hs.get("ra", 200)))
        a_pyth = _pyth_win_pct(float(as_.get("rs", 200)), float(as_.get("ra", 200)))
        # Log5 formula: P(A beats B) = (A - A*B) / (A + B - 2*A*B)
        if h_pyth + a_pyth == 0: return 0.54, 0.46, -120
        h_prob_raw = (h_pyth - h_pyth * a_pyth) / (h_pyth + a_pyth - 2 * h_pyth * a_pyth)
        h_prob = min(0.82, max(0.18, h_prob_raw + hfa))
        a_prob = 1 - h_prob
        # Convert to American ML
        if h_prob >= 0.5:
            ml = -int(round(h_prob / (1 - h_prob) * 100))
        else:
            ml = int(round((1 - h_prob) / h_prob * 100))
        return h_prob, a_prob, ml
    except:
        return 0.54, 0.46, -120

def calculate_best_bets(
    nba_today: list, mlb_today: list, nhl_today: list,
    weather: dict, mp: dict | None = None, nhl_edge: dict | None = None,
    nhl_props: list | None = None, nhl_trends: list | None = None,
    mlb_sabre: dict | None = None, best_odds: dict | None = None,
    nba_adv: dict | None = None, mlb_standings: dict | None = None,
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

    # NBA advanced stats helper
    _nba_adv = nba_adv or {}

    def _nba_net_rtg_adj(home: str, away: str) -> tuple[float, str]:
        """
        Return (home_prob_adj, note) from net rating differential.
        Net Rating gap of 10 pts → ~4% win probability swing.
        """
        ht = _nba_adv.get(home, {}); at = _nba_adv.get(away, {})
        if not ht or not at: return 0.0, ""
        h_net = ht.get("net_rtg", 0.0)
        a_net = at.get("net_rtg", 0.0)
        diff  = h_net - a_net
        adj   = diff * 0.004       # 10pt gap → +4% for home
        parts = []
        if abs(adj) > 0.005:
            parts.append(f"NetRtg: {home} {h_net:+.1f} / {away} {a_net:+.1f}")
        h_efg = ht.get("efg_pct", 0); a_efg = at.get("efg_pct", 0)
        efg_adj = (h_efg - a_efg) * 0.5  # 2% eFG gap → ~1% prob swing
        if abs(efg_adj) > 0.005:
            adj += efg_adj
            parts.append(f"eFG%: {home} {h_efg*100:.1f} / {away} {a_efg*100:.1f}")
        return adj, "  ".join(parts)

    # NBA moneylines
    for g in nba_today:
        if g.get("state") != "pre": continue
        hml, aml  = g.get("homeML"), g.get("awayML")
        hprob_raw, aprob_raw = _ml_to_prob(hml), _ml_to_prob(aml)
        home, away = g.get("home",""), g.get("away","")
        game_str   = f"{away} @ {home}"
        adv_adj, adv_note = _nba_net_rtg_adj(home, away)
        extra_sig  = 1 if adv_note else 0
        hprob = max(0.05, min(0.95, hprob_raw + adv_adj)) if hprob_raw else None
        aprob = max(0.05, min(0.95, aprob_raw - adv_adj)) if aprob_raw else None
        if hprob and hprob > 0.62:
            add("NBA", game_str, f"{home} ML {hml}", hprob, hml,
                "LOCK" if hprob>0.67 else "GOOD",
                note=(g.get("seriesNote","") + ("  " + adv_note if adv_note else "")).strip(),
                extra_signals=extra_sig)
        elif aprob and aprob > 0.62:
            add("NBA", game_str, f"{away} ML {aml}", aprob, aml,
                "LOCK" if aprob>0.67 else "GOOD",
                note=(g.get("seriesNote","") + ("  " + adv_note if adv_note else "")).strip(),
                extra_signals=extra_sig)
        # O/U info
        ou = g.get("ou")
        if ou and hml and aml:
            # Pace-adjusted O/U lean
            h_pace = _nba_adv.get(home, {}).get("pace", 0)
            a_pace = _nba_adv.get(away, {}).get("pace", 0)
            avg_pace = (h_pace + a_pace) / 2 if h_pace and a_pace else 0
            pace_note = f"Pace: {home} {h_pace:.1f} / {away} {a_pace:.1f}" if avg_pace else ""
            picks.append({
                "sport":"NBA","game":game_str,"pick":f"O/U {ou}","prob":52.0,
                "ev":0.0,"evGrade":"D","confidence":52,"ml":"-110","grade":"INFO",
                "note":f"Line: {home} {hml} / {away} {aml}" + (f"  {pace_note}" if pace_note else ""),
                "date":TODAY_ISO,
            })

    # ── MLB sabermetric lookup helpers ──────────────────────────────────────
    _sabre = mlb_sabre or {}
    _best  = best_odds or {}

    # Build abbr→full-name reverse map from whatever keys exist in _sabre
    # Sabre data may be keyed by full name ("Tampa Bay Rays") or abbr ("TB")
    _ABBR_TO_FULL: dict[str, str] = {v: k for k, v in _TEAM_NAME_TO_ABBR.items()}

    def _sabre_lookup(abbr: str) -> dict:
        """Look up sabre stats by ESPN abbr, tolerating full-name or abbr keys."""
        d = _sabre.get(abbr)
        if d: return d
        full = _ABBR_TO_FULL.get(abbr, "")
        return _sabre.get(full, {})

    def _sabre_edge(home: str, away: str) -> tuple[float, float, str]:
        """
        Return (home_adj, away_adj, note) capped at ±4% total.
        Uses OPS+ (offense) and ERA- (pitching) — both scaled to 100 = league avg.
        OPS+ typical range: 70–140. ERA- typical range: 65–140.
        Values outside these ranges are treated as data errors and clamped.
        """
        hs = _sabre_lookup(home); as_ = _sabre_lookup(away)
        if not hs and not as_:
            return 0.0, 0.0, ""

        def _clamp_ops(v) -> float:
            try: v = float(v or 100)
            except: v = 100.0
            return max(50.0, min(160.0, v))  # clip outliers

        def _clamp_era(v) -> float:
            try: v = float(v or 100)
            except: v = 100.0
            return max(50.0, min(160.0, v))  # clip outliers

        h_ops = _clamp_ops(hs.get("ops_plus", 100))
        a_ops = _clamp_ops(as_.get("ops_plus", 100))
        h_era = _clamp_era(hs.get("era_minus", 100))
        a_era = _clamp_era(as_.get("era_minus", 100))

        # 10pt OPS+ gap → ~1.5% win prob swing; 10pt ERA- gap → ~1% swing
        ops_adj = (h_ops - a_ops) * 0.0015
        era_adj = (a_era - h_era) * 0.001   # lower ERA- is better for pitching

        total = max(-0.04, min(0.04, ops_adj + era_adj))  # hard cap ±4%
        parts = []
        if abs(ops_adj) > 0.005:
            parts.append(f"OPS+: {home} {h_ops:.0f} / {away} {a_ops:.0f}")
        if abs(era_adj) > 0.005:
            parts.append(f"ERA-: {home} {h_era:.0f} / {away} {a_era:.0f}")
        note = "  ".join(parts)
        return total, -total, note

    _standings = mlb_standings or {}

    # MLB — wind-adjusted O/U + sabermetric ML model
    for g in mlb_today:
        if g.get("state") != "pre": continue
        home, away = g.get("home",""), g.get("away","")
        game_str   = f"{away} @ {home}"
        w          = weather.get(home,{})
        # Best available odds: Odds API (real book lines) → ESPN → estimated
        bk       = _best.get(f"{home}:{away}", {})
        hml      = bk.get("homeML") or g.get("homeML")
        aml      = bk.get("awayML") or g.get("awayML")
        ou       = bk.get("ou") or g.get("ou")
        book_src = bk.get("book", "")
        hbook    = bk.get("homeBook", book_src)
        abook    = bk.get("awayBook", book_src)
        # Fallback: estimate from standings when no book odds
        using_estimated_odds = False
        if hml is None and _standings:
            h_est, a_est, hml_est = _estimate_prob_from_standings(home, away, _standings)
            aml_est = (-int(round(a_est/(1-a_est)*100)) if a_est >= 0.5
                       else int(round((1-a_est)/a_est*100)))
            hml, aml = hml_est, aml_est
            using_estimated_odds = True
        # Wind-adjusted O/U
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
        # Independent model probability + sabermetric edge vs book odds
        # Step 1: Independent win probability from Pythagorean + Log5
        h_model, a_model, _ = _estimate_prob_from_standings(home, away, _standings)
        # Step 2: Sabermetric edge shifts the model probability
        h_adj, a_adj, sabre_note = _sabre_edge(home, away)
        h_model = max(0.10, min(0.90, h_model + h_adj))
        a_model = max(0.10, min(0.90, a_model + a_adj))
        extra_sig = 1 if sabre_note else 0
        real_odds = not using_estimated_odds and hml is not None
        est_note  = " [model est.]" if using_estimated_odds else (f" [{hbook}]" if hbook else "")

        # Step 3: EV = model_prob × book_decimal - 1
        # Positive when our model thinks team more likely to win than book implies
        if hml is not None:
            hdec = _ml_to_dec(hml)
            hev  = round(_ev(h_model, hdec) * 100, 1)
            # Fire when: model prob ≥ 53%, EV ≥ 1.5% with real odds / ≥ 3% with estimated
            ev_min = 1.5 if real_odds else 3.0
            if h_model >= 0.53 and hev >= ev_min:
                grade = "LOCK" if hev >= 8 else ("GOOD" if hev >= 4 else "LEAN")
                note_parts = []
                if sabre_note: note_parts.append(sabre_note)
                note_parts.append(f"model {h_model*100:.1f}% vs book {(_ml_to_prob(hml) or 0)*100:.1f}%")
                if est_note.strip(): note_parts.append(est_note.strip())
                add("MLB", game_str, f"{home} ML {hml}", h_model, hml,
                    grade, note="  ".join(note_parts), extra_signals=extra_sig)

        if aml is not None:
            adec = _ml_to_dec(aml)
            aev  = round(_ev(a_model, adec) * 100, 1)
            ev_min = 1.5 if real_odds else 3.0
            if a_model >= 0.53 and aev >= ev_min:
                grade = "LOCK" if aev >= 8 else ("GOOD" if aev >= 4 else "LEAN")
                book_n = f" [{abook}]" if abook and not using_estimated_odds else est_note.strip()
                note_parts = []
                if sabre_note: note_parts.append(sabre_note)
                note_parts.append(f"model {a_model*100:.1f}% vs book {(_ml_to_prob(aml) or 0)*100:.1f}%")
                if book_n: note_parts.append(book_n)
                add("MLB", game_str, f"{away} ML {aml}", a_model, aml,
                    grade, note="  ".join(note_parts), extra_signals=extra_sig)

    # NHL — moneyline + puck line + O/U (pre-game and live)
    mp_teams = (mp or {}).get("teams",{}) if mp else {}
    nhl_edge_teams = (nhl_edge or {}).get("teams",{}) if nhl_edge else {}
    for g in nhl_today:
        if g.get("state") not in ("FUT","PRE","LIVE","CRIT"): continue
        home, away  = g.get("home",""), g.get("away","")
        # Best odds: Odds API → ESPN fallback
        nhl_bk = _best.get(f"{home}:{away}", {})
        hml  = nhl_bk.get("homeML") or g.get("homeML")
        aml  = nhl_bk.get("awayML") or g.get("awayML")
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

        # PDO regression: PDO = sh% + sv% (league avg ≈ 1.000 in 5v5)
        # High PDO (>1.025) → likely to regress negatively; Low PDO (<0.975) → positive regression
        pdo_adj  = 0.0
        pdo_note = ""
        h_edge = nhl_edge_teams.get(home, {})
        a_edge = nhl_edge_teams.get(away, {})
        if h_edge and a_edge:
            h_sf60 = float(h_edge.get("sf60") or 0)
            h_gf60 = float(h_edge.get("gf60") or 0)
            h_sa60 = float(h_edge.get("sa60") or 0)
            h_ga60 = float(h_edge.get("ga60") or 0)
            a_sf60 = float(a_edge.get("sf60") or 0)
            a_gf60 = float(a_edge.get("gf60") or 0)
            a_sa60 = float(a_edge.get("sa60") or 0)
            a_ga60 = float(a_edge.get("ga60") or 0)
            # sh% = gf / sf (avoid div/0)
            h_sh = h_gf60 / h_sf60 if h_sf60 > 0 else 0.08
            a_sh = a_gf60 / a_sf60 if a_sf60 > 0 else 0.08
            # sv% = 1 - ga/sa (goalie; lower ga/sa = better)
            h_sv = 1 - (h_ga60 / h_sa60) if h_sa60 > 0 else 0.915
            a_sv = 1 - (a_ga60 / a_sa60) if a_sa60 > 0 else 0.915
            h_pdo = h_sh + h_sv
            a_pdo = a_sh + a_sv
            # PDO above 1.050 is unusually lucky; adjust model_home
            # Each 0.010 PDO above 1.025 reduces win prob by ~1.5%
            h_pdo_adj = -max(0, (h_pdo - 1.025)) * 1.5  # negative if home over-performing
            a_pdo_adj = -max(0, (a_pdo - 1.025)) * 1.5
            # Home benefiting from away's negative regression = positive adj for home
            pdo_adj = h_pdo_adj - a_pdo_adj
            pdo_adj = max(-0.06, min(0.06, pdo_adj))  # cap at ±6%
            if abs(pdo_adj) > 0.01:
                pdo_note = (f"PDO: {home} {h_pdo:.3f}{'↓' if h_pdo>1.025 else ''} / "
                            f"{away} {a_pdo:.3f}{'↓' if a_pdo>1.025 else ''}")
                xgf_edge += 1  # extra signal strength

        # Apply PDO adjustment to model probabilities
        model_home = min(0.80, max(0.20, model_home + pdo_adj))
        model_away = 1.0 - model_home
        if pdo_note:
            xgf_note = f"{xgf_note}  {pdo_note}"

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

    # ── NHL Player Props (from Linemate trends) ──────────────────────────────
    if nhl_trends:
        for trend in nhl_trends:
            player    = trend.get("player", "")
            category  = trend.get("category", "")
            direction = trend.get("direction", "neutral")
            l5_str    = trend.get("l5", "")
            l10_str   = trend.get("l10", "")
            if not player or not category:
                continue
            # Parse "X/Y" hit-rate strings
            def _parse_rate(s):
                m = re.match(r"(\d+)/(\d+)", s or "")
                return (int(m.group(1)), int(m.group(2))) if m else (0, 0)
            l5_hit, l5_tot  = _parse_rate(l5_str)
            l10_hit, l10_tot = _parse_rate(l10_str)
            # Score: require at least 4/5 or 7/10 hit rate to qualify
            strong_l5  = l5_tot >= 5  and l5_hit / l5_tot  >= 0.80
            strong_l10 = l10_tot >= 8 and l10_hit / l10_tot >= 0.70
            if not (strong_l5 or strong_l10):
                continue
            hit_rate   = (l5_hit / l5_tot) if l5_tot else (l10_hit / l10_tot if l10_tot else 0.5)
            bet_dir    = ("OVER" if direction in ("hot","up") else
                          "UNDER" if direction in ("cold","down") else
                          ("OVER" if hit_rate >= 0.8 else "UNDER"))
            grade      = "LOCK" if (strong_l5 and l5_hit == l5_tot) else "GOOD" if strong_l5 else "INFO"
            # Build note with trend streaks
            note_parts = []
            if l5_str:  note_parts.append(f"L5: {l5_str}")
            if l10_str: note_parts.append(f"L10: {l10_str}")
            if trend.get("lineMove"): note_parts.append(f"Line: {trend['lineMove']}")
            trend_note = "  ".join(note_parts) if note_parts else "Linemate trend"
            # Estimated prob from hit rate (regress to the mean slightly)
            prop_prob = max(0.52, min(0.85, hit_rate * 0.88 + 0.10))
            picks.append({
                "sport":      "NHL",
                "game":       player,
                "pick":       f"{bet_dir} {category}",
                "prob":       round(prop_prob * 100, 1),
                "ev":         round((prop_prob * 1.909 - 1) * 100, 1),  # assume -110
                "evGrade":    _ev_grade(round((prop_prob * 1.909 - 1) * 100, 1)),
                "confidence": _confidence(prop_prob, round((prop_prob * 1.909 - 1) * 100, 1), 1),
                "ml":         "-110",
                "grade":      grade,
                "note":       trend_note,
                "date":       TODAY_ISO,
                "betType":    "PROP",
                "propPlayer": player,
                "propStat":   category,
                "propDir":    bet_dir,
                "propHitRate": f"{l5_hit}/{l5_tot}" if l5_tot else f"{l10_hit}/{l10_tot}",
            })

    # ── BUG 2 FIX: Filter Linemate date-as-game garbage ─────────────────────
    # ── WNBA moneylines ──────────────────────────────────────────────────────
    wnba_games = (best_odds or {}).get("_wnba_today", [])
    for g in wnba_games:
        if g.get("state") != "pre": continue
        home, away = g.get("home",""), g.get("away","")
        game_str   = f"{away} @ {home}"
        hml, aml   = g.get("homeML"), g.get("awayML")
        hprob_raw, aprob_raw = _ml_to_prob(hml), _ml_to_prob(aml)
        if hprob_raw and hprob_raw > 0.60:
            add("WNBA", game_str, f"{home} ML {hml}", hprob_raw, hml, "GOOD",
                note=f"WNBA home advantage")
        if aprob_raw and aprob_raw > 0.60:
            add("WNBA", game_str, f"{away} ML {aml}", aprob_raw, aml, "GOOD",
                note=f"WNBA road value")

    # ── NCAA Baseball — top-25 ranked team picks ──────────────────────────────
    ncaa_games = (best_odds or {}).get("_ncaa_today", [])
    for g in ncaa_games:
        if g.get("state") != "pre": continue
        home, away = g.get("home",""), g.get("away","")
        game_str   = f"{away} @ {home}"
        hml, aml   = g.get("homeML"), g.get("awayML")
        hprob_raw  = _ml_to_prob(hml)
        aprob_raw  = _ml_to_prob(aml)
        if hprob_raw and hprob_raw > 0.62:
            add("NCAAB", game_str, f"{home} ML {hml}", hprob_raw, hml, "GOOD",
                note="NCAA Baseball — ranked home team")
        elif aprob_raw and aprob_raw > 0.62:
            add("NCAAB", game_str, f"{away} ML {aml}", aprob_raw, aml, "GOOD",
                note="NCAA Baseball — ranked away team")

    # Linemate scraper sometimes returns the date string (e.g. "12/11/25") as
    # the "game" field or propPlayer field.  Remove those entries.
    _date_like = re.compile(r"^\d{2}/\d{2}/\d{2,4}$")
    def _is_valid_pick(p: dict) -> bool:
        game_field = str(p.get("game", ""))
        if _date_like.match(game_field):
            return False
        # For PROP bets: propPlayer must exist and must not be a date string
        if p.get("betType") == "PROP" or p.get("propPlayer") is not None:
            player_field = str(p.get("propPlayer", ""))
            if not player_field or _date_like.match(player_field):
                return False
        return True
    picks = [p for p in picks if _is_valid_pick(p)]

    grade_order = {"LOCK":0,"GOOD":1,"INFO":2}
    picks.sort(key=lambda p: (grade_order.get(p["grade"],9), -p.get("confidence",0)))
    top = picks[:20]   # bumped cap to 20 to include room for props
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
        "roi":       compute_roi(history),
        "streak":    compute_streak(history),
    }

def compute_roi(history: list[dict]) -> dict:
    """ROI and PnL from settled bet history."""
    settled = [b for b in history if b.get("outcome") in ("win","loss","push")]
    if not settled:
        return {"roi": 0.0, "totalWagered": 0.0, "totalPnl": 0.0, "avgOdds": 0.0, "n": 0}
    wagered = sum(float(b.get("wager", 100)) for b in settled)
    pnl = sum(float(b.get("pnl") or 0) for b in settled)
    odds_sum = 0; odds_n = 0
    for b in settled:
        ml = b.get("ml") or b.get("line")
        try:
            dec = _ml_to_dec(float(ml))
            odds_sum += dec; odds_n += 1
        except Exception:
            pass
    return {
        "roi":          round(pnl / wagered * 100, 2) if wagered else 0.0,
        "totalWagered": round(wagered, 2),
        "totalPnl":     round(pnl, 2),
        "avgOdds":      round(odds_sum / odds_n, 3) if odds_n else 0.0,
        "n":            len(settled),
    }

def compute_streak(history: list[dict]) -> dict:
    """Current and longest win/loss streaks from settled history."""
    settled = sorted(
        [b for b in history if b.get("outcome") in ("win","loss")],
        key=lambda b: b.get("settledAt","") or b.get("date","")
    )
    if not settled:
        return {"current": 0, "direction": "W", "longestW": 0, "longestL": 0}
    cur = 1; cur_dir = "W" if settled[-1]["outcome"]=="win" else "L"
    for i in range(len(settled)-2, -1, -1):
        d = "W" if settled[i]["outcome"]=="win" else "L"
        if d == cur_dir: cur += 1
        else: break
    lw = ll = run = 0
    run_d = None
    for b in settled:
        d = "W" if b["outcome"]=="win" else "L"
        if d == run_d: run += 1
        else: run = 1; run_d = d
        if d == "W": lw = max(lw, run)
        else: ll = max(ll, run)
    return {"current": cur, "direction": cur_dir, "longestW": lw, "longestL": ll}

def surface_best_bets_for_day(best_bets: list[dict], n: int = 6) -> list[dict]:
    """Top N deduped picks by composite EV+confidence score for the home tab hero section.
    Always filters to TODAY_ISO and excludes entries with date-like game fields."""
    _date_like_sbd = re.compile(r"^\d{2}/\d{2}/\d{2,4}$")
    seen_games: set = set()
    ranked = sorted(
        [b for b in best_bets
         if b.get("date", TODAY_ISO) == TODAY_ISO
         and not _date_like_sbd.match(str(b.get("game", "")))],
        key=lambda b: (b.get("ev", 0) or 0) * 0.6 + (b.get("confidence", 0) or 0) * 0.4,
        reverse=True
    )
    out = []
    for b in ranked:
        game_key = (b.get("sport",""), b.get("home","") or b.get("game",""))
        if game_key in seen_games: continue
        seen_games.add(game_key)
        out.append(b)
        if len(out) >= n: break
    return out

def compute_live_win_prob(game: dict, sport: str) -> dict:
    """
    Estimate in-game win probability from score + game state.
    MLB: score diff + innings remaining via logit model.
    NBA: point diff + time remaining (linear regression).
    NHL: goal diff + period + time remaining.
    """
    h = game.get("hScore", 0) or 0
    a = game.get("aScore", 0) or 0
    diff = h - a
    import math

    if sport == "mlb":
        inning = game.get("inning", 5) or 5
        innings_left = max(0, 9 - inning)
        # Run expectancy: ~0.5 runs/inning regression to mean
        # logit(p) = diff * 0.45 - 0.015 * innings_left * abs(diff)
        logit_val = diff * 0.45 - 0.015 * innings_left * abs(diff)
        home_wp = round(1 / (1 + math.exp(-logit_val)), 3)
    elif sport == "nba":
        quarter = game.get("period", 4) or 4
        mins_elapsed = (quarter - 1) * 12 + (game.get("minutesElapsed") or ((quarter-1)*12))
        mins_left = max(0, 48 - mins_elapsed)
        # ~2.5 pts per minute variance; logit from FiveThirtyEight-style model
        sigma = math.sqrt(mins_left * 2.5)
        logit_val = diff / (sigma + 1e-9) * 1.5
        home_wp = round(1 / (1 + math.exp(-logit_val)), 3)
    elif sport == "nhl":
        period = game.get("period", 3) or 3
        mins_left_est = max(0, (3 - period) * 20)
        # ~0.15 goals/min base; logit from goal diff + time
        logit_val = diff * 0.55 - 0.008 * mins_left_est * abs(diff)
        home_wp = round(1 / (1 + math.exp(-logit_val)), 3)
    else:
        home_wp = 0.5

    return {
        "homeWinProb": home_wp,
        "awayWinProb": round(1 - home_wp, 3),
        "hScore": h,
        "aScore": a,
        "gameId": game.get("id",""),
        "home": game.get("home",""),
        "away": game.get("away",""),
        "state": game.get("state",""),
    }

# ═══════════════════════════════════════════════════════════════════════════════
# data.json writer + HTML timestamp patcher
# ═══════════════════════════════════════════════════════════════════════════════
def write_data_json(bundle: dict) -> None:
    payload = json.dumps(bundle, indent=2)
    FE_DATA.write_text(payload)
    # Also mirror to frontend/ for local dev
    fe_mirror = ROOT / "frontend" / "data.json"
    fe_mirror.write_text(payload)
    note(f"data.json written ({len(payload)//1024} KB) → docs/ (github.io) + frontend/ (local)")

def patch_html_timestamp() -> None:
    # Patch the engine SPA in docs/ — served at mercmink21.github.io/clairvoyance-backend/
    if not FE.exists(): return
    html   = FE.read_text(encoding="utf-8")
    ts_pat = r"(LAST_AUTO_UPDATE\s*=\s*['\"])([^'\"]*?)(['\"])"
    if re.search(ts_pat, html):
        html = re.sub(ts_pat, rf"\g<1>{TS_DISPLAY}\g<3>", html)
    else:
        html = html.replace("<script>",
            f'<script>\nconst LAST_AUTO_UPDATE = "{TS_DISPLAY}";\n', 1)
    FE.write_text(html, encoding="utf-8")
    # Keep app.html in sync with index.html
    app_html = FE.parent / "app.html"
    app_html.write_text(html, encoding="utf-8")
    vlog(f"HTML timestamp patched → {TS_DISPLAY}")

# ═══════════════════════════════════════════════════════════════════════════════
# Git push
# ═══════════════════════════════════════════════════════════════════════════════
def git_push(summary: str = "") -> bool:
    try:
        subprocess.run(["git","-C",str(ROOT),"add",
            # engine SPA + data — served at mercmink21.github.io/clairvoyance-backend/
            "docs/index.html",
            "docs/app.html",
            "docs/data.json",
            "docs/live_data.json",
            "docs/card.png",
            "docs/social_copy.json",
            "docs/bet_history.csv",
            # persistent records
            "data/bet_history.json",
            "data/bet_history.csv",
            # local frontend mirror (not pushed to Pages but kept in sync)
            "frontend/data.json",
            "frontend/index.html",
            "frontend/live_data.json",
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
def run_live_window(push: bool = True, interval_sec: int = 120) -> None:
    log("=== LIVE WINDOW MODE STARTED ===")
    live_data_fe   = ROOT / "docs" / "live_data.json"        # served at github.io

    while True:
        try:
            now_mt = datetime.now().astimezone()  # uses system TZ (set to America/Denver in cron)
        except Exception:
            now_mt = datetime.now()
        hour = now_mt.hour
        if hour >= 23 or hour < 16:
            log("=== LIVE WINDOW END (outside 16:00-23:00 MT) ==="); break

        log(f"Live refresh {now_mt.strftime('%H:%M')}…")
        try:
            mlb_t, _  = fetch_mlb_scoreboard()
            nba_t, _  = fetch_nba_scoreboard()
            nhl_t, _  = fetch_nhl_today()
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
            live_probs = {"mlb":[], "nba":[], "nhl":[]}
            for g in live_bundle["mlbLive"]:
                live_probs["mlb"].append(compute_live_win_prob(g, "mlb"))
            for g in live_bundle["nbaLive"]:
                live_probs["nba"].append(compute_live_win_prob(g, "nba"))
            for g in live_bundle["nhlLive"]:
                live_probs["nhl"].append(compute_live_win_prob(g, "nhl"))
            live_bundle["liveProbs"] = live_probs
            live_bundle["autoSettled"] = auto_settle(live_bundle["mlbAll"], live_bundle["nbaAll"], live_bundle["nhlAll"])
            live_data_fe.write_text(json.dumps(live_bundle, indent=2))

            if push:
                subprocess.run(["git","-C",str(ROOT),"add",
                    "docs/live_data.json"], capture_output=True)
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

    parser = argparse.ArgumentParser(description="Clairvoyance v6.0 data refresh")
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
    log(f"Clairvoyance v6.0 — {TS_DISPLAY}")
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
    # Schedule accuracy: log the exact dates used per sport to confirm alignment
    log(f"Schedule dates → MLB/NBA: {TODAY_ET} (ET) · NHL/Tennis/F1: {TODAY_ISO} (MT ISO)")
    mlb_today, mlb_tom   = fetch_mlb_scoreboard(TODAY_ET)  if S in ("mlb","all") else ([],[])
    mlb_standings        = fetch_mlb_standings()          if S in ("mlb","all") else {}
    mlb_week             = fetch_mlb_schedule_week()      if S in ("mlb","all") else []
    mlb_ref              = (fetch_baseball_reference()    if not args.no_reference else {}) if S in ("mlb","all") else {}
    mlb_sabre            = (fetch_mlb_team_sabermetrics() if not args.no_reference else {}) if S in ("mlb","all") else {}
    mlb_nrfi             = fetch_mlb_nrfi_data(mlb_today) if S in ("mlb","all") else []

    nba_today, nba_tom   = fetch_nba_scoreboard()         if S in ("nba","all") else ([],[])
    nba_standings        = fetch_nba_standings()          if S in ("nba","all") else {}
    nba_players          = fetch_nba_player_stats()       if S in ("nba","all") else []
    nba_bracket          = fetch_nba_playoff_bracket()    if S in ("nba","all") else {}
    nba_ref              = (fetch_basketball_reference()  if not args.no_reference else {}) if S in ("nba","all") else {}
    nba_adv              = (fetch_nba_team_advanced()     if not args.no_reference else {}) if S in ("nba","all") else {}

    nhl_today, nhl_tom   = fetch_nhl_today()               if S in ("nhl","all") else ([],[])
    nhl_standings        = fetch_nhl_standings()          if S in ("nhl","all") else {}
    nhl_bracket          = fetch_nhl_playoff_bracket()    if S in ("nhl","all") else {}
    nhl_edge             = fetch_nhl_edge()               if S in ("nhl","all") else {}
    nhl_edge_enh         = fetch_nhl_edge_enhanced()      if S in ("nhl","all") else {}
    mp                   = fetch_moneypuck()              if S in ("nhl","all") else {}
    hockeyviz            = fetch_hockeyviz()              if S in ("nhl","all") else {}
    hockey_ref           = (fetch_hockey_reference()      if not args.no_reference else {}) if S in ("nhl","all") else {}

    atp_elo   = fetch_tennis_elo("atp")      if S in ("tennis","all") else []
    wta_elo   = fetch_tennis_elo("wta")      if S in ("tennis","all") else []
    atp_yelo  = fetch_tennis_yelo("atp")     if S in ("tennis","all") else []
    wta_yelo  = fetch_tennis_yelo("wta")     if S in ("tennis","all") else []
    tennis_ratio      = fetch_tennis_ratio()          if S in ("tennis","all") else {}
    tennis_schedule   = fetch_tennis_schedule()       if S in ("tennis","all") else []
    tennis_sched_full = fetch_tennis_schedule_full()  if S in ("tennis","all") else {}
    tennis_rankings   = fetch_tennis_rankings_espn()  if S in ("tennis","all") else {}

    f1_data          = fetch_f1()               if S in ("f1","all") else {}
    f1_analytics     = fetch_f1_analytics()     if S in ("f1","all") else {}
    f1_tracing       = fetch_f1_tracing_insights() if S in ("f1","all") else {}
    f1_calendar      = fetch_f1_calendar_datastop() if S in ("f1","all") else []
    f1_comprehensive = fetch_f1_data()          if S in ("f1","all") else {}
    f1_unchained     = fetch_f1_unchained()     if S in ("f1","all") else {}

    roland_garros    = fetch_roland_garros()    if S in ("tennis","all") else {}
    tennis_odds      = fetch_tennis_odds()      if S in ("tennis","all") else {}
    futures_odds     = fetch_futures_odds()

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

    # NCAA Baseball + WNBA + PWHL
    ncaa_baseball = fetch_ncaa_baseball() if S in ("mlb","all") else {}
    wnba          = fetch_wnba()          if S in ("nba","all") else {}
    pwhl          = fetch_pwhl()          if S in ("nhl","all") else {}

    # Week schedules
    mlb_week_schedule = fetch_week_schedule("baseball/mlb","mlb",10)      if S in ("mlb","all") else []
    nba_week_schedule = fetch_week_schedule("basketball/nba","nba",8)      if S in ("nba","all") else []
    nhl_week_schedule = fetch_week_schedule("hockey/nhl","nhl",8)          if S in ("nhl","all") else []

    # News + injuries
    sports_news = fetch_sports_news()
    injuries    = fetch_injuries_all()

    # Best bets + auto-settle
    # Best odds per sport (Odds API if key set, ESPN fallback)
    mlb_best_odds = fetch_best_odds("mlb", mlb_today) if S in ("mlb","all") else {}
    nba_best_odds = fetch_best_odds("nba", nba_today) if S in ("nba","all") else {}
    nhl_best_odds = fetch_best_odds("nhl", nhl_today) if S in ("nhl","all") else {}

    # Backfill real book odds into game objects so the app displays them
    def _backfill_odds(game_list: list, odds_map: dict) -> None:
        for g in game_list:
            key = f"{g.get('home','')}:{g.get('away','')}"
            bk  = odds_map.get(key, {})
            if bk.get("homeML") is not None:
                g["homeML"] = bk["homeML"]
            if bk.get("awayML") is not None:
                g["awayML"] = bk["awayML"]
            if bk.get("ou") is not None:
                g["ou"] = bk["ou"]
            if bk.get("book"):
                g["oddsBook"] = bk["book"]
    _backfill_odds(mlb_today, mlb_best_odds)
    _backfill_odds(nba_today, nba_best_odds)
    _backfill_odds(nhl_today, nhl_best_odds)

    best_bets = calculate_best_bets(
        nba_today, mlb_today, nhl_today, weather, mp, nhl_edge,
        nhl_props=lm_props.get("nhl", []),
        nhl_trends=lm_trends.get("nhl", []),
        mlb_sabre=mlb_sabre,
        best_odds={
            **mlb_best_odds, **nba_best_odds, **nhl_best_odds,
            "_wnba_today":  wnba.get("today", []),
            "_ncaa_today":  ncaa_baseball.get("today", []),
        },
        nba_adv=nba_adv,
        mlb_standings=mlb_standings,
    )
    # Merge Roland Garros Elo bets (with real Odds API lines when available)
    rg_bets = _enrich_rg_bets(roland_garros.get("bets", []), tennis_odds)
    if rg_bets:
        best_bets = best_bets + rg_bets
        log(f"Roland Garros bets merged: +{len(rg_bets)} → {len(best_bets)} total")
    # Merge F1 race bets
    if f1_comprehensive.get("raceBets"):
        best_bets = best_bets + [b for b in f1_comprehensive["raceBets"] if b.get("ev", 0) > 0]
        log(f"F1 race bets merged: +{len(f1_comprehensive['raceBets'])} → {len(best_bets)} total")
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
        "version":      "7.0",
        "mlb": {
            "today":        mlb_today,
            "tomorrow":     mlb_tom,
            "standings":    mlb_standings,
            "weekSchedule": mlb_week,
            "weekSchedule7": mlb_week_schedule,
            "nrfi":         mlb_nrfi,
            "sabre":        mlb_sabre,
            "reference":    mlb_ref,
        },
        "nba": {
            "today":        nba_today,
            "tomorrow":     nba_tom,
            "standings":    nba_standings,
            "players":      nba_players,
            "bracket":      nba_bracket,
            "reference":    nba_ref,
            "teamAdv":      nba_adv,
            "weekSchedule": nba_week_schedule,
        },
        "nhl": {
            "today":        nhl_today,
            "tomorrow":     nhl_tom,
            "standings":    nhl_standings,
            "bracket":      nhl_bracket,
            "edge":         nhl_edge,
            "edgeEnhanced": nhl_edge_enh,
            "hockeyviz":    hockeyviz,
            "hockeyRef":    hockey_ref,
            "props":        lm_props.get("nhl", []),
            "trends":       lm_trends.get("nhl", []),
            "form":         lm_form.get("nhl", []),
            "weekSchedule": nhl_week_schedule,
        },
        "ncaaBaseball": ncaa_baseball,
        "wnba":         wnba,
        "pwhl":         pwhl,
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
            "rolandGarros":  roland_garros,
            "oddsMatches":   tennis_odds.get("matches", []),
            "oddsSource":    tennis_odds.get("source", ""),
            "tennisRatio":   tennis_ratio,
            "calendar":      tennis_sched_full,
        },
        "futures":   futures_odds,
        "f1": {
            **f1_data,
            "analytics":    f1_analytics,
            "tracing":      f1_tracing,
            "calendar":     f1_calendar,
            "comprehensive": f1_comprehensive,
            "unchained":    f1_unchained,
        },
        "linemate": {
            "props":  lm_props,
            "trends": lm_trends,
            "form":   lm_form,
        },
        "bestBets":      best_bets,
        "heroPicksForDay": surface_best_bets_for_day(best_bets),
        "bestOdds":      {**mlb_best_odds, **nba_best_odds, **nhl_best_odds},
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
        from content_generator import generate_content, write_social_json, detect_slot
        from generate_card import generate_card
        slot   = detect_slot()
        social = generate_content(bundle, slot=slot, verbose=_verbose)
        if social:
            write_social_json(social)
            note("social_copy.json written")
            img = generate_card(bundle, social)
            for p in (ROOT/"frontend"/"card.png", ROOT/"docs"/"card.png"):
                img.save(str(p), format="PNG", optimize=True)
            note("card.png written")
            top_pick = bundle.get("bestBets", [{}])[0]
            pick_summary = f"{top_pick.get('pick','—')}  EV {top_pick.get('ev','?')}%" if top_pick else "No picks today"
            _notify("Content Delivered", f"card.png + social copy ready · {pick_summary}")
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
        pushed = git_push(summary)
        if pushed:
            n_bets = len(best_bets)
            top_grade = best_bets[0].get("evGrade","—") if best_bets else "—"
            _notify("Refresh Complete", f"Push done · {n_bets} picks · top grade {top_grade} · {TS_DISPLAY}")
    else:
        _notify("Refresh Complete", f"Data updated (no push) · {len(best_bets)} picks · {TS_DISPLAY}")

    log("=" * 60)
    log(f"Done. {len(_changes)} changes.")
    for c in _changes: log(f"  • {c}")
    log("=" * 60)


if __name__ == "__main__":
    main()
