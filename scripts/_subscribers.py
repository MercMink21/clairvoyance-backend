"""
_subscribers.py — shared subscriber-list loader for segmented per-sport
locks emails.

MVP: manually-edited data/subscribers.json, no payment automation yet.
Venmo is the payment method for now -- when someone pays, add their email
under the sport(s) they bought in that file (a plain {"nfl": ["a@x.com"],
...} map, one list per paid product) and commit it. No webhook, no
database; this is intentionally the simplest thing that works for a
manually-tracked MVP.

The account owner's own address is always included for every product
regardless of subscriber list state, so the personal daily reference
this was originally built for keeps working with zero paying subscribers.

7 paid products (confirmed structure): nfl, cfb, nba, wnba, mlb, hockey
(NHL + KHL/SHL/LIIGA bundled -- those 3 have no real game cards wired up
yet, but the product covers them too so nothing needs to change here
once they are), soccer (all 6 leagues bundled -- the 5 European leagues
+ MLS -- as one purchase, not sold separately).
"""
from __future__ import annotations
import json
import os
from pathlib import Path

SUBSCRIBERS_FILE = Path(__file__).resolve().parent.parent / "data" / "subscribers.json"
PRODUCTS = ("nfl", "cfb", "nba", "wnba", "mlb", "hockey", "soccer")
OWNER_EMAIL = os.environ.get("LOCKS_EMAIL_TO", "") or os.environ.get("SOCIAL_CARD_EMAIL_TO", "")


def load_subscribers() -> dict[str, list[str]]:
    try:
        return json.loads(SUBSCRIBERS_FILE.read_text())
    except Exception:
        return {}


def recipients_for(product: str) -> list[str]:
    """Owner + every paying subscriber for this product, deduped, order
    preserved (owner first)."""
    subs = load_subscribers().get(product, [])
    seen: list[str] = []
    for email in [OWNER_EMAIL, *subs]:
        if email and email not in seen:
            seen.append(email)
    return seen
