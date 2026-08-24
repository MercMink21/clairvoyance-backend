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

Every email sent through send_email() automatically gets the CLAIRVOYANCE
/ ADVANCED SPORTS INTELLIGENCE ENGINE brand header prepended -- callers
don't add it themselves. Callers SHOULD still wrap their own html_body in
EMAIL_WRAP_OPEN/EMAIL_WRAP_CLOSE (the shared dark-card body chrome) so
the header flows into the body with no visual seam -- send_email() only
owns the header, not the body wrapper, since some callers build multi-
part content around it.

Usage:
  from _gmail_email import send_email, EMAIL_WRAP_OPEN, EMAIL_WRAP_CLOSE
  ok, msg = send_email("Subject", "recipient@example.com", EMAIL_WRAP_OPEN + "<p>html body</p>" + EMAIL_WRAP_CLOSE)
  ok, msg = send_email("Subject", "recipient@example.com", "<p>html body</p>", attachments=[Path("card.png")])
  ok, msg = send_email("Subject", ["a@x.com", "b@x.com"], "<p>html body</p>")  # BCC'd -- see note below
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

# Same wordmark treatment as the live site and the local subscriber admin
# page: "CLAIRVOYANCE" in neon magenta, "ADVANCED SPORTS INTELLIGENCE
# ENGINE" in neon cyan. Prepended here (not in each caller) so every email
# this system sends -- locks, settlement, social cards, ad-hoc -- carries
# it automatically regardless of sport, with nothing to remember to add
# per email builder. text-shadow (the glow) is stripped by some email
# clients (Outlook, some Gmail views); the plain magenta/cyan colors
# still come through everywhere, which is the part that actually matters.
# Same background image the live site (clairvoyanceengine.info) uses
# behind its own body -- referenced by its real public URL (not a data
# URI: emails already run large from attachments, and this keeps the
# image cacheable across every send instead of re-embedding ~1MB each
# time) so the email actually looks like it belongs to the same product
# instead of a plain flat card. background-color is the fallback for
# clients that block remote images by default (Outlook, and Gmail until
# "display images" is allowed) -- same dark tone the site itself falls
# back to before its own image loads.
_BG_STYLE = ("background-color:#16122a;background-image:url('https://clairvoyanceengine.info/bg.jpg');"
             "background-size:cover;background-position:center center;")

_BRAND_HEADER = (
    f'<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
    f'max-width:640px;margin:0 auto;text-align:center;padding:20px 16px 16px;{_BG_STYLE}">'
    '<div style="font-size:24px;font-weight:900;letter-spacing:4px;color:#f000ff;'
    'text-shadow:0 0 10px #f000ff,0 0 24px rgba(240,0,255,.6)">CLAIRVOYANCE</div>'
    '<div style="font-size:11px;letter-spacing:3px;color:#00f0ff;'
    'text-shadow:0 0 8px rgba(0,240,255,.5);margin-top:5px;text-transform:uppercase">'
    'Advanced Sports Intelligence Engine</div>'
    '</div>'
)

# Shared body chrome -- every email's actual content renders inside this
# same card shell (not just the header above it) so every script that
# sends mail through here reads as one consistent product instead of
# some emails carrying the site's look and others dropping into a plain
# flat background right below the branded header. Callers wrap their
# own html_body with EMAIL_WRAP_OPEN/EMAIL_WRAP_CLOSE before passing it
# to send_email() -- kept as two pieces (not done automatically here)
# because some callers build multi-part content around it.
EMAIL_WRAP_OPEN = (f'<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
                    f'max-width:640px;margin:0 auto;color:#e8e8e8;padding:20px 16px;{_BG_STYLE}">')
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
    msg.attach(MIMEText(_BRAND_HEADER + html_body, "html"))

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
