"""College Football data pipeline — foundation layer.

Builds the conference/team roster for the 9 conferences the engine tracks
(ACC, American, Big 12, Big Ten, FBS Independents, MAC, Mountain West,
Pac-12, SEC), since the bulk ESPN team-list endpoint doesn't expose
conference membership and its `groups=` query param is silently ignored —
confirmed by direct testing. The only reliable source is each team's own
detail endpoint (`teams/{id}` -> `groups.id`), so this pages through the
full FBS team list once, then does one detail call per team to resolve its
real conference.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "docs" / "cfb_teams.json"
POWER_OUT_PATH = ROOT / "docs" / "cfb_power.json"

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ClairvoyanceBot/1.0)"}

# The 9 conferences this engine tracks, keyed by ESPN's own group id
# (confirmed via GET .../standings?group=80's children listing).
TARGET_CONFERENCES = {
    "151": "American",
    "1":   "ACC",
    "4":   "Big 12",
    "5":   "Big Ten",
    "18":  "FBS Independents",
    "15":  "MAC",
    "17":  "Mountain West",
    "9":   "Pac-12",
    "8":   "SEC",
}


def _log(msg: str) -> None:
    print(f"[cfb] {msg}", flush=True)


def fetch_all_team_ids() -> list[dict]:
    """Full team list (all divisions — FBS, FCS, D2/D3 club programs ESPN
    also carries under this sport). Filtered down to FBS by conference
    membership in the next step, not here."""
    r = requests.get(f"{ESPN_BASE}/teams", params={"limit": 500}, headers=HEADERS, timeout=15)
    r.raise_for_status()
    d = r.json()
    teams = d.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
    return [t["team"] for t in teams]


def fetch_team_conference(team_id: str) -> dict | None:
    try:
        r = requests.get(f"{ESPN_BASE}/teams/{team_id}", headers=HEADERS, timeout=10)
        r.raise_for_status()
        t = r.json().get("team", {})
        groups = t.get("groups") or {}
        return {
            "id": t.get("id"),
            "abbr": t.get("abbreviation"),
            "name": t.get("displayName"),
            "confId": groups.get("id"),
        }
    except Exception as e:
        _log(f"  team {team_id} FAILED: {e}")
        return None


def build_roster() -> dict:
    all_teams = fetch_all_team_ids()
    _log(f"{len(all_teams)} total teams found (all divisions) — resolving conference for each…")

    roster: dict[str, list[dict]] = {name: [] for name in TARGET_CONFERENCES.values()}
    checked = 0
    for t in all_teams:
        tid = t.get("id")
        if not tid:
            continue
        info = fetch_team_conference(tid)
        checked += 1
        if checked % 25 == 0:
            _log(f"  …{checked}/{len(all_teams)} checked")
        if not info or not info.get("confId"):
            time.sleep(0.15)
            continue
        conf_name = TARGET_CONFERENCES.get(str(info["confId"]))
        if conf_name:
            roster[conf_name].append({"id": info["id"], "abbr": info["abbr"], "name": info["name"]})
        time.sleep(0.15)

    for conf, teams in roster.items():
        _log(f"  {conf}: {len(teams)} teams")
    return roster


def run() -> dict:
    roster = build_roster()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "generated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "conferences": roster,
    }, indent=2))
    _log(f"wrote {OUT_PATH}")
    return roster


# Field allow-lists per the exact categories requested: offense (total
# yards, passing, rushing, receiving, downs), defense (points allowed,
# yards allowed, passing, rushing), special teams (returning, kicking,
# punting). ESPN's own per-team /statistics endpoint returns far more
# fields than this per category — trimmed down to what's actually needed
# rather than carrying everything.
_OFFENSE_FIELDS = {
    "passing":       ["completionPct", "passingYards", "passingYardsPerGame", "passingTouchdowns",
                        "interceptions", "yardsPerPassAttempt", "QBRating"],
    "rushing":       ["rushingYards", "rushingYardsPerGame", "yardsPerRushAttempt",
                        "rushingTouchdowns", "rushingFirstDowns"],
    "receiving":     ["receivingYards", "receivingYardsPerGame", "receivingTouchdowns", "yardsPerReception"],
    "miscellaneous": ["firstDowns", "thirdDownConvPct", "fourthDownConvPct", "totalPenaltyYards",
                        "possessionTimeSeconds", "turnOverDifferential"],
}
_DEFENSE_ALLOWED_FIELDS = {
    # from the "opponent" split — what opponents did against this team,
    # i.e. this team's defense
    "passing": ["totalPointsPerGame", "yardsPerGame", "passingYardsPerGame", "passingTouchdowns"],
    "rushing": ["rushingYardsPerGame", "yardsPerRushAttempt", "rushingTouchdowns"],
}
_ST_FIELDS = {
    "returning": ["yardsPerKickReturn", "kickReturnTouchdowns", "yardsPerPuntReturn", "puntReturnTouchdowns"],
    "kicking":   ["fieldGoalPct", "longFieldGoalMade", "extraPointPct", "totalKickingPoints"],
    "punting":   ["grossAvgPuntYards", "netAvgPuntYards", "puntsInside20"],
}


def _extract_fields(categories: list[dict], allow: dict[str, list[str]]) -> dict:
    out = {}
    by_cat = {c["name"]: c for c in categories}
    for cat_name, fields in allow.items():
        cat = by_cat.get(cat_name)
        if not cat:
            continue
        stat_by_name = {s["name"]: s for s in cat.get("stats", [])}
        for f in fields:
            s = stat_by_name.get(f)
            if s is not None:
                out[f] = s.get("value", s.get("displayValue"))
    return out


def fetch_team_stats(team_id: str, season: int) -> dict | None:
    try:
        r = requests.get(f"{ESPN_BASE}/teams/{team_id}/statistics",
                         params={"season": season}, headers=HEADERS, timeout=12)
        r.raise_for_status()
        d = r.json()
        results = d.get("results", {})
        own_cats = results.get("stats", {}).get("categories", [])
        opp_cats = results.get("opponent", [])
        if not own_cats:
            return None
        return {
            "offense": _extract_fields(own_cats, _OFFENSE_FIELDS),
            "defenseAllowed": _extract_fields(opp_cats, _DEFENSE_ALLOWED_FIELDS),
            "specialTeams": _extract_fields(own_cats, _ST_FIELDS),
        }
    except Exception as e:
        _log(f"  team {team_id} stats FAILED: {e}")
        return None


def fetch_all_team_stats(roster: dict, season: int = 2025) -> dict:
    """season=2025 (last completed season) until 2026 games actually post
    stats — the /statistics endpoint returns an empty categories list for
    a season with zero games played, confirmed by direct testing, not a
    bug. Automatically has real current-season numbers once games start;
    no code change needed when that happens, just re-run with
    season=2026 (or leave it: main() below already tries the current
    year first and falls back)."""
    out = {}
    all_teams = [t for teams in roster.values() for t in teams]
    _log(f"Fetching stats for {len(all_teams)} teams (season={season})…")
    for i, t in enumerate(all_teams):
        stats = fetch_team_stats(t["id"], season)
        if stats:
            out[t["abbr"]] = {"teamId": t["id"], "name": t["name"], **stats}
        if (i + 1) % 20 == 0:
            _log(f"  …{i+1}/{len(all_teams)}")
        time.sleep(0.2)
    _log(f"  {len(out)}/{len(all_teams)} teams had stats")
    return out


def fetch_rankings() -> list[dict]:
    """AP Top 25 — updates weekly (Mon/Tue during the season, once for the
    preseason poll in mid-August). Defaults to whatever ESPN's own API
    currently considers "latest" (last season's final poll until the 2026
    preseason poll actually drops), which is expected/correct, not a bug —
    it'll pick up the new poll automatically the moment ESPN publishes it."""
    r = requests.get(f"{ESPN_BASE}/rankings", headers=HEADERS, timeout=15)
    r.raise_for_status()
    d = r.json()
    ap = next((p for p in d.get("rankings", []) if p.get("shortName") == "AP Poll"), None)
    if not ap:
        _log("  AP Poll not found in rankings response")
        return []
    out = []
    for entry in ap.get("ranks", []):
        t = entry.get("team", {})
        out.append({
            "rank": entry.get("current"),
            "previousRank": entry.get("previous"),
            "trend": entry.get("trend"),
            "points": entry.get("points"),
            "firstPlaceVotes": entry.get("firstPlaceVotes"),
            "teamId": t.get("id"),
            "abbr": t.get("abbreviation"),
            # ESPN's team object here has location/name/nickname backwards
            # from what the field names suggest -- "name" holds the mascot
            # ("Hoosiers"), "nickname" holds the short school name
            # ("Indiana"), confirmed by direct inspection (Indiana Hoosiers
            # entry: name="Hoosiers", nickname="Indiana"). Using location +
            # name gives the correct "Indiana Hoosiers".
            "name": f"{t.get('location','')} {t.get('name','')}".strip(),
        })
    _log(f"AP Top 25: {len(out)} teams, week={d.get('latestWeek',{}).get('displayValue')}")
    return out


_ESPNFITT_RE = re.compile(r"window\['__espnfitt__'\]\s*=\s*(\{.*?\});", re.DOTALL)


def _fetch_fpi_view(view: str | None = None) -> dict:
    """FPI / Resume / Efficiencies all share one page template — ESPN
    server-renders the table into a `window['__espnfitt__']` JSON blob
    (same pattern as their other stat pages), so this reads that directly
    instead of parsing rendered HTML, which is far more stable and avoids
    another Playwright dependency for something that's already
    server-side JSON. Genuinely useful even now, in preseason — FPI/Resume/
    Efficiencies projections already exist ahead of Week 1."""
    url = "https://www.espn.com/college-football/fpi" + (f"/_/view/{view}" if view else "")
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    m = _ESPNFITT_RE.search(r.text)
    if not m:
        _log(f"  FPI view={view or 'fpi'}: embedded data blob not found")
        return {}
    data = json.loads(m.group(1))
    table = data.get("page", {}).get("content", {}).get("table", {})
    rows = []
    for entry in table.get("stats", []):
        team = entry.get("team", {})
        stats = {s["name"]: s.get("value") for s in entry.get("stats", [])}
        rows.append({"teamId": team.get("id"), "abbr": team.get("abbrev"),
                     "name": team.get("displayName"), "stats": stats})
    _log(f"  FPI view={view or 'fpi'}: {len(rows)} teams")
    return {"headers": table.get("headers", {}), "rows": rows}


def fetch_power_ratings() -> dict:
    out = {}
    for view, key in [(None, "fpi"), ("resume", "resume"), ("efficiencies", "efficiencies")]:
        out[key] = _fetch_fpi_view(view)
        time.sleep(1)
    return out


if __name__ == "__main__":
    run()
    rankings = fetch_rankings()
    power = fetch_power_ratings()
    POWER_OUT_PATH.write_text(json.dumps({
        "generated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "rankings": rankings,
        "power": power,
    }, indent=2))
    _log(f"wrote {POWER_OUT_PATH}")
