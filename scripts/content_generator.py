#!/usr/bin/env python3
from __future__ import annotations
"""
content_generator.py — Clairvoyance Social Media Content Generator

Reads data.json, calls Claude API to generate platform-specific content,
writes social_copy.json to frontend/ and docs/.

Usage:
  python3 scripts/content_generator.py              # auto-detect session from time
  python3 scripts/content_generator.py --session morning
  python3 scripts/content_generator.py --print      # also print to stdout
  python3 scripts/content_generator.py --verbose    # debug context output
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Load .env from project root if present (key=value format, one per line)
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            _v = _v.strip().strip('"').strip("'")
            if _v:  # skip empty values
                os.environ.setdefault(_k.strip(), _v)

ROOT      = Path(__file__).parent.parent
FE_DATA   = ROOT / "frontend" / "data.json"
FE_SOCIAL = ROOT / "frontend" / "social_copy.json"
DC_SOCIAL = ROOT / "docs"     / "social_copy.json"

try:
    import anthropic
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "anthropic"], check=True)
    import anthropic

NOW         = datetime.now(timezone.utc)
ET          = NOW - timedelta(hours=5)
HOUR_ET     = ET.hour
DATE_DISPLAY = ET.strftime("%B %d, %Y")
DATE_SHORT  = ET.strftime("%m/%d")


# ── session detection ─────────────────────────────────────────────────────────

def get_session() -> str:
    if 5  <= HOUR_ET < 12: return "morning"
    if 12 <= HOUR_ET < 17: return "afternoon"
    if 17 <= HOUR_ET < 22: return "evening"
    return "night"


# ── data context builder ──────────────────────────────────────────────────────

def _ordinal(n: int) -> str:
    return {1:"1st",2:"2nd",3:"3rd"}.get(n, f"{n}th")

def _game_line(g: dict) -> str:
    """Format a single game into a compact context line."""
    state = g.get("state", "pre")
    away, home = g.get("away", ""), g.get("home", "")
    score = ""
    if state in ("in", "post"):
        a_score = g.get("awayScore", 0)
        h_score = g.get("homeScore", 0)
        score = f" [{a_score}-{h_score}]"
        if state == "in":
            clk = g.get("displayClock", "")
            per = g.get("period", "")
            score += f" {_ordinal(per) if isinstance(per, int) else per} {clk}".rstrip()
        else:
            score += " FINAL"
    odds = ""
    ml_a, ml_h = g.get("awayML"), g.get("homeML")
    if ml_a and ml_h:
        odds = f" | ML {away} {ml_a:+d} / {home} {ml_h:+d}"
    ou = g.get("ou")
    if ou:
        odds += f" O/U {ou}"
    series = g.get("seriesNote", "")
    series_str = f" ({series})" if series else ""
    return f"  {away} @ {home}{score}{odds}{series_str}"

def extract_context(data: dict, session: str) -> str:
    lines = [f"Date: {DATE_DISPLAY}", f"Session: {session}", ""]

    # Best bets (highest priority)
    best_bets = data.get("bestBets", [])
    if best_bets:
        lines.append("=== MODEL BEST BETS ===")
        for b in best_bets[:6]:
            if isinstance(b, dict):
                game  = b.get("game", "")
                pick  = b.get("pick", "")
                prob  = b.get("modelProb", b.get("prob", 0))
                impl  = b.get("impliedProb", b.get("implied", 0))
                edge  = b.get("edge", round((prob - impl) * 100, 1) if prob and impl else 0)
                conf  = b.get("confidence", "")
                lines.append(f"  {game} | {pick} | Model: {prob*100:.1f}% | Implied: {impl*100:.1f}% | Edge: {edge:+.1f}% | {conf}")
            else:
                lines.append(f"  {b}")
        lines.append("")

    # Settled record
    settled = data.get("settled", [])
    if settled:
        wins   = sum(1 for s in settled if s.get("result") == "win")
        losses = sum(1 for s in settled if s.get("result") == "loss")
        pushes = sum(1 for s in settled if s.get("result") == "push")
        units  = sum(s.get("units", 0) for s in settled)
        lines.append(f"=== CLAIRVOYANCE RECORD === {wins}W-{losses}L-{pushes}P ({units:+.1f}u)")
        lines.append("")

    # Today's game slates
    for sport, key in [("MLB", "mlb"), ("NBA", "nba"), ("NHL", "nhl")]:
        today = data.get(key, {}).get("today", [])
        if not today:
            continue
        live_ct  = sum(1 for g in today if g.get("state") == "in")
        final_ct = sum(1 for g in today if g.get("state") == "post")
        lines.append(f"=== {sport} TODAY — {len(today)} games ({live_ct} live, {final_ct} final) ===")
        for g in today[:8]:
            lines.append(_game_line(g))
        lines.append("")

    # Tomorrow's slate (brief)
    mlb_tom = data.get("mlb", {}).get("tomorrow", [])
    if mlb_tom:
        lines.append(f"=== MLB TOMORROW — {len(mlb_tom)} games ===")
        for g in mlb_tom[:4]:
            lines.append(f"  {g.get('away','')} @ {g.get('home','')}")
        lines.append("")

    # MoneyPuck: top NHL teams by 5v5 xGF%
    mp_teams = data.get("mp", {}).get("teams", {})
    if mp_teams:
        sorted_teams = sorted(
            [(k, v) for k, v in mp_teams.items() if isinstance(v, dict)],
            key=lambda x: x[1].get("5on5", {}).get("xgfPct", 0),
            reverse=True,
        )
        if sorted_teams:
            lines.append("=== NHL MoneyPuck 5v5 xGF% LEADERS ===")
            for abbr, stats in sorted_teams[:5]:
                s = stats.get("5on5", {})
                lines.append(f"  {abbr}: xGF% {s.get('xgfPct', 0):.3f} | GF {s.get('gf', 0):.0f} | GA {s.get('ga', 0):.0f}")
            lines.append("")

    # Tennis ELO top 5 ATP + WTA
    atp = data.get("tennis", {}).get("atpElo", [])
    wta = data.get("tennis", {}).get("wtaElo", [])
    if atp:
        lines.append("=== ATP ELO TOP 5 ===")
        for p in atp[:5]:
            lines.append(f"  {p.get('rank')}. {p.get('name')} — ELO {p.get('elo')} | H {p.get('hElo')} | C {p.get('cElo')}")
        lines.append("")
    if wta:
        lines.append("=== WTA ELO TOP 5 ===")
        for p in wta[:5]:
            lines.append(f"  {p.get('rank')}. {p.get('name')} — ELO {p.get('elo')}")
        lines.append("")

    # Weather (outdoor parks with notable wind)
    weather = data.get("weather", {})
    windy = [(k, v) for k, v in weather.items()
             if not v.get("indoor") and v.get("wind") and v.get("wind", 0) >= 10]
    if windy:
        lines.append("=== MLB WEATHER FACTORS (wind ≥10 mph) ===")
        for team, w in windy[:4]:
            lines.append(f"  {team}: {w.get('temp')}°F, {w.get('wind')} mph, {w.get('condition')}")
        lines.append("")

    return "\n".join(lines)


# ── Claude prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are the content writer for Clairvoyance, a sports intelligence engine.

Voice: analytical, transparent, never hype, no "LOCK" language.
Tone: Bloomberg Sports meets sharp bettor. Concise. Data-driven. Professional.

Rules — strictly follow:
- NEVER use: LOCK, guaranteed, can't miss, fire, 🔥, free play, best bet of the day
- When model probabilities are available, always include them with the implied market prob and edge %
- Be transparent about uncertainty — show the model's reasoning, not just output
- Lead with data, follow with context
- For X posts: punchy, information-dense, max 280 chars, no generic filler
- For X threads: each tweet self-contained, builds on the last; include data in each
- For Instagram: slightly more narrative but still data-first; end with a clear insight
- Hashtags: analytical community, NOT gambling spam (no #bettingpicks, #freeplays)
- story_bullets: each under 10 words, work as standalone chips

Output EXACTLY this JSON — no markdown code fences, no explanation outside JSON:
{
  "x_post": "string (≤280 chars)",
  "x_thread": ["string", "string", "string"],
  "instagram_caption": "string (2-3 sentences, data-first, ends with insight)",
  "instagram_hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "story_bullets": ["≤10 words", "≤10 words", "≤10 words"],
  "content_theme": "morning_preview|afternoon_analysis|live_update|results|education",
  "highlight_game": "AWAY @ HOME or null"
}"""

_SESSION_INSTRUCTIONS = {
    "morning": (
        "Generate MORNING PREVIEW content. Focus on today's game slate, key matchups, "
        "model projections, line value, and any weather or injury factors."
    ),
    "afternoon": (
        "Generate MID-DAY ANALYSIS content. Focus on line movement since open, "
        "sharp money signals, any injury news impact on model output. "
        "Educational framing works well — explain WHY a line moved."
    ),
    "evening": (
        "Generate GAME TIME content. Focus on tonight's featured matchups, "
        "model confidence on any identified edges, and live tracking context. "
        "Build analytical anticipation without hype."
    ),
    "night": (
        "Generate LIVE/RESULTS content. Reference in-progress games with win probabilities, "
        "or completed final scores. Real-time feel. Accountability if there were picks."
    ),
}

def build_prompt(context: str, session: str) -> str:
    return f"""{_SESSION_INSTRUCTIONS[session]}

CURRENT CLAIRVOYANCE DATA:
{context}

Generate platform-specific content. Remember: data-first, transparent, never hype."""


# ── API call ──────────────────────────────────────────────────────────────────

def generate_content(data: dict, session: str | None = None, verbose: bool = False) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[WARN] ANTHROPIC_API_KEY not set — skipping content generation", file=sys.stderr)
        return {}

    if session is None:
        session = get_session()

    context = extract_context(data, session)
    if verbose:
        print(f"[DEBUG] Context ({len(context)} chars):\n{context}\n")

    client = anthropic.Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=1200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_prompt(context, session)}],
        )
        raw = message.content[0].text.strip()

        # Strip any accidental markdown fences
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:]).strip()
        if raw.endswith("```"):
            raw = "\n".join(raw.split("\n")[:-1]).strip()

        result = json.loads(raw)
        result["generated_at"] = ET.strftime("%Y-%m-%d %H:%M ET")
        result["session"]      = session
        return result

    except json.JSONDecodeError as exc:
        print(f"[ERROR] Could not parse Claude response: {exc}", file=sys.stderr)
        if verbose:
            print(f"[DEBUG] Raw response: {raw[:800]}", file=sys.stderr)
        return {}
    except Exception as exc:
        print(f"[ERROR] Claude API error: {exc}", file=sys.stderr)
        return {}


# ── write output ──────────────────────────────────────────────────────────────

def write_social_copy(content: dict) -> None:
    if not content:
        return
    payload = json.dumps(content, indent=2)
    FE_SOCIAL.write_text(payload)
    DC_SOCIAL.write_text(payload)
    print(f"[INFO] social_copy.json written → frontend/ + docs/")


def print_content(content: dict) -> None:
    if not content:
        return
    print(f"\n{'='*60}")
    print(f"SESSION: {content.get('session','').upper()}  |  {content.get('generated_at','')}")
    print(f"THEME:   {content.get('content_theme','')}")
    print(f"{'='*60}")
    print(f"\nX POST ({len(content.get('x_post',''))} chars):")
    print(f"  {content.get('x_post','')}")
    print(f"\nX THREAD:")
    for i, t in enumerate(content.get("x_thread", []), 1):
        print(f"  [{i}] {t}")
    print(f"\nINSTAGRAM:")
    print(f"  {content.get('instagram_caption','')}")
    print(f"  #{' #'.join(content.get('instagram_hashtags',[]))}")
    print(f"\nSTORIES:")
    for b in content.get("story_bullets", []):
        print(f"  • {b}")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Clairvoyance Social Content Generator")
    parser.add_argument("--session",  choices=["morning","afternoon","evening","night"])
    parser.add_argument("--verbose",  action="store_true")
    parser.add_argument("--print",    action="store_true", dest="print_output",
                        help="Print generated content to stdout")
    args = parser.parse_args()

    if not FE_DATA.exists():
        print("[ERROR] data.json not found — run clairvoyance_update.py first", file=sys.stderr)
        sys.exit(1)

    data    = json.loads(FE_DATA.read_text())
    content = generate_content(data, session=args.session, verbose=args.verbose)

    if content:
        write_social_copy(content)
        if args.print_output or args.verbose:
            print_content(content)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
