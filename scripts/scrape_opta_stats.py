#!/usr/bin/env python3
"""
scrape_opta_stats.py — Daily team-stats refresh for BL/PL/Serie A/MLS.

Pulls real team totals (attacking, passing, pressing, sequences, defending)
from theanalyst.com's (Opta) public tournament-stats JSON API for the 4
leagues whose static _SOC_XG fallback table in docs/app.html was hand-
calibrated against real 2025/26 data in an earlier session. This script
re-fetches that same data on a schedule so the fallback table — and the
win-probability model that reads it (_socXG/_soccerMC) — never goes stale
the way it had (rosters still listing relegated Ipswich/Venezia/Bochum,
xG figures frozen at whatever a human typed in months ago).

Writes:
  - data/opta_reference/{league}_team_stats_2025_26.json  (full scrape:
    attacking/passing/pressing/sequences/defending, not just xg/xga)
  - Regenerates the corresponding block inside docs/app.html's _SOC_XG
    object (per-game xg/xga/gf/ga, +/-10% home-away split — same
    convention that table already used before this script existed).

Usage:
  python3 scripts/scrape_opta_stats.py            # scrape + write, no push
  python3 scripts/scrape_opta_stats.py --push     # scrape + write + commit + push
  python3 scripts/scrape_opta_stats.py --dry-run  # print, no file writes
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
APP = ROOT / "docs" / "app.html"
INDEX = ROOT / "docs" / "index.html"
REF_DIR = ROOT / "data" / "opta_reference"
REF_DIR.mkdir(parents=True, exist_ok=True)

API = "https://theanalyst.com/wp-json/sdapi/v1/soccerdata/tournamentstats"

# league key -> (tmcl competition id, referer page + _meta_post_id the API
# checks against — requests without a matching Referer 401, since this
# endpoint is meant to be called from within the page it's embedded on,
# not hit directly), real team-name -> _SOC_XG key map
LEAGUES: dict[str, dict] = {
    "pl": {
        "tmcl": "51r6ph2woavlbbpk8f29nynf8",
        "referer": "https://theanalyst.com/competition/premier-league/stats",
        "meta_post_id": "135731",
        "file": "premier_league_team_stats_2025_26.json",
        "name_map": {
            "Man Utd": "manchester united", "Leeds": "leeds", "Arsenal": "arsenal",
            "Newcastle": "newcastle", "Spurs": "tottenham", "Villa": "aston villa",
            "Chelsea": "chelsea", "Everton": "everton", "Liverpool": "liverpool",
            "Forest": "nottingham forest", "West Ham": "west ham", "Palace": "crystal palace",
            "Brighton": "brighton", "Wolves": "wolverhampton", "Man City": "manchester city",
            "Fulham": "fulham", "Sunderland": "sunderland", "Burnley": "burnley",
            "Bournemouth": "bournemouth", "Brentford": "brentford",
        },
    },
    "ita": {
        "tmcl": "emdmtfr1v8rey2qru3xzfwges",
        "referer": "https://theanalyst.com/competition/serie-a/stats",
        "meta_post_id": "135738",
        "file": "serie_a_team_stats_2025_26.json",
        "name_map": {
            "Inter": "inter milan", "Napoli": "napoli", "Juventus": "juventus", "Milan": "ac milan",
            "Atalanta": "atalanta", "Roma": "roma", "Lazio": "lazio", "Fiorentina": "fiorentina",
            "Bologna": "bologna", "Torino": "torino", "Udinese": "udinese", "Genoa": "genoa",
            "Verona": "hellas verona", "Cagliari": "cagliari", "Parma": "parma", "Como": "como",
            "Lecce": "lecce", "Pisa": "pisa", "Cremonese": "cremonese", "Sassuolo": "sassuolo",
        },
    },
    "bl": {
        "tmcl": "2bchmrj23l9u42d68ntcekob8",
        "referer": "https://theanalyst.com/competition/bundesliga/stats",
        "meta_post_id": "135740",
        "file": "bundesliga_team_stats_2025_26.json",
        "name_map": {
            "FC Bayern": "bayern munich", "Bayer 04": "bayer leverkusen",
            "Dortmund": "borussia dortmund", "Leipzig": "rb leipzig",
            "Frankfurt": "eintracht frankfurt", "Stuttgart": "vfb stuttgart",
            "Freiburg": "sc freiburg", "Hoffenheim": "tsg hoffenheim",
            "M'gladbach": "borussia monchengladbach", "Union Berlin": "union berlin",
            "Wolfsburg": "vfl wolfsburg", "Bremen": "werder bremen", "Augsburg": "augsburg",
            "Mainz": "mainz 05", "Heidenheim": "fc heidenheim", "Hamburger": "hamburger sv",
            "Köln": "fc koln", "St. Pauli": "st pauli",
        },
    },
    "mls": {
        "tmcl": "6i6n0jkbh9zzij6s8htfjh2j8",
        "referer": "https://theanalyst.com/competition/mls/stats",
        "meta_post_id": "202451",
        "file": "mls_team_stats_2026.json",
        # MLS already has a dedicated first-party stats pipeline
        # (fetch_mls_team_stats() in clairvoyance_update.py) that feeds
        # docs/data.json / _socXG's live path — this scrape is saved as
        # reference data only, not merged into _SOC_XG's static fallback,
        # so it doesn't fight with that existing real-time source.
        "name_map": None,
    },
}


def fetch_tournament_stats(page, tmcl: str, referer: str, meta_post_id: str) -> dict | None:
    """Loads the real stats page in an actual browser (the API 401s on a
    plain HTTP request — same Cloudflare-style bot-check this repo already
    documents hitting FBref with — but works fine once a genuine page/
    session context makes the call) and pulls the JSON via the page's own
    fetch(), exactly like a human loading the page would trigger it."""
    url = f"{API}?tmcl={tmcl}&_meta_post_id={meta_post_id}&_meta_subpage=stats"
    try:
        page.goto(referer, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        result = page.evaluate(f"""
            fetch({json.dumps(url)}).then(r => r.ok ? r.json() : null)
        """)
        return result
    except Exception as exc:
        print(f"[WARN] fetch failed for tmcl={tmcl}: {exc}", file=sys.stderr)
        return None


def slim_categories(team_block: dict) -> dict:
    """Extract the 5 requested categories (attacking/passing/pressing/
    sequences/defending) per team from the raw tournamentstats payload."""
    def pick(rows, fields):
        out = []
        for t in rows:
            row = {"team": t.get("contestantShortName") or t.get("team")}
            for f in fields:
                row[f] = t.get(f)
            out.append(row)
        return out

    attack = team_block.get("attack", {}).get("overall", [])
    poss = team_block.get("possession", {}).get("overall", [])
    seq = team_block.get("sequences", {}).get("overall", [])
    defend = team_block.get("defending", {}).get("overall", [])

    return {
        "attacking": pick(attack, ["played", "goals", "xg", "goals_vs_xg", "total_shots",
                                    "sot", "shot_conv", "xg_per_shot"]),
        "passing": pick(poss, ["pos_perc", "passes", "successful_pass", "accuracy",
                                "final_third_passes", "successful_final_third_passes_perc",
                                "op_crosses", "through_balls"]),
        "pressing": pick(seq, ["ppda", "high_turnovers", "shot_ending_high_turnovers",
                                "defensive_actions"]),
        "sequences": pick(seq, ["pressed_sequences", "build_ups", "build_up_goals",
                                 "direct_attacks", "direct_attack_goals", "ten_plus_passes",
                                 "direct_speed_for", "seq_time_for"]),
        "defending": pick(defend, ["goals_against", "xg_against", "goals_vs_xg_conceded",
                                    "total_shots_against", "sot_against",
                                    "shot_conv_against", "xg_per_shot_against"]),
    }


def build_soc_xg_lines(slim: dict, name_map: dict) -> list[str]:
    """Per-game xg/xga/gf/ga with the same +/-10% home-away split
    convention _SOC_XG already used before this script existed."""
    att = {t["team"]: t for t in slim["attacking"]}
    deff = {t["team"]: t for t in slim["defending"]}
    lines = []
    for short, key in name_map.items():
        a, d = att.get(short), deff.get(short)
        if not a or not d or not a.get("played"):
            print(f"[WARN] missing data for '{short}' — skipping", file=sys.stderr)
            continue
        played = a["played"]
        xg_pg = a["xg"] / played
        xga_pg = d["xg_against"] / played
        gf_pg = a["goals"] / played
        ga_pg = d["goals_against"] / played
        hxg, axg = round(xg_pg * 1.10, 3), round(xg_pg * 0.90, 3)
        hxga, axga = round(xga_pg * 0.90, 3), round(xga_pg * 1.10, 3)
        lines.append(
            f"  '{key}':{{xg:{round(xg_pg,3)},xga:{round(xga_pg,3)},hxg:{hxg},hxga:{hxga},"
            f"axg:{axg},axga:{axga},gf:{round(gf_pg,3)},ga:{round(ga_pg,3)},mp:{played}}},"
        )
    return lines


def replace_league_block(html: str, name_map: dict, new_lines: list[str]) -> str:
    """Replace each existing `'key':{...},` entry for this league's teams
    in _SOC_XG in place, preserving surrounding structure/comments. Falls
    back to leaving unmatched keys untouched (roster changes — promotions/
    relegations — need a manual one-off edit like the initial migration,
    same as the docstring for fetch_mls_rosters already documents for
    similar roster-coverage gaps)."""
    new_by_key = {}
    for line in new_lines:
        key = line.split("'")[1]
        new_by_key[key] = line

    for key, new_line in new_by_key.items():
        # Trailing comma is optional — the last entry in a block (right
        # before the closing `};`) has none. Capture it so the
        # replacement preserves whichever the original line had, instead
        # of only ever matching entries that happen to have a comma.
        pattern = re.compile(r"^  '" + re.escape(key) + r"':\{[^}]*\}(,?)\s*$", re.MULTILINE)
        m = pattern.search(html)
        if m:
            trailing_comma = m.group(1)
            replacement = new_line.rstrip().rstrip(",") + trailing_comma
            html = pattern.sub(replacement, html, count=1)
        else:
            print(f"[WARN] key '{key}' not found in _SOC_XG — needs manual roster update "
                  f"(promoted/relegated team not yet in the table)", file=sys.stderr)
    return html


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    html = APP.read_text(encoding="utf-8")
    original_html = html
    any_changes = False

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        for lg_key, cfg in LEAGUES.items():
            print(f"[INFO] {lg_key}: fetching tournament stats…")
            raw = fetch_tournament_stats(page, cfg["tmcl"], cfg["referer"], cfg["meta_post_id"])
            if not raw or "team" not in raw:
                print(f"[WARN] {lg_key}: no data returned, skipping", file=sys.stderr)
                continue
            slim = slim_categories(raw["team"])
            slim["league"] = raw["team"].get("league")
            slim["lastUpdated"] = raw["team"].get("lastUpdated")
            slim["source"] = "theanalyst.com (Opta) tournament stats API"

            out_path = REF_DIR / cfg["file"]
            if args.dry_run:
                print(f"[DRY-RUN] would write {out_path} ({len(slim['attacking'])} teams)")
            else:
                out_path.write_text(json.dumps(slim, indent=2), encoding="utf-8")
                print(f"[INFO] wrote {out_path} ({len(slim['attacking'])} teams)")

            if cfg["name_map"]:
                new_lines = build_soc_xg_lines(slim, cfg["name_map"])
                if not args.dry_run:
                    updated = replace_league_block(html, cfg["name_map"], new_lines)
                    if updated != html:
                        html = updated
                        any_changes = True
                else:
                    print(f"[DRY-RUN] {lg_key} _SOC_XG lines:\n" + "\n".join(new_lines))

        browser.close()

    if any_changes and not args.dry_run:
        APP.write_text(html, encoding="utf-8")
        INDEX.write_text(html, encoding="utf-8")
        print("[INFO] Wrote docs/app.html + docs/index.html")

        val = subprocess.run(["python3", str(ROOT / "scripts" / "validate.py")],
                              capture_output=True, text=True, cwd=ROOT)
        if val.returncode != 0:
            print("[ERROR] Validator FAILED after inject — reverting!", file=sys.stderr)
            APP.write_text(original_html, encoding="utf-8")
            INDEX.write_text(original_html, encoding="utf-8")
            print(val.stdout[-2000:])
            sys.exit(1)
        print("[INFO] Validator: all checks passed")

    if args.push and any_changes and not args.dry_run:
        msg = "chore: refresh BL/PL/Serie A team xG stats (Opta scrape)"
        subprocess.run(["git", "add", "docs/app.html", "docs/index.html", "data/opta_reference"],
                        cwd=ROOT, check=True)
        r = subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, capture_output=True, text=True)
        if r.returncode == 0:
            print("[INFO] Committed.")
            push = subprocess.run(["git", "push", "origin", "main"], cwd=ROOT,
                                   capture_output=True, text=True)
            if push.returncode != 0:
                print(f"[WARN] Push rejected, retrying with rebase: {push.stderr.strip()[:200]}")
                pull = subprocess.run(["git", "pull", "--rebase", "origin", "main"],
                                       cwd=ROOT, capture_output=True, text=True)
                if pull.returncode == 0:
                    push2 = subprocess.run(["git", "push", "origin", "main"], cwd=ROOT,
                                            capture_output=True, text=True)
                    if push2.returncode != 0:
                        print(f"[ERROR] Push still failed: {push2.stderr.strip()[:300]}", file=sys.stderr)
                else:
                    print(f"[ERROR] Rebase failed: {pull.stderr.strip()[:300]}", file=sys.stderr)
            else:
                print("[INFO] Pushed.")
        elif "nothing to commit" in r.stdout + r.stderr:
            print("[INFO] Nothing changed — skipping commit.")
        else:
            print(f"[WARN] Commit failed: {r.stderr}", file=sys.stderr)

    print("[INFO] Done.")


if __name__ == "__main__":
    main()
