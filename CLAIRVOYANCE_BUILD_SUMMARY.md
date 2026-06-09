# CLAIRVOYANCE ENGINE — Master Build Summary & Session Context
> Generated: June 9, 2026 (Session 3) | Supersedes all prior versions

---

## 1. Repository & Live URLs

| Property | Value |
|---|---|
| **GitHub Repo** | `MercMink21/clairvoyance-backend` |
| **Live URL** | `https://mercmink21.github.io/clairvoyance-backend/app.html` |
| **Root redirect** | `docs/index.html` → identical copy of `app.html` |
| **Custom domain** | `clairvoyanceengine.info` (Talos spam review flagged ~2026-05-31) |
| **GitHub Pages source** | `docs/` folder |
| **Latest commit** | `0fcc172` — fix(mobile): screen fit + always-current version enforcement |
| **Local repo path** | `/Users/reeseoliver/clairvoyance-backend/` |

**⚠️ ALWAYS link to `/app.html` directly** — never the root URL.

---

## 2. File Structure

```
docs/
  app.html          # 14,688 lines — full SPA, SOURCE OF TRUTH (HTML+CSS+JS)
  index.html        # IDENTICAL copy of app.html — always kept in sync
  data.json         # 784KB — live sports data (written by Python, network-first)
  picks.json        # 191KB — permanent bet history (203 bets, 166W-37L-0P)
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

**CSS utility classes**: `.card`, `.sh`, `.nb`, `.btn`, `.btn-p`, `.btn-o`, `.btn-sm`, `.tab`, `.act`, `.sa`, `.sg`, `.sgt`, `.spane`, `.fi`, `.pk`, `.pkt`, `.pkt2`, `.pkd`, `.pkb`, `.g2`, `.g3`, `.g4`, `.ct`, `.stat-val`, `.stat-lbl`, `.chip`, `.gc`, `.gch`, `.gtm`, `.gsp`, `.brow`, `.tbl-wrap`

---

## 5. Sport Panes & Navigation

### Main Nav: `SS(sport)` | Sub-tab: `T(sport, tab)` | Sub-pane: `setSub(sport, sub)`

| Pane ID | Nav Label | Sub-tabs | Sub-panes |
|---|---|---|---|
| `sp-home` | HOME | — | — |
| `sp-mlb` | BASEBALL | today, games, schedule, props, parlay, nrfi, ranks, model, set | mlb |
| `sp-nba` | BASKETBALL | today, props, parlay, model, config | nba, wnba |
| `sp-hk` | HOCKEY | today, props, parlay, model, config, edge, goalies, puck | nhl, pwhl, ncaah, khl, liiga, shl |
| `sp-fb` | FOOTBALL | picks, schedule, stats | nfl, cfb |
| `sp-ten` | TENNIS | picks, today, slams, schedule, h2h, rankings, compare, model, config | — |
| `sp-ovr` | OVERALL | dash, history, adaptive, sync | — |
| `sp-analytics` | ANALYTICS | — | betanalytics, bethistory, bysport, byteam, mlb, nhl, nba, ncaa, fb, atsanalysis, trends, clvanalytics |
| `sp-fut` | FUTURES | nba, mlb, nhl, tennis | — |
| `sp-social` | SOCIAL | cards, monte, record | — |
| `sp-news` | NEWS | all, mlb, nba, nhl, injuries, trades | — |
| `sp-live` | LIVE | games, bets | — |

### Tabs removed this session (Session 3):
- **NBA**: picks, history, schedule sub-tabs removed
- **NHL**: picks, history, schedule sub-tabs removed
- **NHL TODAY buttons**: LIVE and TOMORROW removed (only ↻ refresh remains)
- **NBA TODAY buttons**: LIVE, SCHED, TOMORROW removed (only ↻ refresh remains)
- **F1 tab**: fully removed in Session 2

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
- Model factors: NET RATING (HIGH), PACE-ADJ eFG% (HIGH), DEFENSIVE RTG (HIGH), TO% (MED), FT RATE (MED), REST ADVANTAGE (LOW)
- Key functions: `nbaEns()`, `renderNBAGames()`, `applyNBAWeights()`

### WNBA
- Same model architecture as NBA
- Ensemble: `WNBA_ENS = {mc:.50, bay:.20, elo:.30}` — `applyWNBAWeights()`
- Model factors: identical 6-factor set as NBA
- Win probability: net rating logistic transform from `D.wnba.teamStats` → fallback win% → 53/47
- Data: BBRef `wnba/years/2026_per_game.html` (players) + `wnba/years/2026.html` (team stats)
- Key functions: `renderWNBAGames()`, `renderWNBAProps()`, `applyWNBAWeights()`

### NHL
- xGF/60, Corsi, GSAx, MoneyPuck goalie data, HockeyViz
- Monte Carlo (Poisson 5K sims), PP%, PK%
- Ensemble: `NHL_ENS = {mc:.50, bay:.20, elo:.30}`
- Key functions: `nhlEns()`, `renderNHLPicks()`

### Tennis
- Surface ELO (clay/hard/grass/form), yELO
- 5-factor composite ELO model
- Key functions: `tennisMatchWinProbFull()`, `renderTennisPicks()`

### Pick Grade Thresholds
- **ELITE**: ≥67% win prob / EV ≥5%
- **LOCK**: ≥62% win prob / EV ≥3%
- **LEAN**: 55–62%
- **SKIP**: <55%

---

## 7. Python Data Pipeline (`scripts/clairvoyance_update.py`)

**3,700+ lines | 55+ fetch functions**

### New functions added Session 3:
- `fetch_wnba_player_stats()` — scrapes BBRef `wnba/years/2026_per_game.html` for pts/reb/ast/stl/blk/ts%/usg%
- `fetch_wnba_team_stats()` — scrapes BBRef team advanced (ortg, drtg, pace, efg%, ts%)

### `write_data_json()` now also writes:
- `docs/version.json` — `{"built": "YYYYMMDD-HHMM", "ts": unix_timestamp}` — used by mobile PWA freshness check

### data.json Top-Level Keys (24):
`generated, generatedMT, version, mlb, nba, nhl, ncaaBaseball, wnba, pwhl, mp, weather, tennis, futures, f1, linemate, bestBets, heroPicksForDay, bestOdds, settled, betHistory, overallStats, seededBets, news, injuries`

### `wnba` key now includes:
`today, standings, schedule, players[], teamStats{}`

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

## 9. Current Pick Record (June 9, 2026)

**203 total | 166W – 37L – 0 pending | 81.8% win rate**

| Sport | Bets | W | L | P | Win% |
|---|---|---|---|---|---|
| MLB | 75 | 47 | 16 | 12 | 75% |
| NBA | 57 | 39 | 7 | 11 | 85% |
| NHL | 47 | 39 | 8 | 0 | 83% |
| TEN | 24 | 24 | 0 | 0 | 100% |

*Note: All 23 NBA Finals G3 props settled (outcomes recorded since Session 2)*

---

## 10. File Health (June 9, 2026)

```
app.html:    14,688 lines | 1,251 KB
Backticks:   2,514 (even ✅)
Braces:      10,081 / 10,081 (balanced ✅)
LOCKED_PROPS declarations: 1
_origSaveP declarations: 1
SW registrations: 0
#app hidden on load: false
renderHomePage() in init: true
endSplash() in init: true
Validator checks: 93 / 93 pass ✅
Named functions: 484
data.json: 784 KB
picks.json: 191 KB
```

---

## 11. Header — Current Structure

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

Clock ticks every 1 second via IIFE setInterval. `America/Denver` (MT) + `America/New_York` (ET).

---

## 12. Home Page — Current Structure

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
  └── Hidden stubs               (keep for JS compat)
```

---

## 13. Game Card Design — MLB-Style `gc` Cards (NBA + WNBA + MLB)

All NBA, WNBA, and MLB TODAY tabs now use the same `gc` card structure:

```
div.gc (clipped border, backdrop blur)
  ├── div.gch
  │   ├── left: AWAY at HOME (gtm, fav highlighted purple)
  │   │         ESPN odds line (ML · O/U)
  │   │         status/time line (gsp, colored by state)
  │   └── right: status indicator (LIVE dot / FINAL / time)
  ├── div.brow (pre-game chips: ML home · ML away · spread · O/U)
  │   └── each chip: ELITE/LOCK/LEAN/SKIP grade pill + lockPick() on tap
  ├── reasoning block (ENGINE REASONING — grade badge + explanation text)
  └── footer: MC%/BAY%/ELO% ensemble + +PAR button
```

NBA game cards use `nbaEns()` for win probability. WNBA uses net rating logistic transform from `D.wnba.teamStats`.

---

## 14. Mobile Architecture

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

### Mobile CSS Overrides (≤768px)
- `body{font-size:15px}` (vs 19px desktop)
- Header: `48px` height, compact buttons, smaller logo
- `.gtm{font-size:16px}` (vs 21px), `.cho{font-size:15px}` (vs 19px)
- `.sh{font-size:14px}`, `.nb{font-size:12px}`
- `.chip{padding:7px 3px}` — 4 chips fit comfortably on 375px screen
- `.tab{padding:10px 8px 82px}` — 82px bottom clearance for nav bar
- `.g3, .g4` → 2-column on mobile; `.g2` → 1-column
- `.tbl-wrap{overflow-x:auto}` — tables scroll horizontally

### Small phone overrides (≤390px)
- `.gtm{font-size:14px}`
- `#hdr-clock{display:none}` — clock hidden (too narrow)

### Mobile Freshness System
- `docs/version.json` — written by Python on every data refresh with build timestamp
- On app load: JS fetches `version.json?_=Date.now()` (cache:no-store)
- Compares `built` field to `localStorage('cv_app_built')`
- If newer build deployed → `window.location.reload(true)` → always current
- `visibilitychange` listener: if backgrounded >10min → reload on resume
- `pageshow` listener: iOS bfcache bypass

### PWA / manifest.json
- `start_url: "./app.html"` (was `"./"`)
- `display: "standalone"`, `orientation: "portrait-primary"`
- `prefer_related_applications: false`
- Icons: `icon-1080.png` at 192×192, 512×512, 1080×1080

### SW (`sw.js`)
- SELF-DESTRUCT pattern — clears all caches, unregisters itself
- Passes every request through to network (no caching)
- **NEVER re-enable caching SW** — caused blank page loops historically

---

## 15. OVERALL Tab — ALL BETS Enhancement

**Pending bets section** pinned to the TOP of the ALL BETS tab:
- Rendered BEFORE any sport/date filter logic runs
- Shows ALL pending bets regardless of active filter state
- Cyan header: `⏳ PENDING BETS — N`
- WIN/LOSS settle buttons with `recR()` + `setTimeout(renderOverallHistory, 400)`

---

## 16. Validator — 93 Checks

Pre-push validator runs on every commit/push via git hooks.

All 93 checks pass on current build.

---

## 17. Critical Architecture Rules — NON-NEGOTIABLE

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
- Validator check 23 catches this class of bug automatically

---

## 18. Safe Edit Protocol

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

open('docs/app.html','w').write(html)
open('docs/index.html','w').write(html)
```

Then: `python3 scripts/validate.py`

---

## 19. Git Push Workflow

```bash
cd /Users/reeseoliver/clairvoyance-backend
git add docs/app.html docs/index.html docs/picks.json
git commit -m "feat/fix: description"
git stash && git pull --rebase origin main && git stash pop && git push
# On data.json conflict: git checkout --theirs docs/data.json && git add docs/data.json && git rebase --continue
```

---

## 20. Current Sports State (June 9, 2026)

### NBA Finals: NYK Knicks vs SA Spurs
- **NYK leads 3-0** — won G1, G2, G3
- G3 (June 8 @ MSG): all props settled
- **G4: June 10 @ MSG** — SA must win to avoid sweep
- G5: June 12 @ SA | G6: June 14 @ MSG | G7: June 16 @ SA (if needed)

### NHL Stanley Cup Finals: VGK vs CAR
- **VGK leads 2-1** (as of Session 2 — G4 June 9 @ PNC Arena)
- CAR must win G4 to stay alive
- Series lines: CAR -125 / VGK +105

### Roland Garros 2026 — COMPLETE
- **WTA Champion**: Mirra Andreeva (RUS, seed 8) def. Chwalinska 6-3, 6-2 — Jun 6
- **ATP Champion**: Alexander Zverev (GER, seed 2) def. Cobolli (ITA, seed 10) — Jun 8

### MLB: 2026 Regular Season active

---

## 21. All Features & Changes — Session 3 (June 9, 2026)

### NBA Tab Cleanup:
- Removed hidden dead divs: `nba-tab-picks`, `nba-tab-history`, `nba-tab-schedule`
- Fixed pre-existing duplicate `sp-ovr` fragment (validator error)
- Removed NBA TODAY buttons: LIVE, ↻ SCHED, TOMORROW → only ↻ remains
- Removed redundant lower props section (duplicate of `renderNBAFinalsProps`)

### WNBA — Real Data Pipeline:
- **Python**: `fetch_wnba_player_stats()` — BBRef per-game (pts/reb/ast/stl/blk/ts%/usg%)
- **Python**: `fetch_wnba_team_stats()` — BBRef ortg/drtg/pace per team
- `fetch_wnba()` now populates `wnba.players[]` + `wnba.teamStats{}` in data.json
- **`renderWNBAGames()`**: real win probs from net rating logistic transform (D.wnba.teamStats)
- **`renderWNBAProps()`**: props from D.wnba.players season averages, real grade thresholds
- **WNBA tab fix**: `nba-wnba` div was orphaned outside `sp-nba` → moved inside, `display:none` override removed
- **WNBA model tab**: full 6-factor grid (NET RATING, PACE-ADJ eFG%, DEFENSIVE RTG, TO%, FT RATE, REST ADVANTAGE)
- **WNBA config tab**: APPLY button + pick thresholds (MIN EV, MIN WIN PROB) matching NBA
- `applyWNBAWeights()` + `window.WNBA_ENS = {mc:.50, bay:.20, elo:.30}` added
- WNBA TODAY header: "WNBA GAMES TODAY" → "TODAY" + date (same as NBA/MLB/NHL)

### NHL Tab Cleanup:
- Removed PICKS sub-tab (nav button, tab div, mobile button)
- Removed HISTORY sub-tab (nav button, tab div)
- Removed SCHEDULE sub-tab (nav button, tab div)
- Removed TODAY buttons: LIVE, TOMORROW → only ↻ remains

### Header:
- Live dual-timezone clock added: `MT HH:MM:SS · ET HH:MM:SS`
- Color: neon purple (`var(--pc)`) with glow
- Position: top-right of header (`hdr-r`)
- Mobile: HH:MM only (≤480px); hidden (≤390px)

### Game Card Design — MLB-Style `gc` Cards:
- **NBA TODAY**: rebuilt to exact MLB gc card structure — away at home, ESPN odds, chip row (ML×2 + spread + O/U), ENGINE REASONING block, MC/BAY/ELO ensemble footer, +PAR button
- **WNBA TODAY**: same gc card design — net rating displayed, real win probs, chip row

### WNBA Model + Config:
- Model tab: 6-factor grid matching NBA exactly
- Config tab: APPLY + pick thresholds matching NBA
- `applyWNBAWeights()` added

### Mobile — Full iPhone Parity:
- Mobile nav bars added for ALL sections (mn2-mn11)
- mn2 (NHL): fixed — HISTORY removed, PROPS added
- mn3 (NBA): MODEL + CONFIG added
- mn8 (WNBA): new nav bar
- mn6 (Analytics): new — BET LAB/BY SPORT/BY TEAM/TRENDS/HISTORY
- mn9 (Social): new — CARDS/MONTE/RECORD
- mn10 (News): new — ALL/MLB/NBA/NHL/INJURY/TRADES
- mn11 (Futures): new — NBA/MLB/NHL/TENNIS
- SS() and setSub() updated to show/hide all new navs
- setSub() swaps mn3↔mn8 when switching NBA↔WNBA

### Mobile CSS Overrides (comprehensive):
- body: 19px → 15px; header: 56px → 48px
- .gtm: 21px → 16px (14px at ≤390px); .cho: 19px → 15px
- .sh: 17px → 14px; .nb: 13px → 12px; .chip: padding reduced
- .tbl-wrap utility added for horizontal table scroll
- .g3/.g4 → 2-col; .g2 → 1-col

### Mobile Freshness System:
- `docs/version.json` written by Python on every data refresh
- JS version check on load: compares built timestamp → `location.reload(true)` if stale
- visibilitychange: reload if backgrounded >10min
- pageshow: iOS bfcache bypass
- manifest.json: `start_url` → `./app.html`, `prefer_related_applications: false`
- meta no-cache tags added (belt-and-suspenders)

---

## 22. Known Issues (Active)

| Issue | Notes |
|---|---|
| `write_social_copy` import error | Python imports function that doesn't exist in content_generator.py. Content generation skipped every run |
| Football tab | NFL/CFB shows "COMING SOON" — no data source connected |
| Linemate Playwright | Only works on desktop. GitHub Actions uses `--no-linemate` flag |
| Custom domain | `clairvoyanceengine.info` — Talos spam review may need resolution |
| NHL SCF G4 result | VGK vs CAR G4 outcome pending (June 9) — needs update |
| NBA Finals G4 | Pending June 10 — need to add props and update series state |

---

## 23. Session Start Checklist

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
