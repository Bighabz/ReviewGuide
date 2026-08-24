#!/usr/bin/env bash
# qa/deploy-vps.sh - set up the QA loop on a Linux VPS. Run ONCE on the VPS,
# from the qa/ dir, AFTER the repo tree + qa/.env are copied over.
#
# Detects available tools and enables exactly the runners whose deps exist:
#   always : api_suite (chat + security probes), data_integrity (Supabase)
#   + npm  : deps_audit (needs ../frontend/package.json too)
#   + playwright browsers : browser_qa
#   + lighthouse : lighthouse
#   unit_suite is never enabled on the VPS (it is a prod monitor, no checkout to test).
#
# It does NOT apt-install anything by itself; missing heavy deps are reported
# with the exact command to add them. Writes config.local.json + installs cron.
set -euo pipefail

QADIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$QADIR/.." && pwd)"
PYTHON="${QA_PYTHON:-python3}"

echo "== ReviewGuide QA loop - VPS deploy =="
command -v "$PYTHON" >/dev/null || { echo "FATAL: $PYTHON not found"; exit 1; }
"$PYTHON" --version

if [ ! -f "$QADIR/.env" ]; then
    echo "FATAL: $QADIR/.env is missing. Copy it from beeep (contains SUPABASE_QA_KEY)."
    exit 1
fi
grep -q '^SUPABASE_QA_KEY=.\+' "$QADIR/.env" || { echo "FATAL: SUPABASE_QA_KEY not set in qa/.env"; exit 1; }

enabled='"api_suite","data_integrity"'
notes=""

if command -v npm >/dev/null && [ -f "$REPO/frontend/package.json" ]; then
    enabled="$enabled,\"deps_audit\""
else
    notes="$notes\n- deps_audit OFF (need npm + $REPO/frontend/package.json)"
fi

PW_BROWSERS="${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}"
if command -v npx >/dev/null && [ -d "$QADIR/playwright/node_modules" ] && [ -d "$PW_BROWSERS" ]; then
    enabled="$enabled,\"browser_qa\""
else
    notes="$notes\n- browser_qa OFF (run: cd $QADIR/playwright && npm ci && npx playwright install --with-deps chromium)"
fi

if command -v lighthouse >/dev/null; then
    enabled="$enabled,\"lighthouse\""
else
    notes="$notes\n- lighthouse OFF (run: npm install -g lighthouse ; needs chromium)"
fi

# notify channel: RC SMS via the clawd stack when RC_SCRIPT_PATH is set in .env, else telegram
if grep -q '^RC_SCRIPT_PATH=.\+' "$QADIR/.env"; then notify=rc; else notify=telegram; fi

cat > "$QADIR/config.local.json" <<JSON
{
  "notify_channel": "$notify",
  "npx_path": "npx",
  "npm_path": "npm",
  "lighthouse_path": "lighthouse",
  "playwright_browsers_path": "$PW_BROWSERS",
  "unit_suite_cmds": [],
  "enabled_runners": [$enabled]
}
JSON
echo "wrote config.local.json  enabled_runners=[$enabled]  notify_channel=$notify"

chmod +x "$QADIR/run.sh" "$QADIR/heartbeat-check.sh" "$QADIR/install-cron.sh" 2>/dev/null || true

echo "== connectivity check =="
QA_PYTHON="$PYTHON" PYTHONPATH="$QADIR" "$PYTHON" - <<PY
from lib import envfile, httpio, store
envfile.load_env("$QADIR/.env")
r = httpio.execute({"method":"GET","url":store.BASE_URL+"/rest/v1/runs","headers":store._headers(),"query":{"select":"run_id","limit":"1"},"json":None})
print("qa.runs reachable:", r["status"])
print("conversation_messages reachable:", len(httpio.pg_rest_query("rows_for_session", {"session_id":"none"})) == 0)
PY

echo "== installing cron =="
bash "$QADIR/install-cron.sh"

echo ""
echo "DONE. Enabled runners: [$enabled]"
[ -n "$notes" ] && printf "To enable the rest:%b\n" "$notes"
echo "Smoke it now:  QA_PYTHON=$PYTHON bash $QADIR/run.sh"
