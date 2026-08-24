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

Every caller wraps its own html_body in EMAIL_WRAP_OPEN/EMAIL_WRAP_CLOSE
before passing it to send_email() -- a plain white body band where the
caller's actual content (picks, results, whatever) renders. No logo/
image header: a styled-text version looked flat and wrong-font in a
real inbox (text-shadow and custom fonts are both unreliable in HTML
email), and the StandardLogo.png image version that replaced it didn't
look right either (mostly-empty 1080x1080 canvas scaled down small).
Simplest thing that actually looks right: no header art at all, just
the subject line and a clean white body.

Usage:
  from _gmail_email import send_email, EMAIL_WRAP_OPEN, EMAIL_WRAP_CLOSE
  ok, msg = send_email("Subject", "recipient@example.com", EMAIL_WRAP_OPEN + "<p>html body</p>" + EMAIL_WRAP_CLOSE)
  ok, msg = send_email("Subject", ["a@x.com", "b@x.com"], EMAIL_WRAP_OPEN + "<p>html body</p>" + EMAIL_WRAP_CLOSE)  # BCC'd -- see note below
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

# Shared chrome every email renders inside -- plain white body, no
# header art. Kept as OPEN/CLOSE (not a single wrap-everything helper)
# so callers can still build multi-part content around it.
EMAIL_WRAP_OPEN = (
    '<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
    'max-width:640px;margin:0 auto;background:#ffffff;color:#1a1a2e;padding:20px 16px">'
)
EMAIL_WRAP_CLOSE = '</div>'


def send_email(subject: str, to: str | list[str], html_body: str, attachments: list[Path] | None = None) -> tuple[bool, str]:
    """Never raises -- returns (success, message) so callers can log the
    result themselves the same way they logged Resend's HTTP response.

    `to` as a list (multiple paying subscribers on the same sport) sends
    to every address via BCC -- the To: header itself stays the sending
    account, so subscribers never see each other's email addresses. A
    single string still populates a real To: header as before."""
    if not GMAIL_APP_PASSWORD:
        return False, "GMAIL_APP_PASSWORD not set"
    recipients = [to] if isinstance(to, str) else list(dict.fromkeys(r for r in to if r))
    if not recipients:
        return False, "no recipient"

    msg = MIMEMultipart()
    msg["From"] = f"Clairvoyance Engine <{GMAIL_USER}>"
    msg["To"] = recipients[0] if len(recipients) == 1 else GMAIL_USER
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
            server.sendmail(GMAIL_USER, recipients, msg.as_string())
        return True, "sent"
    except Exception as exc:
        return False, str(exc)
