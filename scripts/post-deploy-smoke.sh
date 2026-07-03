#!/usr/bin/env bash
# Post-deploy smoke check
# Usage: BACKEND_URL=https://your-backend.com scripts/post-deploy-smoke.sh
# Exits non-zero on any failure so CI/Railway can page on regressions.

set -euo pipefail

BACKEND_URL="${BACKEND_URL:-https://backend-production-0ae7.up.railway.app}"
TIMEOUT="${TIMEOUT:-30}"
FAIL=0

say() { printf '\n▸ %s\n' "$*"; }
fail() { printf '✗ %s\n' "$*" >&2; FAIL=1; }
ok() { printf '✓ %s\n' "$*"; }

# ---------------------------------------------------------------------------
# 1. Health endpoint must return 200
# ---------------------------------------------------------------------------
say "checking /health …"
HEALTH_CODE=$(curl -sS -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" "$BACKEND_URL/health" || echo "000")
if [[ "$HEALTH_CODE" == "200" ]]; then
  ok "/health returned 200"
else
  fail "/health returned $HEALTH_CODE (expected 200)"
fi

# ---------------------------------------------------------------------------
# 2. Product chat query must return non-empty ui_blocks with an Amazon tag
# ---------------------------------------------------------------------------
say "running canonical product query …"
PRODUCT_BODY=$(cat <<'EOF'
{"message":"best wireless earbuds under $100","session_id":null}
EOF
)
# Stream the SSE response to a temp file so we can grep it.
PRODUCT_OUT=$(mktemp)
trap 'rm -f "$PRODUCT_OUT"' EXIT

curl -sSN --max-time "$TIMEOUT" \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -d "$PRODUCT_BODY" \
  "$BACKEND_URL/v1/chat/stream" > "$PRODUCT_OUT" || true

# The flow is clarifier-first: turn 1 usually halts with questions. Answer with
# a no-preference follow-up on the SAME session to reach actual product cards.
if grep -q '"status": *"halted"' "$PRODUCT_OUT"; then
  say "clarifier halted turn 1 (expected) — answering to reach results …"
  SMOKE_SESSION=$(grep -oE '"session_id": *"[^"]+"' "$PRODUCT_OUT" | head -1 | grep -oE '[0-9a-f-]{8,}' || echo "smoke-$$")
  curl -sSN --max-time 120 \
    -H 'Content-Type: application/json' \
    -H 'Accept: text/event-stream' \
    -d "{\"message\":\"no preference, just show me the best options\",\"session_id\":\"$SMOKE_SESSION\"}" \
    "$BACKEND_URL/v1/chat/stream" > "$PRODUCT_OUT" || true
fi

if ! [[ -s "$PRODUCT_OUT" ]]; then
  fail "product chat stream returned no body"
elif grep -qi 'error while formatting the response' "$PRODUCT_OUT"; then
  fail "product compose returned the error-fallback string"
elif ! grep -q '"ui_blocks"' "$PRODUCT_OUT"; then
  fail "product chat stream had no ui_blocks payload"
elif grep -q 'amazon\.' "$PRODUCT_OUT" && ! grep -q 'tag=revguide-20' "$PRODUCT_OUT"; then
  fail "product chat produced an Amazon link without tag=revguide-20 (revenue leak)"
elif ! grep -q 'tag=revguide-20' "$PRODUCT_OUT"; then
  fail "no tagged Amazon links in product results (expected at least one)"
else
  ok "product query produced ui_blocks AND Amazon tag present"
fi

# ---------------------------------------------------------------------------
# 3. Travel chat query must NOT hang (has a timeout/recovery path)
# ---------------------------------------------------------------------------
say "running canonical travel query …"
TRAVEL_BODY=$(cat <<'EOF'
{"message":"plan a 5-day trip to Tokyo","session_id":null}
EOF
)
TRAVEL_OUT=$(mktemp)
trap 'rm -f "$PRODUCT_OUT" "$TRAVEL_OUT"' EXIT

# 45s upper bound — if it's still streaming, kill and record failure.
if ! timeout 45 curl -sSN \
     -H 'Content-Type: application/json' \
     -H 'Accept: text/event-stream' \
     -d "$TRAVEL_BODY" \
     "$BACKEND_URL/v1/chat/stream" > "$TRAVEL_OUT"; then
  fail "travel chat hung or errored (>45s or non-zero curl exit)"
elif ! [[ -s "$TRAVEL_OUT" ]]; then
  fail "travel chat returned no body"
elif ! grep -qE '("event": ?"done"|"done"|artifact|clarifier)' "$TRAVEL_OUT"; then
  fail "travel chat completed but no 'done'/'artifact'/'clarifier' event seen"
else
  ok "travel query completed within 45s with a terminal event"
fi

# ---------------------------------------------------------------------------
# 4. Deployed SHA must match origin/main (catches silent deploy gaps)
# ---------------------------------------------------------------------------
say "checking deployed SHA vs origin/main …"
DEPLOYED_SHA=$(curl -sS --max-time "$TIMEOUT" "$BACKEND_URL/health" | grep -oE '"version": ?"[0-9a-f]{40}"' | grep -oE '[0-9a-f]{40}' || true)
MAIN_SHA=$(git ls-remote origin main 2>/dev/null | cut -f1 || true)
if [[ -z "$DEPLOYED_SHA" ]]; then
  fail "/health .version is not a commit SHA (deploy pipeline regression — see CLAUDE.md Production Reality)"
elif [[ -z "$MAIN_SHA" ]]; then
  ok "deployed SHA $DEPLOYED_SHA (origin/main unknown here — skipping comparison)"
elif [[ "$DEPLOYED_SHA" == "$MAIN_SHA" ]]; then
  ok "deployed SHA matches origin/main ($DEPLOYED_SHA)"
else
  fail "deployed $DEPLOYED_SHA != origin/main $MAIN_SHA (undeployed commits on main)"
fi

# ---------------------------------------------------------------------------
# 5. Revenue: eBay links must not carry the placeholder campaign ID
# ---------------------------------------------------------------------------
say "checking eBay campaign ID in product output …"
if grep -q 'campid=1234567890' "$PRODUCT_OUT"; then
  fail "eBay links carry PLACEHOLDER campid=1234567890 — links earn \$0 (set real EBAY_CAMPAIGN_ID)"
elif grep -q 'campid=' "$PRODUCT_OUT"; then
  ok "eBay links carry a non-placeholder campid"
else
  ok "no eBay links in this response (nothing to check)"
fi

# ---------------------------------------------------------------------------
# 6. Frontend: robots.txt, sitemap.xml, OG tags (skip with FRONTEND_URL=skip)
# ---------------------------------------------------------------------------
FRONTEND_URL="${FRONTEND_URL:-https://www.reviewguide.ai}"
if [[ "$FRONTEND_URL" != "skip" ]]; then
  say "checking frontend surface at $FRONTEND_URL …"
  for path in /robots.txt /sitemap.xml; do
    CODE=$(curl -sSL -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" "$FRONTEND_URL$path" || echo "000")
    if [[ "$CODE" == "200" ]]; then ok "$path returned 200"; else fail "$path returned $CODE (expected 200)"; fi
  done
  # Download first, then grep — `curl | grep -q` under pipefail turns grep's
  # early exit (SIGPIPE back to curl) into a spurious failure.
  HOME_OUT=$(mktemp)
  curl -sSL --max-time "$TIMEOUT" "$FRONTEND_URL/" -o "$HOME_OUT" || true
  if grep -q 'property="og:image' "$HOME_OUT"; then
    ok "og:image tag present on /"
  else
    fail "og:image tag missing on / (share unfurls broken)"
  fi
  rm -f "$HOME_OUT"
fi

# ---------------------------------------------------------------------------
# 7. Rate limit (opt-in: RATE_LIMIT_PROBE=1 — sends 22 rapid requests)
# ---------------------------------------------------------------------------
if [[ "${RATE_LIMIT_PROBE:-0}" == "1" ]]; then
  say "probing rate limit (22 rapid requests) …"
  GOT_429=0
  for i in $(seq 1 22); do
    CODE=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 \
      -H 'Content-Type: application/json' \
      -d '{"message":"rate limit probe","session_id":"rl-probe"}' \
      "$BACKEND_URL/v1/chat/stream" || echo "000")
    [[ "$CODE" == "429" ]] && GOT_429=1 && break
  done
  if [[ "$GOT_429" == "1" ]]; then
    ok "rate limit fired (429 observed)"
  else
    fail "no 429 after 22 rapid requests — RATE_LIMIT_ENABLED is off or misconfigured"
  fi
fi

# ---------------------------------------------------------------------------
# Exit summary
# ---------------------------------------------------------------------------
if [[ "$FAIL" -ne 0 ]]; then
  printf '\n✗ POST-DEPLOY SMOKE CHECK FAILED (BACKEND_URL=%s)\n' "$BACKEND_URL" >&2
  exit 1
fi

printf '\n✓ Post-deploy smoke check OK (BACKEND_URL=%s)\n' "$BACKEND_URL"
