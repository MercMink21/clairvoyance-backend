#!/usr/bin/env python3
"""
CLAIRVOYANCE — Pre-push validator
Runs automatically via .git/hooks/pre-push
Also callable directly: python3 scripts/validate.py [--fix]

Exit 0 = all checks pass (push proceeds)
Exit 1 = checks failed (push blocked)
"""

import re, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_HTML = os.path.join(ROOT, 'docs', 'app.html')

BOLD  = '\033[1m'
RED   = '\033[31m'
GRN   = '\033[32m'
YLW   = '\033[33m'
CYN   = '\033[36m'
RST   = '\033[0m'

errors   = []
warnings = []
passed   = []

def ok(msg):
    passed.append(msg)

def err(msg):
    errors.append(msg)

def warn(msg):
    warnings.append(msg)


# ─────────────────────────────────────────────────────────────────────────────
# LOAD FILE
# ─────────────────────────────────────────────────────────────────────────────
if not os.path.exists(APP_HTML):
    print(f'{RED}FATAL: docs/app.html not found{RST}')
    sys.exit(1)

html = open(APP_HTML, encoding='utf-8').read()

# Also validate index.html exists and matches
IDX_HTML = os.path.join(ROOT, 'docs', 'index.html')
if not os.path.exists(IDX_HTML):
    err('docs/index.html missing — must be kept in sync with app.html')
elif open(IDX_HTML, encoding='utf-8').read() != html:
    err('docs/index.html differs from app.html — run: cp docs/app.html docs/index.html')
else:
    ok('index.html matches app.html')


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACT MAIN JS BLOCK
# ─────────────────────────────────────────────────────────────────────────────
scripts = list(re.finditer(r'<script([^>]*)>([\s\S]*?)</script>', html))
js_blocks = [s.group(2) for s in scripts if len(s.group(2)) > 10000]

if not js_blocks:
    err('No main JS block found (> 10 000 chars)')
    print(f'{RED}FATAL: cannot locate main JS block{RST}')
    sys.exit(1)

main_js = js_blocks[0]


# ─────────────────────────────────────────────────────────────────────────────
# 1. JS SYNTAX INTEGRITY
# ─────────────────────────────────────────────────────────────────────────────
bt = main_js.count('`')
if bt % 2 == 0:
    ok(f'Backticks even: {bt}')
else:
    err(f'ODD BACKTICK COUNT ({bt}) — unclosed template literal will crash engine')

op = main_js.count('{')
cl = main_js.count('}')
if op == cl:
    ok(f'Braces balanced: {op}/{cl}')
else:
    err(f'BRACE MISMATCH: {op} open vs {cl} close (diff={op-cl}) — function not closed')

lp = len(re.findall(r'\blet LOCKED_PROPS\b', main_js))
if lp == 1:
    ok('LOCKED_PROPS declared once')
elif lp == 0:
    err('LOCKED_PROPS not found — required global missing')
else:
    err(f'DUPLICATE let LOCKED_PROPS ({lp}x) — SyntaxError will crash engine on load')

sp = len(re.findall(r'\bconst _origSaveP\b', main_js))
if sp == 1:
    ok('_origSaveP declared once')
elif sp == 0:
    warn('_origSaveP not found — picks sync may be broken')
else:
    err(f'DUPLICATE const _origSaveP ({sp}x) — infinite loop crash')

# ─────────────────────────────────────────────────────────────────────────────
# 2. SERVICE WORKER — must stay disabled
# ─────────────────────────────────────────────────────────────────────────────
sw = html.count('serviceWorker.register')
if sw == 0:
    ok('No service worker registration')
else:
    err(f'serviceWorker.register found ({sw}x) — re-enabling SW causes blank page loading loops')

# ─────────────────────────────────────────────────────────────────────────────
# 3. CRITICAL HTML ELEMENTS
# ─────────────────────────────────────────────────────────────────────────────
required_ids = [
    ('sp-home',              'Home pane'),
    ('sp-mlb',               'Baseball pane'),
    ('sp-nba',               'Basketball pane'),
    ('sp-hk',                'Hockey pane'),
    ('sp-ten',               'Tennis pane'),
    ('sp-f1',                'F1 pane'),
    ('sp-fb',                'Football pane'),
    ('sp-ovr',               'Overall pane'),
    ('sp-analytics',         'Analytics pane'),
    ('sp-social',            'Social pane'),
    ('sp-news',              'News pane'),
    ('sp-fut',               'Futures pane'),
    ('hdr',                  'Header'),
    ('sbar',                 'Sport nav bar'),
    ('home-picks',           'Home picks container'),
    ('home-best-bets',       'Home best bets container'),
    ('home-engine-record',   'Home engine record'),
    ('home-performance',     'Home performance section'),
    ('home-yesterday-results','Home yesterday results'),
    ('home-hero-ts',         'Home hero timestamp'),
    ('home-hero-acc',        'Home hero accuracy'),
    ('home-hero-rec',        'Home hero record'),
    ('home-data-ts',         'Home data-as-of timestamp'),
    ('navd-ovr',             'Overall nav dropdown'),
    ('navd-mlb',             'Baseball nav dropdown'),
    ('navd-nba',             'Basketball nav dropdown'),
    ('navd-hk',              'Hockey nav dropdown'),
    ('navd-ten',             'Tennis nav dropdown'),
    ('navd-f1',              'F1 nav dropdown'),
    ('navd-fb',              'Football nav dropdown'),
    ('navd-social',          'Social nav dropdown'),
    ('splash',               'Splash screen'),
    ('app',                  'App container'),
    ('mn',                   'Mobile nav'),
    ('toast',                'Toast notification'),
]
for eid, label in required_ids:
    pat = f'id="{eid}"'
    if pat in html:
        ok(f'Element present: {label} (#{eid})')
    else:
        err(f'MISSING ELEMENT: {label} (#{eid})')

# ─────────────────────────────────────────────────────────────────────────────
# 4. CRITICAL JS FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────
required_fns = [
    'function renderHomePage()',
    'function renderPerformanceSection(',
    'function endSplash(',
    'function SS(',
    'function T(',
    'function setSub(',
    'function updHdr(',
    'function getP(',
    'function saveP(',
    'function loadRemoteData(',
    'function loadPicksFromGitHub(',
    'function savePicksToGitHub(',
    'function getMSTNow(',
    'function showND(',
    'function hideAllND(',
    'function startHideND(',
    '(function seedBetHistory(',
    'function renderNHLPicks(',
    'function renderNBAPicks(',
    'function renderTennisPicks(',
]
for fn in required_fns:
    if fn in main_js:
        ok(f'Function present: {fn.split("(")[0].replace("function ","").replace("(","").strip()}')
    else:
        err(f'MISSING FUNCTION: {fn}')

# ─────────────────────────────────────────────────────────────────────────────
# 5. DUPLICATE ID DETECTION
# ─────────────────────────────────────────────────────────────────────────────
# Find all id="..." in HTML (outside of <script> blocks so JS strings don't count)
html_without_js = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html)
all_ids = re.findall(r'\bid="([^"]+)"', html_without_js)
from collections import Counter
id_counts = Counter(all_ids)
dup_ids = {k: v for k, v in id_counts.items() if v > 1}
if dup_ids:
    for did, cnt in dup_ids.items():
        err(f'DUPLICATE HTML ID: "{did}" appears {cnt}x — getElementById returns wrong element')
else:
    ok(f'No duplicate HTML IDs ({len(all_ids)} unique IDs found)')

# ─────────────────────────────────────────────────────────────────────────────
# 6. NAV DROPDOWN PLACEMENT — must be at body level, NOT inside JS strings
# ─────────────────────────────────────────────────────────────────────────────
if 'id="navd-ovr"' in html:
    navd_pos = html.index('id="navd-ovr"')
    # Must come after </script> closing the main JS block
    last_script_close = html.rindex('</script>')
    # Must come before real </body>
    real_body = html.rindex('</body>')
    if navd_pos > last_script_close and navd_pos < real_body:
        ok('Nav dropdowns at body level (after </script>, before </body>)')
    elif navd_pos < last_script_close:
        # Check if navd is inside a JS template literal (the critical bug)
        context_before = html[max(0, navd_pos-200):navd_pos]
        if '`' in context_before or 'innerHTML' in context_before:
            err('NAV DROPDOWNS INSIDE JS STRING — raw HTML injected into template literal, corrupts JS')
        else:
            err(f'Nav dropdowns appear before </script> (pos {navd_pos} vs script close {last_script_close})')
    else:
        err(f'Nav dropdowns after </body> (pos {navd_pos} vs body {real_body})')
else:
    warn('No navd-ovr found — nav dropdowns not present')

# ─────────────────────────────────────────────────────────────────────────────
# 7. SEED BET HISTORY IIFE MUST EXIST
# ─────────────────────────────────────────────────────────────────────────────
if '(function seedBetHistory()' in html:
    ok('seedBetHistory() IIFE present')
else:
    err('MISSING seedBetHistory() IIFE — bet history will not populate on load')

# ─────────────────────────────────────────────────────────────────────────────
# 8. INIT SEQUENCE INTEGRITY
# ─────────────────────────────────────────────────────────────────────────────
if 'renderHomePage()' in main_js and 'endSplash()' in main_js:
    dom_block = main_js[main_js.rindex('DOMContentLoaded'):]
    has_render = 'renderHomePage' in dom_block
    has_splash = 'endSplash' in dom_block
    if has_render and has_splash:
        ok('renderHomePage() + endSplash() in DOMContentLoaded init block')
    else:
        if not has_render:
            err('renderHomePage() missing from DOMContentLoaded init block')
        if not has_splash:
            err('endSplash() missing from DOMContentLoaded init block')

# ─────────────────────────────────────────────────────────────────────────────
# 9. APP MUST NEVER START HIDDEN
# ─────────────────────────────────────────────────────────────────────────────
app_style_match = re.search(r'id="app"[^>]*style="[^"]*opacity\s*:\s*0', html)
if app_style_match:
    err('#app starts with opacity:0 — page will be blank if JS crashes')
else:
    ok('#app does not start hidden (opacity:0 absent)')

# ─────────────────────────────────────────────────────────────────────────────
# 10. REMOVED ELEMENTS STAY REMOVED
# ─────────────────────────────────────────────────────────────────────────────
must_be_gone = [
    ('id="date-strip"',           'Top date/status strip (removed by design)'),
    ('id="home-sync-bar"',        'Home sync status bar (removed by design)'),
    ('CLAIRVOYANCE ENGINE v8.0',  'Version comment banner (removed by design)'),
]
for pattern, label in must_be_gone:
    if pattern not in html:
        ok(f'Correctly absent: {label}')
    else:
        warn(f'Re-appeared: {label} — was intentionally removed, check if re-added accidentally')

# ─────────────────────────────────────────────────────────────────────────────
# 11. KEY CSS ANIMATIONS PRESENT
# ─────────────────────────────────────────────────────────────────────────────
css_checks = [
    ('cvScanLine',   'Home scan line animation'),
    ('cvRadarSpin',  'Home radar animation'),
    ('cvBarPulse',   'Home signal bar animation'),
    ('splashFade',   'Splash fade animation'),
    ('logoPulse',    'Logo pulse animation'),
]
for cls, label in css_checks:
    if cls in html:
        ok(f'CSS animation: {label}')
    else:
        warn(f'CSS animation missing: {label}')

# ─────────────────────────────────────────────────────────────────────────────
# 12. PERFORMANCE SECTION LABELS
# ─────────────────────────────────────────────────────────────────────────────
perf_checks = [
    ('PAST WEEK',      'Past week label'),
    ('PAST MONTH',     'Past month label'),
    ('ALL TIME',       'All time label'),
    ('BY SPORT',       'By sport label'),
    ('FUTURE SPORTS',  'Future sports placeholder'),
    ('DAILY SIGNALS',  'Daily Signals header'),
]
for text, label in perf_checks:
    if text in html:
        ok(f'Label present: {label}')
    else:
        warn(f'Label missing: {label}')

# ─────────────────────────────────────────────────────────────────────────────
# RESULTS
# ─────────────────────────────────────────────────────────────────────────────
total  = len(passed) + len(warnings) + len(errors)
print()
print(f'{BOLD}{"─"*60}{RST}')
print(f'{BOLD}CLAIRVOYANCE — Pre-push validation{RST}')
print(f'{"─"*60}')
print(f'  File: docs/app.html  ({len(html)//1024}KB, {html.count(chr(10))+1} lines)')
print(f'{"─"*60}')

if errors:
    print(f'\n{RED}{BOLD}  ERRORS ({len(errors)}) — PUSH BLOCKED{RST}')
    for e in errors:
        print(f'  {RED}  {e}{RST}')

if warnings:
    print(f'\n{YLW}{BOLD}  WARNINGS ({len(warnings)}){RST}')
    for w in warnings:
        print(f'  {YLW}  {w}{RST}')

print(f'\n{GRN}  PASSED: {len(passed)}/{total} checks{RST}')
print(f'{"─"*60}')

if errors:
    print(f'\n{RED}{BOLD}  PUSH BLOCKED — fix errors above before pushing{RST}\n')
    sys.exit(1)
elif warnings:
    print(f'\n{YLW}  Push allowed with warnings — review above{RST}\n')
    sys.exit(0)
else:
    print(f'\n{GRN}{BOLD}  All checks passed — safe to push{RST}\n')
    sys.exit(0)
