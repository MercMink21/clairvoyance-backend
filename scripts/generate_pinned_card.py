#!/usr/bin/env python3
"""
generate_pinned_card.py — Clairvoyance Engine Pinned Post Cards
Generates 4 × 1080×1080 PNGs for Instagram + X pinned posts.

Variants:
  pinned_card_carbon.png       — black/grey charcoal carbon fiber
  pinned_card_whitecarbon.png  — white/grey charcoal carbon fiber
  pinned_card_purplecarbon.png — deep purple carbon fiber (original brand)
  pinned_card_plaid.png        — black/grey/white/purple tartan plaid

Usage:
  python3 scripts/generate_pinned_card.py
"""

import math, subprocess, sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"], check=True)
    from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).parent.parent
W = H = 1080

X_HANDLE  = "@ClairvoyanceEng"
IG_HANDLE = "@clairvoyanceengine"
DOMAIN    = "clairvoyanceengine.info"

# ── Three theme palettes ───────────────────────────────────────────────────────
THEMES = {
    "carbon": dict(
        BG=(14,14,14), PURPLE=(192,48,240), PURPLE_D=(80,18,110),
        CYAN=(48,208,240), CYAN_D=(20,80,110),
        TEXT=(218,212,232), MUTED=(96,86,128), DIM=(54,46,80),
        SEP=(36,28,60), FOOTER=(8,8,8), light=False, purple_fiber=False,
    ),
    "whitecarbon": dict(
        BG=(235,235,235), PURPLE=(150,10,200), PURPLE_D=(100,10,150),
        CYAN=(10,150,180), CYAN_D=(8,90,120),
        TEXT=(30,24,46), MUTED=(90,80,115), DIM=(140,130,160),
        SEP=(180,172,200), FOOTER=(200,200,204), light=True, purple_fiber=False,
    ),
    "purplecarbon": dict(
        BG=(10,8,20), PURPLE=(192,48,240), PURPLE_D=(80,18,110),
        CYAN=(48,208,240), CYAN_D=(20,80,110),
        TEXT=(218,212,232), MUTED=(96,86,128), DIM=(54,46,80),
        SEP=(36,28,60), FOOTER=(6,4,14), light=False, purple_fiber=True,
    ),
    "plaid": dict(
        BG=(10,10,12), PURPLE=(200,30,255), PURPLE_D=(90,10,130),
        CYAN=(0,210,245), CYAN_D=(0,130,160),
        TEXT=(12,10,18), MUTED=(30,24,44), DIM=(50,44,66),
        SEP=(40,36,56), FOOTER=(6,6,8), light=False, purple_fiber=False,
        plaid=True,
    ),
}

OUTPUT = {
    "carbon":       (ROOT/"frontend"/"pinned_card_carbon.png",      ROOT/"docs"/"pinned_card_carbon.png"),
    "whitecarbon":  (ROOT/"frontend"/"pinned_card_whitecarbon.png",  ROOT/"docs"/"pinned_card_whitecarbon.png"),
    "purplecarbon": (ROOT/"frontend"/"pinned_card_purplecarbon.png", ROOT/"docs"/"pinned_card_purplecarbon.png"),
    "plaid":        (ROOT/"frontend"/"pinned_card_plaid.png",        ROOT/"docs"/"pinned_card_plaid.png"),
}

# ── Font loader ────────────────────────────────────────────────────────────────
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
                _cache[key] = ImageFont.truetype(str(p), size, index=idx); break
            except Exception:
                try: _cache[key] = ImageFont.truetype(str(p), size); break
                except Exception: continue
        if key not in _cache:
            _cache[key] = ImageFont.load_default()
    return _cache[key]

def _tw(draw, text, font):
    bb = draw.textbbox((0,0), text, font=font); return bb[2]-bb[0]
def _cx(draw, text, font): return (W-_tw(draw,text,font))//2
def _tracked_w(draw, text, font, sp):
    return sum(_tw(draw,ch,font)+sp for ch in text)-sp
def _tracked(draw, xy, text, font, fill, sp):
    x, y = xy
    for ch in text:
        draw.text((x,y), ch, font=font, fill=fill); x += _tw(draw,ch,font)+sp
def _tracked_cx(draw, text, font, sp):
    return (W-_tracked_w(draw,text,font,sp))//2

# ── Plaid / tartan background ─────────────────────────────────────────────────
def _draw_plaid_bg(img: Image.Image) -> None:
    """
    Classic black-and-white tartan with cool-grey transitions.
    White and black are the dominant bands; grey creates the authentic
    woven mid-tones at intersections.  No purple in the background —
    purple/cyan are reserved for the text layer above.
    """
    # Palette — strictly black · grey family · off-white
    BLK  = (8,   8,   9)     # near-black base
    DG   = (32,  32,  36)    # dark grey transition
    MG   = (72,  70,  78)    # mid grey
    LG   = (130, 128, 138)   # light grey highlight
    WHT  = (215, 213, 220)   # cool off-white

    # Symmetric tartan sett — wide black & white bands, grey accents
    # One full repeat ≈ 104 px; gives ~10 visible checks across 1080 px
    # fmt: off
    SETT = [
        (BLK, 20), (DG, 5),
        (WHT, 16), (DG, 5),
        (BLK, 10), (DG, 4),
        (MG,   8), (LG, 4), (WHT, 4), (LG, 4), (MG, 8),
        (DG,   4), (BLK, 10),
        (DG,   5), (WHT, 16),
        (DG,   5), (BLK,  1),
    ]
    # fmt: on

    # Build the colour strip for one period
    strip = []
    for col, w in SETT:
        strip.extend([col] * w)
    n = len(strip)

    def avg(a, b):
        """Average blend — gives authentic grey mid-tones where b/w threads cross."""
        return tuple((a[i] + b[i]) // 2 for i in range(3))

    # Build the square tile using a 2×2 twill weave
    tile = Image.new("RGB", (n, n))
    pix  = tile.load()
    for ty in range(n):
        vc = strip[ty]
        for tx in range(n):
            hc = strip[tx]
            # Twill: alternate which thread sits on top in each 2×2 block
            if (tx // 2 + ty // 2) % 2 == 0:
                # Warp (horizontal thread) on top
                pix[tx, ty] = avg(hc, avg(hc, vc))   # 75% hc, 25% vc
            else:
                # Weft (vertical thread) on top
                pix[tx, ty] = avg(vc, avg(vc, hc))   # 75% vc, 25% hc

    # Tile across the full canvas
    for y in range(0, H, n):
        for x in range(0, W, n):
            img.paste(tile, (x, y))

# ── Carbon fiber background (mode-aware) ───────────────────────────────────────
def _draw_bg(img: Image.Image, t: dict) -> None:
    CW, CH = 8, 16; TW, TH = CW*2, CH*2
    tile = Image.new("RGB",(TW,TH)); pix = tile.load()
    for ty in range(TH):
        for tx in range(TW):
            cx=tx//CW; cy=ty//CH
            px=(tx%CW)/(CW-1) if CW>1 else 0
            py=(ty%CH)/(CH-1) if CH>1 else 0
            fib = py if (cx+cy)%2==0 else px
            if t["purple_fiber"]:
                r=int(10+18*fib); g=int(8+12*fib); b=int(20+30*fib)
                if py<0.12: r,g,b=r+5,g+3,b+8
                pix[tx,ty]=(min(r,42),min(g,30),min(b,64))
            elif t["light"]:
                v=int(200+32*fib)
                if py<0.12: v=min(v+10,242)
                pix[tx,ty]=(min(v,242),min(v,242),min(v+1,242))
            else:
                v=int(16+26*fib)
                if py<0.12: v=min(v+8,52)
                pix[tx,ty]=(min(v,52),min(v,52),min(v+1,54))
    for y in range(0,H,TH):
        for x in range(0,W,TW):
            img.paste(tile,(x,y))

# ── Top-only corner HUD brackets ──────────────────────────────────────────────
def _brackets(draw: ImageDraw.ImageDraw, t: dict, m=32, s=48, w=2) -> None:
    for bx, by in [(m,m), (W-m,m)]:          # top-left and top-right only
        sx = 1 if bx < W//2 else -1
        draw.line([(bx,by),(bx+sx*s,by)], fill=t["CYAN_D"], width=w)
        draw.line([(bx,by),(bx,by+s)],    fill=t["CYAN_D"], width=w)

# ── Orbital eye ───────────────────────────────────────────────────────────────
def _draw_eye(img: Image.Image, cx: int, cy: int, t: dict, size: int=94) -> Image.Image:
    draw = ImageDraw.Draw(img)
    ow=int(size*1.10); oh=int(size*0.36)
    draw.ellipse([cx-ow//2,cy-oh//2,cx+ow//2,cy+oh//2], outline=t["CYAN"], width=2)
    gap,tick=7,16
    draw.line([(cx-ow//2-gap-tick,cy),(cx-ow//2-gap,cy)], fill=t["CYAN"], width=1)
    draw.line([(cx+ow//2+gap,cy),(cx+ow//2+gap+tick,cy)], fill=t["CYAN"], width=1)
    draw.line([(cx,cy-oh//2-gap-8),(cx,cy-oh//2-gap)],   fill=t["CYAN"], width=1)
    draw.line([(cx,cy+oh//2+gap),(cx,cy+oh//2+gap+8)],   fill=t["CYAN"], width=1)
    ir=int(size*0.42)
    for angle in range(0,360,12):
        a0=math.radians(angle); a1=math.radians(angle+7)
        x0=cx+int(ir*math.cos(a0)); y0=cy+int(ir*math.sin(a0))
        x1=cx+int(ir*math.cos(a1)); y1=cy+int(ir*math.sin(a1))
        draw.line([(x0,y0),(x1,y1)], fill=t["PURPLE_D"], width=1)
    draw.ellipse([cx-ir,cy-ir,cx+ir,cy+ir], outline=t["PURPLE"], width=3)
    gr=int(size*0.20)
    glow=Image.new("RGBA",(W,H),(0,0,0,0)); gd=ImageDraw.Draw(glow)
    gd.ellipse([cx-gr,cy-gr,cx+gr,cy+gr], fill=(*t["PURPLE"],160))
    glow=glow.filter(ImageFilter.GaussianBlur(18))
    img=Image.alpha_composite(img.convert("RGBA"),glow).convert("RGB")
    draw=ImageDraw.Draw(img)
    pr=int(size*0.26)
    draw.ellipse([cx-pr,cy-pr,cx+pr,cy+pr], fill=(14,8,28) if not t["light"] else (230,225,245))
    draw.ellipse([cx-gr,cy-gr,cx+gr,cy+gr], fill=t["PURPLE"])
    dr=int(size*0.052)
    draw.ellipse([cx-dr,cy-dr,cx+dr,cy+dr], fill=(228,190,255))
    return img

# ── Centred glow text ─────────────────────────────────────────────────────────
def _glow(img, text, y, font, color, glow_color, radius=10, spacing=0):
    tmp=ImageDraw.Draw(img)
    x=_tracked_cx(tmp,text,font,spacing) if spacing else _cx(tmp,text,font)
    gl=Image.new("RGBA",(W,H),(0,0,0,0)); gd=ImageDraw.Draw(gl)
    if spacing: _tracked(gd,(x,y),text,font,(*glow_color,200),spacing)
    else:       gd.text((x,y),text,font=font,fill=(*glow_color,200))
    gl=gl.filter(ImageFilter.GaussianBlur(radius))
    img=Image.alpha_composite(img.convert("RGBA"),gl).convert("RGB")
    draw=ImageDraw.Draw(img)
    if spacing: _tracked(draw,(x,y),text,font,color,spacing)
    else:       draw.text((x,y),text,font=font,fill=color)
    return img

def _sep(draw, y, t, mx=72):
    draw.line([(mx,y),(W-mx,y)], fill=t["SEP"], width=1)

# ── Main card generator ───────────────────────────────────────────────────────
def generate(t: dict) -> Image.Image:
    img  = Image.new("RGB",(W,H),t["BG"])
    if t.get("plaid"):
        _draw_plaid_bg(img)
    else:
        _draw_bg(img, t)
    draw = ImageDraw.Draw(img)

    # Top-only corner brackets
    _brackets(draw, t)

    # Eye logo
    img  = _draw_eye(img, W//2, 148, t, size=90)
    draw = ImageDraw.Draw(img)

    # CLAIRVOYANCE title
    title_font = _font(88, bold=True)
    img  = _glow(img,"CLAIRVOYANCE",258,title_font,
                 color=t["PURPLE"],glow_color=t["PURPLE"],radius=18,spacing=4)
    draw = ImageDraw.Draw(img)

    # Subtitle — updated wording
    sub_font = _font(24)
    img  = _glow(img,"ADVANCED SPORTS INTELLIGENCE ENGINE",362,sub_font,
                 color=t["CYAN"],glow_color=t["CYAN"],radius=6,spacing=3)
    draw = ImageDraw.Draw(img)

    # Tagline — now in PURPLE, same shade as title
    tag_font = _font(18)
    x_tag = _tracked_cx(draw,"SEE WHAT OTHERS CANNOT",tag_font,3)
    _tracked(draw,(x_tag,402),"SEE WHAT OTHERS CANNOT",tag_font,t["PURPLE"],3)

    _sep(draw,442,t)

    # Description — updated copy
    desc_font  = _font(25)
    desc_lines = [
        "An advanced sports intelligence engine built around",
        "mathematical precision, multi-layered ensemble models,",
        "and adaptive intelligence.",
    ]
    dy = 468
    for line in desc_lines:
        x = _cx(draw,line,desc_font)
        draw.text((x,dy),line,font=desc_font,fill=t["TEXT"]); dy+=36

    _sep(draw,dy+18,t); dy+=46

    # Feature rows
    label_font = _font(20,bold=True)
    val_font   = _font(20)
    rows = [
        ("SPORTS COVERED",
         "MLB  ·  NBA  ·  NHL  ·  TENNIS  ·  F1  ·  More Coming"),
        ("EVERY PICK GRADED",
         "Advanced Analytics  ·  Confidence Scores  ·  Market Edge"),
        ("ADAPTIVE ENGINE",
         "Recalibration  ·  Simulations  ·  Cutting Edge Statistical Analysis"),
    ]
    for label, value in rows:
        lx = _tracked_cx(draw,label,label_font,2)
        _tracked(draw,(lx,dy),label,label_font,t["CYAN"],2); dy+=30
        vx = _cx(draw,value,val_font)
        draw.text((vx,dy),value,font=val_font,fill=t["MUTED"]); dy+=48

    _sep(draw,dy+4,t); dy+=28

    # Follow block
    follow_font = _font(22,bold=True)
    fol_x = _tracked_cx(draw,"FOLLOW FOR DAILY SIGNALS",follow_font,2)
    _tracked(draw,(fol_x,dy),"FOLLOW FOR DAILY SIGNALS",follow_font,t["TEXT"],2)
    dy+=40

    # Handles — both in PURPLE (same shade as CLAIRVOYANCE header)
    lbl_font = _font(17); h_font = _font(26,bold=True); gap_mid = 36
    x_lbl_w  = _tw(draw,"X ",lbl_font)
    x_h_w    = _tw(draw,X_HANDLE,h_font)
    ig_lbl_w = _tw(draw,"IG ",lbl_font)
    ig_h_w   = _tw(draw,IG_HANDLE,h_font)
    total_w  = x_lbl_w+x_h_w+gap_mid+ig_lbl_w+ig_h_w
    sx       = (W-total_w)//2

    # "X" label + X handle (purple, with glow)
    draw.text((sx,dy+5),"X ",font=lbl_font,fill=t["MUTED"]); sx+=x_lbl_w
    gl=Image.new("RGBA",(W,H),(0,0,0,0)); gd=ImageDraw.Draw(gl)
    gd.text((sx,dy),X_HANDLE,font=h_font,fill=(*t["PURPLE"],200))
    gl=gl.filter(ImageFilter.GaussianBlur(8))
    img=Image.alpha_composite(img.convert("RGBA"),gl).convert("RGB")
    draw=ImageDraw.Draw(img)
    draw.text((sx,dy),X_HANDLE,font=h_font,fill=t["PURPLE"]); sx+=x_h_w+gap_mid

    # "IG" label + IG handle (purple, with glow)
    draw.text((sx,dy+5),"IG ",font=lbl_font,fill=t["MUTED"]); sx+=ig_lbl_w
    gl=Image.new("RGBA",(W,H),(0,0,0,0)); gd=ImageDraw.Draw(gl)
    gd.text((sx,dy),IG_HANDLE,font=h_font,fill=(*t["PURPLE"],200))
    gl=gl.filter(ImageFilter.GaussianBlur(8))
    img=Image.alpha_composite(img.convert("RGBA"),gl).convert("RGB")
    draw=ImageDraw.Draw(img)
    draw.text((sx,dy),IG_HANDLE,font=h_font,fill=t["PURPLE"])

    dy+=46

    # Domain
    dom_font = _font(20)
    dx = _cx(draw,DOMAIN,dom_font)
    draw.text((dx,dy),DOMAIN,font=dom_font,fill=t["CYAN_D"])

    # Footer bar
    draw.rectangle([(0,H-60),(W,H)],fill=t["FOOTER"])
    foot_font = _font(18,bold=True)
    draw.text((72,H-38),"CLAIRVOYANCE ENGINE",font=foot_font,fill=t["MUTED"])
    disc_font = _font(16)
    disc = "Model outputs are probabilistic projections, not financial advice."
    draw.text((_cx(draw,disc,disc_font),H-22),disc,font=disc_font,fill=t["DIM"])

    return img


if __name__ == "__main__":
    for name, theme in THEMES.items():
        print(f"Generating pinned_card_{name}.png…")
        img = generate(theme)
        for path in OUTPUT[name]:
            img.save(str(path), format="PNG", optimize=True)
            print(f"  Saved → {path}")
    print("Done — all 4 variants saved.")
