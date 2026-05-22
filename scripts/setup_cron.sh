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
# Clairvoyance — Full refresh at 0800, 1200, 1600, 2000, 0000 MT
0 8,12,16,20,0 * * * cd $ROOT && $PYTHON scripts/clairvoyance_update.py --push >> $LOG 2>&1
# Clairvoyance — Live window 1700 MT (self-terminates at 2300)
0 17 * * * cd $ROOT && $PYTHON scripts/clairvoyance_update.py --mode live --push >> $LOG 2>&1
# Clairvoyance — Props-only refresh at 1500 MT
0 15 * * * cd $ROOT && $PYTHON scripts/clairvoyance_update.py --mode props --push >> $LOG 2>&1"

echo "Current crontab:"
crontab -l 2>/dev/null || echo "(empty)"
echo ""
echo "Adding Clairvoyance cron jobs..."

# Remove old Clairvoyance lines and add new ones
(crontab -l 2>/dev/null | grep -v "clairvoyance_update.py" | grep -v "# Clairvoyance"; echo "$CRON_LINES") | crontab -

echo "Done. New crontab:"
crontab -l
