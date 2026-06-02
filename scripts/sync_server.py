#!/usr/bin/env python3
"""
Clairvoyance Local Sync Server
Listens on localhost:47821 for POST /sync requests from the browser.
Runs the full data refresh pipeline and pushes to GitHub.

Start: python3 scripts/sync_server.py
Auto-start: added to launchd via scripts/install_sync_server.sh
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess, threading, json, os, time, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 47821
_running = False
_last_run: dict = {"status": "idle", "started": None, "finished": None, "log": ""}

def _run_update():
    global _running, _last_run
    _running = True
    _last_run = {"status": "running", "started": time.time(), "finished": None, "log": ""}
    try:
        result = subprocess.run(
            ["bash", "scripts/run_update.sh", "--push"],
            cwd=ROOT, capture_output=True, text=True, timeout=600
        )
        _last_run["log"] = (result.stdout + result.stderr)[-3000:]  # last 3KB
        _last_run["status"] = "success" if result.returncode == 0 else "error"
    except subprocess.TimeoutExpired:
        _last_run["status"] = "timeout"
        _last_run["log"] = "Update timed out after 10 minutes"
    except Exception as e:
        _last_run["status"] = "error"
        _last_run["log"] = str(e)
    finally:
        _last_run["finished"] = time.time()
        _running = False

class SyncHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress request logs

    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(data))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            self._send(200, {**_last_run, "running": _running, "port": PORT})
        elif self.path == "/ping":
            self._send(200, {"ok": True, "version": "1.0"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/sync":
            global _running
            if _running:
                self._send(200, {"queued": False, "reason": "already running", "running": True})
                return
            threading.Thread(target=_run_update, daemon=True).start()
            self._send(200, {"queued": True, "running": True, "message": "Refresh started"})
        else:
            self._send(404, {"error": "not found"})

if __name__ == "__main__":
    os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
    server = HTTPServer(("127.0.0.1", PORT), SyncHandler)
    print(f"[Clairvoyance Sync Server] Listening on http://127.0.0.1:{PORT}")
    print(f"  POST /sync   → trigger full rebuild")
    print(f"  GET  /status → check run status")
    print(f"  GET  /ping   → health check")
    print(f"  Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Sync Server] Stopped.")
