#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Clairvoyance automated data refresh wrapper
# Schedule with cron (5× daily):
#   crontab -e
#   0 7,11,15,18,22 * * * /Users/reeseoliver/clairvoyance-backend/scripts/run_update.sh --push
#
# Or for a quick manual refresh:
#   ./scripts/run_update.sh
#   ./scripts/run_update.sh --push --verbose
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$REPO_DIR/scripts/clairvoyance_update.py"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/update_$(date +%Y%m%d).log"

# Use the system Python or a venv
PYTHON="${CLAIRVOYANCE_PYTHON:-python3}"

# ── ensure log dir ────────────────────────────────────────────────────────────
mkdir -p "$LOG_DIR"

# ── activate venv if it exists ────────────────────────────────────────────────
if [[ -f "$REPO_DIR/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1090
  source "$REPO_DIR/.venv/bin/activate"
  PYTHON="$REPO_DIR/.venv/bin/python3"
elif [[ -f "$REPO_DIR/venv/bin/activate" ]]; then
  # shellcheck disable=SC1090
  source "$REPO_DIR/venv/bin/activate"
  PYTHON="$REPO_DIR/venv/bin/python3"
fi

# ── install / upgrade deps once per day ──────────────────────────────────────
STAMP_FILE="$LOG_DIR/.deps_$(date +%Y%m%d)"
if [[ ! -f "$STAMP_FILE" ]]; then
  echo "[$(date +%H:%M:%S)] Installing/upgrading dependencies…" | tee -a "$LOG_FILE"
  $PYTHON -m pip install -q -r "$REPO_DIR/scripts/requirements.txt" 2>&1 | tail -5 | tee -a "$LOG_FILE"
  touch "$STAMP_FILE"
fi

# ── run update ────────────────────────────────────────────────────────────────
echo "" | tee -a "$LOG_FILE"
echo "════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "[$(date +%H:%M:%S)] Starting Clairvoyance update  (args: $*)" | tee -a "$LOG_FILE"
echo "════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"

cd "$REPO_DIR"
$PYTHON "$SCRIPT" "$@" 2>&1 | tee -a "$LOG_FILE"

echo "[$(date +%H:%M:%S)] Done." | tee -a "$LOG_FILE"

# ── keep logs for 14 days ─────────────────────────────────────────────────────
find "$LOG_DIR" -name "update_*.log" -mtime +14 -delete 2>/dev/null || true
find "$LOG_DIR" -name ".deps_*"      -mtime +1  -delete 2>/dev/null || true
