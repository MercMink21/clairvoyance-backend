#!/usr/bin/env python3
"""
generate_social_cards.py — automated export of the social-tab canvas cards
(Track Record, Sport Performance, League Performance, and — when a known
event window is configured — Event Performance), emailed daily for easy
same-day posting.

The cards themselves are rendered client-side by JS canvas code in
docs/app.html (_genCombinedTrackGraphic, _genSportPerfGraphic,
_genLeaguePerfGraphic, _exportEventPerfCard) — there's no server-side
equivalent, and duplicating that drawing logic in Python would just be a
second thing to keep in sync with every visual tweak made to the real
cards. Instead this drives a headless Chromium (Playwright, already a
project dependency for Linemate scraping) against the LIVE deployed app,
so whatever the cards actually look like in the browser is exactly what
gets emailed.

Two problems a naive "just load the page and click export" approach hits,
both handled below:
  1. A fresh headless browser has empty localStorage — the real bet ledger
     only exists in Supabase (mirrored from the user's own browser) and in
     whichever browser they've actually used the app in. Fixed by fetching
     the real ledger from Supabase's REST API (in-page, using the same
     publishable/anon key already embedded in app.html) and replaying it
     into localStorage via the page's own saveP() before rendering.
  2. The export functions trigger a real browser file download
     (_saveCanvas creates an <a download> and clicks it). _saveCanvas
     itself lives inside a closure, not on window, so it can't be
     monkey-patched from outside. So instead of fighting that, this just
     lets the real download happen and captures it via Playwright's
     native download interception.

Cadence — one run per day, but the day's date decides what extra content
rides along with the standard daily post:
  - Every day:      Track Record + Sport/League Performance (YESTERDAY),
                     all 3 as static cards, plus a daily stats-reveal video
                     (rotates visual style by weekday) and a Sport
                     Performance breakdown video — the breakdown video only
                     sends when there's real per-sport data to show
                     (relevancy guard: no data, no video, rather than an
                     empty/misleading one).
  - Sundays:        + a weekly recap (ROLLING 7D) — bigger "7-day roundup"
  - 1st of month:   + a monthly recap (LAST MONTH)
  - January 1st:    + a year-in-review post covering Jan 1 - Dec 31 of the
                     year that just ended. Computed directly from the real
                     ledger's date field (the underlying app has no
                     built-in "calendar year" period the way it has
                     YESTERDAY/ROLLING 7D/LAST MONTH, so this bypasses that
                     system and filters bets by date range itself) - video
                     only, no static cards (same reason).
  - Every 5th day:  + one bonus content video, cycling through the
                     ROTATION_CONTENT list (grading system, subscription
                     tiers, and the 3 educational topics) - deterministic
                     from the calendar date, not stored state, so it can't
                     drift or double-fire.
  - Configured event end dates (see EVENTS below): + an Event Performance
    card for that tournament/season, the day after it ends

EVENTS is empty by default — Event Performance cards need a real
tournament name/date window, and there's no way to auto-detect "this
tournament just ended" from the data alone. Add entries as they're known
(see the EVENTS docstring below for the exact shape).

Usage:
  python3 scripts/generate_social_cards.py            # generate + email
  python3 scripts/generate_social_cards.py --no-email # generate only, save to /tmp
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

APP_URL = "https://mercmink21.github.io/clairvoyance-backend/app.html"
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SOCIAL_CARD_EMAIL_TO = os.environ.get("SOCIAL_CARD_EMAIL_TO", "")
ROOT = Path(__file__).resolve().parent.parent
# Lives under docs/ (not data/) so the live app can fetch it directly the
# same way it fetches docs/mls_opta_stats.json — this is both the git-
# committed source of truth and the file the home page's "PICK OF DAY"
# tile reads over HTTP.
PICK_OF_DAY_PATH = ROOT / "docs" / "pick_of_day.json"

# ESPN scoreboard path per sport/league tag, keyed exactly the way
# _epGatherLegs() tags its legs (see docs/app.html) — used to auto-settle
# yesterday's pick against the real final score. Tags with no entry here
# (ATP/WTA — different API entirely; WC26 — one-off schedule, not a
# scoreboard feed) simply can't be auto-settled and stay pending.
ESPN_SPORT_PATHS = {
    "MLB": "baseball/mlb", "NBA": "basketball/nba", "WNBA": "basketball/wnba",
    "NHL": "hockey/nhl", "NFL": "football/nfl", "CFB": "football/college-football",
    "CBB": "basketball/mens-college-basketball", "NCAAH": "hockey/mens-college-hockey",
    "BL": "soccer/ger.1", "LIGA": "soccer/esp.1", "MLS": "soccer/usa.1",
    "PL": "soccer/eng.1", "SERIEA": "soccer/ita.1", "CL": "soccer/UEFA.champions",
}

# Known tournament/season windows to auto-post an Event Performance card
# for, the day after they end. Add entries as they're known — each is
# {"name": <exact string to show on the card>, "start": "YYYY-MM-DD",
# "end": "YYYY-MM-DD", "leagues": [<league filter labels, matching
# LEAGUE_FILTER_LABELS in app.html, or [] for no filter / all activity>]}.
EVENTS: list[dict] = [
    {"name": "WIMBLEDON 2026", "start": "2026-06-29", "end": "2026-07-12", "leagues": ["ATP", "WTA"]},
    {"name": "WORLD CUP 2026", "start": "2026-06-11", "end": "2026-07-19", "leagues": ["World Cup"]},
    {"name": "CINCINNATI OPEN 2026", "start": "2026-08-12", "end": "2026-08-23", "leagues": ["ATP", "WTA"]},
    {"name": "US OPEN 2026", "start": "2026-08-04", "end": "2026-09-13", "leagues": ["ATP", "WTA"]},
    # Still needed, not guessed: exact 2026 dates for ATP/WTA Finals, end
    # of NFL/CFB season, start of NHL/NBA seasons aren't "end of window"
    # events so don't belong here, and end of MLB playoffs (World Series
    # date TBD). Add each with real dates once known.
]

# Bonus content that isn't tied to daily performance data — cycles once
# every 5 calendar days, deterministically (days-since-epoch // 5), so it
# never needs stored state and can't double-fire or drift out of sync.
ROTATION_EPOCH = datetime(2026, 7, 1, tzinfo=timezone.utc)
ROTATION_CONTENT = ["grading", "subscription", "covers"]
# Static "what Clairvoyance covers" asset — a real pre-made card (not
# generated), attached as-is rather than turned into a video.
COVERS_CARD_PATH = ROOT / "scripts" / "assets" / "covers_card.png"
ROTATION_DAYS = 5


def get_rotation_item(today_mt: datetime) -> str | None:
    days_since = (today_mt.date() - ROTATION_EPOCH.date()).days
    if days_since < 0 or days_since % ROTATION_DAYS != 0:
        return None
    idx = (days_since // ROTATION_DAYS) % len(ROTATION_CONTENT)
    return ROTATION_CONTENT[idx]


CARD_JOBS = [
    ("cv-track-record-", "_genCombinedTrackGraphic()", "Track Record"),
    ("cv-sport-perf-",   "_genSportPerfGraphic()",     "Sport Performance"),
    ("cv-league-perf-",  "_genLeaguePerfGraphic()",    "League Performance"),
]


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _mt_now() -> datetime:
    # Good enough for day-of-week/day-of-month cadence decisions — this
    # project's other scheduled workflows are all pinned to MDT (UTC-6)
    # rather than doing real DST-aware conversion, same convention here.
    return datetime.now(timezone.utc) - timedelta(hours=6)


def load_pick_of_day_ledger() -> list[dict]:
    if PICK_OF_DAY_PATH.exists():
        try:
            return json.loads(PICK_OF_DAY_PATH.read_text())
        except Exception:
            pass
    return []


def save_pick_of_day_ledger(ledger: list[dict]) -> None:
    PICK_OF_DAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    PICK_OF_DAY_PATH.write_text(json.dumps(ledger, indent=2))


def _ml_to_dec(ml) -> float:
    m = float(str(ml).replace("+", ""))
    return m / 100 + 1 if m > 0 else 100 / abs(m) + 1


def _espn_scoreboard_result(entry: dict) -> str | None:
    """Looks up entry's matchup in ESPN's scoreboard for its sport+date and
    returns 'win'/'loss' if the game is final and the picked side is
    unambiguously identifiable, else None (left pending — never guess)."""
    path = ESPN_SPORT_PATHS.get(entry["sport"])
    if not path:
        return None
    date_str = entry["date"].replace("-", "")
    try:
        resp = requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard",
            params={"dates": date_str}, timeout=15,
        )
        resp.raise_for_status()
        events = resp.json().get("events", [])
    except Exception as exc:
        log(f"  ESPN scoreboard lookup failed for {entry['sport']} {entry['date']}: {exc}")
        return None

    picked_abbr = entry.get("pickedAbbr", "")
    for ev in events:
        comp = (ev.get("competitions") or [{}])[0]
        state = ((comp.get("status") or {}).get("type") or {}).get("state")
        if state != "post":
            continue
        competitors = comp.get("competitors") or []
        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not home or not away:
            continue
        h_abbr = ((home.get("team") or {}).get("abbreviation") or "").upper()
        a_abbr = ((away.get("team") or {}).get("abbreviation") or "").upper()
        if picked_abbr.upper() not in (h_abbr, a_abbr):
            continue
        picked_team = home if picked_abbr.upper() == h_abbr else away
        other_team = away if picked_team is home else home
        if picked_team.get("winner") is True:
            return "win"
        if other_team.get("winner") is True:
            return "loss"
        # Final but neither side flagged a winner — a genuine tie/push,
        # not something to force into win/loss.
        return None
    return None


# Only the stat categories _mlbGenerateDailyProps() actually deals in
# real props for (see docs/app.html's addSP/hitter blocks) map to a
# boxscore field here — anything else (a stat this pipeline never
# generates) is left pending rather than guessed at.
_MLB_STAT_FIELDS = {"K": ("pitching", "strikeOuts"), "HR": ("batting", "homeRuns"), "H": ("batting", "hits")}


def _mlb_prop_result(entry: dict) -> str | None:
    """Grades an MLB O/U player-prop pick against the real MLB Stats API
    boxscore for that date. Looks up the game by matching both team
    abbreviations from the pick's matchup, then finds the named player in
    either team's boxscore and compares their actual stat line to the
    posted line. Returns None (left pending) if the game isn't found,
    hasn't gone final, the player isn't in the boxscore, or the stat
    category isn't one this pipeline knows how to read — never a guess."""
    stat_field = _MLB_STAT_FIELDS.get(entry.get("stat", ""))
    if not stat_field:
        return None
    try:
        away_abbr, home_abbr = [t.strip() for t in entry["matchup"].split("@")]
    except Exception:
        return None
    try:
        resp = requests.get(
            "https://statsapi.mlb.com/api/v1/schedule",
            params={"sportId": 1, "date": entry["date"]}, timeout=15,
        )
        resp.raise_for_status()
        dates = resp.json().get("dates", [])
    except Exception as exc:
        log(f"  MLB schedule lookup failed for {entry['date']}: {exc}")
        return None

    game_pk = None
    for d in dates:
        for g in d.get("games", []):
            if (g.get("status") or {}).get("abstractGameState") != "Final":
                continue
            teams = g.get("teams") or {}
            h_abbr = ((teams.get("home") or {}).get("team") or {}).get("abbreviation", "")
            a_abbr = ((teams.get("away") or {}).get("team") or {}).get("abbreviation", "")
            if h_abbr == home_abbr and a_abbr == away_abbr:
                game_pk = g.get("gamePk")
                break
        if game_pk:
            break
    if not game_pk:
        return None

    try:
        box_resp = requests.get(f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore", timeout=15)
        box_resp.raise_for_status()
        box = box_resp.json()
    except Exception as exc:
        log(f"  MLB boxscore lookup failed for game {game_pk}: {exc}")
        return None

    cat, field = stat_field
    player_lower = entry["player"].lower()
    for side in ("home", "away"):
        players = ((box.get("teams") or {}).get(side) or {}).get("players", {})
        for pdata in players.values():
            name = ((pdata.get("person") or {}).get("fullName") or "")
            if name.lower() != player_lower:
                continue
            stats = ((pdata.get("stats") or {}).get(cat) or {})
            if field not in stats:
                return None
            val = stats[field]
            line = entry["line"]
            if val == line:
                return "push"
            cleared = val > line if entry.get("over") else val < line
            return "win" if cleared else "loss"
    return None


def settle_pending_picks(ledger: list[dict]) -> list[dict]:
    """Checks every still-pending ledger entry against the real final
    score/boxscore and updates it in place. Entries whose sport/type has
    no verifiable data source (tennis, one-off tournaments, unrecognized
    prop stat) or whose game hasn't gone final yet are left untouched —
    settlement only ever writes a result it can verify, never a guess."""
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    for entry in ledger:
        if entry.get("outcome") != "pending":
            continue
        result = _mlb_prop_result(entry) if entry.get("type") == "PROP" else _espn_scoreboard_result(entry)
        if result:
            entry["outcome"] = result
            entry["settledAt"] = now_ms
            log(f"  Settled pick-of-day {entry['date']} {entry['pick']}: {result.upper()}")
    return ledger


def pick_of_day_stats(ledger: list[dict]) -> dict:
    settled = [e for e in ledger if e.get("outcome") in ("win", "loss")]
    w = sum(1 for e in settled if e["outcome"] == "win")
    l = len(settled) - w
    units = sum((_ml_to_dec(e["ml"]) - 1 if e["outcome"] == "win" else -1) for e in settled)
    return {"w": w, "l": l, "pct": (w / len(settled) if settled else None), "units": units}


# Matches SPORT_LEAGUES in docs/app.html's Sport Performance card exactly
# — shown as the sub-line under each sport row in the breakdown videos.
SPORT_LEAGUES = {
    "BASEBALL": "MLB",
    "BASKETBALL": "NBA, WNBA, CBB",
    "FOOTBALL": "NFL, CFB",
    "HOCKEY": "NHL, KHL, SHL, LIIGA",
    "SOCCER": "Bundesliga, Champions League, La Liga, MLS, Premier League, Serie A",
    "TENNIS": "ATP, WTA",
}


def _strip_stale_hockey(stats: dict) -> None:
    """One-time correction for 5 leftover test-fixture bets (ids "b0"-"b4",
    no real team/matchup data, dated July 10-14 2026) sitting in the real
    Supabase ledger and tagged NHL -- there's no actual hockey being
    played right now, so a "HOCKEY 1-1" (or similar) row was showing up
    in the monthly recap purely from that stale test data. User asked to
    patch the video output rather than delete the underlying rows, so
    this drops the HOCKEY row from the Sport Performance breakdown and
    backs 1 win + 1 loss out of the monthly total here, in place, before
    the monthly video/caption get built. Mutates stats in place; no-ops
    once the HOCKEY row disappears from bySport (e.g. once real hockey
    resumes and there's actual data to show, or the row rolls out of the
    monthly window on its own)."""
    if not stats or not stats.get("bySport"):
        return
    hockey = next((s for s in stats["bySport"] if s.get("label") == "HOCKEY"), None)
    if not hockey:
        return
    stats["bySport"] = [s for s in stats["bySport"] if s.get("label") != "HOCKEY"]
    if stats.get("w") is not None and stats.get("l") is not None:
        new_w, new_l = max(0, stats["w"] - 1), max(0, stats["l"] - 1)
        settled = new_w + new_l
        stats["w"], stats["l"] = new_w, new_l
        stats["pct"] = (new_w / settled) if settled else None
        if stats.get("units") is not None:
            # Same unit-normalized pnl convention as everywhere else
            # (win: decOdds-1, loss: -1) -- the 5 fake bets all used
            # decOdds:1.9, so back out exactly that pnl rather than a
            # generic +/-1u guess.
            stats["units"] = stats["units"] - (0.9 - 1.0)
    log("  Stripped stale HOCKEY test data from monthly stats (-1W-1L)")


def _breakdown_rows(stats: dict) -> list[dict]:
    """Builds populateRows()-shaped rows (label/sub/record/pct/units) from
    a stats dict's bySport list, with a TOTAL row appended — shared by
    daily/weekly/monthly/yearly so they all look identical."""
    by_sport = stats.get("bySport") or []
    rows = [
        {"label": s["label"], "sub": SPORT_LEAGUES.get(s["label"], ""),
         "record": f"{s['w']}W-{s['l']}L", "pct": _fmt_pct(s.get("pct")),
         "units": _fmt_units(s.get("units")), "isTotal": False}
        for s in by_sport
    ]
    rows.append({"label": "TOTAL", "record": f"{stats['w']}W-{stats['l']}L", "pct": _fmt_pct(stats.get("pct")),
                 "units": _fmt_units(stats.get("units")), "isTotal": True})
    return rows


def _fmt_date_range(start: datetime, end: datetime) -> str:
    """"July 26 – August 1, 2026" style range, correct whether the span
    stays inside one month or crosses a month/year boundary. The old
    inline version always used the start date's month for both ends
    (f"{start:%B %-d}–{end:%-d, %Y}"), which reads fine for a same-month
    week ("July 26–31, 2026") but silently mangled any week spanning two
    months into something like "July 26 – 1, 2026" (missing "August"
    entirely) instead of "July 26 – August 1, 2026"."""
    if start.year != end.year:
        return f"{start.strftime('%B %-d, %Y')} – {end.strftime('%B %-d, %Y')}"
    if start.month != end.month:
        return f"{start.strftime('%B %-d')} – {end.strftime('%B %-d, %Y')}"
    return f"{start.strftime('%B %-d')}–{end.strftime('%-d, %Y')}"


def _fmt_units(units: float | None) -> str:
    if units is None:
        return "N/A"
    return f"{'+' if units >= 0 else ''}{units:.1f}u"


def _fmt_pct(pct: float | None) -> str:
    return f"{pct*100:.1f}%" if pct is not None else "N/A"


def generate_cards(page, out_dir: Path, period: str, prefix_extra: str = "") -> tuple[list[Path], dict | None]:
    """Generate the standard 3-card set for a given period ('YESTERDAY',
    'ROLLING 7D', 'LAST MONTH', etc). prefix_extra distinguishes filenames
    across multiple generations in the same run (e.g. daily + weekly on a
    Sunday)."""
    saved: list[Path] = []
    page.evaluate(
        f"() => {{ renderTrackRecord._sportPeriod = '{period}'; renderTrackRecord._leaguePeriod = '{period}'; }}"
    )
    for _, js_call, label in CARD_JOBS:
        log(f"Rendering {label} card ({period})…")
        with page.expect_download(timeout=15000) as download_info:
            page.evaluate(f"async () => {{ await {js_call}; }}")
        download = download_info.value
        fname = f"{prefix_extra}{download.suggested_filename}" if prefix_extra else download.suggested_filename
        path = out_dir / fname
        download.save_as(str(path))
        saved.append(path)
        log(f"  saved {path} ({path.stat().st_size/1024:.0f} KB)")

    stats = page.evaluate(
        """
        () => {
          const d = window._cvSportPeriodData;
          if (!d || !d.totalP) return null;
          // d.bySport[sport] is the RAW array of bet objects for that
          // sport, not a pre-computed summary — the card renderer computes
          // w/l/pct inline via its own cP() closure, which isn't reachable
          // from here, so replicate that same win/loss/settled-only logic
          // directly against the raw array.
          let lockedCount = 0;
          const bySport = (d.sportList || []).map(s => {
            const bets = (d.bySport && d.bySport[s]) || [];
            lockedCount += bets.length;
            const settled = bets.filter(p => p.outcome === 'win' || p.outcome === 'loss');
            const w = settled.filter(p => p.outcome === 'win').length;
            const l = settled.length - w;
            const units = settled.reduce((a, p) => {
              if (p.outcome === 'win') return a + (parseFloat(p.decOdds) || 2) - 1;
              if (p.outcome === 'loss') return a - 1;
              return a;
            }, 0);
            return { label: s, w, l, n: settled.length, pct: settled.length ? w / settled.length : null, units };
          }).filter(s => s.n);
          return {
            w: d.totalP.w, l: d.totalP.l, pct: d.totalP.pct, units: d.totalP.units,
            lockedCount, bySport,
          };
        }
        """
    )
    return saved, stats


def generate_event_card(page, out_dir: Path, event: dict) -> Path | None:
    log(f"Rendering Event Performance card for {event['name']}…")
    leagues_js = json.dumps(event.get("leagues") or [])
    page.evaluate(
        f"""
        () => {{
          renderTrackRecord._eventName = {json.dumps(event['name'])};
          renderTrackRecord._eventStart = {json.dumps(event['start'])};
          renderTrackRecord._eventEnd = {json.dumps(event['end'])};
          renderTrackRecord._eventFilters = {leagues_js};
        }}
        """
    )
    page.wait_for_timeout(200)
    try:
        with page.expect_download(timeout=15000) as download_info:
            page.evaluate("async () => { await _exportEventPerfCard(); }")
    except Exception as exc:
        log(f"  Event Performance card for {event['name']} failed to generate: {exc}")
        return None
    download = download_info.value
    path = out_dir / download.suggested_filename
    download.save_as(str(path))
    log(f"  saved {path} ({path.stat().st_size/1024:.0f} KB)")
    return path


def get_event_stats(page) -> dict | None:
    """Win/loss/pct/units for the event window just rendered by
    generate_event_card() — reads window._cvEventPeriodData.totalP, which
    the card renderer already computed and left on the page. Note: the
    cP() in scope here (docs/app.html ~line 18044) names the units field
    "units", not "u" like the other cP() defined near line 11609 — they're
    separate closures, easy to mix up (this was a real bug: reading t.u
    silently returned undefined -> "N/A" in every event caption/video)."""
    return page.evaluate(
        """
        () => {
          const d = window._cvEventPeriodData;
          if (!d || !d.totalP) return null;
          const t = d.totalP;
          return { w: t.w, l: t.l, n: t.n, pct: t.pct, units: t.units };
        }
        """
    )


# Mirrors ESPN_SPORT_PATHS' keys — only sports/leagues with a real
# scoreboard feed to auto-settle against are eligible to become the
# tracked Pick of the Day. (Tennis/WC26 legs can still appear in the
# Parlay tab's own pools — they're just not selected here, since an
# unsettleable pick would sit "pending" on the home-page tracker forever.)
_ELIGIBLE_POTD_SPORTS = [
    "MLB", "NBA", "WNBA", "NHL", "NFL", "CFB", "CBB", "NCAAH",
    "BL", "LIGA", "MLS", "PL", "SERIEA", "CL",
]
_POTD_BROAD_SPORT = {
    "MLB": "BASEBALL", "NBA": "BASKETBALL", "WNBA": "BASKETBALL", "CBB": "BASKETBALL",
    "NHL": "HOCKEY", "NCAAH": "HOCKEY", "NFL": "FOOTBALL", "CFB": "FOOTBALL",
    "BL": "SOCCER", "LIGA": "SOCCER", "MLS": "SOCCER", "PL": "SOCCER", "SERIEA": "SOCCER", "CL": "SOCCER",
}


# MLB player-prop legs (the only PROP-type legs _epGatherLegs produces)
# encode player/stat/line/over only inside their display name, e.g.
# "MLB Aaron Judge O1.5 HR" — parsed back out here so the ledger entry
# has structured fields _mlb_prop_result() can grade against a real
# boxscore. Matches _mlbGenerateDailyProps()'s "MLB "+player+' '+O/U+line+' '+stat format exactly.
_MLB_PROP_RE = re.compile(r"^MLB (.+) ([OU])([\d.]+) (\S+)$")


def get_free_pick(page) -> dict | None:
    """The single highest-probability *auto-gradable* pick across every
    sport/league for today — ML/game legs or MLB O/U player-prop legs,
    whichever the engine's own leg-gathering logic (_epGatherLegs, the
    same function that feeds the Parlay tab's "engine recommended"
    slates) ranks highest by win probability. Restricted to sports/leg
    types this pipeline can actually verify the next day: GAME/ML legs
    whose sport has a real ESPN scoreboard feed (_ELIGIBLE_POTD_SPORTS),
    or MLB PROP legs (auto-settled against the MLB Stats API boxscore) —
    an unsettleable pick would just sit "pending" forever, which defeats
    the point of "accumulating" record/win%/units. Warms every league's
    game/odds cache first (the exact same warmup renderEngineParlays()
    itself runs) so the pool spans all sports, not just whatever this
    headless session happened to touch already. Returns None if nothing
    eligible clears the engine's own probability floor for that day — no
    fake "pick of the day" gets sent."""
    result = page.evaluate(
        """
        async (eligibleSports) => {
          const warmups = [];
          if (typeof renderGenericWeek === 'function') {
            warmups.push(renderGenericWeek('cfb-week-list', 'football/college-football', 'CFB').catch(() => {}));
            warmups.push(renderGenericWeek('nfl-week-list', 'football/nfl', 'NFL').catch(() => {}));
            warmups.push(renderGenericWeek('cbb-week-list', 'basketball/mens-college-basketball', 'CBB').catch(() => {}));
            warmups.push(renderGenericWeek('ncaah-matches-list', 'hockey/mens-college-hockey', 'NCAAH').catch(() => {}));
          }
          if (typeof renderLeagueMatches === 'function') {
            ['bl', 'liga', 'mls', 'pl', 'ita', 'cl'].forEach(k => warmups.push(renderLeagueMatches(k).catch(() => {})));
          }
          if (!(window.ESPN_GAMES && window.ESPN_GAMES.length) && typeof loadGames === 'function') {
            warmups.push(loadGames().catch(() => {}));
          }
          if (typeof renderWNBAWeek === 'function') {
            try { renderWNBAWeek(); } catch (e) {}
          }
          await Promise.allSettled(warmups);
          if (typeof _epGatherLegs !== 'function') return null;
          // MLB GAME legs are excluded from _epGatherLegs()'s result here
          // and rebuilt below straight from mlbEns() (the Monte
          // Carlo/Bayesian/ELO ensemble) as the default probability
          // source for every MLB game, live odds or not — not just a
          // fallback for when the odds feed is empty. mlbEns() already
          // blends in live market odds at 30% weight when present, so
          // this doesn't discard real odds data when it exists, it just
          // stops being fully dependent on that feed ever being
          // populated. Every other sport/league (and MLB PROP legs)
          // still come from _epGatherLegs() unchanged. This is safe ONLY
          // here, never in _epGatherLegs() itself — that function also
          // drives the live Parlay tab on every user's page load, and a
          // single mlbEns() call measured 3s+ against live team data;
          // looping that across a full slate there froze the page during
          // testing. This picker runs once a day, headless, with nobody
          // waiting on it, so it can afford the cost — capped at 15
          // games and a reduced 600-sim pass (vs the normal 5000) to
          // keep total runtime bounded (~6s worst case).
          const legs = _epGatherLegs().filter(l => !(l.sport === 'MLB' && l.type === 'GAME')).filter(l =>
            (l.type === 'GAME' && eligibleSports.includes(l.sport)) ||
            (l.type === 'PROP' && l.sport === 'MLB')
          );
          if (typeof mlbEns === 'function' && typeof p2ml === 'function') {
            const mlbGames = (window.ESPN_GAMES || window._mlbGames || [])
              .filter(g => { const s = (g.status || '').toUpperCase(); return g.hA && g.awA && s !== 'FINAL' && s !== 'F'; })
              .slice(0, 15);
            const _grade = p => p >= 0.67 ? 'PREMIUM' : p >= 0.62 ? 'OPTIMAL' : p >= 0.55 ? 'LEAN' : 'SKIP';
            mlbGames.forEach(g => {
              const ens = mlbEns(g.hA, g.awA, g, 600);
              const hP = ens.p, aP = 1 - hP;
              const hmlRaw = g.hML || p2ml(hP), amlRaw = g.aML || p2ml(aP);
              const matchup = g.awA + ' @ ' + g.hA;
              if (hP >= 0.58 && hP >= aP) {
                legs.push({ name: 'MLB ML ' + g.hA, ml: hmlRaw, prob: hP, matchup, sport: 'MLB', type: 'GAME', grade: _grade(hP) });
              } else if (aP >= 0.58 && aP > hP) {
                legs.push({ name: 'MLB ML ' + g.awA, ml: amlRaw, prob: aP, matchup, sport: 'MLB', type: 'GAME', grade: _grade(aP) });
              }
            });
          }
          // WNBA GAME legs, same principle as MLB above: rebuilt from
          // window._wnbaGameData's already-computed wnbaEns() fields
          // (hP/aP) instead of _epGatherLegs()'s own re-derivation via
          // _epImp(g.hML) — g.hML there is itself already synthesized
          // from hP when no live odds exist (see WPAR push in
          // renderWNBAWeek), so this isn't fixing a missing-data gap the
          // way MLB needed; it just uses the model probability directly
          // rather than round-tripping it through a synthesized American-
          // odds price and back. No extra simulation cost — hP/aP are
          // already computed by the renderWNBAWeek() warmup call above.
          const wnbaLegs = legs.filter(l => l.sport === 'WNBA');
          if (window._wnbaGameData && window._wnbaGameData.length) {
            const _gradeW = p => p >= 0.67 ? 'PREMIUM' : p >= 0.62 ? 'OPTIMAL' : p >= 0.55 ? 'LEAN' : 'SKIP';
            const seen = new Set(wnbaLegs.map(l => l.matchup));
            window._wnbaGameData.forEach(g => {
              const matchup = g.aab + '@' + g.hab;
              if (seen.has(matchup)) return;
              const hP = g.hP, aP = g.aP != null ? g.aP : 1 - hP;
              if (hP == null) return;
              if (hP >= 0.58 && hP >= aP) {
                legs.push({ name: 'WNBA ML ' + g.hab, ml: g.hML, prob: hP, matchup, sport: 'WNBA', type: 'GAME', grade: _gradeW(hP) });
              } else if (aP >= 0.58 && aP > hP) {
                legs.push({ name: 'WNBA ML ' + g.aab, ml: g.aML, prob: aP, matchup, sport: 'WNBA', type: 'GAME', grade: _gradeW(aP) });
              }
            });
          }
          if (!legs.length) return null;
          const best = legs.reduce((a, b) => (b.prob > a.prob ? b : a));
          const out = {
            name: best.name, matchup: best.matchup, sport: best.sport,
            type: best.type, prob: best.prob, ml: best.ml, grade: best.grade,
          };
          if (best.type === 'GAME') out.pickedAbbr = best.name.trim().split(' ').pop();
          return out;
        }
        """,
        _ELIGIBLE_POTD_SPORTS,
    )
    if result and result["type"] == "PROP":
        m = _MLB_PROP_RE.match(result["name"])
        if m:
            result["player"] = m.group(1)
            result["over"] = m.group(2) == "O"
            result["line"] = float(m.group(3))
            result["stat"] = m.group(4)
        else:
            # Couldn't parse the structured fields needed to grade this
            # prop — don't silently track an unsettleable pick.
            log(f"  Free pick was a PROP leg but didn't match expected format, skipping: {result['name']}")
            return None
    return result


def build_free_pick_caption(pick: dict) -> dict[str, str]:
    ig = (
        f"FREE PICK OF THE DAY\n\n{pick['matchup']}\n\n{pick['name']}\n\n"
        f"Engine grade: {pick['grade']}\n\n"
        f"This one's on the house — every pick graded, every result public, no cherry-picking.\n\n"
        f"Follow for daily signals, subscribe for exclusive graded picks, and intelligence briefs.\n\n"
        f"clairvoyanceengine.info\nIG @clairvoyanceengine\nX @clairvoyanceeng\n\n"
        f"#foryou #sportsbetting #bettingtips #bettingpicks #freepick"
    )
    x = (
        f"FREE PICK: {pick['name']}\n\n{pick['matchup']}\n\n"
        f"Engine grade: {pick['grade']}\n\n"
        f"clairvoyanceengine.info\n\n#sportsbetting #freepick"
    )
    return {"instagram": ig, "x": x}


def get_year_stats(page, year: int) -> dict:
    """Win/loss/pct/units for a full calendar year, computed directly from
    the real ledger's date field. The underlying app has no "calendar
    year" period option (only YESTERDAY/ROLLING 7D/LAST MONTH/etc via
    renderTrackRecord._sportPeriod), so this bypasses that system entirely
    rather than trying to force a year-long window through it. Same unit-
    normalized pnl convention as everywhere else (win: decOdds-1, loss:
    -1) so the units figure is directly comparable to daily/weekly/
    monthly numbers."""
    return page.evaluate(
        """
        (year) => {
          const start = year + '-01-01', end = year + '-12-31';
          const inYear = getP().filter(p => p.date && p.date >= start && p.date <= end);
          const settled = inYear.filter(p => p.outcome === 'win' || p.outcome === 'loss');
          const w = settled.filter(p => p.outcome === 'win').length;
          const l = settled.length - w;
          const units = settled.reduce((a, p) => {
            if (p.outcome === 'win') return a + (parseFloat(p.decOdds) || 2) - 1;
            if (p.outcome === 'loss') return a - 1;
            return a;
          }, 0);
          // Same 6-broad-sport grouping the Sport Performance card itself
          // uses (_normSport is the app's own helper, confirmed reachable
          // globally). _broadSportOf is NOT reliably reachable from an
          // external page.evaluate() — on the live page it ends up nested
          // inside a scope that only the app's own internal functions can
          // see (confirmed via typeof check: _normSport is a global
          // function, _broadSportOf is undefined from outside) — so its
          // mapping table is inlined here instead of calling it directly.
          const _broadSport = (tag) => {
            const t = (tag || '').toUpperCase().trim();
            if (t === 'MLB') return 'BASEBALL';
            if (['NBA','WNBA','CBB','NCAAB'].includes(t)) return 'BASKETBALL';
            if (['NFL','CFB'].includes(t)) return 'FOOTBALL';
            if (['NHL','KHL','SHL','LIIGA','NCAAH'].includes(t)) return 'HOCKEY';
            if (['SOC','WC','WORLD_CUP','WORLDCUP','PL','LIGA','BL','MLS','CH'].includes(t)) return 'SOCCER';
            if (['ATP','WTA','TEN','TENNIS'].includes(t)) return 'TENNIS';
            return null;
          };
          const SPORT_ORDER = ['BASEBALL','BASKETBALL','FOOTBALL','HOCKEY','SOCCER','TENNIS'];
          const bucket = {}; SPORT_ORDER.forEach(s => bucket[s] = []);
          inYear.forEach(b => { const s = _broadSport(_normSport(b)); if (s && bucket[s]) bucket[s].push(b); });
          const bySport = SPORT_ORDER.map(s => {
            const bets = bucket[s];
            const settledS = bets.filter(p => p.outcome === 'win' || p.outcome === 'loss');
            const wS = settledS.filter(p => p.outcome === 'win').length;
            const lS = settledS.length - wS;
            const unitsS = settledS.reduce((a, p) => {
              if (p.outcome === 'win') return a + (parseFloat(p.decOdds) || 2) - 1;
              if (p.outcome === 'loss') return a - 1;
              return a;
            }, 0);
            return { label: s, w: wS, l: lS, n: settledS.length, pct: settledS.length ? wS / settledS.length : null, units: unitsS };
          }).filter(s => s.n);
          return { w, l, n: settled.length, pct: settled.length ? w / settled.length : null, units, lockedCount: inYear.length, bySport };
        }
        """,
        year,
    )


def run(out_dir: Path, force: set[str] | None = None) -> dict:
    from playwright.sync_api import sync_playwright

    force = force or set()
    out_dir.mkdir(parents=True, exist_ok=True)
    now_mt = _mt_now()
    yesterday_mt = now_mt - timedelta(days=1)
    # `force` (from --force, review-only) bypasses the date gate for a
    # given period without touching the real cadence for every other
    # day — e.g. forcing "weekly" for a one-off review doesn't also
    # force monthly/yearly, and doesn't change what fires on a normal
    # unforced run.
    is_sunday = now_mt.weekday() == 6 or "weekly" in force
    is_first_of_month = now_mt.day == 1 or "monthly" in force
    is_new_year = (now_mt.month == 1 and now_mt.day == 1) or "yearly" in force
    # Deterministic, days-since-epoch cadence (same pattern as
    # get_rotation_item) — no stored state, can't drift or double-fire.
    is_biweekly = (now_mt.date() - ROTATION_EPOCH.date()).days % 14 == 0 or "alltime" in force

    result = {"daily": None, "weekly": None, "monthly": None, "yearly": None, "events": [], "alltime": None}

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1400, "height": 1000}, accept_downloads=True)
        page = context.new_page()
        log(f"Loading {APP_URL} …")
        page.goto(APP_URL, wait_until="load", timeout=60000)
        page.wait_for_timeout(3000)

        bet_count = page.evaluate(
            """
            async () => {
              // PostgREST caps a single response at 1000 rows by default —
              // the real ledger is already past that, so an unpaginated
              // fetch here would silently undercount getP() (which feeds
              // both the cards and the milestone streak/count check).
              // Page through with the Range header until a batch comes
              // back short.
              const rows = [];
              let offset = 0;
              const page_size = 1000;
              while (true) {
                // outcome=neq._removed excludes soft-deleted rows (real
                // DELETEs are blocked by RLS, see _deleteBetsFromSupabase
                // in docs/app.html -- removal is a PATCH to outcome:
                // '_removed' on the row's own column, not inside raw,
                // which this headless pull never touched before, so a
                // "removed" test/bad bet kept showing up in every daily
                // video/breakdown indefinitely even after being wiped in
                // the live app.
                const r = await fetch(SUPABASE_URL + '/rest/v1/bets?select=raw&order=date.desc&outcome=neq._removed', {
                  headers: {
                    apikey: SUPABASE_KEY, Authorization: 'Bearer ' + SUPABASE_KEY,
                    Range: offset + '-' + (offset + page_size - 1),
                  }
                });
                if (!r.ok) return -1;
                const batch = await r.json();
                rows.push(...batch);
                if (batch.length < page_size) break;
                offset += page_size;
              }
              const preds = rows.map(x => x.raw).filter(Boolean);
              saveP(preds);
              return preds.length;
            }
            """
        )
        if bet_count is None or bet_count < 0:
            raise RuntimeError("Failed to load bet ledger from Supabase in-page — check SUPABASE_URL/KEY are still valid in app.html")
        log(f"Loaded {bet_count} real bets from Supabase into headless session")

        page.evaluate("() => { try { renderTrackRecord(); } catch(e) {} }")
        page.wait_for_timeout(400)
        page.evaluate("async () => { if (document.fonts && document.fonts.ready) await document.fonts.ready; }")

        # Daily (always)
        cards, stats = generate_cards(page, out_dir, "YESTERDAY")
        result["daily"] = {"cards": cards, "stats": stats}

        # Free pick of the day — highest win-probability leg across every
        # sport/league, from the same engine gathering logic behind the
        # Parlay tab's recommended slates.
        result["free_pick"] = get_free_pick(page)

        # Weekly (Sundays)
        if is_sunday:
            cards, stats = generate_cards(page, out_dir, "ROLLING 7D", prefix_extra="weekly-")
            result["weekly"] = {"cards": cards, "stats": stats}

        # Monthly (1st of month — covers the month that just ended)
        if is_first_of_month:
            cards, stats = generate_cards(page, out_dir, "LAST MONTH", prefix_extra="monthly-")
            result["monthly"] = {"cards": cards, "stats": stats}

        # Year in review (Jan 1 — covers the year that just ended)
        if is_new_year:
            year_stats = get_year_stats(page, now_mt.year - 1)
            result["yearly"] = {"stats": year_stats}

        # All Time (every 14 days) — a real period the app itself already
        # supports (renderTrackRecord._sportPeriod), generated the exact
        # same way as weekly/monthly. Since Launch retired (redundant
        # with All Time for this app's purposes).
        if is_biweekly:
            cards, stats = generate_cards(page, out_dir, "ALL TIME", prefix_extra="alltime-")
            result["alltime"] = {"cards": cards, "stats": stats}

        # Events — the day after a configured window ends
        for event in EVENTS:
            end_date = datetime.strptime(event["end"], "%Y-%m-%d").date()
            if yesterday_mt.date() == end_date:
                path = generate_event_card(page, out_dir, event)
                if path:
                    event_stats = get_event_stats(page)
                    result["events"].append({"event": event, "card": path, "stats": event_stats})

        browser.close()

    return result


def build_daily_caption(stats: dict | None, date_ref: datetime) -> dict[str, str]:
    # date_ref is always yesterday relative to the run — callers must pass
    # the actual reporting date (not "today"), so this line stays accurate
    # regardless of when the workflow happens to fire.
    date_str = date_ref.strftime("%B %-d, %Y")
    tally_line = ""
    if stats and stats.get("w") is not None:
        tally_line = (
            f"Final tally: {stats['w']}W-{stats['l']}L · {_fmt_pct(stats.get('pct'))} win rate · "
            f"{_fmt_units(stats.get('units'))}\n\n"
        )
    ig = (
        f"Yesterdays Performance\n\n{date_str}\n\nThis is Clairvoyance.\n\n{tally_line}"
        f"Every pick graded. Every line evaluated for edge. No guesswork.\n\n"
        f"Follow for daily signals, subscribe for exclusive graded picks, and intelligence briefs.\n\n"
        f"clairvoyanceengine.info\nIG @clairvoyanceengine\nX @clairvoyanceeng\n\n"
        f"#foryou #sportsbetting #bettingtips #bettingpicks"
    )
    x = (
        f"Yesterdays Performance\n\nThis is Clairvoyance.\n\n{tally_line}"
        f"clairvoyanceengine.info\n\n#sportsbetting #bettingtips #bettingpicks"
    )
    return {"instagram": ig, "x": x}


def build_weekly_caption(stats: dict | None, week_end: datetime) -> dict[str, str]:
    week_start = week_end - timedelta(days=6)
    range_str = _fmt_date_range(week_start, week_end)
    tally_line = ""
    if stats and stats.get("w") is not None:
        tally_line = (
            f"Final tally: {stats['w']}W-{stats['l']}L · {_fmt_pct(stats.get('pct'))} win rate · "
            f"{_fmt_units(stats.get('units'))}\n\n"
        )
    ig = (
        f"This Week in Review — {range_str}\n\nThis is Clairvoyance.\n\n{tally_line}"
        f"Seven days. Every pick graded, every line evaluated for edge. No guesswork.\n\n"
        f"Follow for daily signals, subscribe for exclusive graded picks, and intelligence briefs.\n\n"
        f"clairvoyanceengine.info\nIG @clairvoyanceengine\nX @clairvoyanceeng\n\n"
        f"#foryou #sportsbetting #bettingtips #bettingpicks #weeklyrecap"
    )
    x = (
        f"This Week in Review — {range_str}\n\nThis is Clairvoyance.\n\n{tally_line}"
        f"Seven days. Every pick graded, every line evaluated for edge.\n\n"
        f"clairvoyanceengine.info\n\n#sportsbetting #bettingtips #weeklyrecap"
    )
    return {"instagram": ig, "x": x}


def build_alltime_caption(stats: dict | None) -> dict[str, str]:
    tally_line = ""
    if stats and stats.get("w") is not None:
        tally_line = (
            f"Final tally: {stats['w']}W-{stats['l']}L · {_fmt_pct(stats.get('pct'))} win rate · "
            f"{_fmt_units(stats.get('units'))}\n\n"
        )
    ig = (
        f"All Time — Every Pick, Every Result\n\nThis is Clairvoyance.\n\n{tally_line}"
        f"The full track record, public from day one. No cherry-picking, no deleted losses.\n\n"
        f"Follow for daily signals, subscribe for exclusive graded picks, and intelligence briefs.\n\n"
        f"clairvoyanceengine.info\nIG @clairvoyanceengine\nX @clairvoyanceeng\n\n"
        f"#foryou #sportsbetting #bettingtips #bettingpicks"
    )
    x = (
        f"All Time — Every Pick, Every Result\n\nThis is Clairvoyance.\n\n{tally_line}"
        f"The full track record, public from day one.\n\n"
        f"clairvoyanceengine.info\n\n#sportsbetting #bettingpicks"
    )
    return {"instagram": ig, "x": x}


def build_monthly_caption(stats: dict | None, month_ref: datetime) -> dict[str, str]:
    last_month = (month_ref.replace(day=1) - timedelta(days=1))
    month_str = last_month.strftime("%B %Y")
    tally_line = ""
    if stats and stats.get("w") is not None:
        tally_line = (
            f"Final tally: {stats['w']}W-{stats['l']}L · {_fmt_pct(stats.get('pct'))} win rate · "
            f"{_fmt_units(stats.get('units'))}\n\n"
        )
    ig = (
        f"{month_str} in the Books\n\nThis is Clairvoyance.\n\n{tally_line}"
        f"A full month tracked, graded, and public. No cherry-picking, no deleted losses.\n\n"
        f"Follow for daily signals, subscribe for exclusive graded picks, and intelligence briefs.\n\n"
        f"clairvoyanceengine.info\nIG @clairvoyanceengine\nX @clairvoyanceeng\n\n"
        f"#foryou #sportsbetting #bettingtips #bettingpicks #monthlyrecap"
    )
    x = (
        f"{month_str} in the Books\n\nThis is Clairvoyance.\n\n{tally_line}"
        f"A full month tracked, graded, and public. No cherry-picking.\n\n"
        f"clairvoyanceengine.info\n\n#sportsbetting #bettingpicks #monthlyrecap"
    )
    return {"instagram": ig, "x": x}


def build_yearly_caption(stats: dict | None, year: int) -> dict[str, str]:
    tally_line = ""
    if stats and stats.get("w") is not None:
        tally_line = (
            f"Final tally: {stats['w']}W-{stats['l']}L · {_fmt_pct(stats.get('pct'))} win rate · "
            f"{_fmt_units(stats.get('units'))}\n\n"
        )
    ig = (
        f"{year} in the Books\n\nThis is Clairvoyance.\n\n{tally_line}"
        f"A full year tracked, graded, and public. Every pick, every result — no cherry-picking, no deleted losses.\n\n"
        f"Follow for daily signals, subscribe for exclusive graded picks, and intelligence briefs.\n\n"
        f"clairvoyanceengine.info\nIG @clairvoyanceengine\nX @clairvoyanceeng\n\n"
        f"#foryou #sportsbetting #bettingtips #bettingpicks #yearinreview"
    )
    x = (
        f"{year} in the Books\n\nThis is Clairvoyance.\n\n{tally_line}"
        f"A full year tracked, graded, and public. No cherry-picking.\n\n"
        f"clairvoyanceengine.info\n\n#sportsbetting #bettingpicks #yearinreview"
    )
    return {"instagram": ig, "x": x}


def build_event_caption(event: dict, stats: dict | None = None) -> dict[str, str]:
    event_hashtag = "#" + "".join(w.capitalize() for w in event["name"].split())
    tally_line = ""
    if stats and stats.get("w") is not None:
        tally_line = (
            f"Final tally: {stats['w']}W-{stats['l']}L · {_fmt_pct(stats.get('pct'))} win rate · "
            f"{_fmt_units(stats.get('units'))}\n\n"
        )
    ig = (
        f"{event['name']} is in the books.\n\nThis is Clairvoyance.\n\n{tally_line}"
        f"Every pick tracked. Every result public. No guesswork.\n\n"
        f"Follow for daily signals, subscribe for exclusive graded picks, and intelligence briefs.\n\n"
        f"clairvoyanceengine.info\nIG @clairvoyanceengine\nX @clairvoyanceeng\n\n"
        f"#foryou #sportsbetting #bettingtips #bettingpicks {event_hashtag}"
    )
    x = (
        f"{event['name']} is in the books.\n\nThis is Clairvoyance.\n\n{tally_line}"
        f"Clairvoyance Engine doesn't miss. 🎯\n\n"
        f"#SportsBetting {event_hashtag}"
    )
    return {"instagram": ig, "x": x}


def build_grading_caption() -> dict[str, str]:
    ig = (
        "Not all picks are created equal.\n\nThis is Clairvoyance.\n\n"
        "Every signal gets graded before it goes public — some clear the bar, some don't make the cut at all. "
        "That's the point. We're not chasing volume, we're chasing quality.\n\n"
        "No hype. No \"lock of the century.\" Just picks that clear the bar, and ones that don't get thrown out.\n\n"
        "Follow for daily signals, subscribe for exclusive graded picks, and intelligence briefs.\n\n"
        "clairvoyanceengine.info\nIG @clairvoyanceengine\nX @clairvoyanceeng\n\n"
        "#foryou #sportsbetting #bettingtips #bettingpicks"
    )
    x = (
        "Not all picks are created equal.\n\nEvery signal gets graded before it goes public. "
        "If the numbers don't clear our bar, it doesn't get posted.\n\n"
        "clairvoyanceengine.info\n\n#sportsbetting #bettingpicks #handicapping"
    )
    return {"instagram": ig, "x": x}


def build_subscription_caption() -> dict[str, str]:
    ig = (
        "Full access. No guesswork.\n\nThis is Clairvoyance.\n\n"
        "Every tier gets real graded picks, real game lines, and Discord access — the only difference is how much of the model you want.\n\n"
        "clairvoyanceengine.info\nIG @clairvoyanceengine\nX @clairvoyanceeng\n\n"
        "#foryou #sportsbetting #bettingtips #bettingpicks"
    )
    x = (
        "Full access. No guesswork.\n\nBase, Plus, Insider — or a Day/Weekend Pass if you just want in for a slate.\n\n"
        "clairvoyanceengine.info\n\n#sportsbetting #bettingpicks"
    )
    return {"instagram": ig, "x": x}


def build_educational_caption(topic: dict) -> dict[str, str]:
    body = " ".join(topic["lines"])
    ig = (
        f"{topic['title']}\n\nThis is Clairvoyance.\n\n{body}\n\n"
        f"Follow for daily signals, subscribe for exclusive graded picks, and intelligence briefs.\n\n"
        f"clairvoyanceengine.info\nIG @clairvoyanceengine\nX @clairvoyanceeng\n\n"
        f"#foryou #sportsbetting #bettingtips #bettingpicks"
    )
    x = f"{topic['title']}\n\n{body}\n\nclairvoyanceengine.info\n\n#sportsbetting #bettingpicks"
    return {"instagram": ig, "x": x}


def build_covers_caption() -> dict[str, str]:
    ig = (
        "One engine. Every sport that matters.\n\nThis is Clairvoyance.\n\n"
        "20 leagues across 6 sports, every pick graded, every result tracked publicly — model outputs, not gut feelings.\n\n"
        "Follow for daily signals, subscribe for exclusive graded picks, and intelligence briefs.\n\n"
        "clairvoyanceengine.info\nIG @clairvoyanceengine\nX @clairvoyanceeng\n\n"
        "#foryou #sportsbetting #bettingtips #bettingpicks"
    )
    x = (
        "One engine. Every sport that matters.\n\n20 leagues, 6 sports, every pick graded.\n\n"
        "clairvoyanceengine.info\n\n#sportsbetting #bettingpicks"
    )
    return {"instagram": ig, "x": x}


def _caption_block(title: str, text: str) -> str:
    html_text = text.replace("\n", "<br>")
    return (
        f'<h3 style="margin-bottom:4px">{title}</h3>'
        f'<div style="background:#f5f5f5;border-radius:6px;padding:12px 16px;'
        f'font-family:monospace;font-size:13px;white-space:pre-wrap;margin-bottom:20px">{html_text}</div>'
    )


def send_email(subject: str, cards: list[Path], captions: dict[str, str], intro: str = "",
                extra_captions: list[tuple[str, dict[str, str]]] | None = None) -> None:
    if not RESEND_API_KEY or not SOCIAL_CARD_EMAIL_TO:
        log(f"Email creds not set — skipping send for: {subject}")
        return
    attachments = [
        {"filename": p.name, "content": base64.b64encode(p.read_bytes()).decode("ascii")}
        for p in cards
    ]
    filename_list_html = "".join(f"<li>{a['filename']}</li>" for a in attachments)
    extra_html = ""
    for label, extra in (extra_captions or []):
        extra_html += (
            f"<p><b>{label}</b> — separate post, own captions below:</p>"
            f"{_caption_block(f'{label} — Instagram caption', extra['instagram'])}"
            f"{_caption_block(f'{label} — X caption', extra['x'])}"
        )
    body_html = (
        f"<p>{intro}</p>"
        f"<p>Cards attached:</p><ul>{filename_list_html}</ul>"
        f"<p>Captions below, ready to copy-paste:</p>"
        f"{_caption_block('Instagram caption', captions['instagram'])}"
        f"{_caption_block('X caption', captions['x'])}"
        f"{extra_html}"
    )
    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={
            "from": "Clairvoyance Engine <onboarding@resend.dev>",
            "to": [SOCIAL_CARD_EMAIL_TO],
            "subject": subject,
            "html": body_html,
            "attachments": attachments,
        },
        timeout=30,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Resend send failed for '{subject}': HTTP {resp.status_code} {resp.text[:300]}")
    log(f"Email sent: {subject} ({len(attachments)} attachment(s))")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-email", action="store_true", help="generate cards only, skip sending")
    parser.add_argument("--out-dir", default="/tmp/cv_social_cards")
    parser.add_argument("--force", default="", help="comma-separated periods to force past today's date "
                         "gate for review (weekly,monthly,yearly,alltime) — does not affect the real "
                         "cadence for anything not explicitly listed")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    now_mt = _mt_now()
    yesterday_mt = now_mt - timedelta(days=1)
    force = {p.strip() for p in args.force.split(",") if p.strip()}

    result = run(out_dir, force=force)

    # Daily
    daily = result["daily"]
    captions = build_daily_caption(daily["stats"], yesterday_mt)
    log("Daily captions:\n--- IG ---\n" + captions["instagram"] + "\n--- X ---\n" + captions["x"])

    # IG gets the video, X gets a still of the same fully-settled content —
    # Track Record/Sport Perf/League Perf PNG cards are no longer attached
    # at all (superseded by the video+still pair).
    daily_attachments = []
    stats = daily["stats"] or {}
    if stats.get("w") is not None:
        try:
            from generate_video_reveal import record_stats_reveal, record_stats_still, record_breakdown_reveal, record_breakdown_still, STATS_VARIANT_NAMES
            # Rotate the visual style by weekday (same index basis as the
            # caption hook rotation) so consecutive daily videos don't all
            # look identical.
            variant = STATS_VARIANT_NAMES[yesterday_mt.weekday() % len(STATS_VARIANT_NAMES)]
            video_path = out_dir / f"cv-reveal-{yesterday_mt.strftime('%Y%m%d')}.mp4"
            record_stats_reveal(
                headline="YESTERDAY'S PERFORMANCE",
                record=f"{stats['w']}W-{stats['l']}L",
                pct=_fmt_pct(stats.get("pct")),
                units=_fmt_units(stats.get("units")),
                locked=str(stats.get("lockedCount", "—")),
                out_path=video_path,
                variant=variant,
                date_str=yesterday_mt.strftime("%B %-d, %Y"),
            )
            log(f"Daily video variant: {variant}")
            daily_attachments.append(video_path)
            log(f"Video reveal generated: {video_path}")

            still_path = out_dir / f"cv-reveal-still-{yesterday_mt.strftime('%Y%m%d')}.png"
            record_stats_still(
                headline="YESTERDAY'S PERFORMANCE",
                record=f"{stats['w']}W-{stats['l']}L",
                pct=_fmt_pct(stats.get("pct")),
                units=_fmt_units(stats.get("units")),
                locked=str(stats.get("lockedCount", "—")),
                out_path=still_path,
                variant=variant,
                date_str=yesterday_mt.strftime("%B %-d, %Y"),
            )
            daily_attachments.append(still_path)
            log(f"Stats still generated: {still_path}")

            if stats.get("bySport"):
                rows = _breakdown_rows(stats)
                breakdown_path = out_dir / f"cv-breakdown-{yesterday_mt.strftime('%Y%m%d')}.mp4"
                record_breakdown_reveal("SPORT PERFORMANCE", rows, breakdown_path)
                daily_attachments.append(breakdown_path)
                log(f"Breakdown video generated: {breakdown_path}")

                breakdown_still_path = out_dir / f"cv-breakdown-still-{yesterday_mt.strftime('%Y%m%d')}.png"
                record_breakdown_still("SPORT PERFORMANCE", rows, breakdown_still_path)
                daily_attachments.append(breakdown_still_path)
                log(f"Breakdown still generated: {breakdown_still_path}")
        except Exception as exc:
            # Video is a bonus on top of the cards, not a hard requirement
            # for the daily post — don't let a video-pipeline hiccup (e.g.
            # ffmpeg conversion issue) block the cards/captions email that
            # actually matters every day.
            log(f"Video reveal generation failed (non-fatal, skipping): {exc}")

    # Pick of the Day — highest win-probability ML leg across every
    # settleable sport/league, same reveal aesthetic as the other daily
    # videos. Sent as its own attachment/caption pair inside the same
    # daily email rather than a separate email, since it's still part of
    # "today's post batch." Skipped entirely (not a fake/weak pick) if no
    # leg cleared the engine's own probability floor today.
    #
    # Before picking today's, settle any still-pending entries from
    # previous days against the real final score (docs/pick_of_day.json
    # is git-committed by the workflow, same durability pattern as the
    # milestone state file — living under docs/ rather than data/ since
    # the live app also fetches it directly over HTTP) — this is what
    # makes the home page's PICK OF DAY tile's record/win%/units actually
    # accumulate day over day.
    pod_ledger = load_pick_of_day_ledger()
    pod_ledger = settle_pending_picks(pod_ledger)
    save_pick_of_day_ledger(pod_ledger)

    free_pick_extra = None
    free_pick = result.get("free_pick")
    if free_pick:
        try:
            from generate_video_reveal import record_free_pick_reveal, record_free_pick_still
            # Video/still layout is league (sport-tag) / matchup / pick,
            # each on its own line -- the league is already shown
            # separately above, so strip that leading "<SPORT> " prefix
            # from the raw leg name ("MLB ML LAD" -> "ML LAD") rather
            # than showing the league twice.
            sport_prefix = free_pick["sport"] + " "
            pick_label = free_pick["name"][len(sport_prefix):] if free_pick["name"].startswith(sport_prefix) else free_pick["name"]
            pick_video_path = out_dir / f"cv-freepick-{yesterday_mt.strftime('%Y%m%d')}.mp4"
            record_free_pick_reveal(
                sport_tag=free_pick["sport"],
                matchup=free_pick["matchup"],
                pick=pick_label,
                grade=free_pick["grade"],
                out_path=pick_video_path,
                date_str=now_mt.strftime("%B %-d, %Y").upper(),
            )
            daily_attachments.append(pick_video_path)

            pick_still_path = out_dir / f"cv-freepick-still-{yesterday_mt.strftime('%Y%m%d')}.png"
            record_free_pick_still(
                sport_tag=free_pick["sport"],
                matchup=free_pick["matchup"],
                pick=pick_label,
                grade=free_pick["grade"],
                out_path=pick_still_path,
                date_str=now_mt.strftime("%B %-d, %Y").upper(),
            )
            daily_attachments.append(pick_still_path)
            free_pick_extra = ("Free Pick of the Day", build_free_pick_caption(free_pick))

            # Record today's pick in the ledger as pending — tomorrow's
            # run will settle it against the real score before picking
            # the next one.
            pod_ledger.append({
                "date": now_mt.strftime("%Y-%m-%d"),
                "sport": _POTD_BROAD_SPORT.get(free_pick["sport"], free_pick["sport"]),
                "league": free_pick["sport"],
                "type": free_pick["type"],
                "betType": "ML",
                "pick": free_pick["name"],
                "matchup": free_pick["matchup"],
                "prob": free_pick["prob"],
                "ml": free_pick["ml"],
                "grade": free_pick["grade"],
                "pickedAbbr": free_pick["pickedAbbr"],
                "outcome": "pending",
                "settledAt": None,
            })
            save_pick_of_day_ledger(pod_ledger)
            log(f"Free pick video generated: {pick_video_path} ({free_pick['name']} @ {free_pick['prob']*100:.0f}%)")
        except Exception as exc:
            log(f"Free pick video generation failed (non-fatal, skipping): {exc}")
    else:
        log("No free pick today — no leg cleared the engine's probability floor.")

    if not args.no_email:
        send_email(
            f"Clairvoyance — Daily Social Cards ({yesterday_mt.strftime('%B %d, %Y')})",
            daily_attachments, captions,
            intro="Today's social cards are attached, ready to post:",
            extra_captions=[free_pick_extra] if free_pick_extra else None,
        )

    # Weekly
    if result["weekly"]:
        captions = build_weekly_caption(result["weekly"]["stats"], yesterday_mt)
        log("Weekly captions:\n--- IG ---\n" + captions["instagram"])
        weekly_attachments = []
        w_stats = result["weekly"]["stats"] or {}
        if w_stats.get("w") is not None:
            try:
                from generate_video_reveal import record_big_recap_reveal, record_big_recap_still
                week_start = yesterday_mt - timedelta(days=6)
                range_str = _fmt_date_range(week_start, yesterday_mt)
                recap_path = out_dir / f"cv-weekly-recap-{yesterday_mt.strftime('%Y%m%d')}.mp4"
                record_big_recap_reveal(
                    tag="WEEKLY RECAP", date_range=range_str,
                    record=f"{w_stats['w']}W-{w_stats['l']}L", pct=_fmt_pct(w_stats.get("pct")),
                    units=_fmt_units(w_stats.get("units")), extra_val=str(w_stats.get("lockedCount", "—")), extra_lbl="PICKS LOCKED",
                    out_path=recap_path,
                )
                weekly_attachments.append(recap_path)
                log(f"Weekly recap video generated: {recap_path}")

                w_still_path = out_dir / f"cv-weekly-recap-still-{yesterday_mt.strftime('%Y%m%d')}.png"
                record_big_recap_still(
                    tag="WEEKLY RECAP", date_range=range_str,
                    record=f"{w_stats['w']}W-{w_stats['l']}L", pct=_fmt_pct(w_stats.get("pct")),
                    units=_fmt_units(w_stats.get("units")), extra_val=str(w_stats.get("lockedCount", "—")), extra_lbl="PICKS LOCKED",
                    out_path=w_still_path,
                )
                weekly_attachments.append(w_still_path)
                log(f"Weekly recap still generated: {w_still_path}")
            except Exception as exc:
                log(f"Weekly recap video generation failed (non-fatal, skipping): {exc}")
            if w_stats.get("bySport"):
                try:
                    from generate_video_reveal import record_breakdown_reveal, record_breakdown_still
                    rows = _breakdown_rows(w_stats)
                    w_breakdown_path = out_dir / f"cv-breakdown-weekly-{yesterday_mt.strftime('%Y%m%d')}.mp4"
                    w_range_str = _fmt_date_range(yesterday_mt - timedelta(days=6), yesterday_mt).upper()
                    record_breakdown_reveal("SPORT PERFORMANCE — ROLLING 7D", rows, w_breakdown_path, date_range=w_range_str)
                    weekly_attachments.append(w_breakdown_path)
                    log(f"Weekly breakdown video generated: {w_breakdown_path}")

                    w_bd_still_path = out_dir / f"cv-breakdown-weekly-still-{yesterday_mt.strftime('%Y%m%d')}.png"
                    record_breakdown_still("SPORT PERFORMANCE — ROLLING 7D", rows, w_bd_still_path, date_range=w_range_str)
                    weekly_attachments.append(w_bd_still_path)
                    log(f"Weekly breakdown still generated: {w_bd_still_path}")
                except Exception as exc:
                    log(f"Weekly breakdown video generation failed (non-fatal, skipping): {exc}")
        if not args.no_email:
            send_email(
                f"Clairvoyance — Weekly Recap ({yesterday_mt.strftime('%B %d, %Y')})",
                weekly_attachments, captions,
                intro="It's Sunday — here's the 7-day roundup, good pinned-post material:",
            )

    # Monthly
    if result["monthly"]:
        m_stats = result["monthly"]["stats"] or {}
        _strip_stale_hockey(m_stats)
        captions = build_monthly_caption(m_stats, now_mt)
        log("Monthly captions:\n--- IG ---\n" + captions["instagram"])
        monthly_attachments = []
        last_month_end = now_mt.replace(day=1) - timedelta(days=1)
        if m_stats.get("w") is not None:
            try:
                from generate_video_reveal import record_big_recap_reveal, record_big_recap_still
                recap_path = out_dir / f"cv-monthly-recap-{last_month_end.strftime('%Y%m')}.mp4"
                record_big_recap_reveal(
                    tag="MONTHLY RECAP", date_range=last_month_end.strftime("%B %Y").upper(),
                    record=f"{m_stats['w']}W-{m_stats['l']}L", pct=_fmt_pct(m_stats.get("pct")),
                    units=_fmt_units(m_stats.get("units")), extra_val=str(m_stats.get("lockedCount", "—")), extra_lbl="PICKS LOCKED",
                    out_path=recap_path,
                )
                monthly_attachments.append(recap_path)
                log(f"Monthly recap video generated: {recap_path}")

                m_still_path = out_dir / f"cv-monthly-recap-still-{last_month_end.strftime('%Y%m')}.png"
                record_big_recap_still(
                    tag="MONTHLY RECAP", date_range=last_month_end.strftime("%B %Y").upper(),
                    record=f"{m_stats['w']}W-{m_stats['l']}L", pct=_fmt_pct(m_stats.get("pct")),
                    units=_fmt_units(m_stats.get("units")), extra_val=str(m_stats.get("lockedCount", "—")), extra_lbl="PICKS LOCKED",
                    out_path=m_still_path,
                )
                monthly_attachments.append(m_still_path)
                log(f"Monthly recap still generated: {m_still_path}")
            except Exception as exc:
                log(f"Monthly recap video generation failed (non-fatal, skipping): {exc}")
            if m_stats.get("bySport"):
                try:
                    from generate_video_reveal import record_breakdown_reveal, record_breakdown_still
                    rows = _breakdown_rows(m_stats)
                    m_breakdown_path = out_dir / f"cv-breakdown-monthly-{last_month_end.strftime('%Y%m')}.mp4"
                    record_breakdown_reveal("SPORT PERFORMANCE — LAST MONTH", rows, m_breakdown_path,
                                             date_range=last_month_end.strftime("%B %Y").upper())
                    monthly_attachments.append(m_breakdown_path)
                    log(f"Monthly breakdown video generated: {m_breakdown_path}")

                    m_bd_still_path = out_dir / f"cv-breakdown-monthly-still-{last_month_end.strftime('%Y%m')}.png"
                    record_breakdown_still("SPORT PERFORMANCE — LAST MONTH", rows, m_bd_still_path,
                                            date_range=last_month_end.strftime("%B %Y").upper())
                    monthly_attachments.append(m_bd_still_path)
                    log(f"Monthly breakdown still generated: {m_bd_still_path}")
                except Exception as exc:
                    log(f"Monthly breakdown video generation failed (non-fatal, skipping): {exc}")
        if not args.no_email:
            send_email(
                f"Clairvoyance — Monthly Recap ({last_month_end.strftime('%B %Y')})",
                monthly_attachments, captions,
                intro="First of the month — last month's recap is ready:",
            )

    # Year in review (Jan 1 — video only, no static cards, since the
    # underlying app has no calendar-year period to render them against)
    if result["yearly"]:
        prior_year = now_mt.year - 1
        y_stats = result["yearly"]["stats"] or {}
        captions = build_yearly_caption(y_stats, prior_year)
        log(f"Yearly captions ({prior_year}):\n--- IG ---\n" + captions["instagram"])
        yearly_attachments = []
        if y_stats.get("w") is not None:
            try:
                from generate_video_reveal import record_big_recap_reveal, record_big_recap_still
                recap_path = out_dir / f"cv-yearly-recap-{prior_year}.mp4"
                record_big_recap_reveal(
                    tag="YEAR IN REVIEW", date_range=f"JANUARY 1 – DECEMBER 31, {prior_year}",
                    record=f"{y_stats['w']}W-{y_stats['l']}L", pct=_fmt_pct(y_stats.get("pct")),
                    units=_fmt_units(y_stats.get("units")), extra_val=str(y_stats.get("lockedCount", "—")), extra_lbl="PICKS LOCKED",
                    out_path=recap_path, duration_s=8.0,
                )
                yearly_attachments.append(recap_path)
                log(f"Yearly recap video generated: {recap_path}")

                y_still_path = out_dir / f"cv-yearly-recap-still-{prior_year}.png"
                record_big_recap_still(
                    tag="YEAR IN REVIEW", date_range=f"JANUARY 1 – DECEMBER 31, {prior_year}",
                    record=f"{y_stats['w']}W-{y_stats['l']}L", pct=_fmt_pct(y_stats.get("pct")),
                    units=_fmt_units(y_stats.get("units")), extra_val=str(y_stats.get("lockedCount", "—")), extra_lbl="PICKS LOCKED",
                    out_path=y_still_path, duration_s=8.0,
                )
                yearly_attachments.append(y_still_path)
                log(f"Yearly recap still generated: {y_still_path}")
            except Exception as exc:
                log(f"Yearly recap video generation failed (non-fatal, skipping): {exc}")
            if y_stats.get("bySport"):
                try:
                    from generate_video_reveal import record_breakdown_reveal, record_breakdown_still
                    rows = _breakdown_rows(y_stats)
                    y_breakdown_path = out_dir / f"cv-breakdown-yearly-{prior_year}.mp4"
                    record_breakdown_reveal(f"SPORT PERFORMANCE — {prior_year}", rows, y_breakdown_path,
                                             date_range=f"JANUARY 1 – DECEMBER 31, {prior_year}")
                    yearly_attachments.append(y_breakdown_path)
                    log(f"Yearly breakdown video generated: {y_breakdown_path}")

                    y_bd_still_path = out_dir / f"cv-breakdown-yearly-still-{prior_year}.png"
                    record_breakdown_still(f"SPORT PERFORMANCE — {prior_year}", rows, y_bd_still_path,
                                            date_range=f"JANUARY 1 – DECEMBER 31, {prior_year}")
                    yearly_attachments.append(y_bd_still_path)
                    log(f"Yearly breakdown still generated: {y_bd_still_path}")
                except Exception as exc:
                    log(f"Yearly breakdown video generation failed (non-fatal, skipping): {exc}")
        if yearly_attachments and not args.no_email:
            send_email(
                f"Clairvoyance — {prior_year} Year In Review",
                yearly_attachments, captions,
                intro=f"Happy New Year — here's the full {prior_year} recap:",
            )
        elif not yearly_attachments:
            log(f"Year-end recap skipped: no settled bets found for {prior_year}")

    # All Time (every 14 days)
    if result["alltime"]:
        at_stats = result["alltime"]["stats"] or {}
        captions = build_alltime_caption(at_stats)
        log("All Time captions:\n--- IG ---\n" + captions["instagram"])
        at_attachments = []
        if at_stats.get("bySport"):
            try:
                from generate_video_reveal import record_breakdown_reveal, record_breakdown_still
                rows = _breakdown_rows(at_stats)
                at_breakdown_path = out_dir / f"cv-breakdown-alltime-{now_mt.strftime('%Y%m%d')}.mp4"
                record_breakdown_reveal("SPORT PERFORMANCE — ALL TIME", rows, at_breakdown_path)
                at_attachments.append(at_breakdown_path)

                at_still_path = out_dir / f"cv-breakdown-alltime-still-{now_mt.strftime('%Y%m%d')}.png"
                record_breakdown_still("SPORT PERFORMANCE — ALL TIME", rows, at_still_path)
                at_attachments.append(at_still_path)
            except Exception as exc:
                log(f"All Time breakdown video generation failed (non-fatal, skipping): {exc}")
        if not args.no_email:
            send_email(
                "Clairvoyance — All Time Track Record",
                at_attachments, captions,
                intro="Full all-time track record, good pinned-post material:",
            )

    # Events
    for ev in result["events"]:
        captions = build_event_caption(ev["event"], ev.get("stats"))
        log(f"Event captions ({ev['event']['name']}):\n--- IG ---\n" + captions["instagram"])
        event_attachments = [ev["card"]]
        ev_stats = ev.get("stats") or {}
        if ev_stats.get("w") is not None:
            try:
                from generate_video_reveal import record_stats_reveal, record_stats_still
                slug = re.sub(r"[^a-z0-9]+", "-", ev["event"]["name"].lower()).strip("-")
                event_video_path = out_dir / f"cv-event-{slug}-{yesterday_mt.strftime('%Y%m%d')}.mp4"
                record_stats_reveal(
                    headline=ev["event"]["name"].title(),
                    record=f"{ev_stats['w']}W-{ev_stats['l']}L",
                    pct=_fmt_pct(ev_stats.get("pct")),
                    units=_fmt_units(ev_stats.get("units")),
                    locked=str(ev_stats.get("n", "—")),
                    out_path=event_video_path,
                    variant="glitch",
                )
                event_attachments.append(event_video_path)
                log(f"Event glitch video generated: {event_video_path}")

                event_still_path = out_dir / f"cv-event-{slug}-still-{yesterday_mt.strftime('%Y%m%d')}.png"
                record_stats_still(
                    headline=ev["event"]["name"].title(),
                    record=f"{ev_stats['w']}W-{ev_stats['l']}L",
                    pct=_fmt_pct(ev_stats.get("pct")),
                    units=_fmt_units(ev_stats.get("units")),
                    locked=str(ev_stats.get("n", "—")),
                    out_path=event_still_path,
                    variant="glitch",
                )
                event_attachments.append(event_still_path)
                log(f"Event still generated: {event_still_path}")
            except Exception as exc:
                log(f"Event video generation failed (non-fatal, skipping): {exc}")
        if not args.no_email:
            send_email(
                f"Clairvoyance — {ev['event']['name']} Wrap-Up",
                event_attachments, captions,
                intro=f"{ev['event']['name']} just wrapped — final performance card is ready:",
            )

    # Rotation content (grading system, subscription tiers, educational
    # series) — every 5th day since launch, deterministic from the date.
    rotation_item = get_rotation_item(now_mt)
    if rotation_item:
        log(f"Rotation content today: {rotation_item}")
        try:
            from generate_video_reveal import (
                record_grading_tiers_reveal, record_subscription_tiers_reveal,
                record_educational_reveal, EDUCATIONAL_TOPICS,
            )
            if rotation_item == "covers":
                # Static pre-made asset, not a generated video — attach as-is.
                subject = "Clairvoyance — What We Cover"
                intro = "Rotation content — What Clairvoyance covers, ready to post:"
                captions = build_covers_caption()
                log(f"Rotation asset (static image): {COVERS_CARD_PATH}")
                if not args.no_email:
                    send_email(subject, [COVERS_CARD_PATH], captions, intro=intro)
            else:
                rotation_path = out_dir / f"cv-rotation-{rotation_item}-{now_mt.strftime('%Y%m%d')}.mp4"
                if rotation_item == "grading":
                    record_grading_tiers_reveal(rotation_path)
                    subject = "Clairvoyance — Pick Grading System"
                    intro = "Rotation content — Pick Grading System, ready to post:"
                    captions = build_grading_caption()
                elif rotation_item == "subscription":
                    record_subscription_tiers_reveal(rotation_path)
                    subject = "Clairvoyance — Choose Your Tier"
                    intro = "Rotation content — Subscription tiers, ready to post:"
                    captions = build_subscription_caption()
                else:
                    topic = EDUCATIONAL_TOPICS[rotation_item]
                    record_educational_reveal(topic["tag"], topic["title"], topic["lines"], rotation_path)
                    subject = f"Clairvoyance — Educational: {topic['title']}"
                    intro = "Rotation content — educational post, ready to post:"
                    captions = build_educational_caption(topic)
                log(f"Rotation video generated: {rotation_path}")
                if not args.no_email:
                    send_email(subject, [rotation_path], captions, intro=intro)
        except Exception as exc:
            log(f"Rotation content generation failed (non-fatal, skipping): {exc}")

    log("Done.")


if __name__ == "__main__":
    main()
