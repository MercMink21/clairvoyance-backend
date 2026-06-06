# CLAIRVOYANCE ENGINE — Build Summary & Session Context
> Generated: June 4, 2026 | Use this file to onboard a new session instantly

---

## 1. Repository
- **Repo:** `MercMink21/clairvoyance-backend`
- **Live URL:** `https://mercmink21.github.io/clairvoyance-backend/app.html`
- **Source of truth:** `docs/app.html` (Python reads + writes this; `docs/index.html` is an identical copy)
- **Pages source:** `docs/` folder → GitHub Pages serves `index.html` at root, `app.html` explicitly
- **Latest working commit:** `7016be2`

---

## 2. File Structure
```
docs/
  app.html          # 12,308 lines — full SPA (HTML + CSS + JS, single file)
  index.html        # Identical copy of app.html (GitHub Pages root)
  data.json         # 704KB — live sports data (written by Python, fetched network-first)
  picks.json        # 35KB — permanent pick/bet history (GitHub Contents API)
  sw.js             # 14 lines — SW self-destruct (clears cache, unregisters itself)
  config.js         # API base URL detection (localhost vs GitHub Pages)
scripts/
  clairvoyance_update.py  # 3,643 lines — Python data fetcher + GitHub pusher
data/
  bet_history.json  # (currently empty — picks.json is the authoritative store)
  bundle.json       # Internal data bundle
```

---

## 3. Tech Stack
- **Frontend:** Vanilla JS/HTML/CSS — single file SPA, no build step, no npm
- **Fonts:** Orbitron (`var(--orb)`), Share Tech Mono (`var(--mono)`), Exo 2
- **Backend:** Python 3 script (`clairvoyance_update.py`) — runs via GitHub Actions
- **Hosting:** GitHub Pages (static)
- **Data refresh:** GitHub Actions workflow (`manual-sync.yml`) triggered by ↻ SYNC button
- **No service worker** — SW self-destructs on load (disabled to prevent cache issues)

---

## 4. Design System
```css
--void:#010006  --nc:#00f0ff   --hc:#ff2090   --vc:#bbff00
--ic:#6690ff    --pc:#f000ff   --gc:#ffdd00   --mc:#ff7700
--rc:#00ffaa    --orb: Orbitron  --mono: Share Tech Mono
```
CSS classes: `.card`, `.sh`, `.nb`, `.btn`, `.btn-p`, `.btn-o`, `.btn-sm`, `.tab`, `.act`, `.sa`, `.sg`, `.sgt`, `.spane`, `.fi`

---

## 5. Sport Panes & Sub-Tabs

| Pane ID | Nav Label | Sub-tabs / Sub-panes |
|---------|-----------|---------------------|
| `sp-home` | HOME | (single view) |
| `sp-mlb` | BASEBALL | tabs: picks, today, games, schedule, props, parlay, nrfi, ranks, history, model, set / subs: mlb, ncaa |
| `sp-nba` | BASKETBALL | tabs: picks, today, games, schedule, props, parlay, playoffs, stats, history, model, config / subs: nba, wnba |
| `sp-hk` | HOCKEY | tabs: picks, today, games, schedule, props, edge, goalies, puck / subs: nhl, pwhl, ncaah, khl, liiga, shl |
| `sp-fb` | FOOTBALL | tabs: picks, schedule, stats / subs: nfl, cfb |
| `sp-ten` | TENNIS | tabs: picks, today, slams, schedule, h2h, rankings, compare, model, config |
| `sp-f1` | F1 | tabs: picks, today, schedule, standings, drivers, stats, model, config |
| `sp-ovr` | OVERALL | tabs: dash, history, adaptive, trends, clv, analytics, ats, teams, visuals, schedule, futures |
| `sp-analytics` | ANALYTICS | subs: betanalytics, bethistory, bysport, byteam, mlb, nhl, nba, ncaa, fb, atsanalysis, trends, clvanalytics |
| `sp-fut` | FUTURES | tabs: nba, mlb, nhl, tennis |
| `sp-social` | SOCIAL | tabs: cards, monte, record |
| `sp-news` | NEWS | tabs: all, mlb, nba, nhl, injuries, trades |
| `sp-live` | LIVE | tabs: games, bets |

**Navigation functions:** `SS(sport)` — switch sport pane | `T(sport, tab)` — switch sub-tab | `setSub(sport, sub)` — switch sub-pane

---

## 6. Prediction Models

| Sport | Signals | Key Functions |
|-------|---------|---------------|
| **MLB** | Poisson runs model, Bayesian team ratings, ELO, xFIP, NRFI probability, Monte Carlo | `mlbEns()`, `buildMLB()`, `renderMLBPicks()` |
| **NBA** | ELO (`NBA_ELO`), Monte Carlo, BBRef advanced stats, TS%, BPM | `nbaEns()`, `renderNBAPicks()` |
| **NHL** | xGF, Corsi, GSAx, MoneyPuck goalie data, HockeyViz, Monte Carlo | `nhlEns()`, `renderNHLPicks()` |
| **Tennis** | Surface ELO (clay/hard/grass), yELO, TennisAbstract, H2H, fatigue | `tennisMatchWinProbFull()`, `renderTennisPicks()` |
| **F1** | Qualifying delta, constructor standings, pit stop strategy, DNF risk | `renderF1Picks()` |

**Ensemble weights:** `ENS = {mc:.50, bay:.20, elo:.30}` (adjustable in CONFIG tabs)

---

## 7. Python Data Pipeline (`clairvoyance_update.py`)

**53 fetch functions** covering:
- `fetch_mlb_scoreboard/standings/schedule_week/sabermetrics`
- `fetch_nba_scoreboard/standings/playoff_bracket/player_stats`
- `fetch_nhl_today/standings/edge_enhanced/moneypuck/hockeyviz`
- `fetch_tennis_elo/yelo/ratio/odds/roland_garros/schedule_full`
- `fetch_f1/f1_analytics/f1_data`
- `fetch_linemate_props/trends/cheatsheet`
- `fetch_ncaa_baseball/wnba/pwhl/week_schedule`
- `fetch_sports_news/injuries_all/weather/futures_odds/best_odds`

**data.json keys (24):** `generated, generatedMT, version, mlb, nba, nhl, ncaaBaseball, wnba, pwhl, mp, weather, tennis, futures, f1, linemate, bestBets, heroPicksForDay, bestOdds, settled, betHistory, overallStats, seededBets, news, injuries`

**SEEDED_BETS constant** in Python — always included in `data.json` as `seededBets` key for network-first delivery.

---

## 8. Permanent Pick Storage (3-Layer System)

```
Layer 1: localStorage['preds']     — instant, in-browser
Layer 2: IndexedDB                 — survives most cache clears
Layer 3: docs/picks.json (GitHub)  — PERMANENT, cross-device, never lost
```

**Key functions:**
- `loadPicksFromGitHub()` — called in init, merges GitHub + localStorage on every load
- `savePicksToGitHub(picks)` — writes picks to `docs/picks.json` via GitHub Contents API
- `syncPicksToGitHub()` — debounced (5s), fires after every `saveP()` call
- `getGHToken()` / `setGHToken(t)` — reads/writes `cv_gh_token` from localStorage

**Token:** Enter in engine via **⚙ Sync Key** button (top header). Needs `repo` scope. Same token handles data sync AND picks storage.

**picks.json current state:** 153 bets (128W–23L, 2 pending) covering NHL RS, NHL Playoffs, MLB, NBA Playoffs, WCF, Finals G1–G2, Roland Garros.

---

## 9. Seeded Bet History (Always Present)

Lives in `app.html` in `seedBetHistory()` IIFE — runs on every page load, strips+reinserts by ID so outcomes never go stale.

**Current seeded bets (95 entries):**
- NHL 2025–26 Regular Season: 25 picks (Oct 2025 – Feb 2026)
- NHL 2026 Playoffs: 10 picks (R1 → WCF/ECF)
- MLB 2026: 24 picks (Apr – Jun 2026)
- NBA 2026 Playoffs: 15 picks (R1 → ECF)
- WCF Props (SA vs OKC): Wemby PRA, J.Williams PTS
- NBA Finals G1 (SA vs NYK Jun 3): 9 props — 8W/1L
- WCF Series picks: SA +210 G1 WIN, SA +136 G7 WIN
- Roland Garros R1 WTA: 8W (Sakkari, Svitolina, Swiatek, Paolini, Rybakina, Sabalenka, Osaka, Keys)

**To add new settled bets:** Add entry to `seedBetHistory()` IIFE in `app.html`. Use same format. Bump no version needed — strip+reinsert handles it.

---

## 10. Critical Implementation Rules

### JavaScript Safety Checklist (run before every push)
```python
scripts = list(re.finditer(r'<script([^>]*)>([\s\S]*?)</script>', html))
main_js = [s.group(2) for s in scripts if len(s.group(2)) > 10000][0]
bt = main_js.count('`')
op = main_js.count('{'); cl = main_js.count('}')
lp = len(re.findall(r'\blet LOCKED_PROPS\b', main_js))
sp = len(re.findall(r'\bconst _origSaveP\b', main_js))
assert bt % 2 == 0,  "BROKEN: odd backtick count — template literal unclosed"
assert op == cl,     "BROKEN: brace mismatch — function not closed"
assert lp == 1,      "BROKEN: duplicate let LOCKED_PROPS — SyntaxError crash"
assert sp == 1,      "BROKEN: duplicate saveP patch — infinite loop crash"
assert html.count('serviceWorker.register') == 0, "BROKEN: SW re-enabled"
```

### Non-negotiable rules
1. **Never use agents for large multi-file edits** — they introduce syntax errors. Edit with targeted Python scripts instead.
2. **Always validate syntax** (backticks even, braces balanced, no duplicate `let`) before pushing.
3. **`app.html` is source of truth** — Python's `FE = ROOT / "docs" / "app.html"`. `patch_html_timestamp()` reads `app.html`, writes both `app.html` AND `index.html`.
4. **No service worker** — `docs/sw.js` self-destructs. Never re-add SW caching — it caused weeks of loading issues.
5. **Bet history must survive** — `seedBetHistory()` IIFE must be present in every push. Never remove it.
6. **One `let LOCKED_PROPS`** — declared once near top of main JS. Never re-declare in seed blocks.
7. **One `const _origSaveP`** — saveP patched once only. syncPicksToGitHub wired into that single patch.
8. **`renderHomePage()` + `endSplash()` must be in init** — at end of `DOMContentLoaded` block.
9. **`#app` must never be `opacity:0`** — if JS crashes, page stays visible.
10. **Splash auto-hides via CSS** — `@keyframes splashFade` after 3s, regardless of JS state.

---

## 11. How to Push Safely

```python
# Safe push template — always use this pattern
python3 << 'PYEOF'
import re

html = open('docs/app.html').read()

# --- make your changes here ---

# Validate before writing
scripts = list(re.finditer(r'<script([^>]*)>([\s\S]*?)</script>', html))
main_js = [s.group(2) for s in scripts if len(s.group(2)) > 10000][0]
bt = main_js.count('`'); op = main_js.count('{'); cl = main_js.count('}')
lp = len(re.findall(r'\blet LOCKED_PROPS\b', main_js))
sp = len(re.findall(r'\bconst _origSaveP\b', main_js))
assert bt%2==0 and op==cl and lp==1 and sp==1, f"SYNTAX ERROR bt={bt} braces={op-cl} lp={lp} sp={sp}"
print(f"✓ BT:{bt} Braces:{op}/{cl} LOCKED_PROPS:{lp} saveP:{sp} — ALL GOOD")

open('docs/app.html','w').write(html)
open('docs/index.html','w').write(html)  # always keep in sync
PYEOF
```

---

## 12. Known History of Issues & Fixes

| Issue | Root Cause | Fix Applied |
|-------|-----------|-------------|
| Blank page (most common) | SW caching broken app.html | Removed SW entirely; sw.js self-destructs |
| Blank page after push | `#app opacity:0`, JS crash before `.ready` | `opacity:1` always + splashFade CSS |
| Splash never hides | `endSplash()` missing from init | Added to end of `DOMContentLoaded` block |
| Nothing populates | `renderHomePage()` missing from init | Added to end of `DOMContentLoaded` block |
| Total JS crash | Duplicate `let LOCKED_PROPS` | Only declare once; seed block must not re-declare |
| Infinite loop / crash | Duplicate `const _origSaveP` (saveP patched twice) | One patch only; wired directly |
| Broken template literals | Agent-generated code with odd backtick count | Always validate bt%2==0 before push |
| History lost on browser clear | Picks only in localStorage/IDB | 3-layer storage: localStorage + IDB + GitHub picks.json |
| Python overwrites app.html | `FE` pointed to `index.html`, not `app.html` | `FE = ROOT / "docs" / "app.html"` |

---

## 13. NBA Playoffs 2026 State (as of Jun 4)

- **WCF:** SA Spurs def. OKC Thunder 4–3. SA advances.
- **ECF:** NYK Knicks def. CLE Cavaliers 4–2. NYK advances.
- **NBA Finals:** SA Spurs vs NYK Knicks. **NYK leads 2–0.** G1: SA won. G2: NYK won 105–104 (Jun 5).
- **Stanley Cup Finals:** VGK Golden Knights vs CAR Hurricanes (VGK swept WCF 4-0)
- **Roland Garros 2026:** In progress (Jun 4). French Open clay. ATP/WTA both active.

---

## 14. NBA Finals G1 Props (Jun 3 2026) — All Settled

| Bet | Result |
|-----|--------|
| Wemby PTS O 24.5 | ✅ WIN |
| Wemby PTS O 26.5 | ✅ WIN |
| Wemby REB O 9.5 | ✅ WIN |
| Wemby 3PM O 1.5 | ✅ WIN |
| Castle PTS O 13.5 | ✅ WIN |
| Brunson PTS O 21.5 | ✅ WIN |
| OG Anunoby PTS O 12.5 | ✅ WIN |
| Champagnie PTS O 9.5 | ✅ WIN |
| Brunson AST O 6.5 | ❌ LOSS |

---

## 15. Quick Reference — Starting a New Session

```
1. Read this file first
2. git pull to get latest
3. Check: python3 -c "
   import re; html=open('docs/app.html').read()
   scripts=list(__import__('re').finditer(r'<script([^>]*)>([\s\S]*?)</script>',html))
   js=[s.group(2) for s in scripts if len(s.group(2))>10000][0]
   bt=js.count('\x60'); op=js.count('{'); cl=js.count('}')
   print(f'BT:{bt} OK={bt%2==0} Braces:{op}/{cl} diff:{op-cl}')
   "
4. Live URL: https://mercmink21.github.io/clairvoyance-backend/app.html
5. Never: re-enable SW, add duplicate let/const declarations, use agents for large edits
6. Always: validate syntax before push, keep seedBetHistory() intact, sync app.html→index.html
```
