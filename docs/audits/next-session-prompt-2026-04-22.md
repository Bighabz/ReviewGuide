> ⚠️ **SUPERSEDED — see [`next-session-prompt-2026-05-19.md`](./next-session-prompt-2026-05-19.md).**
>
> This doc's premise (`ui_blocks: []`, providers report "unavailable") was wrong. Live audit on 2026-04-21 confirmed cards DO render — they just point to wrong products via a positional-zip bug. The env-mutation plan in §1 below (`USE_MOCK_AFFILIATE=true`, etc.) would have made things worse and should NOT be executed.
>
> Kept for historical context only.

---

# Next Session Prompt — ReviewGuide.ai Stabilization Continuation

**Pick up from:** 2026-04-21 session end (commit `84d2999` on `origin/main`)
**Session goal:** Restore affiliate revenue (`ui_blocks: []` + providers report "unavailable"), re-land deferred sprint items, activate dormant infrastructure.
**Expected duration:** 2-3 hours.

## Reference Documents (read these first)

- **Original audit report:** [`docs/audits/opus-4.7-audit-report-2026-04-16.md`](./opus-4.7-audit-report-2026-04-16.md) — principal-engineer deep dive, P0-P3 inventory, v2-vs-v3 assessment, 3-month roadmap
- **3-week sprint plan:** [`docs/audits/sprint-plan-2026-04-21.md`](./sprint-plan-2026-04-21.md) — day-by-day breakdown with acceptance criteria
- **Refreshed codebase maps** (cited throughout the audit):
  - [`.planning/codebase/STACK.md`](../../.planning/codebase/STACK.md)
  - [`.planning/codebase/ARCHITECTURE.md`](../../.planning/codebase/ARCHITECTURE.md)
  - [`.planning/codebase/CONVENTIONS.md`](../../.planning/codebase/CONVENTIONS.md)
  - [`.planning/codebase/CONCERNS.md`](../../.planning/codebase/CONCERNS.md)

## State Snapshot (at end of 2026-04-21 session)

**Last commit on `main`:** `84d2999` — "fix(backend): add missing generate_compose / generate_compose_with_streaming"

**What's verified live on https://www.reviewguide.ai:**

| # | Fix | Commit | Status |
|---|---|---|---|
| P0-1 | Desktop layout overflow (homepage cards no longer behind footer) | `df4adc9` | ✅ |
| P0-2/3 | Chat welcome screen + input visible at 1440×900 (footer hidden on /chat) | `df4adc9` + `20b858e` | ✅ |
| P0-4 | Product compose error (the REAL cause was missing `model_service.generate_compose` method — ported from v3 commit `6cde1a6`) | `84d2999` | ✅ |
| P1-1 | Custom editorial 404 "This page *wandered off.*" | `df4adc9` | ✅ |
| P1-2 | Profile nav link hidden from topbar | `df4adc9` | ✅ |
| Boot | bcrypt restored to requirements.txt (the passlib[bcrypt] removal transitively killed bcrypt, crashed container with ModuleNotFoundError) | `b9b23a7` | ✅ |
| Rollback | Temporary sentry-sdk removal (turned out unnecessary, red herring on the boot-502 diagnosis) | `d7581fc` | ✅ |

**What's still broken (this session's targets):**

1. **P0-5 not verified** — Amazon affiliate `tag=revguide-20` presence. Can't verify without product cards rendering.
2. **`ui_blocks: []`** — affiliate providers return `{"provider": "amazon", "status": "unavailable", "result_count": 0}` + same for eBay. Compose now works but has no products to render.
3. **Sentry not live** — backend SDK reverted, needs re-add with verified dep compatibility.
4. **Deferred cherry-picks:** `2b1c653` (sentinel scroll), `3e5f0a3` (WCAG + queued message).
5. **Tests not running:** `ChatContainer.test.tsx.skip` still skipped.

## Priority 1 — Fix Provider Config (The Revenue Blocker)

Start with Railway env. Assumes `railway link --project reviewguide-backend` + `railway service link backend` still active from prior session. If not, re-link.

```bash
railway variables | grep -iE "AMAZON|EBAY|USE_MOCK|AFFILIATE|SERPAPI"
```

**Expected config** (cross-reference vs actual output):

| Var | Expected | Why |
|---|---|---|
| `AMAZON_API_ENABLED` | `false` | Per CLAUDE.md/MEMORY.md: PA-API rate-limits brutally; curated `amzn.to` links (141 of them, `curated_amazon_links.py`) are the preferred path. |
| `USE_MOCK_AFFILIATE` | `true` | Enables the fallback provider chain when PA-API off. |
| `AMAZON_ASSOCIATE_TAG` | `revguide-20` | **Revenue-critical** — without this, every Amazon link earns $0. |
| `AMAZON_ASSOCIATE_TAGS` | `US:revguide-20` (plus any country-specific) | Multi-country fallback parsed by `amazon_provider.parse_associate_tags()`. |
| `EBAY_APP_ID` / `EBAY_CERT_ID` / `EBAY_CAMPAIGN_ID` | all set | eBay provider marks itself unavailable without all three. |
| `ENABLE_SERPAPI` | `true` | Review citations tool (`review_search`) gated on this. |
| `SERPAPI_API_KEY` | set | Actually Serper.dev key despite the name; empty = review_search returns empty bundle. |

If anything's off: `railway variables set KEY=value` then `railway redeploy`. Wait for `railway service status --all | grep backend` to go from `DEPLOYING` to `SUCCESS`.

**Validation (do this before declaring P1 done):**
```bash
curl -sSN --max-time 45 -H 'Content-Type: application/json' \
  -d '{"message":"best wireless earbuds under $100","session_id":null}' \
  https://backend-production-0ae7.up.railway.app/v1/chat/stream \
  > /tmp/rg_test.sse
grep -c '"ui_blocks": \[\]' /tmp/rg_test.sse   # should print 0 (no empty ui_blocks)
grep -c 'tag=revguide-20' /tmp/rg_test.sse      # should print ≥1
grep -c 'error while formatting' /tmp/rg_test.sse   # should print 0
```

If validation passes, close P0-5.

If the affiliate providers STILL show unavailable even with env correct, next suspect is `AffiliateProviderRegistry` not registering the mock provider at startup — grep `backend/app/services/affiliate/registry.py` + startup_manifest.py.

## Priority 2 — Run the Playwright Smoke Suite

```bash
cd frontend
npm install                    # picks up @playwright/test (already in package.json)
npx playwright install chromium
BASE_URL=https://www.reviewguide.ai npm run test:e2e
```

Expected: all 5 tests pass. The 5 tests (see `frontend/tests/e2e/smoke.spec.ts`):

1. Homepage trending cards visible above footer at 1440×900
2. `/chat?new=1` welcome screen + chat input in viewport at 1440×900
3. Product query returns ≥3 cards + at least one `tag=revguide-20` link (needs P1 fixed)
4. Travel query completes within 30s — no indefinite hang
5. `/browse/nonexistent` renders custom 404, not Next.js default

If any fail, fix before moving on. Wire `npm run test:e2e` into `.github/workflows/ci.yml` as a blocking job.

## Priority 3 — Re-land Deferred Sprint Items

In this order (each 30-60 min):

### 3a. Re-add Sentry (with verified compat)

```bash
# Verify no conflict with langfuse/otel stack
cd backend
pip install --dry-run 'sentry-sdk[fastapi]==2.20.0' -r /app/requirements.txt
```
If clean, add back to `requirements.txt` with comment noting it was re-added after bcrypt root cause confirmed. Set `SENTRY_DSN` on Railway + `NEXT_PUBLIC_SENTRY_DSN` on Vercel. Throw a synthetic exception to prove it captures.

### 3b. Cherry-pick `2b1c653` (sentinel scroll)

Conflicts with current `MessageList.tsx`/`chat/page.tsx`. Process:
```bash
git cherry-pick --no-commit 2b1c653
# Resolve conflicts preserving the overflow-y-auto + footer-on-chat-hidden fixes
git add -u && git cherry-pick --continue
```
Manual QA at 1440×900 + 390×844 before push. Test: momentum scroll on mobile doesn't fight auto-scroll during streaming.

### 3c. Cherry-pick `3e5f0a3` (WCAG contrast + queued message)

Same process. `frontend/components/ChatContainer.tsx` adds queued-message state + "Message queued" banner. Manual QA: send a second message during streaming, verify it's queued (not dropped) and fires when the first completes.

### 3d. Re-enable `ChatContainer.test.tsx.skip`

```bash
cd frontend
mv tests/ChatContainer.test.tsx.skip tests/ChatContainer.test.tsx
npm run test:run
```
Fix whatever fails. If the fix is bigger than 45 min, revert to `.skip` and open a follow-up. The goal here is getting CI to actually test the 884-LOC streaming hot path.

## Priority 4 — Activate Dormant Infrastructure

Only if P1-3 done and time remains.

### 4a. Tiered Router

Per `.planning/codebase/ARCHITECTURE.md`, `backend/app/services/tiered_router/` is fully built + tested but never fires because `clarifier_agent` always emits `next_agent="plan_executor"`.

- Add `ENABLE_TIERED_ROUTING` feature flag to `backend/app/core/config.py`
- In `clarifier_agent.py` (find where it returns the state dict), conditionally emit `next_agent="routing_gate"` when flag on + intent is `product|travel|comparison|price_check|review_deep_dive`
- Enable on staging, compare LLM token count vs flag-off baseline (should drop ≥30%)

### 4b. Restore Skimlinks + Serper Shopping providers

Deleted from v2 per CONCERNS.md:
```bash
git show v3-full-implementation -- backend/app/services/affiliate/providers/skimlinks_provider.py > /tmp/skimlinks.py
git show v3-full-implementation -- backend/app/services/affiliate/providers/serper_shopping_provider.py > /tmp/serper.py
# If both exist, restore to backend/app/services/affiliate/providers/
# Update AffiliateProviderRegistry registration if needed
```

## Out of Scope for This Session (backlog)

- `product_compose.py` refactor (1400 LOC → composable units) — XL, do as its own focused PR
- Saved + Compare feature builds — XL each
- Profile page (currently hidden)
- Next.js 15 migration
- Python `requirements.lock` via `uv pip compile`
- Logo gradient pill in dark mode
- `kishan_frontend/` deletion — local-only, gitignored, user's call
- Carousel consolidation (ProductCarousel.tsx + ProductReviewCarousel.tsx → unified)
- Card component helper dedup (`PLPLinkCard` × 3)

## Pre-Session Checklist

- [ ] `git status` shows clean working tree, on `main`
- [ ] `railway status` shows linked to `reviewguide-backend` → backend service
- [ ] Chrome MCP extension connected (restart Chrome if flaky)
- [ ] Backend responding: `curl -sS -o /dev/null -w "%{http_code}\n" https://backend-production-0ae7.up.railway.app/health` returns `200`

## Kickoff Prompt (paste this to start the next session)

> Continue the ReviewGuide stabilization sprint. Read `docs/audits/next-session-prompt-2026-04-22.md` first for full context, then `docs/audits/sprint-plan-2026-04-21.md` for the broader plan and `docs/audits/opus-4.7-audit-report-2026-04-16.md` for original findings. Start by dumping Railway env vars (`railway variables | grep -iE "AMAZON|EBAY|USE_MOCK|AFFILIATE|SERPAPI"`) and fixing any that don't match the expected config in Priority 1 of the next-session-prompt doc. Then run the Playwright smoke suite and verify P0-5 (Amazon `tag=revguide-20` in product-query response). Track progress with TaskCreate. Current commit on main: `84d2999`.

## Rollback Plan (if something new breaks)

All sprint commits are atomic. To revert to the last-verified-healthy state:
```bash
git revert 84d2999  # compose methods — if provider fix produces a new crash
# Or harder rollback:
git revert 84d2999 b9b23a7 d7581fc 20b858e fa8b401 bd98c97 1b66a02 df4adc9 a1d51ef 74c1d37
```
Pre-sprint state was `e89a54f` on main. Known-healthy for serving the site (but with all P0 bugs still live).

---

*Written 2026-04-21 by Claude Opus 4.7. Next session should complete this file's Priority 1-3 minimum.*
