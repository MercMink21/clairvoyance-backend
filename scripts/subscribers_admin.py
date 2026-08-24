#!/usr/bin/env python3
"""
subscribers_admin.py — local-only web UI for viewing/editing the paid
mailing list (data/subscribers.json), a point-and-click alternative to
manage_subscribers.py for anyone who'd rather click than type.

Run:
  python3 scripts/subscribers_admin.py
Then open http://127.0.0.1:8899, or from a phone on the same Wi-Fi,
http://<this Mac's LAN IP>:8899 (find it with `ipconfig getifaddr en0`).

Binds to 0.0.0.0 -- reachable from any device on the same network, with
NO auth. That's a deliberate choice for home-network convenience (so a
phone can load and bookmark it), not an oversight -- do not run this on
a network you don't trust every device on. Edits write straight to
data/subscribers.json on disk; nothing here talks to git, Supabase, or
email. After editing, the usual workflow still applies: the file has to
be committed and pushed for the change to actually reach the GitHub
Actions lock/email runs -- this tool only edits your local working copy,
same as manage_subscribers.py does.
"""
from __future__ import annotations
import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _subscribers import (
    PRODUCTS, add_subscriber, remove_subscriber, active_subscribers,
    products_for_email, analytics_summary, EXPIRY_DAYS,
)

PORT = 8899
# Same icon the main app uses for its own iOS home-screen add (see
# docs/app.html's apple-touch-icon link) -- so this admin page's Home
# Screen icon matches the real app's instead of Safari's generic favicon
# screenshot fallback.
ICON_PATH = Path(__file__).resolve().parent.parent / "docs" / "icon-1080.png"

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="CLAIRVOYANCE">
<meta name="theme-color" content="#020008">
<link rel="apple-touch-icon" sizes="1080x1080" href="/icon-1080.png">
<title>Clairvoyance — Subscribers</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&family=Exo+2:wght@300;400;600;700;800&display=swap" rel="stylesheet">
<style>
:root{
  --void:#010006;--b1:#04000c;--b2:#080014;--b3:#0c001e;--b4:#10002a;
  --w:#1a0035;--w2:#3a0065;--w3:#4e0090;
  --nc:#00f0ff;--nc2:#00c8e0;--n3:rgba(0,240,255,.12);
  --hc:#ff2090;--h2:#dd0070;--h3:rgba(255,32,144,.12);
  --vc:#bbff00;--v2:#99dd00;--v3:rgba(187,255,0,.10);
  --ic:#6690ff;--i2:#3360ee;--i3:rgba(102,144,255,.12);
  --pc:#f000ff;--p2:#f000ff;--p3:rgba(240,0,255,.14);
  --gc:#ffdd00;--g2:#ddaa00;--g3:rgba(255,221,0,.12);
  --mc:#ff7700;--m3:rgba(255,119,0,.12);
  --rc:#00ffaa;--r3:rgba(0,255,170,.12);
  --t:#f0f6ff;--t2:#c8d8f0;--t3:#9aabb8;
  --orb:'Orbitron',sans-serif;--mono:'Share Tech Mono',monospace;--ex:'Exo 2',sans-serif;
}
*{margin:0;padding:0;box-sizing:border-box;max-width:100%}
html{-webkit-text-size-adjust:100%}
body{
  font-family:var(--ex);font-size:16px;color:var(--t);background-color:#0d0d0d;
  background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.04) 0px,rgba(255,255,255,.04) 1px,transparent 1px,transparent 50%),repeating-linear-gradient(-45deg,rgba(255,255,255,.04) 0px,rgba(255,255,255,.04) 1px,transparent 1px,transparent 50%),repeating-linear-gradient(0deg,rgba(0,0,0,.25) 0px,rgba(0,0,0,.25) 1px,transparent 1px,transparent 22px),repeating-linear-gradient(90deg,rgba(0,0,0,.25) 0px,rgba(0,0,0,.25) 1px,transparent 1px,transparent 22px),radial-gradient(ellipse at 0% 0%,rgba(240,0,255,.10) 0%,transparent 50%),radial-gradient(ellipse at 100% 0%,rgba(77,121,255,.08) 0%,transparent 45%),radial-gradient(ellipse at 50% 100%,rgba(0,240,255,.06) 0%,transparent 45%);
  background-size:22px 22px,22px 22px,22px 22px,22px 22px,100% 100%,100% 100%,100% 100%;
  background-attachment:fixed;
  min-height:100vh;padding:30px 20px 70px;overflow-x:hidden;
}
.wrap{max-width:880px;margin:0 auto}
.hdr{text-align:center;margin-bottom:30px}
.logo{font-family:var(--orb);font-weight:900;font-size:clamp(24px,6vw,36px);letter-spacing:6px;
  color:#f000ff;text-shadow:0 0 10px #f000ff,0 0 28px rgba(240,0,255,.75),0 0 60px rgba(240,0,255,.35);
  animation:logoPulse 4s ease-in-out infinite}
@keyframes logoPulse{0%,100%{text-shadow:0 0 10px #f000ff,0 0 28px rgba(240,0,255,.75),0 0 60px rgba(240,0,255,.35)}50%{text-shadow:0 0 16px #f000ff,0 0 42px rgba(240,0,255,.9),0 0 90px rgba(240,0,255,.55)}}
.subtitle{font-family:var(--mono);font-size:14px;letter-spacing:3px;color:var(--nc);text-transform:uppercase;
  margin-top:10px;text-shadow:0 0 8px rgba(0,240,255,.4)}
.card{
  background:rgba(10,4,22,0.92);backdrop-filter:blur(2px);border:1px solid rgba(77,40,120,.55);
  box-shadow:0 0 8px rgba(240,0,255,.05),inset 0 0 8px rgba(0,0,0,.3);border-radius:3px;
  padding:20px;margin-bottom:20px;position:relative;overflow:hidden;
  clip-path:polygon(0 0,calc(100% - 12px) 0,100% 12px,100% 100%,12px 100%,0 calc(100% - 12px));
}
.sh{font-family:var(--orb);font-size:19px;font-weight:700;letter-spacing:2px;text-transform:uppercase;
  margin:0 0 16px;padding-bottom:8px;border-bottom:1px solid rgba(240,0,255,.45);
  text-shadow:0 0 8px rgba(240,0,255,.4);color:var(--pc)}
label{display:block;font-family:var(--mono);font-size:13px;letter-spacing:1.5px;color:var(--t3);
  text-transform:uppercase;margin-bottom:7px}
input[type=email]{
  background:var(--b1);border:1px solid var(--w2);color:var(--t);border-radius:2px;padding:12px;
  font-family:var(--mono);font-size:16px;width:100%;box-sizing:border-box;transition:border-color .15s;
}
input[type=email]:focus{outline:none;border-color:var(--pc);box-shadow:0 0 8px rgba(240,0,255,.25)}
.row{display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap;align-items:flex-end}
.row > div{flex:1;min-width:200px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.chip{
  font-family:var(--mono);font-size:14px;letter-spacing:1px;text-transform:uppercase;
  background:transparent;border:1px solid var(--w2);color:var(--t3);border-radius:2px;
  padding:7px 13px;cursor:pointer;user-select:none;transition:all .15s;
}
.chip.on{background:var(--p3);border-color:var(--pc);color:var(--pc);text-shadow:0 0 8px rgba(240,0,255,.5)}
.btn{
  display:inline-flex;align-items:center;justify-content:center;gap:4px;font-family:var(--mono);
  letter-spacing:1.5px;text-transform:uppercase;border:none;cursor:pointer;border-radius:2px;
  transition:all .15s;clip-path:polygon(0 0,calc(100% - 6px) 0,100% 6px,100% 100%,6px 100%,0 calc(100% - 6px));
  padding:12px 22px;font-size:15px;font-weight:700;
}
.btn:active{filter:brightness(1.25);transform:scale(.97)}
.btn-p{background:linear-gradient(135deg,var(--pc),var(--ic));color:#fff}
.btn-n{background:linear-gradient(135deg,var(--nc),var(--ic));color:#000}
.btn-h{background:var(--hc);color:#fff;padding:6px 12px;font-size:13px}
.msg{font-family:var(--mono);font-size:14px;margin-top:10px;min-height:16px;letter-spacing:.5px}
.msg.ok{color:var(--rc)}
.msg.err{color:var(--hc)}
.tablewrap{width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;min-width:420px;border-collapse:collapse;font-family:var(--mono);font-size:15px}
th{text-align:left;color:var(--t3);font-weight:400;letter-spacing:1px;text-transform:uppercase;
  font-size:12px;padding:8px;border-bottom:1px solid rgba(240,0,255,.25);white-space:nowrap}
td{padding:9px 8px;border-bottom:1px solid rgba(255,255,255,.06);color:var(--t2);white-space:nowrap}
.empty{color:var(--t3);font-family:var(--mono);font-size:14px;padding:6px 8px}
.days{color:var(--gc);font-weight:700}
.days.low{color:var(--hc)}
.expired-note{font-family:var(--mono);font-size:13px;color:var(--t3);margin-top:10px;letter-spacing:.5px}
.count-note{font-family:var(--mono);font-size:13px;color:var(--t3);letter-spacing:.5px;margin:-6px 0 14px}
.emlist{display:flex;flex-direction:column}
.emrow{padding:14px 0;border-bottom:1px solid rgba(255,255,255,.06)}
.emrow:last-child{border-bottom:none;padding-bottom:0}
.emaddr{font-family:var(--mono);font-size:17px;color:var(--t);margin-bottom:9px;word-break:break-all}
.ptags{display:flex;flex-wrap:wrap;gap:8px}
.ptag{
  display:inline-flex;align-items:center;gap:8px;font-family:var(--mono);font-size:13px;
  letter-spacing:1px;text-transform:uppercase;background:var(--p3);border:1px solid var(--pc);
  color:var(--pc);border-radius:2px;padding:5px 10px;
}
.ptag.low{background:var(--h3);border-color:var(--hc);color:var(--hc)}
.ptag .x{cursor:pointer;opacity:.6;font-family:var(--ex);font-size:15px;line-height:1;transition:opacity .15s}
.ptag .x:hover{opacity:1}
.prodblock{margin-bottom:20px}
.prodblock:last-child{margin-bottom:0}
.prodblock h3{font-family:var(--orb);font-size:16px;color:var(--nc);margin:0 0 9px;
  text-transform:uppercase;letter-spacing:2px}
.priceval{color:var(--gc);font-weight:700}
.priceavg{color:var(--t3);font-size:13px}
.pricebest{background:var(--p3);border-left:2px solid var(--pc)}
.price-note{font-family:var(--mono);font-size:12px;color:var(--t3);letter-spacing:.5px;margin:-8px 0 14px}

.stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin-bottom:20px}
.stat{background:var(--b1);border:1px solid var(--w2);border-radius:2px;padding:14px}
.stat-val{font-family:var(--orb);font-size:30px;font-weight:700;color:var(--nc);text-shadow:0 0 10px rgba(0,240,255,.4)}
.stat-val.money{color:var(--gc);text-shadow:0 0 10px rgba(255,221,0,.4)}
.stat-lbl{font-family:var(--mono);font-size:12px;letter-spacing:1.5px;color:var(--t3);text-transform:uppercase;margin-top:5px}
.stat-note{font-family:var(--mono);font-size:11px;color:var(--t3);margin-top:2px}
.analytics-sub{font-family:var(--orb);font-size:15px;letter-spacing:1.5px;text-transform:uppercase;color:var(--t2);
  margin:22px 0 11px}
.analytics-sub:first-child{margin-top:0}
.bar-row{display:flex;align-items:center;gap:10px;margin-bottom:8px;font-family:var(--mono);font-size:14px}
.bar-label{width:75px;color:var(--t3);text-transform:uppercase;flex-shrink:0}
.bar-track{flex:1;background:var(--b1);border-radius:2px;height:16px;overflow:hidden;border:1px solid var(--w2)}
.bar-fill{height:100%;background:linear-gradient(90deg,var(--pc),var(--ic));border-radius:2px}
.bar-count{width:26px;text-align:right;color:var(--t2);flex-shrink:0}
.activity-row{display:flex;justify-content:space-between;font-family:var(--mono);font-size:15px;
  padding:7px 0;border-bottom:1px solid rgba(255,255,255,.06)}
.activity-row:last-child{border-bottom:none}
.activity-row span:last-child{color:var(--t2);font-weight:700}
.tracking-note{font-family:var(--mono);font-size:12px;color:var(--t3);margin-bottom:16px}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <div class="logo">CLAIRVOYANCE</div>
    <div class="subtitle">SUBSCRIBER ACCESS</div>
  </div>

  <div class="card">
    <div class="sh">Analytics</div>
    <div class="tracking-note" id="trackingNote"></div>
    <div class="stat-grid" id="statGrid"></div>
    <div class="analytics-sub">Active by Product</div>
    <div id="barChart"></div>
    <div class="analytics-sub">Activity (7d / 30d)</div>
    <div id="activityBox"></div>
    <div class="analytics-sub" id="expiringHdr" style="display:none">Expiring Soon (&le;5 days)</div>
    <div id="expiringBox"></div>
  </div>

  <div class="card">
    <div class="sh">Add / Renew</div>
    <div class="row">
      <div>
        <label>Email</label>
        <input type="email" id="addEmail" placeholder="someone@example.com">
      </div>
    </div>
    <label>Products</label>
    <div class="chips" id="addChips"></div>
    <button class="btn btn-p" onclick="doAdd()">Add / Renew</button>
    <div class="msg" id="addMsg"></div>
  </div>

  <div class="card">
    <div class="sh">Check an Email</div>
    <div class="row">
      <div>
        <input type="email" id="checkEmail" placeholder="someone@example.com">
      </div>
      <button class="btn btn-n" onclick="doCheck()" style="flex:0 0 auto">Check</button>
    </div>
    <div id="checkResult"></div>
  </div>

  <div class="card">
    <div class="sh">All Active Subscribers</div>
    <div class="count-note" id="countNote"></div>
    <div id="allList"></div>
  </div>

  <div class="card">
    <div class="sh">Subscribers by Product</div>
    <div id="byProductList"></div>
  </div>

  <div class="card">
    <div class="sh">Pricing</div>
    <div class="price-note" id="priceNote">All access windows last 30 days from the date added or renewed.</div>
    <div class="tablewrap">
      <table>
        <tr><th>Sports</th><th>Price</th><th>Avg / sport</th></tr>
        <tr><td>1</td><td class="priceval">$20</td><td class="priceavg">$20.00</td></tr>
        <tr><td>2</td><td class="priceval">$30</td><td class="priceavg">$15.00</td></tr>
        <tr><td>3</td><td class="priceval">$40</td><td class="priceavg">$13.33</td></tr>
        <tr><td>4</td><td class="priceval">$45</td><td class="priceavg">$11.25</td></tr>
        <tr><td>5</td><td class="priceval">$55</td><td class="priceavg">$11.00</td></tr>
        <tr><td>6</td><td class="priceval">$60</td><td class="priceavg">$10.00</td></tr>
        <tr><td>7</td><td class="priceval">$70</td><td class="priceavg">$10.00</td></tr>
        <tr class="pricebest"><td>8 (ALL ACCESS)</td><td class="priceval">$75</td><td class="priceavg">$9.38</td></tr>
      </table>
    </div>
  </div>
</div>

<script>
let PRODUCTS = [];
let selectedProducts = new Set();

async function loadAll() {
  const res = await fetch('/api/subscribers');
  const data = await res.json();
  PRODUCTS = data.products;
  document.getElementById('priceNote').textContent =
    'All access windows last ' + data.expiry_days + ' days from the date added or renewed.';
  renderChips();
  renderAllList(data.data);
  renderByProduct(data.data);
  loadAnalytics();
}

async function loadAnalytics() {
  const res = await fetch('/api/analytics');
  const a = await res.json();

  const trackEl = document.getElementById('trackingNote');
  trackEl.textContent = a.events_since
    ? 'Activity tracked since ' + a.events_since.slice(0, 10) + ' · estimated revenue is not a real payment ledger'
    : 'No activity tracked yet -- signup/renewal/removal trends start accumulating from today · estimated revenue is not a real payment ledger';

  document.getElementById('statGrid').innerHTML = `
    <div class="stat"><div class="stat-val">${a.active_emails}</div><div class="stat-lbl">Active Subscribers</div></div>
    <div class="stat"><div class="stat-val">${a.active_subscriptions}</div><div class="stat-lbl">Active Subscriptions</div></div>
    <div class="stat"><div class="stat-val money">$${a.estimated_mrr}</div><div class="stat-lbl">Est. 30-Day Revenue</div></div>
    <div class="stat"><div class="stat-val">${a.renewal_rate_30d === null ? '—' : a.renewal_rate_30d + '%'}</div><div class="stat-lbl">Renewal Rate (30d)</div><div class="stat-note">${a.renewal_rate_30d === null ? 'no renewals/removes yet' : ''}</div></div>
  `;

  const maxCount = Math.max(1, ...Object.values(a.per_product_counts));
  document.getElementById('barChart').innerHTML = PRODUCTS.map(p => {
    const n = a.per_product_counts[p] || 0;
    const pct = Math.round((n / maxCount) * 100);
    return `<div class="bar-row">
      <div class="bar-label">${p}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
      <div class="bar-count">${n}</div>
    </div>`;
  }).join('');

  document.getElementById('activityBox').innerHTML = `
    <div class="activity-row"><span>New signups</span><span>${a.window_7d.add} / ${a.window_30d.add}</span></div>
    <div class="activity-row"><span>Renewals</span><span>${a.window_7d.renew} / ${a.window_30d.renew}</span></div>
    <div class="activity-row"><span>Removed</span><span>${a.window_7d.remove} / ${a.window_30d.remove}</span></div>
  `;

  const expHdr = document.getElementById('expiringHdr');
  const expBox = document.getElementById('expiringBox');
  if (a.expiring_soon.length) {
    expHdr.style.display = '';
    expBox.innerHTML = a.expiring_soon.map(r =>
      `<div class="activity-row"><span>${escapeHtml(r.email)} · ${r.product.toUpperCase()}</span><span class="${daysClass(r.days_left)}">${r.days_left}d</span></div>`
    ).join('');
  } else {
    expHdr.style.display = 'none';
    expBox.innerHTML = '';
  }
}

function renderChips() {
  const el = document.getElementById('addChips');
  el.innerHTML = PRODUCTS.map(p =>
    `<span class="chip${selectedProducts.has(p)?' on':''}" onclick="toggleChip('${p}')">${p.toUpperCase()}</span>`
  ).join('');
}

const daysClass = d => 'days' + (d <= 5 ? ' low' : '');

function toggleChip(p) {
  if (selectedProducts.has(p)) selectedProducts.delete(p); else selectedProducts.add(p);
  renderChips();
}

function groupByEmail(data) {
  const byEmail = {};
  for (const p of PRODUCTS) {
    for (const r of (data[p] || [])) {
      (byEmail[r.email] = byEmail[r.email] || []).push({ product: p, days_left: r.days_left, added: r.added });
    }
  }
  return Object.keys(byEmail).sort().map(email => ({
    email,
    products: byEmail[email].sort((a, b) => a.days_left - b.days_left),
  }));
}

function renderAllList(data) {
  const el = document.getElementById('allList');
  const grouped = groupByEmail(data);
  const noteEl = document.getElementById('countNote');
  if (!grouped.length) {
    el.innerHTML = '<div class="empty">No active subscribers.</div>';
    noteEl.textContent = '';
    return;
  }
  const totalSubs = grouped.reduce((n, g) => n + g.products.length, 0);
  noteEl.textContent = `${grouped.length} email${grouped.length === 1 ? '' : 's'} · ${totalSubs} active subscription${totalSubs === 1 ? '' : 's'}`;
  el.innerHTML = '<div class="emlist">' + grouped.map(g => `
    <div class="emrow">
      <div class="emaddr">${escapeHtml(g.email)}</div>
      <div class="ptags">${g.products.map(p => `
        <span class="ptag${p.days_left <= 5 ? ' low' : ''}">${p.product.toUpperCase()} · ${p.days_left}D
          <span class="x" onclick="doRemove('${p.product}','${escapeAttr(g.email)}')" title="Remove ${p.product}">×</span>
        </span>`).join('')}</div>
    </div>`).join('') + '</div>';
}

function renderByProduct(data) {
  const el = document.getElementById('byProductList');
  el.innerHTML = PRODUCTS.map(p => {
    const rows = data[p] || [];
    const body = rows.length
      ? `<div class="tablewrap"><table><tr><th>Email</th><th>Days left</th><th>Added</th><th></th></tr>` +
        rows.map(r => `<tr>
          <td>${escapeHtml(r.email)}</td>
          <td class="${daysClass(r.days_left)}">${r.days_left}</td>
          <td>${r.added.slice(0,10)}</td>
          <td><button class="btn btn-h" onclick="doRemove('${p}','${escapeAttr(r.email)}')">Remove</button></td>
        </tr>`).join('') + `</table></div>`
      : `<div class="empty">no active subscribers</div>`;
    return `<div class="prodblock"><h3>${p} (${rows.length})</h3>${body}</div>`;
  }).join('');
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function escapeAttr(s) { return s.replace(/'/g, "\\'"); }

async function doAdd() {
  const email = document.getElementById('addEmail').value.trim();
  const msgEl = document.getElementById('addMsg');
  if (!email || selectedProducts.size === 0) {
    msgEl.className = 'msg err';
    msgEl.textContent = 'Enter an email and pick at least one product.';
    return;
  }
  const results = [];
  for (const product of selectedProducts) {
    const res = await fetch('/api/add', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({product, email})
    });
    const j = await res.json();
    results.push(j.message || j.error);
  }
  msgEl.className = 'msg ok';
  msgEl.textContent = results.join(' · ');
  selectedProducts.clear();
  document.getElementById('addEmail').value = '';
  renderChips();
  loadAll();
}

async function doRemove(product, email) {
  await fetch('/api/remove', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({product, email})
  });
  loadAll();
}

async function doCheck() {
  const email = document.getElementById('checkEmail').value.trim();
  const el = document.getElementById('checkResult');
  if (!email) { el.innerHTML = ''; return; }
  const res = await fetch('/api/check?email=' + encodeURIComponent(email));
  const j = await res.json();
  if (!j.rows.length) { el.innerHTML = `<div class="empty">Not on any product's list.</div>`; return; }
  const active = j.rows.filter(r => r.active);
  const expired = j.rows.filter(r => !r.active);
  let html = '';
  if (active.length) {
    html += '<div class="tablewrap"><table><tr><th>Product</th><th>Days left</th><th>Added</th></tr>' +
      active.map(r => `<tr><td>${r.product}</td><td class="${daysClass(r.days_left)}">${r.days_left}</td><td>${r.added.slice(0,10)}</td></tr>`).join('') +
      '</table></div>';
  } else {
    html += '<div class="empty">No active subscriptions.</div>';
  }
  if (expired.length) {
    html += '<div class="expired-note">Expired: ' + expired.map(r => r.product).join(', ') + '</div>';
  }
  el.innerHTML = html;
}

loadAll();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html: str):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._html(PAGE)
        elif parsed.path == "/icon-1080.png":
            try:
                body = ICON_PATH.read_bytes()
            except Exception:
                self._json({"error": "icon not found"}, 404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/api/subscribers":
            self._json({
                "products": list(PRODUCTS),
                "data": {p: active_subscribers(p) for p in PRODUCTS},
                "expiry_days": EXPIRY_DAYS,
            })
        elif parsed.path == "/api/check":
            email = parse_qs(parsed.query).get("email", [""])[0]
            self._json({"email": email, "rows": products_for_email(email)})
        elif parsed.path == "/api/analytics":
            self._json(analytics_summary())
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._json({"error": "bad json"}, 400)
            return
        product = body.get("product")
        email = (body.get("email") or "").strip()
        parsed = urlparse(self.path)
        if parsed.path == "/api/add":
            if product not in PRODUCTS or not email:
                self._json({"error": "invalid product/email"}, 400)
                return
            self._json({"ok": True, "message": add_subscriber(product, email)})
        elif parsed.path == "/api/remove":
            if product not in PRODUCTS or not email:
                self._json({"error": "invalid product/email"}, 400)
                return
            self._json({"ok": True, "message": remove_subscriber(product, email)})
        else:
            self._json({"error": "not found"}, 404)


def main() -> None:
    url = f"http://127.0.0.1:{PORT}"
    try:
        # 0.0.0.0, not 127.0.0.1 -- deliberately reachable from other
        # devices on the same network (e.g. a phone), see the module
        # docstring for the no-auth trade-off that comes with that.
        server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    except OSError:
        # Most likely cause: the LaunchAgent (see setup_launch_agent.sh) is
        # already running this in the background -- that's fine, the
        # bookmark still works. Only a real problem if nothing answers at
        # this URL at all.
        print(f"Port {PORT} is already in use -- probably already running "
              f"at {url}. If that URL doesn't load, something else has "
              f"the port; check with `lsof -i :{PORT}`.")
        return
    print(f"Subscriber admin running at {url} (and on the LAN)  (Ctrl+C to stop)")
    if "--open" in sys.argv:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
