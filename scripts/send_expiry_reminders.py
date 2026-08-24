#!/usr/bin/env python3
"""
send_expiry_reminders.py — warns subscribers a few days before their
30-day access window lapses, so losing access isn't a surprise and they
have a chance to renew first. Each (email, product) pair only ever gets
warned once per window -- reminder_sent resets on every add/renew (see
_subscribers.add_subscriber()), so a later lapse-and-resubscribe cycle
gets its own fresh reminder too, not silently skipped forever.

Grouped by email: someone with multiple products expiring around the
same time gets ONE email listing all of them, not one per product.

Usage:
  python3 scripts/send_expiry_reminders.py [--days-before 3]
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _subscribers import subscribers_needing_reminder, mark_reminder_sent  # noqa: E402
from auto_lock_settle import PRODUCT_LABEL  # noqa: E402
from _gmail_email import send_email, EMAIL_WRAP_OPEN, EMAIL_WRAP_CLOSE  # noqa: E402


def _build_email(products_and_days: list[tuple[str, int]]) -> tuple[str, str]:
    """Returns (subject, html_body). products_and_days is a list of
    (product, days_left) for this one subscriber."""
    names = [PRODUCT_LABEL[p] for p, _ in products_and_days]
    soonest = min(d for _, d in products_and_days)

    if len(products_and_days) == 1:
        product, days = products_and_days[0]
        subject = f"Clairvoyance — {PRODUCT_LABEL[product]} access expires in {days} day{'s' if days != 1 else ''}"
    else:
        subject = f"Clairvoyance — {len(products_and_days)} subscriptions expiring soon"

    rows = "".join(
        f'<div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,.08);font-size:15px;color:#ddd">'
        f'<strong style="color:#fff">{PRODUCT_LABEL[p]}</strong> — '
        f'<span style="color:{"#ff3b5c" if d <= 1 else "#ffdd00"}">{d} day{"s" if d != 1 else ""} left</span>'
        f'</div>'
        for p, d in sorted(products_and_days, key=lambda x: x[1])
    )
    urgency = "expires today" if soonest <= 0 else f"expires in {soonest} day{'s' if soonest != 1 else ''}"
    body = (
        EMAIL_WRAP_OPEN +
        f'<div style="font-size:16px;color:#fff;margin-bottom:14px">'
        f'Your access to {", ".join(names)} {urgency}.</div>'
        f'<div style="background:#14001f;border-radius:6px;padding:4px 14px;margin-bottom:16px">{rows}</div>'
        f'<div style="font-size:14px;color:#ccc;line-height:1.6">'
        f'To keep it going with no gap in your daily picks, reply to this email or Venmo the usual '
        f'amount — we\'ll renew you for another 30 days from whenever it\'s received. '
        f'No action needed if you\'re fine letting it lapse.</div>' +
        EMAIL_WRAP_CLOSE
    )
    return subject, body


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days-before", type=int, default=3,
                     help="Send a reminder once a subscription has this many days (or fewer) left")
    ap.add_argument("--dry-run", action="store_true",
                     help="Log what would be sent without actually sending or marking reminder_sent")
    args = ap.parse_args()

    needing = subscribers_needing_reminder(days_before=args.days_before)
    if not needing:
        print("No subscribers need a reminder today.")
        return

    by_email: dict[str, list[tuple[str, int]]] = {}
    for row in needing:
        by_email.setdefault(row["email"], []).append((row["product"], row["days_left"]))

    for email, products_and_days in by_email.items():
        subject, body = _build_email(products_and_days)
        if args.dry_run:
            print(f"[DRY RUN] would email {email}: {subject}")
            continue
        ok, msg = send_email(subject, email, body)
        if ok:
            for product, _days in products_and_days:
                mark_reminder_sent(product, email)
            print(f"Reminder sent to {email} for {[p for p, _ in products_and_days]}")
        else:
            print(f"FAILED to send reminder to {email}: {msg}")


if __name__ == "__main__":
    main()
