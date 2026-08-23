#!/usr/bin/env bash
# qa/run.sh - the single supervised entrypoint (Linux / VPS).
# Mirrors run.ps1: kill-switch, per-runner timeouts, breach-aborts prod
# runners, writes SUMMARY, notifies, prunes. Runners read qa/.env themselves;
# no secrets on the command line.
set -uo pipefail

QADIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$QADIR"
PYTHON="${QA_PYTHON:-python3}"
cd "$QADIR"

# 1. kill-switch
if [ -f "$QADIR/DISABLED" ]; then echo "qa/DISABLED present - exit 0 (kill-switch)"; exit 0; fi

# 2. run id + artifacts dir
RUN_ID="run-$(date -u +%Y%m%d-%H%M%S)"
RUN_DIR="$QADIR/runs/$RUN_ID"
mkdir -p "$RUN_DIR"

ctl() { "$PYTHON" -m lib.runctl "$@" >/dev/null 2>&1 || true; }

# 3. start + first heartbeat (best-effort)
ctl start --run-id "$RUN_ID" --host "$(hostname)"
ctl beat --run-id "$RUN_ID"

# runner order + which are prod-facing (skipped on a containment breach)
ALL="unit_suite deps_audit api_suite browser_qa lighthouse data_integrity"
ENABLED="$("$PYTHON" -c "from lib import config; print(' '.join(config.load().get('enabled_runners', '$ALL'.split())))" 2>/dev/null)"
[ -z "$ENABLED" ] && ENABLED="$ALL"
PROD="api_suite browser_qa lighthouse data_integrity"

declare -A TIMEOUT=( [unit_suite]=6000 [deps_audit]=600 [api_suite]=900 [browser_qa]=1500 [lighthouse]=900 [data_integrity]=300 )

declare -A RESULT
BREACHED=0
for runner in $ENABLED; do
    if [ "$BREACHED" = "1" ] && [[ " $PROD " == *" $runner "* ]]; then
        RESULT[$runner]="SKIPPED_breach"; continue
    fi
    timeout "${TIMEOUT[$runner]:-900}" "$PYTHON" -m "runners.$runner" --run-id "$RUN_ID" --artifacts-dir "$RUN_DIR" \
        >"$RUN_DIR/$runner.out" 2>"$RUN_DIR/$runner.err"
    rc=$?
    RESULT[$runner]=$rc
    ctl beat --run-id "$RUN_ID"
    if [ "$runner" = "api_suite" ] && [ "$rc" = "3" ]; then
        BREACHED=1
        "$PYTHON" -m lib.notifyctl breach "CONTAINMENT BREACH in api_suite (run $RUN_ID) - prod runners aborted." >/dev/null 2>&1 || true
    fi
done

# 4. aggregate severity counts + write SUMMARY
COUNTS="$("$PYTHON" - "$RUN_DIR" <<'PY'
import glob, json, os, sys
d = sys.argv[1]
counts = {"high": 0, "medium": 0, "low": 0, "info": 0}
for f in glob.glob(os.path.join(d, "*.json")):
    if os.path.basename(f) in ("qa-writes-manifest.json", "playwright-report.json"):
        continue
    try:
        doc = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    for x in doc.get("findings", []):
        s = x.get("severity")
        if s in counts:
            counts[s] += 1
print(json.dumps(counts))
PY
)"
[ -z "$COUNTS" ] && COUNTS='{"high":0,"medium":0,"low":0,"info":0}'

{
    echo "run: $RUN_ID"
    echo "breached: $BREACHED"
    echo "findings: $COUNTS"
    echo "runners:"
    for runner in $ALL; do echo "  $runner: ${RESULT[$runner]:-not_run}"; done
} > "$RUN_DIR/SUMMARY.txt"

# 5. finish + notify. Any non-zero (that is not the skip sentinel) = failure.
ctl finish --run-id "$RUN_ID" --counts "$COUNTS"
CRASHED=0
for runner in $ENABLED; do
    r="${RESULT[$runner]:-0}"
    [ "$r" = "SKIPPED_breach" ] && continue
    [ "$r" != "0" ] && CRASHED=1
done
if [ "$BREACHED" = "1" ] || [ "$CRASHED" = "1" ]; then
    "$PYTHON" -m lib.notifyctl run_failed "QA run $RUN_ID FAILED (breach=$BREACHED crash=$CRASHED). $COUNTS" >/dev/null 2>&1 || true
else
    "$PYTHON" -m lib.notifyctl run_complete "QA run $RUN_ID OK. $COUNTS" >/dev/null 2>&1 || true
fi

# 6. retention: prune run dirs older than retention_days (default 30)
DAYS="$("$PYTHON" -c "from lib import config; print(int(config.load().get('retention_days',30)))" 2>/dev/null)"
[ -z "$DAYS" ] && DAYS=30
find "$QADIR/runs" -maxdepth 1 -type d -name 'run-*' -mtime +"$DAYS" -exec rm -rf {} + 2>/dev/null || true

echo "$RUN_DIR/SUMMARY.txt"
if [ "$BREACHED" = "1" ] || [ "$CRASHED" = "1" ]; then exit 1; fi
exit 0
