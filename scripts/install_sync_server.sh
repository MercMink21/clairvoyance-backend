#!/bin/bash
# Installs the Clairvoyance sync server as a macOS LaunchAgent
# so it starts automatically at login and stays running.
# Run: bash scripts/install_sync_server.sh

PLIST="$HOME/Library/LaunchAgents/com.clairvoyance.syncserver.plist"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT/venv/bin/python3"
[ -f "$PYTHON" ] || PYTHON="$(which python3)"

cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.clairvoyance.syncserver</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$ROOT/scripts/sync_server.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$ROOT</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$ROOT/logs/sync_server.log</string>
    <key>StandardErrorPath</key>
    <string>$ROOT/logs/sync_server.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "✅ Sync server installed and started (port 47821)"
echo "   Logs: $ROOT/logs/sync_server.log"
echo "   To stop:  launchctl unload $PLIST"
echo "   To start: launchctl load $PLIST"
