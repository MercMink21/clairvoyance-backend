#!/usr/bin/env python3
"""
snapshot_cfb_2025.py — one-time manual tool. Builds docs/cfb_team_stats_2025.json,
a PERMANENT snapshot of real 2025 CFB team offense/defense (now including
the own-side scoring field added to _OFFENSE_FIELDS specifically for
this) using the same ESPN pipeline as fetch_cfb.py's regular daily
fetch, just pinned to season=2025 and written to a filename the daily
refresh (fetch_cfb.py itself) never touches.

Exists because cfb_team_stats.json's own season field flips to 2026 the
moment 2026 games start posting real stats (fetch_all_team_stats's
documented, intentional behavior) -- at that point the 2025 numbers this
season needs as a small 15%-weighted historical signal (last season's
roster/results are still informative even though 2026's roster differs,
same rationale as weighting a European soccer league's prior season)
would otherwise be gone with no way to get them back apart from
re-scraping a full season that's already over.

Not part of any scheduled workflow -- run once, commit the output, done.
Re-run only if this exact snapshot ever needs to be regenerated (e.g. a
field extraction bug is found and fixed) -- it will NOT pick up 2026
data no matter when it's run, since season is hardcoded below.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_cfb import build_roster, fetch_all_team_stats  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "docs" / "cfb_team_stats_2025.json"


def main() -> None:
    print("[snapshot] Building full 11-conference roster (this takes a few minutes)…")
    roster = build_roster()
    total = sum(len(v) for v in roster.values())
    print(f"[snapshot] Roster built: {total} teams across {len(roster)} conferences")

    print("[snapshot] Fetching season=2025 team stats for every roster team…")
    stats = fetch_all_team_stats(roster, season=2025)

    out = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "season": 2025,
        "note": "Permanent one-time snapshot -- never overwritten by the daily refresh. See snapshot_cfb_2025.py.",
        "teams": stats,
    }
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"[snapshot] Wrote {len(stats)} teams to {OUT_PATH}")


if __name__ == "__main__":
    main()
