#!/usr/bin/env python3
"""
generate_video_reveal.py — short animated "stats reveal" video for IG/X,
built from a local HTML/CSS animation (scripts/video_templates/) recorded
via Playwright and converted to MP4 (X and Instagram both require MP4;
Playwright's native recording is WebM).

Usage (standalone test):
  python3 scripts/generate_video_reveal.py --record "19W-4L" --pct "82.6%" \
      --units "+11.8u" --headline "YESTERDAY'S PERFORMANCE" --out /tmp/reveal.mp4
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "video_templates" / "daily_reveal.html"


def record_and_convert(headline: str, record: str, pct: str, units: str, out_path: Path, duration_s: float = 5.5) -> Path:
    from playwright.sync_api import sync_playwright
    import imageio_ffmpeg

    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()

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
            page.goto(f"file://{TEMPLATE}")
            page.evaluate(
                """
                ({headline, record, pct, units}) => {
                  document.getElementById('headline').textContent = headline;
                  document.getElementById('v-record').textContent = record;
                  document.getElementById('v-pct').textContent = pct;
                  document.getElementById('v-units').textContent = units;
                }
                """,
                {"headline": headline, "record": record, "pct": pct, "units": units},
            )
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--headline", default="YESTERDAY'S PERFORMANCE")
    parser.add_argument("--record", required=True)
    parser.add_argument("--pct", required=True)
    parser.add_argument("--units", required=True)
    parser.add_argument("--out", default="/tmp/cv_reveal.mp4")
    args = parser.parse_args()

    out = record_and_convert(args.headline, args.record, args.pct, args.units, Path(args.out))
    print(f"Saved {out} ({out.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
