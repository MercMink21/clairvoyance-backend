#!/usr/bin/env python3
"""
suggest_weight_adjustments.py — Reads the calibration backtest and proposes
tier-threshold adjustments per sport/bet-type bucket.

Scope note (read before wiring this into anything automatic): true adaptive
ensemble-weight tuning — nightly reweighting the MC/Bayesian/Elo blend per
sport based on trailing calibration — needs each settled bet's *individual*
sub-model probabilities (ens.mc/ens.bay/ens.elo) persisted at lock time, not
just the final blended `prob` that bet_history.json currently stores. Without
that breakdown there's no way to attribute a calibration gap to "MC was too
aggressive" vs "Elo was too conservative" — only to the bucket as a whole.

So this script does the version of "adaptive tuning" the current data
actually supports: it suggests moving a bucket's TIER THRESHOLD (the
p>=0.67 PREMIUM cutoff, etc.) up or down based on realized-vs-modeled gap,
which is a real, actionable lever today. Getting to true per-sub-model
weight auto-tuning is a follow-up that starts with adding mc/bay/elo to the
lockPick() payload in app.html so future settled bets carry that detail.

Usage:
  python3 scripts/suggest_weight_adjustments.py
  python3 scripts/suggest_weight_adjustments.py --json
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import backtest_calibration as bc

# How many percentage points of calibration gap justify a threshold nudge,
# and how big a nudge (in probability points) to suggest per 5pp of gap.
GAP_ACTION_THRESHOLD_PP = 5.0
NUDGE_PER_5PP = 0.02  # 2 probability points per 5pp of calibration gap


def suggest(min_n: int = 5) -> dict:
    result = bc.run(min_n=min_n)
    suggestions = []
    for b in result["buckets"]:
        gap = b["calibrationGapPP"]
        if abs(gap) < GAP_ACTION_THRESHOLD_PP:
            continue
        nudge = round((gap / 5.0) * NUDGE_PER_5PP, 3)
        direction = "lower" if gap > 0 else "raise"
        suggestions.append({
            "sport": b["sport"], "betType": b["betType"], "tier": b["tier"],
            "n": b["n"], "calibrationGapPP": gap,
            "suggestion": f"{direction} the {b['tier']} threshold by ~{abs(nudge)*100:.1f}pp of probability",
            "rationale": (
                f"Realized {b['realizedWinRate']}% vs modeled {b['modeledWinRate']}% "
                f"over {b['n']} settled bets — {'model is underconfident here, tier is stricter than it needs to be' if gap > 0 else 'model is overconfident here, tier is looser than it should be'}."
            ),
            "suggestedThresholdDeltaProb": -nudge if gap > 0 else -nudge,
        })
    return {
        "generatedFrom": f"{result['settledRecords']} settled records ({result['totalRecords']} total in bet_history.json)",
        "note": (
            "Threshold suggestions only — see module docstring for why full "
            "MC/Bayesian/Elo sub-model auto-tuning isn't possible yet with "
            "the current bet_history.json schema."
        ),
        "suggestions": suggestions,
    }


def print_report(result: dict) -> None:
    print("=" * 78)
    print("CLAIRVOYANCE — Tier Threshold Suggestions")
    print("=" * 78)
    print(result["generatedFrom"])
    print(result["note"])
    print()
    if not result["suggestions"]:
        print("No buckets with |gap| >= {:.0f}pp — nothing to suggest yet.".format(GAP_ACTION_THRESHOLD_PP))
        print("=" * 78)
        return
    for s in result["suggestions"]:
        print(f"[{s['sport']} {s['betType']} {s['tier']}] (n={s['n']})")
        print(f"  {s['suggestion']}")
        print(f"  {s['rationale']}")
        print()
    print("=" * 78)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min-n", type=int, default=5)
    args = ap.parse_args()
    result = suggest(min_n=args.min_n)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)
