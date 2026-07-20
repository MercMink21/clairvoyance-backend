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


def _caption_block(title: str, text: str) -> str:
    html_text = text.replace("\n", "<br>")
    return (
        f'<h3 style="margin-bottom:4px">{title}</h3>'
        f'<div style="background:#f5f5f5;border-radius:6px;padding:12px 16px;'
        f'font-family:monospace;font-size:13px;white-space:pre-wrap;margin-bottom:20px">{html_text}</div>'
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", required=True)
    parser.add_argument("--intro", default="")
    parser.add_argument("--caption-ig", default=None)
    parser.add_argument("--caption-x", default=None)
    parser.add_argument("--to", default=None, help="Override recipient (defaults to SOCIAL_CARD_EMAIL_TO)")
    parser.add_argument("--file", action="append", dest="files", required=True)
    args = parser.parse_args()

    recipient = args.to or SOCIAL_CARD_EMAIL_TO
    if not RESEND_API_KEY or not recipient:
        raise RuntimeError("RESEND_API_KEY not set, or no recipient (pass --to or set SOCIAL_CARD_EMAIL_TO)")

    attachments = []
    for f in args.files:
        with open(f, "rb") as fh:
            attachments.append({
                "filename": os.path.basename(f),
                "content": base64.b64encode(fh.read()).decode("ascii"),
            })

    filename_list_html = "".join(f"<li>{a['filename']}</li>" for a in attachments)
    body_html = f"<p>{args.intro}</p><p>Attached:</p><ul>{filename_list_html}</ul>"
    if args.caption_ig or args.caption_x:
        body_html += "<p>Captions below, ready to copy-paste:</p>"
        if args.caption_ig:
            body_html += _caption_block("Instagram caption", args.caption_ig)
        if args.caption_x:
            body_html += _caption_block("X caption", args.caption_x)

    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={
            "from": "Clairvoyance Engine <onboarding@resend.dev>",
            "to": [recipient],
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
