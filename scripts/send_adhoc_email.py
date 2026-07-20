#!/usr/bin/env python3
"""
send_adhoc_email.py — one-off asset delivery via Resend, for content that
isn't part of the scheduled generate_social_cards.py pipeline (manual
requests, spot-checks, one-time exports).

Usage:
  python3 scripts/send_adhoc_email.py --subject "..." --intro "..." \
      --file path/to/one.mp4 --file path/to/two.png
"""
import argparse
import base64
import os

import requests

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SOCIAL_CARD_EMAIL_TO = os.environ.get("SOCIAL_CARD_EMAIL_TO", "")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", required=True)
    parser.add_argument("--intro", default="")
    parser.add_argument("--file", action="append", dest="files", required=True)
    args = parser.parse_args()

    if not RESEND_API_KEY or not SOCIAL_CARD_EMAIL_TO:
        raise RuntimeError("RESEND_API_KEY / SOCIAL_CARD_EMAIL_TO not set")

    attachments = []
    for f in args.files:
        with open(f, "rb") as fh:
            attachments.append({
                "filename": os.path.basename(f),
                "content": base64.b64encode(fh.read()).decode("ascii"),
            })

    filename_list_html = "".join(f"<li>{a['filename']}</li>" for a in attachments)
    body_html = f"<p>{args.intro}</p><p>Attached:</p><ul>{filename_list_html}</ul>"

    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={
            "from": "Clairvoyance Engine <onboarding@resend.dev>",
            "to": [SOCIAL_CARD_EMAIL_TO],
            "subject": args.subject,
            "html": body_html,
            "attachments": attachments,
        },
        timeout=30,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Resend send failed: HTTP {resp.status_code} {resp.text[:300]}")
    print(f"Email sent: {args.subject} ({len(attachments)} attachment(s))")


if __name__ == "__main__":
    main()
