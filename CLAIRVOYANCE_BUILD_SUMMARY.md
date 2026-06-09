# CLAIRVOYANCE ENGINE — Master Build Summary & Session Context
> Generated: June 8, 2026 (Session 2) | Supersedes all prior versions

---

## 1. Repository & Live URLs

| Property | Value |
|---|---|
| **GitHub Repo** | `MercMink21/clairvoyance-backend` |
| **Live URL** | `https://mercmink21.github.io/clairvoyance-backend/app.html` |
| **Root redirect** | `docs/index.html` → identical copy of `app.html` |
| **Custom domain** | `clairvoyanceengine.info` (Talos spam review flagged ~2026-05-31) |
| **GitHub Pages source** | `docs/` folder |
| **Latest commit** | `7c425dc` — home tab live ticker + sport records with ML/PROP/RL sub-rows |
| **Local repo path** | `/Users/reeseoliver/clairvoyance-backend/` |

**⚠️ ALWAYS link to `/app.html` directly** — never the root URL.

---

## 2. File Structure

```
docs/
  app.html          # 13,110 lines — full SPA, SOURCE OF TRUTH (HTML+CSS+JS)
  index.html        # IDENTICAL copy of app.html — always kept in sync
  data.json         # 817KB — live sports data (written by Python, network-first)
  picks.json        # 161KB — permanent bet history (203 bets, 149W-31L-23P)
  live_data.json    # Live in-game scores (MLB/NBA/NHL/Tennis, refreshes ~45s)
  sw.js             # Service worker SELF-DESTRUCT (clears cache, unregisters)
  config.js         # API base URL detection (localhost vs GitHub Pages)
  card.png          # Social card image
scripts/
  clairvoyance_update.py  # 3,643 lines — Python data fetcher + GitHub pusher
  validate.py             # Pre-push validator (94 checks, auto-blocks bad pushes)
  run_update.sh           # Wrapper — use --push to auto-commit
  setup_cron.sh           # Installs cron jobs
data/
  bundle.json       # Internal data bundle
CLAIRVOYANCE_BUILD_SUMMARY.md     # This file
CLAIRVOYANCE_SESSION_CONTEXT.json # Machine-readable session state
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
--hc:   #ff2090     /* hot pink — danger/loss / MLB */
--vc:   #bbff00     /* volt green — value picks */
--ic:   #6690ff     /* indigo — NHL/info */
--pc:   #f000ff     /* purple — NBA/picks */
--gc:   #ffdd00     /* gold — wins/champion */
--mc:   #ff7700     /* orange — tennis/warning */
--rc:   #00ffaa     /* seafoam — special */
--orb:  'Orbitron', sans-serif
--mono: 'Share Tech Mono', monospace
```

**CSS utility classes**: `.card`, `.sh`, `.nb`, `.btn`, `.btn-p`, `.btn-o`, `.btn-sm`, `.tab`, `.act`, `.sa`, `.sg`, `.sgt`, `.spane`, `.fi`, `.pk`, `.pkt`, `.pkt2`, `.pkd`, `.pkb`, `.g2`, `.g3`, `.g4`, `.ct`, `.stat-val`, `.stat-lbl`, `.chip`

---

## 5. Sport Panes & Navigation

### Main Nav: `SS(sport)` | Sub-tab: `T(sport, tab)` | Sub-pane: `setSub(sport, sub)`

| Pane ID | Nav Label | Sub-tabs | Sub-panes |
|---|---|---|---|
| `sp-home` | HOME | — | — |
| `sp-mlb` | BASEBALL | picks, today, games, schedule, props, parlay, nrfi, ranks, history, model, set | mlb *(NCAA removed)* |
| `sp-nba` | BASKETBALL | picks, today, games, schedule, props, parlay, playoffs, stats, history, model, config | nba, wnba |
| `sp-hk` | HOCKEY | picks, today, props, parlay, history, model, schedule, config, edge, goalies, puck | nhl, pwhl, ncaah, khl, liiga, shl |
| `sp-fb` | FOOTBALL | picks, schedule, stats | nfl, cfb |
| `sp-ten` | TENNIS | picks, today, slams, schedule, h2h, rankings, compare, model, config | — |
| `sp-ovr` | OVERALL | dash, history, adaptive, trends, clv, analytics, ats, teams, visuals, schedule, futures | — |
| `sp-analytics` | ANALYTICS | — | betanalytics, bethistory, bysport, byteam, mlb, nhl, nba, ncaa, fb, atsanalysis, trends, clvanalytics |
| `sp-fut` | FUTURES | nba, mlb, nhl, tennis | — |
| `sp-social` | SOCIAL | cards, monte, record | — |
| `sp-news` | NEWS | all, mlb, nba, nhl, injuries, trades | — |
| `sp-live` | LIVE | games, bets | — |

**⚠️ REMOVED THIS SESSION**: F1 tab (`sp-f1`, `navd-f1`, `mn6`) — fully deleted
**⚠️ REMOVED THIS SESSION**: NCAA sub-tab from Baseball (`setSub('mlb','ncaa')` button removed)

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

### Pick Grade Thresholds
- **ELITE**: ≥67% win prob / EV ≥8%
- **LOCK**: 62–67% win prob / EV 4–8%
- **LEAN**: 55–62% win prob / EV 1–4%
- **SKIP**: explicit model flag — no edge / negative EV

---

## 7. Python Data Pipeline (`scripts/clairvoyance_update.py`)

**3,643 lines | 53 fetch functions**

Fetch functions cover: MLB scoreboard/standings/schedule/sabermetrics, NBA scoreboard/standings/playoff bracket/player stats, NHL today/standings/edge/moneypuck/hockeyviz, tennis ELO/yelo/odds/roland_garros/schedule, Linemate props/trends/cheatsheet, NCAA baseball/WNBA/PWHL, news/injuries/weather/futures.

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

**203 total | 149W – 31L – 23 pending | 82.8% win rate**

| Sport | Bets | W | L | P | Win% |
|---|---|---|---|---|---|
| MLB | 75 | 47 | 16 | 12 | 75% |
| NBA | 57 | 39 | 7 | 11 | 85% |
| NHL | 47 | 39 | 8 | 0 | 83% |
| TEN | 24 | 24 | 0 | 0 | 100% |

**23 pending**: NBA Finals G3 props (10 new Linemate lines + 7 engine locks + SA ML + others), MLB tonight

---

## 10. Seeded Bet History (seedBetHistory IIFE)

Lives in `app.html`. Runs on every page load. Strip+reinsert by ID.

**Coverage** (in order):
- NHL RS 2025-26: 25 picks
- NHL Playoffs 2026 (R1/R2/WCF/ECF/SCF G1-G2): 12 picks
- NBA Playoffs 2026 (R1 through WCF): 15 picks
- WCF Props: SA vs OKC (various)
- NBA Finals G1 (June 3): 9 props — 7W/2L
- NBA Finals G2 (June 5, NYK won 105-104): 8 props — 6W/2L
- **NBA Finals G3 (June 8, pending)**: 10 props from Linemate screenshots
- SCF G1 VGK +1.5 WIN, SCF G2 CAR +118 WIN
- Roland Garros 2026: WTA R1 (8 picks all WIN), WTA QF, WTA SF Andreeva +280 WIN, WTA Final Andreeva -350 WIN

---

## 11. Current Sports State (June 8, 2026)

### NBA Finals: NYK Knicks vs SA Spurs
- **NYK leads 2-0** — won G1 and G2 on the road in San Antonio
- G1 (June 3 @ SA): NYK WIN — Brunson 30pts/2ast, Wemby 26pts/12reb/3blk
- G2 (June 5 @ SA): NYK WIN 105-104 — Brunson 28+pts/6+ast, Wemby 26+pts/10.5+reb/3+blk
- **G3 TONIGHT (June 8 @ MSG)** — SA 19, NYK 9, Q1 (6:49 remaining at last check)
- G4: June 10 @ MSG | G5: June 12 @ SA | G6: June 14 @ MSG | G7: June 16 @ SA (if needed)

### NHL Stanley Cup Finals: VGK vs CAR
- **VGK leads 2-1**
- G1: VGK 5–4 WIN | G2: CAR 4–3 WIN | G3: VGK WIN (on road at PNC)
- **G4 TOMORROW (June 9 @ PNC Arena Raleigh)** — CAR must win to stay alive
- Series lines: CAR -125 / VGK +105
- VGK home ice: G1, G2, G5, G7 | CAR home ice: G3, G4, G6

### Roland Garros 2026 — COMPLETE
- **WTA Champion**: Mirra Andreeva (RUS, seed 8) def. M.Chwalinska 6-3, 6-2 — Jun 6
- **ATP Champion**: Alexander Zverev (GER, seed 2) def. F.Cobolli (ITA, seed 10) — Jun 8
- All futures settled: Zverev WINNER ✓ / Andreeva WINNER ✓

### MLB: 2026 Regular Season active
- Live games tonight: multiple games in progress (see live_data.json)

---

## 12. NBA Finals G3 Props — Full Linemate Analysis (June 8)

**Lines from Linemate.io/nba screenshots:**

| Prop | Line | Book Line | Model | Grade |
|---|---|---|---|---|
| De'Aaron Fox PTS+REB+AST | OVER 22.5 | Linemate | 72% | **LOCK** |
| De'Aaron Fox PTS+REB+AST | OVER 19.5 | Alt line | 78% | **LOCK** |
| KAT REB | OVER 10.5 | Linemate ✓ | 67% | **LOCK** |
| KAT PTS+REB+AST | OVER 29.5 | Linemate | 70% | **LOCK** |
| Brunson PTS | OVER 24.5 | Linemate | 75% | **LOCK** |
| Brunson PTS | OVER 26.5 | Alt line | 68% | **LOCK** |
| Brunson PTS | OVER 28.5 | Alt line | 62% | **LEAN** |
| Wemby PTS | OVER 26.5 | Linemate | 58% | **LEAN** |
| Wemby PTS | OVER 25.5 | Alt line | 64% | **LEAN** |
| OG Anunoby PTS | OVER 12.5 | Linemate | 72% | **LOCK** |
| Wemby PTS+AST | OVER 29.5 | Engine | 56% | **LEAN** |
| Wemby BLK | OVER 2.5 | Engine | 67% | **LOCK** |
| Brunson UNDER AST | UNDER 6 | Engine | 55% | **LEAN** |
| Dylan Harper PTS+REB+AST | OVER 19.5 | Linemate | 55% | **LEAN** |
| OG Anunoby PTS | OVER 14.5 | Alt line | 63% | **LEAN** |
| SA ML | +135 | Engine | — | Pending |

All seeded as pending in both picks.json and seedBetHistory IIFE.

---

## 13. Home Page — Current Structure

```
sp-home
  ├── ● LIVE GAMES ticker        (home-live-games, reads window.__CV_LIVE)
  │   • MLB: inning + half + outs
  │   • NBA: quarter + clock
  │   • NHL: period + clock (OT/SO labels)
  │   • Updates every 45s from live_data.json via loadLiveData()
  │
  ├── // ENGINE RECORD           (home-engine-record)
  │   • 4 cells: YESTERDAY · ROLLING 7D · LAST 30D · ALL TIME
  │   • Each shows: W-L · win% · net units
  │
  ├── // RECORD BY SPORT         (home-performance)
  │   • Collapsible row per sport (tap to expand/collapse)
  │   • Header: sport name + W-L + win% + progress bar
  │   • Sub-rows: ML / PROP / SPREAD — each with W-L, win%, units
  │
  ├── Utility buttons            (EXPORT JSON · SYNC EXPORT · NOTIFS · SYNC IMPORT)
  └── Hidden stubs               (home-picks, home-best-bets, etc. — keep for JS compat)
```

---

## 14. OVERALL Tab — ALL BETS Enhancement

**Pending bets section** now pinned to the TOP of the ALL BETS tab:
- Rendered BEFORE any sport/date filter logic runs
- Shows ALL pending bets regardless of active filter state
- Cyan header: `⏳ PENDING BETS — N`
- Each entry shows: sport badge · matchup · betOn · ml · WIN/LOSS settle buttons
- `recR()` + `setTimeout(renderOverallHistory, 400)` for instant settle-and-refresh

---

## 15. Validator — 94 Checks

Pre-push validator runs on every commit/push via git hooks.

**Notable changes this session:**
- Check for `DAILY SIGNALS` → replaced with `RECORD BY SPORT`
- F1 pane/navd-f1 checks → commented out (elements removed)
- All 94 checks pass on current build

---

## 16. Critical Architecture Rules — NON-NEGOTIABLE

1. **`app.html` is the SOURCE OF TRUTH** — Python `FE = ROOT / "docs" / "app.html"`. Always write both `app.html` AND `index.html`
2. **NEVER re-enable service worker** — caused weeks of blank page loops. `sw.js` self-destructs
3. **NEVER use agents for large edits** — introduce syntax errors. Use targeted Python scripts with string replacement
4. **ALWAYS validate syntax before pushing** — run `python3 scripts/validate.py` (also runs automatically via git hooks)
5. **`seedBetHistory()` IIFE must survive every push** — never remove it
6. **One `let LOCKED_PROPS`** — never re-declare
7. **One `const _origSaveP`** — saveP patched once only
8. **`renderHomePage()` + `endSplash()` must be in DOMContentLoaded init block**
9. **`#app` must never start with `opacity:0`**
10. **Always copy app.html → index.html** — they must be identical

### Template Literal Safety (CRITICAL):
- **NEVER put `;` as the last char inside `${...}` template expressions**
- `color:${a ? b : c;}` → the `;` before `}` is a JavaScript `SyntaxError` that kills the ENTIRE script
- Correct: `color:${a ? b : c}` (no semicolon inside)
- Validator check 23 catches this class of bug automatically

---

## 17. Safe Edit Protocol

```python
html = open('docs/app.html').read()
old = "exact string to replace"
new = "replacement string"
assert html.count(old) == 1, f"Pattern not unique: {html.count(old)}"
html = html.replace(old, new, 1)

# Validate:
import re
scripts = list(re.finditer(r'<script([^>]*)>([\s\S]*?)</script>', html))
js = [s.group(2) for s in scripts if len(s.group(2)) > 10000][0]
bt = js.count('`'); op = js.count('{'); cl = js.count('}')
assert bt%2==0 and op==cl
assert len(re.findall(r'\blet LOCKED_PROPS\b', js)) == 1
assert len(re.findall(r'\bconst _origSaveP\b', js)) == 1

open('docs/app.html','w').write(html)
open('docs/index.html','w').write(html)
```

Then: `python3 scripts/validate.py`

---

## 18. Git Push Workflow

```bash
cd /Users/reeseoliver/clairvoyance-backend
git add docs/app.html docs/index.html docs/picks.json
git commit -m "feat/fix: description"
git stash && git pull --rebase origin main && git stash pop && git push
# On data.json conflict: git checkout --theirs docs/data.json && git add docs/data.json && git rebase --continue
```

---

## 19. All Features & Changes — This Session (June 8, 2026)

### Series State Updates:
- **NHL SCF**: Updated from "Series tied 1-1" → "VGK leads 2-1"
  - G3 result card added (VGK WIN), G4 preview card for tomorrow June 9
  - Schedule updated: G3 done, G4 TOMORROW, G5-G7 dates shifted
  - Lock buttons updated to June 9 dates
- **NBA Finals**: Updated from stale pre-series → "NYK leads 2-0"
  - G3 preview card added (NYK -160 / SA +135, tonight June 8 @ MSG)
  - SA playoff run entry added: `FINALS: DOWN 0-2`
  - NYK playoff run entry added: `FINALS: LEADS 2-0`
  - NYK record updated to 10-0

### NBA Finals G3 Props (Full Linemate Analysis):
- `NBA_PROPS_DATA` completely rewritten with G3 lines from Linemate screenshots
- Lines documented from 3 image screenshots (different books)
- New grade system: ELITE > LOCK > LEAN > SKIP (replacing old GOOD/FAIR/FADE)
- Banner updated: "G3 TONIGHT · SA at NYK · MSG · NYK LEADS 2-0"
- Date header updated: "FINALS G3 · Jun 8 · 8:30 PM ET @ MSG · SA +135"
- Stale WCF G7 injury banner (Jalen Williams) removed
- Both `renderNBAFinalsProps` and `renderNBAProps` grade systems updated

### Seeded G3 Props:
- 10 new pending bets added to both `picks.json` and `seedBetHistory` IIFE:
  - Wemby 26.5/25.5 PTS, Fox 22.5/19.5 PRA, KAT 29.5 PRA, Harper 19.5 PRA
  - Brunson 24.5/26.5/28.5 PTS, OG 12.5 PTS
- All seeded with `outcome:'pending'`, `date:'2026-06-08'`, `lockedAt:1749340800000`

### Home Page Overhaul:
- **Removed**: Daily Signals section (WP/EV explanation, pulsing header, 2-col pick grid)
- **Added**: `renderHomeLiveGames()` — live game ticker at top
  - Reads from `window.__CV_LIVE` (live_data.json, updated every 45s)
  - MLB: shows inning + half + outs (e.g. "Bot 8th · 1 out")
  - NBA: shows quarter + clock (e.g. "Q1 6:49")
  - NHL: shows period/OT/SO + clock (e.g. "P2 14:22")
  - Leading team name bolds dynamically
  - Hides entirely when no live games
  - Also called from `loadLiveData()` for real-time updates
- **Enhanced**: Engine record — YESTERDAY / ROLLING 7D / LAST 30D / ALL TIME
- **Enhanced**: By-sport records — collapsible rows with ML/PROP/SPREAD sub-sections
  - Each sub-row shows W-L, win%, net units for that bet type

### OVERALL ALL BETS Tab:
- Pending bets section pinned above all filters — always visible
- Shows ALL pending bets regardless of sport/date filter state
- Cyan banner `⏳ PENDING BETS — N` with WIN/LOSS settle buttons inline

### Tab Removals:
- **F1 tab fully removed**: `sp-f1` pane, `navd-f1` dropdown, F1 top nav button, `mn6` mobile nav, CSS selectors (`#mn6`), JS references (`mn6` variable, `s==='f1'?'mn6'` routing)
- **NCAA sub-tab removed** from Baseball: `setSub('mlb','ncaa')` button removed
- Validator updated to reflect both removals (94 checks now, was 96)

### Roland Garros 2026:
- ATP Final corrected: Zverev (2) def. Cobolli (10) ✓ (was wrong way around)
- WTA Final date corrected: Jun 6 (was Jun 7)

---

## 20. Known Issues (Active)

| Issue | Notes |
|---|---|
| `write_social_copy` import error | Python imports function that doesn't exist in content_generator.py. Content generation skipped every run |
| Football tab | NFL/CFB shows "COMING SOON" — no data source connected |
| Linemate Playwright | Only works on desktop. GitHub Actions uses `--no-linemate` flag |
| Custom domain | `clairvoyanceengine.info` — Talos spam review may need resolution |
| G3 props pending | 23 pending bets — need outcome updates after tonight's game |

---

## 21. Session Start Checklist

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
p = sum(1 for b in bets if b.get('outcome') not in ('win','loss'))
print(f'Lines: {html.count(chr(10))+1}')
print(f'BT:{bt}(ok={bt%2==0}) Braces:{op}/{cl}(ok={op==cl})')
print(f'Picks: {len(bets)} | {w}W-{l}L-{p}P | {w/(w+l)*100:.1f}%')
"
```
