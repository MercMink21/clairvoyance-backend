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
<style>
  :root { color-scheme: dark; }
  body { background:#0a0014; color:#e8e8e8; font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
         max-width:920px; margin:0 auto; padding:24px 20px 60px; }
  h1 { font-size:20px; letter-spacing:1px; margin-bottom:4px; }
  .sub { color:#999; font-size:13px; margin-bottom:24px; }
  .card { background:#14001f; border-radius:8px; padding:16px 18px; margin-bottom:18px; }
  .card h2 { font-size:13px; letter-spacing:2px; color:#00e5ff; text-transform:uppercase; margin:0 0 12px; }
  label { display:block; font-size:12px; color:#999; margin-bottom:4px; }
  input[type=email], input[type=text] {
    background:#1c0230; border:1px solid #333; color:#fff; border-radius:4px; padding:8px 10px;
    font-size:14px; width:100%; box-sizing:border-box;
  }
  .row { display:flex; gap:10px; margin-bottom:10px; flex-wrap:wrap; }
  .row > div { flex:1; min-width:180px; }
  .chips { display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }
  .chip { background:#1c0230; border:1px solid #333; border-radius:14px; padding:4px 10px; font-size:12px;
          cursor:pointer; user-select:none; }
  .chip.on { background:#00e5ff; color:#000; border-color:#00e5ff; font-weight:700; }
  button { background:#00e5ff; color:#000; border:none; border-radius:4px; padding:9px 16px; font-weight:700;
           font-size:13px; cursor:pointer; margin-top:4px; }
  button.secondary { background:#333; color:#e8e8e8; }
  button.danger { background:#ff3b5c; color:#fff; padding:4px 10px; font-size:11px; margin:0; }
  .msg { font-size:13px; margin-top:8px; min-height:16px; }
  .msg.ok { color:#00e676; }
  .msg.err { color:#ff3b5c; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th { text-align:left; color:#999; font-weight:600; padding:6px 8px; border-bottom:1px solid #333; }
  td { padding:6px 8px; border-bottom:1px solid rgba(255,255,255,.06); }
  .prodblock { margin-bottom:16px; }
  .prodblock h3 { font-size:14px; color:#fff; margin:0 0 6px; text-transform:uppercase; letter-spacing:1px; }
  .empty { color:#666; font-size:12px; padding:4px 8px; }
  .days { color:#ffdd00; }
  .days.low { color:#ff3b5c; }
</style>
</head>
<body>
  <h1>SUBSCRIBERS</h1>
  <div class="sub" id="expiryNote">30-day access windows · data/subscribers.json (local file only)</div>

  <div class="card">
    <h2>Add / Renew</h2>
    <div class="row">
      <div>
        <label>Email</label>
        <input type="email" id="addEmail" placeholder="someone@example.com">
      </div>
    </div>
    <label>Products</label>
    <div class="chips" id="addChips"></div>
    <button onclick="doAdd()">Add / Renew</button>
    <div class="msg" id="addMsg"></div>
  </div>

  <div class="card">
    <h2>Check an email</h2>
    <div class="row">
      <div>
        <input type="email" id="checkEmail" placeholder="someone@example.com">
      </div>
      <button class="secondary" onclick="doCheck()" style="flex:0 0 auto">Check</button>
    </div>
    <div id="checkResult"></div>
  </div>

  <div class="card">
    <h2>All active subscribers</h2>
    <div id="allList"></div>
  </div>

<script>
let PRODUCTS = [];
let selectedProducts = new Set();

async function loadAll() {
  const res = await fetch('/api/subscribers');
  const data = await res.json();
  PRODUCTS = data.products;
  document.getElementById('expiryNote').textContent =
    data.expiry_days + '-day access windows · data/subscribers.json (local file only)';
  renderChips();
  renderAllList(data.data);
}

function renderChips() {
  const el = document.getElementById('addChips');
  el.innerHTML = PRODUCTS.map(p =>
    `<span class="chip${selectedProducts.has(p)?' on':''}" onclick="toggleChip('${p}')">${p.toUpperCase()}</span>`
  ).join('');
}

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
          <td class="days${r.days_left<=5?' low':''}">${r.days_left}</td>
          <td>${r.added.slice(0,10)}</td>
          <td><button class="danger" onclick="doRemove('${p}','${escapeAttr(r.email)}')">remove</button></td>
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
      active.map(r => `<tr><td>${r.product}</td><td class="days${r.days_left<=5?' low':''}">${r.days_left}</td><td>${r.added.slice(0,10)}</td></tr>`).join('') +
      '</table>';
  } else {
    html += '<div class="empty">No active subscriptions.</div>';
  }
  if (expired.length) {
    html += '<div class="sub" style="margin-top:8px">Expired: ' + expired.map(r => r.product).join(', ') + '</div>';
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
