#!/usr/bin/env python3
"""
Log June 9, 2026 actual results into picks.json
Source: PrizePicks + Hard Rock Bet screenshots
"""
import json, time

bets = json.load(open('docs/picks.json'))

# Base timestamp for June 9 2026 ~8 PM ET
# Existing picks at ~1781043349 = ~2:30 PM ET June 9
# 8 PM ET = ~5.5 hrs later = +19800s
BASE = 1781063000000  # ~8:00 PM ET June 9, 2026

new_bets = []

# ── PRIZEPICKS 5-PICK POWER PLAY WIN ($5 → $28.75) ──────────────
# WNBA: ATL 82 vs CHI 75 (Angel Reese, Kamilla Cardoso, Skylar Diggins)
#       DAL 76 vs MIN 100 (Olivia Miles, Paige Bueckers)
# All 5 picks hit — logged as individual WNBA props + 1 parlay entry

new_bets.append({
    "id": "wnba_prop_pp5_angelreese_reb",
    "date": "2026-06-09",
    "sport": "WNBA",
    "betType": "PROP",
    "betOn": "Angel Reese REB O 11.5",
    "propPlayer": "Angel Reese",
    "propStat": "Rebounds",
    "propDir": "OVER",
    "line": "O 11.5",
    "result": 17,
    "hA": "ATL",
    "awA": "CHI",
    "winProb": 0.68,
    "ml": -200,
    "decOdds": 1.5,
    "wager": 0,
    "outcome": "win",
    "lockedAt": BASE + 100,
    "src": "PrizePicks 5-Pick PP",
    "notes": "Hit 17 vs 11.5 line. ATL 82 CHI 75 Final."
})

new_bets.append({
    "id": "wnba_prop_pp5_kamillacardoso_pts",
    "date": "2026-06-09",
    "sport": "WNBA",
    "betType": "PROP",
    "betOn": "Kamilla Cardoso PTS O 9.5",
    "propPlayer": "Kamilla Cardoso",
    "propStat": "Points",
    "propDir": "OVER",
    "line": "O 9.5",
    "result": 13,
    "hA": "CHI",
    "awA": "ATL",
    "winProb": 0.62,
    "ml": -162,
    "decOdds": 1.617,
    "wager": 0,
    "outcome": "win",
    "lockedAt": BASE + 200,
    "src": "PrizePicks 5-Pick PP",
    "notes": "Hit 13 vs 9.5 line. ATL 82 CHI 75 Final."
})

new_bets.append({
    "id": "wnba_prop_pp5_skylardiggins_pra",
    "date": "2026-06-09",
    "sport": "WNBA",
    "betType": "PROP",
    "betOn": "Skylar Diggins PRA O 14.5",
    "propPlayer": "Skylar Diggins",
    "propStat": "Pts+Rebs+Ast",
    "propDir": "OVER",
    "line": "O 14.5",
    "result": 20,
    "hA": "CHI",
    "awA": "ATL",
    "winProb": 0.65,
    "ml": -186,
    "decOdds": 1.538,
    "wager": 0,
    "outcome": "win",
    "lockedAt": BASE + 300,
    "src": "PrizePicks 5-Pick PP",
    "notes": "Hit 20 vs 14.5 line. ATL 82 CHI 75 Final."
})

new_bets.append({
    "id": "wnba_prop_pp5_oliviamiles_pts",
    "date": "2026-06-09",
    "sport": "WNBA",
    "betType": "PROP",
    "betOn": "Olivia Miles PTS O 11.5",
    "propPlayer": "Olivia Miles",
    "propStat": "Points",
    "propDir": "OVER",
    "line": "O 11.5",
    "result": 24,
    "hA": "MIN",
    "awA": "DAL",
    "winProb": 0.70,
    "ml": -233,
    "decOdds": 1.429,
    "wager": 0,
    "outcome": "win",
    "lockedAt": BASE + 400,
    "src": "PrizePicks 5-Pick PP",
    "notes": "Hit 24 vs 11.5 line. MIN 100 DAL 76 Final."
})

new_bets.append({
    "id": "wnba_prop_pp5_paigebueckers_3pt",
    "date": "2026-06-09",
    "sport": "WNBA",
    "betType": "PROP",
    "betOn": "Paige Bueckers 3PTM O 0.5",
    "propPlayer": "Paige Bueckers",
    "propStat": "3PT Made",
    "propDir": "OVER",
    "line": "O 0.5",
    "result": 3,
    "hA": "DAL",
    "awA": "MIN",
    "winProb": 0.75,
    "ml": -300,
    "decOdds": 1.333,
    "wager": 0,
    "outcome": "win",
    "lockedAt": BASE + 500,
    "src": "PrizePicks 5-Pick PP",
    "notes": "Hit 3 vs 0.5 line. MIN 100 DAL 76 Final."
})

# PrizePicks 5-pick PP overall entry
new_bets.append({
    "id": "wnba_parlay_pp5_win_0609",
    "date": "2026-06-09",
    "sport": "WNBA",
    "betType": "PARLAY",
    "betOn": "PP 5-Pick: A.Reese REB|K.Cardoso PTS|S.Diggins PRA|O.Miles PTS|P.Bueckers 3PM",
    "hA": "WNBA",
    "awA": "",
    "winProb": 0.25,
    "ml": "+475",
    "decOdds": 5.75,
    "wager": 5,
    "payout": 28.75,
    "outcome": "win",
    "lockedAt": BASE + 600,
    "src": "PrizePicks",
    "notes": "5-Pick Power Play WIN. All 5 WNBA props hit. $5 → $28.75."
})

# ── HARD ROCK BET 3-TEAM WNBA PARLAY WIN ($5 → $12.20) ──────────
# ATL Dream -400 + MIN Lynx -185 + GSV Valkyries -375

new_bets.append({
    "id": "wnba_ml_atl_0609",
    "date": "2026-06-09",
    "sport": "WNBA",
    "betType": "ML",
    "betOn": "ATL Dream ML",
    "hA": "ATL",
    "awA": "CHI",
    "winProb": 0.80,
    "ml": -400,
    "decOdds": 1.25,
    "wager": 0,
    "outcome": "win",
    "lockedAt": BASE + 700,
    "src": "Hard Rock Bet",
    "notes": "ATL 82 def CHI 75 Final."
})

new_bets.append({
    "id": "wnba_ml_min_0609",
    "date": "2026-06-09",
    "sport": "WNBA",
    "betType": "ML",
    "betOn": "MIN Lynx ML",
    "hA": "MIN",
    "awA": "DAL",
    "winProb": 0.65,
    "ml": -185,
    "decOdds": 1.541,
    "wager": 0,
    "outcome": "win",
    "lockedAt": BASE + 800,
    "src": "Hard Rock Bet",
    "notes": "MIN 100 def DAL 76 Final."
})

new_bets.append({
    "id": "wnba_ml_gsv_0609",
    "date": "2026-06-09",
    "sport": "WNBA",
    "betType": "ML",
    "betOn": "GSV Valkyries ML",
    "hA": "GSV",
    "awA": "PHX",
    "winProb": 0.79,
    "ml": -375,
    "decOdds": 1.267,
    "wager": 0,
    "outcome": "win",
    "lockedAt": BASE + 900,
    "src": "Hard Rock Bet",
    "notes": "GSV 87 def PHX 81 Final."
})

# Hard Rock 3-team parlay overall entry
new_bets.append({
    "id": "wnba_parlay_hrb3_win_0609",
    "date": "2026-06-09",
    "sport": "WNBA",
    "betType": "PARLAY",
    "betOn": "ATL ML -400|MIN ML -185|GSV ML -375",
    "hA": "WNBA",
    "awA": "",
    "winProb": 0.42,
    "ml": "+144",
    "decOdds": 2.44,
    "wager": 5,
    "payout": 12.20,
    "outcome": "win",
    "lockedAt": BASE + 1000,
    "src": "Hard Rock Bet",
    "notes": "3-team WNBA parlay WIN. ATL/MIN/GSV all cover. $5 → $12.20."
})

# ── HARD ROCK BET SGP WIN ($1 → $6.83) ──────────────────────────
# MIN ML + Olivia Miles PTS O 16.5 + Paige Bueckers PTS O 18.5 + Angel Reese REB O 12.5

new_bets.append({
    "id": "wnba_prop_sgp_oliviamiles_pts165",
    "date": "2026-06-09",
    "sport": "WNBA",
    "betType": "PROP",
    "betOn": "Olivia Miles PTS O 16.5",
    "propPlayer": "Olivia Miles",
    "propStat": "Points",
    "propDir": "OVER",
    "line": "O 16.5",
    "result": 24,
    "hA": "MIN",
    "awA": "DAL",
    "winProb": 0.67,
    "ml": -203,
    "decOdds": 1.493,
    "wager": 0,
    "outcome": "win",
    "lockedAt": BASE + 1100,
    "src": "Hard Rock SGP",
    "notes": "Hit 24 vs 16.5 line. MIN 100 DAL 76 Final."
})

new_bets.append({
    "id": "wnba_prop_sgp_paigebueckers_pts185",
    "date": "2026-06-09",
    "sport": "WNBA",
    "betType": "PROP",
    "betOn": "Paige Bueckers PTS O 18.5",
    "propPlayer": "Paige Bueckers",
    "propStat": "Points",
    "propDir": "OVER",
    "line": "O 18.5",
    "result": 24,
    "hA": "DAL",
    "awA": "MIN",
    "winProb": 0.65,
    "ml": -186,
    "decOdds": 1.538,
    "wager": 0,
    "outcome": "win",
    "lockedAt": BASE + 1200,
    "src": "Hard Rock SGP",
    "notes": "Hit 24+ vs 18.5 line. MIN 100 DAL 76 Final."
})

new_bets.append({
    "id": "wnba_prop_sgp_angelreese_reb125",
    "date": "2026-06-09",
    "sport": "WNBA",
    "betType": "PROP",
    "betOn": "Angel Reese REB O 12.5",
    "propPlayer": "Angel Reese",
    "propStat": "Rebounds",
    "propDir": "OVER",
    "line": "O 12.5",
    "result": 17,
    "hA": "ATL",
    "awA": "CHI",
    "winProb": 0.64,
    "ml": -110,
    "decOdds": 1.909,
    "wager": 0,
    "outcome": "win",
    "lockedAt": BASE + 1300,
    "src": "Hard Rock SGP",
    "notes": "Hit 17 vs 12.5 line (-110). ATL 82 CHI 75 Final."
})

new_bets.append({
    "id": "wnba_ml_min_sgp_0609",
    "date": "2026-06-09",
    "sport": "WNBA",
    "betType": "ML",
    "betOn": "MIN Lynx ML (SGP)",
    "hA": "MIN",
    "awA": "DAL",
    "winProb": 0.65,
    "ml": -185,
    "decOdds": 1.541,
    "wager": 0,
    "outcome": "win",
    "lockedAt": BASE + 1350,
    "src": "Hard Rock SGP",
    "notes": "MIN 100 def DAL 76 Final. SGP leg."
})

# Hard Rock SGP overall entry
new_bets.append({
    "id": "wnba_parlay_sgp_win_0609",
    "date": "2026-06-09",
    "sport": "WNBA",
    "betType": "PARLAY",
    "betOn": "SGP: MIN ML|O.Miles PTS O16.5|P.Bueckers PTS O18.5|A.Reese REB O12.5",
    "hA": "WNBA",
    "awA": "",
    "winProb": 0.28,
    "ml": "+583",
    "decOdds": 6.83,
    "wager": 1,
    "payout": 6.83,
    "outcome": "win",
    "lockedAt": BASE + 1400,
    "src": "Hard Rock Bet SGP",
    "notes": "4-leg SGP WIN. MIN ML + 3 player props. $1 → $6.83."
})

# ── PRIZEPICKS 6-PICK PP LOSS — Mixed NHL/WNBA ($5 wager) ───────
# Mitch Marner SOG O 1.5 → 0 (MISS) killed the slip
# Brett Howden SOG O 0.5 → 1 HIT / Jordan Staal SOG O 0.5 → 4 HIT
# Sean Walker Hits O 3.5 → 5 HIT / Taylor Hall SOG O 1.5 → 3 HIT
# Olivia Miles PTS O 11.5 → 24 HIT / Marner SOG O 1.5 → 0 MISS
new_bets.append({
    "id": "nhl_parlay_pp6_loss_0609",
    "date": "2026-06-09",
    "sport": "NHL",
    "betType": "PARLAY",
    "betOn": "PP 6-Pick: O.Miles PTS|B.Howden SOG|J.Staal SOG|M.Marner SOG|S.Walker Hits|T.Hall SOG",
    "hA": "VGK/CAR",
    "awA": "",
    "winProb": 0.20,
    "ml": "+625",
    "decOdds": 7.25,
    "wager": 5,
    "payout": 0,
    "outcome": "loss",
    "lockedAt": BASE + 1500,
    "src": "PrizePicks",
    "notes": "6-Pick PP LOSS. Marner 0 SOG vs 1.5 line killed slip. CAR 2 VGK 0 Final."
})

# ── PRIZEPICKS 5-PICK NHL PP LOSS ($5 wager) ─────────────────────
# Brett Howden SOG O 1.5 → 1 MISS
# Jack Eichel PTS O 0.5 → 0 MISS
# Jordan Staal Faceoffs Won O 11.5 → 12 HIT
# Logan Stankoven PTS O 0.5 → 1 HIT
# Mitch Marner PTS O 1.5 → 1 MISS (exactly at line = miss for over)
new_bets.append({
    "id": "nhl_parlay_pp5_loss_0609",
    "date": "2026-06-09",
    "sport": "NHL",
    "betType": "PARLAY",
    "betOn": "PP 5-Pick: B.Howden SOG O1.5|J.Eichel PTS O0.5|J.Staal FOW O11.5|L.Stankoven PTS O0.5|M.Marner PTS O1.5",
    "hA": "VGK/CAR",
    "awA": "",
    "winProb": 0.25,
    "ml": "+900",
    "decOdds": 10.0,
    "wager": 5,
    "payout": 0,
    "outcome": "loss",
    "lockedAt": BASE + 1600,
    "src": "PrizePicks",
    "notes": "5-Pick PP LOSS. Howden 1 SOG (need 1.5+), Eichel 0 PTS, Marner 1 PTS (need 1.5+). CAR 2 VGK 0 Final."
})

# ── APPEND AND SAVE ───────────────────────────────────────────────
print(f'Adding {len(new_bets)} new bet entries...')
bets.extend(new_bets)

# Count by sport
from collections import defaultdict
rec = defaultdict(lambda: {'w':0,'l':0,'p':0})
for b in bets:
    sp = b.get('sport','UNK')
    o = b.get('outcome','pending')
    if o == 'win': rec[sp]['w'] += 1
    elif o == 'loss': rec[sp]['l'] += 1
    else: rec[sp]['p'] += 1

print('\nPROJECTED RECORDS AFTER:')
for sp, r in sorted(rec.items()):
    total = r['w']+r['l']
    pct = r['w']/total*100 if total else 0
    print(f'  {sp}: {r["w"]}W-{r["l"]}L-{r["p"]}P ({pct:.1f}%)')
print(f'TOTAL: {len(bets)} bets')

json.dump(bets, open('docs/picks.json','w'), indent=2)
print('\npicks.json saved OK')
