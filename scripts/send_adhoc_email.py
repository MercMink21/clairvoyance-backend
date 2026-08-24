#!/usr/bin/env python3
"""
send_adhoc_email.py — one-off asset delivery via Gmail SMTP (_gmail_email.py), for content that
isn't part of the scheduled generate_social_cards.py pipeline (manual
requests, spot-checks, one-time exports).

Usage:
  python3 scripts/send_adhoc_email.py --subject "..." --intro "..." \
      --file path/to/one.mp4 --file path/to/two.png
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _gmail_email import send_email as _send_gmail  # noqa: E402
from _gmail_email import EMAIL_WRAP_OPEN as _EMAIL_WRAP_OPEN, EMAIL_WRAP_CLOSE as _EMAIL_WRAP_CLOSE  # noqa: E402

SOCIAL_CARD_EMAIL_TO = os.environ.get("SOCIAL_CARD_EMAIL_TO", "")


def _caption_block(title: str, text: str) -> str:
    html_text = text.replace("\n", "<br>")
    return (
        f'<h3 style="margin-bottom:4px;color:#1a1a2e">{title}</h3>'
        f'<div style="background:#14001f;border-radius:6px;padding:12px 16px;color:#eee;'
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
    if not recipient:
        raise RuntimeError("No recipient (pass --to or set SOCIAL_CARD_EMAIL_TO)")

    file_paths = [Path(f) for f in args.files]
    filename_list_html = "".join(f"<li>{p.name}</li>" for p in file_paths)
    body_html = _EMAIL_WRAP_OPEN + f"<p>{args.intro}</p><p>Attached:</p><ul>{filename_list_html}</ul>"
    if args.caption_ig or args.caption_x:
        body_html += "<p>Captions below, ready to copy-paste:</p>"
        if args.caption_ig:
            body_html += _caption_block("Instagram caption", args.caption_ig)
        if args.caption_x:
            body_html += _caption_block("X caption", args.caption_x)
    body_html += _EMAIL_WRAP_CLOSE

    ok, msg = _send_gmail(args.subject, recipient, body_html, attachments=file_paths)
    if not ok:
        raise RuntimeError(f"Gmail send failed: {msg}")
    print(f"Email sent: {args.subject} ({len(file_paths)} attachment(s))")


if __name__ == "__main__":
    main()
