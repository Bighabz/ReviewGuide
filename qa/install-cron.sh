#!/usr/bin/env bash
# qa/install-cron.sh - register the two cron jobs (idempotent). Replaces the
# Windows Task Scheduler on the VPS. Times are the crontab's local tz; the VPS
# should be UTC (heartbeat compares UTC). Logs to qa/runs/cron.log.
set -euo pipefail

QADIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$QADIR/runs/cron.log"
mkdir -p "$QADIR/runs"

RUN_LINE="45 5 * * * /usr/bin/env bash $QADIR/run.sh >> $LOG 2>&1  # RG-QA-Run"
BEAT_LINE="0 8 * * * /usr/bin/env bash $QADIR/heartbeat-check.sh >> $LOG 2>&1  # RG-QA-Heartbeat"

# Rebuild crontab: keep every line that is not ours, then append ours.
current="$(crontab -l 2>/dev/null || true)"
filtered="$(printf '%s\n' "$current" | grep -v -e 'RG-QA-Run' -e 'RG-QA-Heartbeat' || true)"
{ printf '%s\n' "$filtered" | sed '/^$/d'; echo "$RUN_LINE"; echo "$BEAT_LINE"; } | crontab -

echo "installed cron jobs:"
crontab -l | grep 'RG-QA'
echo "log: $LOG"
