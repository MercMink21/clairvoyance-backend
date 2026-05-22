#!/usr/bin/env python3
"""
generate_social_assets.py — Clairvoyance Social Media Asset Generator

Generates 12 images across 4 platforms × 3 variants each:
  ig_profile_A/B/C.png    1080×1080   Instagram profile picture
  x_header_A/B/C.png      1500×500    X (Twitter) banner header
  x_profile_A/B/C.png     400×400     X profile photo
  discord_A/B/C.png       512×512     Discord avatar

Variant themes:
  A — Carbon · icon only (eye) · clean, minimal
  B — Carbon · eye + CLAIRVOYANCE wordmark
  C — Carbon · eye + CLAIRVOYANCE + "Advanced Sports Intelligence Engine"

Brand spec:
  Font     : Orbitron (/tmp/Orbitron.ttf)
  Purple   : rgb(240,   0, 255)  — neon
  Cyan     : rgb(  0, 240, 255)  — neon
  CF base  : rgb( 16,  16,  16)  — darkest groove
  CF peak  : rgb( 50,  50,  51)  — strand highlight
  CF fill  : rgb( 24,  24,  24)  — mid-tone

Usage:
  python3 scripts/generate_social_assets.py
"""

import math, subprocess, sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import numpy as np
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "Pillow", "numpy"], check=True)
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import numpy as np

ROOT    = Path(__file__).parent.parent
OUT_FE  = ROOT / "frontend" / "social"
OUT_DOC = ROOT / "docs"    / "social"
for d in (OUT_FE, OUT_DOC):
    d.mkdir(parents=True, exist_ok=True)

# ── Brand colors ─────────────────────────────────────────────────────────────────
PURPLE     = (240,   0, 255)    # neon purple
CYAN       = (  0, 240, 255)    # neon cyan
CF_BASE    = ( 16,  16,  16)    # darkest CF groove
CF_PEAK    = ( 50,  50,  51)    # CF strand highlight
CF_FILL    = ( 24,  24,  24)    # CF mid background

# ── Theme dicts ───────────────────────────────────────────────────────────────────
DARK = dict(
    BG=CF_BASE, PURPLE=PURPLE, PURPLE_D=(110, 0, 130),
    CYAN=CYAN, CYAN_D=(0, 120, 145),
    TEXT=(232, 240, 255), MUTED=(105, 118, 155), DIM=(55, 50, 72),
    purple_bg=False,
)
PURP = dict(
    BG=(12, 8, 18), PURPLE=PURPLE, PURPLE_D=(110, 0, 130),
    CYAN=CYAN, CYAN_D=(0, 120, 145),
    TEXT=(232, 240, 255), MUTED=(105, 118, 155), DIM=(55, 50, 72),
    purple_bg=True,
)

# ── Font loader — Orbitron primary, system fallback ───────────────────────────────
_FONT_PRIMARY = "/tmp/Orbitron.ttf"
_FONT_FALLBACKS = [
    "/Library/Fonts/Orbitron-Regular.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]
_fcache: dict = {}

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key in _fcache:
        return _fcache[key]
    # Try Orbitron first (single weight file — bold is same face)
    for path in [_FONT_PRIMARY] + _FONT_FALLBACKS:
        p = Path(path)
        if not p.exists():
            continue
        try:
            idx = 1 if bold and path.endswith(".ttc") else 0
            _fcache[key] = ImageFont.truetype(str(p), max(6, size), index=idx)
            return _fcache[key]
        except Exception:
            try:
                _fcache[key] = ImageFont.truetype(str(p), max(6, size))
                return _fcache[key]
            except Exception:
                continue
    _fcache[key] = ImageFont.load_default()
    return _fcache[key]

# ── Text helpers ──────────────────────────────────────────────────────────────────
def _tw(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

def _th(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]

def _tracked_w(draw, text, font, sp):
    return sum(_tw(draw, ch, font) + sp for ch in text) - sp

def _tracked(draw, xy, text, font, fill, sp=0):
    x, y = xy
    if sp == 0:
        draw.text((x, y), text, font=font, fill=fill)
        return
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += _tw(draw, ch, font) + sp

def _tracked_cx(iw, draw, text, font, sp=0):
    return (iw - _tracked_w(draw, text, font, sp)) // 2

def _cx(iw, draw, text, font):
    return (iw - _tw(draw, text, font)) // 2

# ── Carbon fiber background ───────────────────────────────────────────────────────
def _draw_bg(img: Image.Image, t: dict) -> None:
    """
    Exact brand CF spec:
      Base dark  rgb(16,16,16)  — groove shadow
      Strand peak rgb(50,50,51) — fiber highlight
      Fill        rgb(24,24,24) — mid background
    14-pixel diagonal weave, alternating fiber directions.
    """
    W, H = img.size
    CELL = 14

    xs = np.arange(W, dtype=np.float32)
    ys = np.arange(H, dtype=np.float32)
    xg, yg = np.meshgrid(xs, ys)

    cx = (xg // CELL).astype(np.int32)
    cy = (yg // CELL).astype(np.int32)
    px = (xg % CELL) / (CELL - 1)   # 0..1 within cell
    py = (yg % CELL) / (CELL - 1)

    # Alternate fiber direction per cell: even → horizontal fiber (py), odd → vertical (px)
    fib = np.where((cx + cy) % 2 == 0, py, px)

    # Peak brightness rises to centre of fiber (triangle wave)
    peak = 1.0 - np.abs(fib * 2.0 - 1.0)

    # Groove darkening at cell edges
    edge = np.minimum(np.minimum(px, 1.0 - px), np.minimum(py, 1.0 - py))
    groove_thresh = 1.5 / CELL
    groove_fade   = np.clip(edge / groove_thresh, 0.0, 1.0)

    fill_v = float(CF_FILL[0])   # 24
    base_v = float(CF_BASE[0])   # 16
    peak_v = float(CF_PEAK[0])   # 50

    # Blend: groove → fill → peak
    groove_v = base_v + (fill_v - base_v) * groove_fade
    strand_v = fill_v + (peak_v - fill_v) * peak * 0.80
    v = np.where(groove_fade < 1.0, np.minimum(groove_v, strand_v + 2), strand_v)
    v = np.clip(v, base_v, peak_v).astype(np.uint8)

    if t.get("purple_bg"):
        # Subtle purple tint: darken R/G slightly, lift B
        r = np.clip(v.astype(np.int32) - 3, 0, 255).astype(np.uint8)
        g = np.clip(v.astype(np.int32) - 5, 0, 255).astype(np.uint8)
        b = np.clip(v.astype(np.int32) + 9, 0, 255).astype(np.uint8)
        arr = np.stack([r, g, b], axis=-1)
    else:
        b = np.clip(v.astype(np.int32) + 1, 0, 255).astype(np.uint8)
        arr = np.stack([v, v, b], axis=-1)

    img.paste(Image.fromarray(arr, "RGB"))

# ── Neon glow text ────────────────────────────────────────────────────────────────
def _glow_text(img, xy, text, font, color, glow_color=None, radius=14, sp=0):
    if glow_color is None:
        glow_color = color
    x, y = xy
    W, H = img.size
    gl   = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(gl)
    gc   = (*glow_color, 180)
    _tracked(gd, (x, y), text, font, gc, sp)
    gl   = gl.filter(ImageFilter.GaussianBlur(radius))
    img  = Image.alpha_composite(img.convert("RGBA"), gl).convert("RGB")
    draw = ImageDraw.Draw(img)
    _tracked(draw, (x, y), text, font, color, sp)
    return img

# ── Orbital eye ───────────────────────────────────────────────────────────────────
def _draw_eye(img: Image.Image, ecx: int, ecy: int, t: dict, size: int) -> Image.Image:
    IW, IH = img.size
    draw   = ImageDraw.Draw(img)
    P, C   = t["PURPLE"], t["CYAN"]

    # Outer orbital ellipse (cyan)
    ow = int(size * 1.12); oh = int(size * 0.37)
    sw = max(2, size // 55)
    draw.ellipse([ecx - ow//2, ecy - oh//2, ecx + ow//2, ecy + oh//2], outline=C, width=sw)

    # HUD tick marks  L / R / T / B
    gap  = size // 13;  t_lr = size // 8;  t_tb = size // 11
    lw   = max(1, size // 90)
    draw.line([(ecx - ow//2 - gap - t_lr, ecy), (ecx - ow//2 - gap, ecy)], fill=C, width=lw)
    draw.line([(ecx + ow//2 + gap, ecy),  (ecx + ow//2 + gap + t_lr, ecy)], fill=C, width=lw)
    draw.line([(ecx, ecy - oh//2 - gap - t_tb), (ecx, ecy - oh//2 - gap)], fill=C, width=lw)
    draw.line([(ecx, ecy + oh//2 + gap),  (ecx, ecy + oh//2 + gap + t_tb)], fill=C, width=lw)

    # Inner dashed ring
    ir_dash = int(size * 0.44)
    seg_on  = 8;  seg_gap = 14
    for angle in range(0, 360, seg_on + seg_gap):
        a0 = math.radians(angle);  a1 = math.radians(angle + seg_on)
        x0 = ecx + int(ir_dash * math.cos(a0));  y0 = ecy + int(ir_dash * math.sin(a0))
        x1 = ecx + int(ir_dash * math.cos(a1));  y1 = ecy + int(ir_dash * math.sin(a1))
        draw.line([(x0, y0), (x1, y1)], fill=t["MUTED"], width=lw)

    # Main iris ring (purple)
    ir = int(size * 0.36)
    draw.ellipse([ecx - ir, ecy - ir, ecx + ir, ecy + ir], outline=P, width=max(2, size // 38))

    # Pupil glow layer
    gr   = int(size * 0.22)
    glow = Image.new("RGBA", (IW, IH), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow)
    gd.ellipse([ecx - gr, ecy - gr, ecx + gr, ecy + gr], fill=(*P, 155))
    glow = glow.filter(ImageFilter.GaussianBlur(max(6, size // 16)))
    img  = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Dark pupil fill
    pr = int(size * 0.28)
    draw.ellipse([ecx - pr, ecy - pr, ecx + pr, ecy + pr], fill=(8, 4, 20))

    # Purple iris fill
    draw.ellipse([ecx - gr, ecy - gr, ecx + gr, ecy + gr], fill=P)

    # Bright core highlight
    dr = int(size * 0.055)
    draw.ellipse([ecx - dr, ecy - dr, ecx + dr, ecy + dr], fill=(235, 195, 255))

    return img

# ── HUD corner brackets ───────────────────────────────────────────────────────────
def _brackets(draw, iw, ih, t, m=32, s=44, w=2):
    c = t["CYAN_D"]
    for bx, by in [(m, m), (iw - m, m)]:
        sx = 1 if bx < iw // 2 else -1
        draw.line([(bx, by), (bx + sx * s, by)], fill=c, width=w)
        draw.line([(bx, by), (bx, by + s)],      fill=c, width=w)

# ── Separator rule ────────────────────────────────────────────────────────────────
def _sep(draw, iw, y, t, mx=60):
    draw.line([(mx, y), (iw - mx, y)], fill=t["DIM"], width=1)


# ═══════════════════════════════════════════════════════════════════════════════════
# PROFILE / SQUARE  (IG 1080×1080 · X profile 400×400 · Discord 512×512)
# ═══════════════════════════════════════════════════════════════════════════════════

def make_profile(theme: dict, variant: str, W: int, H: int) -> Image.Image:
    img  = Image.new("RGB", (W, H), theme["BG"])
    _draw_bg(img, theme)
    draw = ImageDraw.Draw(img)
    t    = theme

    if variant == "A":
        # ── Icon only ─────────────────────────────────────────────────────────
        eye_sz = int(min(W, H) * 0.54)
        img    = _draw_eye(img, W // 2, H // 2, t, eye_sz)
        draw   = ImageDraw.Draw(img)
        m = max(18, W // 28);  s = max(24, W // 22)
        _brackets(draw, W, H, t, m=m, s=s, w=max(1, W // 300))

    elif variant == "B":
        # ── Eye + wordmark ────────────────────────────────────────────────────
        eye_sz = int(min(W, H) * 0.40)
        ey     = int(H * 0.36)
        img    = _draw_eye(img, W // 2, ey, t, eye_sz)
        draw   = ImageDraw.Draw(img)
        _sep(draw, W, int(H * 0.605), t, mx=int(W * 0.12))

        tf  = _font(int(W * 0.078), bold=True)
        ty  = int(H * 0.635)
        tx  = _tracked_cx(W, draw, "CLAIRVOYANCE", tf)
        img = _glow_text(img, (tx, ty), "CLAIRVOYANCE", tf,
                         color=t["PURPLE"], radius=max(8, int(W * 0.013)))
        draw = ImageDraw.Draw(img)

        df  = _font(int(W * 0.024))
        dy  = ty + int(W * 0.078) + int(H * 0.022)
        dx  = _cx(W, draw, "clairvoyanceengine.info", df)
        draw.text((dx, dy), "clairvoyanceengine.info", font=df, fill=t["CYAN"])

    elif variant == "C":
        # ── Full brand lockup ─────────────────────────────────────────────────
        # "Just a tad" smaller than original: eye 0.36→0.33, fonts ~7% reduced
        eye_sz = int(min(W, H) * 0.33)         # original was 0.36
        ey     = int(H * 0.30)
        img    = _draw_eye(img, W // 2, ey, t, eye_sz)
        draw   = ImageDraw.Draw(img)

        # HUD brackets
        m = max(18, W // 28);  s = max(24, W // 22)
        _brackets(draw, W, H, t, m=m, s=s, w=max(1, W // 300))

        # Separator
        sep_y = int(H * 0.560)
        _sep(draw, W, sep_y, t, mx=int(W * 0.11))

        # CLAIRVOYANCE
        tf  = _font(int(W * 0.069), bold=True)  # original was 0.074
        ty  = int(H * 0.578)
        tx  = _tracked_cx(W, draw, "CLAIRVOYANCE", tf)
        img = _glow_text(img, (tx, ty), "CLAIRVOYANCE", tf,
                         color=t["PURPLE"], radius=max(10, int(W * 0.013)))
        draw = ImageDraw.Draw(img)

        # Subtitle — neon cyan, Orbitron
        sub = "ADVANCED SPORTS INTELLIGENCE ENGINE"
        sf  = _font(int(W * 0.022))             # original was 0.024
        sx  = _cx(W, draw, sub, sf)
        sy  = int(H * 0.715)
        draw.text((sx, sy), sub, font=sf, fill=t["CYAN"])

        # Thin rule
        _sep(draw, W, int(H * 0.790), t, mx=int(W * 0.18))

        # Tagline
        tg  = _font(int(W * 0.019))             # original was 0.020
        tgx = _cx(W, draw, "SEE WHAT OTHERS CANNOT", tg)
        draw.text((tgx, int(H * 0.808)), "SEE WHAT OTHERS CANNOT",
                  font=tg, fill=t["MUTED"])

        # Domain
        df  = _font(int(W * 0.022))
        dx  = _cx(W, draw, "clairvoyanceengine.info", df)
        draw.text((dx, int(H * 0.880)), "clairvoyanceengine.info",
                  font=df, fill=t["CYAN"])

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
        # ── Asymmetric: eye left | wordmark right ─────────────────────────────
        eye_sz = int(H * 0.64)
        ecx    = int(W * 0.21)
        img    = _draw_eye(img, ecx, H // 2, t, eye_sz)
        draw   = ImageDraw.Draw(img)
        draw.line([(int(W * 0.40), 48), (int(W * 0.40), H - 48)], fill=t["DIM"], width=1)

        tx0 = int(W * 0.43)
        tf  = _font(int(H * 0.174), bold=True)
        ty  = int(H * 0.26)
        img = _glow_text(img, (tx0, ty), "CLAIRVOYANCE", tf,
                         color=t["PURPLE"], radius=20)
        draw = ImageDraw.Draw(img)

        sf  = _font(int(H * 0.050))
        draw.text((tx0, int(H * 0.60)), "ADVANCED SPORTS INTELLIGENCE ENGINE",
                  font=sf, fill=t["CYAN"])
        tgf = _font(int(H * 0.038))
        draw.text((tx0, int(H * 0.76)), "SEE WHAT OTHERS CANNOT",
                  font=tgf, fill=t["PURPLE"])
        df  = _font(int(H * 0.032))
        draw.text((tx0, int(H * 0.88)), "clairvoyanceengine.info",
                  font=df, fill=t["CYAN"])

    elif variant == "B":
        # ── Centered: eye top, wordmark below ─────────────────────────────────
        eye_sz = int(H * 0.50)
        img    = _draw_eye(img, W // 2, int(H * 0.41), t, eye_sz)
        draw   = ImageDraw.Draw(img)
        _sep(draw, W, int(H * 0.68), t, mx=int(W * 0.28))

        tf  = _font(int(H * 0.200), bold=True)
        ty  = int(H * 0.70)
        tx  = _tracked_cx(W, draw, "CLAIRVOYANCE", tf)
        img = _glow_text(img, (tx, ty), "CLAIRVOYANCE", tf,
                         color=t["PURPLE"], radius=22)
        draw = ImageDraw.Draw(img)

        sub = "ADVANCED SPORTS INTELLIGENCE ENGINE"
        sf  = _font(int(H * 0.046))
        sx  = _cx(W, draw, sub, sf)
        draw.text((sx, int(H * 0.88)), sub, font=sf, fill=t["CYAN"])
        _brackets(draw, W, H, t, m=28, s=38, w=1)

    elif variant == "C":
        # ── Full brand, centred — just a tad smaller than original ────────────
        eye_sz = int(H * 0.43)                  # original was 0.46
        img    = _draw_eye(img, W // 2, int(H * 0.37), t, eye_sz)
        draw   = ImageDraw.Draw(img)
        _brackets(draw, W, H, t, m=28, s=40, w=1)

        # Section label
        lf  = _font(int(H * 0.040))             # original was 0.042
        lx  = _cx(W, draw, "// ADVANCED SPORTS INTELLIGENCE ENGINE", lf)
        draw.text((lx, int(H * 0.072)), "// ADVANCED SPORTS INTELLIGENCE ENGINE",
                  font=lf, fill=t["CYAN_D"])

        _sep(draw, W, int(H * 0.645), t, mx=int(W * 0.30))

        # CLAIRVOYANCE
        tf  = _font(int(H * 0.174), bold=True)  # original was 0.185
        ty  = int(H * 0.663)
        tx  = _tracked_cx(W, draw, "CLAIRVOYANCE", tf)
        img = _glow_text(img, (tx, ty), "CLAIRVOYANCE", tf,
                         color=t["PURPLE"], radius=24)
        draw = ImageDraw.Draw(img)

        df  = _font(int(H * 0.038))             # original was 0.040
        dtx = _cx(W, draw, "SEE WHAT OTHERS CANNOT", df)
        draw.text((dtx, int(H * 0.872)), "SEE WHAT OTHERS CANNOT",
                  font=df, fill=t["MUTED"])

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
