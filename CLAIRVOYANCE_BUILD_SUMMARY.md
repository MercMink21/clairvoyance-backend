# CLAIRVOYANCE ENGINE — Master Build Summary & Session Context
> Generated: June 9, 2026 (Session 4) | Supersedes all prior versions

---

## 1. Repository & Live URLs

| Property | Value |
|---|---|
| **GitHub Repo** | `MercMink21/clairvoyance-backend` |
| **Live URL** | `https://mercmink21.github.io/clairvoyance-backend/app.html` |
| **Root redirect** | `docs/index.html` → identical copy of `app.html` |
| **Custom domain** | `clairvoyanceengine.info` (Talos spam review flagged ~2026-05-31) |
| **GitHub Pages source** | `docs/` folder |
| **Latest commit** | `2bcdf86` — feat(tags): CV_META league/sport system, correct tags everywhere |
| **Local repo path** | `/Users/reeseoliver/clairvoyance-backend/` |
| **Mobile repo** | `MercMink21/Clairvoyance-backend-mobile` — `https://mercmink21.github.io/Clairvoyance-backend-mobile/` |

**⚠️ ALWAYS link to `/app.html` directly** — never the root URL.

---

## 2. File Structure

```
docs/
  app.html          # 15,483 lines — full SPA, SOURCE OF TRUTH (HTML+CSS+JS+standalone script)
  index.html        # IDENTICAL copy of app.html — always kept in sync
  data.json         # 784KB — live sports data (written by Python, network-first)
  picks.json        # 545KB — permanent bet history (212 bets, 166W-37L-9P)
  version.json      # Tiny — build timestamp, read by mobile PWA freshness check
  live_data.json    # Live in-game scores (MLB/NBA/NHL/Tennis, refreshes ~45s)
  sw.js             # Service worker SELF-DESTRUCT (clears cache, unregisters)
  manifest.json     # PWA manifest — start_url: ./app.html
  config.js         # API base URL detection (localhost vs GitHub Pages)
  card.png          # Social card image
scripts/
  clairvoyance_update.py  # 3,700+ lines — Python data fetcher + GitHub pusher
  validate.py             # Pre-push validator (93 checks, auto-blocks bad pushes)
  run_update.sh           # Wrapper — use --push to auto-commit
  setup_cron.sh           # Installs cron jobs
  mobile_transform.py     # Transforms app.html into iPhone-optimized build
  inject_sim_tracker.py   # Injects Simulator+Tracker standalone <script> block
.github/workflows/
  mobile-sync.yml         # GitHub Action: syncs to Clairvoyance-backend-mobile on every push
data/
  bundle.json       # Internal data bundle
CLAIRVOYANCE_BUILD_SUMMARY.md     # This file
CLAIRVOYANCE_SESSION_CONTEXT.json # Machine-readable session state
```

### Script Architecture Note (CRITICAL):
`app.html` contains **two script blocks**:
1. **Main script** (line ~144, ~1.1MB) — all engine logic inside `DOMContentLoaded` async IIFE
2. **Standalone script** (injected by `inject_sim_tracker.py` after main `</script>`) — Simulator + Tracker functions as true globals, NOT inside IIFE

Any new global functions needed by `onclick` handlers must either be:
- Added to the standalone script block, OR
- Exported via `window.fnName = fn` inside the IIFE

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

**CSS utility classes**: `.card`, `.sh`, `.nb`, `.btn`, `.btn-p`, `.btn-o`, `.btn-sm`, `.tab`, `.act`, `.sa`, `.sg`, `.sgt`, `.spane`, `.fi`, `.pk`, `.pkt`, `.pkt2`, `.pkd`, `.pkb`, `.g2`, `.g3`, `.g4`, `.ct`, `.stat-val`, `.stat-lbl`, `.chip`, `.gc`, `.gch`, `.gtm`, `.gsp`, `.brow`, `.tbl-wrap`

---

## 5. Sport Panes & Navigation

### Main Nav: `SS(sport)` | Sub-tab: `T(sport, tab)` | Sub-pane: `setSub(sport, sub)`

| Pane ID | Nav Label | Sub-tabs | Sub-panes |
|---|---|---|---|
| `sp-home` | HOME | — | — |
| `sp-mlb` | BASEBALL | today, games, schedule, props, parlay, nrfi, ranks, model, set | mlb |
| `sp-nba` | BASKETBALL | today, props, parlay, model, config | nba, wnba |
| `sp-hk` | HOCKEY | today, props, parlay, model, config, edge, goalies, puck | nhl, pwhl, ncaah (College Hockey), khl, shl, liiga |
| `sp-fb` | FOOTBALL | picks, schedule, stats | nfl, cfb |
| `sp-soc` | SOCCER | worldcup | — |
| `sp-ten` | TENNIS | picks, today, slams, schedule, h2h, rankings, compare, model, config | — |
| `sp-sim` | SIMULATOR | — | — |
| `sp-tracker` | TRACKER | — | locked, parlay |
| `sp-ovr` | OVERALL | dash, history, adaptive, sync | — |
| `sp-analytics` | ANALYTICS | — | betanalytics, bethistory, bysport, byteam, mlb, nhl, nba, ncaa, fb, trends |
| `sp-fut` | FUTURES | nba, mlb, nhl, tennis | — |
| `sp-social` | SOCIAL | cards, monte, record | — |
| `sp-news` | NEWS | all, mlb, nba, nhl, injuries, trades | — |
| `sp-live` | LIVE | games, bets | — |

### Auto-load behavior (added Session 4):
`SS()` now calls `T(sport, 'today_tab')` on navigation so every sport lands on the TODAY tab:
- MLB → `T('mlb','games')` | Hockey → `setSub('hk','nhl')` + `T('hk','games')`
- Basketball → `setSub('nba','nba')` + `T('nba','games')` | Tennis → `T('ten','today')`
- `setSub()` also auto-jumps: NHL → TODAY, NBA → TODAY, WNBA → TODAY

### Coming Soon panes (activates dates):
| Sub-pane | Activates |
|---|---|
| College Hockey | October 2026 · 2026-27 Season |
| PWHL | November 2026 · 2026-27 Season |
| KHL | September 1, 2026 |
| SHL | September 10, 2026 |
| LIIGA | September 5, 2026 |
| CFB | August 29, 2026 |
| NFL | September 3, 2026 |
| World Cup | June–July 2026 |

---

## 6. Prediction Models

### MLB
- Monte Carlo (5K-8K sims) + Bayesian + ELO + Poisson runs model
- xFIP, wOBA, wRC+, BABIP, ISO from sabermetrics; NRFI probability model
- Ensemble: `ENS = {mc:.50, bay:.20, elo:.30}`
- Key functions: `mlbEns()`, `buildMLB()`, `renderMLBEnginePicks()`, `projectMLBScore()`

### NBA
- ELO (`NBA_ELO`), Monte Carlo (5K sims), BBRef advanced stats
- TS%, BPM, Net Rating, Pace, eFG%
- Ensemble: `NBA_ENS = {mc:.50, bay:.20, elo:.30}`
- Key functions: `nbaEns()`, `renderNBAGames()`, `applyNBAWeights()`

### WNBA
- Same model architecture as NBA
- Ensemble: `WNBA_ENS = {mc:.50, bay:.20, elo:.30}` — `applyWNBAWeights()`
- Win probability: net rating logistic transform from `D.wnba.teamStats`
- Key functions: `renderWNBAGames()`, `renderWNBAProps()`, `applyWNBAWeights()`

### NHL
- xGF/60, Corsi, GSAx, MoneyPuck goalie data, HockeyViz
- Monte Carlo (Poisson 5K sims), PP%, PK%
- Ensemble: `NHL_ENS = {mc:.50, bay:.20, elo:.30}`
- Key functions: `nhlEns()`, `renderNHLTonight()`

### Tennis
- Surface ELO (clay/hard/grass/form), yELO, 5-factor composite
- Key functions: `tennisMatchWinProbFull()`, `renderTennisPicks()`

### Simulator (Session 4 — new)
- Standalone MC engine: 5,000 / 7,500 / 10,000 iterations selectable
- Sports: MLB, NBA, NHL, WNBA, Tennis — uses existing `mlbEns`, `nbaEns`, `nhlEns` for base probability
- Flags: Injury adj, Home adv, Recent form, Rest/fatigue, Weather
- Output: win prob split + EV, score distributions (P10/P90), 20-block trend, outliers (>2σ), engine findings
- Lock buttons wire directly to `lockPick()` via `setTimeout` listeners
- Key functions: `simUpdateTeams()`, `runSimulator()`, `_simRun()`, `_simRender()`

### Pick Grade Thresholds
- **ELITE**: ≥67% win prob / EV ≥5%
- **LOCK**: ≥62% win prob / EV ≥3%
- **LEAN**: 55–62%
- **SKIP**: <55%

---

## 7. Python Data Pipeline (`scripts/clairvoyance_update.py`)

**3,700+ lines | 55+ fetch functions**

### Functions added Session 3:
- `fetch_wnba_player_stats()` — BBRef per-game stats
- `fetch_wnba_team_stats()` — BBRef team advanced stats
- `write_data_json()` also writes `docs/version.json`

### data.json Top-Level Keys (24):
`generated, generatedMT, version, mlb, nba, nhl, ncaaBaseball, wnba, pwhl, mp, weather, tennis, futures, f1, linemate, bestBets, heroPicksForDay, bestOdds, settled, betHistory, overallStats, seededBets, news, injuries`

### GitHub Actions Schedules:
- **09:00, 15:00, 23:00 MT** — full refresh via `scheduled-refresh.yml`
- **16:00–23:00 MT** — live tracking every 2 min
- **On every push to main** — `mobile-sync.yml` transforms + pushes to `Clairvoyance-backend-mobile`

---

## 8. CV_META — Centralized Sport/League Registry (Session 4 — new)

**Location**: standalone script block in `app.html` (after main `</script>`)

```js
CV_META.sports   // Baseball, Basketball, Hockey, Tennis, Football, Soccer
CV_META.leagues  // MLB, NBA, WNBA, NFL, CFB, NHL, PWHL, CH, KHL, SHL, LIIGA, ATP, WTA, WORLD_CUP
CV_META.sportToLeague  // sport code → default league
```

**Tag helper functions** (globally accessible):
- `cvLeagueTag(leagueKey)` — colored pill badge for league (e.g. NHL in indigo)
- `cvSportTag(leagueKey)` — muted sport category derived from league
- `cvBetTypeTag(betType)` — MONEYLINE / PUCK LINE / O/U / SPREAD / PROP
- `cvParlayTag(legCount)` — purple `PARLAY N-LEG` badge
- `cvParlayLegTag(n)` — `LEG 1`, `LEG 2` per parlay leg
- `cvPickLeague(pick)` — resolves league from stored pick (checks `p.league`, falls back to sport code + ATP_DB/WTA_DB for tennis)

**To add a new sport/league**: add one entry to `CV_META.leagues` and optionally `CV_META.sports`. All tag rendering auto-updates.

**lockPick now stores `league` field** on every pick object alongside `sport`.

---

## 9. Permanent Pick Storage — 3-Layer System

```
Layer 1: localStorage['preds']     — instant, in-browser
Layer 2: IndexedDB                 — survives most cache clears
Layer 3: docs/picks.json (GitHub)  — PERMANENT, cross-device, never lost
Layer 4: localStorage['cv_parlays'] — parlay history (up to 50 parlays)
```

- `loadPicksFromGitHub()` — merges GitHub + localStorage on every load
- `savePicksToGitHub(picks)` — writes `docs/picks.json` via GitHub Contents API
- `syncPicksToGitHub()` — debounced 5s, fires after every `saveP()` call
- `seedBetHistory()` — IIFE, runs every load, strip+reinsert by ID
- `saveParlayToTracker(legs, sport)` — saves parlays to `cv_parlays` localStorage

---

## 10. Current Pick Record (June 9, 2026)

**212 total | 166W – 37L – 9P | 81.8% win rate**

| Sport | Bets | W | L | P | Win% |
|---|---|---|---|---|---|
| MLB | ~75 | 47 | 16 | ~12 | 75% |
| NBA | ~57 | 39 | 7 | ~11 | 85% |
| NHL | ~56 | 39 | 8 | ~9 | 83% |
| TEN | 24 | 24 | 0 | 0 | 100% |

---

## 11. File Health (June 9, 2026 — Session 4)

```
app.html:    15,483 lines | 1,307 KB
Backticks:   2,536 (even ✅)  — main script only
Braces:      10,241 / 10,241 (balanced ✅)
Standalone script: 38,192 chars | 183/183 braces ✅
LOCKED_PROPS declarations: 1
_origSaveP declarations: 1
SW registrations: 0
#app hidden on load: false
renderHomePage() in init: true
endSplash() in init: true
Validator checks: 93 / 93 pass ✅
Named functions: 482
data.json: 784 KB
picks.json: 545 KB
```

---

## 12. Header — Current Structure

```
#hdr (56px desktop / 48px mobile)
  ├── .hdr-l   SYNC button + ⚙ Sync Key button + live dot
  ├── .logo    CLAIRVOYANCE (neon purple glow, Orbitron 900)
  │            └── #hdr-status-bar (hidden, for status messages)
  └── .hdr-r   #hdr-clock — live dual timezone
               Desktop: "MT HH:MM:SS · ET HH:MM:SS" (neon purple glow)
               Mobile ≤480px: "MT HH:MM · ET HH:MM"
               Mobile ≤390px: hidden entirely
```

---

## 13. Game Card Design — Unified `gc` Cards (ALL sports)

All game cards across MLB, NBA, WNBA, NHL, Tennis use the same `gc` card structure:

```
div.gc (clipped border, backdrop blur)
  ├── div.gch
  │   ├── left: AWAY at HOME (gtm, fav highlighted purple)
  │   │         odds/matchup line (gsp)
  │   │         status/time (gsp, colored by state)
  │   └── right: status indicator (LIVE dot / FINAL / time)
  ├── div.brow (chips: ML home · ML away · spread/puck line · O/U)
  │   └── each chip: ELITE/LOCK/LEAN/SKIP grade pill + lockPick() on tap
  ├── ENGINE REASONING block (grade badge + explanation text)
  └── footer: MC%/xGF%/ELO% ensemble + +PAR button
```

- **NHL**: gold border, goalie matchup in gsp, puck line chip, MC/xGF/ELO footer
- **NBA/WNBA**: purple border, ESPN odds, spread chip
- **MLB**: purple border, pitcher ERA, run line chip
- **Tennis**: teal border, surface + tour (ATP/WTA), model% vs market%

---

## 14. NHL Today Tab — Cleaned Structure (Session 4)

The NHL TODAY tab now shows ONLY:
1. Header with date + ↻ refresh button
2. `#nhl-tn` — `renderNHLTonight()` gc game cards (SCF series game)

**Removed**: schedule section header, `#nhl-games` lower cards, live scores section, `#nhl-series-status`, `#nhl-inline-props`

---

## 15. SIMULATOR Tab (Session 4 — new)

**Location**: `sp-sim` pane, top nav between SOCIAL and TRACKER

**Controls**:
- Sport selector: MLB / NBA / NHL / WNBA / Tennis
- Home / Away team dropdowns (auto-populate from live data; hardcoded fallbacks)
- Sim count: 5,000 / 7,500 / 10,000
- Filter toggles: Injury adj · Home adv · Recent form · Rest/fatigue · Weather

**Output panels**:
- Win probability split (home% vs away%) with moneyline + EV for each side
- O/U projection — over% from simulations vs set O/U line
- Score distribution charts (home / total / away): bar histogram + P10–P90 band
- Win probability trend: 20 simulation blocks, STABLE vs VOLATILE flag
- Outlier outcomes: results >2σ from mean, blowout rate
- Engine Findings: tier (ELITE/LOCK/LEAN/EDGE), margin projection, O/U recommendation, EV, confidence
- Lock buttons: LOCK [home] ML / LOCK [away] ML / LOCK OVER/UNDER (wired via setTimeout listeners)

**Key functions** (in standalone script): `simUpdateTeams()`, `runSimulator()`, `_simRun()`, `_simRender()`, `_simBarChart()`

---

## 16. TRACKER Tab (Session 4 — new)

**Location**: `sp-tracker` pane, top nav (last item)

### LOCKED BETS sub-tab
- Reads all picks from `getP()`
- Filters: by sport (MLB/NBA/NHL/TEN/WNBA) + by status (all/pending/win/loss)
- Each bet card shows:
  - **League tag** (colored: NHL=indigo, NBA=purple, MLB=pink, etc.)
  - **Sport category** tag (HOCKEY, BASKETBALL, etc.)
  - **Bet type** (MONEYLINE / PUCK LINE / O/U / SPREAD / PROP)
  - **Status badge** (PENDING=cyan / WIN=gold / LOSS=red)
  - **PARLAY badge** for parlay bets, **LEG N** badge if part of a saved parlay
  - Win probability bar (color-coded by confidence tier)
  - Locked timestamp + EV calculation
  - WIN / LOSS / PUSH settle buttons for pending bets
  - For PARLAY bets: full leg list with LEG N badges and individual leg text

### PARLAY sub-tab
- Reads from `localStorage['cv_parlays']` + live `PAR[]` + `NBA_PAR[]`
- Each parlay card shows:
  - **PARLAY N-LEG** badge + league (or MULTI-SPORT if mixed leagues)
  - Combined moneyline + win probability
  - Leg count status (X/N won · Y lost · Z pending)
  - Payout multiplier
  - **Full leg breakdown**: LEG N badge + league tag + bet type + selection + odds + win% + outcome
  - Combined prob + payout + EV summary row
- `saveParlayToTracker(legs, sport)` — persists to `cv_parlays` localStorage (max 50)

**Key functions** (in standalone script): `renderLockedTracker()`, `renderParlayTracker()`, `saveParlayToTracker()`, `cvPickLeague()`

---

## 17. Mobile Repository — Clairvoyance-backend-mobile (Session 4 — new)

| Property | Value |
|---|---|
| **GitHub** | `MercMink21/Clairvoyance-backend-mobile` |
| **Live URL** | `https://mercmink21.github.io/Clairvoyance-backend-mobile/` |
| **GitHub Pages** | `docs/` folder |
| **Sync trigger** | `mobile-sync.yml` — fires on every push to `clairvoyance-backend` main |

**mobile_transform.py** applies these changes to `app.html`:
- Viewport: `maximum-scale=1, user-scalable=no, viewport-fit=cover`
- Font reductions: body 15px→13px, `.sp` 10px, `.nb` 10px, `.sh` 12px, `.gtm` 14px
- Header height: 56px→42px, logo 17px
- Chip padding further reduced, tab bottom padding 86px
- `.g2/.g3/.g4` → 1-column grid
- Safe-area insets for iPhone notch via `env(safe-area-inset-top/bottom)`
- SW cache name prefixed `cve-mobile-v*` to avoid collision with desktop
- PWA name: "Clairvoyance Mobile" / short_name: "CVE-M"
- `MOBILE_SYNC_TOKEN` secret stored in clairvoyance-backend repo secrets

**Repos are fully independent** — mobile sync is one-way (desktop → mobile only). Never pull from mobile back to desktop.

---

## 18. Mobile Architecture (Desktop Repo)

### Mobile Nav Bars (bottom of screen, shown/hidden by SS() / setSub())

| Sport | Nav ID | Tabs |
|---|---|---|
| MLB | `mn` | TODAY · PARLAY · STATS · MODEL · CONFIG |
| NHL | `mn2` | TODAY · PROPS · PARLAY · MODEL · CONFIG |
| NBA | `mn3` | TODAY · PROPS · PARLAY · MODEL · CONFIG |
| WNBA | `mn8` | TODAY · PROPS · PARLAY · MODEL · CONFIG |
| OVERALL | `mn4` | DASH · BETS · ADAPTIVE · SYNC |
| TENNIS | `mn5` | PICKS · TODAY · TOURN · COMPARE · H2H · RANKS |
| ANALYTICS | `mn6` | BET LAB · BY SPORT · BY TEAM · TRENDS · HISTORY |
| LIVE | `mn7` | LIVE · BETS |
| SOCIAL | `mn9` | CARDS · MONTE · RECORD |
| NEWS | `mn10` | ALL · MLB · NBA · NHL · INJURY · TRADES |
| FUTURES | `mn11` | NBA · MLB · NHL · TENNIS |

---

## 19. Sport/League Tag System (Session 4)

### Sport categories (display names):
| Code | Label | Color |
|---|---|---|
| baseball | BASEBALL | `var(--hc)` pink |
| basketball | BASKETBALL | `var(--pc)` purple |
| hockey | HOCKEY | `var(--ic)` indigo |
| tennis | TENNIS | `var(--mc)` orange |
| football | FOOTBALL | `var(--gc)` gold |
| soccer | SOCCER | `var(--nc)` cyan |

### Leagues:
| Key | Label | Sport | Color |
|---|---|---|---|
| MLB | MLB | baseball | pink |
| NBA | NBA | basketball | purple |
| WNBA | WNBA | basketball | volt |
| NFL | NFL | football | gold |
| CFB | CFB | football | seafoam |
| NHL | NHL | hockey | indigo |
| PWHL | PWHL | hockey | purple |
| CH | COLLEGE HCKY | hockey | volt |
| KHL | KHL | hockey | blue |
| SHL | SHL | hockey | cyan |
| LIIGA | LIIGA | hockey | seafoam |
| ATP | ATP | tennis | orange |
| WTA | WTA | tennis | pink |
| WORLD_CUP | WORLD CUP | soccer | gold |

**To add a new league**: one entry in `CV_META.leagues` + one in `CV_META.sportToLeague`. All rendering auto-adapts.

---

## 20. lockPick — Sport & League Detection

```js
lockPick(hA, awA, type, betOn, p, ml, d, date)
// Stores: { sport: sportTag, league: leagueTag, betType: _betTypeNorm, ... }
```

**Type → sport mapping** (explicit, checked first):
`WNBA→WNBA`, `NBA→NBA`, `PL/NHL→NHL`, `TEN/TENNIS→TEN`, `NFL→NFL`, `CFB→CFB`, `PWHL→PWHL`, `KHL→KHL`, `SHL→SHL`, `LIIGA→LIIGA`, `CH→CH`, `SOC/WORLDCUP→SOC`, `ATP→ATP`, `WTA→WTA`

**Fallback** (team abbreviation lookup): NHL set → NBA set → MLB set

**League detection**: `_leagueMap[sportTag]` — for TEN sport, checks `ATP_DB[hA]` / `WTA_DB[hA]` at lock time.

---

## 21. Validator — 93 Checks

Pre-push validator runs on every commit/push via git hooks. All 93 checks pass on current build.

**Important**: Validator checks that nav dropdowns are AFTER all `</script>` tags. The standalone script injected after the main script must stay before the nav dropdown HTML section. Use `inject_sim_tracker.py` to re-inject if the standalone script needs to be rebuilt.

---

## 22. Critical Architecture Rules — NON-NEGOTIABLE

1. **`app.html` is SOURCE OF TRUTH** — always write both `app.html` AND `index.html`
2. **NEVER re-enable service worker** — `sw.js` self-destructs
3. **NEVER use agents for large edits** — use targeted Python scripts with string replacement
4. **ALWAYS validate before pushing** — `python3 scripts/validate.py`
5. **`seedBetHistory()` IIFE must survive every push** — never remove it
6. **One `let LOCKED_PROPS`** — never re-declare
7. **One `const _origSaveP`** — saveP patched once only
8. **`renderHomePage()` + `endSplash()` must be in DOMContentLoaded init block**
9. **`#app` must never start with `opacity:0`**
10. **Always copy `app.html` → `index.html`** — they must be identical
11. **Standalone script must be injected AFTER main `</script>` but BEFORE nav dropdown HTML** — use `inject_sim_tracker.py`; do NOT put onclick-accessible functions inside the IIFE

### Template Literal Safety (CRITICAL):
- **NEVER put `;` as the last char inside `${...}` template expressions**
- `color:${a ? b : c;}` → SyntaxError that kills entire script
- Validator check 23 catches this automatically

### Standalone Script Injection:
- Run `python3 scripts/inject_sim_tracker.py docs/app.html` to re-inject
- Script targets: after the 2nd `</script>` close (main script), before nav dropdowns
- Never inject near `</body>` or `</html>` — validator will reject

---

## 23. Safe Edit Protocol

```python
html = open('docs/app.html').read()
old = "exact string to replace"
new = "replacement string"
assert html.count(old) == 1, f"Pattern not unique: {html.count(old)}"
html = html.replace(old, new, 1)

# Validate MAIN script:
import re
scripts = list(re.finditer(r'<script([^>]*)>([\s\S]*?)</script>', html))
main_js = [s.group(2) for s in scripts if len(s.group(2)) > 10000][0]
bt = main_js.count('`'); op = main_js.count('{'); cl = main_js.count('}')
assert bt%2==0 and op==cl

open('docs/app.html','w').write(html)
open('docs/index.html','w').write(html)
```

Then: `python3 scripts/validate.py`

---

## 24. Git Push Workflow

```bash
cd /Users/reeseoliver/clairvoyance-backend
git add docs/app.html docs/index.html docs/picks.json
git commit -m "feat/fix: description"
git stash && git pull --rebase origin main && git stash pop && git push
# On data.json conflict: git checkout --theirs docs/data.json && git add docs/data.json && git rebase --continue
```

---

## 25. Current Sports State (June 9, 2026)

### NBA Finals: NYK Knicks vs SA Spurs
- **NYK leads 3-0** — won G1, G2, G3
- **G4: June 10 @ MSG** — SA must win to avoid sweep
- G5: June 12 @ SA | G6: June 14 @ MSG | G7: June 16 @ SA (if needed)

### NHL Stanley Cup Finals: VGK vs CAR
- **VGK leads 2-1** — G4 tonight June 9 @ PNC Arena, 8 PM ET TNT
- CAR must win G4 to stay alive; series lines CAR -125 / VGK +105
- TONIGHT array updated: `{h:'CAR',a:'VGK',gn:4,ctx:'SCF — VGK leads 2-1',time:'8 PM ET',net:'TNT',ou:5.5}`

### Roland Garros 2026 — COMPLETE
- **WTA Champion**: Mirra Andreeva (RUS, seed 8)
- **ATP Champion**: Alexander Zverev (GER, seed 2)

### MLB: 2026 Regular Season active

---

## 26. All Features & Changes — Session 4 (June 9, 2026)

### NHL Game Cards — Unified gc Format:
- `renderNHLTonight()` rebuilt to gc card (was custom old format)
- `renderNHLGames()` ESPN path rebuilt to gc card
- `renderNHLGamesOffline()` rebuilt to gc card
- All show: away at home, goalie matchup, puck line chip, engine reasoning, MC/xGF/ELO footer, +PAR
- Gold border `rgba(255,204,0,.5)` for SCF games
- Series state updated: VGK 2-1 CAR, G4 tonight

### NHL Today Tab Cleanup:
- Removed: SCHEDULE section header, lower `#nhl-games` card block, live scores section
- Now shows ONLY: tonight header + `#nhl-tn` gc cards

### Emoji Removal:
- Removed all decorative emojis from visible UI: NCAA Hockey, MLB buttons, WNBA, tennis tournaments, bracket, goalie prefixes
- Replaced `🥅` with `GOALIES:`, `🏏`/`💥` with text labels, etc.

### Coming Soon Screens (all leagues):
- PWHL, College Hockey, KHL, SHL, LIIGA, CFB, NFL: uniform styled preview cards
- Format: gradient title + `Activates: [date]` + description
- No emojis in any coming soon screen

### NCAA Hockey → College Hockey:
- Nav button, dropdown, sub-tab ID `hk-ncaah` — label changed to "COLLEGE HOCKEY"

### Soccer Tab Added:
- `sp-soc` pane with WORLD CUP sub-tab
- Coming soon: FIFA World Cup 2026 module description
- Dropdown nav entry added

### SIMULATOR Tab (new):
- Full Monte Carlo engine: 5k/7.5k/10k sims, all 5 sports
- Score distributions, trend analysis, outlier detection
- Implemented as standalone script to avoid IIFE isolation
- All functions global via separate `<script>` tag

### TRACKER Tab (new):
- LOCKED BETS: reads `getP()`, filters, shows league+sport+type tags, settle buttons
- PARLAY: reads cv_parlays + PAR[] + NBA_PAR[], leg-by-leg breakdown
- Implemented as standalone script

### CV_META Tag System (new):
- Centralized registry for all sports and leagues
- `cvLeagueTag()`, `cvSportTag()`, `cvBetTypeTag()`, `cvParlayTag()`, `cvParlayLegTag()`
- `lockPick` now stores `league` field on every pick
- ATP vs WTA distinguished at lock time via ATP_DB/WTA_DB
- Re-inference for old picks without league field in `renderLockedTracker`

### Sport Tag Fixes:
- WNBA bets no longer tagged as NBA/MLB (type==='WNBA' handled first)
- NHL PROP bets correctly tagged NHL
- NBA SPREAD/OU correctly tagged NBA
- Complete NHL team set (32 teams), NBA set with correct abbreviations

### Auto-load TODAY Tab:
- `SS()` calls `T(sport,'games')` on every sport navigation
- `setSub()` calls `T()` when switching sub-leagues (NHL, NBA, WNBA)

### Mobile Repository (new):
- `MercMink21/Clairvoyance-backend-mobile` created and deployed
- `scripts/mobile_transform.py` — applies iPhone-specific CSS
- `mobile-sync.yml` GitHub Action — auto-syncs on every desktop push
- `MOBILE_SYNC_TOKEN` secret configured in clairvoyance-backend

---

## 27. Known Issues (Active)

| Issue | Notes |
|---|---|
| `write_social_copy` import error | Python imports function not in content_generator.py. Content generation skipped every run |
| Football tab | NFL/CFB shows Coming Soon — no data source connected |
| Linemate Playwright | Only works on desktop. GitHub Actions uses `--no-linemate` flag |
| Custom domain | `clairvoyanceengine.info` — Talos spam review may need resolution |
| NHL SCF G4 result | VGK vs CAR G4 tonight (June 9) — result not yet recorded |
| NBA Finals G4 | June 10 — need props and series update after game |
| Parlay leg linkback | Picks in getP() don't have `inParlay` flag yet — parlay lookup by pickId incomplete |

---

## 28. Session Start Checklist

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
