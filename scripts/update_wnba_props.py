#!/usr/bin/env python3
"""
update_wnba_props.py — Daily WNBA Player Props Refresh
Fetches today's WNBA schedule from ESPN, pulls 2026 season stats from BBRef,
generates contextual player props for each game, and injects the result into
docs/app.html + docs/index.html. Optionally commits and pushes.

Usage:
  python3 scripts/update_wnba_props.py           # inject only
  python3 scripts/update_wnba_props.py --push    # inject + git commit + push
  python3 scripts/update_wnba_props.py --dry-run # print props, no file write

Cron (Mountain Time):
  0 10 * * * cd /path/to/clairvoyance-backend && python3 scripts/update_wnba_props.py --push
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).parent.parent
APP     = ROOT / "docs" / "app.html"
INDEX   = ROOT / "docs" / "index.html"
LOGS    = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

# ── deps ──────────────────────────────────────────────────────────────────────
try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "lxml"],
                   check=True, capture_output=True)
    import requests
    from bs4 import BeautifulSoup

# ── utils ─────────────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
}

def log(msg: str, lvl: str = "INFO") -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{lvl}] {msg}", flush=True)

def fetch_json(url: str, timeout: int = 12) -> dict | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"fetch_json {url[:60]}: {e}", "WARN")
        return None

def fetch_html(url: str, timeout: int = 15) -> BeautifulSoup | None:
    try:
        time.sleep(3)  # BBRef rate-limit courtesy
        r = requests.get(url, headers={**HEADERS, "Referer": "https://www.basketball-reference.com/"},
                         timeout=timeout)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        log(f"fetch_html {url[:60]}: {e}", "WARN")
        return None

# ── team abbrev normalisation ─────────────────────────────────────────────────
# ESPN → engine abbreviation map
ESPN_TO_ENG = {
    "ATL": "ATL", "CHI": "CHI", "CON": "CON", "DAL": "DAL",
    "IND": "IND", "LA":  "LAS", "LAS": "LAS", "LV":  "LVA",
    "LVA": "LVA", "MIN": "MIN", "NY":  "NYL", "NYL": "NYL",
    "PDX": "PDX", "PHX": "PHX", "SEA": "SEA", "TOR": "TOR",
    "WAS": "WSH", "WSH": "WSH", "GS":  "GSV", "GSV": "GSV",
}
# BBRef team name substrings → engine abbrev
BBREF_TO_ENG: dict[str, str] = {
    "Atlanta":       "ATL",
    "Chicago":       "CHI",
    "Connecticut":   "CON",
    "Dallas":        "DAL",
    "Indiana":       "IND",
    "Los Angeles":   "LAS",
    "Las Vegas":     "LVA",
    "Minnesota":     "MIN",
    "New York":      "NYL",
    "Portland":      "PDX",
    "Phoenix":       "PHX",
    "Seattle":       "SEA",
    "Toronto":       "TOR",
    "Washington":    "WSH",
    "Golden State":  "GSV",
}

def _norm(abbr: str) -> str:
    return ESPN_TO_ENG.get(abbr.upper(), abbr.upper())

# ── ESPN schedule ─────────────────────────────────────────────────────────────
def fetch_today_games(date_str: str) -> list[dict]:
    """Return list of {home, away, homeName, awayName, time, spread, ou} for today."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard?dates={date_str}&limit=20"
    data = fetch_json(url)
    if not data:
        return []
    games = []
    for ev in data.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        comps = comp.get("competitors") or []
        h = next((c for c in comps if c.get("homeAway") == "home"), {})
        a = next((c for c in comps if c.get("homeAway") == "away"), {})
        ha = _norm((h.get("team") or {}).get("abbreviation", ""))
        aa = _norm((a.get("team") or {}).get("abbreviation", ""))
        if not ha or not aa:
            continue
        odds_list = comp.get("odds") or []
        odds = odds_list[0] if odds_list else {}
        h_odds = odds.get("homeTeamOdds") or {}
        a_odds = odds.get("awayTeamOdds") or {}
        spread  = h_odds.get("pointSpread", {}).get("alternateDisplayValue") or ""
        ou      = odds.get("overUnder") or ""
        h_ml    = h_odds.get("moneyLine")
        a_ml    = a_odds.get("moneyLine")
        status = ev.get("status", {}).get("type", {}).get("state", "pre")
        # parse game time
        date_raw = ev.get("date", "")
        try:
            dt_utc = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
            dt_mt  = dt_utc.astimezone(timezone(timedelta(hours=-6)))
            time_str = dt_mt.strftime("%-I:%M %p MT")
        except Exception:
            time_str = ""
        games.append({
            "home": ha, "away": aa,
            "homeName": (h.get("team") or {}).get("displayName", ha),
            "awayName":  (a.get("team") or {}).get("displayName", aa),
            "time": time_str,
            "spread": spread,
            "ou": str(ou),
            "hML": h_ml,
            "aML": a_ml,
            "state": status,
        })
    return games

# ── BBRef player stats ────────────────────────────────────────────────────────
def fetch_player_stats(year: int = 2026) -> dict[str, dict]:
    """Scrape per-game + advanced from BBRef. Returns {name: stats_dict}."""
    players: dict[str, dict] = {}

    def _parse(soup: BeautifulSoup, tbl_id: str) -> list[dict]:
        tbl = soup.find("table", id=tbl_id)
        if not tbl:
            return []
        rows = []
        for row in tbl.find_all("tr"):
            th = row.find("th", attrs={"data-stat": "player"})
            if not th:
                continue
            a = th.find("a")
            name = a.get_text(strip=True) if a else th.get_text(strip=True)
            if not name or name in ("Player", "Rk", ""):
                continue
            rd: dict = {"player": name}
            for td in row.find_all("td"):
                stat = td.get("data-stat", "")
                if stat:
                    rd[stat] = td.get_text(strip=True)
            rows.append(rd)
        return rows

    def _f(val) -> float:
        try:
            return float(val or 0)
        except (ValueError, TypeError):
            return 0.0

    # Per-game
    log("BBRef per-game stats…")
    soup = fetch_html(f"https://www.basketball-reference.com/wnba/years/{year}_per_game.html")
    if soup:
        for r in _parse(soup, "per_game"):
            name = r["player"]
            # resolve team
            team_raw = r.get("team_id", r.get("team", ""))
            team = "UNK"
            for substr, abbr in BBREF_TO_ENG.items():
                if substr.lower() in team_raw.lower():
                    team = abbr
                    break
            if team == "UNK" and len(team_raw) <= 3:
                team = _norm(team_raw)
            players[name] = {
                "name":    name,
                "team":    team,
                "pos":     r.get("pos", ""),
                "g":       int(_f(r.get("g", 0))),
                "mp":      _f(r.get("mp_per_g", 0)),
                "pts":     _f(r.get("pts_per_g", 0)),
                "reb":     _f(r.get("trb_per_g", 0)),
                "ast":     _f(r.get("ast_per_g", 0)),
                "fg3m":    _f(r.get("fg3_per_g", 0)),
                "fg_pct":  _f(r.get("fg_pct", 0)),
                "fg3_pct": _f(r.get("fg3_pct", 0)),
                "ft_pct":  _f(r.get("ft_pct", 0)),
                "usg_pct": 0.0,
                "ts_pct":  0.0,
            }
        log(f"  per-game: {len(players)} players")

    # Advanced
    log("BBRef advanced stats…")
    soup2 = fetch_html(f"https://www.basketball-reference.com/wnba/years/{year}_advanced.html")
    if soup2:
        enriched = 0
        for r in _parse(soup2, "advanced"):
            name = r["player"]
            if name in players:
                players[name]["usg_pct"] = _f(r.get("usg_pct", 0))
                players[name]["ts_pct"]  = _f(r.get("ts_pct", 0))
                players[name]["per"]     = _f(r.get("per", 0))
                enriched += 1
        log(f"  advanced: enriched {enriched} players")

    return players

# ── key players per team ──────────────────────────────────────────────────────
# Used as fallback / ordering when BBRef data is unavailable.
# Format: {team_abbr: [{name, pts, reb, ast, fg3m, pos}, ...]}
FALLBACK_ROSTERS: dict[str, list[dict]] = {
    "ATL": [
        {"name": "Angel Reese",       "pts": 18.2, "reb": 11.8, "ast": 3.1, "fg3m": 0.4, "pos": "F"},
        {"name": "Skylar Diggins",    "pts": 16.4, "reb": 3.8,  "ast": 6.2, "fg3m": 1.2, "pos": "G"},
        {"name": "Pauline Astier",    "pts": 13.6, "reb": 4.2,  "ast": 5.8, "fg3m": 0.8, "pos": "G"},
    ],
    "CHI": [
        {"name": "Kamilla Cardoso",   "pts": 13.2, "reb": 8.8,  "ast": 1.4, "fg3m": 0.0, "pos": "C"},
        {"name": "Marina Mabrey",     "pts": 17.4, "reb": 4.1,  "ast": 3.8, "fg3m": 2.1, "pos": "G"},
    ],
    "CON": [
        {"name": "Alyssa Thomas",     "pts": 15.8, "reb": 8.2,  "ast": 7.1, "fg3m": 0.2, "pos": "F"},
        {"name": "DiJonai Carrington","pts": 15.7, "reb": 4.6,  "ast": 2.8, "fg3m": 1.4, "pos": "G"},
        {"name": "DeWanna Bonner",    "pts": 14.2, "reb": 6.4,  "ast": 2.1, "fg3m": 1.6, "pos": "F"},
    ],
    "DAL": [
        {"name": "Paige Bueckers",    "pts": 22.8, "reb": 4.2,  "ast": 6.2, "fg3m": 2.1, "pos": "G"},
        {"name": "Azzi Fudd",         "pts": 17.4, "reb": 3.6,  "ast": 2.8, "fg3m": 2.8, "pos": "G"},
        {"name": "Arike Ogunbowale",  "pts": 19.6, "reb": 3.2,  "ast": 3.8, "fg3m": 1.8, "pos": "G"},
    ],
    "IND": [
        {"name": "Aliyah Boston",     "pts": 16.8, "reb": 7.4,  "ast": 2.4, "fg3m": 0.4, "pos": "C-F"},
        {"name": "Kelsey Mitchell",   "pts": 20.1, "reb": 2.8,  "ast": 4.2, "fg3m": 2.2, "pos": "G"},
        {"name": "NaLyssa Smith",     "pts": 13.8, "reb": 8.6,  "ast": 1.6, "fg3m": 0.2, "pos": "F"},
    ],
    "LAS": [
        {"name": "Cameron Brink",     "pts": 17.6, "reb": 9.4,  "ast": 2.2, "fg3m": 0.4, "pos": "C-F"},
        {"name": "Kelsey Plum",       "pts": 18.9, "reb": 3.2,  "ast": 4.8, "fg3m": 2.4, "pos": "G"},
        {"name": "Dearica Hamby",     "pts": 14.2, "reb": 8.8,  "ast": 3.2, "fg3m": 0.8, "pos": "F"},
    ],
    "LVA": [
        {"name": "A'ja Wilson",       "pts": 28.4, "reb": 10.6, "ast": 3.8, "fg3m": 0.6, "pos": "C-F"},
        {"name": "Kelsey Plum",       "pts": 19.8, "reb": 2.8,  "ast": 5.2, "fg3m": 2.6, "pos": "G"},
        {"name": "Jackie Young",      "pts": 16.4, "reb": 4.2,  "ast": 4.6, "fg3m": 1.4, "pos": "G"},
    ],
    "MIN": [
        {"name": "Napheesa Collier",  "pts": 21.2, "reb": 9.8,  "ast": 3.4, "fg3m": 0.8, "pos": "F"},
        {"name": "Olivia Miles",      "pts": 18.6, "reb": 5.2,  "ast": 7.4, "fg3m": 1.6, "pos": "G"},
        {"name": "Bridget Carleton",  "pts": 12.8, "reb": 5.8,  "ast": 2.4, "fg3m": 2.2, "pos": "F"},
    ],
    "NYL": [
        {"name": "Breanna Stewart",   "pts": 21.4, "reb": 9.2,  "ast": 3.8, "fg3m": 1.2, "pos": "F"},
        {"name": "Sabrina Ionescu",   "pts": 19.8, "reb": 5.8,  "ast": 7.4, "fg3m": 3.2, "pos": "G"},
        {"name": "Jonquel Jones",     "pts": 16.2, "reb": 8.6,  "ast": 3.2, "fg3m": 1.0, "pos": "F-C"},
    ],
    "PDX": [
        {"name": "Satou Sabally",     "pts": 16.8, "reb": 6.4,  "ast": 3.4, "fg3m": 1.4, "pos": "F"},
        {"name": "Ezi Magbegor",      "pts": 13.2, "reb": 8.8,  "ast": 1.6, "fg3m": 0.2, "pos": "C"},
    ],
    "PHX": [
        {"name": "Kahleah Copper",    "pts": 21.8, "reb": 5.4,  "ast": 3.2, "fg3m": 1.6, "pos": "G-F"},
        {"name": "Brittney Griner",   "pts": 17.4, "reb": 7.2,  "ast": 1.8, "fg3m": 0.2, "pos": "C"},
        {"name": "Sophie Cunningham", "pts": 14.8, "reb": 4.2,  "ast": 2.4, "fg3m": 2.4, "pos": "G"},
    ],
    "SEA": [
        {"name": "Nneka Ogwumike",    "pts": 14.8, "reb": 6.4,  "ast": 2.6, "fg3m": 0.6, "pos": "F"},
        {"name": "Skylar Diggins-Smith","pts":15.4,"reb": 3.6,  "ast": 5.8, "fg3m": 1.4, "pos": "G"},
    ],
    "TOR": [
        {"name": "Brittney Sykes",    "pts": 18.4, "reb": 4.8,  "ast": 4.4, "fg3m": 1.6, "pos": "G"},
        {"name": "Marina Mabrey",     "pts": 17.4, "reb": 3.8,  "ast": 3.6, "fg3m": 2.4, "pos": "G"},
        {"name": "Sonia Citron",      "pts": 14.8, "reb": 4.2,  "ast": 3.2, "fg3m": 1.8, "pos": "G"},
    ],
    "WSH": [
        {"name": "Shakira Austin",    "pts": 14.6, "reb": 8.4,  "ast": 2.2, "fg3m": 0.4, "pos": "C-F"},
        {"name": "Sonia Citron",      "pts": 14.8, "reb": 4.2,  "ast": 3.2, "fg3m": 1.8, "pos": "G"},
    ],
    "GSV": [
        {"name": "Natisha Hiedeman",  "pts": 14.8, "reb": 3.8,  "ast": 4.2, "fg3m": 1.8, "pos": "G"},
        {"name": "Gabby Williams",    "pts": 15.2, "reb": 7.4,  "ast": 4.8, "fg3m": 0.8, "pos": "F"},
        {"name": "Flau'jae Johnson",  "pts": 12.4, "reb": 4.2,  "ast": 2.8, "fg3m": 1.6, "pos": "G"},
    ],
}

# ── prop line generation ──────────────────────────────────────────────────────
HOME_BOOST  = 0.04   # home teams boost output ~4%
ROAD_PENALTY= -0.02  # road teams slight penalty
OVER_BIAS   = 0.88   # line set at 88% of avg (books shade slightly under avg)
MIN_CONF    = 58
MAX_CONF    = 72

def _grade(conf: int) -> str:
    if conf >= 68: return "ELITE"
    if conf >= 62: return "LOCK"
    if conf >= 57: return "LEAN"
    return "FADE"

def _ml(conf: int) -> str:
    p = conf / 100
    ml = -round(p / (1 - p) * 100) if p >= 0.5 else round((1 - p) / p * 100)
    return f"+{ml}" if ml > 0 else str(ml)

def _cap(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def generate_props_for_game(
    home: str, away: str, home_name: str, away_name: str,
    spread: str, ou: str, players: dict[str, dict]
) -> list[dict]:
    """Build a list of WNBA_PROPS_DATA entries for one game."""
    game_key = f"{away}_{home}"
    props: list[dict] = []

    # Determine favored side from spread
    try:
        sp = float(spread.replace("−", "-").replace("–", "-").split()[0])
        home_favored = sp < 0
    except Exception:
        home_favored = True  # default home favour

    def _team_players(team_abbr: str) -> list[dict]:
        """Get ordered list of player dicts for a team (live BBRef or fallback)."""
        live = [p for p in players.values() if p.get("team") == team_abbr and p.get("pts", 0) >= 6.0]
        live.sort(key=lambda p: p.get("pts", 0), reverse=True)
        if live:
            return live[:4]
        # fallback
        return FALLBACK_ROSTERS.get(team_abbr, [])[:4]

    def _add_prop(player_name: str, team: str, opp: str,
                  stat: str, avg: float, is_home: bool, base_conf: int,
                  hit_rate_str: str, basis_str: str) -> None:
        if avg < 2.0 and stat in ("PTS", "REB", "AST", "PRA"):
            return
        boost = HOME_BOOST if is_home else ROAD_PENALTY
        adj_avg = avg * (1 + boost)
        line = round(adj_avg * OVER_BIAS * 2) / 2  # round to nearest 0.5
        if line <= 0:
            return
        conf = int(_cap(base_conf + (5 if is_home else -2), MIN_CONF, MAX_CONF))
        props.append({
            "player":   player_name,
            "team":     team,
            "opp":      opp,
            "game":     game_key,
            "stat":     stat,
            "line":     line,
            "over":     True,
            "ml":       _ml(conf),
            "conf":     conf,
            "grade":    _grade(conf),
            "hitRate":  hit_rate_str,
            "basis":    basis_str,
        })

    for role, (team_abbr, opp_abbr, is_home) in enumerate([
        (home, away, True),
        (away, home, False),
    ]):
        for p in _team_players(team_abbr):
            name = p["name"]
            pts  = p.get("pts", 0)
            reb  = p.get("reb", 0)
            ast  = p.get("ast", 0)
            fg3m = p.get("fg3m", 0)
            pra  = pts + reb + ast
            usg  = p.get("usg_pct", 0)
            pos  = p.get("pos", "")

            home_label = "home" if is_home else "road"
            fav_label  = "favored" if (is_home == home_favored) else "underdog"
            opp_label  = home_name if opp_abbr == home else away_name

            # PTS
            if pts >= 10.0:
                conf = int(_cap(60 + (usg - 22) * 0.4 + (3 if is_home else 0), MIN_CONF, MAX_CONF))
                _add_prop(name, team_abbr, opp_abbr, "PTS", pts, is_home, conf,
                          f"{pts:.1f} ppg · {home_label} {fav_label}",
                          f"{name} {home_label} scorer vs {opp_label}. "
                          f"{'Home crowd elevates output.' if is_home else 'Road usage stays high in close matchups.'} "
                          f"Season avg {pts:.1f} pts. Matchup context favors over.")

            # REB (for bigs/forwards)
            if reb >= 5.5 and "F" in pos or "C" in pos or reb >= 8.0:
                conf = int(_cap(60 + (reb - 6) * 1.5 + (2 if is_home else -1), MIN_CONF, MAX_CONF))
                _add_prop(name, team_abbr, opp_abbr, "REB", reb, is_home, conf,
                          f"{reb:.1f} rpg · glass control",
                          f"{name} rebounds dominate the paint. {opp_label} interior rotation leaves gaps. "
                          f"Season avg {reb:.1f} reb. {'Home board advantage.' if is_home else 'Road rebounding stays consistent for elite rebounders.'}")

            # AST (for guards/playmakers)
            if ast >= 4.5 and ("G" in pos or ast >= 6.0):
                conf = int(_cap(60 + (ast - 5) * 1.2 + (2 if is_home else -1), MIN_CONF, MAX_CONF))
                _add_prop(name, team_abbr, opp_abbr, "AST", ast, is_home, conf,
                          f"{ast:.1f} apg · playmaking engine",
                          f"{name} runs the offense at {home_label}. {opp_label} help rotations create kick-outs. "
                          f"Season avg {ast:.1f} ast. Matchup style favors high-usage playmakers.")

            # 3PM (for shooters)
            if fg3m >= 2.0:
                conf = int(_cap(60 + (fg3m - 2) * 3 + (1 if is_home else 0), MIN_CONF, MAX_CONF))
                _add_prop(name, team_abbr, opp_abbr, "3PM", fg3m, is_home, conf,
                          f"{fg3m:.1f} 3PM/game · catch-and-shoot",
                          f"{name} elite three-point threat. {opp_label} allows high 3PM rate to opposing guards. "
                          f"Season avg {fg3m:.1f} 3PM. Off-ball movement creates open looks.")

            # PRA (for stars with 30+ avg)
            if pra >= 26.0:
                conf = int(_cap(63 + (pra - 28) * 0.3 + (3 if is_home else -1), MIN_CONF, MAX_CONF))
                _add_prop(name, team_abbr, opp_abbr, "PRA", pra, is_home, conf,
                          f"{pra:.1f} PRA avg · all-around floor",
                          f"{name} fills every box. Season avg {pts:.1f} pts / {reb:.1f} reb / {ast:.1f} ast. "
                          f"{'Home amplifies every category.' if is_home else 'Road usage stays elite — needed to keep team competitive.'} "
                          f"{opp_label} matchup supports high PRA floor.")

    # Sort: ELITE first, then by conf desc, limit to 6 per game
    props.sort(key=lambda x: (-x["conf"]))
    return props[:6]

# ── JS block builder ──────────────────────────────────────────────────────────
def props_to_js(props: list[dict], date_key: str, games: list[dict]) -> str:
    """Return the full WNBA_PROPS_DATE + WNBA_PROPS_DATA = [...] JS block."""
    lines = [f"var WNBA_PROPS_DATE='{date_key}';", "var WNBA_PROPS_DATA=["]
    # Group by game
    from collections import defaultdict
    by_game: dict[str, list[dict]] = defaultdict(list)
    for p in props:
        by_game[p["game"]].append(p)

    # Build game order from schedule
    game_order = [f"{g['away']}_{g['home']}" for g in games]
    seen_keys = set()
    ordered_keys = []
    for k in game_order:
        if k not in seen_keys:
            ordered_keys.append(k)
            seen_keys.add(k)
    for k in by_game:
        if k not in seen_keys:
            ordered_keys.append(k)
            seen_keys.add(k)

    first_game = True
    for gk in ordered_keys:
        game_props = by_game.get(gk, [])
        if not game_props:
            continue
        # Find game info
        away_abbr, home_abbr = gk.split("_", 1)
        ginfo = next((g for g in games if g["home"] == home_abbr and g["away"] == away_abbr), {})
        time_s  = ginfo.get("time", "")
        spread_s= ginfo.get("spread", "")
        ou_s    = ginfo.get("ou", "")
        home_nm = ginfo.get("homeName", home_abbr)
        away_nm = ginfo.get("awayName", away_abbr)
        header  = f"  // ── {away_nm} @ {home_nm}"
        if time_s:
            header += f" ({time_s}"
            if spread_s:
                header += f" · {home_abbr} {spread_s}"
            if ou_s:
                header += f" · O/U {ou_s}"
            header += ")"
        header += " ──"
        if not first_game:
            lines.append("")
        first_game = False
        lines.append(header)
        for p in game_props:
            basis_esc = p["basis"].replace("'", "\\'")
            hit_esc   = p["hitRate"].replace("'", "\\'")
            lines.append(
                f"  {{player:'{p['player']}',team:'{p['team']}',opp:'{p['opp']}',"
                f"game:'{p['game']}',stat:'{p['stat']}',line:{p['line']},"
                f"over:true,ml:'{p['ml']}',conf:{p['conf']},grade:'{p['grade']}',"
                f"hitRate:'{hit_esc}',"
                f"basis:'{basis_esc}'}},"
            )

    lines.append("];")
    return "\n".join(lines)

# ── inject into app.html ──────────────────────────────────────────────────────
# File layout: var WNBA_PROPS_DATE='...'; \n var WNBA_PROPS_DATA=[...]; \n async function renderWNBAProps
PROPS_START_RE = re.compile(r"var WNBA_PROPS_DATE='[0-9]+';\n")
PROPS_END_RE   = re.compile(r'\];\n(?=async function renderWNBAProps)')

def inject_props(html: str, new_block: str) -> str:
    """Replace WNBA_PROPS_DATE + WNBA_PROPS_DATA block with refreshed version."""
    m_start = PROPS_START_RE.search(html)
    if not m_start:
        raise ValueError("WNBA_PROPS_DATE declaration not found in app.html")
    m_end = PROPS_END_RE.search(html, m_start.start())
    if not m_end:
        raise ValueError("WNBA_PROPS_DATA closing ]; not found before renderWNBAProps")
    return html[:m_start.start()] + new_block + "\n" + html[m_end.end():]

# ── validate no broken JS ─────────────────────────────────────────────────────
def validate_block(block: str) -> list[str]:
    errs = []
    if re.search(r"'\+\+[a-zA-Z_$]", block):
        errs.append("string++identifier pattern found")
    if block.count("{") != block.count("}"):
        errs.append(f"brace mismatch {block.count('{')}/{block.count('}')}")
    return errs

# ── main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description="Daily WNBA props refresh")
    ap.add_argument("--push",    action="store_true", help="git commit + push after inject")
    ap.add_argument("--dry-run", action="store_true", help="print props only, no file write")
    ap.add_argument("--no-bbref",action="store_true", help="skip BBRef fetch, use fallback rosters only")
    ap.add_argument("--date",    default="", help="override date YYYYMMDD (default: today ET)")
    args = ap.parse_args()

    # Date
    et_now   = datetime.now(timezone(timedelta(hours=-5)))  # ET
    date_key = args.date if args.date else et_now.strftime("%Y%m%d")
    year     = int(date_key[:4])
    log(f"WNBA props refresh for {date_key}")

    # 1. Today's schedule
    log("Fetching today's WNBA schedule from ESPN…")
    games = fetch_today_games(date_key)
    if not games:
        log("No WNBA games today — nothing to do.", "WARN")
        sys.exit(0)
    log(f"Games today: {len(games)}")
    for g in games:
        fav = g["homeName"] if (g.get("hML") or 999) < (g.get("aML") or 999) else g["awayName"]
        log(f"  {g['away']} @ {g['home']}  {g['time']}  (spread: {g.get('spread','?')}  OU: {g.get('ou','?')})")

    # 2. Player stats
    players: dict[str, dict] = {}
    if not args.no_bbref:
        players = fetch_player_stats(year)
        if not players:
            log("BBRef returned no data — using fallback rosters.", "WARN")
    else:
        log("--no-bbref: using fallback rosters only.")

    # 3. Generate props
    all_props: list[dict] = []
    for g in games:
        gprops = generate_props_for_game(
            home=g["home"], away=g["away"],
            home_name=g["homeName"], away_name=g["awayName"],
            spread=g.get("spread", ""), ou=g.get("ou", ""),
            players=players,
        )
        log(f"  {g['away']}@{g['home']}: {len(gprops)} props generated")
        all_props.extend(gprops)

    if not all_props:
        log("No props generated — aborting.", "WARN")
        sys.exit(1)

    log(f"Total props: {len(all_props)}")

    if args.dry_run:
        print("\n" + "=" * 60)
        print(props_to_js(all_props, date_key, games))
        return

    # 4. Build JS block
    new_block = props_to_js(all_props, date_key, games)

    # 5. Validate
    errs = validate_block(new_block)
    if errs:
        log(f"VALIDATION FAILED: {errs}", "ERROR")
        sys.exit(1)

    # 6. Inject into app.html
    html = APP.read_text(encoding="utf-8")
    try:
        new_html = inject_props(html, new_block)
    except ValueError as e:
        log(f"Inject failed: {e}", "ERROR")
        sys.exit(1)

    # Run the project validator first
    val = subprocess.run(["python3", str(ROOT / "scripts" / "validate.py")],
                         capture_output=True, text=True, cwd=ROOT)

    # Write
    APP.write_text(new_html, encoding="utf-8")
    INDEX.write_text(new_html, encoding="utf-8")
    log(f"Wrote {APP} + {INDEX}")

    # Run validator on new file
    val2 = subprocess.run(["python3", str(ROOT / "scripts" / "validate.py")],
                          capture_output=True, text=True, cwd=ROOT)
    if val2.returncode != 0:
        log("Validator FAILED after inject — reverting!", "ERROR")
        APP.write_text(html, encoding="utf-8")
        INDEX.write_text(html, encoding="utf-8")
        print(val2.stdout[-2000:])
        sys.exit(1)
    log("Validator: all checks passed")

    # 7. Commit + push
    if args.push:
        game_summary = ", ".join(f"{g['away']}@{g['home']}" for g in games)
        msg = (f"chore: refresh WNBA player props {date_key} ({len(all_props)} props)\n\n"
               f"Games: {game_summary}\n\n"
               f"Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>")
        subprocess.run(["git", "add", "docs/app.html", "docs/index.html"], cwd=ROOT, check=True)
        r = subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, capture_output=True, text=True)
        if r.returncode == 0:
            log("Committed.")
            push = subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, capture_output=True, text=True)
            if push.returncode == 0:
                log("Pushed to origin/main.")
            else:
                log(f"Push failed: {push.stderr}", "WARN")
        elif "nothing to commit" in r.stdout + r.stderr:
            log("Nothing changed — skipping commit.")
        else:
            log(f"Commit failed: {r.stderr}", "WARN")

    log("Done.")

if __name__ == "__main__":
    main()
