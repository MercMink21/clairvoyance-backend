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
EVENTS_FILE = Path(__file__).resolve().parent.parent / "data" / "subscriber_events.json"
PRODUCTS = ("nfl", "cfb", "nba", "wnba", "mlb", "hockey", "soccer", "tennis")
OWNER_EMAIL = os.environ.get("LOCKS_EMAIL_TO", "") or os.environ.get("SOCIAL_CARD_EMAIL_TO", "")
EXPIRY_DAYS = 30

# 30-day access price by number of simultaneous products, per the pricing
# table worked out for this MVP. Used only to ESTIMATE current recurring
# revenue from active subscription counts -- this is not a real payment
# ledger (Venmo payments aren't tracked here at all), just what someone
# following the standard pricing would owe for their current product count.
PRICING_BY_COUNT = {1: 20, 2: 30, 3: 40, 4: 45, 5: 55, 6: 60, 7: 70, 8: 75}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _load_events() -> list[dict]:
    try:
        return json.loads(EVENTS_FILE.read_text())
    except Exception:
        return []


def _log_event(action: str, product: str, email: str) -> None:
    """Append-only history of add/renew/remove actions, the only source
    of real trend/churn data -- current-state files alone (subscribers.json)
    can't answer "how many joined this week" or "who lapsed", since a
    removal or expiry just deletes/filters an entry with no trace. Analytics
    that need history only see it from the point this logging started
    (event_history_since in analytics_summary()), not retroactively."""
    events = _load_events()
    events.append({"ts": _now().isoformat(), "action": action, "product": product, "email": email})
    EVENTS_FILE.write_text(json.dumps(events, indent=2) + "\n")


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
            _log_event("renew", product, email)
            return f"renewed {email} on {product} -- 30-day window reset from today"
    entries.append({"email": email, "added": now_iso})
    save_subscribers(data)
    _log_event("add", product, email)
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
    _log_event("remove", product, email)
    return f"removed {email} from {product}"


def list_subscribers(product: str | None = None) -> dict[str, list[dict]]:
    """Active subscribers (with days_left) for one product, or every
    product if none given."""
    products = [product] if product else list(PRODUCTS)
    return {p: active_subscribers(p) for p in products}


def analytics_summary() -> dict:
    """Everything the admin page's Analytics card shows, computed fresh
    from current subscriber state + the event log. Two different kinds
    of number here, kept clearly separate:
      - state-derived (active counts, per-product breakdown, estimated
        revenue, expiring-soon): always accurate, no history needed.
      - event-derived (signups/renewals/removes in a window, renewal
        rate): only reflects activity SINCE event logging started
        (events_since) -- there's no way to retroactively know about
        adds/removes that happened before this file existed.
    "estimated_mrr" is exactly that -- an estimate from applying
    PRICING_BY_COUNT to current active product counts per email, not a
    real payment ledger (no actual Venmo amounts are tracked anywhere)."""
    now = _now()
    all_data = load_subscribers()

    per_product_counts: dict[str, int] = {}
    active_counts_by_email: dict[str, int] = {}
    for product in PRODUCTS:
        actives = active_subscribers(product)
        per_product_counts[product] = len(actives)
        for entry in actives:
            active_counts_by_email[entry["email"]] = active_counts_by_email.get(entry["email"], 0) + 1

    estimated_mrr = sum(PRICING_BY_COUNT.get(min(n, 8), 0) for n in active_counts_by_email.values())

    expiring_soon = []
    for product in PRODUCTS:
        for entry in active_subscribers(product):
            if entry["days_left"] <= 5:
                expiring_soon.append({"product": product, "email": entry["email"], "days_left": entry["days_left"]})
    expiring_soon.sort(key=lambda r: r["days_left"])

    events = _load_events()
    events_since = events[0]["ts"] if events else None

    def _events_in(days: int) -> list[dict]:
        cutoff = now - timedelta(days=days)
        out = []
        for e in events:
            ts = _parse(e.get("ts", ""))
            if ts is not None and ts >= cutoff:
                out.append(e)
        return out

    def _window_counts(days: int) -> dict[str, int]:
        counts = {"add": 0, "renew": 0, "remove": 0}
        for e in _events_in(days):
            if e.get("action") in counts:
                counts[e["action"]] += 1
        return counts

    win7, win30 = _window_counts(7), _window_counts(30)
    renew_denom_30 = win30["renew"] + win30["remove"]
    renewal_rate_30d = round(100 * win30["renew"] / renew_denom_30) if renew_denom_30 else None

    recent_signups = [e for e in reversed(events) if e.get("action") == "add"][:8]

    return {
        "active_emails": len(active_counts_by_email),
        "active_subscriptions": sum(per_product_counts.values()),
        "per_product_counts": per_product_counts,
        "estimated_mrr": estimated_mrr,
        "expiring_soon": expiring_soon,
        "events_since": events_since,
        "window_7d": win7,
        "window_30d": win30,
        "renewal_rate_30d": renewal_rate_30d,
        "recent_signups": recent_signups,
    }


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
