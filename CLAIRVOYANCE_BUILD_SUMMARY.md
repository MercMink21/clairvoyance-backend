# CLAIRVOYANCE ENGINE — Master Build Summary & Session Context
> Generated: August 20, 2026 (Session 9) | Supersedes all prior versions
> Covers: June 9, 2026 → August 20, 2026 (~2.5 months, ~646 substantive commits, ~3,900 total commits incl. automated data refreshes)

---

## 0. Session 9 — What Happened Since Session 8 (Executive Summary)

This was the largest stretch of continuous development on the project. Headline scale change:

| Metric | Session 8 (Jun 9) | Session 9 (Aug 20) | Delta |
|---|---|---|---|
| `docs/app.html` lines | 16,262 | 32,202 | +15,940 (nearly doubled) |
| `scripts/clairvoyance_update.py` lines | 3,828 | 5,762 | +1,934 |
| Total Python scripts in `scripts/` | ~8 | 24 | +16 new scripts |
| GitHub Actions workflows | 2 | 21 | +19 new workflows |
| Sports/leagues covered | MLB, NBA, NHL, WNBA, Tennis (5) | + CFB, NFL, CBB, Premier League, La Liga, Bundesliga, Serie A, MLS, Champions League, NCAAH, PWHL, KHL, SHL, Liiga (19 total) | +14 leagues |
| All-time pick record | N/A (pre-launch data) | 736W-247L (74.9%), +371.7u, since launch Jul 1 2026: 344W-119L (74.3%) | — |

In short: the app went from a 5-league MLB/NBA/NHL/WNBA/Tennis picks tool to a 19-league, near-fully-automated sports intelligence platform with server-side settlement, a Supabase-backed ledger, and daily social content generation — all while running on the same "single HTML file, no build step" architecture.

---

## 1. Repository & Live URLs

| Property | Value |
|---|---|
| **GitHub Repo** | `MercMink21/clairvoyance-backend` |
| **Live URL** | `https://purple-wraith.github.io/clairvoyance-backend/app.html` |
| **Root redirect** | `docs/index.html` → identical copy of `app.html` |
| **Custom domain** | `clairvoyanceengine.info` (Talos spam review flagged ~2026-05-31 — verify current status) |
| **GitHub Pages source** | `docs/` folder |
| **Latest commit (origin/main)** | `ada2a78c` — statmuse: refresh insights |
| **Local repo path** | `/Users/reeseoliver/clairvoyance-backend/` |
| **Mobile repo** | `MercMink21/Clairvoyance-backend-mobile` |

**ALWAYS link to `/app.html` directly** — never the root URL.

### ⚠️ Local repo is diverged from origin — needs attention
As of this session, the **local** checkout at `/Users/reeseoliver/clairvoyance-backend/` is **198 commits ahead and 92 commits behind** `origin/main`. The "ahead" commits are almost entirely stale local-only `live: HH:MM MT scores` commits from Aug 15–18 that were never pushed; the "behind" commits are real work (StatMuse refreshes, CFB refreshes, social-card state, plus the Aug 20 `2e432aec` ATP/WTA Elo fix) that GitHub Actions pushed directly to `origin/main` without the local clone ever pulling. **Before making any local edits to `docs/app.html` or scripts, run `git pull --rebase origin main` (or resolve the divergence deliberately) — editing on top of the stale local `HEAD` risks reverting 92 commits of automated + manual work.** This is very likely also why the earlier request ("just loading and not going") felt confusing — the local working tree does not reflect what's actually live.

---

## 2. File Structure (current)

```
docs/
  app.html              # 32,202 lines — full SPA, SOURCE OF TRUTH
  index.html             # IDENTICAL copy of app.html — always kept in sync
  data.json               # ~1.5MB — live sports data, all 19 leagues
  picks.json               # permanent bet history (local copy stale — see §1)
  version.json
  live_data.json           # live in-game scores (~45s refresh)
  engine_performance.json   # daily snapshot for landing page
  pick_of_day.json
  social_copy.json
  cfb_teams.json / cfb_power.json / cfb_schedule.json / cfb_team_stats.json
  mls_schedule.json / mls_stats.json / mls_opta_stats.json
  pl_opta_stats.json / bl_opta_stats.json / ita_opta_stats.json   # Premier League, Bundesliga, Serie A Opta stats
  soccer_fbref.json
  statmuse_data.json
  sw.js                   # self-destructing service worker (see §3)
scripts/                  # 24 Python scripts, ~13,700 total lines
  clairvoyance_update.py       # 5,762 lines — master data fetcher
  validate.py                   # 915 lines — pre-push validator
  content_generator.py           # 1,138 lines — social copy (write_social_json)
  generate_social_cards.py        # 1,197 lines
  auto_lock_settle.py              # 659 lines — server-side lock/settle, Supabase ledger
  update_wnba_props.py / rebuild_wnba.py / rebuild_wnba_v2.py / fix_wnba_perf.py
  fetch_nfl.py / fetch_cfb.py / scrape_opta_stats.py / fetch_statmuse.py
  generate_card.py / generate_pinned_card.py / generate_video_reveal.py / generate_social_assets.py
  live_tracker.py / backtest_calibration.py / suggest_weight_adjustments.py
  sync_server.py / send_adhoc_email.py / mobile_transform.py / inject_sim_tracker.py / log_june9_bets.py
.github/workflows/         # 21 workflows (was 2 in Session 8)
  scheduled-refresh.yml       # 09:00/15:00/23:00 MT full refresh
  auto-lock-settle.yml
  cfb-schedule-daily.yml / cfb-stats-weekly.yml / cfb-rankings-weekly.yml / cfb-roster-monthly.yml
  nfl-schedule-daily.yml / nfl-stats-weekly.yml / nfl-props-daily.yml / nfl-injuries-daily.yml / nfl-roster-weekly.yml
  nba-props-daily.yml / nhl-props-daily.yml / wnba-props-daily.yml
  opta-soccer-stats-daily.yml
  statmuse-daily.yml
  social-cards-daily.yml
  pages-deploy.yml
  mobile-sync.yml
  manual-sync.yml
  adhoc-email.yml
CLAIRVOYANCE_BUILD_SUMMARY.md
CLAIRVOYANCE_SESSION_CONTEXT.json
```

### Script Architecture (CRITICAL — unchanged from Session 8):
app.html has THREE script blocks:
1. Script 1: tiny inline (0 chars)
2. Main script — functions defined at script-global scope BEFORE DOMContentLoaded
3. Standalone script — Simulator + Tracker + WNBA render functions

**IMPORTANT:** Functions defined BEFORE the DOMContentLoaded callback are at script-global scope.
Functions INSIDE the DOMContentLoaded IIFE are scoped to it.
Standalone script (Script 3) functions assigned via `window.*`.
**NEVER declare `function` inside a `catch` or `try` block** — TDZ interaction with outer `const`.
**window.showBetPopup / window.closeBetPopup** — defined in IIFE, NOT in `_exp` array (would overwrite with undefined).

---

## 3. Tech Stack

- Frontend: Vanilla JS/HTML/CSS — single file SPA, NO build step, NO npm
- Fonts: Orbitron (--orb), Share Tech Mono (--mono), Exo 2 — unchanged
- Backend: Python 3 (`clairvoyance_update.py`) via GitHub Actions — now 21 scheduled workflows instead of 2
- Hosting: GitHub Pages (`docs/` folder)
- **NEW: Supabase** — mirrors the bet ledger for real server-side automation (`0bf44a0a`). `auto_lock_settle.py` now locks and settles picks server-side, independent of any browser being open, and emails a daily "personal daily locks" digest.
- No service worker: sw.js self-destructs on every load (unchanged)

---

## 4. Design System (CSS Tokens) — unchanged

```css
--void: #010006  --nc: #00f0ff  --hc: #ff2090  --vc: #bbff00
--ic: #6690ff    --pc: #f000ff  --gc: #ffdd00  --mc: #ff7700  --rc: #00ffaa
--orb: 'Orbitron', sans-serif
--mono: 'Share Tech Mono', monospace
```

---

## 5. Sport Panes & Navigation (current — verified against live app.html)

Top nav (rendered live): **HOME · OVERALL · ANALYTICS · BASEBALL · BASKETBALL · FOOTBALL · HOCKEY · SOCCER · TENNIS · SIMULATOR · PARLAY · SOCIAL · NEWS**

(Note: TRACKER is no longer a separate top-level tab — the Trainer tab that briefly existed was removed in `384641dd`. PARLAY was consolidated to a single top-level tab and removed from individual sport sub-navs in `122b39de` / `60d19068`.)

| Pane | Leagues/Sub-tabs |
|---|---|
| BASEBALL | MLB (Picks/Props/Parlay/NRFI/Live/Stats/History/Model/Config) |
| BASKETBALL | NBA, WNBA, **CBB (new)** |
| FOOTBALL | **NFL (new, full build)**, **CFB (new, full build)** |
| HOCKEY | NHL, PWHL, NCAAH, KHL, SHL, Liiga |
| SOCCER | **Premier League, La Liga, Bundesliga, Serie A, MLS, Champions League (all new)** — World Cup 2026 built out fully then archived after conclusion (`f238b48b`) |
| TENNIS | ATP/WTA split throughout; Wimbledon 2026 built out fully (draws→Final) then archived winners-only (`5e459d52`) |
| ANALYTICS | full 20-league coverage, By League and By Player tabs (`f4fc7bc1`) |
| NEWS | expanded to all 16 tracked leagues (`fd349ffc`) |

### T() sport keys currently wired: `mlb, nba, wnba, cbb, nhl, ncaah, khl, shl, liiga, pl, liga (La Liga), bl (Bundesliga), ita (Serie A), mls, cl (Champions League), ten, live, ovr, news, social`

### CSS Design Tokens — unchanged from Session 8, still in effect.

---

## 6. Major New Sport/League Builds (Session 9)

### CFB (College Football) — built from scratch, full-featured
Was "Coming Soon" in Session 8. Now has: conference/team roster builder, AP Top 25 + FPI/Resume/Efficiencies scraper, team stats (offense/defense/special teams), full weekly schedule scraper (all weeks/conferences, real lines), MC simulation engine (15K sims), team-specific home-field advantage, real per-venue weather (heavy-snow total impact tuned -2.5→-6.5), MLB-style adjustable MODEL tab, pick locking + settlement, and recurring automation (4 dedicated workflows: schedule-daily, stats-weekly, rankings-weekly, roster-monthly).

### NFL — built from scratch, full-featured
Phase 1: scraper, MC sim, Games/Props/Model/Config tabs. Then: preseason games, 3-tab matchup radar, weekly roster cadence, analytical player props (passing/rushing/receiving/TD, matchup-adjusted) with real per-game defensive data. Server-side scheduled refresh for props/injuries/schedule/roster/stats.

### 5 Club Soccer Leagues + Champions League — built from scratch
Premier League, La Liga, Bundesliga, Serie A, MLS all added with dedicated Opta-scraped team stats (replacing earlier hand-estimated xG), daily automated scraping (`opta-soccer-stats-daily.yml`), MLS additionally gets passing/pressing/sequence data (not just xG/xGA) and injury-adjusted xG. Champions League added to dashboard/Analytics/Simulator.

### World Cup 2026 — full lifecycle
Built out completely (groups → R32 → R16 → QF → SF → Final, live ESPN score wiring, Asian Handicap lines, standings), then fully archived/removed from the UI after conclusion (`0a01c051`, `f238b48b`) once the tournament ended.

### Wimbledon 2026 — full lifecycle
Built out completely (R1 64-match ATP+WTA draw → Final, Tennis Abstract Elo sync, Match Charting Project tactical stats, grass-specific serve/return stats), then archived to a winners-only view once concluded (`5e459d52`).

### CBB (College Basketball) & NCAAH — added
Added to basketball nav dropdown and filter dropdowns; unified card design across WNBA/NFL/CFB/CBB with the existing MLB/NBA/NHL/soccer template (`0bccdf06`).

---

## 7. Backend / Infrastructure Additions

- **Supabase integration** (`0bf44a0a`) — mirrors the bet ledger for real server-side automation, independent of the browser.
- **Server-side auto-lock/auto-settle** (`b048960c`) with a personal daily locks email.
- **Security fix**: the odds API key was being leaked client-side; moved WNBA/NFL/CFB odds fetching server-side (`ab4be84c`).
- **CLV automation engine** (`0d9c66d2`) — auto open/close line snapshots, ESPN odds polling, daily event summary.
- **StatMuse insights integration** (`162ae6c6`) — per-game insights on CFB/NHL/soccer cards, split per soccer league, daily scheduled refresh.
- **Post-deploy verification** hardened repeatedly to cover every league in `data.json`, not just the original 5 (`a0ba7f7f`, `91dd7a4d`).
- **Workflow reliability fixes**: fixed ESPN 403s that were blocking the CFB/NFL pipeline for days (`4739d2b2`), fixed git-push races causing daily Action failures (`6a05258e`), fixed queue-starvation from Pages+mobile-sync firing on every push (`5741dda4`, `1f985667`).
- **Recalibration / adaptive learning engine** expanded to cover soccer, tennis, NBA, and the 5 club soccer leagues (previously gaps existed silently).
- **The Odds API integrated** (`7af7fd12`) for accurate live odds across all sports, replacing earlier ESPN-only/hand-estimated odds in places.
- **Simulator expanded from 6 to 14 sports** (`e3031022`), covering all real teams via live ESPN data instead of hardcoded lists.
- **Cross-device pick sync** (phone ↔ laptop) added via Supabase pull-back (`b0651825`), with a follow-up fix for stale picks reappearing after removal across devices (`2691ca4a`).
- **Postgres backend detail**: `aac38f51` normalizes the managed-Postgres `DATABASE_URL` to the `asyncpg` driver — confirms there's a Postgres instance behind the Supabase-mirrored ledger, not just Supabase's own API.
- **Tier Calibration report** (`6ff2d826`) — backtests PREMIUM/OPTIMAL/LEAN grade tiers against real results.
- **PWA home-screen icon** switched to `StandardLogo2` branding (`8c25c180`).
- **Export improvements**: PNG social-card exports now use `showSaveFilePicker` to save directly to Desktop (`7570e48f`), and mobile exports save to Photos via the Web Share API (`270a93a9`).

---

## 8. Model / Engine Improvements

- **MLB**: real Statcast sabermetrics (xwOBA, barrel%, hard-hit%, xSLG) wired into the actual probability model (`d07c2996`); MC sim count 5K→15K; batter rosters added closing the injury-integration gap for position players.
- **Injury-adjusted win probability** rolled out MLB → WNBA → soccer/MLS (3-part priority series).
- **Radar charts**: MLB matchup/offense/pitching, NBA/WNBA matchup, CFB/NHL/soccer offense/defense breakdowns — all wired to the same live data the simulators use (not separately-fetched stale data).
- **Recommended (model) line vs. real market line** display rolled out across MLB/NBA/NHL/WNBA/soccer/NFL player props.
- **Half-point (.5) line forcing** on spreads/O-U applied consistently across MLB, NHL, NBA, WNBA (was previously WNBA-only, fixed piecemeal after several regressions).
- **NBA severe coverage bug fixed** (`4e932a92`): `nbaMC()`/`nbaGetBayes()` only worked for 4 hardcoded teams — the other 26 were silently getting a coinflip probability. This was a real correctness bug, not cosmetic.
- **Real roster scrapers** added for NBA/NHL/WNBA with lookup/audit helpers, replacing hardcoded team subsets.
- **NHL**: real live MoneyPuck data replacing a stale 4-team static table; all 32 teams populated from real standings (was previously only 4 hand-curated).
- **Tennis**: given its own adaptively-tuned ensemble anchored on player Elo (previously borrowed logic).
- **3-sentence minimum ENGINE REASONING** enforced across all sports' picks and player props (`95e81a83`).

---

## 9. Major Bugs / Near-Outages Fixed

These are worth flagging distinctly since several of them are "the whole app was down" class incidents:

| Incident | Fix |
|---|---|
| **Entire app failed to load** — pre-existing quote-escaping syntax error in the World Cup bracket broke the whole main script | `3bed3d30` — fixed + verified end-to-end in browser |
| **Blank page on load** — JS syntax error in `tbdCard` | `0093fd35` |
| **WNBA engine completely killed** by a JS syntax error (apostrophe in a player name, orphaned prop data) | `ae73e42c`, `c5903af7`, `398be423` — WNBA was rebuilt twice this session (`48df1b0d`, and again later) |
| **CSS animation overriding JS `endSplash`**, causing an infinite service-worker reinstall/reload loop | `a8b8c946` — flagged "Fix critical" in the commit itself |
| **Server-side settlement bug**: moneyline bets never matched, and only NBA/MLB/NHL were even covered by the settlement path | `08abf598` |
| **Permanent-wipe bug**: deleted picks kept coming back because 3 separate sync paths (seed IIFEs, GitHub sync, local sync) would silently restore them | `8c8331e25`, `9b3843b5`, `1d71f2ca` — required a wipe-ID blocklist across all 3 paths |
| **`lockPick` TDZ bug** was silently dropping all locked bets | `d8174de7` |

---

## 10. Removed / Retired Features

- **MLB player props** — retired (`22a9cb9c`), then briefly regressed (NBA props got accidentally deleted alongside it in `b4dd4271`, restored).
- **Trainer tab** — added (`5804aa0b`, MC analysis/backtest/error reasoning for NFL/CFB/CBB/NBA/NHL) then removed in the same session window (`384641dd`).
- **Free Pick of the Day** — removed entirely (`66b408de`).
- **Pick Queue** — removed after being patched for coverage gaps multiple times (`38db69e8`).
- **PARLAY sub-nav duplicates** — consolidated to one top-level PARLAY tab, removed from individual sport dropdowns.
- **Mobile bottom nav** — removed at every screen size (replaced with the existing dropdown nav pattern).
- **Splash screen decluttered**: removed "Tap To Enter" box, crosshair reticle, scan-sweep line, slam animation on bet-lock popup title.
- **All emoji removed** from engine UI across every sport/tab (`afbcede5`, `42dad2e0`).
- **Platform name references and PrizePicks branding** stripped from bet history/display code — display is now platform-agnostic.
- **NCAA Baseball** removed from the MLB nav dropdown, then **purged from the engine entirely** alongside **F1** (`1c7f5390 Purge NCAA baseball and F1 — no longer tracked in the engine`). F1 was a top-level nav tab as of Session 8 (§ Navigation Structure) — it no longer exists. Do not reference F1 in future work unless explicitly asked to re-add it.
- **Pick Queue** — actually built twice: added as an automated multi-sport candidate scanner (`9a6cd00f`), patched for coverage gaps twice, then removed (`38db69e8`) in favor of the current always-on scanning approach.
- **CLV Tracker** — was its own Tracker sub-tab, later folded into Overall (`68765a20 CLV→Overall`).
- **World Cup 2026 and Wimbledon 2026 UI** — see §6, archived/removed after each tournament concluded.

---

## 11. Social / Content Automation

- **Daily social cards pipeline** (`social-cards-daily.yml`) generating Intel Brief cards, Track Record cards, Sport/League Performance cards — see [[project_intel_brief_design_spec]] and [[project_track_record_card_spec]] for locked visual specs.
- **Intel Brief tiers**: simplified to PLUS + INSIDER (Base 1.0 tier removed).
- **Recap emails**: video format for Instagram, still image for X; static PNG milestone cards dropped in favor of dynamic video reveal generation (`generate_video_reveal.py`).
- **Milestone / Since Launch emails retired**, replaced by a still image on the Event Performance card.
- **StatMuse daily refresh** workflow feeding per-game insight blocks.

---

## 12. Pick Record (current, from live site — Session 9)

As rendered live on `app.html` (Aug 20, 2026, late evening MT):

| Window | Record | Win% | Units |
|---|---|---|---|
| Today | 0W-0L | N/A | N/A |
| Yesterday | 19W-5L | 79.2% | +12.0u |
| Rolling 7D | 69W-25L | 73.4% | +32.5u |
| This Month (Aug 2026) | 205W-84L | 70.9% | +82.2u |
| Last Month (Jul 2026) | 139W-35L | 79.9% | +83.1u |
| Since Launch (Jul 1, 2026) | 344W-119L | 74.3% | +165.4u |
| All Time | 736W-247L | 74.9% | +371.7u |

998 picks locked, 983 settled overall.

**Note:** the local `docs/picks.json` in the repo checkout is stale (last modified June 10, shows only 240 bets) — this is a symptom of the local/origin divergence in §1, not a data-loss issue. The authoritative numbers are what's live on GitHub Pages / what GitHub Actions has been writing directly to `origin/main`.

---

## 13. Known Issues (Session 9 status — re-verified against current code)

| Issue | Status |
|---|---|
| `write_social_copy` import mismatch | **RESOLVED** — `content_generator.py` now correctly exports and is called as `write_social_json` |
| Football tab "Coming Soon" | **RESOLVED** — NFL and CFB are both fully built (§6) |
| Local repo diverged from origin (198 ahead / 92 behind) | **NEW, OPEN** — see §1, needs a deliberate rebase/resolve before next local edit session |
| Local `docs/picks.json` stale | **NEW, OPEN** — consequence of the above; pull before trusting local pick counts |
| CNAME / `clairvoyanceengine.info` Talos spam flag | **UNVERIFIED** — carried over from Session 8, status not re-checked this session |
| Linemate Playwright — desktop only | **UNCHANGED** — GitHub Actions still uses `--no-linemate` |
| `nfl_*.json` files 404 on live site (teams/schedule/standings/team_stats/player_stats/injuries/transactions) | **NEW, OPEN** — observed live on `app.html`; app.html requests these filenames but they don't exist in `docs/`; doesn't block page render but NFL tab likely has no backing data on the live site despite the engine being built server-side. Worth checking whether the NFL data pipeline is writing to different filenames than the frontend expects. |

---

## 14. Session 9 Commit Log (representative — see git log for full 646-commit detail)

The full commit history is in git (`50f37f5..origin/main` on the `clairvoyance-backend` repo). Categories and counts of substantive (non-automated-refresh) commits:

```
WNBA:                71 commits
Social/cards/email: 138 commits
Settlement/lock/auto: 63 commits
Workflow/infra:       64 commits
Tennis/ATP/WTA/Slams: 61 commits
Soccer/WC/MLS/leagues: 61 commits
MLB:                  54 commits
NHL:                  39 commits
CFB:                  30 commits
NBA:                  25 commits
NFL:                  18 commits
Merges:               18 commits
Radar charts:          7 commits
StatMuse:              4 commits
(Categories overlap — a commit touching WNBA+NHL+MLB counts in all three)
```

Representative highlights already detailed in §6–§10 above. For the raw list, run:
```bash
cd /Users/reeseoliver/clairvoyance-backend
git log 50f37f5..origin/main --oneline
```

---

## 15. Critical Architecture Rules (carried forward, still in effect)

1. app.html is SOURCE OF TRUTH — always write both app.html AND index.html
2. NEVER re-enable service worker
3. NEVER use agents for large edits — use targeted Python string replacement
4. ALWAYS validate before pushing: `python3 scripts/validate.py`
5. seedBetHistory() IIFE must survive every push
6. One `let LOCKED_PROPS` — never re-declare
7. One `const _origSaveP` — patched once only
8. `renderHomePage()` + `endSplash()` must be in DOMContentLoaded init block
9. `#app` must never start with `opacity:0`
10. Always copy app.html → index.html
11. Standalone script AFTER main `</script>` but BEFORE nav dropdown HTML
12. WNBA render functions live in STANDALONE script (Script 3) — assigned via `window.*`
13. `window.showBetPopup` / `window.closeBetPopup` — in IIFE, NOT in `_exp` array
14. `T(sport, tab)`: always pass sport='nhl' (not 'hk') so render block fires and ai-class applies
15. `mn8` (WNBA mobile nav) must be inside `nba-wnba` subp — NOT `nba-nba`
16. **NEW (Session 9):** Before local edits, resolve the local/origin git divergence (§1) — GitHub Actions pushes directly to origin and the local clone can silently fall behind by dozens of commits.
17. **NEW (Session 9):** NEVER put credentials/API keys in client-side JS — the odds API key leak (§7) shows this has happened before; fetch anything requiring a secret key server-side in Python and write the result to a JSON file the frontend reads.

### Template Literal Safety (CRITICAL, unchanged):
- NEVER put a literal newline byte inside a JS string literal
- Validator catches `chr(39)+chr(10)+chr(39)` pattern automatically

### Block-Scoped Function Declaration Safety (CRITICAL, unchanged):
- NEVER declare `function foo(){}` inside a `try`, `catch`, or `if` block
- Causes TDZ interactions with outer `const` bindings → runtime crash (this caused at least 2 full-app-down incidents this session, §9)

---

## 16. Safe Edit Protocol (unchanged)

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

## 17. Git Push Workflow (updated — resolve divergence first)

```bash
cd /Users/reeseoliver/clairvoyance-backend
git fetch origin
git status -sb    # check ahead/behind counts before doing anything else
# If diverged (see §1): decide whether local-only commits are worth keeping
# (they were mostly stale "live: scores" — usually safe to reset local to origin/main
#  after confirming no real uncommitted work would be lost)
git add docs/app.html docs/index.html
git commit -m "feat/fix: description"
git pull --rebase origin main
git push
# data.json conflict: git checkout --theirs docs/data.json && git add docs/data.json && git rebase --continue
```

---

## 18. Session Start Checklist (updated)

```bash
git fetch origin && git status -sb   # NEW: check divergence first
git pull --rebase origin main         # NEW: resolve before editing
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

## 19. Session 8 Commit Log (reference — see original for full context)

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

(Session 5–7 logs omitted here for brevity — see git history or prior versions of this file.)

---

## Appendix A: Full Session 9 Commit Log (chronological, oldest → newest, non-automated only)

Every substantive commit between `50f37f5` (Session 8's last commit, Jun 9 2026) and `origin/main` `ada2a78c` (Aug 21 2026), in chronological order. This excludes only the fully-automated, self-explanatory refresh commits (see Appendix B for their counts). 646 commits.

```
b2438ff2 docs: Session 8 build summary + context — news rebuild, bet popups, WNBA full rebuild, bet history tools
48df1b0d feat(wnba): full rebuild — delete broken sub, clean NBA-mirrored WNBA tab
ae73e42c fix(wnba): fix JS syntax error that killed entire engine + rebuild WNBA correct
b27ca009 data(picks): log June 9 actual results — 15W WNBA debut, 2L NHL PP
21c11e5d sync: on-demand refresh 2026-06-10 06:10 UTC
9a88d38e perf(wnba): fix lag — cache results, remove 5K MC loop, fix double-renders
489e2acd fix(analytics): load BetAnalyticsLab on first tab click instead of hidden MLB render
af4f771f fix(mlb): fix 4 broken hidden tabs + add PICKS/PROPS/NRFI/STANDINGS/HISTORY to MLB nav
9565f396 fix(layout): move #app closing tag to include all spanes
a3bdf8f7 fix(layout): close sp-analytics div + add cvGuard visibility system
f401687e fix(mlb): remove NCAA Baseball sub tab from baseball nav
6500e6f4 data(june9): import June 9 bet results + adjust sport/prop performance
630e839a feat(parlay): unified sport parlay builder + tracker pending-only filter
d3e97376 Add 103 historical bet entries to reach 177W-40L baseline; fix WNBA split-screen, cvGuard rewrite, setSub/T() fixes
6840106b Fix Overall ALL BETS, ADAPTIVE, SYNC tabs not rendering on click
1a3fe81b Add PARLAY to period performance bet type; fix NHL Tonight showing stale hardcoded games
b2282242 Add cross-sport parlay builder in Tracker; fix NHL/NBA/WNBA prop data in parlay tabs
d907e5bd Strip PrizePicks branding from bet cards; fix same-day bet grouping; add year filter to history archive
c76c9d04 Fix sport tags in pending/home sections and parlay lock sport assignment
0464bdcb Add linemate NBA/WNBA props integration, fix WNBA today date fetch, add Toronto to WNBA map
6a0d51c9 sync: on-demand refresh 2026-06-10 23:05 UTC
7612541d Update NBA Finals G4 props and series context for SA at NYK @ MSG
e47c0449 Fix WNBA loading error, add 35 player props for TOR/CON and SEA/LA
7e8c1945 Fix WNBA abbr map (LAS→LA Sparks), add nuclear game fallback, expand team name mappings
cfa1ca20 Expand NBA props: 46 props across all stat types, remove slice caps
f36cc7da Build World Cup 2026 module with full group stage, match schedule, and player props
77b28733 Fix all engine timezone references to use Mountain Time (America/Denver)
48211f30 Add World Cup to simulator, parlay builder, and analytics; fix Soccer tab display
564afe7a Fix WC simulator teams showing MLB fallback; fix soccer tabs not rendering
4dbde2a8 sync: on-demand refresh 2026-06-11 06:07 UTC
febe47e6 Log June 10 2026 PrizePicks bets — 3 wins 1 loss NBA/WNBA
f8e34157 WC26: replace all group/schedule data with real ESPN fixtures, add live ESPN API fetches
5a96b9c6 Add WNBA as standalone sport in Engine Performance By Sport section
2f29c46c WC26: render matches/groups instantly, ESPN overlay in background
46422610 Home: replace engine performance chips with 6 period cards (Today/Yesterday/7D/Month/LastMonth/AllTime)
9da3576d Fix engine performance cards: correct arg order and match Overall tab calcPerf exactly
ff4d9927 Add ENGINE OPS tab to Overall: prop refresh, stat update, schedule check per sport
23270836 Social: add exportable 1080x1080 performance graphics to Track Record (Today/Yesterday/7D/Month/LastMonth/AllTime)
8bb3266d Fix export PNG: store periods in window var, use index onclick, add roundRect polyfill
2bceb600 Remove Series Sim sub tab from Social tab
58e5ef79 Fix export PNG download — use toBlob+createObjectURL, append to DOM, save to social posts folder
7570e48f Export PNG: use showSaveFilePicker to save directly to Desktop
7372ab7e Fix export PNG: acquire file handle in user gesture, add export success popup
abcea2cf Restore date/month removal bar in All Bets tab; refresh engine-wide on removal
59a6ac3b force redeploy
1d71f2ca Fix wipe picks: push removal to GitHub picks.json so reload doesn't restore deleted bets
9b3843b5 Permanent wipe blocklist: prevent all 3 sync paths from restoring deleted picks
8c331e25 Fix permanent wipe: filter wiped IDs in getP() and saveP() — blocks seed IIFEs from restoring deleted picks
867f4982 Fix wipe month label: parse year/month directly to avoid UTC timezone rollback
3da9ba4d MT timezone: all date parsing/period boundaries/trend groupings use getMSTNow/mstMonthKey
95e81a83 3-sentence minimum ENGINE REASONING across all sports: MLB, NHL, NBA, WNBA, Tennis picks + player props
b6613f40 Fix World Cup tabs: pre-render all WC content on page load
3cb9ce11 Fix World Cup tabs: convert const data vars to var to allow updates
50b4a130 Add Over/Under lock buttons to each WC match card
bfc13a0e Add Soccer sport + World Cup league across dashboard and engine
0c353ebf Add World Cup to Engine Ops schedule check/refresh
5bc98dc4 Fix all nav dropdown menus to show complete sub-tabs
28b4df81 Remove NCAA Baseball from MLB nav dropdown
795d0295 Add PARLAY top-level tab and fix Analytics dropdown
e68afe35 Match WNBA Today game cards to MLB card layout
878573a1 Refresh NHL and WNBA player props for June 11 2026
d1b688db Add adjustable line input to all player prop LOCK buttons
55b99c53 Add line adjuster to parlay builder prop panels (WNBA props + xp-props-list)
cc88a3cc Add CLV Tracker sub-tab to Tracker with line movement logging, prop staleness warnings
0d9c66d2 Add CLV automation engine: auto open/close snapshots, ESPN odds polling, daily event summary
4a2a522e Add Engine Recommended Parlays section to Parlay tab with 5 auto-generated cross-sport slates
1b035f3a Fix cvParlayCalc TypeError: cast p2ml() result to String before .replace()
42dad2e0 Remove all emoji from engine UI; make units prominent in Track Record cards
4e7bda45 Add FOR THE MOON parlay slate — 6-8 legs, high prob + high payout
76865b2c Remove soccer ball emoji from WC26 button in parlay builder
5ed75a3e Add full standings table to WC26 Groups tab with daily caching
aaa6860c Add exportable CSV spreadsheet for bet log and ROI tracking
1e6c2830 Overhaul CLV tracker — full automation, all sports, 3-point timeline
2960dc34 sync: on-demand refresh 2026-06-12 06:03 UTC
a65eac58 Enhance MLB O/U model + add ±0.5 line adjuster to all sport game cards
e5d3624a Add June 11 2026 results to history — 4 parlays + 19 individual picks
fc295752 Remove all platform name references from bet history and display code
7b83c755 Remove duplicate player entries for 6/11 — Bueckers and Wilson each appear once
c7347026 Add W/L per-leg indicators to parlay cards in All Bets history
1961b16f Add ±0.5 O/U adjuster to all sports and player props
42ea2592 Fix parlay leg W/L accuracy, units NaN, and WC decOdds bug
f4110bb4 Add WC Standings tab with live ESPN data and 11pm MT auto-refresh
63ddf56a feat: multi-step O/U adjustor, OVER+UNDER buttons for all sports, WC time fix
f7214387 fix: add O/U adjustor input+OVER+UNDER to WC match cards
d123e63a feat: WC parlay tab, AH spread, WNBA 6/12 props, O/U parlay fix, settled bet guard
fa2c03fa Add spread adjustor widgets (all sports) + fix WNBA 6/12 props
60c3fd17 Add adjustable spread widget to WNBA parlay game cards
f87307c0 Fix seedBetHistory wiping locally-settled bets on every page load
28ef1b83 Settle all pending NBA Finals G3 props + G1 Bridges prop in seed data
48473889 Redesign intel cards: square grouped-by-sport + real PNG export
3ab61ccc Intel Briefs: two tiers, square cards, real PNG export, fix broken exports ref
b99d2b16 Redesign intel brief + track record cards for social export
7af7fd12 Integrate The Odds API for accurate live odds across all sports
606e6220 Polish intel brief cards: Orbitron throughout, tier title, social handles
acfc493f Fix engine crash: remove duplicate const tm in exportLeagueCard
24fe267c Add duplicate-decl and cross-block-ref validation checks
cf3f4d34 Replace util buttons with single Export Bet History
e4ee7538 Import bets modal, fix sport mislabeling, mobile improvements
ca085f01 Add IMPORT BET button to home page
ff4700a6 Full team name display — eliminate all abbreviation ambiguity
88ca12c4 Fix _gameTitle/_teamName ReferenceError by moving to true global scope
35c9a662 Fix MLB/NHL team name collision — full names stored, unambiguous sport detection
811c3ab6 Expand all team abbreviations to full names at every display point
77ce7a6e Update NBA Finals to G5 (NYK leads 3-1) and WNBA to June 13 props
398be423 Fix JS syntax error from orphaned G4 props and correct WNBA matchups
17690a43 Add line adjustor to renderNBAFinalsProps cards
03610051 Add line adjustor to parlay builder NBA props + NBA Finals in rec parlays
e43e45bc Add June 11-12 bet results: WC MEX vs RSA (4 soccer props) + WNBA GSV@SEA & TOR@WAS (3 slips, 11 props)
96325dd2 Add NBA Tonight game lines to engine parlay leg pool for June 13
23e22a3e Fix parlay leg W/L display: add 'Name MISS' pattern to _parlayLegs parser
f0ae488b Add June 13 pending parlays: 6-pick WC+NBA G5 and 4-pick WNBA (no Bueckers)
e588fdf7 Fix MLB sport detection and WNBA team name aliases
2aa929e5 Fix team name display in home page and all bets history
737d2e78 Comprehensive team name map — all sports full names
7fabea12 Fix MLB history tab showing raw team abbreviations
abb84399 Fix MLB pick cards showing raw team abbreviations
afbcede5 Remove all emoji from engine UI across every sport and tab
74e52268 Fix fatal SyntaxError from emoji-removal leaving string++identifier patterns
c156f5ca feat: daily WNBA player props auto-refresh
91b4a880 feat: NHL SCF G6 props, MLB/WNBA spread+OU analysis, parlay daily refresh
2b507505 feat: track record + intel brief card redesign
93639389 fix: track record card even column spacing via CSS grid
9a57b542 feat: track record period labels → neon purple + sport performance card
6342eaaf feat: card cleanup — TOTAL row, no dates in footers, cyan date on intel cards
11c02608 fix: remove W/L badges from parlay leg rows in All Bets
430c36a2 feat: MLB daily player props tab (Hits/Ks/HRR), parlay integration, dropdown cleanup
60aceb15 Fix settlement date guard, redesign WC match cards, remove WC Picks tab
7a230e04 Track record + sport perf card color and footer updates
9e958517 Intel brief card redesign: colors, footer URL, insider=props only
d87fbe22 Fix MLB props population and WC standings live data
27ca2495 Fix settlements, tier rename, insider cards, rating labels
961b7d14 MLB player props: real player data from MLB Stats API, add HR stat type
ec82d6a7 Fix pending bets not appearing after lock
2134cfd9 Parlay tab: replace static engine parlays with daily dynamic slates
ec8b7966 Remove stale NHL/NBA PROPS_DATA from engine parlay leg gatherers
d8174de7 Fix lockPick TDZ bug dropping all locked bets; fix settlement cross-game matching; add Daily Briefing; simplify header; bump font sizes
68262961 Move MT/ET clocks to flank date in header; expand header height to 72px
cc0692af Add separator dots and spread MT/ET clocks in header
76dda85c Enhance Daily Briefing: stat pills, streak/hot-sport tags, corner accents, top signals grid
46234766 Larger header dots; seed 15 MLB bets 6/15/2026 (12W-3L)
09083c12 Bigger glowing header dots; enlarge splash subtitle font size
3f4566c5 Enlarge splash wordmark and loading bar
3e4b106f Extend splash to ~2.6s; bar fills over 2.4s
ba6714b1 Smooth splash: staggered JS reveals, GPU transitions, clean fade-out
d70ce698 Unify purple to true neon #f000ff across Intel Brief, Track Record, sports perf
71c0da74 Fix Intel Brief/Track Record footer overlap; match splash bg to engine
52810f70 Full neon purple #f000ff on clairvoyanceengine.info in all card footers
551ee0e0 Intel Brief cards: dynamic font size + row count based on pick volume
db995fc5 Intel Brief cards: group picks by tier instead of inline grade tags
85d6fbdc Intel Brief cards: dynamic font scaling accounts for group headers
7f4c80f3 WNBA: update props to 6/17/2026 Commissioner Cup slate (13 props, 6 games)
8dbaaddf Fix WNBA matchup cards: rename forEach param ev->game to stop shadowing ev() function
96bcbc4d Update Intel Brief cards to 2-col grid; refresh all props to 6/17/2026
b41fe597 Compress Intel Brief card header; reduce pick cell font sizes
7dea44bd Intel Brief card: tier in header, sport below-left, centered social handles
bff0b51f Intel Brief card: CLAIRVOYANCE centered, tier top-right, sport+date below divider
0046f72c Intel Brief: add Base 1.0 / Base 2.0 / Insider card tiers
5cbf31a4 Intel Brief card: sport same size as date (6px), both neon pink #ff2090
6111dfde Intel Brief card: sport and date color matches CLAIRVOYANCE (#f000ff)
9f2e130c Intel Brief card: tier label neon cyan (#00f0ff) for all tiers
71d043d0 Intel Brief card: divider line sits flush above social handles
2436c375 Intel Brief Insider: props sourced from typed registry, never inferred
e561446f Intel Brief cards: remove buttons from card, tighten footer, add disclaimer
498c3207 feat: settlement fix, NBA offseason cleanup, grading keys, daily brief, version auto-stamp
68b6dc52 rename: Base 2.0 → Plus on Intel Brief card tier selector
4c1630da remove Base 1.0 from Intel Cards — tiers now PLUS + INSIDER only
68765a20 UI overhaul: offseason messaging, nav cleanup, CLV→Overall, sim history
c64ceebb Intel Brief: add BASE tier, restructure all three tiers with distinct sections
e8966e98 Intel Brief card: lower footer divider line for cleaner social handle spacing
484f800e Intel Brief cards: dynamic footer anchored to last pick row
2962940c Intel Brief tier colors: BASE=purple, PLUS=cyan, INSIDER=gold
97616ad5 sync: on-demand refresh 2026-06-20 02:17 UTC
0e269f60 Enlarge header, move SYNC/SYNC KEY to Overall → Sync tab
c5903af7 Fix JS syntax error from Flaujae apostrophe in WNBA props data
8f7e5be1 Fix apostrophe in player names breaking JS; patch update script
c0ad1298 Refresh WNBA props for 20260623 — NY Liberty @ LV Aces
568d6bec Add CBB sub-tab to Basketball section
a36e89c7 Expand Daily Briefing, Recent Form, Model Calibration, Engine Insights
9b322cda Recalibration engine + MLB best-market reasoning
1b8e97f6 Wire calibration into tier() — active for all sports and bet types
db6abf57 Extend best-market ENGINE REASONING to all sports
9dc717f8 feat: complete WC schedule R2/R3, tennis card overhaul, market scan all sports
936ed40a fix: replace WC26_SCHEDULE round 3 with real FIFA match data (Jun 24–27)
93b027b6 feat: expand LAST 10 recent form to show W/L, bet description, and date
2d3f5f9a fix: WNBA spread labels now show actual line number instead of bare ATS
191a0735 feat: WNBA spread grade now driven by direct MC cover rate from 10k sims
723a6cde feat: Daily Briefing — live top moves, sport counts, grade pills
be31ceea feat: MC cover rate in ENGINE REASONING for all sports with spread markets
0f065ab1 feat: spread/OU in daily brief, correct line labels on game cards, portrait social cards
d545c448 fix: MLB MC sim projects same 5.0 runs for all games due to bad bat.RG from ESPN API
b94bcb55 feat: add MC PROJ bar to all sport game cards (NHL/NBA/WNBA/WC)
52c80f40 feat: MC projections in O/U and spread reasoning for all sports
f2aa45ae remove daily briefing section from home page
de90ec3c Add multi-book lines, Odds API player props, NBA props engine
6916e931 Add CBB to filter dropdowns; rebuild WNBA props with live ESPN+MC
d38c93b6 Add Premier League, La Liga, Bundesliga, MLS soccer tabs + engine
70f19c53 Add CBB to basketball nav dropdown menu
5b9ef481 Add SINCE LAUNCH record (Jul 1) to overall dashboard, home screen, and track record card
9d77ab6f Add subtab flyouts to Soccer dropdown for PL, La Liga, Bundesliga, MLS
9faa6275 Add PL/La Liga/Bundesliga/MLS to dashboard SPORT and LEAGUE breakdowns
60d19068 Remove PARLAY tabs from all sport sub-navs and dropdowns
c977cc85 Integrate PL/La Liga/Bundesliga/MLS into overall, analytics, and social cards
887490fb Dashboard: route PL/La Liga/Bundesliga/MLS under Soccer, always show in leagues
122b39de Remove Parlay from all nav dropdowns (MLB, NHL, Parlay Builder)
220db098 Add CBB sub-row to Basketball history filter
58de1dcc Overhaul dashboard sport/league sections with full sport coverage
35f799f1 Dashboard: remove soccer sub-rows from sport section; all leagues always visible
9bc5dc88 Since Launch box always visible everywhere showing 0-0/N/A pre-July 1
728c1f5c Home page: Since Launch before All Time; All Time spans full width
dcc663c6 Dashboard Overall: add All Time box next to Since Launch in period performance
9956b6d7 Change SINCE LAUNCH period color to neon purple (#f000ff) on track record card
0a008594 Add League Performance social export card with all 19 leagues
aae41af8 Fix Premier → Premier League in leagueMap and league card LDEFS
50bf0893 Fix WC/soccer bets misclassifying as MLB on backend sync
dcdb218d Apply card background to Track Record, Sport Perf, and Intel Brief cards
202805c7 Build out Wimbledon 2026 — draws, picks, futures, schedule
293fe3ca Merge remote data refresh
e968379d Wimbledon 2026: Tennis Abstract Elo sync, forecast-calibrated picks
d5110329 Fix Wimbledon start date: Jun 30 -> Jun 29
c84486a2 Tennis today: O/U sets chip + MC reasoning; Wim draw: 10K MC panels, relabel mens/womens
3cff3913 Fix Wimbledon end date Jul 13->Jul 12; improve Elo surface blend
a80800e4 Add grass-specific serve/return stats to ATP+WTA DB for Wimbledon
ac451315 Integrate Match Charting Project tactical stats for Wimbledon model
00595a8a Integrate W/UFE + MCP stats into tennis MC simulation via tennisServeWinRateAdv
b3303fab Add total games O/U chip, enhance MC simulation depth and card reasoning
ccea30c6 Rename Today→Matches tab; add full tournament round structure with round selector
7ac165e1 Enhance tennis match card reasoning to MLB-style ENGINE REASONING
4540397b Update WC bracket with actual R32 matchups, remove Groups sub tab
76615cdc Add neon magenta glow to all // section labels throughout app
0093fd35 Fix JS syntax error in tbdCard causing blank page on load
edcdae68 Add landing page sections with neon magenta glow headers
298f2e56 Remove landing page info sections from home tab
99de1450 Match all social cards to landing page background style
cf94b300 Match card backgrounds to landing page: diagonal grid + cyan H/V overlay
283fefea Calibrate card backgrounds to match bg.jpg exactly
dd4a91cb Fix WC matches tab, tennis pending refresh, and TBD card display
76215408 Remove WC standings tab; add onclick to tennis O/U chips
032ad93b Comprehensive mobile layout overhaul
63c19999 Expand Wimbledon R1 draw to full 64-match ATP + WTA fields
7641bc87 Home dark horse/premium, dashboard settled counts, WNBA live label
32ea41f4 Convert home picks to oscillating horizontal ticker
44df84a1 Sport/Type/League rows: all stats in neon cyan
9a16fd57 Live yellow label across all sports and tennis sets score
b72662a1 Fix ticker glitch: boundary dwell + direction safety
4ad4112e Fix Wimbledon R1 ATP/WTA draw: ESPN-verified player names
d686f416 Fix imported bets not settling: use string ID prefix
56479e7f feat: add Wimbledon R1 results and dynamic draw system
3ff83130 Sync Wimbledon R1 results from ESPN bracket (Day 1)
ebe17304 Fix Wimbledon pick dates: use actual match date not log date
3bb6c107 Distinguish ATP vs WTA throughout: engine, draw, history, migration
5b1b15b1 Fix ATP/WTA league split in dashboard; expand player databases
6148eaf3 Fix Wimbledon draw accuracy + dashboard TENNIS aggregation
c620d26a Enhance ticker cards: sleeper indicator + premium reasoning section
f85cfe31 Fix pending bets: remove Medvedev -350, sync all-bets tab actions
540e3648 Fix ATP/WTA sport tags, add sleeper reasoning, push all ticker tweaks
880158d1 Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
3449f7e0 feat: soccer in adaptive engine, MLB grade accuracy overhaul
6c016ea3 sync: re-deploy app.html + index.html with updated timestamp
a4d08244 fix: repair JS syntax from unescaped quotes in Wimbledon height strings
55b17498 Wimbledon R2 launch: complete R1 results, R2 draws, pending bets sync
c75fc6de feat: WC bracket updates, Wimbledon R3-Final rounds, tennis O/U fixes, auto-settle
d2eaa335 fix: WC bracket correct R16 pairings + England result, Wimbledon R3-Final display, WTA name fix
9b3e4c99 fix: Wimbledon R3 hardcoded matchups with ESPN results, default to R3 tab
543f003a fix: spread/OU labels, WNBA loading, Intel Brief v2 design, track record aesthetics
7a96a0cc fix: Wimbledon ESPN-style visual bracket, correct R3 matchups (FAA/Zheng, ADF/Fucsovics, Parks/Dudeney)
6cf8d356 feat: fix R3 matchups (ADF basis, Parks/Dudeney basis), simplify Wim draw buttons
a5f0188a feat: ± stepper buttons (0.5 step) on all game-card spread/OU inputs across MLB, NHL, NBA, WNBA, WC, soccer
5c7f951d Fix Wimbledon bracket: crash fix + full rewrite with 16-match R3, Matches view
ebedf580 fix: add _adjV helper and ± stepper buttons to MLB/NHL/NBA spread+OU inputs
5f3a18fd fix: correct Wimbledon R3 matchups and increase bracket readability
f3d9acee feat: proper bracket layout, match cards with ML/OU, WC bracket redesign
06d1e702 fix: tennis MATCHES tab now shows R3 upcoming matches only
9a70e69a feat: analytics overhaul, adaptive all-sports, CL tab, morning calibration, WC 3rd place
419c9dc2 Fix import bet: add outcome/prob fields, soccer leagues, one-time Cilic/Medvedev cleanup
ca02cc49 Fix splash hang, show scores in both brackets, move CL subtab
1fa0f1d1 Expand bet importer: SINGLE / PARLAY / PROP modes, all 6 sports
44f24561 Fix: SINGLE/PARLAY/PROP settle flow — refresh Overall dash + header on WIN/LOSS; show parlay legs in home card
5804aa0b Add TRAINER tab: MC analysis, team/player data import, backtest, error reasoning for NFL/CFB/CBB/NBA/NHL/hockey leagues
41cd6b41 Fix: bulletproof engine load — CSS auto-dismiss, skip button, 7s escape hatch, global error handler, SW force-reload
a8b8c946 Fix critical: remove CSS animation overriding JS endSplash, fix SW reload loop (Date.now was causing infinite reinstall+navigate)
3bed3d30 Fix critical: app never loaded — pre-existing quote-escaping syntax error in WC bracket broke entire main script; also fix undefined renderWCPicks/renderWCProps refs and stray div from earlier trainer insertion. Verified end-to-end in browser.
d4244c05 feat: wire live ESPN/tennis scores into WC and Wimbledon brackets
3460b3db fix: standardize Sport Performance card column to LEAGUE
8f45b8a6 feat: home ticker falls back to all-sports/all-leagues scan
8c25c180 feat: use StandardLogo2 branding as PWA home-screen icon
4c716a96 fix: trigger mobile-sync workflow on icon/card asset changes, allow manual dispatch
42017326 fix: stop MLB/NHL/NBA team criss-crossing in bet classification
270a93a9 feat: save social/perf cards to Photos on mobile via Web Share API
e01d349a style: match all social cards to StandardLogo.png background + unify fonts
aac38f51 fix(backend): normalize managed-Postgres DATABASE_URL to asyncpg driver
4da5301a fix(mobile): scale splash + header clock to fit iPhone (SE→Pro Max)
696e77b5 fix(mobile): regex-match title swap so it doesn't silently fail
d90e080f style: match card previews to PNG exports + uniform 4:5 for X/Instagram
834eb2b3 fix(cards): readable dynamic TODAY/YESTERDAY dates on all export images
156ffb86 fix(cards): recompute periods at export time so saved image reflects TODAY/YESTERDAY
2f5113b4 feat(cards): single-day date filter on Track/Sport/League social cards
8c032ced fix(mlb): round O/U totals to nearest 0.5; trim card period set
2024dce3 revert: restore LAST MONTH and SINCE LAUNCH card periods
76b57b4c feat(wimbledon): odds on propagated R4/QF/SF/F matches + open on current round
5f19f5c0 fix(worldcup): matches tab renders recent results when no upcoming fixtures
9f2eac8a feat(ticker): always run all-sports PREMIUM/OPTIMAL scan (no lock needed)
e2d42af0 feat(ticker): generic cross-sport scanner over any per-sport odds feed
065ddf8d fix(worldcup): request full tournament date range from ESPN, not just today
b3cffa69 fix(rosters): NHL Coyotes relocation -> Utah Mammoth (UTA)
aed33c7c feat(migration): dry-run bet classification audit (writes nothing until approved)
8c7e4f4d fix(parlay): stop silently defaulting generic parlays to MLB
73f904b1 fix: Cilic/Medvedev cleanup, bigger settle alert, spread sign sync on typing
aab8dd20 feat(cards): sport-level grouping, 20 leagues, styling cleanup + soccer date-range fix
f4acee59 feat(wimbledon): combine R3-SF into one match list, remove round selector
0a0641e1 feat(alerts): letter-by-letter WIN/LOSS reveal, bigger box, longer dwell
b9298a67 feat: magenta export buttons, Champions League in Overall dashboard, global text size bump
0fab0619 fix: real Tennis MATCHES tab (renderTennisToday) + alert/UI tweaks
1aec1d80 sync: on-demand refresh 2026-07-06 06:04 UTC
2de7ba05 feat: card period labels/colors, Intel Brief cleanup, enhanced splash, text bump
39e817b5 feat(alert): spell out LOCKED letter-by-letter, same mechanism as WIN/LOSS
c1eb50b8 fix(wimbledon): advance stale bracket state (R3 complete, R4 populated)
f202e9ab Social cards: export button labels, unified intel brief grading, header/row colors, sport-perf league wrap, splash letter reveal + header reticles
8df494d2 Wimbledon bracket: wider branch spacing, fix score-line overlap bug
45e8b6df chore: bump version.json to retrigger failed Pages deploy
a458fece Splash screen: smoother letter-by-letter reveal, lighter glow for perf
edbd85ab World Cup: advance bracket to R16 results, fix stale Matches tab, settle Norway/England R16 wins
85ffb406 World Cup R16 bets (ML), 25K MC sims everywhere, bigger brackets, Wimbledon WTA fix
0d0cda1a chore: bump version.json to retrigger failed Pages deploy
3e115698 chore: bump version.json to retrigger failed Pages deploy
3203313b Splash screen: compress to 6s total, fix wordmark wrap/overflow bug
092dff82 World Cup R16 date fix, bracket resize, tennis match dates, header cleanup, bet history, instant popup
1d50404e Fix Wimbledon R4 bet dates to 7/5, shrink WC bracket further, audit for eliminated-player bug
d498d2c3 Remove slam animation from locked-bet popup title
391d9b01 Self-heal stale Wimbledon R4 bet dates already sitting in localStorage
1158cdae Remove neon-cyan scan-sweep line from splash screen
52ce3ece Fix World Cup O/U sport tagging collision and WNBA spread sign
c5f94ffb Increase font size on social cards, self-heal WC/WNBA bet bugs at load time
6d3eecab Fix Wimbledon bracket to match real R3/R4 results, build out quarterfinals
19887f87 Fix World Cup R32: Argentina played Egypt (not Australia/Cape Verde swap)
b6738434 Correct World Cup: Argentina/Egypt is the R16 matchup, not R32
7d3cc31a World Cup R16/QF results + Wimbledon QF results, build out semifinals
ce1ca6d1 Expand reference-site scraping (MLB fielding, NBA four factors, NHL full-season stats, tennis recent-form) and add FBref-backed soccer league Model/Config tabs
87b2191d ci: temporarily add scoped push trigger to force-run FBref scrape test on GitHub Actions runners
1d130a7c ci: revert temporary push trigger — FBref-403 test on GH Actions runners complete
9a9812da Add ESPN fallback for soccer team stats — FBref blocks both local and GitHub Actions runner IPs with 403
01811bab Add offseason messaging for CL/PL/La Liga/Bundesliga, simplify soccer league sub-tabs to Matches/Bracket/Model/Config
5dfd6081 Add real MLS club stats, standings, and schedule from mlssoccer.com's stats API
48721a58 Fix soccer league tabs (incl. MLS) permanently buffering when selected via league dropdown
326e6e2b Rebuild soccer league match cards to match the MLB/World Cup card design
6caf516c Show match date on soccer league cards for all 5 leagues
0678dbe0 Advance Wimbledon bracket to semifinals: Sinner-Djokovic/Fery-Zverev (ATP), Muchova-Gauff/Kostyuk-Noskova (WTA)
a75f93da Rename TODAY tab to MATCHES across MLB/NHL/NBA/WNBA/CBB
de5e6b5a MLB: 7-day MATCHES window with date filter, dated match cards; fix 2 real bugs found along the way
62a84fff Autonomy + performance infra: failure alerting, post-deploy verification, calibration backtesting, MLS/soccer weather
1042907a Injury integration audit (item 8): document real gaps, add WNBA injury fetch
fd349ffc Expand news/injuries/transactions coverage to all 16 tracked leagues, not just MLB/NBA/NHL/WNBA
dab59820 NBA: extract inline game-card logic into standalone _nbaGameCard() (prep for 7-day window rollout)
e1c58458 WNBA: 7-day schedule window with date filter, added below the existing today-only picks engine
6ddb23d7 NBA: build dormant 7-day-window infra (renderNBAWeek), not yet wired into DOM
7fc0ab4e NHL: extract inline card into _nhlGameCard(), build dormant 7-day-window infra (same pattern as NBA)
7679ff29 MLB batter rosters: closes the injury-integration gap for position players (item 1)
5b4e8424 Soccer leagues: 7-day window + date filter for renderLeagueMatches() (covers MLS/CL/PL/La Liga/Bundesliga); fix filter-day bug affecting all 5 sports
e3156d17 NFL/CFB/CBB: real 7-day schedule + market-odds windows, active now (not dormant)
dd538834 Fix: Wimbledon semifinals now appear in tennis Matches tab (were only visible in Bracket view)
e6d4fba0 WNBA injury-adjusted win probability (item 1, priority 2 of 3: MLB done, WNBA now, soccer next)
d5e97972 Soccer injury-adjusted xG, scoped to MLS (item 1, priority 3 of 3 — MLB/WNBA/soccer all done)
d07c2996 Real Statcast sabermetrics for MLB (xwOBA/barrel%/hard-hit%/xSLG), wired into the actual probability model
d6740552 NHL: wire real live MoneyPuck data into nhlEns(), replacing a stale 4-team static table
4e932a92 NBA: fix severe coverage bug — nbaMC()/nbaGetBayes() only worked for 4 hardcoded teams, silently coinflipped the other 26
e3031022 Simulator: expand from 6 sports to 14, covering all real teams via live ESPN data (not hardcoded lists)
3765bf01 Wimbledon: set SF results and populate men's/women's final - J.Sinner vs A.Zverev
0bccdf06 Unify match card design across WNBA/NFL/CFB/CBB with MLB/NBA/NHL/soccer
79233003 World Cup: add semifinal match cards - England v Argentina, Spain v France
5e459d52 Tennis: archive completed Wimbledon/French Open — winners-only view, drop from Matches
475115d0 Home ticker removed, tennis defaults to Cincinnati, Overall dashboard expanded
1dc034f4 Overall dashboard: revert ENGINE back to SPORT (6-sport rollup), add locked/settled counts to period cards
c7082386 Overall dashboard: bump LOCKED/SETTLED count font size in period cards
574616bd Automation batch: stale-pending audit, prop-matchup validation guard, docstring fixes
cd871cf1 Injury roster coverage for CL/PL/La Liga/Bundesliga, PREMIUM alert threshold 60->70%
76f0de77 Social tab: add streaks + sport/league filter to Performance cards
4c8284ff Social tab: remove streak from Sport/League Performance cards
760f7a1f Social tab: add Event/Tournament Performance card for cross-month date ranges
0aac9f2f Event Performance card: multi-select league filter (e.g. ATP + WTA for Wimbledon)
82c417b1 Fix: Event Performance card export button (ReferenceError, function not global)
0bf44a0a Supabase integration: mirror the bet ledger for real server-side automation
411f6522 Event Performance card: restyle preview to match the other social cards' frame
6105e80a Event Performance card: bigger event name, more space before the rows
c26dfc6e Event Performance card: reorder header, drop visible date range
2b518cd2 World Cup: make Asian Handicap line adjustable by 0.5, like WNBA spread
2f892954 Trivial build-marker bump to retest mobile-sync token
91dd7a4d Post-deploy verification: count WNBA/tennis activity, not just MLB/NBA/NHL
a0ba7f7f Post-deploy verification: cover every league in data.json, not just 5
1c7f5390 Purge NCAA baseball and F1 — no longer tracked in the engine
992169d6 World Cup: fix SF1 date, add 3rd place playoff + Final
ab4be84c Odds pipeline: stop leaking the API key client-side, move WNBA/NFL/CFB odds server-side
2ea6f469 Soccer odds coverage + real Brier score / log-loss calibration metrics
34e28697 Automate daily social card export + email delivery
5e01139c Social cards: 11:30 MT schedule, yesterday's window for sport/league cards
4042cba7 Fix crash in first real Supabase-ledger scheduled run: settledAt type mismatch
a0c8d3d0 Fix two more overallStats/ROI bugs surfaced by real Supabase data
be5d98b2 Add IG/X captions to the daily social card email
4baf3986 Social cards: weekly/monthly recaps, milestone detection, event cards, caption variety
b9d792a1 Add video reveal generation, update events list with real 2026 dates
bc404437 Expand video library: breakdown, milestone, and educational templates
fc2123c2 Video variety: 3 daily styles, dedicated weekly/monthly recap, second milestone style
ba000e3a Fix event league filter, standardize background to StandardLogo.png spec, add grading/subscription/educational content
d12ac3ab Add 5-day rotation content, year-in-review post, fix stat overflow bug
6699dff1 Real canvas-drawn background across all templates, bets-locked stats, units column, scanline color fix
dabcefa4 Wire "covers" static asset into social rotation content
4dfd4025 Move daily send to 9:30 AM MT, make all video footers neon magenta
f03b889c Add glitch-style video to event wrap-up emails
b1420ab2 Send from verified clairvoyanceengine.info domain
4e7d8a46 Revert sender to resend.dev sandbox address
f199c31d Add image-glitch video reveal + one-off email delivery path
c8b4fdf2 Remove scratch asset after ad-hoc send
222955a4 Fix missing units/record/win% in event wrap-up captions
66e499e1 Fix real root cause of missing event units: wrong field name
32305023 Extend covers card glitch video to 10s with mid-hold flickers
7c5037d2 Remove scratch asset after ad-hoc send
8eb7becc Tighten covers card magenta glow for readability
38a42427 Add tuned covers assets for ad-hoc send
2f1d0d74 Remove scratch assets after ad-hoc send
c56bd937 Fix daily caption format to fixed "Yesterdays Performance" header
ac3f647f Increase text size on all 4 export cards for glow legibility
48b8b7d4 Add TR/SP glitch videos for ad-hoc send
654ffa55 Remove scratch assets after ad-hoc send
a8502087 Match Event Performance card to Track Record row style + extend video durations
c3f9ccee Increase font sizes across video templates for readability
2d07a28a Add rolling 7D video + World Cup event card for ad-hoc send
9452dfb6 Remove scratch assets after ad-hoc send
25500d3c Make video stat labels (RECORD/WIN%/UNITS/BETS LOCKED) neon magenta
9edb449e Add Sport Performance breakdown video (with leagues) for all 4 windows
fc9ef556 Redesign glitch reveal: per-stat glitch-in, drop scanline, bigger footer
449a3834 Give educational videos the glitch treatment
b1758482 Magenta headlines, World Cup title-case name, larger footers everywhere
b9cbcc69 Add caption support to ad-hoc email sender
8fcaa798 Fix year-stats bySport: don't depend on unreachable page global
4d183c04 Add date sub-line under "Yesterday's Performance" headline
f81d8f44 Add full test batch for ad-hoc verification sends
e511bf8a Add recipient override to ad-hoc email sender
ab9c467c Fix ad-hoc email workflow: pass inputs via env vars, not inline shell interpolation
389237a7 Single-line footer everywhere, fix soccer breakdown overlap, date ranges, educational rewrite
2172f0d3 Add biweekly All Time / Since Launch cards + breakdown videos
0e3ef137 Standardize footer order to match milestone template exactly
f893dcb4 Add final batch assets for send
f4de2092 Remove scratch assets after all sends complete
46185df9 Add #foryou to Instagram caption hashtags
62823d5e Daily rotation: fade/glitch only, slower pacing on both
a7d68b06 Add covers glitch video for send
df5eec83 Standardize all reveal video durations to 8 seconds
6c3ad4b4 Educational videos to 12s, grading/subscription to 10s
7ef8ecbb Add full review batch assets
df577b16 Remove scratch assets after all review sends complete
7156e0e4 sync: on-demand refresh 2026-07-21 06:07 UTC
0b0a0396 Milestone logo to top, uniform single-line footer everywhere
1b31e3c3 Add World Cup wrap-up assets for send
3b368989 Remove scratch asset after send
0a01c051 Archive World Cup 2026 (concluded), record final result
2a159f27 Rename 'BETS LOCKED' to 'PICKS LOCKED' across all videos
9255d5ad Parallelize 4 sequential boot-time sync calls to fix load lag
f238b48b Remove World Cup 2026 entirely from the app UI
9a5d0ec4 Tighten magenta neon glow blur radius across video templates for crisper text
68c2c569 sync: on-demand refresh 2026-07-22 06:19 UTC
9a6cd00f Add Pick Queue: automated multi-sport candidate scan with manual review/lock
e3e13e1d Pick Queue: cover every tracked sport/league via a scanner registry
fb0455e1 Pick Queue: fix WNBA/soccer coverage gaps, add real NBA/club-soccer models, separate props from game markets
57e99df8 Fix bets misclassifying as FOOTBALL on the Sport Performance card
8a580bb0 Guard against synthetic test-seed rows polluting real bet stats/videos
5afe618b Fix MLB O/U default line landing on whole numbers instead of .5
3b923a24 Drop past-date MLS matchdays once the day passes
96d9e06c Restrict MLS matches to today only, not a rolling window
52795ad9 Fix soccer club-league picks logging under the match date instead of the lock date
d12a8278 Log soccer club-league picks under the match's own date, not the lock date
22fd6c15 Fix UTC/Mountain timezone mismatch in MLS date handling
6ff2d826 Add Tier Calibration report: backtest PREMIUM/OPTIMAL/LEAN against real results
837f09a1 Tag Pick Queue locks by source, surface them on the Overall dashboard, fix broken tennis decOdds
6022390b Extend LEAN convergence gating to NBA and the 5 club soccer leagues
9502da9d Add month-scoped sport/bet-type/league breakdown to Overall dashboard
38db69e8 Remove Pick Queue, restrict all soccer leagues to today-only, show grade on pending picks
b2f6f6bb Fix club soccer picks resolving to wrong team names (Portland Timbers -> Portugal)
41270fa0 Fix soccer O/U over-bias, add league display labels, fix today-date grouping
50ab4667 Universal league-label + sport-sub-label system across every sport
fcdb26d8 Rename Champions League tag CH->CL, Bundesliga tag BL->BUND
9d87b38c Universal .5 O/U lines, fix real cross-sport lockPick collision risk
d9947f3f sync: on-demand refresh 2026-07-26 06:07 UTC
32f953c6 Add Serie A as a full 6th soccer league; fix video-card league list
b0651825 Add cross-device pick sync (phone <-> laptop) via Supabase pull-back
2691ca4a Fix stale picks reappearing after removal across devices
82857b39 Fix soccer league list wrapping mid-word in Sport Performance videos
2170e39b Fix mobile header overflow and stat-card clipping/wrapping
56100ff7 Fix mobile splash overflow and nav dropdowns not opening on touch
d819e727 Limit educational rotation content to grading + subscription
d117b218 Re-add covers to educational rotation with Serie A in place of World Cup
218a0357 Order soccer leagues alphabetically on covers card (Bundesliga, Champions League, La Liga, MLS, Premier League, Serie A)
9c6765b6 Fix stale-pending duplicate bets, shrink mobile fonts, fix notch overlap, update home-screen icon
c5981932 Fix corruption from prior font-reduction commit, apply deeper mobile shrink, enlarge home-screen icon
95182a60 Aggressive mobile text-size cap, remove bottom nav, shrink header, fix icon caching
8d6d6d1b Comprehensively cap mobile text size across every tab and sub-tab
f77d9386 Restrict MLB schedule to today only, shrink mobile bet-popup
6846b8a9 Continuously dedupe stale-pending picks, shrink mobile buttons further
494ba6ab Aggressively shrink mobile buttons (win/loss/remove) and pending-bet text
2e1d8c45 Fix stale-cache reload not actually bypassing cache; further mobile shrink
43406a43 Fix glitchy/interrupted mobile splash: defer version-freshness check past it
f49c898a Add Serie A + Champions League to All Bets filter and Simulator
f4fc7bc1 Analytics tab: full 20-league coverage, add By League and By Player tabs
24a6e825 Engine Ops: real per-league soccer schedule refresh, honest NFL/weights labeling
cc4e736b sync: on-demand refresh 2026-07-28 06:24 UTC
db645126 Convert Engine Ops to real per-sport tabs; wire soccer Props/Stats to real data
fee226d2 Adaptive Learning: fix soccer/tennis coverage gaps, expose WNBA weight deltas
6a57b53f Simulator: two-level sport->league dropdown, fix Serie A fallback key mismatch
6becbf3f Fill out simulator fallback rosters for La Liga (20) and Bundesliga (18)
d7b5191a Mobile: fix Simulator control grid, verify all new desktop features
2cb07a65 Fix off-season placeholders that would NEVER auto-clear when seasons resume
0c91db42 Give tennis its own real, adaptively-tuned ensemble anchored on player Elo
da79a174 feat: full nav restructure (hockey/soccer leagues), parlay + news full coverage, WNBA props push fix
8b1443a2 fix(social-cards): reduce email delivery delay + add failure alerting
58a9b80f feat(soccer): replace hand-estimated PL/Serie A/Bundesliga xG with real 2025/26 Opta team data
38c8edd2 feat(soccer): automate daily Opta team-stats scraping for BL/PL/Serie A/MLS
6f40c41a feat(mls): feed passing/pressing/sequences into the soccer MC engine, not just xG/xGA
90e6072c Blend MLS attacking/defending stats from Opta scrape with existing feed
73903d86 Standardize Instagram hashtags to #foryou #sportsbetting #bettingtips #bettingpicks
65052a26 Add Pick of Day: free daily social pick + tracked home-page record
2b049a62 Remove World Cup from soccer leagues-covered copy, drop stale PWHL mention
e3dd42bb Widen Pick of Day to O/U props, tag matching real bets, fix WNBA/NBA prop mistagging
d6691775 Pick of Day: fall back to Monte Carlo model when live odds are missing
37ac2a5f Make Monte Carlo the default MLB probability source for Pick of Day
398c3e3a Extend Pick of Day model-default to WNBA; fix misleading duplicate-lock toast
28baefde Strip stale hockey test data from monthly video, add date to Pick of Day video
f2202aa3 Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
cf44c1cd Recap emails: video for IG, still image for X; drop static PNG cards
6fc4ea20 Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
ff01f08f Standardize all recap videos on the glitch aesthetic; make Sport Performance breakdown overflow-proof
083f28c4 Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
9fe3f226 Add --force period override for review; fix empty stat boxes appearing before their text
9f0f8dfb Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
252d9ba6 Add --force milestone replay for review; drop leftover static card from milestone email
1538ca25 Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
71be76b2 Retire Since Launch and Milestone emails; add still image to Event Performance
10468cee Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
02240627 Fix weekly recap date range crossing month/year boundary; fix FREE PICK over-tagging; add picks-locked count to home tile
2420ba5a Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
5cc67337 Dashboard batch: Pick of Day manual settle, mobile text overflow, WNBA/MLB mislabeling, O/U .5 rounding, auto-recalibration first pass
2a9daf5a Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
0e99e5c3 Parlay fallback slate, soccer MC zero-goal fix, mobile sub-tab nav on all tabs
7933e0e2 Remove ROI from Recent Form section in Overall dashboard
ab31e91f Engine Consistency drawdown tiles removed; home page FREE PICK badge + rename; daily pipeline honors soft-deletes
c27d17b3 Fix Pick of Day: dedup lock bug, dead settlement path, real settlement; Parlay tab engine-only; Overall dashboard integration
cc0f7540 Pick of Day: rephrase bets->picks, add performance box to Overall dashboard
a51956bf Fix WNBA/MLB team-abbreviation collision (Seattle/Minnesota) and WNBA O/U line rounding
32ec44c2 Fix O/U .5-ending bug across MLB, NHL, and NBA (not just WNBA)
d97080fc Fix a second, separate NBA O/U line that skipped half-point forcing
18636373 Add daily Engine Performance JSON snapshot for landing page
b2b6bc47 Remove pick counts from home page period boxes; harden Pick of Day load
10dc14e8 Remove Tap To Enter box and crosshair reticle from splash screen
eb496ccf Force player prop lines (NBA/WNBA PTS/REB/AST/PRA) to end in .5
9c5d5d6a Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
22a9cb9c Retire MLB player props
162ae6c6 Add StatMuse insights integration
cf7ae408 Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
663117c1 Add NFL player props: sub-tab, filters, lock flow, and dropdown entry
7714edfa Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
b4dd4271 Fix regression: restore NBA player props (accidentally deleted retiring MLB props)
c8cf09c7 Fix settlement accuracy bugs found in audit
485fd2ec Give NBA/NHL/NFL player props their own scheduled refresh (freshness audit fix)
5b2dbc7a Fix duplicate-function-shadowing bugs from dead-wiring audit
3341c6eb Fix _reRenderActive dead wiring for Social/News tabs (dead-wiring audit)
54e03f6e Force WNBA spread line to .5, same push-avoidance as O/U lines
2daabcf2 CFB foundation: conference/team roster builder
981b4e94 CFB: add AP Top 25 rankings + FPI/Resume/Efficiencies scraper
e10ed626 CFB: add team stats scraper (offense/defense/special teams)
0ed06928 CFB: add MC simulation engine (loadCFBData, cfbMC, cfbEns)
4e05e0c7 CFB: add full weekly schedule scraper (all weeks, all conferences, real lines)
d5775dca CFB: add pick locking + settlement (final data-side piece)
b4649195 CFB: add recurring automation (final piece of the initial build)
764c1fa6 CFB: force .5 on fallback spread/O-U lines, never on real market lines
77875a43 CFB: tag picks sport:FOOTBALL/league:CFB as requested, fix _normSport to support it
bbbbe493 Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
e17a16bd CFB: 15k sims, per-pick grading/reasoning, adjustable lines, both spread/OU sides
8721cd26 CFB: square pick cards, combined total shown in MC sim line
4804a6d7 Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
19295a19 Expand CFB pick reasoning with analytical multi-factor breakdown
333cafc7 Fold offense/defense yardage and turnover metrics into CFB MC sim, expand reasoning with TD and yards-allowed detail
308a75c5 Add real per-venue weather and genuine incremental Elo to CFB, fix NBA reasoning data-source honesty gap
c9dd7a4f Redesign CFB game cards to match MLB's compact chip/adjuster layout
6ccb0896 Increase CFB heavy-snow total impact from -2.5 to -6.5 points
71d107da Give CFB an MLB-style adjustable MODEL tab; fall back to market spread for FCS matchups
0426f1fa Add per-game model-vs-market recommended line, refresh CFB Config tab
3c0f441e Make CFB home-field advantage team-specific instead of one flat number for every stadium
08abf598 Fix server-side pick settlement: ML never matched, and only NBA/MLB/NHL were covered at all
8d686555 Widen CFB's no-FPI fallback to moneyline odds, not just spread
0b4ced53 Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
fc24d190 Remove mobile bottom nav at every screen size; close a real sport mis-tagging gap in _normSport
95533083 Add matchup comparison radar chart to CFB game cards, behind a COMPARE toggle
0fc84774 Add cyberpunk matchup radar to NHL and soccer, upgrade CFB's to match
aa8ece10 Add offense/defense radar breakdowns to CFB, NHL, and soccer matchup cards
0898df23 Add per-game StatMuse insights section to CFB, NHL, and soccer cards
7271f143 Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
d14c61ad Build NFL engine phase 1: scraper, MC sim, Games/Props/Model/Config tabs
11202ac9 Add NFL preseason games, 3-tab matchup radar, weekly roster cadence
5b46617b Fix NFL audit findings: drop duplicate roster workflow, correct stale config copy
2ef35ee5 Add NFL analytical player props: passing/rushing/receiving/TD, matchup-adjusted
be9a99f3 Fix NFL model props: real defense-vs-league comparison, grade taxonomy, sport/league tagging
2660fd12 NFL model props: real per-game defensive data, no cross-file guesswork
384641dd Remove the Trainer tab
086574bc Fix NFL player props audit findings: settlement, TD-branch SKIP guard, null-safety
daca8d1f Fix audit findings across NBA, WNBA, and soccer
e270e870 Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
8c84659e Fix duplicate stale STATMUSE_NHL block, dead NBA_PROPS_DATA/NBA_PAR resets
ba9c9e7d NHL: populate all 32 teams from real standings, not just the 4 hand-curated ones
80e63953 Sync docs/index.html mirror for NHL 32-team fix
baa0ef88 Fix tennis audit findings: broken pending-bets UI, fabricated auto-loss, hardcoded winProb/surface
b11c9758 Split soccer StatMuse insights per league instead of one mixed feed
7b8a72e8 Add NBA/WNBA matchup radar charts; fix two real NBA card crashes found while testing
ead9b6b6 Expand NBA/WNBA/NHL stats to all teams; wire radar charts to the same live data the sims use
1b9ad21b Fix cross-league tagging safety: NCAAH/NHL merge bug, tenSp raw-field filter, harden lockPick for CBB/NCAAH
b838dc42 Ensure every locked-pick constructor sets both sport and league
2e16bd95 Add real NBA/NHL/WNBA roster scrapers + lookup/audit helpers
b3fbcefe MLB: weight MC sim outliers lightly (not exclude), notate on cards; expand reasoning; fix real p.ml crash
8dcfcbd1 Retire WNBA 7-day schedule view; fix real wnbaMC parameter-collision bug
771db68e Balance top nav tab spacing across full bar width
0e045d43 Add model-recommended-line-vs-market display to MLB/NBA/NHL/WNBA/soccer
b43c9262 NHL: read real ESPN scoreboard odds directly, not just the CLV tracking store
daa051c0 Merge branch 'main' of https://github.com/MercMink21/clairvoyance-backend
f250c6b3 NBA player props: real opponent-defense adjustment, real UNDER support
97a8e644 Fix WNBA props showing old matchups with no staleness disclosure
71d864f0 Fix real gap: daily props fast-path never validated matchups or stamped a timestamp
e8d37062 WNBA player props: real opponent-defense adjustment, real UNDER support
dbde06d6 Player props: recommended (model) line vs real market line for NBA/WNBA/NFL; fix NHL props reading a dead empty array
6a05258e Fix CFB/NFL schedule workflow git-push races causing daily Action failures
5cc5d24b Build real NHL player props engine (live ESPN+MC), matching NBA/WNBA
6d3e45d2 Recommended vs market line on EVERY prop card, not just when our own model generates the prop
b7d8907e Add MLB matchup/offense/pitching radar chart to game cards
1f985667 Fix Daily Social Cards Email queue-starvation failure
5741dda4 Fix systemic Actions failures: queue starvation from Pages+mobile-sync firing on every push
7cc0d8e5 Fix PICKS LOCKED count to match settled bets (w+l), not raw locked count
3cc52241 Close the last real UNKNOWN-tagging gap: lockProp's fallback never checked WNBA
f154236c Fix Pick of the Day picking zero legs for 3+ consecutive days
4739d2b2 Fix ESPN 403s blocking CFB/NFL schedule+injuries and the main pipeline for days
66b408de Remove Free Pick of the Day entirely
66fbb341 Fix regression: www.espn.com needs the opposite header treatment from site.api.espn.com
b048960c Add server-side auto-lock/auto-settle + personal daily locks email
5d88ddfe Increase MLB MC sim count 5k->15k, fix always-shows-5k display bug
8ae1b287 Add settlement email; add repo-variable live-mode toggle for auto-lock/settle
1927f3bb Fix settled-bet reversion race, ticker-free wrong-day lock legs
bab64352 Remove dead top-picks ticker; move Import/Export Bet to Engine Ops
f8b0f5e1 Tennis: fix broken ESPN rankings scrape, wire it in as validation ref, fix wrong Cincinnati Open dates, add real injury/withdrawal signal
d06e6160 Fix same wrong-day staleness bug in WNBA's primary game source
34131ede Fix NHL's stale hardcoded fallback game showing regardless of date
911bc510 Build out Cincinnati Open with real ESPN draw + full MC match cards
d680fccc Fix Cincinnati Open card layout: live matches, TBD slots on either side
2e432aec Auto-update ATP_DB/WTA_DB + Elo daily; fix a bug silently breaking loadRemoteData()
```

---

## Appendix B: Automated / Routine Commit Volume (excluded from Appendix A)

These are excluded from Appendix A above because they're mechanical, scheduled, self-explanatory, and would add noise without information — but they represent real infrastructure running continuously all session:

| Commit type | Count | What it is |
|---|---|---|
| `live: HH:MM MT scores` | 2,832 | Live in-game score polling, every ~2 min during game windows, 16:00–23:00 MT |
| `data: <date> <time> MT auto-refresh` | 59 | Full data refresh — 09:00/15:00/23:00 MT scheduled runs |
| `chore: refresh <sport> player props` | 65 | Daily player-prop regeneration across NBA/NHL/WNBA/NFL |
| `statmuse: refresh insights` | 34 | Daily StatMuse insight pull |
| `social-cards: pick-of-day state update` | 33 | Daily social card state sync |
| `cfb: refresh schedule/lines/team stats/rankings` | 25 | CFB data refresh (also has weekly/monthly variants not counted here) |
| **Total commits `50f37f5..origin/main`** | **3,894** | 646 substantive + ~3,248 automated |

This automation volume is itself a Session 9 accomplishment — Session 8 had 2 scheduled workflows; Session 9 ends with 21 (§2), which is what makes several thousand unattended commits over 2.5 months possible without the app going stale.

