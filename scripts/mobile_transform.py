"""
mobile_transform.py
Transforms docs/app.html into a mobile-optimized version for Clairvoyance-backend-mobile.
Run: python3 scripts/mobile_transform.py
Output: docs/app.html (in place — run from mobile repo root or redirect output)
"""
import re, sys, os

src = sys.argv[1] if len(sys.argv) > 1 else 'docs/app.html'
dst = sys.argv[2] if len(sys.argv) > 2 else 'docs/app.html'

html = open(src, encoding='utf-8').read()

# ── 1. Update viewport meta for strict mobile ─────────────────────────────
# Regex-match whatever viewport tag exists (spacing/attrs vary between builds)
# so the replacement never silently fails.
new_vp = '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">'
html, _n = re.subn(r'<meta\s+name="viewport"[^>]*>', new_vp, html, count=1)
if _n == 0:
    # No viewport tag found — inject one right after <head>
    html = re.sub(r'(<head[^>]*>)', r'\1\n' + new_vp, html, count=1)

# ── 2. Inject mobile-only CSS overrides before </style> ──────────────────
mobile_css = """
/* ═══ MOBILE-ONLY OVERRIDES (injected by mobile_transform.py) ═══════════ */
:root{--mob-font:13px;--mob-mono:12px;--mob-orb:11px;}
body{font-size:var(--mob-font)!important;-webkit-text-size-adjust:100%;}
#hdr{height:42px!important;min-height:42px!important;}
.logo{font-size:17px!important;letter-spacing:3px!important;}
.sp{font-size:10px!important;padding:4px 6px!important;letter-spacing:1.5px!important;}
.nb{font-size:10px!important;padding:6px 5px!important;}
.sb2{font-size:10px!important;padding:6px 8px!important;}
.sh{font-size:12px!important;}
.tab{padding:10px 10px 86px!important;}
.sa{padding:10px!important;}
.card{padding:9px 10px!important;}
.gc{padding:0!important;}
.gch{padding:9px 10px!important;}
.brow{padding:6px 8px!important;gap:4px!important;}
.chip{padding:6px 2px!important;min-width:0!important;}
.cht{font-size:9px!important;}
.cho{font-size:13px!important;}
.chp{font-size:10px!important;}
.gtm{font-size:14px!important;}
.gsp{font-size:11px!important;}
.mono,.np{font-size:11px!important;}
.stat-val{font-size:18px!important;}
.stat-lbl{font-size:9px!important;}
.btn{font-size:11px!important;padding:5px 10px!important;}
.btn-sm{font-size:10px!important;padding:3px 7px!important;}
.snav{padding:6px 6px!important;}
.inav{padding:4px 6px!important;}
.g2,.g3,.g4{grid-template-columns:1fr!important;}
.tbl-wrap{overflow-x:auto!important;-webkit-overflow-scrolling:touch!important;}
table{font-size:11px!important;}
th,td{padding:4px 5px!important;}
input[type=range]{height:32px!important;}
/* Header clock — real element ids are #hdr-clock-mt/#hdr-clock-et (the old
   #hdr-clock rule never matched). Shrink the 15px times AND the oversized
   30px "·" separators (14px side padding each) so the MT · date · ET row
   fits an iPhone instead of overflowing the header. */
#hdr-clock-mt,#hdr-clock-et,#hdr-status-bar{font-size:10px!important;letter-spacing:.5px!important;}
.logo>div>span{font-size:15px!important;padding:0 5px!important;}
@media(max-width:390px){
  #hdr-clock-mt,#hdr-clock-et,#hdr-status-bar{font-size:9px!important;}
  .logo>div>span{font-size:12px!important;padding:0 4px!important;}
  .gtm{font-size:13px!important;}
  .logo{font-size:15px!important;}
}
/* safe-area insets for iPhone notch */
#hdr{padding-top:env(safe-area-inset-top)!important;}
.mn,#mn,#mn2,#mn3,#mn4,#mn5,#mn6,#mn7,#mn8,#mn9,#mn10,#mn11{
  padding-bottom:env(safe-area-inset-bottom)!important;
}
/* ── Splash screen — scale wordmark/subtitle to fit iPhone width ────────── */
/* Desktop inline styles use clamp(52px,13vw,110px)+6px tracking which overflows
   a 320-430px screen. These !important rules beat the (non-important) inline
   styles and keep CLAIRVOYANCE + subtitle on one line down to iPhone SE. */
#splash-wordmark{font-size:clamp(28px,9vw,52px)!important;letter-spacing:2px!important;white-space:nowrap!important;}
#splash-sub{font-size:clamp(8px,2.4vw,14px)!important;letter-spacing:1.5px!important;white-space:nowrap!important;}
#splash-bar-wrap{max-width:70vw!important;}
.si{width:100%!important;padding:0 12px!important;box-sizing:border-box!important;text-align:center!important;}
#splash{padding-top:env(safe-area-inset-top)!important;padding-bottom:env(safe-area-inset-bottom)!important;}
"""

# Inject before first </style>
style_end = html.find('</style>')
if style_end != -1:
    html = html[:style_end] + mobile_css + html[style_end:]

# ── 3. Update manifest start_url and PWA name ─────────────────────────────
html = html.replace('"name": "Clairvoyance"', '"name": "Clairvoyance Mobile"', 1)
html = html.replace('"short_name": "CVE"', '"short_name": "CVE-M"', 1)

# ── 4. Update title ───────────────────────────────────────────────────────
# Regex-match whatever the desktop title is (it carries a version suffix) so
# the swap never silently fails.
html = re.sub(r'<title>[^<]*</title>', '<title>CLAIRVOYANCE MOBILE</title>', html, count=1)

# ── 5. Update service worker cache name so it doesn't collide ────────────
html = re.sub(r"cv-engine-v(\d+)", lambda m: f"cve-mobile-v{m.group(1)}", html)

with open(dst, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Mobile transform complete: {src} -> {dst}")
print(f"Lines: {html.count(chr(10))+1}")
