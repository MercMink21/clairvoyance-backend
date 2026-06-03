# Clairvoyance Engine — Complete Build Summary

> Last updated: 2026-06-03
> Live URL: https://mercmink21.github.io/clairvoyance-backend/app.html
> Repo: https://github.com/MercMink21/clairvoyance-backend
> Local: /Users/reeseoliver/clairvoyance-backend/

---

## What Clairvoyance Is

Clairvoyance is a sports betting intelligence engine — a single-file progressive web app (PWA) that pulls live data from ESPN, MoneyPuck, NHL Edge, TennisAbstract, Baseball Reference, Basketball Reference, Linemate, and more, runs ensemble probability models, surfaces best bets with EV calculations, tracks locked picks, and auto-settles results. It runs entirely on GitHub Pages (free hosting) with a Python backend that refreshes data on a cron schedule.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Pure vanilla JS + CSS, single HTML file (`docs/app.html`, ~10,700 lines) |
| Backend | Python 3.11 (`scripts/clairvoyance_update.py`, ~3,450 lines) |
| Hosting | GitHub Pages (`docs/` folder → `mercmink21.github.io/clairvoyance-backend/`) |
| Data format | `docs/data.json` (~670KB, written by Python, consumed by JS) |
| Build system | None — no npm, no webpack, no framework |
| CI/CD | GitHub Actions (manual trigger + scheduled auto-refresh) |
| PWA | Service worker (`docs/sw.js`), `manifest.json`, `icon-1080.png` |

---

## Repository File Structure

```
clairvoyance-backend/
├── docs/                          # GitHub Pages root (everything served live)
│   ├── app.html                   # THE ENGINE — entire frontend (~10,714 lines)
│   ├── index.html                 # Redirect → app.html
│   ├── data.json                  # Live data bundle (~670KB, refreshed by Python)
│   ├── live_data.json             # Live in-game scores (refreshed every 2 min during games)
│   ├── social_copy.json           # Generated social media copy
│   ├── config.js                  # API base URL detection (localhost vs GitHub Pages)
│   ├── sw.js                      # Service worker (PWA caching, v6)
│   ├── manifest.json              # PWA manifest
│   ├── .nojekyll                  # Prevents GitHub Pages Jekyll processing
│   ├── icon-1080.png              # App icon
│   ├── card.png                   # Generated social card image
│   └── social/                    # Generated social copy files
├── scripts/
│   ├── clairvoyance_update.py     # Master data refresh engine v7.0 (~3,449 lines)
│   ├── content_generator.py       # Social copy generator (X/IG/Discord)
│   ├── generate_card.py           # Social card image generator
│   ├── run_update.sh              # Wrapper script for the Python engine
│   ├── setup_cron.sh              # Installs cron jobs (09:00, 15:00, 23:00 MT)
│   ├── live_tracker.py            # Live score polling daemon
│   ├── sync_server.py             # Local sync server
│   └── requirements.txt           # Python dependencies
├── data/
│   ├── bundle.json                # Full data bundle (backup)
│   └── best_bets.json             # Today's best bets
├── .github/workflows/
│   ├── manual-sync.yml            # Manual trigger via GitHub token (⚙ Sync Key button)
│   └── scheduled-refresh.yml      # Auto-runs at 09:00, 15:00, 23:00 MT daily
└── .env                           # ODDS_API_KEY and other secrets (gitignored)
```

---

## App Navigation Structure

### Top Nav (`SS(key)`)
`HOME · BASEBALL · FOOTBALL · HOCKEY · BASKETBALL · TENNIS · F1 · LIVE · OVERALL · ANALYTICS · SOCIAL · NEWS`

### MLB sub-tabs (`T('mlb', tab)`)
`PICKS · TODAY · PROPS · PARLAY · NRFI · LIVE · STATS · HISTORY · MODEL · CONFIG`

### NHL sub-tabs (`T('nhl', tab)`)
`LORD STANLEY · PICKS · TODAY · PROPS · PARLAY · LIVE · STATS · HISTORY · MODEL · CONFIG`

### NBA sub-tabs (`T('nba', tab)`)
`LARRY O'BRIEN · PICKS · TODAY · PROPS · PARLAY · LIVE · STATS · HISTORY · MODEL · CONFIG`

### Tennis sub-tabs (`T('ten', tab)`)
`PICKS · TODAY · LIVE · SLAMS · H2H · RANKINGS · MODEL · CONFIG`

### F1 sub-tabs (`T('f1', tab)`)
`PICKS · TODAY · SCHEDULE · DRIVERS · CONSTRUCTORS · STATS · MODEL · CONFIG`

### OVERALL sub-tabs (`T('ovr', tab)`)
`DASHBOARD · ALL BETS · TRENDS · CLV · FUTURES · TENNIS · ADAPTIVE`

### ANALYTICS sub-tabs (`setSub('analytics', sub)`)
`MLB RADAR · NHL RADAR · NBA RADAR · FB RADAR`

### SOCIAL sub-tabs (`setSub('social', sub)`)
`X/TWITTER · INSTAGRAM · DISCORD`

---

## CSS Design Tokens

```css
--void: #010006   /* background base */
--nc:   #00f0ff   /* cyan — primary accent */
--hc:   #ff2090   /* hot pink — warnings/losses */
--vc:   #bbff00   /* volt green — wins/positives */
--ic:   #6690ff   /* indigo — secondary */
--pc:   #f000ff   /* purple — primary highlight */
--gc:   #ffdd00   /* gold — elite picks */
--mc:   #ff7700   /* orange — medium priority */
--rc:   #00ffaa   /* mint — records/stats */
font headers: Orbitron
font data:    Share Tech Mono
font body:    Exo 2
```

---

## Data Sources (52 fetch functions in Python)

### MLB
- ESPN API — scoreboard, schedule, standings, scores, injuries
- MLB Stats API — team hitting/pitching sabermetrics
- Baseball Reference — batting leaders, pitching leaders, fielding leaders, team stats
- Linemate — props, trends, cheatsheet (via Playwright)
- Open-Meteo — park weather for outdoor stadiums
- NCAA Baseball — scores and standings

### NBA
- ESPN API — scoreboard, schedule, playoff bracket, scores, injuries
- Basketball Reference — playoffs per game, per 100 possessions, advanced, shooting
- NBA series stats — ECF (CLE vs NY), WCF (OKC vs SA)
- WNBA — scores and schedule

### NHL
- ESPN API — scoreboard, schedule, standings, injuries
- NHL API — today's games, playoff bracket
- NHL Edge — team stats, goalie save %, 5v5/5v4/4v5 shot data, zone time
- NHL Edge Enhanced — shot location, save locations, strength-based save %
- MoneyPuck — team xGF%, shot data across all situations (5v5, 5v4, 4v5)
- HockeyViz — 5v5 offense/defense, PP offense, PK defense, finishing, shot rates by score
- Hockey Reference — playoff series stats (CAR vs MTL ECF)

### Tennis
- TennisAbstract — ATP/WTA ELO ratings (top 100)
- TennisAbstract — ATP/WTA yElo ratings (seasonal)
- TennisRatio — player comparison and surface stats
- ESPN — rankings (ATP/WTA), schedule (ATP/WTA)
- Roland Garros — draw, schedule, match results
- The Odds API — match odds (ATP/WTA French Open)

### F1
- Ergast API — current season schedule, driver/constructor standings
- F1Datastop — race calendar, race analysis
- TracingInsights GitHub — telemetry data (speed, throttle, DRS, lap times)
- F1 Unchained — track guides (overtaking spots, DRS zones, racing lines)
- ESPN — F1 scoreboard and standings

### Other
- Open-Meteo API — weather for MLB outdoor stadiums
- The Odds API — futures odds (MLB, NBA, NHL, Golf)
- ESPN News API — news across all sports
- ESPN Injuries API — injury reports (MLB, NBA, NHL)
- ESPN Transactions API — trades, signings, waivers

---

## Python Engine Architecture (clairvoyance_update.py v7.0)

### Run Modes
```bash
python3 scripts/clairvoyance_update.py              # full refresh
python3 scripts/clairvoyance_update.py --push       # + git commit & push
python3 scripts/clairvoyance_update.py --mode live  # live-window loop 16:00-23:00 MT
python3 scripts/clairvoyance_update.py --mode props # Linemate only
python3 scripts/clairvoyance_update.py --sport nhl  # single sport
python3 scripts/clairvoyance_update.py --no-linemate    # skip Playwright
python3 scripts/clairvoyance_update.py --no-reference   # skip slow Reference sites
```

### Key Functions
| Function | Purpose |
|---|---|
| `fetch_mlb_scoreboard()` | ESPN MLB games, scores, odds |
| `fetch_mlb_standings()` | ESPN MLB standings |
| `fetch_baseball_reference()` | BBRef batting/pitching/fielding leaders |
| `fetch_mlb_team_sabermetrics()` | MLB Stats API team hitting/pitching |
| `fetch_mlb_nrfi_data()` | NRFI probability per game |
| `fetch_nba_scoreboard()` | ESPN NBA games, scores, odds |
| `fetch_nba_playoff_bracket()` | ESPN NBA bracket |
| `fetch_basketball_reference()` | BBRef playoffs per game/advanced |
| `fetch_basketball_reference_series()` | Series-level stats |
| `fetch_nhl_today()` | NHL API today's games |
| `fetch_nhl_edge()` | NHL Edge team/goalie/skater advanced |
| `fetch_nhl_edge_enhanced()` | Shot location, zone time, 5v5 save % |
| `fetch_moneypuck()` | MoneyPuck 5v5/5v4/4v5 xGF, goalies |
| `fetch_hockeyviz()` | HockeyViz shot rates, zone control |
| `fetch_hockey_reference()` | Hockey Reference playoff stats |
| `fetch_tennis_elo()` | TennisAbstract ELO top 100 |
| `fetch_tennis_yelo()` | TennisAbstract yElo seasonal |
| `fetch_tennis_ratio()` | TennisRatio player comparison |
| `fetch_roland_garros()` | Roland Garros draw + betting lines |
| `fetch_f1()` | Ergast F1 schedule/standings |
| `fetch_f1_tracing_insights()` | TracingInsights telemetry data |
| `fetch_f1_unchained()` | Track guides (overtaking, DRS zones) |
| `fetch_linemate_props()` | Linemate props via Playwright |
| `fetch_linemate_trends()` | Linemate trends |
| `fetch_weather()` | Open-Meteo park weather |
| `fetch_best_odds()` | The Odds API moneylines |
| `calculate_best_bets()` | Main picks engine (EV, ensemble model) |
| `surface_best_bets_for_day()` | Top 6 hero picks for HOME tab |
| `auto_settle()` | Match locked bets against final scores |
| `merge_settled_to_history()` | Build full bet history |
| `build_overall_stats()` | ROI, streaks, win rates |
| `run_live_window()` | Live score loop 16:00-23:00 MT |
| `git_push()` | Auto-commit and push to GitHub |
| `write_data_json()` | Write docs/data.json + frontend/ |

### Betting Model (Ensemble)
- **Monte Carlo simulation** — 5,000-8,000 iterations per game
- **Bayesian probability** — prior + game log posterior
- **ELO ratings** — updated per game with margin-of-victory multiplier (538 method)
- **Logistic regression** — sigmoid blend of multiple features
- **Markov chain momentum** — hot/cold streak modeling
- **HMM streak model** — exponential smoothing on results
- **Random forest approximation** — gradient-boosted feature ensemble
- **Expected Value (EV)** — `EV = (win_prob × dec_odds) - 1`
- **CLV tracking** — closing line value vs opening line

### Bet Grades
| Grade | Win Prob | EV |
|---|---|---|
| A+ ELITE | 67%+ | 8%+ |
| A LOCK | 62-67% | 4-8% |
| B LEAN | 55-62% | 1-4% |

---

## Auto-Refresh Schedule (GitHub Actions)

| Time (MT) | Action |
|---|---|
| 09:00 | Full data refresh — all sports, push to GitHub |
| 15:00 | Full data refresh — all sports, push to GitHub |
| 16:00 | Live window starts — 2-min score refresh loop |
| 23:00 | Full data refresh — all sports, push to GitHub |
| 16:00-23:00 | Live tracking active — `live_data.json` updated every 2 min |

Workflows:
- `scheduled-refresh.yml` — runs automatically on schedule
- `manual-sync.yml` — triggered by user via the ⚙ Sync Key button in the app

---

## Frontend JS Architecture (app.html)

### Global State
```js
D = window.__CV_DATA           // loaded from data.json
TEAMS = {}                     // MLB team objects
NHL = {}                       // NHL team objects (full stats)
NBA_TEAMS = {}                 // NBA team objects
ELO = {}                       // MLB ELO ratings
NBA_ELO = {}                   // NBA ELO ratings
ENS = {}                       // MLB ensemble weights
NHL_ENS = {}                   // NHL ensemble weights
TONIGHT = []                   // Tonight's NHL games
PAR = []                       // MLB parlay legs
```

### Key JS Functions
| Function | Purpose |
|---|---|
| `SS(sport)` | Switch top-level sport tab + re-render content |
| `T(sport, tab)` | Switch sub-tab within a sport |
| `setSub(sport, sub)` | Switch sub-section (MLB/NCAA, NBA/WNBA) |
| `loadRemoteData(force)` | Fetch and apply fresh data.json |
| `renderHomePage()` | Render HOME tab with today's best bets |
| `renderBestBetsFromRemote()` | Display picks from data.json bestBets |
| `renderHomeBestBets()` | Hero picks section on home tab |
| `renderMLBPickCards()` | MLB pick cards with lock button |
| `renderNHLPicks()` | NHL picks with EV display |
| `renderNBAPicks()` | NBA picks with bracket context |
| `renderTennisPicks()` | Tennis picks sorted by win probability |
| `renderOverall()` | Overall stats dashboard |
| `renderOverallHistory()` | Full bet history with filters |
| `renderAdaptiveLearning()` | Model calibration and pattern detection |
| `lockPick()` | Lock a pick into pending bets |
| `lockBet()` | Lock a ML bet (MLB/NBA/NHL) |
| `lockTennisBet()` | Lock a tennis match bet |
| `auto_settle()` | Match pending bets against results |
| `endSplash()` | Dismiss splash + call SS('home') |
| `startSplash()` | Animate splash screen |
| `doUpdate()` | SYNC button — triggers GH rebuild or ESPN fetch |
| `triggerFullRebuild()` | Call GitHub Actions workflow via API |
| `openTokenModal()` | Open GitHub token modal |
| `saveTokenFromModal()` | Save GH token to localStorage |
| `getGHToken()` | Get saved GH token |
| `renderNewsAll()` | Async ESPN news + injuries + transactions |
| `renderIntelCards()` | Social media pick cards |
| `renderF1Schedule()` | F1 race schedule |
| `renderGlobalLive()` | Live in-game tracker |
| `adaptiveTick()` | Run adaptive learning calibration |

### Data Flow
```
GitHub Actions (cron) 
  → clairvoyance_update.py 
  → docs/data.json 
  → GitHub Pages CDN 
  → loadRemoteData() in browser 
  → patch functions update JS state 
  → render functions update DOM
```

---

## Header Buttons

| Button | Function |
|---|---|
| `↻ SYNC` | If GH token saved: triggers full GitHub rebuild. Otherwise: fetches ESPN data directly |
| `⚙ Sync Key` | Opens GitHub token modal — paste ghp_ token, save, then trigger rebuild |

---

## GitHub Token Sync Flow

1. Click **⚙ Sync Key** in header
2. Paste your GitHub Personal Access Token (`ghp_...`) with `workflow` scope
3. Click **SAVE TOKEN** — stored in localStorage
4. Click **↻ TRIGGER FULL REBUILD NOW**
5. App calls GitHub Actions API → triggers `manual-sync.yml`
6. Polls workflow status every 8 seconds
7. When complete (~2-4 min), auto-loads fresh `data.json`

---

## Critical Bugs Fixed in This Session

### 1. Engine Not Loading (SyntaxError)
**Problem:** Boot block (lines 9173-9225) had bare `await` calls at top level of a non-module `<script>` — SyntaxError killed entire engine before any function loaded.
**Fix:** Wrapped boot block in `document.addEventListener('DOMContentLoaded', () => { (async() => { ... })(); })`.

### 2. Duplicate Declarations (SyntaxError)
**Problem:** 11 variables declared twice at top level (`STATMUSE_NHL`, `NBA_TEAMS`, `NBA_TONIGHT`, `NBA_PLAYERS`, `NBA_BBREF`, `NBA_LEADERS`, `NBA_PROPS_DATA`, `MLB_PROPS_DATA`, `NBA_ELO`, `NBA_PAR`, `lastMidDate`).
**Fix:** Changed all second declarations from `const`/`let` to plain reassignments.

### 3. All Tabs Blank — Functions Trapped in INIT IIFE
**Problem:** An `(async function INIT(){})()` IIFE spanning ~1400 lines trapped 67 render functions in its closure scope. In strict mode, function declarations inside a block/function are not hoisted to global — `renderIntelCards`, `renderNewsAll`, `renderTennisToday`, `renderF1Schedule`, `renderGlobalLive`, `broadcastBetLock`, and 61 more were inaccessible.
**Fix:** Added `window[fn.name] = fn` export for all 67 trapped functions at end of INIT.

### 4. All Tabs No Visual Content — #app Closed at Line 484
**Problem:** An extra `</div>` at line 484 was closing `#app` prematurely right after the baseball pane. Every tab after baseball (hockey, NBA, tennis, F1, live, overall, analytics, social, news) was outside the `#app` flex container — no flex parent means `.sa` scroll areas had `height: 0` and were visually invisible even though content existed.
**Fix:** Removed the extra `</div>`. Now `#app` closes at line 10713 (just before `</body>`), containing all 18 sport panes.

### 5. Service Worker Blocking Updates
**Problem:** `sw.js` used cache-first strategy. Normal Chrome cache clearing (`Cmd+Shift+Delete`) does NOT clear service worker cache — users kept getting the broken old version.
**Fix:** Bumped SW cache name from `cv-engine-v4` to `cv-engine-v6`, forcing all clients to discard old cache on next visit.

### 6. Tabs Not Re-Rendering on Click
**Problem:** `SS()` only triggered re-renders for home/overall/social/analytics. Clicking MLB, Hockey, NBA, Tennis, F1, Live tabs did nothing to refresh content — if boot rendering failed, tabs stayed blank forever.
**Fix:** Added render calls to every sport in `SS()`, all wrapped in try/catch. Also added `SS('home')` call inside `endSplash()` so HOME always renders on app entry.

### 7. Splash Blocking Entry
**Problem:** "TAP TO ENTER" button had `opacity: 0` by default and only became visible after JS added a `.v` class 700ms in. Auto-dismiss was 3.2 seconds. If timing failed, users were stuck on splash forever.
**Fix:** Made button always visible with cyan border, reduced auto-dismiss to 1.8s, made clicking anywhere on splash dismiss it.

### 8. GitHub Actions Failures (.nojekyll Missing)
**Problem:** Without `.nojekyll`, GitHub Pages runs Jekyll on the `docs/` folder. Jekyll fails on JavaScript template literals (`${...}`) treating them as broken Liquid templates.
**Fix:** Added `docs/.nojekyll` file, added `permissions: contents: write` to workflow so bot can push data back.

### 9. GitHub Token Sync Dead Code
**Problem:** `_triggerGHAction()` and `_pollGHRun()` existed but were never called from anywhere. The SYNC button had no knowledge of the GitHub token.
**Fix:** Created `triggerFullRebuild()` that wires token → GitHub Actions API → poll → load fresh data. Added `↻ TRIGGER FULL REBUILD NOW` button to the token modal.

### 10. index.html Stale Separate Copy
**Problem:** `index.html` was a separate (outdated) copy of the app, causing the root GitHub Pages URL to show an old version.
**Fix:** Replaced `index.html` with a meta-refresh redirect to `app.html`.

### 11. renderTennisPicks — elId ReferenceError
**Problem:** Line 6832 referenced `elId` which was removed in a refactor, throwing `ReferenceError: elId is not defined` on every tennis tab load.
**Fix:** Removed the stale `elId` reference.

### 12. MLB Lock Button Wrong Position
**Problem:** Lock button was a full-width button at the bottom of each pick card.
**Fix:** Moved to right-aligned inline position beside the prob/EV display.

---

## Data Bundle Structure (data.json keys)

```json
{
  "generated": "ISO timestamp",
  "generatedMT": "human readable MT time",
  "version": "7.0",
  "mlb": { "today", "tomorrow", "standings", "weekSchedule", "nrfi", "sabre", "reference" },
  "nba": { "today", "tomorrow", "standings", "players", "bracket", "reference", "teamAdv", "weekSchedule" },
  "nhl": { "today", "tomorrow", "standings", "bracket", "edge", "edgeEnhanced", "hockeyviz", "hockeyRef", "props", "trends", "form", "weekSchedule" },
  "mp": { "teams": { "5v5", "5v4", "4v5", "all" }, "goalies": [] },
  "weather": { "TEAM_ABBR": { "temp", "wind", "condition", "humidity" } },
  "tennis": { "atpElo", "wtaElo", "atpYelo", "wtaYelo", "schedule", "rankings", "rolandGarros", "tennisRatio" },
  "futures": { "mlb", "nba", "nhl", "golf" },
  "f1": { "nextRace", "driverStandings", "constructorStandings", "analytics", "tracing", "calendar", "unchained" },
  "linemate": { "props": { "nba", "mlb", "nhl" }, "trends": {}, "form": {} },
  "bestBets": [ { "pick", "ev", "evGrade", "sport", "game", "prob", "ml" } ],
  "heroPicksForDay": [ 6 top picks for HOME tab ],
  "bestOdds": { "TEAM:TEAM": { "homeML", "awayML", "ou", "book" } },
  "settled": [ auto-settled bets ],
  "betHistory": [ last 200 settled bets ],
  "overallStats": { "totalBets", "wins", "losses", "roi", "streak", "byGrade", "bySport" },
  "news": { "mlb", "nba", "nhl", "tennis", "f1" },
  "injuries": { "mlb", "nba", "nhl" }
}
```

---

## How to Run Locally

```bash
cd /Users/reeseoliver/clairvoyance-backend

# Full data refresh (no push)
python3 scripts/clairvoyance_update.py

# Full refresh + push to GitHub
bash scripts/run_update.sh --push

# Live mode (runs 16:00-23:00 MT, 2-min intervals)
bash scripts/run_update.sh --mode live --push

# Props only (Linemate scrape)
bash scripts/run_update.sh --mode props --push

# Single sport
bash scripts/run_update.sh --sport nhl --push

# Skip slow Reference scrapes
bash scripts/run_update.sh --no-reference --push

# Install cron schedule (09:00, 15:00, 23:00 MT)
bash scripts/setup_cron.sh

# Serve frontend locally
python3 -m http.server 8765 --directory docs
# Then open: http://localhost:8765/app.html
```

---

## Environment Variables (.env)

```bash
ODDS_API_KEY=your_the_odds_api_key     # For real moneylines and futures odds
# GitHub token stored in browser localStorage (not in .env)
```

---

## Known Pending Items

1. **write_social_copy import error** — `content_generator.py` exports `write_social_json` but update script imports `write_social_copy`. Content generation step is skipped every run.
2. **clairvoyanceengine.info** — Custom domain added in GitHub Pages settings. CNAME file may need to be created: `echo "clairvoyanceengine.info" > docs/CNAME`. Talos spam review was flagged ~2026-05-31.
3. **Football tab** — NFL/College football shows "COMING SOON" placeholder. No data source connected.
4. **Linemate Playwright** — Only works on desktop with Playwright installed. GitHub Actions uses `--no-linemate` flag so props data comes from last successful local run.

---

## Session Bug Fix Summary (2026-06-03)

All fixes applied in a single session:

| # | Bug | Root Cause | Fix |
|---|---|---|---|
| 1 | Engine not loading | Bare `await` at script top level | DOMContentLoaded async IIFE wrapper |
| 2 | SyntaxError on load | 11 duplicate `const`/`let` declarations | Changed duplicates to reassignments |
| 3 | All tabs blank (JS) | 67 render functions trapped in INIT IIFE | Export all to `window[]` |
| 4 | All tabs blank (visual) | `#app` div closed at line 484, all panes outside flex | Remove extra `</div>`, close app before `</body>` |
| 5 | Cache not clearing | Service worker cache-first bypasses browser cache | Bump SW version v4 → v6 |
| 6 | Tabs not re-rendering | `SS()` only re-rendered 4 sections | Add render call for every sport in `SS()` |
| 7 | Splash blocking entry | Button hidden by default, 3.2s auto-dismiss | Always-visible button, 1.8s dismiss, click anywhere |
| 8 | GitHub Actions failures | Jekyll running on docs/, no .nojekyll | Add .nojekyll, add permissions: write |
| 9 | GitHub token sync broken | `_triggerGHAction` never called | Wire into `triggerFullRebuild()` + header button |
| 10 | Root URL stale version | index.html was separate old copy | Redirect to app.html |
| 11 | Tennis picks ReferenceError | Stale `elId` variable | Remove stale reference |
| 12 | MLB lock button wrong | Full-width at bottom | Inline right, beside prob/EV |

---

## Continuing Development

When starting a new chat, reference this file for full context. Key things to know:

- **The entire frontend is `docs/app.html`** — one file, 10,714 lines, pure vanilla JS
- **The Python engine is `scripts/clairvoyance_update.py`** — 3,449 lines, no dependencies except requests/bs4
- **All sport panes must be inside `<div id="app">`** — flex layout depends on it
- **The INIT IIFE at line ~8365** traps functions — any new functions added inside it must be exported to `window`
- **Service worker caches aggressively** — bump `sw.js` cache version when pushing breaking changes
- **GitHub Actions requires `permissions: contents: write`** to push data files back
- **The scheduled-refresh.yml runs at 09:00/15:00/23:00 MT automatically** — no manual trigger needed
- **Live URL:** https://mercmink21.github.io/clairvoyance-backend/app.html (not the root URL)
