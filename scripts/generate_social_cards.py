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
  - Every day:      Track Record + Sport/League Performance (YESTERDAY)
  - Sundays:        + a weekly recap (ROLLING 7D) — bigger "7-day roundup"
  - 1st of month:   + a monthly recap (LAST MONTH)
  - Configured event end dates (see EVENTS below): + an Event Performance
    card for that tournament/season, the day after it ends
  - Any run:        a milestone check (win streak / round-number bet-count
    triggers) — fires a bonus email the day a new one is crossed. State is
    persisted in data/social_milestones.json (committed back to the repo
    by the workflow) so a milestone only ever fires once.

Caption copy rotates through a few hook-style variants (see HOOK_STYLES)
so consecutive daily posts don't read as obviously templated.

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
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

APP_URL = "https://mercmink21.github.io/clairvoyance-backend/app.html"
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SOCIAL_CARD_EMAIL_TO = os.environ.get("SOCIAL_CARD_EMAIL_TO", "")
ROOT = Path(__file__).resolve().parent.parent
MILESTONE_STATE_PATH = ROOT / "data" / "social_milestones.json"

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

# Rotating opening-hook styles for the daily caption, keyed by weekday
# index (Mon=0..Sun=6) so the same day of week always gets the same
# style — avoids two similar-sounding posts landing back to back while
# still giving four distinct voices across a week.
HOOK_STYLES = [
    lambda date_str: f"Yesterday's Performance — {date_str}",
    lambda date_str: f"{date_str} results are in.",
    lambda date_str: f"How we did on {date_str}:",
    lambda date_str: f"The numbers don't lie — {date_str} recap:",
]

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


def load_milestone_state() -> dict:
    if MILESTONE_STATE_PATH.exists():
        try:
            return json.loads(MILESTONE_STATE_PATH.read_text())
        except Exception:
            pass
    return {"lastStreak": 0, "lastCountMilestone": 0}


def save_milestone_state(state: dict) -> None:
    MILESTONE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MILESTONE_STATE_PATH.write_text(json.dumps(state, indent=2))


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
          const bySport = (d.sportList || []).map(s => {
            const bets = (d.bySport && d.bySport[s]) || [];
            const settled = bets.filter(p => p.outcome === 'win' || p.outcome === 'loss');
            const w = settled.filter(p => p.outcome === 'win').length;
            const l = settled.length - w;
            return { label: s, w, l, n: settled.length, pct: settled.length ? w / settled.length : null };
          }).filter(s => s.n);
          return {
            w: d.totalP.w, l: d.totalP.l, pct: d.totalP.pct, units: d.totalP.units,
            bySport,
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


def get_milestone_data(page) -> dict:
    """All-time settled-bet count and current win/loss streak, computed
    from the real ledger already loaded into this page's localStorage."""
    return page.evaluate(
        """
        () => {
          const all = getP();
          const settled = all
            .filter(p => p.outcome === 'win' || p.outcome === 'loss')
            .sort((a, b) => (a.settledAt || a.lockedAt || 0) - (b.settledAt || b.lockedAt || 0));
          let streak = 0, dir = null;
          for (let i = settled.length - 1; i >= 0; i--) {
            const d = settled[i].outcome === 'win' ? 'W' : 'L';
            if (dir === null) { dir = d; streak = 1; }
            else if (d === dir) { streak++; }
            else break;
          }
          return { totalSettled: settled.length, streak, streakDir: dir };
        }
        """
    )


def run(out_dir: Path) -> dict:
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    now_mt = _mt_now()
    yesterday_mt = now_mt - timedelta(days=1)
    is_sunday = now_mt.weekday() == 6
    is_first_of_month = now_mt.day == 1

    result = {"daily": None, "weekly": None, "monthly": None, "events": [], "milestone": None}

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
                const r = await fetch(SUPABASE_URL + '/rest/v1/bets?select=raw&order=date.desc', {
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

        # Weekly (Sundays)
        if is_sunday:
            cards, stats = generate_cards(page, out_dir, "ROLLING 7D", prefix_extra="weekly-")
            result["weekly"] = {"cards": cards, "stats": stats}

        # Monthly (1st of month — covers the month that just ended)
        if is_first_of_month:
            cards, stats = generate_cards(page, out_dir, "LAST MONTH", prefix_extra="monthly-")
            result["monthly"] = {"cards": cards, "stats": stats}

        # Events — the day after a configured window ends
        for event in EVENTS:
            end_date = datetime.strptime(event["end"], "%Y-%m-%d").date()
            if yesterday_mt.date() == end_date:
                path = generate_event_card(page, out_dir, event)
                if path:
                    result["events"].append({"event": event, "card": path})

        # Milestones
        milestone_data = get_milestone_data(page)
        result["milestone_data"] = milestone_data

        browser.close()

    return result


def build_daily_caption(stats: dict | None, date_ref: datetime) -> dict[str, str]:
    date_str = date_ref.strftime("%B %-d, %Y")
    hook = HOOK_STYLES[date_ref.weekday() % len(HOOK_STYLES)](date_str)
    tally_line = ""
    if stats and stats.get("w") is not None:
        tally_line = (
            f"Final tally: {stats['w']}W-{stats['l']}L · {_fmt_pct(stats.get('pct'))} win rate · "
            f"{_fmt_units(stats.get('units'))}\n\n"
        )
    ig = (
        f"{hook}\n\nThis is Clairvoyance.\n\n{tally_line}"
        f"Every pick graded. Every line evaluated for edge. No guesswork.\n\n"
        f"Follow for daily signals, subscribe for exclusive graded picks, and intelligence briefs.\n\n"
        f"clairvoyanceengine.info\nIG @clairvoyanceengine\nX @clairvoyanceeng\n\n"
        f"#sportsbetting #bettingtips #bettingpicks #handicapping #sports"
    )
    x = (
        f"{hook}\n\nThis is Clairvoyance.\n\n{tally_line}"
        f"Every pick graded. Every line evaluated for edge. No guesswork.\n\n"
        f"Follow for daily signals, subscribe for exclusive graded picks, and intelligence briefs.\n\n"
        f"clairvoyanceengine.info\n\n#sportsbetting #bettingtips #bettingpicks"
    )
    return {"instagram": ig, "x": x}


def build_weekly_caption(stats: dict | None, week_end: datetime) -> dict[str, str]:
    week_start = week_end - timedelta(days=6)
    range_str = f"{week_start.strftime('%B %-d')}–{week_end.strftime('%-d, %Y')}"
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
        f"#sportsbetting #bettingtips #bettingpicks #handicapping #sports #weeklyrecap"
    )
    x = (
        f"This Week in Review — {range_str}\n\nThis is Clairvoyance.\n\n{tally_line}"
        f"Seven days. Every pick graded, every line evaluated for edge.\n\n"
        f"clairvoyanceengine.info\n\n#sportsbetting #bettingtips #weeklyrecap"
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
        f"#sportsbetting #bettingtips #bettingpicks #handicapping #sports #monthlyrecap"
    )
    x = (
        f"{month_str} in the Books\n\nThis is Clairvoyance.\n\n{tally_line}"
        f"A full month tracked, graded, and public. No cherry-picking.\n\n"
        f"clairvoyanceengine.info\n\n#sportsbetting #bettingpicks #monthlyrecap"
    )
    return {"instagram": ig, "x": x}


def build_event_caption(event: dict) -> dict[str, str]:
    event_hashtag = "#" + "".join(w.capitalize() for w in event["name"].split())
    ig = (
        f"{event['name']} is in the books.\n\nThis is Clairvoyance.\n\n"
        f"Every pick tracked. Every result public. No guesswork.\n\n"
        f"Follow for daily signals, subscribe for exclusive graded picks, and intelligence briefs.\n\n"
        f"clairvoyanceengine.info\nIG @clairvoyanceengine\nX @clairvoyanceeng\n\n"
        f"#SportsBetting #BettingModel {event_hashtag} #SportsAnalytics #ModelPicks"
    )
    x = (
        f"{event['name']} is in the books.\n\nThis is Clairvoyance.\n\n"
        f"Clairvoyance Engine doesn't miss. 🎯\n\n"
        f"#SportsBetting {event_hashtag}"
    )
    return {"instagram": ig, "x": x}


def build_milestone_caption(milestone_data: dict, trigger: str, threshold: int) -> dict[str, str]:
    if trigger == "streak":
        # threshold here is the round streak number just crossed (e.g. 10),
        # not necessarily the live streak count — announce the milestone
        # that was hit, not whatever the streak has ticked up to by the
        # time this caption gets built.
        dir_word = "WIN" if milestone_data["streakDir"] == "W" else "LOSS"
        headline = f"{threshold}-{dir_word} STREAK"
        body = f"{threshold} straight {'wins' if dir_word=='WIN' else 'losses'}. The model doesn't flinch either way — every pick graded the same, win or lose."
    else:
        headline = f"{threshold} BETS TRACKED"
        body = f"{threshold} graded picks, settled and public. Every single one — no cherry-picking, no deleted losses."
    ig = (
        f"MILESTONE: {headline}\n\nThis is Clairvoyance.\n\n{body}\n\n"
        f"Follow for daily signals, subscribe for exclusive graded picks, and intelligence briefs.\n\n"
        f"clairvoyanceengine.info\nIG @clairvoyanceengine\nX @clairvoyanceeng\n\n"
        f"#sportsbetting #bettingtips #bettingpicks #handicapping"
    )
    x = f"MILESTONE: {headline}\n\nThis is Clairvoyance.\n\n{body}\n\n#sportsbetting #bettingpicks"
    return {"instagram": ig, "x": x}


def _caption_block(title: str, text: str) -> str:
    html_text = text.replace("\n", "<br>")
    return (
        f'<h3 style="margin-bottom:4px">{title}</h3>'
        f'<div style="background:#f5f5f5;border-radius:6px;padding:12px 16px;'
        f'font-family:monospace;font-size:13px;white-space:pre-wrap;margin-bottom:20px">{html_text}</div>'
    )


def send_email(subject: str, cards: list[Path], captions: dict[str, str], intro: str = "") -> None:
    if not RESEND_API_KEY or not SOCIAL_CARD_EMAIL_TO:
        log(f"Email creds not set — skipping send for: {subject}")
        return
    attachments = [
        {"filename": p.name, "content": base64.b64encode(p.read_bytes()).decode("ascii")}
        for p in cards
    ]
    filename_list_html = "".join(f"<li>{a['filename']}</li>" for a in attachments)
    body_html = (
        f"<p>{intro}</p>"
        f"<p>Cards attached:</p><ul>{filename_list_html}</ul>"
        f"<p>Captions below, ready to copy-paste:</p>"
        f"{_caption_block('Instagram caption', captions['instagram'])}"
        f"{_caption_block('X caption', captions['x'])}"
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
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    now_mt = _mt_now()
    yesterday_mt = now_mt - timedelta(days=1)

    result = run(out_dir)

    # Daily
    daily = result["daily"]
    captions = build_daily_caption(daily["stats"], yesterday_mt)
    log("Daily captions:\n--- IG ---\n" + captions["instagram"] + "\n--- X ---\n" + captions["x"])

    daily_attachments = list(daily["cards"])
    stats = daily["stats"] or {}
    if stats.get("w") is not None:
        try:
            from generate_video_reveal import record_stats_reveal, record_breakdown_reveal, STATS_VARIANT_NAMES
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
                out_path=video_path,
                variant=variant,
            )
            log(f"Daily video variant: {variant}")
            daily_attachments.append(video_path)
            log(f"Video reveal generated: {video_path}")

            by_sport = stats.get("bySport") or []
            if by_sport:
                rows = [
                    {"label": s["label"], "record": f"{s['w']}W-{s['l']}L", "pct": _fmt_pct(s.get("pct")), "isTotal": False}
                    for s in by_sport
                ]
                rows.append({"label": "TOTAL", "record": f"{stats['w']}W-{stats['l']}L", "pct": _fmt_pct(stats.get("pct")), "isTotal": True})
                breakdown_path = out_dir / f"cv-breakdown-{yesterday_mt.strftime('%Y%m%d')}.mp4"
                record_breakdown_reveal("SPORT PERFORMANCE", rows, breakdown_path)
                daily_attachments.append(breakdown_path)
                log(f"Breakdown video generated: {breakdown_path}")
        except Exception as exc:
            # Video is a bonus on top of the cards, not a hard requirement
            # for the daily post — don't let a video-pipeline hiccup (e.g.
            # ffmpeg conversion issue) block the cards/captions email that
            # actually matters every day.
            log(f"Video reveal generation failed (non-fatal, skipping): {exc}")

    if not args.no_email:
        send_email(
            f"Clairvoyance — Daily Social Cards ({yesterday_mt.strftime('%B %d, %Y')})",
            daily_attachments, captions,
            intro="Today's social cards are attached, ready to post:",
        )

    # Weekly
    if result["weekly"]:
        captions = build_weekly_caption(result["weekly"]["stats"], yesterday_mt)
        log("Weekly captions:\n--- IG ---\n" + captions["instagram"])
        weekly_attachments = list(result["weekly"]["cards"])
        w_stats = result["weekly"]["stats"] or {}
        if w_stats.get("w") is not None:
            try:
                from generate_video_reveal import record_big_recap_reveal
                week_start = yesterday_mt - timedelta(days=6)
                range_str = f"{week_start.strftime('%B %-d')} – {yesterday_mt.strftime('%-d, %Y')}"
                recap_path = out_dir / f"cv-weekly-recap-{yesterday_mt.strftime('%Y%m%d')}.mp4"
                record_big_recap_reveal(
                    tag="WEEKLY RECAP", date_range=range_str,
                    record=f"{w_stats['w']}W-{w_stats['l']}L", pct=_fmt_pct(w_stats.get("pct")),
                    units=_fmt_units(w_stats.get("units")), extra_val="7 DAYS", extra_lbl="TRACKED",
                    out_path=recap_path,
                )
                weekly_attachments.append(recap_path)
                log(f"Weekly recap video generated: {recap_path}")
            except Exception as exc:
                log(f"Weekly recap video generation failed (non-fatal, skipping): {exc}")
        if not args.no_email:
            send_email(
                f"Clairvoyance — Weekly Recap ({yesterday_mt.strftime('%B %d, %Y')})",
                weekly_attachments, captions,
                intro="It's Sunday — here's the 7-day roundup, good pinned-post material:",
            )

    # Monthly
    if result["monthly"]:
        captions = build_monthly_caption(result["monthly"]["stats"], now_mt)
        log("Monthly captions:\n--- IG ---\n" + captions["instagram"])
        monthly_attachments = list(result["monthly"]["cards"])
        m_stats = result["monthly"]["stats"] or {}
        last_month_end = now_mt.replace(day=1) - timedelta(days=1)
        if m_stats.get("w") is not None:
            try:
                from generate_video_reveal import record_big_recap_reveal
                days_in_month = last_month_end.day
                recap_path = out_dir / f"cv-monthly-recap-{last_month_end.strftime('%Y%m')}.mp4"
                record_big_recap_reveal(
                    tag="MONTHLY RECAP", date_range=last_month_end.strftime("%B %Y").upper(),
                    record=f"{m_stats['w']}W-{m_stats['l']}L", pct=_fmt_pct(m_stats.get("pct")),
                    units=_fmt_units(m_stats.get("units")), extra_val=f"{days_in_month} DAYS", extra_lbl="TRACKED",
                    out_path=recap_path,
                )
                monthly_attachments.append(recap_path)
                log(f"Monthly recap video generated: {recap_path}")
            except Exception as exc:
                log(f"Monthly recap video generation failed (non-fatal, skipping): {exc}")
        if not args.no_email:
            send_email(
                f"Clairvoyance — Monthly Recap ({last_month_end.strftime('%B %Y')})",
                monthly_attachments, captions,
                intro="First of the month — last month's recap is ready:",
            )

    # Events
    for ev in result["events"]:
        captions = build_event_caption(ev["event"])
        log(f"Event captions ({ev['event']['name']}):\n--- IG ---\n" + captions["instagram"])
        if not args.no_email:
            send_email(
                f"Clairvoyance — {ev['event']['name']} Wrap-Up",
                [ev["card"]], captions,
                intro=f"{ev['event']['name']} just wrapped — final performance card is ready:",
            )

    # Milestones
    milestone_data = result.get("milestone_data") or {}
    state = load_milestone_state()
    new_state = dict(state)
    triggered = None

    triggered_threshold = None
    streak = milestone_data.get("streak", 0)
    streak_thresholds = [5, 10, 15, 20, 25, 30]
    for t in streak_thresholds:
        if streak >= t > state.get("lastStreak", 0):
            triggered = "streak"
            triggered_threshold = t
            new_state["lastStreak"] = t
            break
    if streak < state.get("lastStreak", 0):
        # streak broke — reset so the next run up can re-trigger at the same threshold later
        new_state["lastStreak"] = 0

    total = milestone_data.get("totalSettled", 0)
    count_thresholds = [100, 250, 500, 750, 1000, 1500, 2000, 2500, 3000]
    if triggered is None:
        for t in count_thresholds:
            if total >= t > state.get("lastCountMilestone", 0):
                triggered = "count"
                triggered_threshold = t
                new_state["lastCountMilestone"] = t
                break

    if triggered:
        log(f"Milestone triggered: {triggered} @ {triggered_threshold} ({milestone_data})")
        captions = build_milestone_caption(milestone_data, triggered, triggered_threshold)
        log("Milestone captions:\n--- IG ---\n" + captions["instagram"])

        milestone_attachments = [daily["cards"][0]]  # reuse the Track Record card already generated this run
        try:
            from generate_video_reveal import record_milestone_reveal
            # Two milestone styles rotate by trigger type so a streak
            # milestone and a bet-count milestone never look the same —
            # streaks get the more kinetic "pulse" (expanding rings, fits
            # a live-momentum feel), round-number counts get the punchier
            # "flash" (fits a single big-number headline moment).
            if triggered == "streak":
                dir_word = "WIN" if milestone_data.get("streakDir") == "W" else "LOSS"
                m_headline = f"{triggered_threshold}-{dir_word} STREAK"
                m_body = f"{triggered_threshold} straight {'wins' if dir_word=='WIN' else 'losses'}. The model doesn't flinch either way."
                m_variant = "pulse"
            else:
                m_headline = f"{triggered_threshold} BETS TRACKED"
                m_body = f"{triggered_threshold} graded picks, settled and public. Every single one."
                m_variant = "flash"
            milestone_video_path = out_dir / f"cv-milestone-{yesterday_mt.strftime('%Y%m%d')}.mp4"
            record_milestone_reveal(m_headline, m_body, milestone_video_path, variant=m_variant)
            milestone_attachments.append(milestone_video_path)
            log(f"Milestone video generated: {milestone_video_path}")
        except Exception as exc:
            log(f"Milestone video generation failed (non-fatal, skipping): {exc}")

        if not args.no_email:
            send_email(
                "Clairvoyance — 🎯 New Milestone!",
                milestone_attachments,
                captions,
                intro="A milestone just hit — good spike-engagement post, don't sit on this one:",
            )
        save_milestone_state(new_state)
    else:
        log(f"No new milestone (streak={streak}, total={total}, state={state})")

    log("Done.")


if __name__ == "__main__":
    main()
