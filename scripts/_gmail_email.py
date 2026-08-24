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
before passing it to send_email() -- EMAIL_WRAP_OPEN already contains the
CLAIRVOYANCE brand header. Two deliberate regions inside one outer
wrapper, applied identically on every send (not something each caller
re-decides): a header band carrying the site's own background image
(matches clairvoyanceengine.info's look, holds only the logo), and a
plain white body band beneath it where the caller's actual content
(picks, results, whatever) renders -- picks read far better against a
clean white background than against a busy image, and individual pick/
leg cards (still their own dark panels, see auto_lock_settle.py) pop
more against white than they did against the old all-dark card.

The header logo is a real PNG (StandardLogo.png, hosted live at
clairvoyanceengine.info), not styled text -- text-shadow glow and the
Orbitron font are both unreliable in HTML email (Outlook strips
text-shadow outright; custom @font-face/Google Fonts links are stripped
by most clients including Gmail), so what rendered as flat, wrong-font
text in a real inbox is the exact same asset the site itself uses for
its own logo, guaranteed to render pixel-correct anywhere images display
at all.

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

# StandardLogo.png -- "CLAIRVOYANCE" in neon magenta + "ADVANCED SPORTS
# INTELLIGENCE ENGINE" in neon cyan, already rendered as pixels on the
# same diamond-grid background the site itself uses. A real PNG instead
# of styled text on purpose: text-shadow (the glow) is stripped outright
# by Outlook and inconsistently elsewhere, and Google Fonts links are
# stripped by most email clients including Gmail, so styled text renders
# as flat, wrong-font text in a real inbox -- an image is immune to both.
_HEADER_IMG = (
    '<img src="https://clairvoyanceengine.info/StandardLogo.png" width="320" '
    'alt="Clairvoyance — Advanced Sports Intelligence Engine" '
    'style="display:block;width:100%;max-width:320px;height:auto;margin:0 auto 16px">'
)

# Shared chrome every email renders inside: an outer layout-only wrapper,
# a header band (site background image + logo), then a white body band
# where the caller's own content goes. Two regions, always the same two
# regions, so "header looks like the site, body is clean and readable"
# is a fixed structural rule instead of something that can drift.
EMAIL_WRAP_OPEN = (
    '<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:640px;margin:0 auto">'
    f'<div style="{_BG_STYLE}padding:24px 16px 20px;text-align:center">{_HEADER_IMG}</div>'
    '<div style="background:#ffffff;color:#1a1a2e;padding:20px 16px">'
)
EMAIL_WRAP_CLOSE = '</div></div>'


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
