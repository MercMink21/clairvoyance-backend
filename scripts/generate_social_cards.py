#!/usr/bin/env python3
"""
generate_social_cards.py — daily automated export of the social-tab canvas
cards (Track Record, Sport Performance, League Performance), emailed for
easy same-day posting.

The cards themselves are rendered client-side by JS canvas code in
docs/app.html (_genCombinedTrackGraphic, _genSportPerfGraphic,
_genLeaguePerfGraphic) — there's no server-side equivalent, and duplicating
that drawing logic in Python would just be a second thing to keep in sync
with every visual tweak made to the real cards. Instead this drives a
headless Chromium (Playwright, already a project dependency for Linemate
scraping) against the LIVE deployed app, so whatever the cards actually
look like in the browser is exactly what gets emailed.

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
     monkey-patched from outside (confirmed: typeof _saveCanvas is
     undefined at global scope, even though the exported generator
     functions that call it internally work fine). So instead of fighting
     that, this just lets the real download happen and captures it via
     Playwright's native download interception.

Event Performance card is deliberately NOT included — it needs a manually
set tournament name/date window with no sensible default, so
auto-generating it would risk emailing an empty/garbage card silently.

Usage:
  python3 scripts/generate_social_cards.py            # generate + email
  python3 scripts/generate_social_cards.py --no-email # generate only, save to /tmp
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

APP_URL = "https://mercmink21.github.io/clairvoyance-backend/app.html"
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SOCIAL_CARD_EMAIL_TO = os.environ.get("SOCIAL_CARD_EMAIL_TO", "")

# filename prefix written by each card's _saveCanvas() call -> (JS call, human label)
CARD_JOBS = [
    ("cv-track-record-", "_genCombinedTrackGraphic()", "Track Record"),
    ("cv-sport-perf-",   "_genSportPerfGraphic()",     "Sport Performance"),
    ("cv-league-perf-",  "_genLeaguePerfGraphic()",    "League Performance"),
]


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def generate_cards(out_dir: Path) -> tuple[list[Path], dict | None]:
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1400, "height": 1000}, accept_downloads=True)
        page = context.new_page()
        log(f"Loading {APP_URL} …")
        # networkidle never fires on this page (live-score polling never
        # stops), so wait for the basic load event plus a fixed settle time.
        page.goto(APP_URL, wait_until="load", timeout=60000)
        page.wait_for_timeout(3000)

        # Real ledger only exists in Supabase / the user's own browser — a
        # fresh headless session starts empty, so pull it in before
        # rendering anything that reads getP().
        bet_count = page.evaluate(
            """
            async () => {
              const r = await fetch(SUPABASE_URL + '/rest/v1/bets?select=raw&order=date.desc', {
                headers: { apikey: SUPABASE_KEY, Authorization: 'Bearer ' + SUPABASE_KEY }
              });
              if (!r.ok) return -1;
              const rows = await r.json();
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

        # Track Record always shows every period as its own row (today,
        # yesterday, rolling 7d, etc) in one card — no period selection
        # needed, "today" here just means the snapshot is dated/generated
        # as of today, which it already is by default.
        #
        # Sport Performance and League Performance are single-period cards
        # (renderTrackRecord._sportPeriod / _leaguePeriod, default
        # 'ALL TIME') — set to YESTERDAY before generating those two so the
        # daily card reflects yesterday's slate rather than the full
        # history every time.
        page.evaluate("() => { renderTrackRecord._sportPeriod = 'YESTERDAY'; renderTrackRecord._leaguePeriod = 'YESTERDAY'; }")

        for _, js_call, label in CARD_JOBS:
            log(f"Rendering {label} card…")
            with page.expect_download(timeout=15000) as download_info:
                page.evaluate(f"async () => {{ await {js_call}; }}")
            download = download_info.value
            path = out_dir / download.suggested_filename
            download.save_as(str(path))
            saved.append(path)
            log(f"  saved {path} ({path.stat().st_size/1024:.0f} KB)")

        # Pull yesterday's real record/win%/units straight from the same
        # data the Sport Performance card just drew (window._cvSportPeriodData
        # .totalP, set by _genSportPerfGraphic() above via renderTrackRecord())
        # rather than recomputing it separately in Python — guarantees the
        # caption numbers can never drift from what the card image itself
        # shows.
        stats = page.evaluate(
            """
            () => {
              const d = window._cvSportPeriodData;
              if (!d || !d.totalP) return null;
              return { w: d.totalP.w, l: d.totalP.l, pct: d.totalP.pct, units: d.totalP.units };
            }
            """
        )

        browser.close()

    if not saved:
        raise RuntimeError("No cards were captured — no downloads fired")

    return saved, stats


def build_captions(stats: dict | None) -> dict[str, str]:
    """
    IG/X captions for the daily post, paired with the Track Record /
    Sport Performance / League Performance cards. Record/win%/units come
    straight from the Sport Performance card's own yesterday-window totals
    (passed in via `stats`) so the caption can never say something the
    image doesn't back up.
    """
    from datetime import timedelta

    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    date_str = yesterday.strftime("%B %-d, %Y")  # e.g. "July 18, 2026"

    if stats and stats.get("w") is not None:
        record = f"{stats['w']}W-{stats['l']}L"
        pct = f"{stats['pct']*100:.1f}%" if stats.get("pct") is not None else "N/A"
        units = stats.get("units")
        units_str = f"{'+' if units is not None and units >= 0 else ''}{units:.1f}u" if units is not None else "N/A"
        tally_line = f"Final tally: {record} · {pct} win rate · {units_str}\n\n"
    else:
        tally_line = ""

    header = f"Yesterday's Performance — {date_str}"

    ig = (
        f"{header}\n\n"
        f"This is Clairvoyance.\n\n"
        f"{tally_line}"
        f"Every pick graded. Every line evaluated for edge. No guesswork.\n\n"
        f"Follow for daily signals, subscribe for exclusive graded picks, and intelligence briefs.\n\n"
        f"clairvoyanceengine.info\n"
        f"IG @clairvoyanceengine\n"
        f"X @clairvoyanceeng\n\n"
        f"#sportsbetting #bettingtips #bettingpicks #handicapping #sports"
    )

    x = (
        f"{header}\n\n"
        f"This is Clairvoyance.\n\n"
        f"{tally_line}"
        f"Every pick graded. Every line evaluated for edge. No guesswork.\n\n"
        f"Follow for daily signals, subscribe for exclusive graded picks, and intelligence briefs.\n\n"
        f"clairvoyanceengine.info\n\n"
        f"#sportsbetting #bettingtips #bettingpicks"
    )

    return {"instagram": ig, "x": x}


def send_email(cards: list[Path], captions: dict[str, str]) -> None:
    if not RESEND_API_KEY:
        log("RESEND_API_KEY not set — skipping email, cards saved locally only", )
        return
    if not SOCIAL_CARD_EMAIL_TO:
        log("SOCIAL_CARD_EMAIL_TO not set — skipping email, cards saved locally only")
        return

    today_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    attachments = []
    for path in cards:
        attachments.append({
            "filename": path.name,
            "content": base64.b64encode(path.read_bytes()).decode("ascii"),
        })

    filename_list_html = "".join(f"<li>{a['filename']}</li>" for a in attachments)

    def _caption_block(title: str, text: str) -> str:
        html_text = text.replace("\n", "<br>")
        return (
            f'<h3 style="margin-bottom:4px">{title}</h3>'
            f'<div style="background:#f5f5f5;border-radius:6px;padding:12px 16px;'
            f'font-family:monospace;font-size:13px;white-space:pre-wrap;margin-bottom:20px">{html_text}</div>'
        )

    body_html = (
        f"<p>Today's social cards are attached, ready to post:</p><ul>{filename_list_html}</ul>"
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
            "subject": f"Clairvoyance — Daily Social Cards ({today_str})",
            "html": body_html,
            "attachments": attachments,
        },
        timeout=30,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Resend send failed: HTTP {resp.status_code} {resp.text[:300]}")
    log(f"Email sent to {SOCIAL_CARD_EMAIL_TO} with {len(attachments)} card(s)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-email", action="store_true", help="generate cards only, skip sending")
    parser.add_argument("--out-dir", default="/tmp/cv_social_cards")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    cards, stats = generate_cards(out_dir)
    log(f"Generated {len(cards)} card(s) in {out_dir}")
    captions = build_captions(stats)
    log("Captions:\n--- INSTAGRAM ---\n" + captions["instagram"] + "\n--- X ---\n" + captions["x"])

    if not args.no_email:
        send_email(cards, captions)
    else:
        log("--no-email set, skipping send")


if __name__ == "__main__":
    main()
