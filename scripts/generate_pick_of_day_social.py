#!/usr/bin/env python3
"""
generate_pick_of_day_social.py — top-3 picks of the day as three separate
Instagram-ready posts (video + still + caption each), emailed for manual
review/posting.

Reuses the existing dormant record_free_pick_reveal()/record_free_pick_still()
templates in generate_video_reveal.py (glitch-reveal aesthetic matching the
daily stats videos) rather than a new combined "top 3 in one graphic" layout
-- a template that's already designed and battle-tested, and single-highlight
posts read better on IG than a dense list crammed into one graphic. Each of
the 3 picks gets its own video, its own still, and its own caption -- three
distinct posts, not one post with three picks in it.

Deliberately does NOT hook into auto_lock_settle.py's live run_lock_segmented()
pipeline (the actual locking pass) -- that's a sensitive, real-money-adjacent
process this script has no business touching. Instead it independently
re-runs gather_legs()/build_qualifying() (both pure read/classify functions,
no locking side effects) against the same live app, purely to get today's
qualifying list for selection. This duplicates a bit of compute but keeps
this script fully decoupled from the live lock pipeline -- a bug or crash
here can never affect real subscriber locks.

Selection: PREMIUM before OPTIMAL/props of either grade (LEAN/SKIP legs
never reach build_qualifying() at all except via the HIGH HIT % exception --
see auto_lock_settle.py), then by EV descending as the tiebreaker within a
tier. Props carry no EV in the underlying data, so they sort after
EV-bearing game legs at the same grade rather than ahead of them.

Usage:
  python3 scripts/generate_pick_of_day_social.py [--no-email] [--out-dir DIR]
"""
from __future__ import annotations
import argparse
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from auto_lock_settle import (  # noqa: E402
    APP_URL, load_bet_ledger, gather_legs, build_qualifying,
    SPORT_DISPLAY_NAME, TIER_LABEL, _prop_matchup_key, log,
)
from _gmail_email import send_email as _send_gmail  # noqa: E402
from _gmail_email import EMAIL_WRAP_OPEN as _EMAIL_WRAP_OPEN, EMAIL_WRAP_CLOSE as _EMAIL_WRAP_CLOSE  # noqa: E402

import os
SOCIAL_CARD_EMAIL_TO = os.environ.get("SOCIAL_CARD_EMAIL_TO", "")

_MT = ZoneInfo("America/Denver")


def _mt_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(_MT)


def _candidate_from_game(q: dict) -> dict:
    tier_n = q["tierN"]
    return {
        "sport": q["sport"],
        "matchup": f"{q['awA']} @ {q['hA']}",
        "pick": q["label"],
        "grade": TIER_LABEL.get(tier_n, "?"),
        "rank_tier": tier_n,
        "ev": q.get("evVal"),
    }


def _candidate_from_prop(q: dict) -> dict:
    leg = q["leg"]
    direction = "UNDER" if leg.get("over") is False else "OVER"
    grade = leg.get("grade") or "?"
    rank_tier = {"PREMIUM": 3, "OPTIMAL": 2}.get(grade, 1)
    return {
        "sport": q["sport"],
        "matchup": _prop_matchup_key(leg),
        "pick": f"{leg.get('player')} {direction} {leg.get('line')} {leg.get('stat')}",
        "grade": grade,
        "rank_tier": rank_tier,
        "ev": None,
    }


def select_top_picks(qualifying: list[dict], n: int = 3) -> list[dict]:
    """PREMIUM before OPTIMAL, then EV descending within a tier. Missing EV
    (every prop, per this file's module docstring) sorts to the bottom of
    its tier rather than the top, so an EV-bearing game leg always outranks
    a same-graded prop."""
    candidates = [
        _candidate_from_game(q) if q["kind"] == "GAME" else _candidate_from_prop(q)
        for q in qualifying
    ]
    candidates.sort(key=lambda c: (-c["rank_tier"], -(c["ev"] if c["ev"] is not None else -999)))
    return candidates[:n]


def build_pick_caption(c: dict, date_str: str) -> str:
    sport_label = SPORT_DISPLAY_NAME.get(c["sport"], c["sport"])
    ev_line = f"Model edge: EV {c['ev']*100:+.1f}%\n\n" if c["ev"] is not None else ""
    return (
        f"🔒 {c['grade']} PICK — {date_str}\n\n"
        f"{sport_label}: {c['matchup']}\n"
        f"{c['pick']}\n\n"
        f"{ev_line}"
        "Model output, not a guarantee -- full reasoning and every graded pick inside.\n\n"
        "clairvoyanceengine.info\n"
        "IG @clairvoyanceengine | X @clairvoyanceeng\n\n"
        "#sportsbetting #bettingpicks #sportsanalytics"
    )


def send_pick_posts(picks_with_captions: list[dict], out_dir: Path, date_str: str) -> None:
    """One email, three clearly-labeled sections (not three separate
    emails) -- easier to review and post from in one pass. Each section's
    video + still are both attached; the caption is inline, ready to
    copy-paste."""
    if not SOCIAL_CARD_EMAIL_TO:
        log("No recipient set (SOCIAL_CARD_EMAIL_TO) — skipping send")
        return
    all_attachments: list[Path] = []
    sections = []
    for i, item in enumerate(picks_with_captions, start=1):
        all_attachments.append(item["video_path"])
        all_attachments.append(item["still_path"])
        caption_html = item["caption"].replace("\n", "<br>")
        sections.append(
            f'<h3 style="margin:24px 0 4px;color:#1a1a2e">Pick {i} of {len(picks_with_captions)} — '
            f'{item["candidate"]["grade"]} — {item["candidate"]["matchup"]}</h3>'
            f'<p style="color:#555;font-size:13px">Files: {item["video_path"].name}, {item["still_path"].name}</p>'
            f'<div style="background:#14001f;border-radius:6px;padding:12px 16px;color:#eee;'
            f'font-family:monospace;font-size:13px;white-space:pre-wrap">{caption_html}</div>'
        )
    body_html = (
        _EMAIL_WRAP_OPEN +
        f"<p>Top {len(picks_with_captions)} picks for {date_str} — one post each, ranked "
        "PREMIUM before OPTIMAL, then by EV.</p>" +
        "".join(sections) +
        _EMAIL_WRAP_CLOSE
    )
    subject = f"Clairvoyance — Top {len(picks_with_captions)} Picks Social Posts for {date_str}"
    ok, msg = _send_gmail(subject, SOCIAL_CARD_EMAIL_TO, body_html, attachments=all_attachments)
    if not ok:
        raise RuntimeError(f"Gmail send failed for '{subject}': {msg}")
    log(f"Email sent: {subject} ({len(all_attachments)} attachment(s))")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-email", action="store_true", help="generate video/stills only, skip sending")
    ap.add_argument("--out-dir", default="/tmp/cv_pick_of_day_social")
    ap.add_argument("--app-url", default=APP_URL)
    ap.add_argument("--top-n", type=int, default=3)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    now_mt = _mt_now()
    date_str = now_mt.strftime("%B %-d, %Y")
    date_tag = now_mt.strftime("%Y%m%d")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1400, "height": 1000})
        page = context.new_page()
        log(f"Loading {args.app_url} …")
        page.goto(args.app_url, wait_until="load", timeout=60000)
        page.wait_for_timeout(3000)

        bet_count = load_bet_ledger(page)
        log(f"Loaded {bet_count} real bets from Supabase into headless session")

        result = gather_legs(page)
        qualifying = build_qualifying(result)
        log(f"{len(qualifying)} qualifying PREMIUM/OPTIMAL(+HIGH HIT) legs found today")

        browser.close()

    if not qualifying:
        log("No qualifying legs today — nothing to post.")
        return

    top_picks = select_top_picks(qualifying, n=args.top_n)
    log(f"Selected top {len(top_picks)}: " +
        "; ".join(f"{c['grade']} {c['matchup']} — {c['pick']}" for c in top_picks))

    from generate_video_reveal import record_free_pick_reveal, record_free_pick_still

    picks_with_captions = []
    for i, c in enumerate(top_picks, start=1):
        sport_label = SPORT_DISPLAY_NAME.get(c["sport"], c["sport"])
        video_path = out_dir / f"cv-pick{i}-{date_tag}.mp4"
        still_path = out_dir / f"cv-pick{i}-still-{date_tag}.png"
        record_free_pick_reveal(sport_label, c["matchup"], c["pick"], c["grade"], video_path, date_str=date_str)
        record_free_pick_still(sport_label, c["matchup"], c["pick"], c["grade"], still_path, date_str=date_str)
        log(f"Pick {i} rendered: {video_path.name}, {still_path.name}")
        picks_with_captions.append({
            "candidate": c,
            "video_path": video_path,
            "still_path": still_path,
            "caption": build_pick_caption(c, date_str),
        })

    if not args.no_email:
        send_pick_posts(picks_with_captions, out_dir, date_str)


if __name__ == "__main__":
    main()
