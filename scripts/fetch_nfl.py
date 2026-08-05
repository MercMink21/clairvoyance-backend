"""NFL data pipeline — foundation layer, same architecture as fetch_cfb.py.

Phase 1: teams/schedule/standings/team-stats/injuries/transactions --
everything the Games/Model/Config tabs, weather, settlement, and the
injuries/transactions news feed need. Player-level stats for props
(passing/rushing/receiving/TD props) are a deliberate phase 2, not
built here -- scraping real per-player season stats well (not just a
handful of league leaders) needs its own pass rather than a rushed
add-on to this one.

Unlike CFB, NFL doesn't need a conference-membership discovery step --
every team's own detail endpoint directly exposes AFC/NFC + division,
no groups= workaround required.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
TEAMS_OUT = ROOT / "docs" / "nfl_teams.json"
SCHEDULE_OUT = ROOT / "docs" / "nfl_schedule.json"
STANDINGS_OUT = ROOT / "docs" / "nfl_standings.json"
STATS_OUT = ROOT / "docs" / "nfl_team_stats.json"
INJURIES_OUT = ROOT / "docs" / "nfl_injuries.json"
TRANSACTIONS_OUT = ROOT / "docs" / "nfl_transactions.json"

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
ESPN_WEB_BASE = "https://site.web.api.espn.com/apis/v2/sports/football/nfl"
ESPN_CORE_BASE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ClairvoyanceBot/1.0)"}

# NFL regular season is 18 weeks; Thursday of week N through Monday of
# week N (Thu/Sun/Mon, per the user's explicit "Thursday night starts
# the week, Monday night ends it" framing) is one calendar window, not
# a Sun-Sat one. ESPN's own week=N indexing already groups games this
# way (a Thursday game shows under the SAME week number as the Sunday/
# Monday games right after it), so no extra bucketing logic is needed
# here beyond using ESPN's week param directly.
REGULAR_SEASON_WEEKS = list(range(1, 19))
POSTSEASON_ROUNDS = {1: "Wild Card", 2: "Divisional", 3: "Conference Championship", 5: "Super Bowl"}
# Preseason (seasontype=1) is 3 real game weeks for most teams (a 4th,
# "Hall of Fame Game" week, only involves 2 teams most years) -- included
# so preseason matchups show up in the engine as soon as they're
# scheduled, not just once the regular season starts.
PRESEASON_WEEKS = {0: "Hall of Fame Game", 1: "Preseason Week 1", 2: "Preseason Week 2", 3: "Preseason Week 3"}


def _log(msg: str) -> None:
    print(f"[nfl] {msg}", flush=True)


def fetch_all_teams() -> list[dict]:
    r = requests.get(f"{ESPN_BASE}/teams", params={"limit": 40}, headers=HEADERS, timeout=15)
    r.raise_for_status()
    d = r.json()
    teams = d.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
    return [t["team"] for t in teams]


def fetch_team_detail(team_id: str) -> dict | None:
    """Conference (AFC/NFC) + division (North/South/East/West) come
    straight off each team's own detail endpoint's groups info -- unlike
    CFB, no bulk-endpoint filter workaround needed, NFL only has 32
    teams total so one detail call per team is cheap."""
    try:
        r = requests.get(f"{ESPN_BASE}/teams/{team_id}", headers=HEADERS, timeout=10)
        r.raise_for_status()
        t = r.json().get("team", {})
        venue = t.get("venue") or {}
        groups = t.get("groups") or {}
        parent = groups.get("parent") or {}
        return {
            "id": t.get("id"),
            "abbr": t.get("abbreviation"),
            "name": t.get("displayName"),
            "conference": parent.get("name"),  # "American Football Conference" / "National Football Conference"
            "division": groups.get("name"),    # e.g. "AFC North"
            "venueName": venue.get("fullName"),
            "venueCapacity": venue.get("capacity"),
            "venueIndoor": venue.get("indoor", False),
        }
    except Exception as exc:
        _log(f"  team {team_id} FAILED: {exc}")
        return None


def build_roster() -> dict:
    all_teams = fetch_all_teams()
    _log(f"{len(all_teams)} teams found — resolving conference/division for each…")
    roster = []
    for i, t in enumerate(all_teams):
        tid = t.get("id")
        if not tid:
            continue
        info = fetch_team_detail(tid)
        if info:
            roster.append(info)
        if (i + 1) % 10 == 0:
            _log(f"  …{i + 1}/{len(all_teams)}")
        time.sleep(0.15)
    return {"teams": roster}


def fetch_week_games(year: int, week: int, seasontype: int = 2) -> list[dict]:
    """One call per week gets every game — venue (for weather), city/
    state, real market spread/O-U/ML odds, and (once played) the final
    score used for settlement. seasontype: 1=preseason, 2=regular,
    3=postseason."""
    r = requests.get(
        f"{ESPN_BASE}/scoreboard",
        params={"limit": 100, "week": week, "seasontype": seasontype, "year": year},
        headers=HEADERS, timeout=15,
    )
    r.raise_for_status()
    d = r.json()
    games = []
    for e in d.get("events", []):
        comp = (e.get("competitions") or [{}])[0]
        home = next((c for c in comp.get("competitors", []) if c.get("homeAway") == "home"), {})
        away = next((c for c in comp.get("competitors", []) if c.get("homeAway") == "away"), {})
        odds = (comp.get("odds") or [{}])[0]
        venue = comp.get("venue") or {}
        address = venue.get("address") or {}
        status = e.get("status", {})
        games.append({
            "id": e.get("id"),
            "date": e.get("date"),
            "name": e.get("name"),
            "venue": venue.get("fullName"),
            "city": address.get("city"),
            "venueState": address.get("state"),
            "indoor": venue.get("indoor", False),
            "neutralSite": comp.get("neutralSite", False),
            "home": (home.get("team") or {}).get("abbreviation"),
            "homeName": (home.get("team") or {}).get("displayName"),
            "homeScore": int(home["score"]) if home.get("score") not in (None, "") else None,
            "away": (away.get("team") or {}).get("abbreviation"),
            "awayName": (away.get("team") or {}).get("displayName"),
            "awayScore": int(away["score"]) if away.get("score") not in (None, "") else None,
            "spread": odds.get("spread"),
            "spreadDetails": odds.get("details"),
            "overUnder": odds.get("overUnder"),
            "homeML": (odds.get("homeTeamOdds") or {}).get("moneyLine"),
            "awayML": (odds.get("awayTeamOdds") or {}).get("moneyLine"),
            "state": status.get("type", {}).get("state", "pre"),
            "week": week,
            "seasonType": seasontype,
        })
    return games


def fetch_full_schedule(year: int) -> dict:
    """Preseason (3-4 weeks), then weeks 1-18 regular season, then the 4
    postseason rounds (Wild Card/Divisional/Conf Champ/Super Bowl —
    ESPN's postseason week numbering skips 4, there's no "week 4"
    round). Thursday/Sunday/Monday games for a given regular-season week
    all come back from the same week=N call already, matching the
    user's own week-boundary framing -- no extra date-bucketing needed.
    Preseason weeks are inserted first so they sort chronologically
    ahead of "Week 1" in the schedule dict/week-filter dropdown."""
    schedule: dict[str, list[dict]] = {}
    for wk, label in PRESEASON_WEEKS.items():
        games = fetch_week_games(year, wk, seasontype=1)
        if games:
            schedule[label] = games
            _log(f"  {label}: {len(games)} games")
        time.sleep(0.2)
    for wk in REGULAR_SEASON_WEEKS:
        games = fetch_week_games(year, wk, seasontype=2)
        schedule[f"Week {wk}"] = games
        _log(f"  Week {wk}: {len(games)} games")
        time.sleep(0.2)
    for wk, label in POSTSEASON_ROUNDS.items():
        games = fetch_week_games(year, wk, seasontype=3)
        if games:
            schedule[label] = games
            _log(f"  {label}: {len(games)} games")
        time.sleep(0.2)
    return schedule


def fetch_standings(year: int) -> dict:
    """W-L-T, PF, PA, point differential, conference/division rank --
    the "surface stats" the user explicitly asked for, not full team
    stats (that's fetch_team_stats below)."""
    try:
        r = requests.get(
            f"{ESPN_WEB_BASE}/standings",
            params={"season": year, "level": 3},  # level 3 = division standings
            headers=HEADERS, timeout=15,
        )
        r.raise_for_status()
        d = r.json()
    except Exception as exc:
        _log(f"  standings FAILED: {exc}")
        return {"conferences": {}}

    conferences: dict[str, list[dict]] = {}
    for group in (d.get("children") or []):  # AFC / NFC
        conf_name = group.get("name") or group.get("abbreviation")
        for div in (group.get("children") or []):  # North/South/East/West
            div_name = div.get("name")
            entries = ((div.get("standings") or {}).get("entries") or [])
            for entry in entries:
                team = entry.get("team") or {}
                stats = {s.get("name"): s.get("value") for s in (entry.get("stats") or [])}
                row = {
                    "abbr": team.get("abbreviation"),
                    "name": team.get("displayName"),
                    "division": div_name,
                    "wins": stats.get("wins"),
                    "losses": stats.get("losses"),
                    "ties": stats.get("ties"),
                    "pointsFor": stats.get("pointsFor"),
                    "pointsAgainst": stats.get("pointsAgainst"),
                    "differential": stats.get("differential"),
                    "divisionRank": stats.get("divisionRank"),
                    "playoffSeed": stats.get("playoffSeed"),
                }
                conferences.setdefault(conf_name, []).append(row)
    return {"conferences": conferences}


# Team stats categories mirroring fetch_cfb.py's own _OFFENSE_FIELDS/
# _DEFENSE_ALLOWED_FIELDS/_ST_FIELDS shape, adapted to what the user
# explicitly asked for: total/passing/rushing/receiving/downs on
# offense; yards allowed/turnovers/passing/receiving/downs on defense;
# returning/kicking/punting on special teams.
_OFFENSE_FIELDS = {
    "total":      ["totalYards", "yardsPerGame", "totalPoints", "totalPointsPerGame", "turnOverDifferential"],
    "passing":    ["netPassingYards", "netPassingYardsPerGame", "passingTouchdowns",
                    "completionPct", "yardsPerPassAttempt", "interceptions"],
    "rushing":    ["rushingYards", "rushingYardsPerGame", "rushingTouchdowns", "yardsPerRushAttempt"],
    "receiving":  ["receivingYards", "receivingTouchdowns", "receivingYardsPerGame"],
    "downs":      ["thirdDownConvPct", "fourthDownConvPct", "firstDowns", "totalPenaltyYards"],
}
_DEFENSE_ALLOWED_FIELDS = {
    "yardsAllowed": ["totalYards", "yardsPerGame", "totalPointsPerGame"],
    "turnovers":    ["interceptions", "fumblesRecovered", "totalTakeaways"],
    "passing":      ["netPassingYardsPerGame", "passingTouchdowns", "interceptions"],
    # "rushing" was missing entirely -- defense radar/reasoning needs a
    # real rush-defense signal, not just pass/receiving, to be a genuine
    # offense/defense breakdown rather than a partial one.
    "rushing":      ["rushingYardsPerGame", "rushingTouchdowns"],
    "receiving":    ["receivingYards", "receivingTouchdowns"],
    "downs":        ["thirdDownConvPct", "fourthDownConvPct"],
}
_ST_FIELDS = {
    "returning": ["yardsPerKickReturn", "kickReturnTouchdowns", "yardsPerPuntReturn", "puntReturnTouchdowns"],
    "kicking":   ["fieldGoalPct", "longFieldGoalMade", "extraPointPct", "totalKickingPoints"],
    "punting":   ["grossAvgPuntYards", "netAvgPuntYards", "puntsInside20"],
}


def _extract_fields(categories: list[dict], field_map: dict[str, list[str]]) -> dict:
    out: dict[str, float] = {}
    wanted = {f for fields in field_map.values() for f in fields}
    for cat in categories or []:
        for stat in cat.get("stats") or []:
            name = stat.get("name")
            if name in wanted:
                val = stat.get("value")
                if val is not None:
                    out[name] = val
    return out


def fetch_team_stats(team_id: str, season: int) -> dict | None:
    try:
        r = requests.get(
            f"{ESPN_BASE}/teams/{team_id}/statistics",
            params={"season": season}, headers=HEADERS, timeout=15,
        )
        r.raise_for_status()
        d = r.json()
        own_cats = ((d.get("results") or {}).get("stats") or {}).get("categories") or []
        opp_cats = (d.get("results") or {}).get("opponent") or []
        return {
            "offense": _extract_fields(own_cats, _OFFENSE_FIELDS),
            "defenseAllowed": _extract_fields(opp_cats, _DEFENSE_ALLOWED_FIELDS),
            "specialTeams": _extract_fields(own_cats, _ST_FIELDS),
        }
    except Exception as exc:
        _log(f"  team {team_id} stats FAILED: {exc}")
        return None


def fetch_all_team_stats(roster: list[dict], season: int) -> dict:
    stats = {}
    for i, t in enumerate(roster):
        abbr, tid = t.get("abbr"), t.get("id")
        if not abbr or not tid:
            continue
        s = fetch_team_stats(tid, season)
        if s:
            stats[abbr] = {"name": t.get("name"), **s}
        if (i + 1) % 8 == 0:
            _log(f"  stats …{i + 1}/{len(roster)}")
        time.sleep(0.2)
    return stats


def fetch_injuries() -> dict:
    """Per-team injury report: player, status, injury description,
    estimated return date when ESPN publishes one. Feeds both the
    per-team game-card context and the NFL news tab."""
    try:
        r = requests.get(f"{ESPN_BASE}/injuries", headers=HEADERS, timeout=15)
        r.raise_for_status()
        d = r.json()
    except Exception as exc:
        _log(f"  injuries FAILED: {exc}")
        return {"teams": {}}
    teams: dict[str, list[dict]] = {}
    for entry in d.get("injuries") or []:
        team = (entry.get("team") or {})
        abbr = team.get("abbreviation")
        if not abbr:
            continue
        rows = []
        for item in entry.get("injuries") or []:
            athlete = item.get("athlete") or {}
            details = item.get("details") or {}
            rows.append({
                "player": athlete.get("displayName"),
                "position": (athlete.get("position") or {}).get("abbreviation"),
                "status": item.get("status"),
                "injury": details.get("type") or item.get("shortComment"),
                "estimatedReturn": details.get("returnDate"),
                "comment": item.get("longComment") or item.get("shortComment"),
                "date": item.get("date"),
            })
        teams[abbr] = rows
    return {"teams": teams}


def fetch_transactions() -> dict:
    """Team, transaction type (trade/signing/release/waiver), date,
    description -- feeds the NFL news tab's transactions section."""
    try:
        r = requests.get(f"{ESPN_BASE}/transactions", headers=HEADERS, timeout=15)
        r.raise_for_status()
        d = r.json()
    except Exception as exc:
        _log(f"  transactions FAILED: {exc}")
        return {"items": []}
    items = []
    for t in d.get("transactions") or []:
        team = (t.get("team") or {})
        items.append({
            "team": team.get("abbreviation"),
            "teamName": team.get("displayName"),
            "date": t.get("date"),
            "description": t.get("description"),
        })
    return {"items": items}


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), **payload}
    path.write_text(json.dumps(payload, indent=2))
    _log(f"wrote {path}")


def git_push(paths: list[str], message: str) -> None:
    subprocess.run(["git", "add", *paths], cwd=ROOT, check=True)
    r = subprocess.run(["git", "commit", "-m", message], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        _log(f"  nothing to commit ({r.stdout.strip()[:120]})")
        return
    subprocess.run(["git", "push"], cwd=ROOT, check=True)
    _log("  pushed")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["roster", "schedule", "standings", "stats", "injuries", "transactions", "all"], default="all")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--stats-season", type=int, default=2025)
    ap.add_argument("--schedule-year", type=int, default=2026)
    args = ap.parse_args()

    did_roster = did_schedule = False
    roster_teams: list[dict] = []

    if args.mode in ("roster", "all"):
        result = build_roster()
        roster_teams = result["teams"]
        _write(TEAMS_OUT, result)
        did_roster = True

    if args.mode in ("schedule", "all"):
        sched = fetch_full_schedule(args.schedule_year)
        _write(SCHEDULE_OUT, {"weeks": sched, "year": args.schedule_year})
        did_schedule = True

    if args.mode in ("standings", "all"):
        standings = fetch_standings(args.schedule_year)
        _write(STANDINGS_OUT, standings)

    if args.mode in ("stats", "all"):
        if not roster_teams:
            if TEAMS_OUT.exists():
                roster_teams = json.loads(TEAMS_OUT.read_text()).get("teams", [])
            else:
                _log("  no roster available for stats — run --mode roster first")
        if roster_teams:
            stats = fetch_all_team_stats(roster_teams, args.stats_season)
            _write(STATS_OUT, {"teams": stats})

    if args.mode in ("injuries", "all"):
        _write(INJURIES_OUT, fetch_injuries())

    if args.mode in ("transactions", "all"):
        _write(TRANSACTIONS_OUT, fetch_transactions())

    if args.push:
        paths = ["docs/nfl_teams.json", "docs/nfl_schedule.json", "docs/nfl_standings.json",
                  "docs/nfl_team_stats.json", "docs/nfl_injuries.json", "docs/nfl_transactions.json"]
        git_push(paths, f"chore: refresh NFL {args.mode} data")
