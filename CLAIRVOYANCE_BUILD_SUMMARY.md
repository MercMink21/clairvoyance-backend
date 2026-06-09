# CLAIRVOYANCE ENGINE — Master Build Summary & Session Context
> Generated: June 9, 2026 (Session 5) | Supersedes all prior versions

---

## 1. Repository & Live URLs

| Property | Value |
|---|---|
| **GitHub Repo** | `MercMink21/clairvoyance-backend` |
| **Live URL** | `https://mercmink21.github.io/clairvoyance-backend/app.html` |
| **Root redirect** | `docs/index.html` → identical copy of `app.html` |
| **Custom domain** | `clairvoyanceengine.info` (Talos spam review flagged ~2026-05-31) |
| **GitHub Pages source** | `docs/` folder |
| **Latest commit** | `76b1952` — fix(wnba): real BBRef stats + working props |
| **Local repo path** | `/Users/reeseoliver/clairvoyance-backend/` |
| **Mobile repo** | `MercMink21/Clairvoyance-backend-mobile` |

**ALWAYS link to `/app.html` directly** — never the root URL.

---

## 2. File Structure

```
docs/
  app.html          # 15,996 lines — full SPA, SOURCE OF TRUTH
  index.html        # IDENTICAL copy of app.html — always kept in sync
  data.json         # ~578KB — live sports data
  picks.json        # ~546KB — permanent bet history (212 bets, 166W-37L-9P)
  version.json      # Build timestamp
  live_data.json    # Live in-game scores (~45s refresh)
  sw.js             # Service worker SELF-DESTRUCT (prevents caching)
scripts/
  clairvoyance_update.py  # 3,800+ lines — Python data fetcher
  validate.py             # Pre-push validator (93 checks)
  run_update.sh           # --push flag auto-commits
  mobile_transform.py     # iPhone-optimized build
  inject_sim_tracker.py   # Injects Simulator+Tracker standalone script
.github/workflows/
  mobile-sync.yml         # Auto-syncs to mobile repo on every push
CLAIRVOYANCE_BUILD_SUMMARY.md
CLAIRVOYANCE_SESSION_CONTEXT.json
```

### Script Architecture (CRITICAL):
app.html has THREE script blocks:
1. Script 1: tiny inline (0 chars)
2. Main script (~1.13MB) — DOMContentLoaded async IIFE
3. Standalone script (~38KB) — Simulator + Tracker globals

New global functions for onclick handlers must go in standalone script OR be exported via window.fnName = fn inside the IIFE.

---

## 3. Tech Stack

- Frontend: Vanilla JS/HTML/CSS — single file SPA, NO build step, NO npm
- Fonts: Orbitron (--orb), Share Tech Mono (--mono), Exo 2
- Backend: Python 3 (clairvoyance_update.py) via GitHub Actions
- Hosting: GitHub Pages (docs/ folder)
- No service worker: sw.js self-destructs on every load

---

## 4. Design System (CSS Tokens)

```css
--void: #010006  --nc: #00f0ff  --hc: #ff2090  --vc: #bbff00
--ic: #6690ff    --pc: #f000ff  --gc: #ffdd00  --mc: #ff7700  --rc: #00ffaa
--orb: 'Orbitron', sans-serif
--mono: 'Share Tech Mono', monospace
```

---

## 5. Sport Panes & Navigation

Main Nav: SS(sport) | Sub-tab: T(sport, tab) | Sub-pane: setSub(sport, sub)

| Pane ID | Nav Label | Sub-tabs | Sub-panes |
|---|---|---|---|
| sp-home | HOME | — | — |
| sp-mlb | BASEBALL | games, schedule, props, parlay, nrfi, ranks, model, set | mlb |
| sp-nba | BASKETBALL | games, props, parlay, model, config | nba, wnba |
| sp-hk | HOCKEY | games, props, parlay, model, config, edge, goalies, puck | nhl, pwhl, ncaah, khl, shl, liiga |
| sp-fb | FOOTBALL | picks, schedule, stats | nfl, cfb |
| sp-soc | SOCCER | worldcup | — |
| sp-ten | TENNIS | picks, today, slams, schedule, h2h, rankings, compare, model, config | — |
| sp-sim | SIMULATOR | — | — |
| sp-tracker | TRACKER | — | locked, parlay |
| sp-ovr | OVERALL | dash, history, adaptive, sync | — |
| sp-analytics | ANALYTICS | — | betanalytics, bethistory, bysport, byteam, mlb, nhl, nba, trends |
| sp-fut | FUTURES | nba, mlb, nhl, tennis | — |
| sp-social | SOCIAL | cards, monte, record | — |
| sp-news | NEWS | all, mlb, nba, nhl, injuries, trades | — |
| sp-live | LIVE | games, bets | — |

WNBA sub-tabs (inside NBA pane): TODAY · PROPS · PARLAY · MODEL · CONFIG
(SCHEDULE and STATS were added then removed in Session 5)

---

## 6. Prediction Models

### MLB
- Monte Carlo (5K-8K sims) + Bayesian + ELO + Poisson runs model
- Ensemble: ENS = {mc:.50, bay:.20, elo:.30}
- Key: mlbEns(), buildMLB(), renderMLBEnginePicks()

### NBA
- ELO (NBA_ELO), Monte Carlo (5K sims), BBRef advanced stats
- Ensemble: NBA_ENS = {mc:.50, bay:.20, elo:.30}
- Key: nbaEns(), renderNBAGames(), applyNBAWeights()

### WNBA (Session 5 — fully rebuilt)
- wnbaMC(): Poisson 5K MC using team net ratings; inline Box-Muller RNG
- wnbaEns(): MC(45%) + Bayesian(25%) + ELO(30%), ESPN odds blended 30%
- WNBA_ELO: 14 teams — NY:1640, MIN:1590, LV:1560, CON:1535, IND:1525,
  SEA:1495, CHI:1485, PHX:1455, ATL:1445, LA:1430, DAL:1415, GS:1410, WSH:1390, TOR:1355
- WNBA_WIN_PCT: 2026 fallback win% (NY:.72, MIN:.65, LV:.60 ... TOR:.30)
- _wnbaKey(): ESPN/BBRef/full-name abbr normaliser
- Grades: ELITE>=68% · LOCK>=61% · LEAN>=54% · SKIP<54%
- Net rating derived from ELO when teamStats empty: (elo-1490)*0.10

### WNBA Props (Session 5 — rebuilt)
- Source: BBRef per-game stats (205 players, table id=per_game)
- PTS/REB/AST props via Poisson model P(X >= line) at line ~82% of avg
- Opponent defensive context from teamStats.drtg
- USG%, TS% per card; Linemate WNBA trend overlay appended
- Team abbr via _wnbaKey() for ESPN/BBRef mismatch

### NHL
- xGF/60, Corsi, GSAx, MoneyPuck, Poisson 5K sims
- Ensemble: NHL_ENS = {mc:.50, bay:.20, elo:.30}
- renderNHLPropsLive(filter): Linemate props + NHL_PROPS_DATA fallback
  Filters: ALL · POINTS · GOALS · SAVES · SHOTS · TOP PICKS

### MLB Props (Session 5 — partial)
- HTML filter buttons: STRIKEOUTS · HITS · RBIs · HOME RUNS · TOP PICKS
- IMPORTANT: renderMLBPropsLive() was written but NOT saved to file (build failure)
- Current file still uses old static renderMLBProps + MLB_PROPS_DATA array
- Data available: mlb.reference.batting/pitching (BBRef, 50 players each)
- TODO: properly inject renderMLBPropsLive

### Tennis
- Surface ELO (clay/hard/grass/form), yELO, 5-factor composite
- Key: tennisMatchWinProbFull(), renderTennisPicks()

### Pick Grades (MLB/NBA/NHL)
- ELITE: >=67% / EV>=5% · LOCK: >=62% / EV>=3% · LEAN: 55-62% · SKIP: <55%

---

## 7. Python Data Pipeline

3,800+ lines | 55+ fetch functions

### WNBA Functions (Session 5 — rewritten):
fetch_wnba_player_stats():
- BBRef table id='per_game' (2026, NOT 'per_game_stats')
- Player name from <th data-stat="player"><a> anchor
- Team from <td data-stat="team"> anchor
- Advanced: table id='advanced' for PER, TS%, USG%, eFG%, BPM

fetch_wnba_team_stats():
- BBRef table id='advanced-team' for ORtg/DRtg/NRtg/Pace/eFG%/TOV%/ORB%
- BBRef table id='per_game-team' for pts_pg/fg%/3p%/ft%
- BBRef table id='per_game-opponent' for opp_pts/opp_fg
- Team abbr from href: /wnba/teams/MIN/2026.html -> MIN

### Linemate Pipeline (Session 5):
- Sports: nba, mlb, nhl, wnba (wnba added)
- Improved parsing: extracts player, team, over/line/conf, stat category
- Filters header/table rows from trends
- Output: data.json.linemate.props.wnba + linemate.trends.wnba

### data.json Top-Level Keys:
generated, generatedMT, version, mlb, nba, nhl, ncaaBaseball, wnba, pwhl,
mp, weather, tennis, futures, f1, linemate, bestBets, heroPicksForDay,
bestOdds, settled, betHistory, overallStats, seededBets, news, injuries

### GitHub Actions Schedules:
- 09:00, 15:00, 23:00 MT — full refresh
- 16:00-23:00 MT — live tracking every 2 min
- On every push — mobile-sync.yml

---

## 8. File Health (Session 5)

```
app.html:    15,996 lines | ~1,340 KB
Backticks:   2,626 (even OK)
Braces:      10,513 / 10,513 (balanced OK)
Standalone:  38,192 chars | 183/183 braces OK
LOCKED_PROPS declarations: 1
_origSaveP declarations: 1
SW registrations: 0
Validator: 93/93 pass OK
Script blocks: 3
data.json: ~578 KB
picks.json: ~546 KB
```

---

## 9. WNBA 2026 Real Data (BBRef verified June 9, 2026)

Team Stats:
- MIN: ORtg=113.4 DRtg=98.4 Net=+15.0 Pace=79.7
- ATL: ORtg=109.1 DRtg=100.8 Net=+8.3 Pace=78.7
- DAL: ORtg=114.4 DRtg=106.2 Net=+8.2 Pace=78.2
- GSV: ORtg=111.6 DRtg=104.6 Net=+7.0 Pace=76.9
- NYL: ORtg=110.4 DRtg=103.9 Net=+6.5

Player Leaders:
- A'ja Wilson (LVA): 25.9pts 9.6reb 3.3ast
- Kelsey Plum (LAS): 25.5pts 2.4reb 6.4ast
- Kelsey Mitchell (IND): 20.5pts 1.5reb 2.5ast
- Breanna Stewart (NYL): 20.5pts 8.6reb 2.6ast
- Caitlin Clark (IND): 18.7pts 4.5reb 7.9ast
- Paige Bueckers (DAL): 18.3pts 3.6reb 6.2ast

BBRef abbreviations (differ from ESPN):
- LVA = Las Vegas Aces (ESPN: LV)
- NYL = New York Liberty (ESPN: NY)
- GSV = Golden State Valkyries (ESPN: GS)
- PHO = Phoenix Mercury (ESPN: PHX)
- WAS = Washington Mystics (ESPN: WSH)
- LAE = Los Angeles Sparks (ESPN: LA)

---

## 10. Current Sports State (June 9, 2026)

NBA Finals: NYK leads SA 3-0 — G4 June 10 @ MSG
NHL SCF: VGK leads CAR 2-1 — G4 tonight June 9 @ PNC Arena, 8 PM ET TNT
Roland Garros 2026: COMPLETE (Andreeva WTA, Zverev ATP)
MLB: 2026 Regular Season active (15 games today)
WNBA: 2026 Season active (3 games: ATL@CHI, DAL@MIN, PHX@GS)

---

## 11. Pick Record (June 9, 2026)

212 total | 166W-37L-9P | 81.8% win rate
MLB ~75: 47W-16L | NBA ~57: 39W-7L | NHL ~56: 39W-8L | TEN 24: 24W-0L

---

## 12. Known Issues (Session 5 Active)

| Issue | Priority | Notes |
|---|---|---|
| renderMLBPropsLive missing | HIGH | build_props_v1.py failed mid-run, function never written to file |
| WNBA teamStats/players empty | MEDIUM | Will populate on next GitHub Actions run (BBRef scrape fixed) |
| write_social_copy import | LOW | Wrong function name in content_generator.py |
| Football tab | LOW | Coming Soon, no data source |
| Linemate Playwright | LOW | Desktop only, Actions uses --no-linemate |
| NHL SCF G4 result | PENDING | VGK@CAR tonight, update series after |
| NBA Finals G4 | PENDING | SA@NYK June 10 |

---

## 13. Critical Architecture Rules

1. app.html is SOURCE OF TRUTH — always write both app.html AND index.html
2. NEVER re-enable service worker
3. NEVER use agents for large edits — use targeted Python string replacement
4. ALWAYS validate before pushing: python3 scripts/validate.py
5. seedBetHistory() IIFE must survive every push
6. One let LOCKED_PROPS — never re-declare
7. One const _origSaveP — patched once only
8. renderHomePage() + endSplash() must be in DOMContentLoaded init block
9. #app must never start with opacity:0
10. Always copy app.html → index.html
11. Standalone script AFTER main </script> but BEFORE nav dropdown HTML

### Template Literal Safety (CRITICAL — Session 5 lesson):
- NEVER put a literal newline byte (0x0a) inside a JS string literal
- 'LF' between single quotes = SyntaxError = entire engine dead, no splash
- Python: use '\\n' (double-escaped) when writing JS code in strings/heredocs
- Validator now catches this automatically (check added Session 5)
- NEVER put ; as last char inside ${...} template expressions

---

## 14. Safe Edit Protocol

```python
html = open('docs/app.html').read()
old = "exact string to replace"
new = "replacement string"
assert html.count(old) == 1
html = html.replace(old, new, 1)

import re
scripts = list(re.finditer(r'<script([^>]*)>([\s\S]*?)</script>', html))
js = [s.group(2) for s in scripts if len(s.group(2)) > 10000][0]
bt=js.count('`'); op=js.count('{'); cl=js.count('}')
bad=js.count(chr(39)+chr(10)+chr(39))  # literal newline in string
assert bt%2==0 and op==cl and bad==0

open('docs/app.html','w').write(html)
open('docs/index.html','w').write(html)
# Then: python3 scripts/validate.py
```

---

## 15. Git Push Workflow

```bash
cd /Users/reeseoliver/clairvoyance-backend
git add docs/app.html docs/index.html
git commit -m "feat/fix: description"
git stash && git pull --rebase origin main && git stash pop && git push
# data.json conflict: git checkout --theirs docs/data.json && git add docs/data.json && git rebase --continue
```

---

## 16. Session Start Checklist

```bash
git pull
python3 -c "
import re, json
html=open('docs/app.html').read()
scripts=list(re.finditer(r'<script([^>]*)>([\s\S]*?)</script>',html))
js=[s.group(2) for s in scripts if len(s.group(2))>10000][0]
bt=js.count('\x60'); op=js.count('{'); cl=js.count('}')
bad=js.count(chr(39)+chr(10)+chr(39))
bets=json.load(open('docs/picks.json'))
w=sum(1 for b in bets if b.get('outcome')=='win')
l=sum(1 for b in bets if b.get('outcome')=='loss')
p=sum(1 for b in bets if b.get('outcome') not in ('win','loss'))
print(f'Lines:{html.count(chr(10))+1}')
print(f'BT:{bt}(ok={bt%2==0}) Braces:{op}/{cl}(ok={op==cl}) LF:{bad}(ok={bad==0})')
print(f'Picks:{len(bets)} {w}W-{l}L-{p}P {w/(w+l)*100:.1f}%')
"
```

---

## 17. Session 5 Commit Log

```
76b1952 fix(wnba): real BBRef stats + working props
c06ec8e fix(wnba): ML model producing real signal — calibrated grades + fallback strength data
71c8551 remove WNBA schedule + stats sub-tabs
4c54bdb fix(validate): add literal newline in JS string check
39be9f6 fix(critical): unterminated string literal in renderNHLPropsLive killing entire engine
2b86a3d fix(wnba): resolve ReferenceError on randn + complete T() tab routing
c906fac feat(props): live MLB/NHL props rebuild + Linemate integration
441e594 feat(wnba): full data model rebuild — BBRef multi-table + Linemate + gc cards
```
