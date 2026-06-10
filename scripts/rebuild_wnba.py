#!/usr/bin/env python3
"""
WNBA full rebuild — Session 9
Deletes broken nba-wnba subpane + all old WNBA JS, replaces with clean NBA-mirrored implementation.
"""
import re, sys

html = open('docs/app.html').read()

# ══════════════════════════════════════════════════════════════════
# 1. REPLACE WNBA HTML SUBPANE
#    Old: lines 879-968  (  <div id="nba-wnba" class="subp"> ... </div>\n\n  </div> )
# ══════════════════════════════════════════════════════════════════

OLD_HTML = '''  <div id="nba-wnba" class="subp">'''
# We need to find start and end precisely
start_marker = '  <div id="nba-wnba" class="subp">'
# End is the closing </div> of nba-wnba, which is the last </div> before </div> that closes sp-nba
# The sp-nba close is the lone </div> on line 969
# We know the block is:   <div id="nba-wnba" ...>  ... </div>\n\n  </div>
# The \n\n  </div> at end closes nba-wnba and then the outer sp-nba div
# Let's find it precisely
idx_start = html.index(start_marker)
# Find the closing pattern: nba-wnba div ends then sp-nba ends
# After the last </div> of wnba-tab-config there's </div> (closes wnba-sa), </div> (closes nba-wnba), </div> (closes sp-nba)
# Pattern:   </div>\n\n  </div>\n</div>\n
end_pattern = '  </div>\n\n  </div>\n</div>'
idx_end = html.index(end_pattern, idx_start) + len(end_pattern)

old_wnba_html = html[idx_start:idx_end]

NEW_HTML = '''  <div id="nba-wnba" class="subp">
    <nav class="inav" id="wnba-in">
      <button class="nb act" onclick="T('wnba','games')">TODAY</button>
      <button class="nb" onclick="T('wnba','props')">PROPS</button>
      <button class="nb" onclick="T('wnba','parlay')">PARLAY</button>
      <button class="nb" onclick="T('wnba','model')">MODEL</button>
      <button class="nb" onclick="T('wnba','config')">CONFIG</button>
    </nav>
    <div class="sa" id="wnba-sa">

      <div id="wnba-tab-games" class="tab act">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <div class="sh" style="margin:0"><span class="i"></span> TODAY\'S GAMES <span id="wnba-games-date" style="font-family:var(--mono);font-size:11px;color:var(--t3);margin-left:8px"></span></div>
          <button class="btn btn-o btn-sm" onclick="renderWNBAGames()">&#8635;</button>
        </div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;padding:7px 10px;background:rgba(10,0,24,.7);border:1px solid rgba(187,255,0,.15);border-radius:2px;margin-bottom:10px;font-family:var(--mono);font-size:11px;letter-spacing:1px">
          <span style="color:var(--t3);letter-spacing:1px;font-size:10px">KEY:</span>
          <span style="color:var(--gc)">ELITE</span><span style="color:var(--t3)">&ge;67% + EV&gt;5%</span>
          <span style="color:var(--nc)">// LOCK</span><span style="color:var(--t3)">&ge;62% + EV&gt;3%</span>
          <span style="color:var(--ic)">// LEAN</span><span style="color:var(--t3)">55-62%</span>
          <span style="color:var(--hc)">// SKIP</span><span style="color:var(--t3)">&lt;55%</span>
        </div>
        <div id="wnba-games-list"><div class="loading"><span class="spi"></span> LOADING&hellip;</div></div>
      </div>

      <div id="wnba-tab-props" class="tab">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <div class="sh" style="margin:0"><span style="color:var(--gc)"></span> WNBA PLAYER PROPS</div>
          <button class="btn btn-p btn-sm" onclick="renderWNBAProps()">&#8635;</button>
        </div>
        <div style="background:rgba(10,0,24,.8);border:1px solid rgba(187,255,0,.25);border-radius:2px;padding:9px 12px;margin-bottom:12px;font-family:var(--mono);font-size:11px;color:var(--t3)">
          POISSON MODEL &middot; OPPONENT DRtg ADJUSTED &middot; TODAY\'S GAMES ONLY &middot; TOP 10 PER MATCHUP
        </div>
        <div id="wnba-props-list"><div class="loading"><span class="spi"></span> LOADING&hellip;</div></div>
      </div>

      <div id="wnba-tab-parlay" class="tab">
        <div class="sh"><span class="p"></span> WNBA PARLAY BUILDER</div>
        <div style="background:rgba(10,0,24,.8);border:1px solid rgba(240,0,255,.25);border-radius:2px;padding:9px 12px;margin-bottom:12px;font-family:var(--mono);font-size:11px;color:var(--t3)">
          MAX 8 LEGS &middot; GAME LINES + PLAYER PROPS &middot; AUTO-CALC COMBINED ODDS + EV%
        </div>
        <div class="g2">
          <div>
            <div style="display:flex;gap:5px;margin-bottom:8px">
              <button class="btn btn-o btn-sm" style="font-size:11px" id="wnba-par-games-btn" onclick="wnbaParTab('games')">GAME LINES</button>
              <button class="btn btn-p btn-sm" style="font-size:11px" id="wnba-par-props-btn" onclick="wnbaParTab('props')">PLAYER PROPS</button>
            </div>
            <div id="wpar-games">
              <div style="font-family:var(--mono);font-size:12px;color:var(--t3);margin-bottom:5px">// GAME LINES &mdash; TAP +PAR TO ADD</div>
              <div id="wnba-parlay-games"><div class="loading"><span class="spi"></span></div></div>
            </div>
            <div id="wpar-props" style="display:none">
              <div style="font-family:var(--mono);font-size:12px;color:var(--t3);margin-bottom:5px">// PLAYER PROPS &mdash; TAP +PAR TO ADD</div>
              <div id="wnba-parlay-props"><div class="loading"><span class="spi"></span></div></div>
            </div>
          </div>
          <div>
            <div style="font-family:var(--mono);font-size:13px;color:var(--t2);margin-bottom:7px">// WNBA PARLAY <span id="wnba-lc">(0)</span></div>
            <div id="wnba-parlay-legs" style="min-height:46px;background:rgba(6,0,15,.9);border:1px dashed rgba(240,0,255,.3);border-radius:2px;padding:7px;margin-bottom:7px;font-family:var(--mono);font-size:12px;color:var(--t3)">NO LEGS ADDED</div>
            <div id="wnba-parlay-res"></div>
            <input type="number" class="fi" id="wnba-p-w" value="100" placeholder="WAGER $" style="margin-bottom:7px" oninput="calcWNBAP()">
            <button class="btn btn-p btn-fw" onclick="calcWNBAP()">CALCULATE</button>
            <button class="btn btn-o btn-fw" style="margin-top:5px" onclick="window._wnbaParlay=[];document.getElementById('wnba-lc').textContent='(0)';document.getElementById('wnba-parlay-legs').innerHTML='NO LEGS ADDED';document.getElementById('wnba-parlay-res').innerHTML=''">CLEAR</button>
          </div>
        </div>
      </div>

      <div id="wnba-tab-model" class="tab">
        <div class="sh"><span class="i"></span> WNBA MODEL ARCHITECTURE</div>
        <div class="g3" style="margin-bottom:12px">
          <div class="card ci"><div class="ct">MONTE CARLO</div><div style="font-size:15px;color:var(--t2);line-height:1.7;margin-top:3px;font-family:var(--mono)">5K sims. Net Rating + Pace + eFG% + HFA. ESPN odds calibration.</div></div>
          <div class="card cp"><div class="ct">BAYESIAN</div><div style="font-size:15px;color:var(--t2);line-height:1.7;margin-top:3px;font-family:var(--mono)">Beta-binomial posterior. Home court + rest day adjustments.</div></div>
          <div class="card cn"><div class="ct">ELO + MOV</div><div style="font-size:15px;color:var(--t2);line-height:1.7;margin-top:3px;font-family:var(--mono)">K=20. Margin-of-victory multiplier. BBRef advanced stats.</div></div>
        </div>
        <div class="sh"><span class="i"></span> MODEL FACTORS</div>
        <div class="g3" style="margin-bottom:12px;gap:8px">
          <div class="card ci" style="padding:10px"><div style="font-family:var(--mono);font-size:13px;letter-spacing:1px;color:var(--ic);margin-bottom:4px">NET RATING</div><div style="font-family:var(--mono);font-size:12px;color:var(--t2)">Points per 100 possessions differential. Weight: HIGH</div><div style="height:3px;background:rgba(0,200,255,.15);border-radius:1px;margin-top:6px"><div style="height:100%;width:85%;background:var(--ic);border-radius:1px"></div></div></div>
          <div class="card cp" style="padding:10px"><div style="font-family:var(--mono);font-size:13px;letter-spacing:1px;color:var(--pc);margin-bottom:4px">PACE-ADJ eFG%</div><div style="font-family:var(--mono);font-size:12px;color:var(--t2)">Effective FG% adjusted for pace. Weight: HIGH</div><div style="height:3px;background:rgba(240,0,255,.15);border-radius:1px;margin-top:6px"><div style="height:100%;width:80%;background:var(--pc);border-radius:1px"></div></div></div>
          <div class="card cn" style="padding:10px"><div style="font-family:var(--mono);font-size:13px;letter-spacing:1px;color:var(--nc);margin-bottom:4px">DEFENSIVE RTG</div><div style="font-family:var(--mono);font-size:12px;color:var(--t2)">Points allowed per 100 possessions. Weight: HIGH</div><div style="height:3px;background:rgba(0,255,136,.15);border-radius:1px;margin-top:6px"><div style="height:100%;width:75%;background:var(--nc);border-radius:1px"></div></div></div>
          <div class="card cm" style="padding:10px"><div style="font-family:var(--mono);font-size:13px;letter-spacing:1px;color:var(--mc);margin-bottom:4px">ESPN ODDS</div><div style="font-family:var(--mono);font-size:12px;color:var(--t2)">Market implied probability blend 30%. Weight: MED</div><div style="height:3px;background:rgba(255,170,0,.15);border-radius:1px;margin-top:6px"><div style="height:100%;width:55%;background:var(--mc);border-radius:1px"></div></div></div>
          <div class="card cp" style="padding:10px"><div style="font-family:var(--mono);font-size:13px;letter-spacing:1px;color:var(--pc);margin-bottom:4px">HFA</div><div style="font-family:var(--mono);font-size:12px;color:var(--t2)">Home court advantage factor. Weight: MED</div><div style="height:3px;background:rgba(240,0,255,.15);border-radius:1px;margin-top:6px"><div style="height:100%;width:50%;background:var(--pc);border-radius:1px"></div></div></div>
          <div class="card ci" style="padding:10px"><div style="font-family:var(--mono);font-size:13px;letter-spacing:1px;color:var(--ic);margin-bottom:4px">REST ADVANTAGE</div><div style="font-family:var(--mono);font-size:12px;color:var(--t2)">Days rest differential between teams. Weight: LOW</div><div style="height:3px;background:rgba(0,200,255,.15);border-radius:1px;margin-top:6px"><div style="height:100%;width:35%;background:var(--ic);border-radius:1px"></div></div></div>
        </div>
        <div id="wnba-model-weights"></div>
      </div>

      <div id="wnba-tab-config" class="tab">
        <div class="sh"><span class="i"></span> WNBA ENGINE CONFIG</div>
        <div class="sg">
          <div class="sgt">// MODEL WEIGHTS</div>
          <div class="rr"><span class="rrl">MONTE CARLO</span><span class="rrv" id="wnba-mc-v">45%</span></div><input type="range" id="wnba-w-mc" min="10" max="70" value="45" oninput="document.getElementById('wnba-mc-v').textContent=this.value+'%';applyWNBAWeights()">
          <div class="dv"></div>
          <div class="rr"><span class="rrl">BAYESIAN</span><span class="rrv" id="wnba-bay-v">25%</span></div><input type="range" id="wnba-w-bay" min="5" max="50" value="25" oninput="document.getElementById('wnba-bay-v').textContent=this.value+'%';applyWNBAWeights()">
          <div class="dv"></div>
          <div class="rr"><span class="rrl">ELO</span><span class="rrv" id="wnba-elo-v">30%</span></div><input type="range" id="wnba-w-elo" min="5" max="50" value="30" oninput="document.getElementById('wnba-elo-v').textContent=this.value+'%';applyWNBAWeights()">
          <button class="btn btn-p btn-sm" style="margin-top:10px" onclick="applyWNBAWeights()">APPLY</button>
        </div>
        <div class="sg">
          <div class="sgt">// PICK THRESHOLDS</div>
          <div class="rr"><span class="rrl">MIN EV %</span><span class="rrv" id="wnba-ev-v">2%</span></div><input type="range" id="wnba-ev-thresh" min="0" max="10" value="2" step="0.5" oninput="document.getElementById('wnba-ev-v').textContent=this.value+'%'">
          <div class="dv"></div>
          <div class="rr"><span class="rrl">MIN WIN PROB</span><span class="rrv" id="wnba-minp-v">54%</span></div><input type="range" id="wnba-min-p" min="50" max="75" value="54" oninput="document.getElementById('wnba-minp-v').textContent=this.value+'%'">
          <button class="btn btn-p btn-sm" style="margin-top:10px" onclick="applyWNBAWeights()">SAVE</button>
        </div>
        <div id="wnba-model-weights-b"></div>
      </div>
    </div>
    <nav id="mn8" style="display:none">
      <button class="mb" onclick="T('wnba','games')"><span class="mbi"></span>TODAY</button>
      <button class="mb" onclick="T('wnba','props')"><span class="mbi"></span>PROPS</button>
      <button class="mb" onclick="T('wnba','parlay')"><span class="mbi"></span>PARLAY</button>
      <button class="mb" onclick="T('wnba','model')"><span class="mbi"></span>MODEL</button>
      <button class="mb" onclick="T('wnba','config')"><span class="mbi"></span>CONFIG</button>
    </nav>
  </div>

  </div>
</div>'''

assert html.count(old_wnba_html) == 1, f"HTML block not unique: found {html.count(old_wnba_html)}"
html = html.replace(old_wnba_html, NEW_HTML, 1)
print("HTML subpane replaced OK")

# ══════════════════════════════════════════════════════════════════
# 2. REPLACE OLD WNBA JS SECTION (lines 13370-14072)
#    From  // ── WNBA ELO ratings  →  window._wnbaRenderLegs=_wnbaRenderLegs;\n\n
# ══════════════════════════════════════════════════════════════════

OLD_JS_START = '// ── WNBA ELO ratings (2026 season baseline) ──────────────────────────────'
OLD_JS_END   = 'window._wnbaRenderLegs=_wnbaRenderLegs;\n\nfunction renderWNBAContent(){'

idx_js_start = html.index(OLD_JS_START)
idx_js_end   = html.index(OLD_JS_END) + len(OLD_JS_END)

old_js = html[idx_js_start:idx_js_end]

NEW_JS = '''// ── WNBA ENGINE (Session 9 rebuild — NBA-mirrored) ───────────────────────────

window.WNBA_ELO={
  NY:1640,MIN:1590,LV:1560,CON:1535,IND:1525,SEA:1495,
  CHI:1485,PHX:1455,ATL:1445,LA:1430,DAL:1415,GS:1410,WSH:1390,TOR:1355
};
// ESPN/BBRef abbr → WNBA_ELO key
var WNBA_ABBR_MAP={
  LVA:'LV',NYL:'NY',GSV:'GS',PHO:'PHX',WAS:'WSH',LAE:'LA',
  LAS:'LV','New York':'NY','Minnesota':'MIN','Las Vegas':'LV',
  'Connecticut':'CON','Indiana':'IND','Seattle':'SEA','Chicago':'CHI',
  'Phoenix':'PHX','Atlanta':'ATL','Los Angeles':'LA','Dallas':'DAL',
  'Golden State':'GS','Washington':'WSH','Toronto':'TOR'
};
var WNBA_WIN_PCT={
  NY:.72,MIN:.65,LV:.60,CON:.58,IND:.58,SEA:.52,
  CHI:.48,PHX:.46,ATL:.45,GS:.44,LA:.40,DAL:.40,WSH:.38,TOR:.30
};
// Config weights (mirroring NBA_ENS)
var WNBA_ENS={mc:.45,bay:.25,elo:.30};
function _wnbaKey(abbr){
  if(!abbr)return abbr;
  var a=abbr.trim();
  return WNBA_ABBR_MAP[a]||a;
}
function wnbaEloWP(r1,r2){return 1/(1+Math.pow(10,(r2-r1)/400));}
function wnbaMC(hA,awA){
  var hk=_wnbaKey(hA),ak=_wnbaKey(awA);
  var D=window.__CV_DATA||{};
  var ts=D.wnba&&D.wnba.teamStats||{};
  var ht=ts[hk]||ts[hA]||{};var at=ts[ak]||ts[awA]||{};
  var hNet=(ht.net!==undefined?ht.net:(ht.ortg||100)-(ht.drtg||100))||0;
  var aNet=(at.net!==undefined?at.net:(at.ortg||100)-(at.drtg||100))||0;
  var hfa=0.028;
  var hBase=0.5+(hNet-aNet)*0.012+hfa;
  hBase=Math.min(.88,Math.max(.12,hBase));
  var wins=0,N=5000;
  for(var i=0;i<N;i++){
    var u1=Math.random(),u2=Math.random();
    var z=Math.sqrt(-2*Math.log(u1+1e-12))*Math.cos(2*Math.PI*u2);
    var p=hBase+z*0.09;
    if(Math.random()<Math.min(.97,Math.max(.03,p)))wins++;
  }
  return{hP:wins/N,aP:1-wins/N,hNet:hNet,aNet:aNet};
}
function wnbaEns(hA,awA,espnOdds){
  var hk=_wnbaKey(hA),ak=_wnbaKey(awA);
  var mc=wnbaMC(hA,awA);
  var hMC=mc.hP;
  var hfa=0.028;
  var eloP=Math.min(.86,Math.max(.14,wnbaEloWP(window.WNBA_ELO[hk]||1490,window.WNBA_ELO[ak]||1490)+hfa));
  var D=window.__CV_DATA||{};
  var ts=D.wnba&&D.wnba.teamStats||{};
  var ht=ts[hk]||ts[hA]||{};var at=ts[ak]||ts[awA]||{};
  var hWp=ht.wpct!==undefined?ht.wpct:(WNBA_WIN_PCT[hk]||0.5);
  var aWp=at.wpct!==undefined?at.wpct:(WNBA_WIN_PCT[ak]||0.5);
  var hBay=Math.min(.86,Math.max(.14,(hWp+hfa)/(hWp+aWp+1e-9)));
  var wmc=parseFloat(document.getElementById('wnba-w-mc')?.value||45)/100;
  var wbay=parseFloat(document.getElementById('wnba-w-bay')?.value||25)/100;
  var welo=parseFloat(document.getElementById('wnba-w-elo')?.value||30)/100;
  var tot=wmc+wbay+welo||1;wmc/=tot;wbay/=tot;welo/=tot;
  var ens=hMC*wmc+hBay*wbay+eloP*welo;
  if(espnOdds&&espnOdds.homeML){
    var hml=espnOdds.homeML;
    var hImp=hml<0?Math.abs(hml)/(Math.abs(hml)+100):100/(hml+100);
    ens=ens*0.70+hImp*0.30;
  }
  ens=Math.min(.88,Math.max(.12,ens));
  return{hP:ens,aP:1-ens,mcP:hMC,bayP:hBay,eloP:eloP,hNet:mc.hNet,aNet:mc.aNet};
}
function applyWNBAWeights(){
  var mc=parseInt(document.getElementById('wnba-w-mc')?.value||45);
  var bay=parseInt(document.getElementById('wnba-w-bay')?.value||25);
  var elo=parseInt(document.getElementById('wnba-w-elo')?.value||30);
  WNBA_ENS={mc:mc/100,bay:bay/100,elo:elo/100};
}
window.applyWNBAWeights=applyWNBAWeights;

// ── Helpers ──────────────────────────────────────────────────────────────────
function _wnbaGrade(p){
  if(p>=.68)return{g:'ELITE',c:'var(--gc)'};
  if(p>=.61)return{g:'LOCK',c:'var(--nc)'};
  if(p>=.54)return{g:'LEAN',c:'var(--ic)'};
  return{g:'SKIP',c:'var(--hc)'};
}
function _wnbaReason(p,hk,ak,nets){
  var gr=_wnbaGrade(p);var netDiff=(nets.hNet-nets.aNet).toFixed(1);
  var sz=p>=.68?'FULL UNIT':p>=.61?'FULL UNIT':p>=.54?'HALF UNIT':'FADE';
  var note=p>=.68?hk+' dominant net rating advantage (+'+netDiff+' pts/100 poss). High-confidence play.':
           p>=.61?hk+' edges '+ak+' on net rating (+'+netDiff+'). Solid play at this number.':
           p>=.54?'Slight edge for '+hk+' (+'+netDiff+' net). Proceed with caution.':
                  'Marginal edge or no edge. Model suggests fading.';
  return'<div style="margin-top:10px;padding:8px 10px;background:rgba(6,0,15,.8);border-left:3px solid '+gr.c+';border-radius:0 2px 2px 0">'
    +'<div style="font-family:var(--mono);font-size:10px;letter-spacing:2px;color:var(--t3);margin-bottom:4px">ENGINE REASONING</div>'
    +'<span style="font-family:var(--mono);font-size:12px;font-weight:700;color:'+gr.c+';letter-spacing:1px">'+gr.g+'</span>'
    +'<span style="font-family:var(--mono);font-size:11px;color:var(--t3);margin-left:8px">SIZE: '+sz+'</span>'
    +'<div style="font-family:var(--mono);font-size:12px;color:var(--t2);margin-top:4px;line-height:1.5">'+note+'</div>'
    +'</div>';
}
function _wnbaML(p){var ml=p>=.5?-Math.round(p/(1-p)*100):Math.round((1-p)/p*100);return ml>0?'+'+ml:ml;}

// ── TODAY tab ────────────────────────────────────────────────────────────────
async function renderWNBAGames(){
  var el=document.getElementById('wnba-games-list');
  var dateEl=document.getElementById('wnba-games-date');
  if(!el)return;
  el.innerHTML='<div class="loading"><span class="spi"></span> LOADING&hellip;</div>';
  var D=window.__CV_DATA||{};
  var today_str=typeof today==='function'?today():new Date().toISOString().slice(0,10);
  if(dateEl){var dt=new Date(today_str+'T12:00:00');dateEl.textContent=dt.toLocaleDateString('en-US',{weekday:'short',month:'short',day:'numeric'});}
  var games=[];
  try{
    var r=await fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard');
    if(r.ok){var jd=await r.json();games=(jd.events||[]);}
  }catch(ex){console.warn('WNBA ESPN scoreboard',ex);}
  if(!games.length){
    var fallback=(D.wnba&&D.wnba.today)||[];
    games=fallback.map(function(g){return{_fallback:true,home:g.home||g.homeName,away:g.away||g.awayName,homeML:g.homeML,awayML:g.awayML,overUnder:g.ou};});
  }
  if(!games.length){el.innerHTML='<div class="empty">NO WNBA GAMES TODAY</div>';return;}
  var WPAR=[];
  var html_parts=[];
  for(var gi=0;gi<games.length;gi++){
    var ev=games[gi];
    var hab,aab,homeML,awayML,spread,ou,homeName,awayName,homeRec,awayRec;
    if(ev._fallback){
      hab=_wnbaKey(ev.home);aab=_wnbaKey(ev.away);homeML=ev.homeML;awayML=ev.awayML;ou=ev.overUnder;
      homeName=ev.home;awayName=ev.away;homeRec='';awayRec='';spread=null;
    }else{
      var comps=ev.competitions&&ev.competitions[0]||{};
      var teams=comps.competitors||[];
      var hTeam=teams.find(function(t){return t.homeAway==='home';})||teams[0]||{};
      var aTeam=teams.find(function(t){return t.homeAway==='away';})||teams[1]||{};
      homeName=(hTeam.team&&(hTeam.team.shortDisplayName||hTeam.team.abbreviation))||'HOME';
      awayName=(aTeam.team&&(aTeam.team.shortDisplayName||aTeam.team.abbreviation))||'AWAY';
      hab=_wnbaKey(hTeam.team&&hTeam.team.abbreviation||homeName);
      aab=_wnbaKey(aTeam.team&&aTeam.team.abbreviation||awayName);
      homeRec=hTeam.records&&hTeam.records[0]&&hTeam.records[0].summary||'';
      awayRec=aTeam.records&&aTeam.records[0]&&aTeam.records[0].summary||'';
      var odds=comps.odds&&comps.odds[0]||{};
      homeML=odds.homeTeamOdds&&odds.homeTeamOdds.moneyLine;
      awayML=odds.awayTeamOdds&&odds.awayTeamOdds.moneyLine;
      spread=odds.spread;ou=odds.overUnder;
    }
    var espnHL=homeML?{homeML:homeML,awayML:awayML}:null;
    var ens=wnbaEns(hab,aab,espnHL);
    var hP=ens.hP,aP=ens.aP;
    var hGr=_wnbaGrade(hP),aGr=_wnbaGrade(aP);
    var topGr=hP>=aP?hGr:aGr;var topPick=hP>=aP?hab:aab;var topP=Math.max(hP,aP);
    var hMLd=homeML||_wnbaML(hP),aMLd=awayML||_wnbaML(aP);
    var hMLn=typeof hMLd==='number'?hMLd:parseInt(hMLd)||0;
    var aMLn=typeof aMLd==='number'?aMLd:parseInt(aMLd)||0;
    var spreadStr=spread!=null?spread:(((0.5-hP)*25).toFixed(1));
    var ouStr=ou||((ens.hNet+ens.aNet)*0.5+170).toFixed(1);
    var gameKey=hab+'_'+aab;
    // Net ratings
    var ts=(D.wnba&&D.wnba.teamStats)||{};
    var ht2=ts[hab]||{};var at2=ts[aab]||{};
    var hNetStr=ht2.net!==undefined?(ht2.net>=0?'+':'')+parseFloat(ht2.net).toFixed(1):'N/A';
    var aNetStr=at2.net!==undefined?(at2.net>=0?'+':'')+parseFloat(at2.net).toFixed(1):'N/A';
    var hDecOdds=(hMLn<0?1+100/Math.abs(hMLn):1+hMLn/100).toFixed(2);
    var aDecOdds=(aMLn<0?1+100/Math.abs(aMLn):1+aMLn/100).toFixed(2);
    WPAR.push({hab:hab,aab:aab,hP:hP,aP:aP,hML:hMLn,aML:aMLn,spread:spreadStr,ou:ouStr,gameKey:gameKey});
    var card='<div class="gc" style="margin-bottom:14px">'
      +'<div class="gch" style="border-top:2px solid var(--vc)">'
      +'<div style="display:flex;justify-content:space-between;align-items:center">'
      +'<div style="font-family:var(--orb);font-size:16px;font-weight:700">'+awayName+' <span style="color:var(--t3);font-size:13px;font-weight:400">'+awayRec+'</span> <span style="font-size:12px;color:var(--t3)">@</span> '+homeName+' <span style="color:var(--t3);font-size:13px;font-weight:400">'+homeRec+'</span></div>'
      +'<div style="text-align:right;font-family:var(--mono);font-size:11px;color:var(--t3)">'
      +'<div>NET: <span style="color:var(--ic)">'+hab+' '+hNetStr+'</span> / <span style="color:var(--vc)">'+aab+' '+aNetStr+'</span></div>'
      +'<div style="margin-top:1px">MC:'+Math.round(ens.mcP*100)+'% BAY:'+Math.round(ens.bayP*100)+'% ELO:'+Math.round(ens.eloP*100)+'%</div>'
      +'</div>'
      +'</div>'
      +'</div>'
      +'<div class="brow">'
      +'<div class="chip" onclick="lockPick(\''+hab+'\',\''+aab+'\',\'WNBA\',\''+hab+' ML\','+hP.toFixed(4)+','+hMLn+','+hDecOdds+',typeof today===\'function\'?today():\'\')" style="border-color:'+hGr.c+'">'
      +'<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">'+hab+' ML</div>'
      +'<div style="font-family:var(--orb);font-size:14px;font-weight:700;color:'+hGr.c+'">'+(hMLn>0?'+':'')+hMLn+'</div>'
      +'<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">'+Math.round(hP*100)+'% '+hGr.g+'</div>'
      +'</div>'
      +'<div class="chip" onclick="lockPick(\''+aab+'\',\''+hab+'\',\'WNBA\',\''+aab+' ML\','+aP.toFixed(4)+','+aMLn+','+aDecOdds+',typeof today===\'function\'?today():\'\')" style="border-color:'+aGr.c+'">'
      +'<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">'+aab+' ML</div>'
      +'<div style="font-family:var(--orb);font-size:14px;font-weight:700;color:'+aGr.c+'">'+(aMLn>0?'+':'')+aMLn+'</div>'
      +'<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">'+Math.round(aP*100)+'% '+aGr.g+'</div>'
      +'</div>'
      +'<div class="chip" onclick="lockPick(\''+hab+'\',\''+aab+'\',\'WNBA\',\'SPREAD '+hab+' '+spreadStr+'\','+hP.toFixed(4)+','+hMLn+','+hDecOdds+',typeof today===\'function\'?today():\'\')">'
      +'<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">SPREAD</div>'
      +'<div style="font-family:var(--orb);font-size:14px;font-weight:700;color:var(--vc)">'+hab+' '+(spreadStr>0?'+':'')+spreadStr+'</div>'
      +'<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">'+Math.round(hP*100)+'%</div>'
      +'</div>'
      +'<div class="chip" onclick="lockPick(\''+hab+'\',\''+aab+'\',\'WNBA\',\'O/U '+ouStr+' OVER\',0.52,+110,2.10,typeof today===\'function\'?today():\'\')">'
      +'<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">O/U</div>'
      +'<div style="font-family:var(--orb);font-size:14px;font-weight:700;color:var(--gc)">'+ouStr+'</div>'
      +'<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">ESPN LINE</div>'
      +'</div>'
      +'<button class="btn btn-o btn-sm" style="font-size:11px;align-self:center" onclick="addWNBAGameLeg(\''+hab+'\',\''+aab+'\',\'ML\',\''+topPick+' ML\','+topP.toFixed(4)+','+(hP>=aP?hMLn:aMLn)+','+(hP>=aP?hDecOdds:aDecOdds)+',\''+gameKey+'\')">+PAR</button>'
      +'</div>'
      +_wnbaReason(topP,topPick,hP>=aP?aab:hab,{hNet:ens.hNet,aNet:ens.aNet})
      +'</div>';
    html_parts.push(card);
  }
  el.innerHTML=html_parts.join('');
  window._wnbaGameData=WPAR;
  // Populate parlay GAME LINES panel
  var pgl=document.getElementById('wnba-parlay-games');
  if(pgl){
    pgl.innerHTML=WPAR.map(function(g){
      var hDecOdds2=(g.hML<0?1+100/Math.abs(g.hML):1+g.hML/100).toFixed(2);
      var aDecOdds2=(g.aML<0?1+100/Math.abs(g.aML):1+g.aML/100).toFixed(2);
      return'<div style="background:rgba(10,0,24,.7);border:1px solid rgba(187,255,0,.2);border-radius:2px;padding:8px;margin-bottom:6px">'
        +'<div style="font-family:var(--mono);font-size:11px;color:var(--t3);margin-bottom:5px">'+g.aab+' @ '+g.hab+'</div>'
        +'<div style="display:flex;flex-wrap:wrap;gap:5px">'
        +'<button class="btn btn-o btn-sm" style="font-size:11px" onclick="addWNBAGameLeg(\''+g.hab+'\',\''+g.aab+'\',\'ML\',\''+g.hab+' ML\','+g.hP.toFixed(4)+','+g.hML+','+hDecOdds2+',\''+g.gameKey+'\')">'+g.hab+' ML '+(g.hML>0?'+':'')+g.hML+'</button>'
        +'<button class="btn btn-o btn-sm" style="font-size:11px" onclick="addWNBAGameLeg(\''+g.hab+'\',\''+g.aab+'\',\'ML\',\''+g.aab+' ML\','+g.aP.toFixed(4)+','+g.aML+','+aDecOdds2+',\''+g.gameKey+'\')">'+g.aab+' ML '+(g.aML>0?'+':'')+g.aML+'</button>'
        +'<button class="btn btn-o btn-sm" style="font-size:11px" onclick="addWNBAGameLeg(\''+g.hab+'\',\''+g.aab+'\',\'SPREAD\',\'SPREAD '+g.hab+' '+g.spread+'\','+g.hP.toFixed(4)+','+g.hML+','+hDecOdds2+',\''+g.gameKey+'\')">SPRD '+g.hab+' '+g.spread+'</button>'
        +'<button class="btn btn-o btn-sm" style="font-size:11px" onclick="addWNBAGameLeg(\''+g.hab+'\',\''+g.aab+'\',\'OU\',\'O/U '+g.ou+' OVER\',0.52,+110,2.10,\''+g.gameKey+'\')">O/U '+g.ou+'</button>'
        +'</div>'
        +'</div>';
    }).join('');
  }
}
window.renderWNBAGames=renderWNBAGames;

// ── PROPS tab ────────────────────────────────────────────────────────────────
function _pGe(lam,n){var p=0,k=n,prob=1;var e=Math.exp(-lam);prob=e;for(var i=1;i<=k;i++)prob*=lam/i;p=0;var cum=0;var cur=e;for(var i=0;i<=k;i++){cum+=cur;if(i<k){cur*=lam/(i+1);}}return Math.max(.01,Math.min(.99,1-cum));}
async function renderWNBAProps(){
  var el=document.getElementById('wnba-props-list');
  if(!el)return;
  el.innerHTML='<div class="loading"><span class="spi"></span> LOADING&hellip;</div>';
  var D=window.__CV_DATA||{};
  var wnbaD=D.wnba||{};
  var players=wnbaD.players||[];
  var ts=wnbaD.teamStats||{};
  var gameData=window._wnbaGameData||[];
  if(!gameData.length){await renderWNBAGames();gameData=window._wnbaGameData||[];}
  if(!gameData.length){el.innerHTML='<div class="empty">NO WNBA GAMES TODAY &mdash; PROPS UNAVAILABLE</div>';return;}
  var today_str=typeof today==='function'?today():new Date().toISOString().slice(0,10);
  var html_parts=[];
  var parlayProps=[];
  for(var gi=0;gi<gameData.length;gi++){
    var g=gameData[gi];
    var hab=g.hab,aab=g.aab;
    // Get players for this game's teams
    var gamePlayers=players.filter(function(p){
      var pk=_wnbaKey(p.team||p.abbr||'');
      return pk===hab||pk===aab||p.team===hab||p.team===aab;
    });
    if(!gamePlayers.length){
      // fallback — top scorers if no team filter
      gamePlayers=players.slice(0,20);
    }
    // Sort by pts descending, take top 10
    gamePlayers=gamePlayers.slice().sort(function(a,b){return(b.pts||b.ppg||0)-(a.pts||a.ppg||0);}).slice(0,10);
    if(!gamePlayers.length)continue;
    html_parts.push('<div style="background:rgba(6,0,15,.9);border:1px solid rgba(187,255,0,.3);border-radius:2px;padding:8px 10px;margin-bottom:10px;font-family:var(--mono);font-size:11px;letter-spacing:1px;color:var(--vc)">'+aab+' @ '+hab+' &mdash; MATCHUP PROPS</div>');
    for(var pi=0;pi<gamePlayers.length;pi++){
      var pl=gamePlayers[pi];
      var pTeam=_wnbaKey(pl.team||pl.abbr||'');
      var opp=pTeam===hab?aab:hab;
      var oppTs=ts[opp]||{};
      var drtg=oppTs.drtg||102;
      var dAdj=(100-drtg)*0.015;
      var pts=parseFloat(pl.pts||pl.ppg||12);
      var reb=parseFloat(pl.reb||pl.rpg||3);
      var ast=parseFloat(pl.ast||pl.apg||2);
      var fg3=parseFloat(pl.fg3m||pl.tpm||0.8);
      var usg=parseFloat(pl.usgpct||pl.usg||20);
      var ts_pct=parseFloat(pl.tspct||pl.ts||0.52);
      // Opponent-adjusted
      var aPts=pts*(1+dAdj);var aReb=reb*(1+dAdj*0.5);var aAst=ast*(1+dAdj*0.5);var aFg3=fg3*(1+dAdj*0.3);
      // Prop lines ~82% of adjusted avg
      var ptsLine=(aPts*0.82).toFixed(1);var rebLine=(aReb*0.82).toFixed(1);var astLine=(aAst*0.82).toFixed(1);
      var praLine=((aPts+aReb+aAst)*0.82).toFixed(1);var fg3Line=(aFg3*0.82).toFixed(1);
      // Probabilities
      var ptsP=_pGe(aPts,parseFloat(ptsLine));
      var rebP=_pGe(aReb,parseFloat(rebLine));
      var astP=_pGe(aAst,parseFloat(astLine));
      var praP=_pGe(aPts+aReb+aAst,parseFloat(praLine));
      var fg3P=_pGe(aFg3,parseFloat(fg3Line));
      var pName=pl.name||pl.player||'PLAYER';
      var pKey=pTeam+'_'+pName.replace(/\s+/g,'_');
      var propCard='<div class="card" style="margin-bottom:10px;border-left:2px solid var(--vc)">'
        +'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">'
        +'<div>'
        +'<div style="font-family:var(--orb);font-size:14px;font-weight:700">'+pName+'</div>'
        +'<div style="font-family:var(--mono);font-size:11px;color:var(--t3);margin-top:2px">'+pTeam+' vs '+opp+' &middot; AVG: '+pts.toFixed(1)+'PTS '+reb.toFixed(1)+'REB '+ast.toFixed(1)+'AST '+fg3.toFixed(1)+'3PT</div>'
        +'<div style="font-family:var(--mono);font-size:10px;color:var(--t3)">USG '+usg.toFixed(0)+'% &middot; TS '+Math.round(ts_pct*100)+'% &middot; OPP DRtg '+drtg.toFixed(0)+'</div>'
        +'</div>'
        +'</div>'
        +'<div style="display:flex;flex-wrap:wrap;gap:6px">';
      // PTS prop
      var ptsGr=_wnbaGrade(ptsP);var ptsML=_wnbaML(ptsP);
      propCard+='<div class="chip" style="border-color:'+ptsGr.c+';min-width:110px">'
        +'<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">PTS O '+ptsLine+'</div>'
        +'<div style="font-family:var(--orb);font-size:13px;font-weight:700;color:'+ptsGr.c+'">'+ptsML+'</div>'
        +'<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">'+Math.round(ptsP*100)+'% '+ptsGr.g+'</div>'
        +'<div style="display:flex;gap:4px;margin-top:5px">'
        +'<button class="btn btn-p btn-sm" style="font-size:10px;padding:2px 5px" onclick="lockPick(\''+pTeam+'\',\''+opp+'\',\'PROP\',\''+pName+' PTS O '+ptsLine+'\','+ptsP.toFixed(4)+','+ptsML+','+(ptsML<0?1+100/Math.abs(ptsML):1+ptsML/100).toFixed(2)+',typeof today===\'function\'?today():\'\')">LOCK</button>'
        +'<button class="btn btn-o btn-sm" style="font-size:10px;padding:2px 5px" onclick="addWNBAPropLeg(\''+pName+' PTS O '+ptsLine+'\','+ptsML+','+ptsP.toFixed(4)+',\''+pKey+'_pts\')">+PAR</button>'
        +'</div></div>';
      parlayProps.push({label:pName+' PTS O '+ptsLine,ml:ptsML,prob:ptsP,key:pKey+'_pts'});
      // REB prop (if avg >= 4)
      if(reb>=4){
        var rebGr=_wnbaGrade(rebP);var rebML=_wnbaML(rebP);
        propCard+='<div class="chip" style="border-color:'+rebGr.c+';min-width:110px">'
          +'<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">REB O '+rebLine+'</div>'
          +'<div style="font-family:var(--orb);font-size:13px;font-weight:700;color:'+rebGr.c+'">'+rebML+'</div>'
          +'<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">'+Math.round(rebP*100)+'% '+rebGr.g+'</div>'
          +'<div style="display:flex;gap:4px;margin-top:5px">'
          +'<button class="btn btn-p btn-sm" style="font-size:10px;padding:2px 5px" onclick="lockPick(\''+pTeam+'\',\''+opp+'\',\'PROP\',\''+pName+' REB O '+rebLine+'\','+rebP.toFixed(4)+','+rebML+','+(rebML<0?1+100/Math.abs(rebML):1+rebML/100).toFixed(2)+',typeof today===\'function\'?today():\'\')">LOCK</button>'
          +'<button class="btn btn-o btn-sm" style="font-size:10px;padding:2px 5px" onclick="addWNBAPropLeg(\''+pName+' REB O '+rebLine+'\','+rebML+','+rebP.toFixed(4)+',\''+pKey+'_reb\')">+PAR</button>'
          +'</div></div>';
      }
      // AST prop (if avg >= 4)
      if(ast>=4){
        var astGr=_wnbaGrade(astP);var astML=_wnbaML(astP);
        propCard+='<div class="chip" style="border-color:'+astGr.c+';min-width:110px">'
          +'<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">AST O '+astLine+'</div>'
          +'<div style="font-family:var(--orb);font-size:13px;font-weight:700;color:'+astGr.c+'">'+astML+'</div>'
          +'<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">'+Math.round(astP*100)+'% '+astGr.g+'</div>'
          +'<div style="display:flex;gap:4px;margin-top:5px">'
          +'<button class="btn btn-p btn-sm" style="font-size:10px;padding:2px 5px" onclick="lockPick(\''+pTeam+'\',\''+opp+'\',\'PROP\',\''+pName+' AST O '+astLine+'\','+astP.toFixed(4)+','+astML+','+(astML<0?1+100/Math.abs(astML):1+astML/100).toFixed(2)+',typeof today===\'function\'?today():\'\')">LOCK</button>'
          +'<button class="btn btn-o btn-sm" style="font-size:10px;padding:2px 5px" onclick="addWNBAPropLeg(\''+pName+' AST O '+astLine+'\','+astML+','+astP.toFixed(4)+',\''+pKey+'_ast\')">+PAR</button>'
          +'</div></div>';
      }
      // PRA combo (if reb>=3 + ast>=3)
      if(reb>=3&&ast>=3){
        var praGr=_wnbaGrade(praP);var praML=_wnbaML(praP);
        propCard+='<div class="chip" style="border-color:'+praGr.c+';min-width:110px">'
          +'<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">PRA O '+praLine+'</div>'
          +'<div style="font-family:var(--orb);font-size:13px;font-weight:700;color:'+praGr.c+'">'+praML+'</div>'
          +'<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">'+Math.round(praP*100)+'% '+praGr.g+'</div>'
          +'<div style="display:flex;gap:4px;margin-top:5px">'
          +'<button class="btn btn-p btn-sm" style="font-size:10px;padding:2px 5px" onclick="lockPick(\''+pTeam+'\',\''+opp+'\',\'PROP\',\''+pName+' PRA O '+praLine+'\','+praP.toFixed(4)+','+praML+','+(praML<0?1+100/Math.abs(praML):1+praML/100).toFixed(2)+',typeof today===\'function\'?today():\'\')">LOCK</button>'
          +'<button class="btn btn-o btn-sm" style="font-size:10px;padding:2px 5px" onclick="addWNBAPropLeg(\''+pName+' PRA O '+praLine+'\','+praML+','+praP.toFixed(4)+',\''+pKey+'_pra\')">+PAR</button>'
          +'</div></div>';
      }
      // 3PT prop (if fg3m >= 1.0)
      if(fg3>=1.0){
        var fg3Gr=_wnbaGrade(fg3P);var fg3ML=_wnbaML(fg3P);
        propCard+='<div class="chip" style="border-color:'+fg3Gr.c+';min-width:110px">'
          +'<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">3PT O '+fg3Line+'</div>'
          +'<div style="font-family:var(--orb);font-size:13px;font-weight:700;color:'+fg3Gr.c+'">'+fg3ML+'</div>'
          +'<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">'+Math.round(fg3P*100)+'% '+fg3Gr.g+'</div>'
          +'<div style="display:flex;gap:4px;margin-top:5px">'
          +'<button class="btn btn-p btn-sm" style="font-size:10px;padding:2px 5px" onclick="lockPick(\''+pTeam+'\',\''+opp+'\',\'PROP\',\''+pName+' 3PT O '+fg3Line+'\','+fg3P.toFixed(4)+','+fg3ML+','+(fg3ML<0?1+100/Math.abs(fg3ML):1+fg3ML/100).toFixed(2)+',typeof today===\'function\'?today():\'\')">LOCK</button>'
          +'<button class="btn btn-o btn-sm" style="font-size:10px;padding:2px 5px" onclick="addWNBAPropLeg(\''+pName+' 3PT O '+fg3Line+'\','+fg3ML+','+fg3P.toFixed(4)+',\''+pKey+'_3pt\')">+PAR</button>'
          +'</div></div>';
      }
      propCard+='</div></div>';
      html_parts.push(propCard);
    }
  }
  el.innerHTML=html_parts.length?html_parts.join(''):'<div class="empty">NO PLAYER DATA AVAILABLE</div>';
  // Populate parlay PLAYER PROPS panel
  var pp=document.getElementById('wnba-parlay-props');
  if(pp&&parlayProps.length){
    pp.innerHTML=parlayProps.map(function(p){
      return'<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 8px;background:rgba(10,0,24,.7);border:1px solid rgba(187,255,0,.15);border-radius:2px;margin-bottom:4px;font-family:var(--mono);font-size:11px">'
        +'<span style="color:var(--t2)">'+p.label+'</span>'
        +'<div style="display:flex;gap:5px;align-items:center">'
        +'<span style="color:var(--vc)">'+(p.ml>0?'+':'')+p.ml+'</span>'
        +'<span style="color:var(--t3)">'+Math.round(p.prob*100)+'%</span>'
        +'<button class="btn btn-o btn-sm" style="font-size:10px;padding:2px 6px" onclick="addWNBAPropLeg(\''+p.label+'\','+p.ml+','+p.prob.toFixed(4)+',\''+p.key+'\')">+PAR</button>'
        +'</div></div>';
    }).join('');
  }
}
window.renderWNBAProps=renderWNBAProps;

// ── PARLAY tab ────────────────────────────────────────────────────────────────
window._wnbaParlay=[];
function wnbaParTab(t){
  var g=document.getElementById('wpar-games'),p=document.getElementById('wpar-props');
  var gb=document.getElementById('wnba-par-games-btn'),pb=document.getElementById('wnba-par-props-btn');
  if(t==='games'){if(g)g.style.display='block';if(p)p.style.display='none';if(gb)gb.classList.add('btn-p');if(pb)pb.classList.remove('btn-p');}
  else{if(g)g.style.display='none';if(p)p.style.display='block';if(pb)pb.classList.add('btn-p');if(gb)gb.classList.remove('btn-p');}
}
window.wnbaParTab=wnbaParTab;
function _wnbaRenderLegs(){
  var legs=window._wnbaParlay||[];
  var el=document.getElementById('wnba-parlay-legs');
  var lc=document.getElementById('wnba-lc');
  if(lc)lc.textContent='('+legs.length+')';
  if(!el)return;
  if(!legs.length){el.innerHTML='<span style="color:var(--t3)">NO LEGS ADDED</span>';return;}
  el.innerHTML=legs.map(function(l,i){
    var badge=l.isGame
      ?'<span style="background:rgba(0,200,255,.15);color:var(--ic);font-size:9px;padding:1px 4px;border-radius:1px;margin-right:4px">GAME</span>'
      :'<span style="background:rgba(187,255,0,.15);color:var(--vc);font-size:9px;padding:1px 4px;border-radius:1px;margin-right:4px">PROP</span>';
    return'<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.06)">'
      +'<span style="font-family:var(--mono);font-size:11px;color:var(--t2)">'+badge+l.label+' '+(l.ml>0?'+':'')+l.ml+'</span>'
      +'<button onclick="window._wnbaParlay.splice('+i+',1);_wnbaRenderLegs();calcWNBAP()" style="background:none;border:none;color:var(--hc);cursor:pointer;font-size:14px;padding:0 4px">&times;</button>'
      +'</div>';
  }).join('');
}
function addWNBAGameLeg(hab,aab,type,betOn,prob,ml,dec,gameKey){
  if(!window._wnbaParlay)window._wnbaParlay=[];
  if(window._wnbaParlay.length>=8){if(typeof toast==='function')toast('// MAX 8 LEGS');return;}
  if(window._wnbaParlay.find(function(l){return l.isGame&&l.gameKey===gameKey&&l.type===type;})){if(typeof toast==='function')toast('// ONE '+type+' PER GAME');return;}
  window._wnbaParlay.push({label:betOn,ml:ml,prob:prob,dec:parseFloat(dec)||2.0,gameKey:gameKey,type:type,isGame:true});
  _wnbaRenderLegs();calcWNBAP();
}
function addWNBALeg(label,ml,prob,game){addWNBAGameLeg(game||'',game||'','ML',label,prob,ml,ml<0?1+100/Math.abs(ml):1+ml/100,game||'');}
function addWNBAPropLeg(label,ml,prob,key){
  if(!window._wnbaParlay)window._wnbaParlay=[];
  if(window._wnbaParlay.length>=8){if(typeof toast==='function')toast('// MAX 8 LEGS');return;}
  if(window._wnbaParlay.find(function(l){return l.propKey===key;})){if(typeof toast==='function')toast('// PROP ALREADY ADDED');return;}
  window._wnbaParlay.push({label:label,ml:ml,prob:parseFloat(prob),dec:ml<0?1+100/Math.abs(ml):1+ml/100,propKey:key,isGame:false});
  _wnbaRenderLegs();calcWNBAP();
}
function calcWNBAP(){
  var legs=window._wnbaParlay||[];
  var el=document.getElementById('wnba-parlay-res');
  if(!el)return;
  if(!legs.length){el.innerHTML='';return;}
  var w=parseFloat(document.getElementById('wnba-p-w')?.value||100);
  var cD=legs.reduce(function(a,l){return a*l.dec;},1);
  var cP=legs.reduce(function(a,l){return a*l.prob;},1);
  var cML=cD>=2?Math.round((cD-1)*100):Math.round(-100/(cD-1));
  var pay=(w*cD).toFixed(2);
  var ev=((cP*cD-1)*100).toFixed(1);
  var e2=parseFloat(ev);
  var gr=_wnbaGrade(cP);
  var gameLegs=legs.filter(function(l){return l.isGame;}).length;
  var propLegs=legs.length-gameLegs;
  el.innerHTML='<div style="background:rgba(6,0,15,.9);border:1px solid rgba(240,0,255,.3);border-radius:2px;padding:10px;margin-bottom:8px">'
    +'<div style="font-family:var(--mono);font-size:11px;color:var(--t3);margin-bottom:4px">PARLAY ANALYSIS</div>'
    +'<div style="font-family:var(--orb);font-size:18px;font-weight:700;color:var(--pc)">'+(cML>0?'+':'')+cML+'</div>'
    +'<div style="font-family:var(--mono);font-size:13px;color:var(--t2);margin-top:4px">COMBINED PROB: <span style="color:'+gr.c+'">'+Math.round(cP*100)+'% '+gr.g+'</span></div>'
    +'<div style="font-family:var(--mono);color:var(--nc);font-size:14px">$'+w+' &rarr; $'+parseFloat(pay).toLocaleString()+'</div>'
    +'<div style="font-family:var(--mono);font-size:12px;color:var(--t2);margin-top:5px">EV: <span style="color:'+(e2>=0?'var(--nc)':'var(--hc)')+'">'+ev+'%</span></div>'
    +'<div style="font-family:var(--mono);font-size:11px;color:var(--t3);margin-top:3px">'+legs.length+' LEGS &middot; '+gameLegs+' GAME &middot; '+propLegs+' PROP</div>'
    +'<button class="btn btn-p btn-fw" style="margin-top:9px" onclick="lockNBAParlay('+w+','+cP.toFixed(4)+',\''+cML+'\',\''+cD.toFixed(2)+'\')">LOCK PARLAY</button>'
    +'</div>';
}
window.addWNBAGameLeg=addWNBAGameLeg;
window.addWNBALeg=addWNBALeg;
window.addWNBAPropLeg=addWNBAPropLeg;
window.calcWNBAP=calcWNBAP;
window._wnbaRenderLegs=_wnbaRenderLegs;

function renderWNBAContent(){'''

assert html.count(old_js) == 1, f"JS block not unique: found {html.count(old_js)}"
html = html.replace(old_js, NEW_JS, 1)
print("JS section replaced OK")

# ══════════════════════════════════════════════════════════════════
# 3. FIX T() WNBA ROUTING — update to call new functions cleanly
# ══════════════════════════════════════════════════════════════════

OLD_WNBA_ROUTE = '''  if(sport==='wnba'){
    try{
      if(tabId==='games')renderWNBAGames();
      else if(tabId==='props')renderWNBAProps();
      else if(tabId==='parlay'){renderWNBAGames();try{const pg=document.getElementById('wnba-parlay-games');if(pg&&pg.innerHTML.includes('LOAD TODAY'))renderWNBAGames();}catch(ex){}}
      else if(tabId==='model'){try{renderModelWeights('wnba','wnba-model-weights');}catch(ex){}}
      else if(tabId==='config'){}
    }catch(e){console.error('WNBA tab',tabId,e);}
  }'''

NEW_WNBA_ROUTE = '''  if(sport==='wnba'){
    try{
      if(tabId==='games')renderWNBAGames();
      else if(tabId==='props')renderWNBAProps();
      else if(tabId==='parlay'){
        renderWNBAGames();
        renderWNBAProps();
      }
      else if(tabId==='model'){try{renderModelWeights('wnba','wnba-model-weights');}catch(ex){}}
      else if(tabId==='config'){}
    }catch(e){console.error('WNBA tab',tabId,e);}
  }'''

assert html.count(OLD_WNBA_ROUTE) == 1, f"Route block not unique: {html.count(OLD_WNBA_ROUTE)}"
html = html.replace(OLD_WNBA_ROUTE, NEW_WNBA_ROUTE, 1)
print("T() WNBA routing updated OK")

# ══════════════════════════════════════════════════════════════════
# 4. FIX setSub WNBA call to use new renderWNBAGames
# ══════════════════════════════════════════════════════════════════

OLD_SETSUB = "  if(sport==='nba'&&sub==='wnba'){try{T('wnba','games');renderWNBAGames();}catch(e){}}"
NEW_SETSUB = "  if(sport==='nba'&&sub==='wnba'){try{T('wnba','games');if(typeof renderWNBAGames==='function')renderWNBAGames();}catch(e){}}"

assert html.count(OLD_SETSUB) == 1, f"setSub block not unique: {html.count(OLD_SETSUB)}"
html = html.replace(OLD_SETSUB, NEW_SETSUB, 1)
print("setSub WNBA call updated OK")

# ══════════════════════════════════════════════════════════════════
# 5. VALIDATE and WRITE
# ══════════════════════════════════════════════════════════════════

scripts = list(__import__('re').finditer(r'<script([^>]*)>([\s\S]*?)</script>', html))
js = [s.group(2) for s in scripts if len(s.group(2)) > 10000][0]
bt = js.count('`'); op = js.count('{'); cl = js.count('}')
bad = js.count(chr(39)+chr(10)+chr(39))
print(f'BT:{bt}(ok={bt%2==0}) Braces:{op}/{cl}(ok={op==cl}) LF:{bad}(ok={bad==0})')
assert bt%2==0, "Backtick imbalance!"
assert op==cl, "Brace imbalance!"
assert bad==0, "LF in string!"

open('docs/app.html','w').write(html)
open('docs/index.html','w').write(html)
print(f"Written OK — {html.count(chr(10))+1} lines")
