#!/usr/bin/env python3
"""
generate_social_assets.py — Clairvoyance Social Media Asset Generator

Generates 12 images across 4 platforms × 3 variants each:
  ig_profile_A/B/C.png    1080×1080   Instagram profile picture
  x_header_A/B/C.png      1500×500    X (Twitter) banner header
  x_profile_A/B/C.png     400×400     X profile photo
  discord_A/B/C.png       512×512     Discord avatar

Variant themes:
  A — Dark charcoal carbon · icon only (eye) · clean, minimal
  B — Dark charcoal carbon · eye + CLAIRVOYANCE wordmark
  C — Deep purple carbon  · eye + CLAIRVOYANCE + "Advanced Sports Intelligence Engine"

Usage:
  python3 scripts/generate_social_assets.py
"""

import math, subprocess, sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"], check=True)
    from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT    = Path(__file__).parent.parent
OUT_FE  = ROOT / "frontend" / "social"
OUT_DOC = ROOT / "docs"    / "social"
for d in (OUT_FE, OUT_DOC):
    d.mkdir(parents=True, exist_ok=True)

# ── Palette ─────────────────────────────────────────────────────────────────────
DARK = dict(
    BG=(14,14,14), PURPLE=(192,48,240), PURPLE_D=(80,18,110),
    CYAN=(48,208,240), CYAN_D=(20,80,110),
    TEXT=(218,212,232), MUTED=(96,86,128), DIM=(44,36,64),
    light=False, purple_fiber=False,
)
PURP = dict(
    BG=(10,8,20), PURPLE=(192,48,240), PURPLE_D=(80,18,110),
    CYAN=(48,208,240), CYAN_D=(20,80,110),
    TEXT=(218,212,232), MUTED=(96,86,128), DIM=(44,36,64),
    light=False, purple_fiber=True,
)

# ── Font loader ──────────────────────────────────────────────────────────────────
_FONT_PATHS = [
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/SFNSDisplay.ttf",
    "/System/Library/Fonts/SFNS.ttf",
]
_fcache: dict = {}

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key not in _fcache:
        for path in _FONT_PATHS:
            p = Path(path)
            if not p.exists(): continue
            try:
                idx = 1 if bold and path.endswith(".ttc") else 0
                _fcache[key] = ImageFont.truetype(str(p), size, index=idx); break
            except Exception:
                try: _fcache[key] = ImageFont.truetype(str(p), size); break
                except Exception: continue
        if key not in _fcache:
            _fcache[key] = ImageFont.load_default()
    return _fcache[key]

# ── Text helpers ─────────────────────────────────────────────────────────────────
def _tw(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

def _th(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]

def _tracked_w(draw, text, font, sp):
    return sum(_tw(draw, ch, font) + sp for ch in text) - sp

def _tracked(draw, xy, text, font, fill, sp):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += _tw(draw, ch, font) + sp

def _tracked_cx(iw, draw, text, font, sp):
    return (iw - _tracked_w(draw, text, font, sp)) // 2

def _cx(iw, draw, text, font):
    return (iw - _tw(draw, text, font)) // 2

# ── Carbon fiber background (canvas-size-aware) ──────────────────────────────────
def _draw_bg(img: Image.Image, t: dict) -> None:
    W, H = img.size
    CW, CH = 8, 16
    TW, TH = CW * 2, CH * 2
    tile = Image.new("RGB", (TW, TH))
    pix  = tile.load()
    for ty in range(TH):
        for tx in range(TW):
            cx = tx // CW; cy = ty // CH
            px = (tx % CW) / (CW - 1) if CW > 1 else 0
            py = (ty % CH) / (CH - 1) if CH > 1 else 0
            fib = py if (cx + cy) % 2 == 0 else px
            if t["purple_fiber"]:
                r = int(10 + 18 * fib); g = int(8 + 12 * fib); b = int(20 + 30 * fib)
                if py < 0.12: r, g, b = r + 5, g + 3, b + 8
                pix[tx, ty] = (min(r, 42), min(g, 30), min(b, 64))
            else:
                v = int(18 + 30 * fib)
                if py < 0.12: v = min(v + 10, 58)
                pix[tx, ty] = (min(v, 58), min(v, 58), min(v + 1, 60))
    for y in range(0, H, TH):
        for x in range(0, W, TW):
            img.paste(tile, (x, y))

# ── Glow text ────────────────────────────────────────────────────────────────────
def _glow_text(img, xy, text, font, color, glow_color, radius=14, sp=0):
    x, y = xy
    gl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(gl)
    if sp:
        _tracked(gd, (x, y), text, font, (*glow_color, 190), sp)
    else:
        gd.text((x, y), text, font=font, fill=(*glow_color, 190))
    gl  = gl.filter(ImageFilter.GaussianBlur(radius))
    img = Image.alpha_composite(img.convert("RGBA"), gl).convert("RGB")
    draw = ImageDraw.Draw(img)
    if sp:
        _tracked(draw, (x, y), text, font, color, sp)
    else:
        draw.text((x, y), text, font=font, fill=color)
    return img

# ── Orbital eye (canvas-size-aware) ──────────────────────────────────────────────
def _draw_eye(img: Image.Image, ecx: int, ecy: int, t: dict, size: int) -> Image.Image:
    IW, IH = img.size
    draw = ImageDraw.Draw(img)

    # Outer orbital ellipse
    ow = int(size * 1.12); oh = int(size * 0.37)
    stroke_w = max(2, size // 55)
    draw.ellipse([ecx - ow//2, ecy - oh//2, ecx + ow//2, ecy + oh//2],
                 outline=t["CYAN"], width=stroke_w)

    # HUD tick marks — L / R / T / B
    gap   = size // 13
    t_lr  = size // 8
    t_tb  = size // 11
    lw    = max(1, size // 90)
    draw.line([(ecx - ow//2 - gap - t_lr, ecy), (ecx - ow//2 - gap, ecy)], fill=t["CYAN"], width=lw)
    draw.line([(ecx + ow//2 + gap, ecy),  (ecx + ow//2 + gap + t_lr, ecy)], fill=t["CYAN"], width=lw)
    draw.line([(ecx, ecy - oh//2 - gap - t_tb), (ecx, ecy - oh//2 - gap)], fill=t["CYAN"], width=lw)
    draw.line([(ecx, ecy + oh//2 + gap),  (ecx, ecy + oh//2 + gap + t_tb)], fill=t["CYAN"], width=lw)

    # Inner dashed ring (drawn as arc segments around the iris radius)
    ir_dash = int(size * 0.44)
    seg_on  = 8; seg_gap = 14
    for angle in range(0, 360, seg_on + seg_gap):
        a0 = math.radians(angle); a1 = math.radians(angle + seg_on)
        x0 = ecx + int(ir_dash * math.cos(a0)); y0 = ecy + int(ir_dash * math.sin(a0))
        x1 = ecx + int(ir_dash * math.cos(a1)); y1 = ecy + int(ir_dash * math.sin(a1))
        draw.line([(x0, y0), (x1, y1)], fill=t["MUTED"], width=lw)

    # Main iris ring
    ir = int(size * 0.36)
    draw.ellipse([ecx - ir, ecy - ir, ecx + ir, ecy + ir],
                 outline=t["PURPLE"], width=max(2, size // 38))

    # Pupil glow (alpha composite onto full canvas)
    gr = int(size * 0.22)
    glow = Image.new("RGBA", (IW, IH), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow)
    gd.ellipse([ecx - gr, ecy - gr, ecx + gr, ecy + gr], fill=(*t["PURPLE"], 150))
    glow = glow.filter(ImageFilter.GaussianBlur(max(6, size // 16)))
    img  = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Dark pupil fill
    pr = int(size * 0.28)
    bg = (8, 4, 20) if not t["light"] else (230, 225, 245)
    draw.ellipse([ecx - pr, ecy - pr, ecx + pr, ecy + pr], fill=bg)

    # Purple centre fill
    draw.ellipse([ecx - gr, ecy - gr, ecx + gr, ecy + gr], fill=t["PURPLE"])

    # Bright core highlight
    dr = int(size * 0.055)
    draw.ellipse([ecx - dr, ecy - dr, ecx + dr, ecy + dr], fill=(228, 190, 255))

    return img

# ── HUD corner brackets ──────────────────────────────────────────────────────────
def _brackets(draw, iw, ih, t, m=32, s=44, w=2):
    for bx, by in [(m, m), (iw - m, m)]:
        sx = 1 if bx < iw // 2 else -1
        draw.line([(bx, by), (bx + sx * s, by)], fill=t["CYAN_D"], width=w)
        draw.line([(bx, by), (bx, by + s)],      fill=t["CYAN_D"], width=w)

# ── Separator line ────────────────────────────────────────────────────────────────
def _sep(draw, iw, y, t, mx=60):
    draw.line([(mx, y), (iw - mx, y)], fill=t["DIM"], width=1)


# ═══════════════════════════════════════════════════════════════════════════════════
# PROFILE PICTURE  (square, displayed as circle — IG / X profile / Discord)
# ═══════════════════════════════════════════════════════════════════════════════════

def make_profile(theme: dict, variant: str, W: int, H: int) -> Image.Image:
    img  = Image.new("RGB", (W, H), theme["BG"])
    _draw_bg(img, theme)
    draw = ImageDraw.Draw(img)
    t    = theme

    if variant == "A":
        # ── Icon only: large eye, fills the circle crop ──────────────────────
        eye_sz = int(min(W, H) * 0.54)
        img    = _draw_eye(img, W // 2, H // 2, t, eye_sz)
        draw   = ImageDraw.Draw(img)

        # Subtle HUD brackets at corners
        m = max(18, W // 28)
        s = max(24, W // 22)
        _brackets(draw, W, H, t, m=m, s=s, w=max(1, W // 300))

    elif variant == "B":
        # ── Eye + CLAIRVOYANCE wordmark ───────────────────────────────────────
        eye_sz = int(min(W, H) * 0.40)
        ey     = int(H * 0.36)
        img    = _draw_eye(img, W // 2, ey, t, eye_sz)
        draw   = ImageDraw.Draw(img)

        # Separator
        sep_y = int(H * 0.605)
        _sep(draw, W, sep_y, t, mx=int(W * 0.12))

        # CLAIRVOYANCE
        tf  = _font(int(W * 0.082), bold=True)
        ty  = int(H * 0.635)
        sp  = max(1, int(W * 0.004))
        tx  = _tracked_cx(W, draw, "CLAIRVOYANCE", tf, sp)
        img = _glow_text(img, (tx, ty), "CLAIRVOYANCE", tf,
                         color=t["PURPLE"], glow_color=t["PURPLE"],
                         radius=max(8, int(W * 0.014)), sp=sp)
        draw = ImageDraw.Draw(img)

        # Domain — tight under CLAIRVOYANCE, bright cyan matching logo
        df  = _font(int(W * 0.026))
        dy  = int(H * 0.635) + int(W * 0.082) + int(H * 0.022)
        dx  = _cx(W, draw, "clairvoyanceengine.info", df)
        draw.text((dx, dy), "clairvoyanceengine.info", font=df, fill=(0, 210, 245))

    elif variant == "C":
        # ── Eye + wordmark + subtitle (full brand lockup) ─────────────────────
        # Zoomed-out: eye ~20% smaller, fonts reduced, more breathing room
        eye_sz = int(min(W, H) * 0.28)        # was 0.36
        ey     = int(H * 0.29)                 # was 0.32 — slightly higher to balance
        img    = _draw_eye(img, W // 2, ey, t, eye_sz)
        draw   = ImageDraw.Draw(img)

        # HUD brackets
        m = max(18, W // 28); s = max(24, W // 22)
        _brackets(draw, W, H, t, m=m, s=s, w=max(1, W // 300))

        # Separator
        sep_y = int(H * 0.535)                 # was 0.575 — tighter to smaller eye
        _sep(draw, W, sep_y, t, mx=int(W * 0.14))

        # CLAIRVOYANCE
        tf  = _font(int(W * 0.060), bold=True) # was 0.074
        ty  = int(H * 0.555)                   # was 0.60
        sp  = max(1, int(W * 0.004))
        tx  = _tracked_cx(W, draw, "CLAIRVOYANCE", tf, sp)
        img = _glow_text(img, (tx, ty), "CLAIRVOYANCE", tf,
                         color=t["PURPLE"], glow_color=t["PURPLE"],
                         radius=max(8, int(W * 0.012)), sp=sp)
        draw = ImageDraw.Draw(img)

        # Subtitle
        sub    = "ADVANCED SPORTS INTELLIGENCE ENGINE"
        sf     = _font(int(W * 0.020))         # was 0.024
        sp_sub = max(1, int(W * 0.002))
        sx     = _tracked_cx(W, draw, sub, sf, sp_sub)
        sy     = int(H * 0.695)                # was 0.74
        _tracked(draw, (sx, sy), sub, sf, t["CYAN"], sp_sub)

        # Separator between subtitle and tagline
        _sep(draw, W, int(H * 0.775), t, mx=int(W * 0.22))

        # Tagline
        tg  = _font(int(W * 0.017))            # was 0.020
        tgx = _tracked_cx(W, draw, "SEE WHAT OTHERS CANNOT", tg, 2)
        _tracked(draw, (tgx, int(H * 0.798)), "SEE WHAT OTHERS CANNOT", tg, t["MUTED"], 2)

        # Domain
        df  = _font(int(W * 0.021))
        dx  = _cx(W, draw, "clairvoyanceengine.info", df)
        draw.text((dx, int(H * 0.875)), "clairvoyanceengine.info", font=df, fill=t["CYAN"])

    return img


# ═══════════════════════════════════════════════════════════════════════════════════
# X HEADER BANNER  1500 × 500
# ═══════════════════════════════════════════════════════════════════════════════════

def make_x_header(theme: dict, variant: str) -> Image.Image:
    W, H = 1500, 500
    img  = Image.new("RGB", (W, H), theme["BG"])
    _draw_bg(img, theme)
    draw = ImageDraw.Draw(img)
    t    = theme

    if variant == "A":
        # ── Asymmetric: large eye left | stacked wordmark right ───────────────
        eye_sz = int(H * 0.64)
        ecx    = int(W * 0.21)
        img    = _draw_eye(img, ecx, H // 2, t, eye_sz)
        draw   = ImageDraw.Draw(img)

        # Vertical rule dividing eye / text zone
        rx = int(W * 0.40)
        draw.line([(rx, 48), (rx, H - 48)], fill=t["DIM"], width=1)

        # Text zone starts at 44% width
        tx0 = int(W * 0.43)

        # CLAIRVOYANCE — size capped so 12-char word fits in remaining canvas width
        tf  = _font(int(H * 0.174), bold=True)
        ty  = int(H * 0.26)
        sp  = max(1, int(H * 0.003))
        img = _glow_text(img, (tx0, ty), "CLAIRVOYANCE", tf,
                         color=t["PURPLE"], glow_color=t["PURPLE"],
                         radius=20, sp=sp)
        draw = ImageDraw.Draw(img)

        # Subtitle
        sub = "ADVANCED SPORTS INTELLIGENCE ENGINE"
        sf  = _font(int(H * 0.054))
        _tracked(draw, (tx0, int(H * 0.60)), sub, sf, t["CYAN"], 2)

        # Tagline — same purple as CLAIRVOYANCE
        tgf = _font(int(H * 0.040))
        _tracked(draw, (tx0, int(H * 0.76)), "SEE WHAT OTHERS CANNOT", tgf, t["PURPLE"], 2)

        # Domain — same cyan as subtitle
        df  = _font(int(H * 0.035))
        draw.text((tx0, int(H * 0.87)), "clairvoyanceengine.info", font=df, fill=t["CYAN"])

    elif variant == "B":
        # ── Centered stacked: eye top-centre, full wordmark below ─────────────
        eye_sz = int(H * 0.50)
        img    = _draw_eye(img, W // 2, int(H * 0.41), t, eye_sz)
        draw   = ImageDraw.Draw(img)

        # Separator
        _sep(draw, W, int(H * 0.68), t, mx=int(W * 0.28))

        # CLAIRVOYANCE
        tf  = _font(int(H * 0.200), bold=True)
        sp  = max(2, int(H * 0.005))
        ty  = int(H * 0.70)
        tx  = _tracked_cx(W, draw, "CLAIRVOYANCE", tf, sp)
        img = _glow_text(img, (tx, ty), "CLAIRVOYANCE", tf,
                         color=t["PURPLE"], glow_color=t["PURPLE"],
                         radius=22, sp=sp)
        draw = ImageDraw.Draw(img)

        # Subtitle
        sub = "ADVANCED SPORTS INTELLIGENCE ENGINE"
        sf  = _font(int(H * 0.050))
        sx  = _tracked_cx(W, draw, sub, sf, 2)
        _tracked(draw, (sx, int(H * 0.88)), sub, sf, t["CYAN"], 2)

        # HUD corner brackets (top only, full banner width)
        m = 28; s = 38
        _brackets(draw, W, H, t, m=m, s=s, w=1)

    elif variant == "C":
        # ── Purple carbon · centred full-brand with section label & domain ────
        # Zoomed-out: eye ~20% smaller, fonts reduced, more breathing room
        eye_sz = int(H * 0.37)                 # was 0.46
        img    = _draw_eye(img, W // 2, int(H * 0.36), t, eye_sz)
        draw   = ImageDraw.Draw(img)

        # HUD brackets all corners
        _brackets(draw, W, H, t, m=28, s=40, w=1)

        # Section label above
        lf  = _font(int(H * 0.036))            # was 0.042
        lx  = _tracked_cx(W, draw, "// ADVANCED SPORTS INTELLIGENCE ENGINE", lf, 2)
        _tracked(draw, (lx, int(H * 0.068)), "// ADVANCED SPORTS INTELLIGENCE ENGINE",
                 lf, t["CYAN_D"], 2)

        # Separator before wordmark
        _sep(draw, W, int(H * 0.635), t, mx=int(W * 0.32))

        # CLAIRVOYANCE
        tf  = _font(int(H * 0.152), bold=True) # was 0.185
        sp  = max(2, int(H * 0.005))
        ty  = int(H * 0.653)
        tx  = _tracked_cx(W, draw, "CLAIRVOYANCE", tf, sp)
        img = _glow_text(img, (tx, ty), "CLAIRVOYANCE", tf,
                         color=t["PURPLE"], glow_color=t["PURPLE"],
                         radius=22, sp=sp)
        draw = ImageDraw.Draw(img)

        # Domain + tagline
        df  = _font(int(H * 0.034))            # was 0.040
        dtx = _tracked_cx(W, draw, "SEE WHAT OTHERS CANNOT", df, 3)
        _tracked(draw, (dtx, int(H * 0.868)), "SEE WHAT OTHERS CANNOT", df, t["MUTED"], 3)

    return img


# ═══════════════════════════════════════════════════════════════════════════════════
# OUTPUT TABLE
# ═══════════════════════════════════════════════════════════════════════════════════

JOBS = [
    # Instagram profile  1080×1080
    ("ig_profile_A",  make_profile, dict(variant="A", W=1080, H=1080), DARK),
    ("ig_profile_B",  make_profile, dict(variant="B", W=1080, H=1080), DARK),
    ("ig_profile_C",  make_profile, dict(variant="C", W=1080, H=1080), PURP),
    # X header  1500×500
    ("x_header_A",   make_x_header, dict(variant="A"), DARK),
    ("x_header_B",   make_x_header, dict(variant="B"), DARK),
    ("x_header_C",   make_x_header, dict(variant="C"), PURP),
    # X profile photo  400×400
    ("x_profile_A",  make_profile, dict(variant="A", W=400, H=400), DARK),
    ("x_profile_B",  make_profile, dict(variant="B", W=400, H=400), DARK),
    ("x_profile_C",  make_profile, dict(variant="C", W=400, H=400), PURP),
    # Discord avatar  512×512
    ("discord_A",    make_profile, dict(variant="A", W=512, H=512), DARK),
    ("discord_B",    make_profile, dict(variant="B", W=512, H=512), DARK),
    ("discord_C",    make_profile, dict(variant="C", W=512, H=512), PURP),
]

if __name__ == "__main__":
    for name, fn, kwargs, theme in JOBS:
        print(f"Generating {name}.png …")
        img = fn(theme, **kwargs)
        for out_dir in (OUT_FE, OUT_DOC):
            path = out_dir / f"{name}.png"
            img.save(str(path), format="PNG", optimize=True)
            print(f"  → {path}")
    print(f"\nDone — {len(JOBS)} assets saved to:")
    print(f"  {OUT_FE}")
    print(f"  {OUT_DOC}")
