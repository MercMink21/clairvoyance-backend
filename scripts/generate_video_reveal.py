#!/usr/bin/env python3
"""
generate_video_reveal.py — short animated videos for IG/X, built from
local HTML/CSS animations (scripts/video_templates/) recorded via
Playwright and converted to MP4 (X and Instagram both require MP4;
Playwright's native recording is WebM).

Four video types, one function each, all sharing the same recording/
conversion core (_record_template):
  - record_stats_reveal()      daily_reveal.html      — single stat block
                                (used for daily/weekly/monthly/event posts,
                                just with different headline/stats passed in)
  - record_breakdown_reveal()  breakdown_reveal.html   — animated row list
                                (Sport Performance / League Performance style)
  - record_milestone_reveal()  milestone_reveal.html   — big single-number
                                celebratory reveal
  - record_educational_reveal() educational_reveal.html — paragraph-style
                                informative content, no live stats

Usage (standalone test):
  python3 scripts/generate_video_reveal.py stats --record "19W-4L" --pct "82.6%" \
      --units "+11.8u" --headline "YESTERDAY'S PERFORMANCE" --out /tmp/reveal.mp4
  python3 scripts/generate_video_reveal.py breakdown --out /tmp/breakdown.mp4
  python3 scripts/generate_video_reveal.py milestone --out /tmp/milestone.mp4
  python3 scripts/generate_video_reveal.py educational --out /tmp/edu.mp4
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "video_templates"


def _record_template(template_name: str, setup_js: str, out_path: Path, duration_s: float) -> Path:
    """Loads a template, runs setup_js to populate it (a JS expression
    string evaluated in-page — each template exposes its own populate
    function or plain element IDs), waits for the animation to play out,
    and converts the resulting WebM to MP4."""
    from playwright.sync_api import sync_playwright
    import imageio_ffmpeg

    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    template = TEMPLATES / template_name

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(
                viewport={"width": 1080, "height": 1350},
                record_video_dir=str(tmp_dir),
                record_video_size={"width": 1080, "height": 1350},
            )
            page = context.new_page()
            page.goto(f"file://{template}")
            page.evaluate(setup_js)
            page.wait_for_timeout(int(duration_s * 1000))
            video_path_obj = page.video
            context.close()
            browser.close()
            webm_path = Path(video_path_obj.path())

        out_path.parent.mkdir(parents=True, exist_ok=True)
        # -y overwrite, -movflags +faststart for web/social playback,
        # yuv420p for broad player compatibility (IG/X both reject some
        # webm-default pixel formats when transcoding on ingest).
        subprocess.run(
            [ffmpeg_bin, "-y", "-i", str(webm_path), "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(out_path)],
            check=True, capture_output=True,
        )
    return out_path


# Daily-stats-shaped templates (headline/v-record/v-pct/v-units element
# IDs, same setup_js works for all of them) — different visual pacing so
# consecutive daily posts don't all look identical. Keyed by name so
# callers/rotation logic can pick by index without knowing filenames.
STATS_VARIANTS = {
    "fade":     ("daily_reveal.html", 5.5),      # original: staggered fade-up
    "scanline": ("scanline_reveal.html", 4.8),   # HUD scan-bar sweep, blur-to-sharp
    "glitch":   ("glitch_reveal.html", 4.2),     # RGB-split glitch settle, terminal feel
    "split":    ("split_reveal.html", 4.0),      # fast alternating slide-in, punchier
}
STATS_VARIANT_NAMES = list(STATS_VARIANTS.keys())


def record_stats_reveal(headline: str, record: str, pct: str, units: str, out_path: Path,
                         variant: str = "fade", duration_s: float | None = None) -> Path:
    template_name, default_duration = STATS_VARIANTS[variant]
    setup_js = f"""
    () => {{
      document.getElementById('headline').textContent = {json.dumps(headline)};
      document.getElementById('v-record').textContent = {json.dumps(record)};
      document.getElementById('v-pct').textContent = {json.dumps(pct)};
      document.getElementById('v-units').textContent = {json.dumps(units)};
    }}
    """
    return _record_template(template_name, setup_js, out_path, duration_s or default_duration)


# Kept for backwards compat with the existing call site in generate_social_cards.py
record_and_convert = record_stats_reveal


def record_breakdown_reveal(headline: str, rows: list[dict], out_path: Path, duration_s: float | None = None) -> Path:
    """rows: [{"label": "BASEBALL", "record": "18W-4L", "pct": "81.8%", "isTotal": False}, ...]
    last row should typically have isTotal=True. Duration auto-scales with
    row count if not given (each row adds ~0.28s to the reveal)."""
    if duration_s is None:
        duration_s = 1.5 + len(rows) * 0.28 + 1.0
    setup_js = f"window.populateRows({json.dumps(headline)}, {json.dumps(rows)})"
    return _record_template("breakdown_reveal.html", setup_js, out_path, duration_s)


def record_big_recap_reveal(tag: str, date_range: str, record: str, pct: str, units: str,
                             extra_val: str, extra_lbl: str, out_path: Path, duration_s: float = 7.0) -> Path:
    """Dedicated weekly/monthly style — bigger reveal, 4-stat grid instead
    of 3 (extra_val/extra_lbl is a 4th callout, e.g. "7 DAYS"/"TRACKED" for
    weekly or "31 DAYS"/"TRACKED" for monthly), slower cinematic pacing."""
    setup_js = f"""
    () => {{
      document.getElementById('tag').textContent = {json.dumps(tag)};
      document.getElementById('range').textContent = {json.dumps(date_range)};
      document.getElementById('v-record').textContent = {json.dumps(record)};
      document.getElementById('v-pct').textContent = {json.dumps(pct)};
      document.getElementById('v-units').textContent = {json.dumps(units)};
      document.getElementById('v-extra').textContent = {json.dumps(extra_val)};
      document.getElementById('v-extra-lbl').textContent = {json.dumps(extra_lbl)};
    }}
    """
    return _record_template("big_recap_reveal.html", setup_js, out_path, duration_s)


# Two milestone styles to rotate between so back-to-back milestones (e.g.
# a streak followed later by a count threshold) don't look identical.
MILESTONE_VARIANTS = {
    "flash": ("milestone_reveal.html", 5.0),        # white flash + pop-in headline
    "pulse": ("milestone_pulse_reveal.html", 5.0),  # concentric expanding rings
}


def record_milestone_reveal(headline: str, body_text: str, out_path: Path,
                             variant: str = "flash", duration_s: float | None = None) -> Path:
    template_name, default_duration = MILESTONE_VARIANTS[variant]
    setup_js = f"""
    () => {{
      document.getElementById('headline').textContent = {json.dumps(headline)};
      document.getElementById('body').textContent = {json.dumps(body_text)};
    }}
    """
    return _record_template(template_name, setup_js, out_path, duration_s or default_duration)


# Content sourced from clairvoyanceengine.info's public "How The Engine
# Works" / "From Data To Decision" / "What The Engine Covers" sections,
# rewritten shorter and deliberately vaguer for social — no exact win-
# prob/EV thresholds or formulas (those stay on the site itself), just
# the structural "what happens" story.
EDUCATIONAL_TOPICS = {
    "how-it-works": {
        "tag": "// HOW THE ENGINE WORKS",
        "title": "SIX STAGES. ONE SIGNAL.",
        "lines": [
            "Raw data comes in — form, conditions, lineups, market moves.",
            "Every matchup gets modeled, not guessed.",
            "Thousands of simulations run before a single pick is graded.",
            "The model's number gets checked against the market's number.",
            "Only real edge makes it out the other side.",
        ],
    },
    "data-to-decision": {
        "tag": "// FROM DATA TO DECISION",
        "title": "INGEST → MODEL → GRADE → DELIVER",
        "lines": [
            "Odds, scores, form, and weather — ingested daily.",
            "Normalized, weighted, and run through the model.",
            "Compared against what the market is actually pricing.",
            "Graded. Delivered. Tracked publicly, win or lose.",
        ],
    },
    "what-it-covers": {
        "tag": "// WHAT THE ENGINE COVERS",
        "title": "20 LEAGUES. 6 SPORTS.",
        "lines": [
            "Baseball, basketball, football, hockey, soccer, tennis.",
            "MLB · NBA · WNBA · NFL · NHL · World Cup · ATP · WTA — and more.",
            "One calibrated model per sport, not a one-size-fits-all number.",
        ],
    },
}


def record_educational_reveal(tag: str, title: str, lines: list[str], out_path: Path, duration_s: float | None = None) -> Path:
    """lines: list of short (~1 sentence) strings, revealed one at a time."""
    if duration_s is None:
        duration_s = 0.9 + len(lines) * 1.1 + 1.6
    setup_js = f"window.populateLines({json.dumps(tag)}, {json.dumps(title)}, {json.dumps(lines)})"
    return _record_template("educational_reveal.html", setup_js, out_path, duration_s)


def record_grading_tiers_reveal(out_path: Path, duration_s: float = 6.5) -> Path:
    """Dedicated Pick Grading System video - static content (no live
    stats), matches the site's public PREMIUM/OPTIMAL/LEAN/SKIP tiers but
    deliberately omits the exact win-prob/EV thresholds the site itself
    shows - qualitative descriptions only, no numbers to keep social copy
    vague about methodology."""
    return _record_template("grading_tiers_reveal.html", "() => {}", out_path, duration_s)


def record_subscription_tiers_reveal(out_path: Path, duration_s: float = 6.0) -> Path:
    """Dedicated 'Choose Your Tier' subscription video - static content,
    real public pricing (not methodology, so no vagueness needed here)."""
    return _record_template("subscription_tiers_reveal.html", "() => {}", out_path, duration_s)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="kind", required=True)

    p_stats = sub.add_parser("stats")
    p_stats.add_argument("--headline", default="YESTERDAY'S PERFORMANCE")
    p_stats.add_argument("--record", required=True)
    p_stats.add_argument("--pct", required=True)
    p_stats.add_argument("--units", required=True)
    p_stats.add_argument("--variant", choices=STATS_VARIANT_NAMES, default="fade")
    p_stats.add_argument("--out", default="/tmp/cv_reveal.mp4")

    p_breakdown = sub.add_parser("breakdown")
    p_breakdown.add_argument("--out", default="/tmp/cv_breakdown.mp4")

    p_milestone = sub.add_parser("milestone")
    p_milestone.add_argument("--variant", choices=list(MILESTONE_VARIANTS.keys()), default="flash")
    p_milestone.add_argument("--out", default="/tmp/cv_milestone.mp4")

    p_recap = sub.add_parser("recap")
    p_recap.add_argument("--out", default="/tmp/cv_recap.mp4")

    p_edu = sub.add_parser("educational")
    p_edu.add_argument("--topic", choices=list(EDUCATIONAL_TOPICS.keys()), default="how-it-works")
    p_edu.add_argument("--out", default="/tmp/cv_educational.mp4")

    p_grading = sub.add_parser("grading")
    p_grading.add_argument("--out", default="/tmp/cv_grading.mp4")

    p_sub = sub.add_parser("subscription")
    p_sub.add_argument("--out", default="/tmp/cv_subscription.mp4")

    args = parser.parse_args()

    if args.kind == "stats":
        out = record_stats_reveal(args.headline, args.record, args.pct, args.units, Path(args.out), variant=args.variant)
    elif args.kind == "recap":
        out = record_big_recap_reveal("WEEKLY RECAP", "JULY 12 – 18, 2026", "50W-13L", "79.4%", "+31.4u", "7 DAYS", "TRACKED", Path(args.out))
    elif args.kind == "breakdown":
        demo_rows = [
            {"label": "BASEBALL", "record": "18W-4L", "pct": "81.8%", "isTotal": False},
            {"label": "BASKETBALL", "record": "12W-3L", "pct": "80.0%", "isTotal": False},
            {"label": "HOCKEY", "record": "9W-2L", "pct": "81.8%", "isTotal": False},
            {"label": "TOTAL", "record": "39W-9L", "pct": "81.3%", "isTotal": True},
        ]
        out = record_breakdown_reveal("SPORT PERFORMANCE", demo_rows, Path(args.out))
    elif args.kind == "milestone":
        out = record_milestone_reveal("10-WIN STREAK", "10 straight wins. The model doesn't flinch either way.", Path(args.out), variant=args.variant)
    elif args.kind == "educational":
        topic = EDUCATIONAL_TOPICS[args.topic]
        out = record_educational_reveal(topic["tag"], topic["title"], topic["lines"], Path(args.out))
    elif args.kind == "grading":
        out = record_grading_tiers_reveal(Path(args.out))
    elif args.kind == "subscription":
        out = record_subscription_tiers_reveal(Path(args.out))
    print(f"Saved {out} ({out.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
