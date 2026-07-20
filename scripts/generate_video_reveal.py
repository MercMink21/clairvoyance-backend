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


def record_stats_reveal(headline: str, record: str, pct: str, units: str, out_path: Path, duration_s: float = 5.5) -> Path:
    setup_js = f"""
    () => {{
      document.getElementById('headline').textContent = {json.dumps(headline)};
      document.getElementById('v-record').textContent = {json.dumps(record)};
      document.getElementById('v-pct').textContent = {json.dumps(pct)};
      document.getElementById('v-units').textContent = {json.dumps(units)};
    }}
    """
    return _record_template("daily_reveal.html", setup_js, out_path, duration_s)


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


def record_milestone_reveal(headline: str, body_text: str, out_path: Path, duration_s: float = 5.0) -> Path:
    setup_js = f"""
    () => {{
      document.getElementById('headline').textContent = {json.dumps(headline)};
      document.getElementById('body').textContent = {json.dumps(body_text)};
    }}
    """
    return _record_template("milestone_reveal.html", setup_js, out_path, duration_s)


def record_educational_reveal(tag: str, title: str, lines: list[str], out_path: Path, duration_s: float | None = None) -> Path:
    """lines: list of short (~1 sentence) strings, revealed one at a time."""
    if duration_s is None:
        duration_s = 0.9 + len(lines) * 1.1 + 1.6
    setup_js = f"window.populateLines({json.dumps(tag)}, {json.dumps(title)}, {json.dumps(lines)})"
    return _record_template("educational_reveal.html", setup_js, out_path, duration_s)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="kind", required=True)

    p_stats = sub.add_parser("stats")
    p_stats.add_argument("--headline", default="YESTERDAY'S PERFORMANCE")
    p_stats.add_argument("--record", required=True)
    p_stats.add_argument("--pct", required=True)
    p_stats.add_argument("--units", required=True)
    p_stats.add_argument("--out", default="/tmp/cv_reveal.mp4")

    p_breakdown = sub.add_parser("breakdown")
    p_breakdown.add_argument("--out", default="/tmp/cv_breakdown.mp4")

    p_milestone = sub.add_parser("milestone")
    p_milestone.add_argument("--out", default="/tmp/cv_milestone.mp4")

    p_edu = sub.add_parser("educational")
    p_edu.add_argument("--out", default="/tmp/cv_educational.mp4")

    args = parser.parse_args()

    if args.kind == "stats":
        out = record_stats_reveal(args.headline, args.record, args.pct, args.units, Path(args.out))
    elif args.kind == "breakdown":
        demo_rows = [
            {"label": "BASEBALL", "record": "18W-4L", "pct": "81.8%", "isTotal": False},
            {"label": "BASKETBALL", "record": "12W-3L", "pct": "80.0%", "isTotal": False},
            {"label": "HOCKEY", "record": "9W-2L", "pct": "81.8%", "isTotal": False},
            {"label": "TOTAL", "record": "39W-9L", "pct": "81.3%", "isTotal": True},
        ]
        out = record_breakdown_reveal("SPORT PERFORMANCE", demo_rows, Path(args.out))
    elif args.kind == "milestone":
        out = record_milestone_reveal("10-WIN STREAK", "10 straight wins. The model doesn't flinch either way.", Path(args.out))
    elif args.kind == "educational":
        out = record_educational_reveal(
            "// EDUCATIONAL", "HOW WE GRADE PICKS",
            [
                "Not all picks are created equal.",
                "Every signal gets graded before it goes public.",
                "Some clear the bar. Some don't make the cut at all.",
                "That's the whole point.",
            ],
            Path(args.out),
        )
    print(f"Saved {out} ({out.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
