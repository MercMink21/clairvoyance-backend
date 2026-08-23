"""
_gmail_email.py — shared Gmail SMTP sender for every Clairvoyance email
script (auto_lock_settle.py's locks/settlement emails, generate_social_cards.
py's daily card email, send_adhoc_email.py's one-off sends).

Replaces Resend: Resend's sandbox mode only lets the `from` address send to
the account owner's own verified email, and full domain verification wasn't
worth the DNS setup + propagation wait for this volume (a handful of emails
a day). Gmail SMTP sends from/to any address once you hold an App Password
for the sending account -- no domain verification needed at all.

GMAIL_USER is the sending account (also the account the App Password was
generated for -- these are tightly coupled, changing one without the other
breaks auth, so this is a plain constant rather than a second secret).

Usage:
  from _gmail_email import send_email
  ok, msg = send_email("Subject", "recipient@example.com", "<p>html body</p>")
  ok, msg = send_email("Subject", "recipient@example.com", "<p>html body</p>", attachments=[Path("card.png")])
"""
from __future__ import annotations
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

GMAIL_USER = "clairvoyanceengine@gmail.com"
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")


def send_email(subject: str, to: str, html_body: str, attachments: list[Path] | None = None) -> tuple[bool, str]:
    """Never raises -- returns (success, message) so callers can log the
    result themselves the same way they logged Resend's HTTP response."""
    if not GMAIL_APP_PASSWORD:
        return False, "GMAIL_APP_PASSWORD not set"
    if not to:
        return False, "no recipient"

    msg = MIMEMultipart()
    msg["From"] = f"Clairvoyance Engine <{GMAIL_USER}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    for path in attachments or []:
        path = Path(path)
        with open(path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={path.name}")
        msg.attach(part)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, [to], msg.as_string())
        return True, "sent"
    except Exception as exc:
        return False, str(exc)
