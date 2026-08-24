"""
Server-side auto-lock and auto-settle, driving the real live app headlessly
via Playwright so both reuse the EXACT same engine/grading/settlement logic
the UI itself uses -- single source of truth, zero duplicated logic here.

Background: server-side settlement previously depended on data/locked_props.json,
a file nothing in this pipeline ever actually wrote (the only writer was a
manual browser export button, never used) -- so auto_settle() in
clairvoyance_update.py silently no-op'd on every run. This script replaces
that dead path: it loads the REAL bet ledger straight from Supabase (same
proven pattern generate_social_cards.py already uses), settles it via the
real client-side autoSettle*() functions, and locks new PREMIUM/OPTIMAL
picks via the real lockPick()/lockProp()/lockNHLProp()/lockNFLModelProp()
functions -- then flushes everything back to Supabase via the app's own
syncBetsToSupabase().

Auto-lock scope: ML, spread, and O/U for every sport/league with a real
proprietary model (MLB, NBA, WNBA, NHL, NFL, CFB, and 6 soccer leagues),
plus sets/games O/U for tennis (ATP/WTA). CBB, NCAAH, and tennis moneyline
already only have a market-read-back model (no proprietary edge to grade),
matching how the rest of the app already treats them -- ML only there via
_epGatherESPNCacheLegs/_epGatherTennisLegs, not extended here. Player props
covered for NBA/WNBA/NHL/NFL (the four sports with real live prop engines
built this session).

Grade capture for game markets: docs/app.html has a small _autoLockCapture()
hook wired into every sport's real game-card render function, right after
each one computes its own real _evalMkts() result -- this script never
re-derives spread/O-U probabilities itself, it only reads what the UI
already computed for that exact game, guaranteeing zero drift.

Known pre-existing app characteristic (not introduced here): lockPick()'s
single `type` parameter can encode EITHER the sport tag OR a bet-type
keyword ('OU'/'SPREAD'/'RL'/'PL'), not always both -- passing the explicit
sport tag (required for correct classification on non-abbreviation-
guessable sports) means the stored betType field defaults to 'ML' even for
a real spread/O-U pick. This already happens for real manually-locked bets
today (confirmed: MLB's own spread-lock button passes type='MLB', not
'RL'). This script matches that exact existing behavior rather than
inventing a new convention -- the betOn text itself (e.g. "PHI -1.5") is
always correct regardless.

Safety: defaults to dry-run (logs exactly what it WOULD lock/settle,
writes nothing anywhere). Pass --live to actually write to Supabase.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from _gmail_email import send_email as _send_gmail  # noqa: E402
from _gmail_email import EMAIL_WRAP_OPEN as _EMAIL_WRAP_OPEN, EMAIL_WRAP_CLOSE as _EMAIL_WRAP_CLOSE  # noqa: E402
from _subscribers import recipients_for, OWNER_EMAIL  # noqa: E402

APP_URL = "https://mercmink21.github.io/clairvoyance-backend/app.html"
# Separate from SOCIAL_CARD_EMAIL_TO on purpose -- this is a personal daily
# betting reference, not public social content, so it can (and probably
# should) go to a different inbox. Falls back to the social recipient only
# so this doesn't silently go nowhere if the dedicated secret isn't set yet.
LOCKS_EMAIL_TO = os.environ.get("LOCKS_EMAIL_TO", "") or os.environ.get("SOCIAL_CARD_EMAIL_TO", "")

# Human-readable section headers for the email, keyed by the same sport
# tags SPORT_TO_LOCKPICK_TYPE/_autoLockCapture use.
SPORT_DISPLAY_NAME = {
    "MLB": "MLB", "NBA": "NBA", "WNBA": "WNBA", "NHL": "NHL", "NFL": "NFL", "CFB": "CFB",
    "SOC_BL": "Bundesliga", "SOC_LIGA": "La Liga", "SOC_MLS": "MLS", "SOC_PL": "Premier League",
    "SOC_ITA": "Serie A", "SOC_CL": "Champions League",
    "ATP": "ATP", "WTA": "WTA",
}

# Maps the sport tag docs/app.html's _autoLockCapture() attaches to each
# game leg (e.g. 'SOC_PL' for Premier League, to keep 'PL' unambiguous --
# lockPick's own type='PL' means NHL puck line) to the exact `type` string
# lockPick() itself expects to resolve the correct sportTag.
SPORT_TO_LOCKPICK_TYPE = {
    "MLB": "MLB", "NBA": "NBA", "WNBA": "WNBA", "NHL": "NHL", "NFL": "NFL", "CFB": "CFB",
    "SOC_BL": "BUND", "SOC_LIGA": "LIGA", "SOC_MLS": "MLS", "SOC_PL": "PL_SOC",
    "SOC_ITA": "SERIEA", "SOC_CL": "CL",
    "ATP": "ATP", "WTA": "WTA",
}
# The 5 European leagues -- deliberately excludes SOC_MLS, which kicks off
# at normal US evening times and doesn't have the early-kickoff problem
# soccer-lock-early.yml exists to solve (confirmed real bug: MLS legs were
# showing up in the "EUROPEAN SOCCER" email before this).
EURO_SOCCER_SPORTS = frozenset({"SOC_CL", "SOC_PL", "SOC_LIGA", "SOC_BL", "SOC_ITA"})

# The 8 paid products (confirmed structure, see _subscribers.py) -- each
# maps to the exact sport tags gather_legs()/_autoLockCapture use. Soccer
# bundles all 6 leagues (5 European + MLS) as one purchase. Hockey bundles
# NHL with KHL/SHL/LIIGA -- those 3 have no real game cards wired up yet
# (confirmed: no _autoLockCapture call exists for them), so today this is
# functionally NHL-only, but the product already covers them once they are.
# Tennis bundles ATP + WTA as one purchase (sets/games O/U only -- no
# proprietary ML edge, same as CBB/NCAAH, so ML isn't part of this product).
PRODUCT_SPORTS: dict[str, frozenset[str]] = {
    "nfl": frozenset({"NFL"}),
    "cfb": frozenset({"CFB"}),
    "nba": frozenset({"NBA"}),
    "wnba": frozenset({"WNBA"}),
    "mlb": frozenset({"MLB"}),
    "hockey": frozenset({"NHL", "KHL", "SHL", "LIIGA"}),
    "soccer": EURO_SOCCER_SPORTS | frozenset({"SOC_MLS"}),
    "tennis": frozenset({"ATP", "WTA"}),
}
PRODUCT_LABEL: dict[str, str] = {
    "nfl": "NFL", "cfb": "CFB", "nba": "NBA", "wnba": "WNBA", "mlb": "MLB",
    "hockey": "HOCKEY", "soccer": "SOCCER", "tennis": "TENNIS",
}
# OPTIMAL=2, PREMIUM=3 in _evalMkts()'s own tierN scale.
QUALIFYING_TIERS = {2, 3}
TIER_LABEL = {0: "SKIP", 1: "LEAN", 2: "OPTIMAL", 3: "PREMIUM"}


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_bet_ledger(page) -> int:
    """Same paginated Supabase pull generate_social_cards.py already uses
    (PostgREST caps a single response at 1000 rows), loaded straight into
    the page's own getP()/saveP() store so every real client function
    (settlement, dedup checks, sync) operates on the real live ledger.
    Uses docs/app.html's OWN already-declared SUPABASE_URL/SUPABASE_KEY
    consts (the anon key, safe client-side by RLS design, same one every
    other Supabase call in the app already uses) rather than injecting a
    separate credential from Python."""
    count = page.evaluate(
        """
        async () => {
          const rows = [];
          let offset = 0;
          const page_size = 1000;
          while (true) {
            const r = await fetch(SUPABASE_URL + '/rest/v1/bets?select=raw&order=date.desc&outcome=neq._removed', {
              headers: {
                apikey: SUPABASE_KEY, Authorization: 'Bearer ' + SUPABASE_KEY,
                Range: offset + '-' + (offset + page_size - 1),
              }
            });
            if (!r.ok) return -1;
            const batch = await r.json();
            rows.push(...batch);
            if (batch.length < page_size) break;
            offset += page_size;
          }
          const preds = rows.map(x => x.raw).filter(Boolean);
          saveP(preds);
          return preds.length;
        }
        """
    )
    if count is None or count < 0:
        raise RuntimeError("Failed to load bet ledger from Supabase in-page — check SUPABASE_URL/KEY")
    return count


def flush_to_supabase(page) -> None:
    """syncBetsToSupabase() (the app's own real sync path) is debounced
    2.5s after the last saveP() call — force a save via a no-op saveP()
    call and wait out the debounce instead of reimplementing the upload."""
    page.evaluate("() => { syncBetsToSupabase(); }")
    page.wait_for_timeout(4000)


# ─────────────────────────────────────────────────────────────────────────
# SETTLE
# ─────────────────────────────────────────────────────────────────────────
def run_settle(page, live: bool) -> list[dict]:
    log("=== AUTO-SETTLE ===")
    before = page.evaluate("() => getP().filter(p => p.outcome === 'pending').length")
    log(f"Pending bets before settle: {before}")

    # Warm the live game caches each autoSettle*() function reads, same
    # warmup every render path already does — settlement can't verify a
    # bet against a game it never loaded.
    page.evaluate(
        """
        async () => {
          const warmups = [];
          if (typeof loadGames === 'function' && !(window.ESPN_GAMES && window.ESPN_GAMES.length)) warmups.push(loadGames().catch(() => {}));
          if (typeof renderNHLGames === 'function') warmups.push(renderNHLGames().catch(() => {}));
          if (typeof renderGenericWeek === 'function') {
            warmups.push(renderGenericWeek('cfb-week-list', 'football/college-football', 'CFB').catch(() => {}));
            warmups.push(renderGenericWeek('nfl-week-list', 'football/nfl', 'NFL').catch(() => {}));
          }
          await Promise.allSettled(warmups);
        }
        """
    )

    result = page.evaluate(
        """
        async () => {
          const results = {};
          try { if (typeof autoSettleFromESPN === 'function' && window.ESPN_GAMES) autoSettleFromESPN(window.ESPN_GAMES); results.mlb = 'ok'; } catch (e) { results.mlb = 'err:' + e.message; }
          try { if (typeof autoSettleNBA === 'function') await autoSettleNBA(); results.nba = 'ok'; } catch (e) { results.nba = 'err:' + e.message; }
          try { if (typeof autoSettleNHL === 'function') await autoSettleNHL(); results.nhl = 'ok'; } catch (e) { results.nhl = 'err:' + e.message; }
          try { if (typeof autoSettleCFB === 'function') await autoSettleCFB(); results.cfb = 'ok'; } catch (e) { results.cfb = 'err:' + e.message; }
          try { if (typeof autoSettleSoccer === 'function') await autoSettleSoccer(); results.soccer = 'ok'; } catch (e) { results.soccer = 'err:' + e.message; }
          try { if (typeof autoSettleWNBA === 'function') await autoSettleWNBA(); results.wnba = 'ok'; } catch (e) { results.wnba = 'err:' + e.message; }
          try { if (typeof autoSettleTennis === 'function') await autoSettleTennis(); results.tennis = 'ok'; } catch (e) { results.tennis = 'err:' + e.message; }
          try { if (typeof autoSettleNFL2 === 'function') await autoSettleNFL2(); results.nfl = 'ok'; } catch (e) { results.nfl = 'err:' + e.message; }
          try { if (typeof autoSettlePropsESPN === 'function') await autoSettlePropsESPN(); results.props = 'ok'; } catch (e) { results.props = 'err:' + e.message; }
          return results;
        }
        """
    )
    log(f"Settlement function results: {result}")

    after = page.evaluate("() => getP().filter(p => p.outcome === 'pending').length")
    settled_count = before - after
    log(f"Pending bets after settle: {after} ({settled_count} newly settled)")

    newly: list[dict] = []
    if settled_count > 0:
        newly = page.evaluate(
            """
            () => getP().filter(p => p.outcome !== 'pending' && p.settledAt && (Date.now() - p.settledAt) < 180000)
              .map(p => ({
                betOn: p.betOn, sport: p.sport, outcome: p.outcome, date: p.date,
                hA: p.hA, awA: p.awA, hScore: p.hScore, aScore: p.aScore,
                playerResult: p.playerResult,
              }))
            """
        )
        for b in newly:
            log(f"  SETTLED: [{b.get('sport')}] {b.get('betOn')} -> {(b.get('outcome') or '').upper()}")

    if settled_count > 0 and live:
        flush_to_supabase(page)
        log("Flushed settlement results to Supabase")
    elif settled_count > 0:
        log("[DRY RUN] Would sync these settlements to Supabase (pass --live to write)")

    return newly


def _esc(s) -> str:
    return str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# _EMAIL_WRAP_OPEN/_EMAIL_WRAP_CLOSE imported from _gmail_email above --
# shared across every script that sends mail (see that module for why),
# not just the two locks/settlement emails built here.
_OUTCOME_COLOR = {"win": "#00e676", "loss": "#ff3b5c", "push": "#ffb300"}


def _settle_result_html(b: dict) -> str:
    """One result row per settled bet: what happened (score for game bets,
    actual stat value for props) alongside the win/loss/push outcome, so
    the email doubles as a same-day reference for picks that have now
    completed."""
    outcome = (b.get("outcome") or "").lower()
    color = _OUTCOME_COLOR.get(outcome, "#999")
    if b.get("hScore") is not None and b.get("aScore") is not None:
        result = f"{_esc(b.get('hA'))} {b['hScore']} – {_esc(b.get('awA'))} {b['aScore']}"
    elif b.get("playerResult") is not None:
        result = f"actual: {_esc(b['playerResult'])}"
    else:
        result = "no score/result captured"
    return (f'<div style="padding:5px 0;font-size:14px;color:#ddd">'
            f'<span style="background:{color};color:#000;font-weight:700;font-size:11px;padding:1px 7px;'
            f'border-radius:3px;margin-right:8px;text-transform:uppercase">{_esc(outcome)}</span>'
            f'{_esc(b.get("betOn"))} <span style="color:#999">({result})</span></div>')


def build_settlement_email_html(settled: list[dict]) -> str:
    by_sport: dict[str, list[dict]] = {}
    for b in settled:
        by_sport.setdefault(b.get("sport") or "?", []).append(b)

    wins = sum(1 for b in settled if b.get("outcome") == "win")
    losses = sum(1 for b in settled if b.get("outcome") == "loss")
    pushes = sum(1 for b in settled if b.get("outcome") not in ("win", "loss"))
    record = f"{wins}W-{losses}L" + (f"-{pushes}P" if pushes else "")
    parts = [_EMAIL_WRAP_OPEN,
              f'<div style="font-size:12px;letter-spacing:1px;color:#999;text-transform:uppercase">'
              f'{len(settled)} bets settled — {record}</div>']
    if not settled:
        parts.append('<div style="padding:20px 0;color:#999;font-size:14px">No bets settled this run.</div>')
        parts.append(_EMAIL_WRAP_CLOSE)
        return "".join(parts)

    for sport in sorted(by_sport, key=lambda s: SPORT_DISPLAY_NAME.get(s, s)):
        bets = by_sport[sport]
        sw = sum(1 for b in bets if b.get("outcome") == "win")
        sl = sum(1 for b in bets if b.get("outcome") == "loss")
        parts.append(f'<div style="font-size:13px;letter-spacing:2px;color:#00e5ff;text-transform:uppercase;'
                      f'margin:22px 0 10px;border-bottom:1px solid rgba(0,229,255,.25);padding-bottom:4px">'
                      f'{_esc(SPORT_DISPLAY_NAME.get(sport, sport))} ({sw}W-{sl}L)</div>')
        parts.append('<div style="background:#14001f;border-radius:6px;padding:10px 14px">')
        parts.append("".join(_settle_result_html(b) for b in bets))
        parts.append('</div>')
    parts.append(_EMAIL_WRAP_CLOSE)
    return "".join(parts)


def send_settlement_email(settled: list[dict], live: bool) -> None:
    if not LOCKS_EMAIL_TO:
        log("LOCKS_EMAIL_TO not set — skipping settlement email")
        return
    if not settled:
        log("Nothing settled this run — skipping settlement email")
        return
    body_html = build_settlement_email_html(settled)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    wins = sum(1 for b in settled if b.get("outcome") == "win")
    losses = sum(1 for b in settled if b.get("outcome") == "loss")
    prefix = "" if live else "[DRY RUN] "
    subject = f"Clairvoyance — {prefix}Settled {date_str}: {wins}W-{losses}L ({len(settled)})"
    ok, msg = _send_gmail(subject, LOCKS_EMAIL_TO, body_html)
    log(f"Settlement email sent to {LOCKS_EMAIL_TO}" if ok else f"Settlement email send failed: {msg}")


# ─────────────────────────────────────────────────────────────────────────
# LOCK
# ─────────────────────────────────────────────────────────────────────────
def gather_legs(page) -> dict:
    return page.evaluate(
        """
        async () => {
          window._autoLockLegs = [];
          // ESPN's site.api.espn.com blocks fetch() calls made from an
          // automated/headless browser context (confirmed: identical
          // failure in a real GitHub Actions run with unrestricted
          // network, and even with a real installed Chrome channel --
          // this isn't a sandbox artifact, it's ESPN detecting the
          // automation fingerprint itself, e.g. navigator.webdriver).
          // loadGames()/renderGenericWeek()/etc. all depend entirely on
          // that live cross-origin fetch with no same-origin fallback, so
          // they silently produce zero games here. Where real game data
          // is already bundled server-side (window.__CV_DATA, written by
          // the Python pipeline's own successful requests-based ESPN
          // calls, a completely different, unblocked code path) this
          // pre-step feeds it into the same card-render function a real
          // page load would use, so _autoLockCapture still fires with
          // real data instead of nothing.
          try {
            const mlbToday = (window.__CV_DATA && window.__CV_DATA.mlb && window.__CV_DATA.mlb.today) || [];
            const todayIso = typeof today === 'function' ? today() : new Date().toISOString().slice(0, 10);
            if (mlbToday.length && typeof mlbCard === 'function' && typeof TEAMS !== 'undefined') {
              mlbToday.forEach(g => {
                if (!g.home || !g.away || !TEAMS[g.home] || !TEAMS[g.away]) return;
                if (g.state === 'post') return; // already final, nothing to lock
                // __CV_DATA.mlb.today is only as fresh as the last pipeline
                // refresh -- if it ran before midnight MT rolled over (or
                // hasn't run yet today), this array is still yesterday's
                // slate. Only render games actually dated today (Denver
                // time, same as today()/lockPick's own date stamp) instead
                // of trusting the array's "today" label blindly. Parse+
                // convert rather than a raw slice(0,10) -- g.date is a UTC
                // timestamp, and a raw slice would misdate any game whose
                // UTC date differs from its Denver-local date (any night
                // game past ~6pm MT).
                const gd = new Date(g.date);
                const dateStr = isNaN(gd) ? (g.date || '').slice(0, 10) : gd.toLocaleDateString('sv-SE', { timeZone: 'America/Denver' });
                if (dateStr !== todayIso) return;
                const espnGame = { hML: g.homeML, aML: g.awayML, ou: g.ou, status: g.state };
                try { mlbCard(g.home, g.away, '', dateStr, espnGame); } catch (e) {}
              });
            }
          } catch (e) {}
          // cfb_schedule.json is a same-origin static file the Python
          // pipeline already publishes (unlike NFL, which currently has
          // no equivalent published file) -- same unblocked fetch as
          // window.__CV_DATA, just a separate file rather than bundled
          // into data.json.
          try {
            if (typeof _cfbGameCard === 'function') {
              const r = await fetch('cfb_schedule.json');
              if (r.ok) {
                const sched = await r.json();
                const todayIso = typeof today === 'function' ? today() : new Date().toISOString().slice(0, 10);
                Object.values(sched.weeks || {}).forEach(week => (week || []).forEach(g => {
                  const d = new Date(g.date);
                  const localIso = isNaN(d) ? (g.date || '').slice(0, 10) : d.toLocaleDateString('sv-SE', { timeZone: 'America/Denver' });
                  if (localIso !== todayIso || g.state === 'post') return;
                  try { _cfbGameCard(g); } catch (e) {}
                }));
              }
            }
          } catch (e) {}
          const warmups = [];
          if (typeof loadGames === 'function') warmups.push(loadGames().catch(() => {}));
          if (typeof renderMLBGames === 'function') { try { renderMLBGames(); } catch (e) {} }
          if (typeof renderNBAGames === 'function') { try { renderNBAGames(); } catch (e) {} }
          if (typeof renderWNBAGames === 'function') warmups.push(renderWNBAGames().catch(() => {}));
          if (typeof renderNHLGames === 'function') warmups.push(renderNHLGames().catch(() => {}));
          if (typeof renderGenericWeek === 'function') {
            warmups.push(renderGenericWeek('cfb-week-list', 'football/college-football', 'CFB').catch(() => {}));
            warmups.push(renderGenericWeek('nfl-week-list', 'football/nfl', 'NFL').catch(() => {}));
          }
          if (typeof renderLeagueMatches === 'function') {
            ['bl', 'liga', 'mls', 'pl', 'ita', 'cl'].forEach(k => warmups.push(renderLeagueMatches(k).catch(() => {})));
          }
          await Promise.allSettled(warmups);
          if (typeof renderTennisScheduleOdds === 'function') { try { renderTennisScheduleOdds(); } catch (e) {} }
          // Card renders above are synchronous once their data warmup
          // resolves, but give any trailing async chip/radar work a moment
          // before reading back what _autoLockCapture collected.
          await new Promise(r => setTimeout(r, 1500));

          const gameLegs = window._autoLockLegs || [];

          const propLegs = [];
          try {
            if (typeof _generateNBAProps === 'function' && typeof _fetchNBAPlayerStats === 'function') {
              const stats = await _fetchNBAPlayerStats();
              const games = window._nbaTodayGames || (typeof NBA_TONIGHT !== 'undefined' ? NBA_TONIGHT : []) || [];
              if (stats) _generateNBAProps(games, stats).forEach(p => propLegs.push({ ...p, sportTag: 'NBA' }));
            }
          } catch (e) {}
          try {
            if (typeof _generateWNBAPropsLive === 'function' && typeof _fetchWNBAPlayerStats === 'function') {
              const stats = await _fetchWNBAPlayerStats();
              const games = window._wnbaGameData || [];
              if (stats) _generateWNBAPropsLive(games, stats).forEach(p => propLegs.push({ ...p, sportTag: 'WNBA' }));
            }
          } catch (e) {}
          try {
            if (typeof _generateNHLPropsLive === 'function' && typeof _fetchNHLPlayerStats === 'function') {
              const stats = await _fetchNHLPlayerStats();
              const games = window._nhlTodayGames || [];
              if (stats) _generateNHLPropsLive(games, stats).forEach(p => propLegs.push({ ...p, sportTag: 'NHL' }));
            }
          } catch (e) {}
          try {
            if (typeof _nflModelPropsForGame === 'function' && window._NFL_DATA) {
              const games = [];
              Object.values(window._NFL_DATA.weeks || {}).forEach(list => (list || []).forEach(g => games.push(g)));
              games.forEach(g => { try { _nflModelPropsForGame(g).forEach(p => propLegs.push({ ...p, sportTag: 'NFL', _nflGame: g })); } catch (e) {} });
            }
          } catch (e) {}

          return { gameLegs, propLegs };
        }
        """
    )


def build_qualifying(result: dict, only_sports: frozenset[str] | None = None) -> list[dict]:
    """only_sports: if given, restricts to exactly these sport tags (e.g.
    EURO_SOCCER_SPORTS for the European-soccer early pass, {"CFB"} for the
    CFB-only early pass) -- for the dedicated early lock runs timed ahead of
    that sport/league's own earlier kickoffs. Deliberately an exact-tag
    allowlist, not a prefix match: a bare "SOC_" prefix match would also
    catch SOC_MLS, which kicks off at normal US evening times and has none
    of the early-kickoff problem this pass exists for (confirmed real bug --
    MLS legs were showing up in the "EUROPEAN SOCCER" email)."""
    def _wanted(sport: str) -> bool:
        return only_sports is None or (sport or "") in only_sports
    qualifying: list[dict] = []
    for gl in result.get("gameLegs") or []:
        sport = gl.get("sport")
        if not _wanted(sport):
            continue
        for m in gl.get("markets") or []:
            tier_n = m.get("tierN")
            if tier_n in QUALIFYING_TIERS:
                qualifying.append({
                    "kind": "GAME", "sport": sport, "hA": gl.get("hA"), "awA": gl.get("awA"),
                    "side": m.get("side"), "label": m.get("label"), "prob": m.get("prob"),
                    "ml": m.get("ml"), "dec": m.get("dec"), "tierN": tier_n, "evVal": m.get("evVal"),
                    # Same for every qualifying market on this game -- carried
                    # per-leg (not de-duped) so build_locks_email_html can
                    # regroup by matchup without needing a second pass over
                    # gameLegs.
                    "mcSummary": gl.get("mcSummary"), "best": gl.get("best"),
                })
    # Props only exist for NBA/WNBA/NHL/NFL -- neither early pass (soccer,
    # CFB) needs or has any to filter, so props are simply included only on
    # the unscoped (full) run.
    if only_sports is None:
        for p in result.get("propLegs") or []:
            if p.get("grade") in ("PREMIUM", "OPTIMAL"):
                qualifying.append({"kind": "PROP", "sport": p.get("sportTag"), "leg": p})
    return qualifying


def lock_game_leg(page, q: dict) -> str:
    """Calls the real lockPick() directly with the explicit, correct sport
    tag (see module docstring on the type/betType tradeoff this mirrors
    from the app's own real lock buttons)."""
    lock_type = SPORT_TO_LOCKPICK_TYPE.get(q["sport"])
    if not lock_type:
        return f"skip: no lockPick type mapping for sport {q['sport']}"
    ml = q.get("ml")
    dec = q.get("dec")
    return page.evaluate(
        """
        async ({ hA, awA, type, betOn, prob, ml, dec }) => {
          const before = getP().length;
          await lockPick(hA, awA, type, betOn, prob, ml != null ? ml : '-110', dec || 1.91, today(), 'manual');
          const after = getP().length;
          return after > before ? 'locked' : 'dup-or-failed';
        }
        """,
        {"hA": q["hA"], "awA": q["awA"], "type": lock_type, "betOn": q["label"], "prob": q["prob"], "ml": ml, "dec": dec},
    )


def lock_prop_leg(page, sport: str, leg: dict) -> str:
    if sport == "NHL":
        return page.evaluate(
            """
            ({ player, stat, dir, prob, ml, line }) => {
              const before = getP().length;
              lockNHLProp(player, stat, dir, prob, ml, line);
              return getP().length > before ? 'locked' : 'dup-or-failed';
            }
            """,
            {"player": leg.get("player"), "stat": leg.get("stat"),
             "dir": "OVER" if leg.get("over") is not False else "UNDER",
             "prob": leg.get("prob") or (leg.get("conf", 0) / 100), "ml": leg.get("ml"), "line": leg.get("line")},
        )
    if sport in ("NBA", "WNBA"):
        return page.evaluate(
            """
            ({ team, player, line, over, prob, ml, sport, opp }) => {
              const before = getP().length;
              lockProp(team, player, line, over, prob, ml, sport, opp);
              return getP().length > before ? 'locked' : 'dup-or-failed';
            }
            """,
            {"team": leg.get("team"), "player": leg.get("player"), "line": leg.get("line"),
             "over": leg.get("over") is not False, "prob": leg.get("prob") or (leg.get("conf", 0) / 100),
             "ml": leg.get("ml"), "sport": sport, "opp": leg.get("opp") or ""},
        )
    if sport == "NFL":
        # Reuses the real lockNFLModelProp(idx) by staging the exact leg it
        # expects into window._nflModelPropsCurrent, rather than
        # duplicating its internal prop-object construction here.
        return page.evaluate(
            """
            (leg) => {
              const g = leg._nflGame;
              const row = { ...leg, team: leg.team, opp: leg.opp, cat: leg.stat || leg.cat, pick: leg.over === false ? 'UNDER' : 'OVER', likelihood: Math.round((leg.prob || 0.6) * 100), grade: leg.grade };
              window._nflModelPropsCurrent = window._nflModelPropsCurrent || [];
              window._nflModelPropsCurrent.push(row);
              const before = getP().length;
              lockNFLModelProp(window._nflModelPropsCurrent.length - 1);
              return getP().length > before ? 'locked' : 'dup-or-failed';
            }
            """,
            leg,
        )
    return "skip: unhandled prop sport"


# Same threshold + same side classification _evalMkts() uses in
# docs/app.html (an 'over'/'under'/'setsOver'/'setsUnder' side is OU, an
# 'rlFav'/'rlDog'/'plFav'/'plDog'/'sprdFav'/'sprdDog'/'ahFav'/'ahDog' side
# is SPREAD, everything else -- including soccer's home/draw/away team-
# name sides -- is ML) and the exact threshold _highHitBadgeHTML() uses
# on the game cards, so "HIGH HIT %" in this email means the same thing
# it means on screen.
_HIGH_HIT_P = 0.75
_OU_SIDES = {"over", "under", "setsOver", "setsUnder"}
_SPREAD_SIDES = {"rlFav", "rlDog", "plFav", "plDog", "sprdFav", "sprdDog", "ahFav", "ahDog"}


def _market_type(side: str | None) -> str:
    if side in _OU_SIDES:
        return "OU"
    if side in _SPREAD_SIDES:
        return "SPREAD"
    return "ML"


_TIER_COLOR = {3: "#ffdd00", 2: "#00e5ff", 1: "#6699ff", 0: "#666"}  # PREMIUM/OPTIMAL/LEAN/SKIP
_GRADE_COLOR = {"PREMIUM": "#ffdd00", "OPTIMAL": "#00e5ff", "LEAN": "#6699ff"}


def _leg_html(q: dict) -> str:
    """One row per qualifying leg: a colored tier badge, probability, EV,
    both odds formats, and (for a moneyline pick at 75%+ model
    probability) the same HIGH HIT % tag the game cards show, so a heavy
    favorite that clears the hit-rate bar but not the EV bar still gets
    flagged here even if its tier is only LEAN."""
    if q["kind"] == "GAME":
        tier_n = q["tierN"]
        tier_lbl = TIER_LABEL.get(tier_n, "?")
        color = _TIER_COLOR.get(tier_n, "#666")
        ev_val = q.get("evVal")
        ev_str = f' · EV {ev_val*100:+.1f}%' if ev_val is not None else ''
        ml, dec = q.get("ml"), q.get("dec")
        odds_str = (f' · {_esc(ml)}' if ml else '') + (f' ({dec:.2f})' if dec else '')
        prob = q.get("prob") or 0
        hh = ' <span style="color:#ffdd00">🔥 HIGH HIT %</span>' if _market_type(q.get("side")) == "ML" and prob >= _HIGH_HIT_P else ''
        return (f'<div style="padding:4px 0;font-size:14px;color:#ddd">'
                f'<span style="background:{color};color:#000;font-weight:700;font-size:11px;padding:1px 7px;'
                f'border-radius:3px;margin-right:8px">{tier_lbl}</span>'
                f'{_esc(q["label"])} — {prob*100:.0f}%{ev_str}{odds_str}{hh}</div>')
    leg = q["leg"]
    direction = "UNDER" if leg.get("over") is False else "OVER"
    prob = leg.get("prob") if leg.get("prob") is not None else (leg.get("conf", 0) / 100)
    prob = prob or 0
    ml, dec = leg.get("ml"), leg.get("dec")
    odds_str = (f' · {_esc(ml)}' if ml else '') + (f' ({dec:.2f})' if dec else '')
    grade = leg.get("grade") or ""
    color = _GRADE_COLOR.get(grade, "#666")
    return (f'<div style="padding:4px 0;font-size:14px;color:#ddd">'
            f'<span style="background:{color};color:#000;font-weight:700;font-size:11px;padding:1px 7px;'
            f'border-radius:3px;margin-right:8px">{_esc(grade)}</span>'
            f'{_esc(leg.get("player"))} {direction} {_esc(leg.get("line"))} {_esc(leg.get("stat"))} — {prob*100:.0f}%{odds_str}</div>')


def _prop_matchup_key(leg: dict) -> str:
    team = leg.get("team") or leg.get("hA") or ""
    opp = leg.get("opp") or leg.get("awA") or ""
    return f"{team} vs {opp}" if opp else team


def build_locks_email_html(qualifying: list[dict], live: bool, locked_count: int | None = None) -> str:
    """Groups qualifying legs by sport/league, then by matchup within each
    sport: the matchup, every qualifying pick for it (grade, probability,
    EV, odds), and the real MC/model reasoning behind it (not necessarily
    one of the qualifying picks itself -- shown either way as context)."""
    by_sport: dict[str, dict[str, list[dict]]] = {}
    for q in qualifying:
        sport = q["sport"]
        matchup = f"{q['awA']} @ {q['hA']}" if q["kind"] == "GAME" else _prop_matchup_key(q["leg"])
        by_sport.setdefault(sport, {}).setdefault(matchup, []).append(q)

    status_line = (
        f"LIVE — {locked_count} of {len(qualifying)} legs actually locked"
        if live else
        f"DRY RUN — {len(qualifying)} legs qualified, nothing was written"
    )
    parts = [_EMAIL_WRAP_OPEN, f'<div style="font-size:12px;letter-spacing:1px;color:#999;text-transform:uppercase">{_esc(status_line)}</div>']

    high_hit = [q for q in qualifying if q["kind"] == "GAME" and _market_type(q.get("side")) == "ML"
                and (q.get("prob") or 0) >= _HIGH_HIT_P]
    if high_hit:
        n = len(high_hit)
        parts.append(f'<div style="background:rgba(255,221,0,.12);border:1px solid rgba(255,221,0,.4);'
                      f'border-radius:4px;padding:8px 12px;margin:10px 0;font-size:13px;color:#ffdd00">'
                      f'🔥 {n} HIGH HIT % moneyline pick{"s" if n != 1 else ""} today '
                      f'(75%+ model win probability, regardless of tier/EV)</div>')

    if not qualifying:
        parts.append('<div style="padding:20px 0;color:#999;font-size:14px">No PREMIUM/OPTIMAL legs cleared the bar today.</div>')
        parts.append(_EMAIL_WRAP_CLOSE)
        return "".join(parts)

    for sport in sorted(by_sport, key=lambda s: SPORT_DISPLAY_NAME.get(s, s)):
        matchups = by_sport[sport]
        total_legs = sum(len(v) for v in matchups.values())
        parts.append(f'<div style="font-size:13px;letter-spacing:2px;color:#00e5ff;text-transform:uppercase;'
                      f'margin:22px 0 10px;border-bottom:1px solid rgba(0,229,255,.25);padding-bottom:4px">'
                      f'{_esc(SPORT_DISPLAY_NAME.get(sport, sport))} ({total_legs})</div>')
        for matchup, legs in matchups.items():
            parts.append('<div style="background:#14001f;border-radius:6px;padding:12px 14px;margin-bottom:10px">')
            parts.append(f'<div style="font-weight:700;font-size:15px;color:#fff;margin-bottom:6px">{_esc(matchup)}</div>')
            parts.append("".join(_leg_html(q) for q in legs))
            mc_summary = next((l.get("mcSummary") for l in legs if l.get("mcSummary")), None)
            best = next((l.get("best") for l in legs if l.get("best")), None)
            if mc_summary or best:
                bits = []
                if mc_summary:
                    bits.append(_esc(mc_summary))
                if best:
                    bits.append(f'Best market value on this game: {_esc(best["label"])} ({TIER_LABEL.get(best.get("tierN"), "?")})')
                parts.append(f'<div style="border-top:1px solid rgba(255,255,255,.08);margin-top:8px;padding-top:8px;'
                              f'font-size:12px;color:#999;line-height:1.5">{"<br>".join(bits)}</div>')
            parts.append('</div>')
    parts.append(_EMAIL_WRAP_CLOSE)
    return "".join(parts)


def send_locks_email(qualifying: list[dict], live: bool, locked_count: int | None = None,
                      label: str = "", to: list[str] | None = None) -> None:
    recipients = to if to is not None else ([LOCKS_EMAIL_TO] if LOCKS_EMAIL_TO else [])
    if not recipients:
        log("No recipients (LOCKS_EMAIL_TO unset and none passed) — skipping locked-picks email")
        return
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tag = f"{label} " if label else ""
    subject = f"Clairvoyance — {'Locked' if live else '[DRY RUN] Would lock'} {tag}picks for {date_str} ({len(qualifying)})"
    body_html = build_locks_email_html(qualifying, live, locked_count)
    ok, msg = _send_gmail(subject, recipients, body_html)
    log(f"Locks email ({label or 'ALL'}) sent to {len(recipients)} recipient(s)" if ok else f"Locks email ({label or 'ALL'}) send failed: {msg}")


def _lock_qualifying_legs(page, qualifying: list[dict]) -> int:
    """Actually calls the real lockPick()/lockProp()/etc. for each leg.
    Shared by run_lock() (single-product early passes) and
    run_lock_segmented() (the main run's per-product loop) so there's one
    place this logic lives, not two copies that could drift."""
    locked = 0
    for q in qualifying:
        try:
            outcome = lock_game_leg(page, q) if q["kind"] == "GAME" else lock_prop_leg(page, q["sport"], q["leg"])
            if outcome == "locked":
                locked += 1
            else:
                log(f"  {outcome}: {q.get('label') or q.get('leg', {}).get('player')}")
        except Exception as exc:
            log(f"  FAILED to lock: {exc}")
    return locked


def run_lock(page, live: bool, only_sports: frozenset[str] | None = None, label: str = "",
              to: list[str] | None = None) -> None:
    """Single-product lock pass -- used by the early soccer/CFB workflows,
    which each run their own gather_legs() call at their own scheduled
    time (not part of the main run's per-product loop)."""
    log(f"=== AUTO-LOCK (PREMIUM/OPTIMAL){' — ' + label if label else ''} ===")
    result = gather_legs(page)
    qualifying = build_qualifying(result, only_sports=only_sports)
    log(f"Gathered {len(result.get('gameLegs') or [])} games' worth of markets, "
        f"{len(result.get('propLegs') or [])} prop legs total")
    log(f"{len(qualifying)} qualifying PREMIUM/OPTIMAL legs found" + (f" ({label.lower()} only)" if label else ""))

    for q in qualifying:
        if q["kind"] == "GAME":
            log(f"  [{q['sport']}] {q['label']} ({TIER_LABEL.get(q['tierN'], '?')})")
        else:
            leg = q["leg"]
            direction = "UNDER" if leg.get("over") is False else "OVER"
            log(f"  [{q['sport']} PROP] {leg.get('player')} {direction} {leg.get('line')} "
                f"{leg.get('stat')} ({leg.get('grade')})")

    if not live:
        log(f"[DRY RUN] Would lock {len(qualifying)} legs above (pass --live to write)")
        send_locks_email(qualifying, live=False, label=label, to=to)
        return

    if not qualifying:
        send_locks_email(qualifying, live=True, locked_count=0, label=label, to=to)
        return

    locked = _lock_qualifying_legs(page, qualifying)
    log(f"Locked {locked}/{len(qualifying)} legs")
    if locked > 0:
        flush_to_supabase(page)
        log("Flushed locks to Supabase")
    send_locks_email(qualifying, live=True, locked_count=locked, label=label, to=to)


def run_lock_segmented(page, live: bool) -> None:
    """Main (unscoped) lock run -- ONE gather_legs() call (the expensive
    part: real browser + live data warmups), then split into a separate
    qualifying-legs list + a separately-addressed email for each of the 8
    paid sport products (see _subscribers.py), plus one more pass for
    whatever isn't covered by any product (CBB/NCAAH market-read-back legs
    today, if/when those get wired into gather_legs), sent to the owner
    only. A subscriber to one product only ever sees that product's email;
    nothing is ever silently dropped -- every qualifying leg lands in
    exactly one of these passes."""
    log("=== AUTO-LOCK (PREMIUM/OPTIMAL) — ALL PRODUCTS ===")
    result = gather_legs(page)
    log(f"Gathered {len(result.get('gameLegs') or [])} games' worth of markets, "
        f"{len(result.get('propLegs') or [])} prop legs total")
    all_qualifying = build_qualifying(result)
    covered_sports: set[str] = set().union(*PRODUCT_SPORTS.values())
    total_locked = 0

    for product, sports in PRODUCT_SPORTS.items():
        qualifying = [q for q in all_qualifying if q["sport"] in sports]
        label = PRODUCT_LABEL[product]
        recipients = recipients_for(product)
        log(f"[{product}] {len(qualifying)} qualifying legs -> {len(recipients)} recipient(s)")
        if not live:
            send_locks_email(qualifying, live=False, label=label, to=recipients)
            continue
        locked = _lock_qualifying_legs(page, qualifying) if qualifying else 0
        total_locked += locked
        send_locks_email(qualifying, live=True, locked_count=locked, label=label, to=recipients)

    other_qualifying = [q for q in all_qualifying if q["sport"] not in covered_sports]
    log(f"[other] {len(other_qualifying)} qualifying legs (not a paid product yet -- owner only)")
    owner_to = [OWNER_EMAIL] if OWNER_EMAIL else None
    if not live:
        send_locks_email(other_qualifying, live=False, label="OTHER", to=owner_to)
    else:
        locked = _lock_qualifying_legs(page, other_qualifying) if other_qualifying else 0
        total_locked += locked
        send_locks_email(other_qualifying, live=True, locked_count=locked, label="OTHER", to=owner_to)

    if total_locked > 0:
        flush_to_supabase(page)
        log(f"Flushed {total_locked} total locks to Supabase")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="Actually write to Supabase. Default is dry-run (logs only).")
    ap.add_argument("--lock", action="store_true", help="Run only the auto-lock step")
    ap.add_argument("--settle", action="store_true", help="Run only the auto-settle step")
    ap.add_argument("--only-soccer", action="store_true",
                     help="Lock step only: restrict to the 5 European soccer leagues (CL/PL/"
                          "La Liga/Bundesliga/Serie A) -- deliberately NOT MLS, which doesn't "
                          "have an early-kickoff problem. For the early-morning pass timed "
                          "ahead of European kickoffs.")
    ap.add_argument("--only-cfb", action="store_true",
                     help="Lock step only: restrict to CFB. For the early-morning pass timed "
                          "ahead of the earliest college football kickoffs (10 AM MT+).")
    ap.add_argument("--app-url", default=APP_URL, help="Override the app URL (e.g. a local server for testing).")
    args = ap.parse_args()
    do_lock, do_settle = (args.lock, args.settle) if (args.lock or args.settle) else (True, True)
    if args.only_soccer and args.only_cfb:
        raise SystemExit("--only-soccer and --only-cfb are mutually exclusive")
    only_sports = EURO_SOCCER_SPORTS if args.only_soccer else frozenset({"CFB"}) if args.only_cfb else None
    label = "EUROPEAN SOCCER" if args.only_soccer else "CFB" if args.only_cfb else ""
    # Early passes route to that product's real (owner + paying
    # subscribers) list; soccer's early pass shares the same "soccer"
    # subscriber list the main run's MLS pass uses, so a soccer subscriber
    # gets both without needing two separate purchases.
    early_to = recipients_for("soccer") if args.only_soccer else recipients_for("cfb") if args.only_cfb else None

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1400, "height": 1000})
        page = context.new_page()
        log(f"Loading {args.app_url} …")
        page.goto(args.app_url, wait_until="load", timeout=60000)
        page.wait_for_timeout(3000)

        bet_count = load_bet_ledger(page)
        log(f"Loaded {bet_count} real bets from Supabase into headless session")

        if do_settle:
            settled = run_settle(page, args.live)
            send_settlement_email(settled, args.live)
        if do_lock:
            if only_sports is None:
                run_lock_segmented(page, args.live)
            else:
                run_lock(page, args.live, only_sports=only_sports, label=label, to=early_to)

        browser.close()

    log("Done." if args.live else "Done (dry-run — nothing was written).")


if __name__ == "__main__":
    main()
