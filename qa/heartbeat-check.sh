#!/usr/bin/env bash
# qa/heartbeat-check.sh - dead-man switch (Linux / VPS). Runs ~08:00 UTC via
# cron. If qa.heartbeats has no beat dated today (UTC), the loop did not run -
# alert. On a VPS this has no same-box blind spot (unlike beeep).
set -uo pipefail

QADIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$QADIR"
PYTHON="${QA_PYTHON:-python3}"
cd "$QADIR"

[ -f "$QADIR/DISABLED" ] && exit 0

TODAY="$(date -u +%Y-%m-%d)"
LAST="$("$PYTHON" -m lib.runctl last-beat 2>/dev/null | head -1 | tr -d '[:space:]')"

if [ "$LAST" != "$TODAY" ]; then
    MSG="DEAD-MAN: QA loop has not run today (last beat: ${LAST:-NONE}, expected $TODAY UTC)."
    "$PYTHON" -m lib.notifyctl run_failed "$MSG" >/dev/null 2>&1 || true
    echo "$MSG"
    exit 1
fi
echo "OK: beat present for $TODAY"
exit 0
