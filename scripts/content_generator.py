#!/usr/bin/env python3
from __future__ import annotations
"""
content_generator.py — Clairvoyance Daily Content Engine (v2)

5 daily posting slots (Mountain Time):
  10am   — Morning Preview      → post ~10:00 AM MT
  2pm    — Midday Adjustments   → post ~2:00 PM MT
  445pm  — Pre-Game Window      → post ~4:45 PM MT
  7pm    — Live + Late Slate    → post ~7:00 PM MT
  10pm   — Day Recap            → post ~10:00 PM MT

Output: ~/Desktop/Clairvoyance/YYYY-MM-DD/
  Files named: {date}_{Platform}_{time}_{label}.txt / .png
  Example: 2026-05-20_X_10am_morning-preview.txt
           2026-05-20_Instagram_10am_morning-preview.png

Usage:
  python3 scripts/content_generator.py              # auto-detect slot from MT time
  python3 scripts/content_generator.py --slot 10am
  python3 scripts/content_generator.py --slot all   # generate all 5 slots
  python3 scripts/content_generator.py --verbose
  python3 scripts/content_generator.py --print
"""

import argparse, json, os, subprocess, sys
from datetime import datetime, date, timezone, timedelta
from pathlib import Path

# ── .env loader ───────────────────────────────────────────────────────────────
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            _v = _v.strip().strip('"').strip("'")
            if _v:
                os.environ.setdefault(_k.strip(), _v)

ROOT        = Path(__file__).parent.parent
FE_DATA     = ROOT / "frontend" / "data.json"
FE_SOCIAL   = ROOT / "frontend" / "social_copy.json"
DC_SOCIAL   = ROOT / "docs"     / "social_copy.json"
DESKTOP_DIR = Path.home() / "Desktop" / "Clairvoyance"
CARD_SCRIPT = Path(__file__).parent / "generate_card.py"

try:
    import anthropic
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "anthropic"], check=True)
    import anthropic

# ── Time (system locale = Mountain Time) ─────────────────────────────────────
NOW_MT       = datetime.now()
HOUR_MT      = NOW_MT.hour
DATE_MT      = NOW_MT.date()
DATE_DISPLAY = NOW_MT.strftime("%B %d, %Y")
DATE_SLUG    = NOW_MT.strftime("%Y-%m-%d")

# ── Tennis gate: only during Grand Slams ─────────────────────────────────────
_SLAMS_2026 = [
    (date(2026,  5, 25), date(2026,  6,  8)),   # Roland Garros
    (date(2026,  6, 29), date(2026,  7, 12)),   # Wimbledon
    (date(2026,  8, 31), date(2026,  9, 13)),   # US Open
]
INCLUDE_TENNIS = any(s <= DATE_MT <= e for s, e in _SLAMS_2026)

# ── Slot system ───────────────────────────────────────────────────────────────
SLOT_NAMES = ["10am", "2pm", "445pm", "7pm", "10pm"]
SLOT_LABELS = {
    "10am":  "Morning Preview",
    "2pm":   "Midday Adjustments",
    "445pm": "Pre-Game Window",
    "7pm":   "Live + Late Slate",
    "10pm":  "Day Recap",
}
SLOT_POST_TIMES = {
    "10am":  "10:00 AM Mountain Time",
    "2pm":   "2:00 PM Mountain Time",
    "445pm": "4:45 PM Mountain Time",
    "7pm":   "7:00 PM Mountain Time",
    "10pm":  "10:00 PM Mountain Time",
}
SLOT_SLUGS = {
    "10am":  "morning-preview",
    "2pm":   "midday",
    "445pm": "pregame",
    "7pm":   "live-update",
    "10pm":  "recap",
}

def _file_stem(slot: str, platform_slug: str) -> str:
    """e.g. 2026-05-20_X_10am_morning-preview"""
    return f"{DATE_SLUG}_{platform_slug}_{slot}_{SLOT_SLUGS[slot]}"

def detect_slot() -> str:
    if  9 <= HOUR_MT < 13: return "10am"
    if 13 <= HOUR_MT < 16: return "2pm"
    if 16 <= HOUR_MT < 18: return "445pm"
    if 18 <= HOUR_MT < 22: return "7pm"
    return "10pm"


# ── EV helpers ────────────────────────────────────────────────────────────────
def _ev_grade(edge_pct: float) -> str:
    if edge_pct >= 12: return "A+"
    if edge_pct >= 8:  return "A"
    if edge_pct >= 4:  return "B"
    if edge_pct >= 1:  return "C"
    return "D"

def _ev_label(edge_pct: float) -> str:
    grade = _ev_grade(edge_pct)
    return f"EV {grade} ({edge_pct:+.1f}%)"


# ── Context builder ───────────────────────────────────────────────────────────
def _ordinal(n: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")

def _game_line(g: dict) -> str:
    state = g.get("state", "pre")
    away, home = g.get("away", ""), g.get("home", "")
    score = ""
    if state in ("in", "post"):
        a, h = g.get("awayScore", 0), g.get("homeScore", 0)
        score = f" [{a}-{h}]"
        if state == "in":
            clk = g.get("displayClock", "")
            per = g.get("period", "")
            score += f" {_ordinal(per) if isinstance(per, int) else per} {clk}".rstrip()
        else:
            score += " FINAL"
    odds = ""
    ml_a, ml_h = g.get("awayML"), g.get("homeML")
    if ml_a and ml_h:
        odds = f" | ML {away} {ml_a:+d}/{home} {ml_h:+d}"
    ou = g.get("ou")
    if ou:
        odds += f" O/U {ou}"
    series = g.get("seriesNote", "")
    series_str = f" ({series})" if series else ""
    return f"  {away} @ {home}{score}{odds}{series_str}"


def extract_context(data: dict, slot: str) -> str:
    lines = [f"Date: {DATE_DISPLAY} (Mountain Time)", f"Slot: {slot} — {SLOT_LABELS[slot]}", ""]

    # ── Model picks with EV grades ────────────────────────────────────────────
    best_bets = data.get("bestBets", [])
    if best_bets:
        lines.append("=== MODEL PICKS — EV RATINGS ===")
        for b in best_bets[:8]:
            if not isinstance(b, dict):
                lines.append(f"  {b}")
                continue
            game  = b.get("game", "")
            pick  = b.get("pick", "")
            prob  = b.get("modelProb", b.get("prob", 0))
            impl  = b.get("impliedProb", b.get("implied", 0))
            edge  = b.get("edge", round((prob - impl) * 100, 1) if prob and impl else 0)
            conf  = b.get("confidence", "")
            ev    = _ev_label(edge)
            lines.append(
                f"  {game} | {pick} | Mdl {prob*100:.1f}% | Mkt {impl*100:.1f}% | Edge {edge:+.1f}% | {ev} | {conf}"
            )
        lines.append("")

    # ── Settled record + recent results ───────────────────────────────────────
    settled = data.get("settled", [])
    if settled:
        wins   = sum(1 for s in settled if s.get("result") == "win")
        losses = sum(1 for s in settled if s.get("result") == "loss")
        pushes = sum(1 for s in settled if s.get("result") == "push")
        units  = sum(s.get("units", 0) for s in settled)
        lines.append(f"=== SEASON RECORD === {wins}W-{losses}L-{pushes}P ({units:+.1f}u)")
        recent = settled[-5:]
        for s in recent:
            r = s.get("result", "").upper()
            u = s.get("units", 0)
            g = s.get("game", "")
            p = s.get("pick", "")
            lines.append(f"  {r} {u:+.1f}u — {g}: {p}")
        lines.append("")

    # ── Today's slates ────────────────────────────────────────────────────────
    for sport, key in [("MLB", "mlb"), ("NBA", "nba"), ("NHL", "nhl")]:
        today = data.get(key, {}).get("today", [])
        if not today:
            continue
        live_ct  = sum(1 for g in today if g.get("state") == "in")
        final_ct = sum(1 for g in today if g.get("state") == "post")
        lines.append(
            f"=== {sport} TODAY — {len(today)} games ({live_ct} live, {final_ct} final) ==="
        )
        for g in today[:10]:
            lines.append(_game_line(g))
        lines.append("")

    # ── Tomorrow's slate ──────────────────────────────────────────────────────
    mlb_tom = data.get("mlb", {}).get("tomorrow", [])
    if mlb_tom:
        lines.append(f"=== MLB TOMORROW — {len(mlb_tom)} games ===")
        for g in mlb_tom[:5]:
            lines.append(f"  {g.get('away','')} @ {g.get('home','')}")
        lines.append("")

    # ── Player props from Linemate recent-form ────────────────────────────────
    lm = data.get("linemateForm", {})
    for sk in ["nba", "mlb", "nhl"]:
        props = lm.get(sk, [])
        if not props:
            continue
        lines.append(f"=== {sk.upper()} PLAYER PROPS — RECENT FORM ===")
        for p in props[:6]:
            if not isinstance(p, dict):
                continue
            name    = p.get("player", "")
            cat     = p.get("category", "")
            line_v  = p.get("line", "")
            trend   = p.get("trend", "")
            hit_pct = p.get("hitRate", "")
            ev_note = p.get("ev", "")
            lines.append(
                f"  {name} | {cat} {line_v} | Hit% {hit_pct} | Trend: {trend} | {ev_note}"
            )
        lines.append("")

    # ── NHL MoneyPuck xGF% ────────────────────────────────────────────────────
    mp_teams = data.get("mp", {}).get("teams", {})
    if mp_teams:
        sorted_teams = sorted(
            [(k, v) for k, v in mp_teams.items() if isinstance(v, dict)],
            key=lambda x: x[1].get("5on5", {}).get("xgfPct", 0),
            reverse=True,
        )
        if sorted_teams:
            lines.append("=== NHL 5v5 xGF% LEADERS ===")
            for abbr, stats in sorted_teams[:5]:
                s = stats.get("5on5", {})
                lines.append(f"  {abbr}: xGF% {s.get('xgfPct', 0):.3f}")
            lines.append("")

    # ── Weather factors ───────────────────────────────────────────────────────
    weather = data.get("weather", {})
    windy = [
        (k, v) for k, v in weather.items()
        if not v.get("indoor") and (v.get("wind") or 0) >= 10
    ]
    if windy:
        lines.append("=== MLB WEATHER FACTORS ===")
        for team, w in windy[:4]:
            lines.append(
                f"  {team}: {w.get('temp')}°F, {w.get('wind')} mph, {w.get('condition')}"
            )
        lines.append("")

    # ── Tennis (only during Grand Slams) ──────────────────────────────────────
    if INCLUDE_TENNIS:
        atp = data.get("tennis", {}).get("atpElo", [])
        if atp:
            lines.append("=== ATP ELO TOP 5 ===")
            for p in atp[:5]:
                lines.append(f"  {p.get('rank')}. {p.get('name')} — ELO {p.get('elo')}")
            lines.append("")
        schedule = data.get("tennis", {}).get("schedule", [])
        if schedule:
            lines.append("=== TENNIS TODAY ===")
            for m in schedule[:8]:
                p1    = m.get("player1", "")
                p2    = m.get("player2", "")
                state = m.get("state", "pre")
                tour  = m.get("tour", "")
                tourn = m.get("tournament", "")
                lines.append(f"  {p1} vs {p2} | {tourn} ({tour}) | {state}")
            lines.append("")

    return "\n".join(lines)


# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are the content writer for Clairvoyance Engine, a sports intelligence platform.

Platform handles:
  X (Twitter): @ClairvoyanceEng
  Instagram:   @clairvoyanceengine

Voice: analytical, transparent, data-first. Never hype. No prediction guarantees.
Tone: Bloomberg Sports meets sharp bettor. Concise. Professional. Confident.

EV Rating scale (always use when referencing picks or props):
  A+ = edge > 12%  |  A = 8-12%  |  B = 4-8%  |  C = 1-4%  |  D = <1%

Content rules (strictly follow every time):
- NEVER use: LOCK, guaranteed, can't miss, fire, 🔥, free play, easy money
- Always include model probability, implied market prob, and EV grade when data is available
- For player props: show hit rate trend and EV grade — do NOT say "best bet"
- Reference trends, patterns, and line movement context — not "insider information"
- NEVER reveal the engine's data sources, model architecture, or proprietary edge methodology
- X posts: ≤280 chars, info-dense, no filler; do NOT include the handle in post text
- X thread: 4 tweets, each self-contained with data, building on the previous
- Instagram: 2-3 sentences, narrative but data-first, ends with a specific concrete insight
- Hashtags: analytical/community tags only (no #FreePlays, #BettingPicks gambling spam)
- story_bullets: each ≤10 words, works as a standalone Story chip
- highlight_game: the single most analytically interesting matchup of the slot, or null

Output EXACTLY this JSON — no markdown fences, no explanation outside the JSON:
{
  "x_post": "string (≤280 chars)",
  "x_thread": ["tweet 1", "tweet 2", "tweet 3", "tweet 4"],
  "instagram_caption": "string",
  "instagram_hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "story_bullets": ["≤10 words", "≤10 words", "≤10 words"],
  "content_theme": "morning_preview|midday_adjustment|pregame|live_update|recap",
  "highlight_game": "AWAY @ HOME or null"
}"""


# ── Slot-specific prompts ─────────────────────────────────────────────────────
def _slot_instruction(slot: str) -> str:
    return {
        "10am": (
            f"Generate MORNING PREVIEW content for {DATE_DISPLAY}.\n\n"
            "Focus: Today's full slate across MLB/NBA/NHL. The engine's approach for the day — "
            "which matchups have the clearest signal, which are noisy. Lead with the highest-EV "
            "model pick(s) and include at least 2 specific player props with their EV grade in the thread. "
            "Include weather context if it affects totals. Reference any active playoff series. "
            "Set an analytical tone — what is the engine watching today and why?"
        ),
        "2pm": (
            f"Generate MIDDAY ADJUSTMENTS content for {DATE_DISPLAY}.\n\n"
            "Focus: What has changed since the morning post. Line movement direction (toward or away "
            "from the model), any early game results, injury news impact on the model's outputs. "
            "If morning picks look better or worse at current lines, say so explicitly. "
            "Educational angle: explain WHY a line moved in data terms — public percentage, "
            "sharp money, injury report. Reference the morning post's picks and update confidence levels. "
            "Include updated prop landscape with EV grades at current closing lines."
        ),
        "445pm": (
            f"Generate PRE-GAME content for {DATE_DISPLAY}.\n\n"
            "Focus: Tonight's primetime games (ET slate, tip-off/first-pitch within 2-3 hours). "
            "Final model reads before action begins. Closing line analysis — are markets converging "
            "with the model or diverging? If props are closing in a favorable direction, note it. "
            "Build analytical anticipation without hype — this is the last pre-game assessment. "
            "Be specific about what the model expects and why, without revealing methodology."
        ),
        "7pm": (
            f"Generate LIVE + LATE SLATE content for {DATE_DISPLAY}.\n\n"
            "Focus: Games currently in progress (check 'in' state in the data) — current scores, "
            "how the game flow compares to model projections. Preview of the late west-coast slate "
            "with fresh model reads. If any earlier picks are tracking well or have settled, "
            "reference them transparently. Keep a real-time feel — specific scores, periods, live context. "
            "Include late-slate prop opportunities with EV grades."
        ),
        "10pm": (
            f"Generate DAY RECAP content for {DATE_DISPLAY}.\n\n"
            "Focus: Full-day accountability report. All results across sports — wins, losses, exact units. "
            "What did the model identify that markets missed? What did it get wrong and why? "
            "Show the model's quality through honest transparency, not spin. "
            "Highlight the most analytically notable call of the day (correct OR incorrect). "
            "Close with one forward-looking insight for tomorrow — what does the engine see ahead."
        ),
    }[slot]


def build_prompt(context: str, slot: str) -> str:
    return f"""{_slot_instruction(slot)}

CURRENT CLAIRVOYANCE DATA:
{context}

Generate platform-specific content. Remember: data-first, transparent, never hype, always EV-graded."""


# ── Claude API call ───────────────────────────────────────────────────────────
def generate_content(data: dict, slot: str, verbose: bool = False) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[WARN] ANTHROPIC_API_KEY not set — skipping content generation", file=sys.stderr)
        return {}

    context = extract_context(data, slot)
    if verbose:
        print(f"[DEBUG] Context ({len(context)} chars):\n{context}\n")

    client = anthropic.Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=1600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_prompt(context, slot)}],
        )
        raw = message.content[0].text.strip()

        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:]).strip()
        if raw.endswith("```"):
            raw = "\n".join(raw.split("\n")[:-1]).strip()

        result              = json.loads(raw)
        result["generated_at"] = NOW_MT.strftime("%Y-%m-%d %H:%M MT")
        result["slot"]      = slot
        result["slot_label"] = SLOT_LABELS[slot]
        return result

    except json.JSONDecodeError as exc:
        print(f"[ERROR] JSON parse failed: {exc}", file=sys.stderr)
        if verbose:
            print(f"[DEBUG] Raw:\n{raw[:1000]}", file=sys.stderr)
        return {}
    except Exception as exc:
        print(f"[ERROR] Claude API: {exc}", file=sys.stderr)
        return {}


# ── Desktop output writers ────────────────────────────────────────────────────
def _header(slot: str, platform_name: str, handle: str) -> list[str]:
    """Shared file header block — platform, post time, date, slot."""
    return [
        "═" * 62,
        f"  PLATFORM :  {platform_name}  ({handle})",
        f"  POST TIME:  {SLOT_POST_TIMES[slot]}",
        f"  DATE     :  {DATE_DISPLAY}",
        f"  SLOT     :  {SLOT_LABELS[slot]}",
        "═" * 62,
        "",
    ]


def _write_x_file(path: Path, content: dict) -> None:
    slot   = content.get("slot", "10am")
    x_post = content.get("x_post", "")
    thread = content.get("x_thread", [])
    lines  = _header(slot, "X (Twitter)", "@ClairvoyanceEng")
    lines += [
        f"POST  ({len(x_post)}/280 chars — copy and paste directly):",
        "─" * 62,
        x_post,
        "",
        "─" * 62,
        "THREAD  (post as reply chain):",
        "─" * 62,
    ]
    for i, tweet in enumerate(thread, 1):
        lines.append(f"[{i}]  {tweet}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_ig_file(path: Path, content: dict) -> None:
    slot     = content.get("slot", "10am")
    caption  = content.get("instagram_caption", "")
    hashtags = " ".join(f"#{t.lstrip('#')}" for t in content.get("instagram_hashtags", []))
    bullets  = content.get("story_bullets", [])
    lines    = _header(slot, "Instagram", "@clairvoyanceengine")
    lines   += [
        "CAPTION  (copy and paste):",
        "─" * 62,
        caption,
        "",
        "─" * 62,
        "HASHTAGS  (paste in first comment or end of caption):",
        "─" * 62,
        hashtags,
        "",
        "─" * 62,
        "STORY BULLETS  (use for Stories / carousel chips):",
        "─" * 62,
    ]
    for b in bullets:
        lines.append(f"  •  {b}")
    path.write_text("\n".join(lines), encoding="utf-8")


def _generate_card(out_path: Path, platform: str) -> None:
    """Invoke generate_card.py for a given platform and output path."""
    cmd = [
        sys.executable, str(CARD_SCRIPT),
        "--platform", platform,
        "--output", str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(
            f"[WARN] Card generation failed ({platform}): {result.stderr[:300]}",
            file=sys.stderr,
        )
    elif out_path.exists():
        kb = out_path.stat().st_size // 1024
        print(f"[INFO] {out_path.name} ({kb} KB)")


def write_desktop_output(content: dict) -> None:
    """Write all files to ~/Desktop/Clairvoyance/YYYY-MM-DD/ with descriptive names."""
    if not content:
        return

    slot     = content.get("slot", "10am")
    date_dir = DESKTOP_DIR / DATE_SLUG
    date_dir.mkdir(parents=True, exist_ok=True)

    x_stem  = _file_stem(slot, "X")
    ig_stem = _file_stem(slot, "Instagram")

    _write_x_file( date_dir / f"{x_stem}.txt",  content)
    _write_ig_file(date_dir / f"{ig_stem}.txt", content)

    _generate_card(date_dir / f"{x_stem}.png",  "x")
    _generate_card(date_dir / f"{ig_stem}.png", "instagram")

    print(f"[INFO] Output → {date_dir}")


def write_social_json(content: dict) -> None:
    """Mirror latest content to frontend/social_copy.json + docs/social_copy.json."""
    if not content:
        return
    payload = json.dumps(content, indent=2)
    FE_SOCIAL.write_text(payload)
    DC_SOCIAL.write_text(payload)
    print("[INFO] social_copy.json updated → frontend/ + docs/")


def print_content(content: dict) -> None:
    if not content:
        return
    print(f"\n{'='*62}")
    print(f"SLOT:  {content.get('slot_label','').upper()}  |  {content.get('generated_at','')}")
    print(f"THEME: {content.get('content_theme','')}")
    print(f"{'='*62}")
    x_post = content.get("x_post", "")
    print(f"\nX POST ({len(x_post)} chars):\n  {x_post}")
    print(f"\nX THREAD:")
    for i, t in enumerate(content.get("x_thread", []), 1):
        print(f"  [{i}] {t}")
    print(f"\nINSTAGRAM:\n  {content.get('instagram_caption','')}")
    print(f"  #{' #'.join(content.get('instagram_hashtags',[]))}")
    print(f"\nSTORY BULLETS:")
    for b in content.get("story_bullets", []):
        print(f"  • {b}")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Clairvoyance Content Generator")
    parser.add_argument(
        "--slot",
        choices=SLOT_NAMES + ["all"],
        help="Content slot to generate (default: auto-detect from MT time)",
    )
    parser.add_argument("--verbose", action="store_true", help="Print debug context")
    parser.add_argument("--print",   action="store_true", dest="print_output",
                        help="Print generated content to stdout")
    args = parser.parse_args()

    if not FE_DATA.exists():
        print("[ERROR] data.json not found — run clairvoyance_update.py first", file=sys.stderr)
        sys.exit(1)

    data  = json.loads(FE_DATA.read_text())
    slots = SLOT_NAMES if args.slot == "all" else [args.slot or detect_slot()]

    any_success = False
    for slot in slots:
        label = SLOT_LABELS[slot]
        print(f"[INFO] Generating: {slot} ({label})")

        content = generate_content(data, slot, verbose=args.verbose)
        if content:
            write_desktop_output(content)
            write_social_json(content)
            if args.print_output or args.verbose:
                print_content(content)
            any_success = True
        else:
            print(f"[WARN] No content for slot: {slot}", file=sys.stderr)

    sys.exit(0 if any_success else 1)


if __name__ == "__main__":
    main()
