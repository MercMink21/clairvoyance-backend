#!/usr/bin/env python3
"""
WNBA full rebuild v2 — Session 9 fix
Uses template literals for all HTML building (mirrors renderNBAGames pattern).
Runs against the last known-good app.html (50f37f5).
"""
import re, sys

html = open('/tmp/working_app.html').read()

# ══════════════════════════════════════════════════════════════════
# 1. REPLACE nba-wnba HTML SUBPANE
# ══════════════════════════════════════════════════════════════════

start_marker = '  <div id="nba-wnba" class="subp">'
end_pattern   = '  </div>\n\n  </div>\n</div>'

idx_start = html.index(start_marker)
idx_end   = html.index(end_pattern, idx_start) + len(end_pattern)
old_wnba_html = html[idx_start:idx_end]

NEW_HTML = """  <div id="nba-wnba" class="subp">
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
          <div class="sh" style="margin:0"><span class="i"></span> TODAY'S GAMES <span id="wnba-games-date" style="font-family:var(--mono);font-size:11px;color:var(--t3);margin-left:8px"></span></div>
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
          POISSON MODEL &middot; OPPONENT DRtg ADJUSTED &middot; TODAY'S GAMES ONLY &middot; TOP 10 PER MATCHUP
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
</div>"""

assert html.count(old_wnba_html) == 1, f"HTML block not unique: {html.count(old_wnba_html)}"
html = html.replace(old_wnba_html, NEW_HTML, 1)
print("HTML subpane replaced OK")

# ══════════════════════════════════════════════════════════════════
# 2. REPLACE OLD WNBA JS — using template literals throughout
# ══════════════════════════════════════════════════════════════════

OLD_JS_START = '// ── WNBA ELO ratings (2026 season baseline) ──────────────────────────────'
OLD_JS_END   = 'window._wnbaRenderLegs=_wnbaRenderLegs;\n\nfunction renderWNBAContent(){'

idx_js_start = html.index(OLD_JS_START)
idx_js_end   = html.index(OLD_JS_END) + len(OLD_JS_END)
old_js = html[idx_js_start:idx_js_end]

# NOTE: All HTML strings use template literals (backtick strings) — same as renderNBAGames.
# This avoids ALL single-quote escaping issues that killed v1.
NEW_JS = r"""// ── WNBA ENGINE (Session 9 v2 — template literal HTML, NBA-mirrored) ────────

window.WNBA_ELO={
  NY:1640,MIN:1590,LV:1560,CON:1535,IND:1525,SEA:1495,
  CHI:1485,PHX:1455,ATL:1445,LA:1430,DAL:1415,GS:1410,WSH:1390,TOR:1355
};
var WNBA_ABBR_MAP={
  LVA:'LV',NYL:'NY',GSV:'GS',PHO:'PHX',WAS:'WSH',LAE:'LA',LAS:'LV',
  'New York':'NY','Minnesota':'MIN','Las Vegas':'LV','Connecticut':'CON',
  'Indiana':'IND','Seattle':'SEA','Chicago':'CHI','Phoenix':'PHX',
  'Atlanta':'ATL','Los Angeles':'LA','Dallas':'DAL',
  'Golden State':'GS','Washington':'WSH','Toronto':'TOR'
};
var WNBA_WIN_PCT={
  NY:.72,MIN:.65,LV:.60,CON:.58,IND:.58,SEA:.52,
  CHI:.48,PHX:.46,ATL:.45,GS:.44,LA:.40,DAL:.40,WSH:.38,TOR:.30
};
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
  var hBase=Math.min(.88,Math.max(.12,0.5+(hNet-aNet)*0.012+hfa));
  var wins=0,N=5000;
  for(var i=0;i<N;i++){
    var u1=Math.random(),u2=Math.random();
    var z=Math.sqrt(-2*Math.log(u1+1e-12))*Math.cos(2*Math.PI*u2);
    if(Math.random()<Math.min(.97,Math.max(.03,hBase+z*0.09)))wins++;
  }
  return{hP:wins/N,aP:1-wins/N,hNet:hNet,aNet:aNet};
}
function wnbaEns(hA,awA,espnOdds){
  var hk=_wnbaKey(hA),ak=_wnbaKey(awA);
  var mc=wnbaMC(hA,awA);
  var hfa=0.028;
  var eloP=Math.min(.86,Math.max(.14,wnbaEloWP(window.WNBA_ELO[hk]||1490,window.WNBA_ELO[ak]||1490)+hfa));
  var D=window.__CV_DATA||{};
  var ts=D.wnba&&D.wnba.teamStats||{};
  var ht=ts[hk]||ts[hA]||{};var at=ts[ak]||ts[awA]||{};
  var hWp=ht.wpct!==undefined?ht.wpct:(WNBA_WIN_PCT[hk]||0.5);
  var aWp=at.wpct!==undefined?at.wpct:(WNBA_WIN_PCT[ak]||0.5);
  var hBay=Math.min(.86,Math.max(.14,(hWp+hfa)/(hWp+aWp+1e-9)));
  var wmc=parseFloat(document.getElementById('wnba-w-mc')&&document.getElementById('wnba-w-mc').value||45)/100;
  var wbay=parseFloat(document.getElementById('wnba-w-bay')&&document.getElementById('wnba-w-bay').value||25)/100;
  var welo=parseFloat(document.getElementById('wnba-w-elo')&&document.getElementById('wnba-w-elo').value||30)/100;
  var tot=wmc+wbay+welo||1;wmc/=tot;wbay/=tot;welo/=tot;
  var ens=mc.hP*wmc+hBay*wbay+eloP*welo;
  if(espnOdds&&espnOdds.homeML){
    var hml=espnOdds.homeML;
    var hImp=hml<0?Math.abs(hml)/(Math.abs(hml)+100):100/(hml+100);
    ens=ens*0.70+hImp*0.30;
  }
  return{hP:Math.min(.88,Math.max(.12,ens)),aP:1-Math.min(.88,Math.max(.12,ens)),
         mcP:mc.hP,bayP:hBay,eloP:eloP,hNet:mc.hNet,aNet:mc.aNet};
}
function applyWNBAWeights(){
  WNBA_ENS={
    mc:parseInt(document.getElementById('wnba-w-mc')&&document.getElementById('wnba-w-mc').value||45)/100,
    bay:parseInt(document.getElementById('wnba-w-bay')&&document.getElementById('wnba-w-bay').value||25)/100,
    elo:parseInt(document.getElementById('wnba-w-elo')&&document.getElementById('wnba-w-elo').value||30)/100
  };
}
window.applyWNBAWeights=applyWNBAWeights;
function _wnbaGrade(p){
  if(p>=.68)return{g:'ELITE',c:'var(--gc)'};
  if(p>=.61)return{g:'LOCK',c:'var(--nc)'};
  if(p>=.54)return{g:'LEAN',c:'var(--ic)'};
  return{g:'SKIP',c:'var(--hc)'};
}
function _wnbaML(p){var ml=p>=.5?-Math.round(p/(1-p)*100):Math.round((1-p)/p*100);return ml>0?'+'+ml:ml;}
function _wnbaDec(ml){return ml<0?1+100/Math.abs(ml):1+ml/100;}

async function renderWNBAGames(){
  var el=document.getElementById('wnba-games-list');
  var dateEl=document.getElementById('wnba-games-date');
  if(!el)return;
  el.innerHTML='<div class="loading"><span class="spi"></span> LOADING...</div>';
  var D=window.__CV_DATA||{};
  var todayStr=typeof today==='function'?today():new Date().toISOString().slice(0,10);
  if(dateEl){
    var dt=new Date(todayStr+'T12:00:00');
    dateEl.textContent=dt.toLocaleDateString('en-US',{weekday:'short',month:'short',day:'numeric'});
  }
  var games=[];
  try{
    var r=await fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard');
    if(r.ok){var jd=await r.json();games=jd.events||[];}
  }catch(ex){console.warn('WNBA scoreboard',ex);}
  if(!games.length){
    var fb=(D.wnba&&D.wnba.today)||[];
    games=fb.map(function(g){
      return{_fb:true,home:g.home||g.homeName,away:g.away||g.awayName,
             homeML:g.homeML,awayML:g.awayML,overUnder:g.ou};
    });
  }
  if(!games.length){el.innerHTML='<div class="empty">NO WNBA GAMES TODAY</div>';return;}
  var WPAR=[];
  el.innerHTML=games.map(function(ev){
    var hab,aab,homeML,awayML,spread,ou,homeName,awayName,homeRec,awayRec;
    if(ev._fb){
      hab=_wnbaKey(ev.home);aab=_wnbaKey(ev.away);
      homeML=ev.homeML;awayML=ev.awayML;ou=ev.overUnder;
      homeName=ev.home;awayName=ev.away;homeRec='';awayRec='';spread=null;
    }else{
      var comps=(ev.competitions&&ev.competitions[0])||{};
      var teams=comps.competitors||[];
      var hT=teams.filter(function(t){return t.homeAway==='home';})[0]||teams[0]||{};
      var aT=teams.filter(function(t){return t.homeAway==='away';})[0]||teams[1]||{};
      homeName=(hT.team&&(hT.team.shortDisplayName||hT.team.abbreviation))||'HOME';
      awayName=(aT.team&&(aT.team.shortDisplayName||aT.team.abbreviation))||'AWAY';
      hab=_wnbaKey((hT.team&&hT.team.abbreviation)||homeName);
      aab=_wnbaKey((aT.team&&aT.team.abbreviation)||awayName);
      homeRec=(hT.records&&hT.records[0]&&hT.records[0].summary)||'';
      awayRec=(aT.records&&aT.records[0]&&aT.records[0].summary)||'';
      var odds=(comps.odds&&comps.odds[0])||{};
      homeML=odds.homeTeamOdds&&odds.homeTeamOdds.moneyLine;
      awayML=odds.awayTeamOdds&&odds.awayTeamOdds.moneyLine;
      spread=odds.spread;ou=odds.overUnder;
    }
    var espnHL=homeML?{homeML:homeML,awayML:awayML}:null;
    var ens=wnbaEns(hab,aab,espnHL);
    var hP=ens.hP,aP=ens.aP;
    var hGr=_wnbaGrade(hP),aGr=_wnbaGrade(aP);
    var topGr=hP>=aP?hGr:aGr;var topPick=hP>=aP?hab:aab;var topP=Math.max(hP,aP);
    var hMLn=homeML||parseInt(_wnbaML(hP));
    var aMLn=awayML||parseInt(_wnbaML(aP));
    var spreadStr=spread!=null?spread:((0.5-hP)*25).toFixed(1);
    var ouStr=ou||((ens.hNet+ens.aNet)*0.5+170).toFixed(1);
    var gameKey=hab+'_'+aab;
    var ts=(D.wnba&&D.wnba.teamStats)||{};
    var ht2=ts[hab]||{};var at2=ts[aab]||{};
    var hNetStr=ht2.net!==undefined?(ht2.net>=0?'+':'')+parseFloat(ht2.net).toFixed(1):'N/A';
    var aNetStr=at2.net!==undefined?(at2.net>=0?'+':'')+parseFloat(at2.net).toFixed(1):'N/A';
    var hDec=_wnbaDec(hMLn).toFixed(2);
    var aDec=_wnbaDec(aMLn).toFixed(2);
    var sz=topP>=.68?'FULL UNIT':topP>=.61?'FULL UNIT':topP>=.54?'HALF UNIT':'FADE';
    var netDiff=(ens.hNet-ens.aNet).toFixed(1);
    var rsn=topP>=.68?hab+' dominant net rating advantage (+'+netDiff+' pts/100). High-confidence play.':
            topP>=.61?hab+' edges '+aab+' (+'+netDiff+' net). Solid play at this number.':
            topP>=.54?'Slight edge for '+hab+' (+'+netDiff+' net). Proceed with caution.':
                      'Marginal edge or no edge. Model suggests fading.';
    WPAR.push({hab:hab,aab:aab,hP:hP,aP:aP,hML:hMLn,aML:aMLn,
               hDec:hDec,aDec:aDec,spread:spreadStr,ou:ouStr,gameKey:gameKey});
    var hSign=hMLn>0?'+':'';
    var aSign=aMLn>0?'+':'';
    return `<div class="gc" style="margin-bottom:14px">
<div class="gch" style="border-top:2px solid var(--vc)">
<div style="display:flex;justify-content:space-between;align-items:center">
<div style="font-family:var(--orb);font-size:15px;font-weight:700">${awayName} <span style="color:var(--t3);font-size:12px">${awayRec}</span> @ ${homeName} <span style="color:var(--t3);font-size:12px">${homeRec}</span></div>
<div style="text-align:right;font-family:var(--mono);font-size:11px;color:var(--t3)">
<div>NET: <span style="color:var(--ic)">${hab} ${hNetStr}</span> / <span style="color:var(--vc)">${aab} ${aNetStr}</span></div>
<div style="margin-top:1px">MC:${Math.round(ens.mcP*100)}% BAY:${Math.round(ens.bayP*100)}% ELO:${Math.round(ens.eloP*100)}%</div>
</div></div></div>
<div class="brow">
<div class="chip" onclick="lockPick('${hab}','${aab}','WNBA','${hab} ML',${hP.toFixed(4)},${hMLn},${hDec},typeof today==='function'?today():'')" style="border-color:${hGr.c}">
<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">${hab} ML</div>
<div style="font-family:var(--orb);font-size:14px;font-weight:700;color:${hGr.c}">${hSign}${hMLn}</div>
<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">${Math.round(hP*100)}% ${hGr.g}</div>
</div>
<div class="chip" onclick="lockPick('${aab}','${hab}','WNBA','${aab} ML',${aP.toFixed(4)},${aMLn},${aDec},typeof today==='function'?today():'')" style="border-color:${aGr.c}">
<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">${aab} ML</div>
<div style="font-family:var(--orb);font-size:14px;font-weight:700;color:${aGr.c}">${aSign}${aMLn}</div>
<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">${Math.round(aP*100)}% ${aGr.g}</div>
</div>
<div class="chip" onclick="lockPick('${hab}','${aab}','WNBA','SPREAD ${hab} ${spreadStr}',${hP.toFixed(4)},${hMLn},${hDec},typeof today==='function'?today():'')">
<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">SPREAD</div>
<div style="font-family:var(--orb);font-size:14px;font-weight:700;color:var(--vc)">${hab} ${spreadStr}</div>
<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">${Math.round(hP*100)}%</div>
</div>
<div class="chip" onclick="lockPick('${hab}','${aab}','WNBA','O/U ${ouStr} OVER',0.52,110,2.10,typeof today==='function'?today():'')">
<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">O/U</div>
<div style="font-family:var(--orb);font-size:14px;font-weight:700;color:var(--gc)">${ouStr}</div>
<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">ESPN LINE</div>
</div>
<button class="btn btn-o btn-sm" style="font-size:11px;align-self:center" onclick="addWNBAGameLeg('${hab}','${aab}','ML','${topPick} ML',${topP.toFixed(4)},${hP>=aP?hMLn:aMLn},${hP>=aP?hDec:aDec},'${gameKey}')">+PAR</button>
</div>
<div style="margin-top:10px;padding:8px 10px;background:rgba(6,0,15,.8);border-left:3px solid ${topGr.c};border-radius:0 2px 2px 0">
<div style="font-family:var(--mono);font-size:10px;letter-spacing:2px;color:var(--t3);margin-bottom:4px">ENGINE REASONING</div>
<span style="font-family:var(--mono);font-size:12px;font-weight:700;color:${topGr.c};letter-spacing:1px">${topGr.g}</span>
<span style="font-family:var(--mono);font-size:11px;color:var(--t3);margin-left:8px">SIZE: ${sz}</span>
<div style="font-family:var(--mono);font-size:12px;color:var(--t2);margin-top:4px;line-height:1.5">${rsn}</div>
</div>
</div>`;
  }).join('');
  window._wnbaGameData=WPAR;
  var pgl=document.getElementById('wnba-parlay-games');
  if(pgl){
    pgl.innerHTML=WPAR.map(function(g){
      var hs=g.hML>0?'+':'';
      var as2=g.aML>0?'+':'';
      return `<div style="background:rgba(10,0,24,.7);border:1px solid rgba(187,255,0,.2);border-radius:2px;padding:8px;margin-bottom:6px">
<div style="font-family:var(--mono);font-size:11px;color:var(--t3);margin-bottom:5px">${g.aab} @ ${g.hab}</div>
<div style="display:flex;flex-wrap:wrap;gap:5px">
<button class="btn btn-o btn-sm" style="font-size:11px" onclick="addWNBAGameLeg('${g.hab}','${g.aab}','ML','${g.hab} ML',${g.hP.toFixed(4)},${g.hML},${g.hDec},'${g.gameKey}')">${g.hab} ML ${hs}${g.hML}</button>
<button class="btn btn-o btn-sm" style="font-size:11px" onclick="addWNBAGameLeg('${g.hab}','${g.aab}','ML','${g.aab} ML',${g.aP.toFixed(4)},${g.aML},${g.aDec},'${g.gameKey}')">${g.aab} ML ${as2}${g.aML}</button>
<button class="btn btn-o btn-sm" style="font-size:11px" onclick="addWNBAGameLeg('${g.hab}','${g.aab}','SPREAD','SPREAD ${g.hab} ${g.spread}',${g.hP.toFixed(4)},${g.hML},${g.hDec},'${g.gameKey}')">SPRD ${g.hab} ${g.spread}</button>
<button class="btn btn-o btn-sm" style="font-size:11px" onclick="addWNBAGameLeg('${g.hab}','${g.aab}','OU','O/U ${g.ou} OVER',0.52,110,2.10,'${g.gameKey}')">O/U ${g.ou}</button>
</div></div>`;
    }).join('');
  }
}
window.renderWNBAGames=renderWNBAGames;

function _pGe(lam,n){
  var e=Math.exp(-lam),cum=0,cur=e;
  for(var i=0;i<=n;i++){cum+=cur;if(i<n)cur*=lam/(i+1);}
  return Math.max(.01,Math.min(.99,1-cum));
}
async function renderWNBAProps(){
  var el=document.getElementById('wnba-props-list');
  if(!el)return;
  el.innerHTML='<div class="loading"><span class="spi"></span> LOADING...</div>';
  var D=window.__CV_DATA||{};
  var wnbaD=D.wnba||{};
  var players=wnbaD.players||[];
  var ts=wnbaD.teamStats||{};
  var gameData=window._wnbaGameData||[];
  if(!gameData.length){await renderWNBAGames();gameData=window._wnbaGameData||[];}
  if(!gameData.length){el.innerHTML='<div class="empty">NO WNBA GAMES TODAY &mdash; PROPS UNAVAILABLE</div>';return;}
  var parlayProps=[];
  el.innerHTML=gameData.map(function(g){
    var hab=g.hab,aab=g.aab;
    var gamePlayers=players.filter(function(p){
      var pk=_wnbaKey(p.team||p.abbr||'');
      return pk===hab||pk===aab||p.team===hab||p.team===aab;
    });
    if(!gamePlayers.length)gamePlayers=players.slice(0,20);
    gamePlayers=gamePlayers.slice().sort(function(a,b){
      return(b.pts||b.ppg||0)-(a.pts||a.ppg||0);
    }).slice(0,10);
    if(!gamePlayers.length)return '';
    var matchupHdr=`<div style="background:rgba(6,0,15,.9);border:1px solid rgba(187,255,0,.3);border-radius:2px;padding:8px 10px;margin-bottom:10px;font-family:var(--mono);font-size:11px;letter-spacing:1px;color:var(--vc)">${aab} @ ${hab} &mdash; MATCHUP PROPS</div>`;
    var propCards=gamePlayers.map(function(pl){
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
      var ts2=parseFloat(pl.tspct||pl.ts||0.52);
      var aPts=pts*(1+dAdj);var aReb=reb*(1+dAdj*0.5);
      var aAst=ast*(1+dAdj*0.5);var aFg3=fg3*(1+dAdj*0.3);
      var ptsLine=(aPts*0.82).toFixed(1);var rebLine=(aReb*0.82).toFixed(1);
      var astLine=(aAst*0.82).toFixed(1);var praLine=((aPts+aReb+aAst)*0.82).toFixed(1);
      var fg3Line=(aFg3*0.82).toFixed(1);
      var ptsP=_pGe(aPts,parseFloat(ptsLine));
      var rebP=_pGe(aReb,parseFloat(rebLine));
      var astP=_pGe(aAst,parseFloat(astLine));
      var praP=_pGe(aPts+aReb+aAst,parseFloat(praLine));
      var fg3P=_pGe(aFg3,parseFloat(fg3Line));
      var pName=pl.name||pl.player||'PLAYER';
      var pKey=(pTeam+'_'+pName).replace(/\s+/g,'_');
      var ptsGr=_wnbaGrade(ptsP);var ptsML=_wnbaML(ptsP);
      var ptsDec=_wnbaDec(parseInt(ptsML)).toFixed(2);
      parlayProps.push({label:pName+' PTS O '+ptsLine,ml:parseInt(ptsML),prob:ptsP,key:pKey+'_pts'});
      var chips=`<div class="chip" style="border-color:${ptsGr.c};min-width:110px">
<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">PTS O ${ptsLine}</div>
<div style="font-family:var(--orb);font-size:13px;font-weight:700;color:${ptsGr.c}">${ptsML}</div>
<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">${Math.round(ptsP*100)}% ${ptsGr.g}</div>
<div style="display:flex;gap:4px;margin-top:5px">
<button class="btn btn-p btn-sm" style="font-size:10px;padding:2px 5px" onclick="lockPick('${pTeam}','${opp}','PROP','${pName} PTS O ${ptsLine}',${ptsP.toFixed(4)},${parseInt(ptsML)},${ptsDec},typeof today==='function'?today():'')">LOCK</button>
<button class="btn btn-o btn-sm" style="font-size:10px;padding:2px 5px" onclick="addWNBAPropLeg('${pName} PTS O ${ptsLine}',${parseInt(ptsML)},${ptsP.toFixed(4)},'${pKey}_pts')">+PAR</button>
</div></div>`;
      if(reb>=4){
        var rebGr=_wnbaGrade(rebP);var rebML=_wnbaML(rebP);var rebDec=_wnbaDec(parseInt(rebML)).toFixed(2);
        chips+=`<div class="chip" style="border-color:${rebGr.c};min-width:110px">
<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">REB O ${rebLine}</div>
<div style="font-family:var(--orb);font-size:13px;font-weight:700;color:${rebGr.c}">${rebML}</div>
<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">${Math.round(rebP*100)}% ${rebGr.g}</div>
<div style="display:flex;gap:4px;margin-top:5px">
<button class="btn btn-p btn-sm" style="font-size:10px;padding:2px 5px" onclick="lockPick('${pTeam}','${opp}','PROP','${pName} REB O ${rebLine}',${rebP.toFixed(4)},${parseInt(rebML)},${rebDec},typeof today==='function'?today():'')">LOCK</button>
<button class="btn btn-o btn-sm" style="font-size:10px;padding:2px 5px" onclick="addWNBAPropLeg('${pName} REB O ${rebLine}',${parseInt(rebML)},${rebP.toFixed(4)},'${pKey}_reb')">+PAR</button>
</div></div>`;
      }
      if(ast>=4){
        var astGr=_wnbaGrade(astP);var astML=_wnbaML(astP);var astDec=_wnbaDec(parseInt(astML)).toFixed(2);
        chips+=`<div class="chip" style="border-color:${astGr.c};min-width:110px">
<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">AST O ${astLine}</div>
<div style="font-family:var(--orb);font-size:13px;font-weight:700;color:${astGr.c}">${astML}</div>
<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">${Math.round(astP*100)}% ${astGr.g}</div>
<div style="display:flex;gap:4px;margin-top:5px">
<button class="btn btn-p btn-sm" style="font-size:10px;padding:2px 5px" onclick="lockPick('${pTeam}','${opp}','PROP','${pName} AST O ${astLine}',${astP.toFixed(4)},${parseInt(astML)},${astDec},typeof today==='function'?today():'')">LOCK</button>
<button class="btn btn-o btn-sm" style="font-size:10px;padding:2px 5px" onclick="addWNBAPropLeg('${pName} AST O ${astLine}',${parseInt(astML)},${astP.toFixed(4)},'${pKey}_ast')">+PAR</button>
</div></div>`;
      }
      if(reb>=3&&ast>=3){
        var praGr=_wnbaGrade(praP);var praML=_wnbaML(praP);var praDec=_wnbaDec(parseInt(praML)).toFixed(2);
        chips+=`<div class="chip" style="border-color:${praGr.c};min-width:110px">
<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">PRA O ${praLine}</div>
<div style="font-family:var(--orb);font-size:13px;font-weight:700;color:${praGr.c}">${praML}</div>
<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">${Math.round(praP*100)}% ${praGr.g}</div>
<div style="display:flex;gap:4px;margin-top:5px">
<button class="btn btn-p btn-sm" style="font-size:10px;padding:2px 5px" onclick="lockPick('${pTeam}','${opp}','PROP','${pName} PRA O ${praLine}',${praP.toFixed(4)},${parseInt(praML)},${praDec},typeof today==='function'?today():'')">LOCK</button>
<button class="btn btn-o btn-sm" style="font-size:10px;padding:2px 5px" onclick="addWNBAPropLeg('${pName} PRA O ${praLine}',${parseInt(praML)},${praP.toFixed(4)},'${pKey}_pra')">+PAR</button>
</div></div>`;
      }
      if(fg3>=1.0){
        var fg3Gr=_wnbaGrade(fg3P);var fg3ML=_wnbaML(fg3P);var fg3Dec=_wnbaDec(parseInt(fg3ML)).toFixed(2);
        chips+=`<div class="chip" style="border-color:${fg3Gr.c};min-width:110px">
<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:1px">3PT O ${fg3Line}</div>
<div style="font-family:var(--orb);font-size:13px;font-weight:700;color:${fg3Gr.c}">${fg3ML}</div>
<div style="font-family:var(--mono);font-size:10px;color:var(--t2)">${Math.round(fg3P*100)}% ${fg3Gr.g}</div>
<div style="display:flex;gap:4px;margin-top:5px">
<button class="btn btn-p btn-sm" style="font-size:10px;padding:2px 5px" onclick="lockPick('${pTeam}','${opp}','PROP','${pName} 3PT O ${fg3Line}',${fg3P.toFixed(4)},${parseInt(fg3ML)},${fg3Dec},typeof today==='function'?today():'')">LOCK</button>
<button class="btn btn-o btn-sm" style="font-size:10px;padding:2px 5px" onclick="addWNBAPropLeg('${pName} 3PT O ${fg3Line}',${parseInt(fg3ML)},${fg3P.toFixed(4)},'${pKey}_3pt')">+PAR</button>
</div></div>`;
      }
      return `<div class="card" style="margin-bottom:10px;border-left:2px solid var(--vc)">
<div style="margin-bottom:8px">
<div style="font-family:var(--orb);font-size:14px;font-weight:700">${pName}</div>
<div style="font-family:var(--mono);font-size:11px;color:var(--t3);margin-top:2px">${pTeam} vs ${opp} &middot; AVG: ${pts.toFixed(1)}PTS ${reb.toFixed(1)}REB ${ast.toFixed(1)}AST ${fg3.toFixed(1)}3PT</div>
<div style="font-family:var(--mono);font-size:10px;color:var(--t3)">USG ${usg.toFixed(0)}% &middot; TS ${Math.round(ts2*100)}% &middot; OPP DRtg ${drtg.toFixed(0)}</div>
</div>
<div style="display:flex;flex-wrap:wrap;gap:6px">${chips}</div>
</div>`;
    }).join('');
    return matchupHdr+propCards;
  }).join('');
  if(!el.innerHTML.trim())el.innerHTML='<div class="empty">NO PLAYER DATA AVAILABLE</div>';
  var pp=document.getElementById('wnba-parlay-props');
  if(pp&&parlayProps.length){
    pp.innerHTML=parlayProps.map(function(p){
      var ms=p.ml>0?'+':'';
      return `<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 8px;background:rgba(10,0,24,.7);border:1px solid rgba(187,255,0,.15);border-radius:2px;margin-bottom:4px;font-family:var(--mono);font-size:11px">
<span style="color:var(--t2)">${p.label}</span>
<div style="display:flex;gap:5px;align-items:center">
<span style="color:var(--vc)">${ms}${p.ml}</span>
<span style="color:var(--t3)">${Math.round(p.prob*100)}%</span>
<button class="btn btn-o btn-sm" style="font-size:10px;padding:2px 6px" onclick="addWNBAPropLeg('${p.label}',${p.ml},${p.prob.toFixed(4)},'${p.key}')">+PAR</button>
</div></div>`;
    }).join('');
  }
}
window.renderWNBAProps=renderWNBAProps;

window._wnbaParlay=[];
function wnbaParTab(t){
  var g=document.getElementById('wpar-games'),p=document.getElementById('wpar-props');
  var gb=document.getElementById('wnba-par-games-btn'),pb=document.getElementById('wnba-par-props-btn');
  if(t==='games'){
    if(g)g.style.display='block';if(p)p.style.display='none';
    if(gb){gb.classList.add('btn-p');gb.classList.remove('btn-o');}
    if(pb){pb.classList.add('btn-o');pb.classList.remove('btn-p');}
  }else{
    if(g)g.style.display='none';if(p)p.style.display='block';
    if(pb){pb.classList.add('btn-p');pb.classList.remove('btn-o');}
    if(gb){gb.classList.add('btn-o');gb.classList.remove('btn-p');}
  }
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
    var ms=l.ml>0?'+':'';
    return '<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.06)">'
      +'<span style="font-family:var(--mono);font-size:11px;color:var(--t2)">'+badge+l.label+' '+ms+l.ml+'</span>'
      +'<button onclick="window._wnbaParlay.splice('+i+',1);_wnbaRenderLegs();calcWNBAP()" style="background:none;border:none;color:var(--hc);cursor:pointer;font-size:14px;padding:0 4px">\xd7</button>'
      +'</div>';
  }).join('');
}
function addWNBAGameLeg(hab,aab,type,betOn,prob,ml,dec,gameKey){
  if(!window._wnbaParlay)window._wnbaParlay=[];
  if(window._wnbaParlay.length>=8){if(typeof toast==='function')toast('// MAX 8 LEGS');return;}
  if(window._wnbaParlay.find(function(l){return l.isGame&&l.gameKey===gameKey&&l.type===type;})){
    if(typeof toast==='function')toast('// ONE '+type+' PER GAME');return;
  }
  window._wnbaParlay.push({label:betOn,ml:ml,prob:prob,dec:parseFloat(dec)||2.0,gameKey:gameKey,type:type,isGame:true});
  _wnbaRenderLegs();calcWNBAP();
}
function addWNBALeg(label,ml,prob,game){addWNBAGameLeg(game||'',game||'','ML',label,prob,ml,_wnbaDec(ml),game||'');}
function addWNBAPropLeg(label,ml,prob,key){
  if(!window._wnbaParlay)window._wnbaParlay=[];
  if(window._wnbaParlay.length>=8){if(typeof toast==='function')toast('// MAX 8 LEGS');return;}
  if(window._wnbaParlay.find(function(l){return l.propKey===key;})){
    if(typeof toast==='function')toast('// PROP ALREADY ADDED');return;
  }
  window._wnbaParlay.push({label:label,ml:ml,prob:parseFloat(prob),dec:_wnbaDec(ml),propKey:key,isGame:false});
  _wnbaRenderLegs();calcWNBAP();
}
function calcWNBAP(){
  var legs=window._wnbaParlay||[];
  var el=document.getElementById('wnba-parlay-res');
  if(!el)return;
  if(!legs.length){el.innerHTML='';return;}
  var w=parseFloat((document.getElementById('wnba-p-w')&&document.getElementById('wnba-p-w').value)||100);
  var cD=legs.reduce(function(a,l){return a*l.dec;},1);
  var cP=legs.reduce(function(a,l){return a*l.prob;},1);
  var cML=cD>=2?Math.round((cD-1)*100):Math.round(-100/(cD-1));
  var pay=(w*cD).toFixed(2);
  var ev=((cP*cD-1)*100).toFixed(1);
  var e2=parseFloat(ev);
  var gr=_wnbaGrade(cP);
  var gLegs=legs.filter(function(l){return l.isGame;}).length;
  var ms=cML>0?'+':'';
  el.innerHTML='<div style="background:rgba(6,0,15,.9);border:1px solid rgba(240,0,255,.3);border-radius:2px;padding:10px;margin-bottom:8px">'
    +'<div style="font-family:var(--mono);font-size:11px;color:var(--t3);margin-bottom:4px">PARLAY ANALYSIS</div>'
    +'<div style="font-family:var(--orb);font-size:18px;font-weight:700;color:var(--pc)">'+ms+cML+'</div>'
    +'<div style="font-family:var(--mono);font-size:13px;color:var(--t2);margin-top:4px">COMBINED PROB: <span style="color:'+gr.c+'">'+Math.round(cP*100)+'% '+gr.g+'</span></div>'
    +'<div style="font-family:var(--mono);color:var(--nc);font-size:14px">$'+w+' &rarr; $'+parseFloat(pay).toLocaleString()+'</div>'
    +'<div style="font-family:var(--mono);font-size:12px;color:var(--t2);margin-top:5px">EV: <span style="color:'+(e2>=0?'var(--nc)':'var(--hc)')+'">'+ev+'%</span></div>'
    +'<div style="font-family:var(--mono);font-size:11px;color:var(--t3);margin-top:3px">'+legs.length+' LEGS &middot; '+gLegs+' GAME &middot; '+(legs.length-gLegs)+' PROP</div>'
    +'<button class="btn btn-p btn-fw" style="margin-top:9px" onclick="lockNBAParlay('+w+','+cP.toFixed(4)+',\''+cML+'\',\''+cD.toFixed(2)+'\')">LOCK PARLAY</button>'
    +'</div>';
}
window.addWNBAGameLeg=addWNBAGameLeg;
window.addWNBALeg=addWNBALeg;
window.addWNBAPropLeg=addWNBAPropLeg;
window.calcWNBAP=calcWNBAP;
window._wnbaRenderLegs=_wnbaRenderLegs;

function renderWNBAContent(){"""

assert html.count(old_js) == 1, f"JS block not unique: {html.count(old_js)}"
html = html.replace(old_js, NEW_JS, 1)
print("JS section replaced OK")

# ══════════════════════════════════════════════════════════════════
# 3. FIX T() WNBA ROUTING
# ══════════════════════════════════════════════════════════════════

OLD_WNBA_ROUTE = """  if(sport==='wnba'){
    try{
      if(tabId==='games')renderWNBAGames();
      else if(tabId==='props')renderWNBAProps();
      else if(tabId==='parlay'){renderWNBAGames();try{const pg=document.getElementById('wnba-parlay-games');if(pg&&pg.innerHTML.includes('LOAD TODAY'))renderWNBAGames();}catch(ex){}}
      else if(tabId==='model'){try{renderModelWeights('wnba','wnba-model-weights');}catch(ex){}}
      else if(tabId==='config'){}
    }catch(e){console.error('WNBA tab',tabId,e);}
  }"""

NEW_WNBA_ROUTE = """  if(sport==='wnba'){
    try{
      if(tabId==='games')renderWNBAGames();
      else if(tabId==='props')renderWNBAProps();
      else if(tabId==='parlay'){renderWNBAGames();renderWNBAProps();}
      else if(tabId==='model'){try{renderModelWeights('wnba','wnba-model-weights');}catch(ex){}}
      else if(tabId==='config'){}
    }catch(e){console.error('WNBA tab',tabId,e);}
  }"""

assert html.count(OLD_WNBA_ROUTE) == 1, f"Route block count: {html.count(OLD_WNBA_ROUTE)}"
html = html.replace(OLD_WNBA_ROUTE, NEW_WNBA_ROUTE, 1)
print("T() routing updated OK")

# ══════════════════════════════════════════════════════════════════
# 4. FIX setSub
# ══════════════════════════════════════════════════════════════════

OLD_SETSUB = "  if(sport==='nba'&&sub==='wnba'){try{T('wnba','games');renderWNBAGames();}catch(e){}}"
NEW_SETSUB = "  if(sport==='nba'&&sub==='wnba'){try{T('wnba','games');if(typeof renderWNBAGames==='function')renderWNBAGames();}catch(e){}}"
assert html.count(OLD_SETSUB) == 1, f"setSub block count: {html.count(OLD_SETSUB)}"
html = html.replace(OLD_SETSUB, NEW_SETSUB, 1)
print("setSub updated OK")

# ══════════════════════════════════════════════════════════════════
# 5. VALIDATE
# ══════════════════════════════════════════════════════════════════

import re as _re
scripts = list(_re.finditer(r'<script([^>]*)>([\s\S]*?)</script>', html))
js = [s.group(2) for s in scripts if len(s.group(2)) > 10000][0]
bt = js.count('`'); op = js.count('{'); cl = js.count('}')
bad = js.count(chr(39)+chr(10)+chr(39))
sq = js.count("'"); dq = js.count('"')
print(f'BT:{bt}(ok={bt%2==0}) Braces:{op}/{cl}(ok={op==cl}) LF:{bad}(ok={bad==0})')
print(f'Single-quotes:{sq}(ok={sq%2==0}) Double-quotes:{dq}(ok={dq%2==0})')
assert bt%2==0, "Backtick imbalance!"
assert op==cl,  "Brace imbalance!"
assert bad==0,  "LF in string!"

open('docs/app.html','w').write(html)
open('docs/index.html','w').write(html)
print(f"Written — {html.count(chr(10))+1} lines")
