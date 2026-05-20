#!/usr/bin/env python3
"""
generate_pinned_card.py — Clairvoyance Engine Pinned Post Card
1080×1080 square PNG for Instagram + X pinned posts.
Matches the existing card brand: carbon fiber, orbital eye, neon palette.

Usage:
  python3 scripts/generate_pinned_card.py
  # outputs: docs/pinned_card.png + frontend/pinned_card.png
"""

import math, subprocess, sys
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"], check=True)
    from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT    = Path(__file__).parent.parent
OUT_FE  = ROOT / "frontend" / "pinned_card.png"
OUT_DOC = ROOT / "docs"     / "pinned_card.png"

W = H = 1080

# ── Palette ───────────────────────────────────────────────────────────────────
BG       = (10,   8,  20)
PURPLE   = (192,  48, 240)
PURPLE_D = ( 80,  18, 110)
CYAN     = ( 48, 208, 240)
CYAN_D   = ( 20,  80, 110)
TEXT     = (218, 212, 232)
MUTED    = ( 96,  86, 128)
DIM      = ( 54,  46,  80)
SEP      = ( 36,  28,  60)
WHITE    = (255, 255, 255)

X_HANDLE  = "@ClairvoyanceEng"
IG_HANDLE = "@clairvoyanceengine"
DOMAIN    = "clairvoyanceengine.info"
DATE_STR  = datetime.now().strftime("%b %-d, %Y").upper()

# ── Font loader ───────────────────────────────────────────────────────────────
_FONT_PATHS = [
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/SFNSDisplay.ttf",
    "/System/Library/Fonts/SFNS.ttf",
]
_cache: dict = {}

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key not in _cache:
        for path in _FONT_PATHS:
            p = Path(path)
            if not p.exists(): continue
            try:
                idx = 1 if bold and path.endswith(".ttc") else 0
                _cache[key] = ImageFont.truetype(str(p), size, index=idx)
                break
            except Exception:
                try:
                    _cache[key] = ImageFont.truetype(str(p), size)
                    break
                except Exception:
                    continue
        if key not in _cache:
            _cache[key] = ImageFont.load_default()
    return _cache[key]

def _tw(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

def _cx(draw, text, font):
    return (W - _tw(draw, text, font)) // 2

# Tracked (letter-spaced) text helpers
def _tracked_w(draw, text, font, sp):
    return sum(_tw(draw, ch, font) + sp for ch in text) - sp

def _tracked(draw, xy, text, font, fill, sp):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += _tw(draw, ch, font) + sp

def _tracked_cx(draw, text, font, sp):
    return (W - _tracked_w(draw, text, font, sp)) // 2

# ── Carbon fiber background ───────────────────────────────────────────────────
def _draw_bg(img: Image.Image) -> None:
    CW, CH = 8, 16
    TW, TH = CW * 2, CH * 2
    tile = Image.new("RGB", (TW, TH))
    pix  = tile.load()
    for ty in range(TH):
        for tx in range(TW):
            cx = tx // CW; cy = ty // CH
            px = (tx % CW) / (CW - 1) if CW > 1 else 0
            py = (ty % CH) / (CH - 1) if CH > 1 else 0
            t  = py if (cx + cy) % 2 == 0 else px
            r  = int(10 + 18 * t)
            g  = int( 8 + 12 * t)
            b  = int(20 + 30 * t)
            if py < 0.12: r, g, b = r + 5, g + 3, b + 8
            pix[tx, ty] = (min(r, 42), min(g, 30), min(b, 64))
    for y in range(0, H, TH):
        for x in range(0, W, TW):
            img.paste(tile, (x, y))

# ── Corner HUD brackets ───────────────────────────────────────────────────────
def _brackets(draw: ImageDraw.ImageDraw, m=32, s=48, w=2) -> None:
    for bx, by in [(m, m), (W-m, m), (m, H-m), (W-m, H-m)]:
        sx = 1 if bx < W//2 else -1
        sy = 1 if by < H//2 else -1
        draw.line([(bx, by), (bx + sx*s, by)], fill=CYAN_D, width=w)
        draw.line([(bx, by), (bx, by + sy*s)], fill=CYAN_D, width=w)

# ── Orbital eye ───────────────────────────────────────────────────────────────
def _draw_eye(img: Image.Image, cx: int, cy: int, size: int = 94) -> Image.Image:
    draw = ImageDraw.Draw(img)
    ow = int(size * 1.10); oh = int(size * 0.36)

    # Outer cyan orbital
    draw.ellipse([cx-ow//2, cy-oh//2, cx+ow//2, cy+oh//2], outline=CYAN, width=2)

    # HUD ticks
    gap, tick = 7, 16
    draw.line([(cx-ow//2-gap-tick, cy), (cx-ow//2-gap, cy)], fill=CYAN, width=1)
    draw.line([(cx+ow//2+gap, cy), (cx+ow//2+gap+tick, cy)], fill=CYAN, width=1)
    draw.line([(cx, cy-oh//2-gap-8), (cx, cy-oh//2-gap)], fill=CYAN, width=1)
    draw.line([(cx, cy+oh//2+gap), (cx, cy+oh//2+gap+8)], fill=CYAN, width=1)

    # Inner dashed ring
    ir = int(size * 0.42)
    for angle in range(0, 360, 12):
        a0 = math.radians(angle); a1 = math.radians(angle + 7)
        x0 = cx + int(ir * math.cos(a0)); y0 = cy + int(ir * math.sin(a0))
        x1 = cx + int(ir * math.cos(a1)); y1 = cy + int(ir * math.sin(a1))
        draw.line([(x0, y0), (x1, y1)], fill=PURPLE_D, width=1)

    # Purple iris
    draw.ellipse([cx-ir, cy-ir, cx+ir, cy+ir], outline=PURPLE, width=3)

    # Glow bloom
    gr = int(size * 0.20)
    glow = Image.new("RGBA", (W, H), (0,0,0,0))
    gd   = ImageDraw.Draw(glow)
    gd.ellipse([cx-gr, cy-gr, cx+gr, cy+gr], fill=(*PURPLE, 160))
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    img  = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Pupil
    pr = int(size * 0.26)
    draw.ellipse([cx-pr, cy-pr, cx+pr, cy+pr], fill=(14, 8, 28))
    draw.ellipse([cx-gr, cy-gr, cx+gr, cy+gr], fill=PURPLE)

    # Bright core
    dr = int(size * 0.052)
    draw.ellipse([cx-dr, cy-dr, cx+dr, cy+dr], fill=(228, 190, 255))
    return img

# ── Glow text (centered) ──────────────────────────────────────────────────────
def _glow(img: Image.Image, text: str, y: int, font,
          color: tuple, glow_color: tuple, radius: int = 10,
          spacing: int = 0) -> Image.Image:
    tmp = ImageDraw.Draw(img)
    x   = _tracked_cx(tmp, text, font, spacing) if spacing else _cx(tmp, text, font)
    gl  = Image.new("RGBA", (W, H), (0,0,0,0))
    gd  = ImageDraw.Draw(gl)
    if spacing:
        _tracked(gd, (x, y), text, font, (*glow_color, 200), spacing)
    else:
        gd.text((x, y), text, font=font, fill=(*glow_color, 200))
    gl  = gl.filter(ImageFilter.GaussianBlur(radius))
    img = Image.alpha_composite(img.convert("RGBA"), gl).convert("RGB")
    draw = ImageDraw.Draw(img)
    if spacing:
        _tracked(draw, (x, y), text, font, color, spacing)
    else:
        draw.text((x, y), text, font=font, fill=color)
    return img

# ── Separator line ────────────────────────────────────────────────────────────
def _sep(draw: ImageDraw.ImageDraw, y: int, mx: int = 72) -> None:
    draw.line([(mx, y), (W - mx, y)], fill=SEP, width=1)

# ── Bullet row ────────────────────────────────────────────────────────────────
def _bullet(draw: ImageDraw.ImageDraw, y: int, label: str, value: str,
            lf=_font, vf=_font) -> int:
    lbl_font = _font(22, bold=True)
    val_font = _font(22)
    draw.text((80, y), label, font=lbl_font, fill=CYAN)
    draw.text((80, y + 28), value, font=val_font, fill=MUTED)
    return y + 68

# ── Main card generator ───────────────────────────────────────────────────────
def generate() -> Image.Image:
    img  = Image.new("RGB", (W, H), BG)
    _draw_bg(img)
    draw = ImageDraw.Draw(img)

    # Corner brackets
    _brackets(draw)


    # ── Eye logo ─────────────────────────────────────────────────────────────
    img = _draw_eye(img, W // 2, 148, size=90)
    draw = ImageDraw.Draw(img)

    # ── CLAIRVOYANCE title ────────────────────────────────────────────────────
    title_font = _font(88, bold=True)
    img = _glow(img, "CLAIRVOYANCE", 258, title_font,
                color=PURPLE, glow_color=PURPLE, radius=18, spacing=4)
    draw = ImageDraw.Draw(img)

    # Subtitle
    sub_font = _font(24)
    img = _glow(img, "PREDICTIVE SPORTS INTELLIGENCE ENGINE", 362, sub_font,
                color=CYAN, glow_color=CYAN, radius=6, spacing=3)
    draw = ImageDraw.Draw(img)

    # Tagline
    tag_font = _font(18)
    x_tag = _tracked_cx(draw, "SEE WHAT OTHERS CANNOT", tag_font, 3)
    _tracked(draw, (x_tag, 402), "SEE WHAT OTHERS CANNOT", tag_font, DIM, 3)

    # ── Separator ─────────────────────────────────────────────────────────────
    _sep(draw, 442)

    # ── Description block ─────────────────────────────────────────────────────
    desc_font = _font(26)
    desc_lines = [
        "A private sports intelligence system that",
        "models edge across five major sports,",
        "grades every pick, and publishes the signal.",
    ]
    dy = 468
    for line in desc_lines:
        x = _cx(draw, line, desc_font)
        draw.text((x, dy), line, font=desc_font, fill=TEXT)
        dy += 36

    # ── Separator ─────────────────────────────────────────────────────────────
    _sep(draw, dy + 18)
    dy += 46

    # ── Three feature rows ────────────────────────────────────────────────────
    label_font = _font(20, bold=True)
    val_font   = _font(20)

    rows = [
        ("SPORTS COVERED",    "MLB  ·  NBA  ·  NHL  ·  TENNIS  ·  F1"),
        ("EVERY PICK GRADED", "Advanced Analytics  ·  Confidence Scores  ·  Market Edge"),
        ("REAL-TIME ENGINE",  "Cutting Edge Statistical Analysis  ·  Live Calibration"),
    ]

    for label, value in rows:
        # Cyan label
        lx = _tracked_cx(draw, label, label_font, 2)
        _tracked(draw, (lx, dy), label, label_font, CYAN, 2)
        dy += 30
        # Muted value
        vx = _cx(draw, value, val_font)
        draw.text((vx, dy), value, font=val_font, fill=MUTED)
        dy += 48

    # ── Separator ─────────────────────────────────────────────────────────────
    _sep(draw, dy + 4)
    dy += 28

    # ── Follow block ─────────────────────────────────────────────────────────
    follow_font = _font(22, bold=True)
    fol_x = _tracked_cx(draw, "FOLLOW FOR DAILY SIGNALS", follow_font, 2)
    _tracked(draw, (fol_x, dy), "FOLLOW FOR DAILY SIGNALS", follow_font, TEXT, 2)
    dy += 40

    # Handles — X (white) and IG (purple), platform labels in muted
    lbl_font  = _font(17)
    h_font    = _font(26, bold=True)
    gap_mid   = 36

    x_lbl_w  = _tw(draw, "X ", lbl_font)
    x_h_w    = _tw(draw, X_HANDLE, h_font)
    ig_lbl_w = _tw(draw, "IG ", lbl_font)
    ig_h_w   = _tw(draw, IG_HANDLE, h_font)
    total_w  = x_lbl_w + x_h_w + gap_mid + ig_lbl_w + ig_h_w
    sx       = (W - total_w) // 2

    # "X " label
    draw.text((sx, dy + 5), "X ", font=lbl_font, fill=MUTED)
    sx += x_lbl_w
    # X handle white
    draw.text((sx, dy), X_HANDLE, font=h_font, fill=WHITE)
    sx += x_h_w + gap_mid
    # "IG " label
    draw.text((sx, dy + 5), "IG ", font=lbl_font, fill=MUTED)
    sx += ig_lbl_w
    # IG handle purple glow
    gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gl)
    gd.text((sx, dy), IG_HANDLE, font=h_font, fill=(*PURPLE, 210))
    gl  = gl.filter(ImageFilter.GaussianBlur(8))
    img = Image.alpha_composite(img.convert("RGBA"), gl).convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.text((sx, dy), IG_HANDLE, font=h_font, fill=PURPLE)

    dy += 46

    # Domain
    dom_font = _font(20)
    dx = _cx(draw, DOMAIN, dom_font)
    draw.text((dx, dy), DOMAIN, font=dom_font, fill=CYAN_D)

    # ── Footer bar ────────────────────────────────────────────────────────────
    draw.rectangle([(0, H - 60), (W, H)], fill=(6, 4, 14))
    foot_font = _font(18, bold=True)
    draw.text((72, H - 38), "CLAIRVOYANCE ENGINE", font=foot_font, fill=MUTED)
    disc_font = _font(16)
    disc = "Model outputs are probabilistic projections, not financial advice."
    draw.text((_cx(draw, disc, disc_font), H - 22), disc, font=disc_font, fill=DIM)

    return img


if __name__ == "__main__":
    print("Generating pinned post card…")
    img = generate()
    for path in (OUT_FE, OUT_DOC):
        img.save(str(path), format="PNG", optimize=True)
        print(f"  Saved → {path}")
    print("Done.")
