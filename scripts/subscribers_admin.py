#!/usr/bin/env python3
"""
subscribers_admin.py — local-only web UI for viewing/editing the paid
mailing list (data/subscribers.json), a point-and-click alternative to
manage_subscribers.py for anyone who'd rather click than type.

Run:
  python3 scripts/subscribers_admin.py
Then open http://127.0.0.1:8899 (opens automatically).

Binds to 127.0.0.1 only -- never reachable from the network, no auth
needed. Edits write straight to data/subscribers.json on disk; nothing
here talks to git, Supabase, or email. After editing, the usual workflow
still applies: the file has to be committed and pushed for the change
to actually reach the GitHub Actions lock/email runs -- this tool only
edits your local working copy, same as manage_subscribers.py does.
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
    products_for_email, EXPIRY_DAYS,
)

PORT = 8899

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
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
*{margin:0;padding:0;box-sizing:border-box}
body{
  font-family:var(--ex);color:var(--t);background-color:#0d0d0d;
  background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.04) 0px,rgba(255,255,255,.04) 1px,transparent 1px,transparent 50%),repeating-linear-gradient(-45deg,rgba(255,255,255,.04) 0px,rgba(255,255,255,.04) 1px,transparent 1px,transparent 50%),repeating-linear-gradient(0deg,rgba(0,0,0,.25) 0px,rgba(0,0,0,.25) 1px,transparent 1px,transparent 22px),repeating-linear-gradient(90deg,rgba(0,0,0,.25) 0px,rgba(0,0,0,.25) 1px,transparent 1px,transparent 22px),radial-gradient(ellipse at 0% 0%,rgba(240,0,255,.10) 0%,transparent 50%),radial-gradient(ellipse at 100% 0%,rgba(77,121,255,.08) 0%,transparent 45%),radial-gradient(ellipse at 50% 100%,rgba(0,240,255,.06) 0%,transparent 45%);
  background-size:22px 22px,22px 22px,22px 22px,22px 22px,100% 100%,100% 100%,100% 100%;
  background-attachment:fixed;
  min-height:100vh;padding:30px 20px 70px;
}
.wrap{max-width:880px;margin:0 auto}
.hdr{text-align:center;margin-bottom:30px}
.logo{font-family:var(--orb);font-weight:900;font-size:clamp(22px,4.5vw,34px);letter-spacing:6px;
  color:#f000ff;text-shadow:0 0 10px #f000ff,0 0 28px rgba(240,0,255,.75),0 0 60px rgba(240,0,255,.35);
  animation:logoPulse 4s ease-in-out infinite}
@keyframes logoPulse{0%,100%{text-shadow:0 0 10px #f000ff,0 0 28px rgba(240,0,255,.75),0 0 60px rgba(240,0,255,.35)}50%{text-shadow:0 0 16px #f000ff,0 0 42px rgba(240,0,255,.9),0 0 90px rgba(240,0,255,.55)}}
.subtitle{font-family:var(--mono);font-size:12px;letter-spacing:3px;color:var(--t3);text-transform:uppercase;margin-top:8px}
.card{
  background:rgba(10,4,22,0.92);backdrop-filter:blur(2px);border:1px solid rgba(77,40,120,.55);
  box-shadow:0 0 8px rgba(240,0,255,.05),inset 0 0 8px rgba(0,0,0,.3);border-radius:3px;
  padding:18px 20px;margin-bottom:20px;position:relative;overflow:hidden;
  clip-path:polygon(0 0,calc(100% - 12px) 0,100% 12px,100% 100%,12px 100%,0 calc(100% - 12px));
}
.sh{font-family:var(--orb);font-size:16px;font-weight:700;letter-spacing:2px;text-transform:uppercase;
  margin:0 0 14px;padding-bottom:7px;border-bottom:1px solid rgba(240,0,255,.45);
  text-shadow:0 0 8px rgba(240,0,255,.3);color:var(--t)}
.sh .n{color:var(--nc)}
label{display:block;font-family:var(--mono);font-size:11px;letter-spacing:1.5px;color:var(--t3);
  text-transform:uppercase;margin-bottom:6px}
input[type=email]{
  background:var(--b1);border:1px solid var(--w2);color:var(--t);border-radius:2px;padding:10px 12px;
  font-family:var(--mono);font-size:14px;width:100%;box-sizing:border-box;transition:border-color .15s;
}
input[type=email]:focus{outline:none;border-color:var(--pc);box-shadow:0 0 8px rgba(240,0,255,.25)}
.row{display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap;align-items:flex-end}
.row > div{flex:1;min-width:200px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.chip{
  font-family:var(--mono);font-size:12px;letter-spacing:1px;text-transform:uppercase;
  background:transparent;border:1px solid var(--w2);color:var(--t3);border-radius:2px;
  padding:6px 12px;cursor:pointer;user-select:none;transition:all .15s;
}
.chip.on{background:var(--p3);border-color:var(--pc);color:var(--pc);text-shadow:0 0 8px rgba(240,0,255,.5)}
.btn{
  display:inline-flex;align-items:center;justify-content:center;gap:4px;font-family:var(--mono);
  letter-spacing:1.5px;text-transform:uppercase;border:none;cursor:pointer;border-radius:2px;
  transition:all .15s;clip-path:polygon(0 0,calc(100% - 6px) 0,100% 6px,100% 100%,6px 100%,0 calc(100% - 6px));
  padding:10px 20px;font-size:13px;font-weight:700;
}
.btn:active{filter:brightness(1.25);transform:scale(.97)}
.btn-p{background:linear-gradient(135deg,var(--pc),var(--ic));color:#fff}
.btn-n{background:linear-gradient(135deg,var(--nc),var(--ic));color:#000}
.btn-h{background:var(--hc);color:#fff;padding:5px 10px;font-size:11px}
.msg{font-family:var(--mono);font-size:12px;margin-top:10px;min-height:14px;letter-spacing:.5px}
.msg.ok{color:var(--rc)}
.msg.err{color:var(--hc)}
table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:13px}
th{text-align:left;color:var(--t3);font-weight:400;letter-spacing:1px;text-transform:uppercase;
  font-size:11px;padding:7px 8px;border-bottom:1px solid rgba(240,0,255,.25)}
td{padding:8px;border-bottom:1px solid rgba(255,255,255,.06);color:var(--t2)}
.prodblock{margin-bottom:18px}
.prodblock h3{font-family:var(--orb);font-size:14px;color:var(--nc);margin:0 0 8px;
  text-transform:uppercase;letter-spacing:2px}
.empty{color:var(--t3);font-family:var(--mono);font-size:12px;padding:6px 8px}
.days{color:var(--gc);font-weight:700}
.days.low{color:var(--hc)}
.expired-note{font-family:var(--mono);font-size:11px;color:var(--t3);margin-top:10px;letter-spacing:.5px}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <div class="logo">CLAIRVOYANCE</div>
    <div class="subtitle" id="expiryNote">SUBSCRIBER ACCESS · 30-DAY WINDOWS</div>
  </div>

  <div class="card">
    <div class="sh">Add <span class="n">/</span> Renew</div>
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
    <div class="sh">Check <span class="n">an</span> Email</div>
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
    <div id="allList"></div>
  </div>
</div>

<script>
let PRODUCTS = [];
let selectedProducts = new Set();

async function loadAll() {
  const res = await fetch('/api/subscribers');
  const data = await res.json();
  PRODUCTS = data.products;
  document.getElementById('expiryNote').textContent =
    'SUBSCRIBER ACCESS · ' + data.expiry_days + '-DAY WINDOWS';
  renderChips();
  renderAllList(data.data);
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

function renderAllList(data) {
  const el = document.getElementById('allList');
  el.innerHTML = PRODUCTS.map(p => {
    const rows = data[p] || [];
    const body = rows.length
      ? `<table><tr><th>Email</th><th>Days left</th><th>Added</th><th></th></tr>` +
        rows.map(r => `<tr>
          <td>${escapeHtml(r.email)}</td>
          <td class="${daysClass(r.days_left)}">${r.days_left}</td>
          <td>${r.added.slice(0,10)}</td>
          <td><button class="btn btn-h" onclick="doRemove('${p}','${escapeAttr(r.email)}')">Remove</button></td>
        </tr>`).join('') + `</table>`
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
    html += '<table><tr><th>Product</th><th>Days left</th><th>Added</th></tr>' +
      active.map(r => `<tr><td>${r.product}</td><td class="${daysClass(r.days_left)}">${r.days_left}</td><td>${r.added.slice(0,10)}</td></tr>`).join('') +
      '</table>';
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
        elif parsed.path == "/api/subscribers":
            self._json({
                "products": list(PRODUCTS),
                "data": {p: active_subscribers(p) for p in PRODUCTS},
                "expiry_days": EXPIRY_DAYS,
            })
        elif parsed.path == "/api/check":
            email = parse_qs(parsed.query).get("email", [""])[0]
            self._json({"email": email, "rows": products_for_email(email)})
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
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"Subscriber admin running at {url}  (Ctrl+C to stop)")
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
