"""
_subscribers.py — shared subscriber-list loader for segmented per-sport
locks emails, with 30-day access windows.

MVP: manually-edited data/subscribers.json, no payment automation yet.
Venmo is the payment method for now -- when someone pays, add them with
manage_subscribers.py (or call add_subscriber() directly) and commit the
resulting file. No webhook, no database; this is intentionally the
simplest thing that works for a manually-tracked MVP.

Schema: {"nfl": [{"email": "a@x.com", "added": "2026-08-23T00:00:00+00:00"},
...], ...} -- one list of timestamped entries per paid product. "added" is
the access-window start; recipients_for() only includes entries less than
EXPIRY_DAYS old, so a subscriber silently drops off the list 30 days after
they were added (or last renewed) without anyone having to remember to
remove them by hand. Re-adding an email that's already on a product's list
renews it -- resets "added" to now rather than creating a duplicate entry.

The account owner's own address is always included for every product
regardless of subscriber list state, so the personal daily reference
this was originally built for keeps working with zero paying subscribers.

8 paid products (confirmed structure): nfl, cfb, nba, wnba, mlb, hockey
(NHL + KHL/SHL/LIIGA bundled -- those 3 have no real game cards wired up
yet, but the product covers them too so nothing needs to change here
once they are), soccer (all 6 leagues bundled -- the 5 European leagues
+ MLS -- as one purchase, not sold separately), tennis (ATP + WTA
bundled as one purchase).
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

SUBSCRIBERS_FILE = Path(__file__).resolve().parent.parent / "data" / "subscribers.json"
PRODUCTS = ("nfl", "cfb", "nba", "wnba", "mlb", "hockey", "soccer", "tennis")
OWNER_EMAIL = os.environ.get("LOCKS_EMAIL_TO", "") or os.environ.get("SOCIAL_CARD_EMAIL_TO", "")
EXPIRY_DAYS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def load_subscribers() -> dict[str, list[dict]]:
    """Raw file contents -- every product's full entry list, expired or
    not. Callers that care about active-only access should use
    recipients_for()/active_subscribers() instead."""
    try:
        return json.loads(SUBSCRIBERS_FILE.read_text())
    except Exception:
        return {}


def save_subscribers(data: dict[str, list[dict]]) -> None:
    SUBSCRIBERS_FILE.write_text(json.dumps(data, indent=2) + "\n")


def _is_active(entry: dict, now: datetime) -> bool:
    added = _parse(entry.get("added", ""))
    return added is not None and now - added < timedelta(days=EXPIRY_DAYS)


def active_subscribers(product: str) -> list[dict]:
    """Non-expired entries for this product, each with a computed
    days_left so callers (the CLI, mainly) don't have to redo the date
    math themselves."""
    now = _now()
    out = []
    for entry in load_subscribers().get(product, []):
        added = _parse(entry.get("added", ""))
        if added is None or now - added >= timedelta(days=EXPIRY_DAYS):
            continue
        days_left = EXPIRY_DAYS - (now - added).days
        out.append({"email": entry["email"], "added": entry["added"], "days_left": days_left})
    return out


def recipients_for(product: str) -> list[str]:
    """Owner + every subscriber whose 30-day window hasn't expired,
    deduped, order preserved (owner first)."""
    subs = [e["email"] for e in active_subscribers(product)]
    seen: list[str] = []
    for email in [OWNER_EMAIL, *subs]:
        if email and email not in seen:
            seen.append(email)
    return seen


def add_subscriber(product: str, email: str) -> str:
    """Adds email to product with a fresh 30-day window, or renews it
    (resets "added" to now) if already present -- either way returns a
    short human-readable status string for CLI/caller use."""
    if product not in PRODUCTS:
        raise ValueError(f"Unknown product {product!r} -- must be one of {PRODUCTS}")
    email = email.strip().lower()
    data = load_subscribers()
    entries = data.setdefault(product, [])
    now_iso = _now().isoformat()
    for entry in entries:
        if entry.get("email", "").strip().lower() == email:
            entry["added"] = now_iso
            save_subscribers(data)
            return f"renewed {email} on {product} -- 30-day window reset from today"
    entries.append({"email": email, "added": now_iso})
    save_subscribers(data)
    return f"added {email} to {product} -- active for {EXPIRY_DAYS} days"


def remove_subscriber(product: str, email: str) -> str:
    if product not in PRODUCTS:
        raise ValueError(f"Unknown product {product!r} -- must be one of {PRODUCTS}")
    email = email.strip().lower()
    data = load_subscribers()
    entries = data.get(product, [])
    before = len(entries)
    data[product] = [e for e in entries if e.get("email", "").strip().lower() != email]
    if len(data[product]) == before:
        return f"{email} was not on {product}'s list -- nothing removed"
    save_subscribers(data)
    return f"removed {email} from {product}"


def list_subscribers(product: str | None = None) -> dict[str, list[dict]]:
    """Active subscribers (with days_left) for one product, or every
    product if none given."""
    products = [product] if product else list(PRODUCTS)
    return {p: active_subscribers(p) for p in products}


def products_for_email(email: str) -> list[dict]:
    """Reverse lookup: every product this email currently has active
    access to, each with days_left -- so you can add someone, then
    immediately check what they're actually going to receive. Includes
    expired entries too (flagged, not just silently omitted) so a lapsed
    subscriber's history doesn't just disappear from view."""
    email = email.strip().lower()
    now = _now()
    out = []
    for product, entries in load_subscribers().items():
        for entry in entries:
            if entry.get("email", "").strip().lower() != email:
                continue
            added = _parse(entry.get("added", ""))
            if added is None:
                continue
            days_left = EXPIRY_DAYS - (now - added).days
            out.append({
                "product": product,
                "added": entry["added"],
                "days_left": days_left,
                "active": days_left > 0,
            })
    return out
