#!/usr/bin/env python3
"""
backtest_calibration.py — Calibration report: realized win-rate vs
model-implied probability, bucketed by sport / bet type / tier.

This is the "does the model actually work" check the engine has been
missing: bet_history.json records what was picked and at what modeled
probability, and settlement records whether it won — but nothing walks
that history and compares realized outcomes to modeled confidence. A
model that says "67% PREMIUM" should win roughly 67% of the time; if
PREMIUM MLB ML picks are actually hitting 71%, there's calibration slack
worth capturing (tighten the tier threshold, or trust it more). If LEAN
soccer O/U is hitting 48% against a 55%+ threshold, that market's ensemble
weight needs to shrink.

Usage:
  python3 scripts/backtest_calibration.py                 # summary report
  python3 scripts/backtest_calibration.py --json           # machine-readable
  python3 scripts/backtest_calibration.py --min-n 10       # suppress buckets with too few samples to be meaningful

Data source: data/bet_history.json (populated by merge_settled_to_history()
in clairvoyance_update.py, itself fed by auto_settle()). NOTE: as of this
writing that file is empty — the ~82% all-time record shown in the app's
Overall tab is tracked client-side in browser localStorage (the `preds` key),
not synced back to this backend repo. This script is correct and ready to
use the moment real settled records land in data/bet_history.json; until a
localStorage→backend sync exists, it will (correctly) report "no data yet"
rather than fabricate numbers.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
BET_HISTORY = ROOT / "data" / "bet_history.json"


def load_history() -> list[dict]:
    if not BET_HISTORY.exists():
        return []
    try:
        return json.loads(BET_HISTORY.read_text())
    except Exception as exc:
        print(f"ERROR reading {BET_HISTORY}: {exc}", file=sys.stderr)
        return []


def tier_from_grade(rec: dict) -> str:
    """
    Normalizes whatever grade/tier field is present into one of
    PREMIUM/OPTIMAL/LEAN/SKIP/UNKNOWN — the frontend's tier() function
    writes evGrade as a letter (A+/A/B/C/D) in some paths and a tier word
    in others (grade field), so check both rather than assuming one schema.
    """
    g = str(rec.get("grade") or rec.get("evGrade") or "").upper()
    if g in ("PREMIUM", "A+"):
        return "PREMIUM"
    if g in ("OPTIMAL", "A", "GOOD"):
        return "OPTIMAL"
    if g in ("LEAN", "B"):
        return "LEAN"
    if g in ("SKIP", "C", "D"):
        return "SKIP"
    return "UNKNOWN"


def outcome_won(rec: dict) -> bool | None:
    o = str(rec.get("outcome", "")).lower()
    if o in ("win", "won", "w"):
        return True
    if o in ("loss", "lost", "l"):
        return False
    return None  # push / pending / unknown — excluded from win-rate math


def bet_type_bucket(rec: dict) -> str:
    bt = str(rec.get("betType") or "").upper()
    if bt:
        return bt
    pick = str(rec.get("pick", "")).upper()
    if "ML" in pick:
        return "ML"
    if "OVER" in pick or "UNDER" in pick or "O/U" in pick:
        return "OU"
    if any(s in pick for s in ("-1.5", "+1.5", "SPREAD", "RL", "AH")):
        return "SPREAD"
    return "OTHER"


def run(min_n: int = 5) -> dict:
    history = load_history()
    buckets: dict[tuple, dict] = defaultdict(lambda: {"n": 0, "wins": 0, "prob_sum": 0.0, "ev_sum": 0.0})

    for rec in history:
        won = outcome_won(rec)
        if won is None:
            continue
        sport = str(rec.get("sport", "UNKNOWN")).upper()
        tier = tier_from_grade(rec)
        bt = bet_type_bucket(rec)
        prob = rec.get("prob")
        try:
            prob = float(prob) / 100.0 if prob and float(prob) > 1 else float(prob or 0)
        except (TypeError, ValueError):
            prob = 0.0
        key = (sport, bt, tier)
        b = buckets[key]
        b["n"] += 1
        b["wins"] += 1 if won else 0
        b["prob_sum"] += prob
        b["ev_sum"] += float(rec.get("ev", 0) or 0)

    report = []
    for (sport, bt, tier), b in sorted(buckets.items()):
        if b["n"] < min_n:
            continue
        realized = b["wins"] / b["n"]
        modeled = b["prob_sum"] / b["n"]
        gap_pp = (realized - modeled) * 100
        report.append({
            "sport": sport, "betType": bt, "tier": tier, "n": b["n"],
            "realizedWinRate": round(realized * 100, 1),
            "modeledWinRate": round(modeled * 100, 1),
            "calibrationGapPP": round(gap_pp, 1),
            "avgEV": round(b["ev_sum"] / b["n"], 2),
            "verdict": (
                "OVERPERFORMING — model underconfident, consider trusting more"
                if gap_pp >= 5 else
                "UNDERPERFORMING — model overconfident, tighten threshold/shrink weight"
                if gap_pp <= -5 else
                "well-calibrated"
            ),
        })

    return {
        "totalRecords": len(history),
        "settledRecords": sum(b["n"] for b in buckets.values()),
        "bucketsBelowMinN": sum(1 for b in buckets.values() if b["n"] < min_n),
        "minN": min_n,
        "buckets": sorted(report, key=lambda r: r["calibrationGapPP"]),
    }


def print_report(result: dict) -> None:
    print("=" * 78)
    print("CLAIRVOYANCE — Calibration Backtest")
    print("=" * 78)
    print(f"Total bet_history.json records: {result['totalRecords']}")
    print(f"Settled (win/loss) records used: {result['settledRecords']}")
    if result["bucketsBelowMinN"]:
        print(f"({result['bucketsBelowMinN']} buckets suppressed — fewer than {result['minN']} samples)")
    print()
    if not result["buckets"]:
        print("No buckets with enough settled history to report yet.")
        print()
        print("bet_history.json is currently populated by merge_settled_to_history(),")
        print("fed from auto_settle() during scheduled runs. If this stays empty, the")
        print("real settlement record is likely tracked client-side only (browser")
        print("localStorage 'preds' key) and never synced back to this backend — that")
        print("sync is the prerequisite for this report to have real signal.")
        print("=" * 78)
        return
    hdr = f"{'SPORT':<8}{'TYPE':<8}{'TIER':<10}{'N':>5}  {'REALIZED':>9}  {'MODELED':>9}  {'GAP':>7}  {'AVG EV':>8}  VERDICT"
    print(hdr)
    print("-" * len(hdr))
    for r in result["buckets"]:
        print(f"{r['sport']:<8}{r['betType']:<8}{r['tier']:<10}{r['n']:>5}  "
              f"{r['realizedWinRate']:>8.1f}%  {r['modeledWinRate']:>8.1f}%  "
              f"{r['calibrationGapPP']:>+6.1f}p  {r['avgEV']:>+7.2f}%  {r['verdict']}")
    print("=" * 78)
    print("GAP = realized - modeled, in percentage points. |GAP| >= 5pp flagged for action.")
    print("=" * 78)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON instead of the table")
    ap.add_argument("--min-n", type=int, default=5, help="minimum settled bets per bucket to report (default 5)")
    args = ap.parse_args()
    result = run(min_n=args.min_n)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)
