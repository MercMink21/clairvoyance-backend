#!/usr/bin/env python3
"""
verify_lock_workflows.py — durable replacement for the manual "did the 3
lock workflows actually go live and lock+send today" check that used to
run as a session-only reminder (dies with the session, auto-expires
after 7 days regardless). This is the deep, content-aware version: not
just "did it run and succeed" (see daily_health_check.py for that shallow
net across all 6 daily workflows) but "did it actually resolve --live
and produce the real lock/email output", by grepping the run's own log --
the exact same manual check this replaces (gh run list -> gh run view
--log -> grep for the invoked command line + success markers).

Catches three distinct failure modes, all real risks documented
elsewhere in this repo:
  1. Didn't fire at all today (the 2026-08-06 queue-starvation incident --
     GitHub never "fails" that, the run just never gets a runner).
  2. Fired but errored (status completed, conclusion != success).
  3. Fired, succeeded, but silently stayed dry-run or errored after
     starting -- caught by grepping the actual log content, not just the
     GitHub-reported conclusion, since a script that runs to completion
     without an unhandled exception still reports "success" even if
     LIVE_MODE didn't apply or a step failed inside a try/except.

Silent on a clean day, matching the hands-off preference already
established for daily_health_check.py -- only emails when it finds a
real problem.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _gmail_email import send_email  # noqa: E402

ALERT_TO = os.environ.get("LOCKS_EMAIL_TO", "") or os.environ.get("SOCIAL_CARD_EMAIL_TO", "")


def _gh(*args: str) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _recent_runs(workflow: str, limit: int = 8) -> list[dict]:
    out = _gh("run", "list", "--workflow", workflow, "--limit", str(limit),
               "--json", "databaseId,createdAt,event,status,conclusion")
    return json.loads(out)


def _log_text(run_id: int) -> str:
    return _gh("run", "view", str(run_id), "--log")


def _check_run(run: dict, label: str, expect_markers: list[str]) -> str | None:
    """Runs the deep content check on one already-identified run.
    Returns a problem string, or None if it looks healthy."""
    if run["status"] != "completed":
        return f"{label}: run {run['databaseId']} still {run['status']} (not completed)"
    if run["conclusion"] != "success":
        return f"{label}: run {run['databaseId']} concluded '{run['conclusion']}', not success"

    try:
        log = _log_text(run["databaseId"])
    except Exception as exc:
        return f"{label}: couldn't fetch log for run {run['databaseId']} ({exc})"

    cmd_lines = [l for l in log.splitlines() if "python3 scripts/auto_lock_settle.py" in l and "##[group]Run" in l]
    if not cmd_lines:
        return f"{label}: run {run['databaseId']} succeeded but no auto_lock_settle.py invocation found in log at all"
    invoked = cmd_lines[-1]
    if "--live" not in invoked:
        return f"{label}: run {run['databaseId']} did NOT include --live (stayed dry-run) -- invoked: {invoked.split('Run ',1)[-1].strip()}"

    missing = [m for m in expect_markers if m not in log]
    if missing:
        return f"{label}: run {run['databaseId']} ran --live but missing expected log line(s): {missing}"

    return None


def check_cfb_early() -> str | None:
    runs = _recent_runs("CFB Auto Lock (Early)")
    todays = [r for r in runs if r["event"] == "schedule" and r["createdAt"].startswith(_today_utc())]
    if not todays:
        return "CFB Early Lock: no schedule-triggered run found today"
    return _check_run(todays[0], "CFB Early Lock",
                       ["=== AUTO-LOCK (PREMIUM/OPTIMAL) — CFB ===", "Locks email (CFB)"])


def check_soccer_early() -> str | None:
    runs = _recent_runs("Soccer Auto Lock (Early)")
    todays = [r for r in runs if r["event"] == "schedule" and r["createdAt"].startswith(_today_utc())]
    if not todays:
        return "Soccer Early Lock: no schedule-triggered run found today"
    return _check_run(todays[0], "Soccer Early Lock",
                       ["=== AUTO-LOCK (PREMIUM/OPTIMAL) — SOCCER ===", "Locks email (SOCCER)"])


def check_main_lock() -> str | None:
    """The main workflow fires 5x/day on one shared schedule trigger (1
    lock pass + 4 settle passes) -- have to find the specific LOCK run
    among today's schedule runs by checking each candidate's own log,
    since the GitHub API's run metadata alone doesn't distinguish them."""
    runs = _recent_runs("Auto Lock + Settle", limit=8)
    todays = [r for r in runs if r["event"] == "schedule" and r["createdAt"].startswith(_today_utc())]
    if not todays:
        return "Main Lock: no schedule-triggered run found today at all"

    for run in todays:
        if run["status"] != "completed":
            continue
        try:
            log = _log_text(run["databaseId"])
        except Exception:
            continue
        cmd_lines = [l for l in log.splitlines() if "python3 scripts/auto_lock_settle.py" in l and "##[group]Run" in l]
        if cmd_lines and "--lock" in cmd_lines[-1] and "--settle" not in cmd_lines[-1]:
            # Found today's lock pass -- run the full content check on it.
            problem = _check_run(run, "Main Lock", ["=== AUTO-LOCK (PREMIUM/OPTIMAL) — ALL PRODUCTS ==="])
            if problem:
                return problem
            email_count = log.count("Locks email (")
            if email_count < 5:
                return f"Main Lock: run {run['databaseId']} only shows {email_count} 'Locks email' line(s), expected ~9 (8 products + OTHER)"
            return None

    return "Main Lock: today's schedule runs exist but none was identifiable as the lock pass (all settle, or none completed)"


def main() -> None:
    checks = [check_main_lock, check_cfb_early, check_soccer_early]
    problems = []
    for check in checks:
        try:
            result = check()
        except Exception as exc:
            result = f"{check.__name__}: check itself errored ({exc})"
        if result:
            problems.append(result)

    if not problems:
        print("All 3 lock workflows confirmed live and successful today.")
        return

    print(f"{len(problems)} issue(s) found:")
    for p in problems:
        print(f"::error::{p}")

    if not ALERT_TO:
        print("No alert recipient configured -- can't email this.")
        return

    body = (
        '<div style="font-family:monospace;font-size:14px;color:#1a1a2e">'
        '<p><strong>Lock workflow verification found issue(s) today:</strong></p>'
        '<ul>' + "".join(f"<li>{p}</li>" for p in problems) + '</ul>'
        '<p>Check the Actions tab for full run logs.</p>'
        '</div>'
    )
    ok, msg = send_email("Clairvoyance -- lock workflow verification FAILED", ALERT_TO, body)
    print(f"Alert email sent to {ALERT_TO}" if ok else f"Alert email FAILED: {msg}")


if __name__ == "__main__":
    main()
