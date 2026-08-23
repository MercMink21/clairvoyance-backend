#!/usr/bin/env python3
"""
scrape_soccer_standings.py — Daily standings snapshot for all 6 tracked
soccer leagues (Champions League, Premier League, La Liga, Bundesliga,
MLS, Serie A).

Standalone script, same convention as scrape_opta_stats.py (no import
dependency on clairvoyance_update.py). Writes docs/soccer_standings.json
in the exact shape the frontend's own _fetchLeagueStandings() (docs/
app.html) already produces, so it can seed the same _leagueStandCache
that function's live browser fetch populates. _socStandingsFactor()
reads from that cache -- until this script existed, the only thing that
ever filled it was a live fetch that only fires when a user opens that
specific league's matches tab this session, so a user who goes straight
to picks/props got a silently-empty cache. This gives every session a
same-day standings snapshot at boot, before any live fetch happens; the
frontend's own live fetch still overwrites it with fresher data the
moment a user actually opens a matches tab.

Usage:
  python3 scripts/scrape_soccer_standings.py            # scrape + write, no push
  python3 scripts/scrape_soccer_standings.py --push     # scrape + write + commit + push
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
OUT = ROOT / "docs" / "soccer_standings.json"

ESPN_SOCCER_LEAGUES: dict[str, dict] = {
    "cl":   {"name": "Champions League", "espn": "UEFA.champions"},
    "pl":   {"name": "Premier League",   "espn": "eng.1"},
    "liga": {"name": "La Liga",          "espn": "esp.1"},
    "bl":   {"name": "Bundesliga",       "espn": "ger.1"},
    "mls":  {"name": "MLS",              "espn": "usa.1"},
    "ita":  {"name": "Serie A",          "espn": "ita.1"},
}


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def fetch_standings(espn_league: str) -> list[dict]:
    r = requests.get(
        f"https://site.api.espn.com/apis/v2/sports/soccer/{espn_league}/standings",
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    rows: list[dict] = []
    for child in (data.get("children") or [data]):
        for entry in ((child or {}).get("standings") or {}).get("entries") or []:
            team = entry.get("team") or {}
            stats = {s.get("name"): s.get("value") for s in (entry.get("stats") or [])}
            logos = team.get("logos") or []
            rows.append({
                "name": team.get("displayName"),
                "abbr": team.get("abbreviation"),
                "logo": logos[0].get("href") if logos else None,
                "mp": stats.get("gamesPlayed", 0) or 0,
                "w":  stats.get("wins", 0) or 0,
                "d":  stats.get("ties", 0) or 0,
                "l":  stats.get("losses", 0) or 0,
                "gf": stats.get("pointsFor", 0) or 0,
                "ga": stats.get("pointsAgainst", 0) or 0,
                "gd": stats.get("pointDifferential", 0) or 0,
                "pts": stats.get("points", 0) or 0,
            })
    rows.sort(key=lambda r: (-r["pts"], -r["gd"], -r["gf"]))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true")
    args = ap.parse_args()

    result: dict[str, list[dict]] = {}
    for key, cfg in ESPN_SOCCER_LEAGUES.items():
        try:
            rows = fetch_standings(cfg["espn"])
            result[key] = rows
            log(f"{cfg['name']}: {len(rows)} teams")
        except Exception as exc:
            log(f"{cfg['name']}: FAILED {exc}")
            result[key] = []
        time.sleep(0.5)

    if not any(result.values()):
        log("no data for any league -- not writing")
        sys.exit(1)

    OUT.write_text(json.dumps(result, indent=2))
    log(f"wrote {OUT}")

    if args.push:
        subprocess.run(["git", "add", "docs/soccer_standings.json"], cwd=ROOT, check=True)
        commit = subprocess.run(
            ["git", "commit", "-m", "chore: refresh soccer standings snapshot"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if commit.returncode != 0:
            log("nothing to commit")
            return
        for attempt in range(5):
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=ROOT, capture_output=True)
            push = subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, capture_output=True, text=True)
            if push.returncode == 0:
                log("pushed")
                return
            log(f"push attempt {attempt+1}/5 failed, retrying: {push.stderr.strip()[:160]}")
            time.sleep(3 + attempt * 2)
        raise RuntimeError("git push failed after 5 retries")


if __name__ == "__main__":
    main()
