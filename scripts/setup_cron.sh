#!/bin/bash
# Clairvoyance Engine — Cron Schedule Setup
# Run: bash scripts/setup_cron.sh
# Installs refresh schedule into current user's crontab

SCRIPT_DIR="$(cd "$(dirname "$0")"; pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON="$(which python3)"
LOG="$ROOT/logs/cron.log"

# Create logs dir
mkdir -p "$ROOT/logs"

# Build crontab additions
CRON_LINES="TZ=America/Denver
# Clairvoyance — 3x daily refresh at 15:00, 20:00, 23:00 MT
0 15,20,23 * * * cd $ROOT && bash scripts/run_update.sh --push >> $LOG 2>&1"

echo "Current crontab:"
crontab -l 2>/dev/null || echo "(empty)"
echo ""
echo "Adding Clairvoyance cron jobs..."

# Remove old Clairvoyance lines and add new ones
(crontab -l 2>/dev/null | grep -v "clairvoyance_update.py" | grep -v "run_update.sh" | grep -v "# Clairvoyance"; echo "$CRON_LINES") | crontab -

echo "Done. New crontab:"
crontab -l
