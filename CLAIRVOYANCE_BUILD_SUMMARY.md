# CLAIRVOYANCE ENGINE — Master Build Summary & Session Context
> Generated: June 9, 2026 (Session 8) | Supersedes all prior versions

---

## 1. Repository & Live URLs

| Property | Value |
|---|---|
| **GitHub Repo** | `MercMink21/clairvoyance-backend` |
| **Live URL** | `https://mercmink21.github.io/clairvoyance-backend/app.html` |
| **Root redirect** | `docs/index.html` → identical copy of `app.html` |
| **Custom domain** | `clairvoyanceengine.info` (Talos spam review flagged ~2026-05-31) |
| **GitHub Pages source** | `docs/` folder |
| **Latest commit** | `50f37f5` — feat(wnba): full TODAY/PROPS/PARLAY rebuild |
| **Local repo path** | `/Users/reeseoliver/clairvoyance-backend/` |
| **Mobile repo** | `MercMink21/Clairvoyance-backend-mobile` |

**ALWAYS link to `/app.html` directly** — never the root URL.

---

## 2. File Structure

```
docs/
  app.html          # 16,262 lines — full SPA, SOURCE OF TRUTH
  index.html        # IDENTICAL copy of app.html — always kept in sync
  data.json         # ~578KB — live sports data (WNBA players/teamStats populated)
  picks.json        # ~546KB — permanent bet history (223 bets, 166W-37L-20P)
  version.json      # Build timestamp
  live_data.json    # Live in-game scores (~45s refresh)
  sw.js             # Service worker SELF-DESTRUCT (prevents caching)
scripts/
  clairvoyance_update.py  # 3,828 lines — Python data fetcher
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
2. Main script (~1.14MB) — functions defined at script-global scope BEFORE DOMContentLoaded
3. Standalone script (~38KB) — Simulator + Tracker + WNBA render functions

**IMPORTANT:** Functions defined BEFORE the DOMContentLoaded callback are at script-global scope.
Functions INSIDE the DOMContentLoaded IIFE are scoped to it.
Standalone script (Script 3) functions assigned via `window.*`.
**NEVER declare `function` inside a `catch` or `try` block** — TDZ interaction with outer `const`.
**window.showBetPopup / window.closeBetPopup** — defined in IIFE, NOT in `_exp` array (would overwrite with undefined).

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
| sp-news | NEWS | all, injuries, trades | — |
| sp-live | LIVE | games, bets | — |

WNBA sub-tabs (inside NBA pane): TODAY · PROPS · PARLAY · MODEL · CONFIG

### T() function mnId map:
```javascript
const mnId = sport==='nhl'?'mn2' : sport==='nba'?'mn3' : sport==='ovr'?'mn4'
           : sport==='ten'?'mn5' : sport==='live'?'mn7' : sport==='wnba'?'mn8' : 'mn';
```

### T() cls (active class):
```javascript
const cls = (sport==='nhl'||sport==='nba'||sport==='wnba') ? 'ai' : 'act';
// Session 8: added 'wnba' — WNBA sub-tabs now highlight in indigo (ai) matching NBA
```

### Mobile nav parents (CRITICAL — fixed Session 8):
- `mn8` (WNBA mobile nav) must be inside `nba-wnba` subp — NOT `nba-nba`
- When `nba-nba` is hidden (display:none), any child nav is also hidden

---

## 6. Prediction Models

### MLB
- Monte Carlo (5K-8K sims) + Bayesian + ELO + Poisson runs model
- Ensemble: ENS = {mc:.50, bay:.20, elo:.30}
- Key: mlbEns(), buildMLB(), renderMLBEnginePicks()

### NBA
- ELO (NBA_ELO), Monte Carlo (5K sims), BBRef advanced stats
- Ensemble: NBA_ENS = {mc:.50, bay:.20, elo:.30}
- Session 7: NBA today tab exclusively uses renderNBAGames() MLB-style gc/gch/brow/chip cards

### WNBA (Session 8 — full TODAY/PROPS/PARLAY rebuild)
- wnbaMC(): Poisson 5K MC using team net ratings; inline Box-Muller RNG
- wnbaEns(): MC(45%) + Bayesian(25%) + ELO(30%), ESPN odds blended 30%
- MODEL_FACTORS['wnba']: MC · BAYESIAN · ELO+MOV · NET RATING · ESPN ODDS (added Session 8)
- Grades: ELITE>=68% · LOCK>=61% · LEAN>=54% · SKIP<54%
- WNBA_ELO: 14 teams — NY:1640, MIN:1590, LV:1560, CON:1535, IND:1525,
  SEA:1495, CHI:1485, PHX:1455, ATL:1445, LA:1430, DAL:1415, GS:1410, WSH:1390, TOR:1355

### NHL
- xGF/60, Corsi, GSAx, MoneyPuck, Poisson 5K sims
- Ensemble: NHL_ENS = {mc:.50, bay:.20, elo:.30}

### Tennis
- Surface ELO (clay/hard/grass/form), yELO, 5-factor composite

### Pick Grades (all sports)
- ELITE: >=67% / EV>=5% · LOCK: >=62% / EV>=3% · LEAN: 55-62% · SKIP: <55%

---

## 7. News Tab (Session 8 — full rebuild)

### Structure
- **3 tabs only:** ALL NEWS · INJURIES · TRANSACTIONS (removed MLB, NBA, NHL sport sub-tabs)
- Mobile bottom nav updated to match (3 tabs)

### Filter System (`newsFilterBar`)
- **SPORT row:** ALL · Baseball · Basketball · Football · Hockey · Soccer · Tennis (full names)
- **LEAGUE row:** ALL · MLB · NBA · WNBA · NFL · CFB · NHL · PWHL · C.HOCKEY · KHL · SHL · LIIGA · WORLD CUP · ATP · WTA
- **SEARCH input:** filters by team, player, sport, league, keyword
- `window._NF_SPORT_MAP`: maps sport groups to league arrays
- `window._applyNewsFilter(bar)`: reads `bar.dataset.fSport/fLeague/fText`, filters `.nc` cards
- Sport→league mapping: Baseball→[MLB], Basketball→[NBA,WNBA], Football→[NFL,CFB], Hockey→[NHL,PWHL,CH,KHL,SHL,LIIGA], Soccer→[SOCCER,WC,WORLDCUP,MLS], Tennis→[TENNIS,ATP,WTA]

### Per-Card Features
- Full datetime: weekday, month, day, year, time
- Sport badge + league badge + team badge + player badge
- Description (up to 280 chars)
- **`// IMPLICATIONS`** block — `newsImplication()`, `injuryImplication()`, `txnImplication()`
  - Position-aware injury implications (SP, QB, PG, etc.)
  - Trade, signing, waiver, recall, streak, weather, clinch scenarios
- READ MORE link
- Cards use `.nc` class + `data-sport` + `data-text` for client-side filtering

### Per-Tab Features
- **LAST UPDATED** bar (weekday, date, time, source)
- **↻ UPDATE [TAB]** button — clears cache, re-fetches ESPN live
- ALL NEWS: fetches MLB+NHL+NBA+NFL news (15 each) + injuries + transactions; no injury alert banner
- INJURIES: MLB+NHL+NBA+NFL · OUT/IR · DTD/DOUBTFUL/QUESTIONABLE · PROBABLE sections
- TRANSACTIONS: TRADES · SIGNINGS · WAIVERS/RELEASES · OTHER MOVES sections

---

## 8. Bet Lock / Settle Popups (Session 8)

### HTML
- `#bet-popup` — `position:fixed; top:0;right:0;bottom:0;left:0; z-index:99999`
- Inner card with glow bar, title, bet label, meta row, result block, dismiss button, progress bar

### JS
- `window.showBetPopup(cfg)` — `cfg: {type:'lock'|'settle', betOn, sport, league, betType, ml, prob, decOdds, outcome, score}`
- `window.closeBetPopup()` — hides + clears timer
- Lock: cyan border. WIN: green. LOSS: red. PUSH: orange.
- 5-second auto-dismiss with progress bar drain
- `el.style.setProperty('display','flex','important')` — overrides inline display:none

### Hooked into ALL 13 lock functions:
`lockPick` (API + local), `lockBet`, `lockNHLGame`, `lockNBAGame`, `lockMLBProp`, `lockNHLProp`,
`lockProp`, `lockParlay`, `lockNBAParlay`, `lockNRFIBet`, `lockLiveBet`, `lockTennisBet`,
`lockFuture`, `lockF1Bet`

### Settle popup hooked into:
`recR` (manual), MLB auto-settle loop, NHL auto-settle loop, NBA auto-settle loop

### Critical fix:
- `showBetPopup` / `closeBetPopup` NOT in `_exp` array — `_exp.forEach(fn=>window[fn.name]=fn)` would resolve their `fn.name` as empty or overwrite correctly-set `window.*` with undefined

---

## 9. Bet History Improvements (Session 8)

### Remove Settled Bet Button
- Every bet card in OVERALL → ALL BETS has `× REMOVE` button
- Pending bets: alongside WIN/LOSS. Settled: only action shown.
- Calls `removePick(id)` → confirm → removes from localStorage + API

### removePicksByDate Utility
- `removePicksByDate(dateStr)` — removes all bets matching date prefix
- Confirm dialog · removes from localStorage · calls DELETE on API for each · refreshes all views
- Exported as `window.removePicksByDate`
- **WIPE DATE** button in OVERALL → ALL BETS pending header
- Date input pre-filled to `2026-06-10` (for June 10 test pick cleanup)

---

## 10. WNBA Tab (Session 8 — full repair + rebuild)

### Bugs Fixed
| Bug | Fix |
|---|---|
| `mn8` inside `nba-nba` (hidden when WNBA active) | Moved `mn8` to inside `nba-wnba` |
| T() cls='act' for WNBA (wrong highlight) | Added 'wnba' to ai-class condition |
| MODEL_FACTORS missing 'wnba' | Added MC/BAYESIAN/ELO+MOV/NET RATING/ESPN ODDS |
| `wnba-model-weights` div missing from MODEL tab | Added div to HTML |
| T() routing gaps for MODEL and CONFIG | Added handlers |
| SS('nba') always resets to NBA | Now preserves WNBA sub-state |

### TODAY Tab (Session 8 full rebuild)
- **MLB-parity card design**: `.gc / .gch / .brow / .chip` identical to `mlbCard()`
- **4 lockable bet chips per game**: ML home · ML away · SPREAD · O/U
- **SPREAD**: derived from ESPN odds or wnbaEns probability (`(0.5-hP)*25`)
- **O/U**: projected from wnbaMC avgPts sum vs ESPN line
- ESPN odds blended 30% with ensemble
- **NET RATING** display (ORtg−DRtg from BBRef, shown right side of card header)
- Team record from standings (W-L) shown next to team name
- **ENGINE REASONING** block: ELITE/LOCK/LEAN/SKIP badge + written explanation per tier
- MC%/BAY%/ELO% breakdown + ESPN blend indicator
- `+PAR` button → `addWNBAGameLeg()` sends top pick to parlay GAME LINES panel
- Date strip auto-populated in `wnba-games-date` span
- `window._wnbaGameData` — stores game array for props tab to reference

### PROPS Tab (Session 8 full rebuild)
- **Filtered to today's active games** via ESPN WNBA scoreboard
- **Matchup header** per game before players
- **Top 10 players per matchup**, sorted by avg points
- **5 prop types per player**: PTS · REB (if avg≥4) · AST (if avg≥4) · PTS+REB+AST/PRA (if reb≥3+ast≥3) · 3PT (if fg3m≥1.0)
- **Prop lines**: ~82% of adjusted average (Poisson `_pGe(lam, n)`)
- **Opponent DRtg adjustment**: `(100-drtg)*0.015` applied to each stat
- Per prop: probability %, American odds, ELITE/LOCK/LEAN/SKIP badge
- **LOCK button**: `lockPick(team, opp, 'PROP', 'Player STAT OVER line', prob, ml, dec, today())`
- **+PAR button**: `addWNBAPropLeg(label, ml, prob, key)` → parlay PLAYER PROPS panel
- Player card shows: name, team vs opp, avg PTS/REB/AST/3PT, USG%, TS%, linemate note
- Linemate WNBA props overlay at bottom (with LOCK + +PAR per prop)
- `wnba-parlay-props` div auto-populated with all lockable PTS props from today's players

### PARLAY Tab (Session 8 full rebuild)
- **Two source panel tabs**: GAME LINES · PLAYER PROPS (toggle)
- `wnba-parlay-games` — populated by `renderWNBAGames()`
- `wnba-parlay-props` — populated by `renderWNBAProps()`
- **`addWNBAGameLeg(hab, aab, type, betOn, prob, ml, dec, gameKey)`** — adds game leg, dedupes per game+type
- **`addWNBAPropLeg(label, ml, prob, key)`** — adds prop leg, dedupes per propKey
- **`addWNBALeg(label, ml, prob, game)`** — legacy shim → calls addWNBAGameLeg
- **`_wnbaRenderLegs()`** — renders leg list with GAME/PROP badge + ✕ remove button
- **`calcWNBAP()`** — combined odds, payout, EV%, tier grade, leg count breakdown
- Max 8 legs total (game + prop mix)
- LOCK PARLAY → `lockNBAParlay(w, cP, cML, cD)` saves to picks history

---

## 11. Python Data Pipeline

3,828 lines | 55+ fetch functions

### data.json Top-Level Keys:
generated, generatedMT, version, mlb, nba, nhl, ncaaBaseball, wnba, pwhl,
mp, weather, tennis, futures, f1, linemate, bestBets, heroPicksForDay,
bestOdds, settled, betHistory, overallStats, seededBets, news, injuries

### GitHub Actions Schedules:
- 09:00, 15:00, 23:00 MT — full refresh
- 16:00-23:00 MT — live tracking every 2 min
- On every push — mobile-sync.yml

---

## 12. File Health (Session 8)

```
app.html:    16,262 lines | ~1,340 KB
Backticks:   2,584 (even OK)
Braces:      10,533 / 10,533 (balanced OK)
LF in strings: 0
SW registrations: 0
Validator: 93/93 pass OK
Script blocks: 3
data.json: ~578 KB (WNBA players=199, teamStats=14 teams)
picks.json: 223 bets (166W-37L-20P · 81.8%)
```

---

## 13. Current Sports State (June 9, 2026)

- **NHL SCF**: VGK leads CAR 2-1 — G4 TONIGHT June 9 @ T-Mobile Arena · 8PM ET TNT (result pending)
- **NBA Finals**: NYK leads SA 2-1 — G4 June 10 @ Frost Bank Center SA · 8:30 PM ET ABC
- **Roland Garros 2026**: COMPLETE (Andreeva WTA, Zverev ATP)
- **MLB**: 2026 Regular Season active
- **WNBA**: 2026 Season active

---

## 14. Pick Record (Session 8, June 9 2026)

223 total | 166W-37L-20P | **81.8%** win rate

---

## 15. Known Issues (Session 8 Status)

| Issue | Priority | Notes |
|---|---|---|
| renderMLBPropsLive missing | HIGH | Old static renderMLBProps still rendering |
| WNBA teamStats/players | MEDIUM | Populated in data.json, overwritten each GitHub Actions run |
| write_social_copy import | LOW | Wrong fn name in content_generator.py |
| Football tab | LOW | Coming Soon, no data source |
| Linemate Playwright | LOW | Desktop only — Actions uses --no-linemate |
| NHL SCF G4 result | PENDING | June 9 — record after game |
| NBA Finals G4 | PENDING | June 10 @ SA |

**RESOLVED in Session 8:**
- ~~WNBA mn8 mobile nav hidden when WNBA active~~ — moved to nba-wnba
- ~~WNBA tab buttons wrong highlight color~~ — ai-class added for wnba
- ~~WNBA MODEL_FACTORS missing~~ — added
- ~~No × REMOVE on settled bets~~ — added to all bet cards
- ~~No way to bulk-wipe test picks by date~~ — WIPE DATE button added
- ~~No popup on bet lock/settle~~ — full popup system built
- ~~Popup not showing (display:none not overridden)~~ — setProperty important fix
- ~~Popup hooked into only 2 lock paths~~ — all 13 lock paths covered
- ~~News tab ESPN sport sub-tabs cluttering nav~~ — removed; 3 tabs only
- ~~News cards missing implications~~ — newsImplication/injuryImplication/txnImplication added
- ~~No sport/league filter in news~~ — full filter bar with 6 sports + 15 leagues
- ~~TODAY tab headers inconsistent~~ — standardized to "TODAY'S GAMES + date" all sports
- ~~WNBA TODAY/PROPS/PARLAY not MLB-parity~~ — full rebuild Session 8

---

## 16. Critical Architecture Rules

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
12. WNBA render functions live in STANDALONE script (Script 3) — assigned via window.*
13. window.showBetPopup / window.closeBetPopup — in IIFE, NOT in _exp array
14. T(sport, tab): always pass sport='nhl' (not 'hk') so render block fires and ai-class applies
15. mn8 (WNBA mobile nav) must be inside nba-wnba subp — NOT nba-nba

### Template Literal Safety (CRITICAL):
- NEVER put a literal newline byte inside a JS string literal
- Validator catches chr(39)+chr(10)+chr(39) pattern automatically

### Block-Scoped Function Declaration Safety (CRITICAL):
- NEVER declare `function foo(){}` inside a `try`, `catch`, or `if` block
- Causes TDZ interactions with outer `const` bindings → runtime crash

---

## 17. Safe Edit Protocol

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
bad=js.count(chr(39)+chr(10)+chr(39))
assert bt%2==0 and op==cl and bad==0

open('docs/app.html','w').write(html)
open('docs/index.html','w').write(html)
# Then: python3 scripts/validate.py
```

---

## 18. Git Push Workflow

```bash
cd /Users/reeseoliver/clairvoyance-backend
git add docs/app.html docs/index.html
git commit -m "feat/fix: description"
git stash && git pull --rebase origin main && git stash pop && git push
# data.json conflict: git checkout --theirs docs/data.json && git add docs/data.json && git rebase --continue
```

---

## 19. Session Start Checklist

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

## 20. Session 8 Commit Log

```
50f37f5 feat(wnba): full TODAY/PROPS/PARLAY rebuild — MLB-parity game cards, player props PTS/REB/AST/PRA/3PT, unified parlay builder
73cc61a fix(wnba): add WNBA to MODEL_FACTORS so model weights panel renders correctly
c6f86ae fix(wnba): mn8 in correct parent, ai-class highlight, model weights, SS state preserve, routing parity with NBA
ef7adcf fix(ui): remove emoji from WIPE DATE button
fd9b56b feat(tracker): remove settled bet button + removePicksByDate utility + June 10 wipe tool
4e8b412 feat(popup): hook bet lock popup into all 13 lock paths — all sports all bet types
266bdb6 fix(popup): fix bet popup not showing — remove from _exp, fix inset:0, use setProperty important
d4c46ab feat(ui): bet lock + settle popups — modal overlay with sport/odds/EV/score, auto-dismiss 5s
731006d feat(news): sport filter full names + league filter row (MLB/NBA/WNBA/NFL/CFB/NHL/PWHL/CH/KHL/SHL/LIIGA/WC/ATP/WTA)
2946ec6 feat(news): rebuild news tab — 3 tabs w/ sport/team filters, implications, last updated, update button
6486074 fix(ui): standardize today tab headers to TODAY'S GAMES across MLB/NBA/NHL/WNBA
226d35d fix(mlb): remove calibration and adaptive learning from MLB MODEL tab
77f8f95 fix(nhl): remove bet log section from NHL MODEL tab
```

---

## 21. Session 7 Commit Log (reference)

```
06dd201 NBA today tab: MLB-style cards only + Finals updated to NYK leads 2-1 G4 tomorrow
e882123 Add REMOVE button to pending bets on home page and Overall All Bets
1f6b659 Add TODAY card to Overall Dashboard period performance section
```

---

## 22. Session 6 Commit Log (reference)

```
a421197 fix(nhl-props): lock prop saves full verbatim
8c83855 feat(nhl-props): add MODEL PROB / MKT IMPLIED / EDGE panel
0eee030 fix(nhl-props): accurate G4 rosters from live research
34b4c1b remove: locked NHL props section from props tab
d7d5600 fix(nhl): correct G4 venue, series schedule, rosters
6848b5c feat(nhl-props): SCF G4 VGK@CAR props — 13 props
e06264f fix(wnba): rewrite renderWNBAGames — eliminate TDZ bug
1b77d53 fix(wnba+sim+tracker): ESPN fallback, auto-run sim, tracker seeded bets
338e2a4 fix(wnba): fix ESPN odds path + inject live BBRef player/team stats
74a58b4 fix(sim+tracker): export engine functions to window
3419641 fix(wnba): wire mn8 mobile nav + parlay auto-load games
```

---

## 23. Session 5 Commit Log (reference)

```
76b1952 fix(wnba): real BBRef stats + working props
c06ec8e fix(wnba): ML model producing real signal
71c8551 remove WNBA schedule + stats sub-tabs
4c54bdb fix(validate): add literal newline in JS string check
39be9f6 fix(critical): unterminated string literal in renderNHLPropsLive
2b86a3d fix(wnba): resolve ReferenceError on randn + complete T() routing
c906fac feat(props): live MLB/NHL props rebuild + Linemate integration
441e594 feat(wnba): full data model rebuild
```
