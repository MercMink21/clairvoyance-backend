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
    # ('sp-f1',              'F1 pane — REMOVED'),
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
    ('home-data-ts',         'Home data-as-of timestamp'),
    ('navd-ovr',             'Overall nav dropdown'),
    ('navd-mlb',             'Baseball nav dropdown'),
    ('navd-nba',             'Basketball nav dropdown'),
    ('navd-hk',              'Hockey nav dropdown'),
    ('navd-ten',             'Tennis nav dropdown'),
    # ('navd-f1',            'F1 nav dropdown — REMOVED'),
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
    ('ENGINE PERFORMANCE', 'Home: engine performance section'),
]
for text, label in perf_checks:
    if text in html:
        ok(f'Label present: {label}')
    else:
        warn(f'Label missing: {label}')

# ─────────────────────────────────────────────────────────────────────────────
# 13. EMPTY onclick HANDLERS — silent functional dead-ends
# ─────────────────────────────────────────────────────────────────────────────
empty_onclick = list(re.finditer(r'onclick=""', html_without_js))
if empty_onclick:
    for m in empty_onclick:
        ctx = html_without_js[max(0,m.start()-60):m.start()+40]
        err(f'Empty onclick="" at ~char {m.start()} — button does nothing: ...{ctx.strip()[:80]}...')
else:
    ok('No empty onclick="" handlers in HTML')

# ─────────────────────────────────────────────────────────────────────────────
# 14. JS getElementById CRASH DETECTION
#     Scans for getElementById calls that dereference the result WITHOUT a
#     null-guard — these WILL throw TypeError if the element is missing.
#     Pattern: getElementById('x').property  (no if/?.  protection)
#     Safely-guarded patterns are skipped:
#       const el=getElementById('x'); if(!el)return;
#       getElementById('x')?.value
#       const el=getElementById('x'); if(el)...
# ─────────────────────────────────────────────────────────────────────────────
# Find all unguarded direct property accesses on getElementById result
# e.g. getElementById('foo').textContent = ...  (will crash if null)
unguarded_deref = re.findall(
    r"getElementById\(['\"]([^'\"]+)['\"]\)\.(?!textContent\s*\?\?|closest)",
    main_js
)
# Filter out patterns that are actually safe (?.  or followed by a guard variable)
truly_unguarded = []
for match in re.finditer(
    r"getElementById\(['\"]([^'\"]+)['\"]\)\.",
    main_js
):
    eid = match.group(1)
    # Get surrounding context (100 chars before and after)
    start = max(0, match.start() - 80)
    ctx = main_js[start : match.end() + 60]
    # Skip if it's inside a conditional (if(el)..., const el=...; if(!el))
    # Skip if result is assigned to a variable first: const el = getElementById(...)
    if re.search(r'const\s+\w+\s*=\s*document\.getElementById', ctx):
        continue
    # Skip if followed by optional chaining
    if main_js[match.end()] == '?':
        continue
    # Skip known-safe patterns in context
    if any(p in ctx for p in ['if(!el)', 'if(el)', 'if (el)', '?.', 'if(!'+eid]):
        continue
    truly_unguarded.append((eid, ctx.strip()[:100]))

# Only flag if the element is ALSO absent from the HTML (otherwise it's fine)
html_ids_all = set(re.findall(r'\bid="([^"]+)"', html))  # includes JS-generated strings
truly_dangerous = [
    (eid, ctx) for eid, ctx in truly_unguarded
    if eid not in html_ids_all
    and f'id="{eid}"' not in main_js   # not dynamically created
    and f"id='{eid}'" not in main_js
]
if truly_dangerous:
    for eid, ctx in truly_dangerous[:8]:
        err(f'CRASH RISK: getElementById("{eid}").property with no null guard and element not in HTML: {ctx[:70]}')
    if len(truly_dangerous) > 8:
        err(f'...and {len(truly_dangerous)-8} more crash-risk getElementById calls')
else:
    ok(f'No unguarded getElementById crash risks found ({len(truly_unguarded)} checked, all elements present)')

# ─────────────────────────────────────────────────────────────────────────────
# 15. HTML INJECTED INTO JS STRINGS (the navd-in-template-literal bug class)
#     Checks that no block-level HTML tags appear inside JS template literals
#     in a way that would corrupt the JS string context.
# ─────────────────────────────────────────────────────────────────────────────
# Find all template literal contents in main_js and check for injected block HTML
# A navd-* div or other structural element inside a template literal is the bug
suspicious_in_js = re.findall(
    r'`[^`]*<div\s+id="navd-[^`]*`',
    main_js
)
if suspicious_in_js:
    err(f'NAV DROPDOWN DIVS FOUND INSIDE JS TEMPLATE LITERAL — HTML was injected into JS string ({len(suspicious_in_js)} occurrences)')
else:
    ok('No nav dropdown divs inside JS template literals')

# Also check that nav dropdowns appear AFTER the closing </script> tag
navd_in_html = html.find('id="navd-ovr"')
script_close  = html.rindex('</script>')
if navd_in_html > 0:
    if navd_in_html > script_close:
        ok('Nav dropdowns correctly placed after </script>')
    else:
        err(f'Nav dropdowns appear INSIDE script block (pos {navd_in_html} vs </script> at {script_close})')

# ─────────────────────────────────────────────────────────────────────────────
# 16. CRITICAL RENDER-TARGET IDs PRESENT
#     Checks that all IDs render functions write to actually exist.
# ─────────────────────────────────────────────────────────────────────────────
render_targets = [
    ('home-games',           'renderHomeBestBets: today\'s games grid'),
    ('home-locked',          'renderHomeLockedBets: locked picks tracker'),
    ('home-date-display',    'renderHomeBestBets: date display'),
    ('home-data-ts',         'loadRemoteData: data-as-of timestamp'),
    ('home-picks',           'renderHomePage: Daily Signals picks'),
    ('home-best-bets',       'renderHomeBestBets: remote picks'),
    ('home-engine-record',   'renderHomePage: engine record strip'),
    ('home-performance',     'renderHomePage: performance section'),
    ('home-yesterday-results','renderHomePage: yesterday results'),
]
for eid, desc in render_targets:
    if f'id="{eid}"' in html_without_js:
        ok(f'Render target present: #{eid}')
    else:
        err(f'MISSING RENDER TARGET: #{eid} ({desc})')

# ─────────────────────────────────────────────────────────────────────────────
# 17. renderRGDraw() ARGUMENT VALIDITY
#     Every renderRGDraw('tour','round') call in HTML must match a handled
#     (tour===... && round===...) branch in the function body.
#     NOTE: renderRGDraw uses heavy template literals which confuse simple
#     brace counters. We search from function start to its real terminator
#     (el.innerHTML=html followed by closing brace) to get the true body.
# ─────────────────────────────────────────────────────────────────────────────
rg_draw_fn_start = main_js.find('function renderRGDraw(')
if rg_draw_fn_start != -1:
    # Find the real function end: el.innerHTML=html;\n} right after the last else-if
    # Search forward from function start for the terminating pattern
    rg_search_window = main_js[rg_draw_fn_start:rg_draw_fn_start + 30000]
    rg_term = re.search(r'el\.innerHTML=html;\s*\n\s*\}', rg_search_window)
    if rg_term:
        rg_fn = rg_search_window[:rg_term.end()]
    else:
        rg_fn = rg_search_window  # fallback: search whole window
    # Extract all handled (tour, round) pairs
    handled_pairs = set(re.findall(r"tour==='(\w+)'&&round==='(\w+)'", rg_fn))
    # Extract all calls from HTML
    called_pairs  = set(re.findall(r"renderRGDraw\('(\w+)','(\w+)'\)", html))
    bad_calls = called_pairs - handled_pairs
    if bad_calls:
        for tour, rnd in sorted(bad_calls):
            err(f"renderRGDraw('{tour}','{rnd}') called but NOT handled in function — silently renders blank")
    else:
        ok(f"All renderRGDraw() calls use handled round codes ({len(called_pairs)} calls, {len(handled_pairs)} handlers)")
else:
    warn('renderRGDraw function not found — skipping argument validity check')

# ─────────────────────────────────────────────────────────────────────────────
# 18. T() NAV ROUTING ARGUMENT VALIDITY
#     T(sport, tab) routes sub-tabs inside a sport pane via saMap/navMap.
#     Valid sports are those defined in T()'s saMap — not sp-{sport} IDs.
#     Guards against dead routing links that appear to work but show nothing.
# ─────────────────────────────────────────────────────────────────────────────
t_fn_idx = main_js.find('function T(sport,tabId)')
if t_fn_idx != -1:
    t_fn_window = main_js[t_fn_idx:t_fn_idx+500]
    # Extract sports from saMap: nhl:'nhl-sa', nba:'nba-sa', ...
    sa_map_match = re.search(r'saMap=\{([^}]+)\}', t_fn_window)
    valid_t_sports = set(['mlb'])  # mlb is the fallback default
    if sa_map_match:
        valid_t_sports |= set(re.findall(r"(\w+):'[^']+\-sa'", sa_map_match.group(1)))
    t_calls_html = re.findall(r"T\('([^']+)','([^']+)'\)", html_without_js)
    bad_t_calls = [(s, t) for s, t in t_calls_html if s not in valid_t_sports]
    if bad_t_calls:
        for sport, tab in bad_t_calls[:5]:
            err(f"T('{sport}','{tab}') — sport '{sport}' not in T() saMap, routing will fail silently")
        if len(bad_t_calls) > 5:
            err(f"...and {len(bad_t_calls)-5} more invalid T() calls")
    else:
        ok(f"All T() nav calls use valid saMap sport keys ({len(t_calls_html)} calls, {len(valid_t_sports)} valid sports)")
else:
    warn('T() function not found — skipping nav routing check')

# ─────────────────────────────────────────────────────────────────────────────
# 20. FUNCTIONS USING BARE D WITHOUT LOCAL DEFINITION
#     D (window.__CV_DATA) is never a global. Any function that accesses
#     D.xxx without first declaring `const D=window.__CV_DATA||{};` will
#     silently read undefined, causing empty sections — the core recurring
#     blank-screen bug. Block any regression of this class.
# ─────────────────────────────────────────────────────────────────────────────
bare_D_offenders = []
for fn_match in re.finditer(r'function\s+(\w+)\s*\([^)]*\)\s*\{', main_js):
    fn_name = fn_match.group(1)
    fn_start = fn_match.start()
    depth = 0; fn_end = fn_start
    for i, c in enumerate(main_js[fn_start:], fn_start):
        if c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: fn_end = i+1; break
    fn_body = main_js[fn_start:fn_end]
    if len(fn_body) < 80: continue
    has_bare_D  = bool(re.search(r'\bD[\.\?\|&]', fn_body))
    has_local_D = bool(re.search(r'(const|let|var)\s+D\s*=', fn_body))
    if has_bare_D and not has_local_D:
        bare_D_offenders.append(fn_name)

if bare_D_offenders:
    for fn in bare_D_offenders:
        err(f"Function {fn}() uses bare D without 'const D=window.__CV_DATA||{{}}' — will silently show blank content")
else:
    ok(f'No functions use bare D without local definition (checked all named functions)')

# ─────────────────────────────────────────────────────────────────────────────
# 21. HARDCODED DATE STRINGS IN LOGIC PATHS
#     Dates hardcoded as `const TODAY='YYYY-MM-DD'` go stale immediately.
#     Must use today() for any date comparison in live render functions.
# ─────────────────────────────────────────────────────────────────────────────
hardcoded_todays = re.findall(r"const TODAY\s*=\s*'(\d{4}-\d{2}-\d{2})'", main_js)
if hardcoded_todays:
    for d in hardcoded_todays:
        err(f"Hardcoded const TODAY='{d}' — will go stale; use today() instead")
else:
    ok('No hardcoded const TODAY= date strings found')

# ─────────────────────────────────────────────────────────────────────────────
# 22. MISSING COMMA BETWEEN seedBetHistory ARRAY ENTRIES
#     A } followed by { without a comma is a SyntaxError that kills the entire
#     script. This is the #1 recurring fatal bug. Detect it before every push.
# ─────────────────────────────────────────────────────────────────────────────
seed_idx = main_js.find('(function seedBetHistory(')
if seed_idx > -1:
    seed_end = seed_idx
    depth = 0
    for i, c in enumerate(main_js[seed_idx:], seed_idx):
        if c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: seed_end = i + 1; break
    seed_body = main_js[seed_idx:seed_end]
    # Find closing } followed by optional whitespace/comments then opening { without comma
    bad = re.findall(r'\}[ \t]*(?:\n[ \t]*//[^\n]*)*\n[ \t]*\{', seed_body)
    if bad:
        err(f"seedBetHistory has {len(bad)} missing comma(s) between array entries — causes SyntaxError blank engine")
    else:
        ok('seedBetHistory array entries all separated by commas')
else:
    err('seedBetHistory IIFE not found in script')

# ─────────────────────────────────────────────────────────────────────────────
# 23. TEMPLATE LITERAL EXPRESSION SYNTAX — TRAILING SEMICOLON CHECK
#
#     The exact bug that broke the engine: a semicolon was the last meaningful
#     character inside a ${...} expression before its closing }:
#
#         color:${g.done ? 'var(--gc)' : 'var(--t3)';}   ← SyntaxError
#
#     JavaScript requires ${Expression} — a semicolon is not part of any
#     Expression production, so the browser JS parser throws SyntaxError
#     before a single line runs.
#
#     Detection strategy (no full JS parser needed):
#       1. Extract all ${...} expression bodies using a balanced-brace walk
#          that skips over JS strings, comments, and nested template literals.
#       2. Strip the extracted body of its string literals and comments so
#          semicolons inside string values (e.g. 'color:red;font-size:12px')
#          are not counted.
#       3. Flag if the last non-whitespace character is ';'.
#
#     This catches: ${expr;} ${a?b:c;} ${fn();} — and nothing else.
# ─────────────────────────────────────────────────────────────────────────────
REGEX_PRECEDE = set('=([,;!&|?:{+->~^%')  # chars after which / starts a regex literal

def skip_string(src, pos, quote):
    pos += 1
    while pos < len(src):
        if src[pos] == '\\': pos += 2; continue
        if src[pos] == quote: return pos + 1
        pos += 1
    return pos

def skip_regex(src, pos):
    """Skip a JS regex literal starting at pos (the opening /)."""
    pos += 1
    while pos < len(src):
        if src[pos] == '\\': pos += 2; continue
        if src[pos] == '[':
            pos += 1
            while pos < len(src):
                if src[pos] == '\\': pos += 2; continue
                if src[pos] == ']': pos += 1; break
                pos += 1
            continue
        if src[pos] == '/': pos += 1; break
        pos += 1
    while pos < len(src) and src[pos].isalpha(): pos += 1
    return pos

def extract_template_expressions(js):
    """
    Yield (start_pos, expr_body) for every ${...} in js,
    walking balanced braces and skipping strings/comments/nested TL/regex.
    """

    def walk_template(src, pos, results):
        """
        Walk a template literal body (pos is AFTER the opening backtick).
        Recursively extracts all ${...} expression bodies into results list.
        Returns position after the closing backtick.
        """
        n = len(src)
        while pos < n:
            c = src[pos]
            if c == '\\': pos += 2; continue
            if c == '`': return pos + 1   # end of this template literal
            if c == '$' and pos+1 < n and src[pos+1] == '{':
                # Extract this expression
                body, end_j = skip_expr_body(src, pos+2, results)
                results.append((pos+2, body))
                pos = end_j + 1; continue
            pos += 1
        return pos

    def skip_expr_body(src, start, results=None):
        """
        Walk from start, find the matching } for the ${.
        If results is not None, recursively collect nested template expressions too.
        Returns (body, end_pos).
        """
        depth = 1; j = start; n = len(src); last_non_ws = ''
        while j < n and depth > 0:
            c = src[j]
            if c == '/' and j+1 < n and src[j+1] == '/':
                end = src.find('\n', j); j = end+1 if end != -1 else n; continue
            if c == '/' and j+1 < n and src[j+1] == '*':
                end = src.find('*/', j+2); j = end+2 if end != -1 else n; continue
            if c == '/' and j+1 < n and src[j+1] not in ('/', '*'):
                if last_non_ws in REGEX_PRECEDE or not last_non_ws:
                    j = skip_regex(src, j); continue
            if c in ('"', "'"):
                j = skip_string(src, j, c); last_non_ws = ' '; continue
            if c == '`':
                # Nested template literal — recurse to collect inner expressions
                if results is not None:
                    j = walk_template(src, j+1, results)
                else:
                    j += 1
                    while j < n:
                        if src[j] == '\\': j += 2; continue
                        if src[j] == '`': j += 1; break
                        if src[j] == '$' and j+1 < n and src[j+1] == '{':
                            j += 2; nd = 1
                            while j < n and nd > 0:
                                if src[j] == '{': nd += 1
                                elif src[j] == '}': nd -= 1
                                j += 1
                            continue
                        j += 1
                last_non_ws = ' '; continue
            if c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0: break
            if not c.isspace(): last_non_ws = c
            j += 1
        return src[start:j], j

    i = 0; n = len(js); results = []
    while i < n - 1:
        if js[i] == '/' and js[i+1] == '/':
            end = js.find('\n', i); i = end+1 if end != -1 else n; continue
        if js[i] == '/' and js[i+1] == '*':
            end = js.find('*/', i+2); i = end+2 if end != -1 else n; continue
        if js[i] in ('"', "'"):
            i = skip_string(js, i, js[i]); continue
        # Top-level template literal — walk it recursively
        if js[i] == '`':
            i = walk_template(js, i+1, results)
            for pos, body in results:
                yield (pos, body)
            results.clear()
            continue
        # Direct ${...} outside template literal (unusual but handle it)
        if js[i] == '$' and js[i+1] == '{':
            body, end_j = skip_expr_body(js, i+2, results)
            yield (i+2, body)
            for pos, body2 in results:
                yield (pos, body2)
            results.clear()
            i = end_j + 1; continue
        i += 1

def strip_strings_and_comments(expr):
    """Remove string literals, regex literals, and comments from a JS expression body."""
    out = []; i = 0; n = len(expr); last_non_ws = ''
    while i < n:
        c = expr[i]
        if c == '/' and i+1 < n and expr[i+1] == '/':
            end = expr.find('\n', i); i = end+1 if end != -1 else n; continue
        if c == '/' and i+1 < n and expr[i+1] == '*':
            end = expr.find('*/', i+2); i = end+2 if end != -1 else n; continue
        # Regex literal: / following an operator char
        if c == '/' and i+1 < n and expr[i+1] not in ('/', '*'):
            if last_non_ws in REGEX_PRECEDE or not last_non_ws:
                i = skip_regex(expr, i); out.append(' '); last_non_ws = ' '; continue
        if c in ('"', "'", '`'):
            q = c; i += 1
            while i < n:
                if expr[i] == '\\': i += 2; continue
                if expr[i] == q:    i += 1; break
                i += 1
            out.append(' ')  # placeholder
            last_non_ws = ' '; continue
        out.append(c)
        if not c.isspace(): last_non_ws = c
        i += 1
    return ''.join(out)

tl_issues = []
for start_pos, body in extract_template_expressions(main_js):
    stripped = strip_strings_and_comments(body).rstrip()
    if stripped.endswith(';'):
        line_no = main_js[:start_pos].count('\n') + 1
        tl_issues.append((line_no, body.strip()[:120]))

if tl_issues:
    for line_no, body in tl_issues[:6]:
        err(f"TEMPLATE LITERAL SYNTAX ERROR at line ~{line_no}: "
            f"semicolon is last char in ${{...}} expression — SyntaxError kills entire script\n"
            f"          Expression: ${{ {body} }}")
    if len(tl_issues) > 6:
        err(f"...and {len(tl_issues)-6} more trailing-semicolon template expressions")
else:
    ok("Template literal expressions: no trailing semicolons inside ${{...}} (would be SyntaxError)")

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
