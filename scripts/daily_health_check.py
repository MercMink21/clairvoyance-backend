#!/usr/bin/env python3
"""
daily_health_check.py — durable replacement for what used to be a
session-only "check the daily jobs actually ran" reminder. Runs once a
day via .github/workflows/daily-health-check.yml, checks every other
scheduled daily workflow in this repo for two failure modes a human
watching casually would otherwise have to notice themselves:

  1. MISSING -- no run at all in the last ~26 hours (the real 2026-08-06
     incident this project already has on record: two Playwright-heavy
     jobs landing ~22min apart queue-starved each other so badly one of
     them never got a runner at all -- GitHub never "fails" that, it just
     silently never runs).
  2. FAILED -- the most recent run happened, but its conclusion wasn't
     "success".

Deliberately silent on a clean day (matches "hands-off" -- nobody wants a
daily "all good" email); only sends anything when there's a real finding.
Uses the repo's own default GITHUB_TOKEN (Actions API read access), not a
personal one -- nothing extra to configure.
"""
from __future__ import annotations
import os
import sys
import urllib.request
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _gmail_email import send_email  # noqa: E402

REPO = "MercMink21/clairvoyance-backend"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
ALERT_TO = os.environ.get("SOCIAL_CARD_EMAIL_TO", "") or os.environ.get("LOCKS_EMAIL_TO", "")

# (workflow filename, human label, how many hours old a run can be before
# it's considered "missing" -- a bit more than 24h to absorb normal
# schedule jitter, per this repo's own documented pattern of GH delaying
# scheduled runs 30-90+ minutes past nominal cron time).
MONITORED = [
    ("auto-lock-settle.yml", "Main Auto-Lock (all 8 products)", 26),
    ("soccer-lock-early.yml", "Soccer Early Lock", 26),
    ("cfb-lock-early.yml", "CFB Early Lock", 26),
    ("send-expiry-reminders.yml", "Expiry Reminders", 26),
    ("social-cards-daily.yml", "Social Cards Daily", 26),
    ("pick-of-day-social-daily.yml", "Pick-of-Day Social", 26),
]


def _api_get(path: str) -> dict:
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def check_workflow(filename: str, label: str, max_age_hours: int) -> str | None:
    """Returns a short problem description, or None if this workflow looks
    healthy (a real run within the window, and it succeeded)."""
    try:
        data = _api_get(f"/repos/{REPO}/actions/workflows/{filename}/runs?per_page=5")
    except Exception as exc:
        return f"{label}: couldn't check ({exc})"

    runs = data.get("workflow_runs") or []
    if not runs:
        return f"{label}: no runs found at all"

    latest = runs[0]
    created = datetime.fromisoformat(latest["created_at"].replace("Z", "+00:00"))
    age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
    if age_hours > max_age_hours:
        return f"{label}: last run was {age_hours:.1f}h ago (expected within {max_age_hours}h) -- may have been queue-starved or the schedule didn't fire"

    if latest.get("status") == "completed" and latest.get("conclusion") != "success":
        return f"{label}: most recent run {latest.get('conclusion')} ({latest.get('html_url')})"

    return None


def main() -> None:
    if not GITHUB_TOKEN:
        print("GITHUB_TOKEN not set -- can't check Actions API, skipping.")
        return

    problems = [p for p in (check_workflow(f, l, h) for f, l, h in MONITORED) if p]

    if not problems:
        print("All monitored workflows healthy -- no alert sent.")
        return

    print(f"{len(problems)} issue(s) found:")
    for p in problems:
        print(f"  - {p}")

    if not ALERT_TO:
        print("No alert recipient configured (SOCIAL_CARD_EMAIL_TO/LOCKS_EMAIL_TO unset) -- can't email this.")
        return

    body = (
        '<div style="font-family:monospace;font-size:14px;color:#1a1a2e">'
        '<p><strong>Daily health check found issue(s):</strong></p>'
        '<ul>' + "".join(f"<li>{p}</li>" for p in problems) + '</ul>'
        '</div>'
    )
    ok, msg = send_email("Clairvoyance -- daily health check found an issue", ALERT_TO, body)
    print(f"Alert email sent to {ALERT_TO}" if ok else f"Alert email FAILED: {msg}")


if __name__ == "__main__":
    main()
