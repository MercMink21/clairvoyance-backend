# CLAIRVOYANCE ENGINE — Master Build Summary & Session Context
> Generated: June 8, 2026 | Comprehensive reference — supersedes all prior versions

---

## 1. Repository & Live URLs

| Property | Value |
|---|---|
| **GitHub Repo** | `MercMink21/clairvoyance-backend` |
| **Live URL** | `https://mercmink21.github.io/clairvoyance-backend/app.html` |
| **Root redirect** | `docs/index.html` → identical copy of `app.html` |
| **Custom domain** | `clairvoyanceengine.info` (Talos spam review flagged ~2026-05-31) |
| **GitHub Pages source** | `docs/` folder |
| **Latest commit** | `22caddb` — fix: correct RG 2026 ATP final |
| **Local repo path** | `/Users/reeseoliver/clairvoyance-backend/` |

**⚠️ ALWAYS link to `/app.html` directly** — never the root URL. Root just redirects. User confirmed 2026-06-03.

---

## 2. File Structure

```
docs/
  app.html          # 13,107 lines — full SPA, SOURCE OF TRUTH (HTML+CSS+JS)
  index.html        # IDENTICAL copy of app.html — always kept in sync
  data.json         # 817KB — live sports data (written by Python, fetched network-first)
  picks.json        # 63KB — permanent bet history (175 bets, 143W-29L)
  sw.js             # Service worker SELF-DESTRUCT (clears cache, unregisters on load)
  config.js         # API base URL detection (localhost vs GitHub Pages)
  card.png          # Social card image
scripts/
  clairvoyance_update.py  # 3,643 lines — Python data fetcher + GitHub pusher
  validate.py             # Pre-push validator (23 checks, auto-blocks bad pushes)
  run_update.sh           # Wrapper — use --push to auto-commit
  setup_cron.sh           # Installs cron jobs
data/
  bet_history.json  # Legacy (empty — picks.json is the authoritative store)
  bundle.json       # Internal data bundle
.git/hooks/
  pre-commit        # Runs validate.py on every commit (when app.html is staged)
  pre-push          # Runs validate.py on every push
```

---

## 3. Tech Stack

- **Frontend**: Vanilla JS/HTML/CSS — single file SPA, NO build step, NO npm, NO framework
- **Fonts**: Orbitron (`var(--orb)`), Share Tech Mono (`var(--mono)`), Exo 2
- **Backend**: Python 3 (`clairvoyance_update.py`) — runs via GitHub Actions
- **Hosting**: GitHub Pages (static, `docs/` folder)
- **Data refresh**: GitHub Actions (`manual-sync.yml`) triggered by ↻ SYNC button
- **No service worker**: `sw.js` self-destructs on every load (prevents caching issues)

---

## 4. Design System (CSS Tokens)

```css
--void: #010006     /* page background */
--nc:   #00f0ff     /* neon cyan — primary accent */
--hc:   #ff2090     /* hot pink — danger/loss */
--vc:   #bbff00     /* volt green — value picks */
--ic:   #6690ff     /* indigo — NHL/info */
--pc:   #f000ff     /* purple — NBA/picks */
--gc:   #ffdd00     /* gold — wins/champion */
--mc:   #ff7700     /* orange — tennis/warning */
--rc:   #00ffaa     /* seafoam — F1/special */
--orb:  'Orbitron', sans-serif
--mono: 'Share Tech Mono', monospace
```

**CSS utility classes**: `.card`, `.sh`, `.nb`, `.btn`, `.btn-p`, `.btn-o`, `.btn-sm`, `.tab`, `.act`, `.sa`, `.sg`, `.sgt`, `.spane`, `.fi`, `.pk`, `.pkt`, `.pkt2`, `.pkd`, `.pkb`, `.g2`, `.g3`, `.g4`, `.ct`, `.stat-val`, `.stat-lbl`, `.chip`

---

## 5. Sport Panes & Navigation

### Main Nav: `SS(sport)` — switch sport pane | `T(sport, tab)` — sub-tab | `setSub(sport, sub)` — sub-pane

| Pane ID | Nav Label | Sub-tabs | Sub-panes |
|---|---|---|---|
| `sp-home` | HOME | — | — |
| `sp-mlb` | BASEBALL | picks, today, games, schedule, props, parlay, nrfi, ranks, history, model, set | mlb, ncaa |
| `sp-nba` | BASKETBALL | picks, today, games, schedule, props, parlay, playoffs, stats, history, model, config | nba, wnba |
| `sp-hk` | HOCKEY | **picks, today, props, parlay, history, model, schedule, config, edge, goalies, puck** | nhl, pwhl, ncaah, khl, liiga, shl |
| `sp-fb` | FOOTBALL | picks, schedule, stats | nfl, cfb |
| `sp-ten` | TENNIS | picks, today, slams, schedule, h2h, rankings, compare, model, config | — |
| `sp-f1` | F1 | picks, today, schedule, standings, drivers, stats, model, config | — |
| `sp-ovr` | OVERALL | dash, history, adaptive, trends, clv, analytics, ats, teams, visuals, schedule, futures | — |
| `sp-analytics` | ANALYTICS | — | betanalytics, bethistory, bysport, byteam, mlb, nhl, nba, ncaa, fb, atsanalysis, trends, clvanalytics |
| `sp-fut` | FUTURES | nba, mlb, nhl, tennis | — |
| `sp-social` | SOCIAL | cards, monte, record | — |
| `sp-news` | NEWS | all, mlb, nba, nhl, injuries, trades | — |
| `sp-live` | LIVE | games, bets | — |

**⚠️ HOCKEY PROPS TAB**: Added June 2026 — `T('nhl','props')` nav button added. Tab was present in HTML but had no button. Now accessible.

---

## 6. Prediction Models

### MLB
- Monte Carlo (5K-8K sims) + Bayesian + ELO + Poisson runs model
- xFIP, wOBA, wRC+, BABIP, ISO from sabermetrics; NRFI probability model
- Ensemble: `ENS = {mc:.50, bay:.20, elo:.30}` (adjustable in CONFIG tab)
- Key functions: `mlbEns()`, `buildMLB()`, `renderMLBEnginePicks()`, `projectMLBScore()`

### NBA
- ELO (`NBA_ELO`), Monte Carlo (5K sims), BBRef advanced stats
- TS%, BPM, Net Rating, Pace, eFG%
- Ensemble: `NBA_ENS = {mc:.50, bay:.20, elo:.30}`
- Key functions: `nbaEns()`, `renderNBAPicks()`

### NHL
- xGF/60, Corsi, GSAx, MoneyPuck goalie data, HockeyViz
- Monte Carlo (Poisson 5K sims), PP%, PK%
- Ensemble: `NHL_ENS = {mc:.50, bay:.20, elo:.30}`
- Key functions: `nhlEns()`, `renderNHLPicks()`

### Tennis
- Surface ELO (clay/hard/grass/form), yELO
- TennisAbstract serve/return metrics, H2H, fatigue
- 5-factor composite ELO model
- Key functions: `tennisMatchWinProbFull()`, `renderTennisPicks()`

### F1
- Qualifying delta, constructor standings, pit stop strategy, DNF risk
- Key function: `renderF1Picks()`

### Pick Grade Thresholds
- **ELITE**: ≥67% win prob / EV ≥8%
- **LOCK**: 62–67% win prob / EV 4–8%
- **LEAN**: 55–62% win prob / EV 1–4%

---

## 7. Python Data Pipeline (`scripts/clairvoyance_update.py`)

**3,643 lines | 53 fetch functions**

Fetch functions cover: MLB scoreboard/standings/schedule/sabermetrics, NBA scoreboard/standings/playoff bracket/player stats, NHL today/standings/edge/moneypuck/hockeyviz, tennis ELO/yelo/odds/roland_garros/schedule, F1/analytics, Linemate props/trends/cheatsheet, NCAA baseball/WNBA/PWHL, news/injuries/weather/futures.

### data.json Top-Level Keys (24):
`generated, generatedMT, version, mlb, nba, nhl, ncaaBaseball, wnba, pwhl, mp, weather, tennis, futures, f1, linemate, bestBets, heroPicksForDay, bestOdds, settled, betHistory, overallStats, seededBets, news, injuries`

### GitHub Actions Schedules:
- **09:00, 15:00, 23:00 MT** — full refresh via `scheduled-refresh.yml`
- **16:00–23:00 MT** — live tracking every 2 min
- **Manual**: ↻ SYNC button (needs `ghp_` token with `workflow` scope)

---

## 8. Permanent Pick Storage — 3-Layer System

```
Layer 1: localStorage['preds']     — instant, in-browser
Layer 2: IndexedDB                 — survives most cache clears
Layer 3: docs/picks.json (GitHub)  — PERMANENT, cross-device, never lost
```

- `loadPicksFromGitHub()` — merges GitHub + localStorage on every load
- `savePicksToGitHub(picks)` — writes `docs/picks.json` via GitHub Contents API
- `syncPicksToGitHub()` — debounced 5s, fires after every `saveP()` call
- `seedBetHistory()` — IIFE, runs every load, strip+reinsert by ID (outcomes never stale)
- GitHub token: enter via **⚙ Sync Key** button (top header), needs `repo` scope

---

## 9. Current Pick Record (June 8, 2026)

**175 total | 143W – 29L – 3 pending | 83.1% win rate**

| Sport | Bets | W | L | Win% |
|---|---|---|---|---|
| NHL | 47 | 39 | 8 | 83% |
| MLB | 62 | 45 | 14 | 76% |
| NBA | 46 | 39 | 7 | 85% |
| TEN | 20 | 20 | 0 | 100% |

| Type | Count |
|---|---|
| ML | 140 |
| PROP | 33 |
| RL | 2 |

---

## 10. Seeded Bet History (114 entries in seedBetHistory IIFE)

Lives in `app.html`. Runs on every page load. Strip+reinsert by ID — outcomes never go stale.

Coverage: NHL RS 2025-26 (25 picks), NHL Playoffs 2026 (10 picks), MLB 2026 (24 picks), NBA Playoffs 2026 (15 picks), WCF Props SA vs OKC, NBA Finals G1 (9 props 8W/1L), NBA Finals G2 (9 props), SCF G1 VGK +1.5 WIN, SCF G2 CAR +118 WIN, Roland Garros WTA R1 (8 picks all WIN), WTA SF Andreeva +280 WIN, WTA Final Andreeva -350 WIN.

---

## 11. Current Sports State (June 8, 2026)

### NBA Finals: NYK Knicks vs SA Spurs
- **NYK leads 3-0** (or 2-1 pending G3 outcome — verify at session start)
- G1: SA won | G2: NYK won 105-104 | G3: NYK won (Jun 7)

### NHL Stanley Cup Finals: VGK vs CAR
- **Series tied 1-1** heading into G3 (Jun 6 result TBD)
- G1: VGK won 5-4 | G2: CAR won 4-3
- G4: June 8 @ PNC Arena Raleigh (TONIGHT)
- VGK home ice: G1, G2, G5, G7 | CAR home ice: G3, G4, G6

### Roland Garros 2026 — COMPLETE
- **WTA Champion**: Mirra Andreeva (RUS, seed 8) def. M.Chwalinska (POL, unseeded) 6-3, 6-2 — Jun 6
  - SF: Andreeva def. Sabalenka (1) 6-1, 6-3 (major upset)
  - QF: Andreeva def. Svitolina; Chwalinska def. Sakkari (upset)
- **ATP Champion**: Alexander Zverev (GER, seed 2) def. F.Cobolli (ITA, seed 10) — Jun 8
  - SF: Zverev def. Albot; Cobolli def. Mensik
  - QF: Zverev def. de Minaur; Cobolli def. Cerundolo; Mensik def. Bublik; Albot def. Fritz

### MLB: 2026 Regular Season active

---

## 12. Critical Architecture Rules — NON-NEGOTIABLE

1. **`app.html` is the SOURCE OF TRUTH** — Python `FE = ROOT / "docs" / "app.html"`. Always write both `app.html` AND `index.html`
2. **NEVER re-enable service worker** — caused weeks of blank page loops. `sw.js` self-destructs
3. **NEVER use agents (spawned sub-agents) for large edits** — introduce syntax errors. Use targeted Python scripts with string replacement
4. **ALWAYS validate syntax before pushing** — run `python3 scripts/validate.py` (also runs automatically via git hooks)
5. **`seedBetHistory()` IIFE must survive every push** — never remove it
6. **One `let LOCKED_PROPS`** — never re-declare
7. **One `const _origSaveP`** — saveP patched once only
8. **`renderHomePage()` + `endSplash()` must be in DOMContentLoaded init block**
9. **`#app` must never start with `opacity:0`**
10. **Always copy app.html → index.html** — they must be identical

### Template Literal Safety (CRITICAL — June 2026 lesson):
- **NEVER put `;` as the last char inside `${...}` template expressions**
- `color:${a ? b : c;}` — the `;` before `}` is a JavaScript `SyntaxError` that kills the ENTIRE script on parse → complete blank page
- Correct: `color:${a ? b : c}` (no semicolon inside)
- The pre-push validator check 23 now catches this class of bug automatically

---

## 13. Pre-Push Validator — 23 Checks

Runs on every commit/push via git hooks. Blocks push on any error.

| # | Check |
|---|---|
| 1 | Odd backtick count (unclosed template literal) |
| 2 | Brace `{` vs `}` mismatch |
| 3 | Duplicate `let LOCKED_PROPS` |
| 4 | Duplicate `const _origSaveP` |
| 5 | `serviceWorker.register` re-enabled |
| 6 | Required HTML elements missing (30 elements) |
| 7 | Required JS functions missing (19 functions) |
| 8 | Duplicate HTML IDs |
| 9–10 | Nav dropdowns inside JS strings |
| 11 | Critical render-target IDs present |
| 12 | `seedBetHistory()` IIFE present |
| 13 | `renderHomePage()` + `endSplash()` in DOMContentLoaded |
| 14 | `#app` does not start hidden |
| 15 | Removed elements stay removed |
| 16 | CSS animations present |
| 17 | `renderRGDraw()` — all called rounds handled in function |
| 18 | `T()` nav routing — all sport keys valid |
| 19 | Unguarded `getElementById` crash risks |
| 20 | Functions using bare `D` without local `const D=window.__CV_DATA` |
| 21 | Hardcoded `const TODAY=` date strings |
| 22 | Missing commas in `seedBetHistory` array entries |
| **23** | **Semicolons inside `${...}` template expressions (recursive TL parser)** |

---

## 14. All Features & Changes — This Session (June 3–8, 2026)

### Data Corrections:
- **Picks deduplication**: 6 NBA Finals G2 props were stored twice with `sport:'MLB'`. Duplicate entries removed; correct NBA-labeled versions retained
- **SA ML sport fix**: `sport:'MLB'` → `sport:'NBA'` for SA Spurs June 5 G2 bet
- **Build Summary corrections**: NBA Finals 2-0 NYK, SCF 1-1, record 130W-27L → 128W-23L (deduplicated)
- **Roland Garros ATP Final corrected**: Was Cobolli def. Zverev (wrong) → Zverev (2) def. Cobolli (10) ✓
- **Roland Garros WTA date**: Final date corrected from Jun 7 → Jun 6

### New Features Added:
1. **OVERALL TRENDS tab — 3 new panels**:
   - BY BET TYPE: Win%/units for ML, PROP, RL
   - BY TEAM: Bar chart of top teams to back vs teams to avoid (≥2 bets, sorted by win%)
   - PLAYER PROPS PERFORMANCE: Per-player win% with sport tag for all PROP bets

2. **Team matchup display standard**: All 18 display locations now show `AWAY at HOME` instead of `HOME vs AWAY`. Parsers, data keys, pitcher labels, and tennis "vs" untouched

3. **NHL HOCKEY → PROPS tab**: Nav button added. `T('nhl','props')` now accessible. Tab was present in HTML since prior build but had no button in nav bar

4. **NHL SCF Player Props** (`renderNHLSCFProps()`): 8 Linemate-sourced SCF G3 props displayed in PROPS tab with grades, model%, hit rate, basis, and LOCK buttons. Source: linemate.io/nhl + linemate.io/nhl/trends

5. **NHL Conference Finals removed**: `renderNHLCFCards()` replaced with compact SCF series status banner (VGK 1-1 CAR). Stale ECF/WCF series data removed from picks tab

6. **NHL SCF Preview updated**: `renderSCFPreview()` rewritten with:
   - Series 1-1 banner
   - G3 tonight card with betting lines + LOCK buttons
   - Full 7-game schedule with dates, venues, lines
   - Matchup matrix, outlook, playoff runs

7. **SCF G2 seeded bet**: Added CAR +118 ML WIN (CAR won 4-3 at T-Mobile, Jun 4)

8. **Roland Garros 2026 — full tournament update**:
   - Replaced stale 2025/pre-tournament data with actual 2026 results
   - New data constants: `RG_QF_MEN/WOMEN`, `RG_SF_MEN/WOMEN`, `RG_FINAL_MEN/WOMEN`
   - `renderRGDraw()` extended with: `tour==='men'&&round==='qf/sf/final'` (6 new handlers)
   - Round nav buttons: FINAL ✓, SF, QF, R3, R2, R1 for both ATP and WTA
   - Default French Open view: Final results tab
   - Futures updated: Sinner/Swiatek pre-tournament → Zverev WINNER / Andreeva WINNER
   - Andreeva ML WTA Final locked in picks.json (Jun 6, outcome WIN)

9. **MLB score projections removed**: `PROJ: X.X-X.X` lines removed from MLB matchup cards, picks detail section, and NRFI cards across 3 locations

### Critical Repairs:
1. **SyntaxError 1 — blank engine on load**: `;` inside template expression `${g.today?'var(--nc)':'var(--t3)');}` killed entire JS script on parse. Fixed by removing `;`. This was caused by a generator script writing Python heredoc into a JS template literal

2. **SyntaxError 2 — propAcc panel**: `${propAcc>=.55?'var(--nc)':'var(--hc)';};font-weight:700` had stray `;` inside `${}`. Fixed during validator check 23 development

3. **renderTrends() MLB fallback**: `p.sport||'MLB'` → `p.sport||'UNK'` — was mislabeling bets with missing sport field as MLB

4. **Validator check 23 added**: Recursive template literal expression parser. Catches semicolons as final char in `${...}` before `}`. Handles: strings, regex literals (`/pattern/`), line/block comments, nested template literals. Confirmed catches the original bug. Also found second real bug during development

---

## 15. Safe Edit Protocol

```python
# Always use this pattern when editing app.html:
import re

html = open('docs/app.html').read()

# Make your changes (string replacement, not direct line editing):
old = "exact string to replace"
new = "replacement string"
assert html.count(old) == 1, f"Pattern not unique: {html.count(old)}"
html = html.replace(old, new, 1)

# Validate BEFORE writing:
scripts = list(re.finditer(r'<script([^>]*)>([\s\S]*?)</script>', html))
main_js = [s.group(2) for s in scripts if len(s.group(2)) > 10000][0]
bt = main_js.count('`'); op = main_js.count('{'); cl = main_js.count('}')
lp = len(re.findall(r'\blet LOCKED_PROPS\b', main_js))
sp = len(re.findall(r'\bconst _origSaveP\b', main_js))
assert bt%2==0 and op==cl and lp==1 and sp==1
print(f"✓ BT:{bt} Braces:{op}/{cl} LP:{lp} SP:{sp}")

# Write both files:
open('docs/app.html','w').write(html)
open('docs/index.html','w').write(html)
```

Then run: `python3 scripts/validate.py` before committing.

---

## 16. Git Push Workflow

```bash
# Standard:
cd /Users/reeseoliver/clairvoyance-backend
git add docs/app.html docs/index.html docs/picks.json  # add what changed
git commit -m "feat/fix: description"
git push  # validator runs automatically, blocks on errors

# If remote has new commits (GitHub Actions auto-synced data):
git stash
git pull --rebase origin main
git stash pop
git push

# If data.json/bundle.json conflict (GitHub Actions vs local):
git checkout --theirs docs/data.json data/bundle.json data/best_bets.json docs/social_copy.json
git add docs/data.json data/bundle.json data/best_bets.json docs/social_copy.json
git rebase --continue  # or git push if already past rebase
```

---

## 17. Known Issues (Active)

| Issue | Notes |
|---|---|
| `write_social_copy` import error | Python imports function that doesn't exist in content_generator.py. Content generation skipped every run |
| `renderSCFPreview(el)` never called | Function exists, `nhl-scf-preview` div exists, but nothing invokes it |
| Football tab | NFL/CFB shows "COMING SOON" — no data source connected |
| Linemate Playwright | Only works on desktop. GitHub Actions uses `--no-linemate` flag |
| Custom domain | `clairvoyanceengine.info` — Talos spam review may need resolution |

---

## 18. Session Start Checklist

```bash
cd /Users/reeseoliver/clairvoyance-backend
git pull
python3 -c "
import re, json
html = open('docs/app.html').read()
scripts = list(re.finditer(r'<script([^>]*)>([\s\S]*?)</script>', html))
js = [s.group(2) for s in scripts if len(s.group(2)) > 10000][0]
bt = js.count('\x60'); op = js.count('{'); cl = js.count('}')
bets = json.load(open('docs/picks.json'))
w = sum(1 for b in bets if b.get('outcome')=='win')
l = sum(1 for b in bets if b.get('outcome')=='loss')
print(f'Lines: {html.count(chr(10))+1}')
print(f'BT:{bt}(ok={bt%2==0}) Braces:{op}/{cl}(ok={op==cl})')
print(f'Picks: {len(bets)} | {w}W-{l}L | {w/(w+l)*100:.1f}%')
"
# Live URL: https://mercmink21.github.io/clairvoyance-backend/app.html
```
