#!/usr/bin/env python3
"""
WNBA performance fixes:
1. Replace 5000-iter synchronous MC with direct analytical calculation
2. Add 5-min result cache — skip ESPN re-fetch on every tab switch
3. Fix parlay tab — don't double-render
4. Fix renderWNBAProps — don't cascade into renderWNBAGames
5. Add render guard to prevent concurrent stacked renders
6. Memoize _pGe with a small cache
"""
import re

html = open('docs/app.html').read()

# ═══════════════════════════════════════════════════════════════════
# FIX 1: Replace slow 5000-iter wnbaMC with direct calculation.
# Box-Muller + 5000 reps of Math.random() blocks the main thread for
# ~80-120ms per game. Replace with instant analytical result.
# hP = hBase (the directly computed win probability) — no precision loss.
# ═══════════════════════════════════════════════════════════════════

OLD_MC = r"""function wnbaMC(hA,awA){
  var hk=_wnbaKey(hA),ak=_wnbaKey(awA);
  var D=window.__CV_DATA||{};
  var ts=D.wnba&&D.wnba.teamStats||{};
  var ht=ts[hk]||ts[hA]||{};var at=ts[ak]||ts[awA]||{};
  var hNet=(ht.net!==undefined?ht.net:(ht.ortg||100)-(ht.drtg||100))||0;
  var aNet=(at.net!==undefined?at.net:(at.ortg||100)-(at.drtg||100))||0;
  var hfa=0.028;
  var hBase=Math.min(.88,Math.max(.12,0.5+(hNet-aNet)*0.012+hfa));
  var wins=0,N=5000;
  for(var i=0;i<N;i++){
    var u1=Math.random(),u2=Math.random();
    var z=Math.sqrt(-2*Math.log(u1+1e-12))*Math.cos(2*Math.PI*u2);
    if(Math.random()<Math.min(.97,Math.max(.03,hBase+z*0.09)))wins++;
  }
  return{hP:wins/N,aP:1-wins/N,hNet:hNet,aNet:aNet};
}"""

NEW_MC = r"""function wnbaMC(hA,awA){
  var hk=_wnbaKey(hA),ak=_wnbaKey(awA);
  var D=window.__CV_DATA||{};
  var ts=D.wnba&&D.wnba.teamStats||{};
  var ht=ts[hk]||ts[hA]||{};var at=ts[ak]||ts[awA]||{};
  var hNet=(ht.net!==undefined?ht.net:(ht.ortg||100)-(ht.drtg||100))||0;
  var aNet=(at.net!==undefined?at.net:(at.ortg||100)-(at.drtg||100))||0;
  var hfa=0.028;
  // Direct analytical result — same math, instant (was 5000-iter sync loop)
  var hP=Math.min(.88,Math.max(.12,0.5+(hNet-aNet)*0.012+hfa));
  return{hP:hP,aP:1-hP,hNet:hNet,aNet:aNet};
}"""

assert html.count(OLD_MC) == 1, f"wnbaMC not unique: {html.count(OLD_MC)}"
html = html.replace(OLD_MC, NEW_MC, 1)
print("FIX 1: wnbaMC loop replaced with direct calculation OK")

# ═══════════════════════════════════════════════════════════════════
# FIX 2: Add cache variables + memoized _pGe before renderWNBAGames
# ═══════════════════════════════════════════════════════════════════

OLD_PGE = r"""function _pGe(lam,n){
  var e=Math.exp(-lam),cum=0,cur=e;
  for(var i=0;i<=n;i++){cum+=cur;if(i<n)cur*=lam/(i+1);}
  return Math.max(.01,Math.min(.99,1-cum));
}"""

NEW_PGE = r"""// cache keyed by "lam_n" — avoids recomputing same prop line twice
var _pGeCache={};
function _pGe(lam,n){
  var k=lam.toFixed(2)+'_'+n;
  if(_pGeCache[k]!==undefined)return _pGeCache[k];
  var e=Math.exp(-lam),cum=0,cur=e;
  for(var i=0;i<=n;i++){cum+=cur;if(i<n)cur*=lam/(i+1);}
  var r=Math.max(.01,Math.min(.99,1-cum));
  _pGeCache[k]=r;return r;
}
// Game data result cache — 5-min TTL avoids re-fetching ESPN every tab switch
var _wnbaGamesCache=null,_wnbaCacheTs=0,_WNBA_TTL=300000;
var _wnbaRendering=false;"""

assert html.count(OLD_PGE) == 1, f"_pGe not unique: {html.count(OLD_PGE)}"
html = html.replace(OLD_PGE, NEW_PGE, 1)
print("FIX 2: _pGe memoized + cache vars added OK")

# ═══════════════════════════════════════════════════════════════════
# FIX 3: Add cache check + render guard at start of renderWNBAGames
# ═══════════════════════════════════════════════════════════════════

OLD_GAMES_START = r"""async function renderWNBAGames(){
  var el=document.getElementById('wnba-games-list');
  var dateEl=document.getElementById('wnba-games-date');
  if(!el)return;
  el.innerHTML='<div class="loading"><span class="spi"></span> LOADING...</div>';"""

NEW_GAMES_START = r"""async function renderWNBAGames(force){
  if(_wnbaRendering&&!force)return;
  _wnbaRendering=true;
  var el=document.getElementById('wnba-games-list');
  var dateEl=document.getElementById('wnba-games-date');
  if(!el){_wnbaRendering=false;return;}
  // Serve from cache if fresh (< 5 min) and not force-refresh
  var now=Date.now();
  if(!force&&_wnbaGamesCache&&(now-_wnbaCacheTs)<_WNBA_TTL){
    el.innerHTML=_wnbaGamesCache.html;
    window._wnbaGameData=_wnbaGamesCache.data;
    var pgl=document.getElementById('wnba-parlay-games');
    if(pgl)pgl.innerHTML=_wnbaGamesCache.parlayHtml||'';
    if(dateEl)dateEl.textContent=_wnbaGamesCache.dateStr||'';
    _wnbaRendering=false;return;
  }
  el.innerHTML='<div class="loading"><span class="spi"></span> LOADING...</div>';"""

assert html.count(OLD_GAMES_START) == 1, f"renderWNBAGames start not unique: {html.count(OLD_GAMES_START)}"
html = html.replace(OLD_GAMES_START, NEW_GAMES_START, 1)
print("FIX 3: renderWNBAGames cache check + guard added OK")

# ═══════════════════════════════════════════════════════════════════
# FIX 4: Cache result + clear render guard at end of renderWNBAGames
# Find the end: "window._wnbaGameData=WPAR;" and the parlay section close
# ═══════════════════════════════════════════════════════════════════

OLD_GAMES_END = r"""  window._wnbaGameData=WPAR;
  var pgl=document.getElementById('wnba-parlay-games');
  if(pgl){"""

NEW_GAMES_END = r"""  window._wnbaGameData=WPAR;
  // Store in cache
  _wnbaGamesCache={html:el.innerHTML,data:WPAR,dateStr:dateEl?dateEl.textContent:''};
  _wnbaCacheTs=Date.now();
  var pgl=document.getElementById('wnba-parlay-games');
  if(pgl){"""

assert html.count(OLD_GAMES_END) == 1, f"cache store anchor not unique: {html.count(OLD_GAMES_END)}"
html = html.replace(OLD_GAMES_END, NEW_GAMES_END, 1)
print("FIX 4: renderWNBAGames cache store added OK")

print("FIX 4b: (guard clear moved to FIX 4c) OK")

# Cache parlay HTML + clear render guard at function close
OLD_PGL_END = "    }).join('');\n  }\n}\nwindow.renderWNBAGames=renderWNBAGames;"
NEW_PGL_END = "    }).join('');\n    if(_wnbaGamesCache)_wnbaGamesCache.parlayHtml=pgl.innerHTML;\n  }\n  _wnbaRendering=false;\n}\nwindow.renderWNBAGames=renderWNBAGames;"

assert html.count(OLD_PGL_END) == 1, f"pgl end not unique: {html.count(OLD_PGL_END)}"
html = html.replace(OLD_PGL_END, NEW_PGL_END, 1)
print("FIX 4c: parlay HTML cached + guard cleared OK")

# ═══════════════════════════════════════════════════════════════════
# FIX 5: renderWNBAProps — don't cascade into renderWNBAGames
# If no game data, show a soft empty state instead of re-fetching
# ═══════════════════════════════════════════════════════════════════

OLD_PROPS_CASCADE = r"""  var gameData=window._wnbaGameData||[];
  if(!gameData.length){await renderWNBAGames();gameData=window._wnbaGameData||[];}
  if(!gameData.length){el.innerHTML='<div class="empty">NO WNBA GAMES TODAY &mdash; PROPS UNAVAILABLE</div>';return;}"""

NEW_PROPS_CASCADE = r"""  var gameData=window._wnbaGameData||[];
  if(!gameData.length){
    el.innerHTML='<div class="empty">NO GAME DATA &mdash; VIEW TODAY TAB FIRST</div>';
    return;
  }"""

assert html.count(OLD_PROPS_CASCADE) == 1, f"props cascade not unique: {html.count(OLD_PROPS_CASCADE)}"
html = html.replace(OLD_PROPS_CASCADE, NEW_PROPS_CASCADE, 1)
print("FIX 5: renderWNBAProps cascade removed OK")

# ═══════════════════════════════════════════════════════════════════
# FIX 6: Fix T() parlay routing — don't call both renders
# Only fetch games if cache is cold; never trigger props from parlay
# ═══════════════════════════════════════════════════════════════════

OLD_PARLAY_ROUTE = r"""      else if(tabId==='parlay'){renderWNBAGames();renderWNBAProps();}"""
NEW_PARLAY_ROUTE = r"""      else if(tabId==='parlay'){
        var now2=Date.now();
        if(!_wnbaGamesCache||(now2-_wnbaCacheTs)>=_WNBA_TTL)renderWNBAGames();
      }"""

assert html.count(OLD_PARLAY_ROUTE) == 1, f"parlay route not unique: {html.count(OLD_PARLAY_ROUTE)}"
html = html.replace(OLD_PARLAY_ROUTE, NEW_PARLAY_ROUTE, 1)
print("FIX 6: T() parlay routing fixed — no double render OK")

# ═══════════════════════════════════════════════════════════════════
# FIX 7: Add force-refresh button to bypass cache (↻ button)
# The refresh button should call renderWNBAGames(true) not renderWNBAGames()
# ═══════════════════════════════════════════════════════════════════

OLD_REFRESH_BTN = 'onclick="renderWNBAGames()">&#8635;</button>'
NEW_REFRESH_BTN = 'onclick="renderWNBAGames(true)">&#8635;</button>'

# This appears once in the TODAY tab header
count = html.count(OLD_REFRESH_BTN)
assert count == 1, f"refresh btn not unique: {count}"
html = html.replace(OLD_REFRESH_BTN, NEW_REFRESH_BTN, 1)
print("FIX 7: refresh button uses force=true OK")

# ═══════════════════════════════════════════════════════════════════
# VALIDATE
# ═══════════════════════════════════════════════════════════════════

scripts = list(__import__('re').finditer(r'<script([^>]*)>([\s\S]*?)</script>', html))
js = [s.group(2) for s in scripts if len(s.group(2)) > 10000][0]
bt = js.count('`'); op = js.count('{'); cl = js.count('}')
bad = js.count(chr(39)+chr(10)+chr(39))
print(f'\nVALIDATION: BT:{bt}(ok={bt%2==0}) Braces:{op}/{cl}(ok={op==cl}) LF:{bad}(ok={bad==0})')
assert bt%2==0 and op==cl and bad==0, "Validation failed!"

open('docs/app.html','w').write(html)
open('docs/index.html','w').write(html)
print(f"Written — {html.count(chr(10))+1} lines")
