#!/usr/bin/env python3
from __future__ import annotations
"""
generate_card.py — Clairvoyance Daily Model Card Generator

Renders a 1080×1080 dark-mode PNG from data.json + social_copy.json.
Output: frontend/card.png + docs/card.png

Usage:
  python3 scripts/generate_card.py
  python3 scripts/generate_card.py --open    # open preview after generation
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"], check=True)
    from PIL import Image, ImageDraw, ImageFont

ROOT      = Path(__file__).parent.parent
FE_DATA   = ROOT / "frontend" / "data.json"
FE_SOCIAL = ROOT / "frontend" / "social_copy.json"
FE_CARD   = ROOT / "frontend" / "card.png"
DC_CARD   = ROOT / "docs"     / "card.png"

# ── palette ───────────────────────────────────────────────────────────────────
BG       = (10, 12, 20)        # deep navy-black
PANEL    = (16, 20, 32)        # slightly lighter panel
ACCENT   = (74, 240, 200)      # teal/cyan — Clairvoyance signature
ACCENT2  = (240, 180, 60)      # gold for record
TEXT     = (230, 230, 230)     # primary text
MUTED    = (130, 140, 160)     # secondary/label text
SEP      = (35, 42, 65)        # separator line color
WIN_CLR  = (74, 240, 140)      # green for wins
LOSS_CLR = (240, 80, 80)       # red for losses

W, H = 1080, 1080

# ── font loader ───────────────────────────────────────────────────────────────
_FONT_CANDIDATES = [
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/SFCompact.ttf",
]

def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        p = Path(path)
        if not p.exists():
            continue
        try:
            # TTC files: index 0 = regular, index 1 often bold
            idx = 1 if (bold and path.endswith(".ttc")) else 0
            return ImageFont.truetype(str(p), size, index=idx)
        except Exception:
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    return ImageFont.load_default()


# ── helpers ───────────────────────────────────────────────────────────────────

def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

def _separator(draw: ImageDraw.ImageDraw, y: int, left: int = 60, right: int = W - 60) -> None:
    draw.line([(left, y), (right, y)], fill=SEP, width=1)

def _pill(draw: ImageDraw.ImageDraw, x: int, y: int, text: str,
          bg: tuple, fg: tuple, font: ImageFont.FreeTypeFont) -> None:
    tw = _text_width(draw, text, font)
    pad = 10
    draw.rounded_rectangle([x, y, x + tw + pad * 2, y + 22], radius=6, fill=bg)
    draw.text((x + pad, y + 1), text, font=font, fill=fg)

def _ordinal(n: int) -> str:
    return {1:"1st", 2:"2nd", 3:"3rd"}.get(n, f"{n}th")


# ── section renderers ─────────────────────────────────────────────────────────

def render_header(draw: ImageDraw.ImageDraw) -> int:
    """Render top header. Returns y after header."""
    font_logo = _load_font(32, bold=True)
    font_date = _load_font(18)

    # Brand mark
    draw.text((60, 42), "◆ CLAIRVOYANCE", font=font_logo, fill=ACCENT)

    # Date right-aligned
    now_et = datetime.now(timezone.utc) - __import__("datetime").timedelta(hours=5)
    date_str = now_et.strftime("%b %d, %Y").upper()
    tw = _text_width(draw, date_str, font_date)
    draw.text((W - 60 - tw, 52), date_str, font=font_date, fill=MUTED)

    # Tagline
    font_tag = _load_font(14)
    draw.text((60, 82), "sports intelligence engine", font=font_tag, fill=MUTED)

    _separator(draw, 114)
    return 130


def render_record(draw: ImageDraw.ImageDraw, y: int, settled: list) -> int:
    """Render win/loss record bar. Returns y after section."""
    font_label = _load_font(13)
    font_val   = _load_font(22, bold=True)

    wins   = sum(1 for s in settled if s.get("result") == "win")
    losses = sum(1 for s in settled if s.get("result") == "loss")
    pushes = sum(1 for s in settled if s.get("result") == "push")
    units  = sum(s.get("units", 0) for s in settled)
    total  = wins + losses + pushes

    draw.text((60, y), "RECORD", font=font_label, fill=MUTED)

    record_str = f"{wins}W-{losses}L" + (f"-{pushes}P" if pushes else "")
    units_str  = f"{units:+.1f}u"
    pct_str    = f"{wins/total*100:.1f}% ATS" if total else "—"

    draw.text((60, y + 18), record_str, font=font_val, fill=WIN_CLR if wins >= losses else LOSS_CLR)

    tw = _text_width(draw, units_str, font_val)
    center_x = W // 2 - tw // 2
    draw.text((center_x, y + 18), units_str, font=font_val,
              fill=WIN_CLR if units >= 0 else LOSS_CLR)

    tw2 = _text_width(draw, pct_str, font_val)
    draw.text((W - 60 - tw2, y + 18), pct_str, font=font_val, fill=ACCENT2)

    _separator(draw, y + 58)
    return y + 74


def render_games(draw: ImageDraw.ImageDraw, y: int, games: list, sport: str, max_games: int = 5) -> int:
    """Render a sport's game list. Returns new y."""
    if not games:
        return y

    font_hdr  = _load_font(12, bold=True)
    font_game = _load_font(15)
    font_live = _load_font(12)

    draw.text((60, y), sport, font=font_hdr, fill=ACCENT)
    y += 22

    for g in games[:max_games]:
        state     = g.get("state", "pre")
        away, home = g.get("away", ""), g.get("home", "")
        matchup   = f"{away} @ {home}"

        # Score / clock
        if state == "post":
            score = f"{g.get('awayScore', 0)}-{g.get('homeScore', 0)} F"
            score_col = MUTED
        elif state == "in":
            score = f"{g.get('awayScore', 0)}-{g.get('homeScore', 0)}"
            score_col = WIN_CLR
        else:
            score = ""
            score_col = MUTED

        draw.text((60, y), matchup, font=font_game, fill=TEXT)

        if score:
            tw = _text_width(draw, score, font_live)
            draw.text((W - 60 - tw, y + 2), score, font=font_live, fill=score_col)

            if state == "in":
                period = g.get("period", "")
                clk    = g.get("displayClock", "")
                lbl    = f"{_ordinal(period) if isinstance(period, int) else period} {clk}".strip()
                tw2    = _text_width(draw, lbl, font_live)
                draw.text((W - 60 - tw2 - tw - 12, y + 2), lbl, font=font_live, fill=ACCENT)

        # Series note
        series = g.get("seriesNote", "")
        if series:
            draw.text((60, y + 18), series, font=font_live, fill=MUTED)
            y += 14

        y += 26

    return y + 4


def render_best_bets(draw: ImageDraw.ImageDraw, y: int, best_bets: list) -> int:
    """Render best bets section. Returns new y."""
    font_hdr  = _load_font(12, bold=True)
    font_game = _load_font(14)
    font_odds = _load_font(13)
    font_sm   = _load_font(11)

    draw.text((60, y), "MODEL EDGES", font=font_hdr, fill=ACCENT)
    y += 22

    if not best_bets:
        draw.text((60, y), "No edges above threshold today", font=font_game, fill=MUTED)
        return y + 30

    for b in best_bets[:4]:
        if not isinstance(b, dict):
            continue
        game = b.get("game", "")
        pick = b.get("pick", "")
        prob = b.get("modelProb", b.get("prob", 0))
        impl = b.get("impliedProb", b.get("implied", 0))
        edge = b.get("edge", round((prob - impl) * 100, 1) if prob and impl else 0)
        conf = b.get("confidence", "")

        draw.text((60, y), f"{game}  •  {pick}", font=font_game, fill=TEXT)

        if prob:
            odds_line = f"Model {prob*100:.1f}% vs Impl {impl*100:.1f}%  |  Edge {edge:+.1f}%"
            edge_col  = WIN_CLR if edge >= 3 else ACCENT2 if edge >= 1 else LOSS_CLR
            draw.text((60, y + 17), odds_line, font=font_sm, fill=edge_col)
            y += 14

        if conf:
            _pill(draw, W - 160, y - 12, conf.upper(), PANEL, ACCENT, font_sm)

        y += 32

    return y + 4


def render_intel_strip(draw: ImageDraw.ImageDraw, y: int, data: dict) -> int:
    """Render a compact strip of analytics intel. Returns new y."""
    font_hdr = _load_font(12, bold=True)
    font_val = _load_font(13)

    _separator(draw, y)
    y += 16

    items = []

    # ATP #1
    atp = data.get("tennis", {}).get("atpElo", [])
    if atp:
        p = atp[0]
        items.append(f"ATP #1  {p.get('name','')}  {p.get('elo','')} ELO")

    # NHL xGF% leader
    mp = data.get("mp", {}).get("teams", {})
    if mp:
        leader = max(mp.items(), key=lambda kv: kv[1].get("5on5", {}).get("xgfPct", 0))
        abbr, stats = leader
        pct = stats.get("5on5", {}).get("xgfPct", 0)
        items.append(f"NHL xGF%  {abbr}  {pct:.3f}")

    # Weather
    weather = data.get("weather", {})
    windy = [(k, v) for k, v in weather.items()
             if not v.get("indoor") and v.get("wind") and v.get("wind", 0) >= 15]
    if windy:
        t, w = windy[0]
        items.append(f"Wind  {t}  {w.get('wind')} mph")

    col_w = (W - 120) // max(len(items), 1)
    for i, item in enumerate(items[:3]):
        parts = item.split("  ", 1)
        label = parts[0]
        value = parts[1] if len(parts) > 1 else ""
        x = 60 + i * col_w
        draw.text((x, y), label, font=font_hdr, fill=MUTED)
        draw.text((x, y + 16), value, font=font_val, fill=TEXT)

    return y + 46


def render_footer(draw: ImageDraw.ImageDraw) -> None:
    font = _load_font(13)
    draw.line([(60, H - 68), (W - 60, H - 68)], fill=SEP, width=1)
    draw.text((60, H - 50), "clairvoyancesports.com", font=font, fill=MUTED)
    handle = "@clairvoyancesports"
    tw = _text_width(draw, handle, font)
    draw.text((W - 60 - tw, H - 50), handle, font=font, fill=ACCENT)

    # Subtle version tag
    font_xs = _load_font(11)
    draw.text((60, H - 28), "Model outputs are probabilistic — not financial advice.",
              font=font_xs, fill=(70, 80, 100))


# ── card composer ─────────────────────────────────────────────────────────────

def generate_card(data: dict, social: dict) -> Image.Image:
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Subtle grid texture (faint horizontal bands)
    for row in range(0, H, 80):
        draw.line([(0, row), (W, row)], fill=(14, 17, 27), width=1)

    # Left accent bar
    draw.rectangle([(0, 0), (4, H)], fill=ACCENT)

    y = render_header(draw)

    settled   = data.get("settled", [])
    best_bets = data.get("bestBets", [])

    # Record only if we have tracked bets
    if settled:
        y = render_record(draw, y, settled)
    else:
        # Show "tracking" state
        font_sm = _load_font(13)
        draw.text((60, y), "RECORD TRACKING ACTIVE — sample accumulating",
                  font=font_sm, fill=MUTED)
        y += 28
        _separator(draw, y)
        y += 16

    # Best bets or model edges
    y = render_best_bets(draw, y, best_bets)
    _separator(draw, y)
    y += 14

    # Sport game slates — fit remaining space
    remaining = H - 160 - y
    per_game  = 28
    budget    = remaining // per_game
    sports_share = budget // 3 or 2

    for sport, key in [("MLB", "mlb"), ("NBA", "nba"), ("NHL", "nhl")]:
        games = data.get(key, {}).get("today", [])
        if games:
            y = render_games(draw, y, games, sport, max_games=sports_share)

    # Intel strip
    y = render_intel_strip(draw, y, data)

    # Social caption snippet from Claude
    if social.get("x_post"):
        font_quote = _load_font(14)
        font_attr  = _load_font(11)
        quote = social["x_post"][:120] + ("…" if len(social["x_post"]) > 120 else "")
        draw.text((60, H - 115), f'"{quote}"', font=font_quote, fill=MUTED)

    render_footer(draw)
    return img


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Clairvoyance Card Generator")
    parser.add_argument("--open", action="store_true", help="Open preview after generation")
    args = parser.parse_args()

    if not FE_DATA.exists():
        print("[ERROR] data.json not found", file=sys.stderr)
        sys.exit(1)

    data   = json.loads(FE_DATA.read_text())
    social = json.loads(FE_SOCIAL.read_text()) if FE_SOCIAL.exists() else {}

    img = generate_card(data, social)
    img.save(str(FE_CARD), format="PNG", optimize=True)
    img.save(str(DC_CARD), format="PNG", optimize=True)

    size_kb = FE_CARD.stat().st_size // 1024
    print(f"[INFO] card.png written ({size_kb} KB) → frontend/ + docs/")

    if args.open:
        subprocess.run(["open", str(FE_CARD)])


if __name__ == "__main__":
    main()
