# QA prod-write containment — backend plan (for /route verification before build)

**Goal:** make it safe for the automated QA loop to exercise LIVE prod without polluting
user-visible data, corrupting metrics, or enabling abuse. Scoped from the QA-LOOP-DESIGN v2
"prod-write containment" requirement. Backend = FastAPI (`backend/`). Keep the suite green.

## Marker convention (no new auth surface)
Synthetic QA traffic is identified by its **`session_id` prefix `qa-auto-`**. The app already
accepts arbitrary `session_id`, so nothing changes about ACCEPTING it — the work is EXCLUDING it
from anything user-visible, and (optionally) exempting it from rate limits behind a token.
Non-session synthetic requests may also send header **`X-QA-Synthetic: 1`**.

## Tasks

### C1 — Exclude qa-auto from every user-visible aggregate in admin metrics
`backend/app/api/v1/admin.py` `get_metrics` (~L314-411) computes, from `request_metrics` +
`affiliate_clicks`: `request_volume` (requests_1h/24h/rpm), `error_rate`, `top_queries.popular`,
`business_metrics.affiliate_ctr`/`travel_ctr`. Add a filter excluding synthetic sessions to EACH
aggregate query: `AND (session_id NOT LIKE 'qa-auto-%' OR session_id IS NULL)` (adapt column/table
per query; affiliate_ctr filters `affiliate_clicks.session_id`). Synthetic rows may still be WRITTEN
(harmless) but must never appear in a displayed number. Acceptance: seeding a `qa-auto-*` session +
click does not move popular_queries, affiliate_ctr, or request_volume.

### C2 — Rate-limit exemption behind a token (future-proof; RATE_LIMIT is off today)
`backend/app/core/rate_limiter.py::check_rate_limit` (and `app/core/dependencies.py:98`). When
`RATE_LIMIT_ENABLED` is true, skip limiting for a request that BOTH has a `qa-auto-` session_id AND
sends header `X-QA-Token` equal to env `QA_BYPASS_TOKEN` (new optional env; empty/unset ⇒ feature
off, no exemption). This stops the daily security/functional probes from self-tripping the limiter
without letting a real user spoof the prefix to escape limits. Acceptance: with the env set, a
qa-auto request + correct token bypasses; wrong/absent token does NOT.

### C3 — Keep qa-auto out of any personalization/memory/trending surface
Grep the backend for other user-visible aggregates or memory writes keyed on session/user
(`conversation_memory`, any "trending"/"suggested"/"recent" surface, `next_step_suggestion`). For
each that could surface synthetic content to real users, exclude `qa-auto-%`. If none exist beyond
C1, say so explicitly. Acceptance: no synthetic query text can reach a real user's screen.

### C4 — Tests
Add a backend test module `tests/test_qa_containment.py`: (a) an aggregate query excludes a seeded
qa-auto row; (b) rate-limit exemption requires the token (bypass with it, limited without it, and
no exemption when `QA_BYPASS_TOKEN` unset).

## Explicitly OUT of scope (handled runner-side, not in the app)
- Affiliate-click "no real redirect" — the Playwright runner asserts the `<a href>` + posts the
  tracking call WITHOUT following the outbound redirect. No backend change.
- Reconciliation manifest of synthetic rows — the runner logs the `qa-auto-*` session_ids it created.
- The QA loop's own scheduling/heartbeat/notify — separate P1 build.

## Constraints / gates
- `cd backend && python -m pytest -q` stays green (currently 985) incl. the new C4 tests.
- Do NOT touch auth logic, the KV layer, or migrations. Additive WHERE-filters + one guarded env only.
- `QA_BYPASS_TOKEN` is a new OPTIONAL env (default unset ⇒ no behavior change). Never commit a value.
- `git diff` touches only admin.py, rate_limiter.py, dependencies.py, and the new test file.

---
# CORRECTED PLAN v2 — after /route verification (Kimi read the real code, 2026-08-19)

The v1 plan was built on wrong assumptions. Verified corrections:
- There is **no `request_metrics` table**; the metrics read `conversation_messages` (admin.py:333/339/375).
  Its `session_id` is `nullable=False`, so the filter is a plain `session_id NOT LIKE 'qa-auto-%'`
  (no `OR IS NULL` — that clause is per-table; only nullable-session tables need it).
- `affiliate_ctr`/`travel_ctr` are **hardcoded `0.0` mock literals** (admin.py:366-369); `affiliate_clicks`
  is never queried. A filter there guards nothing today.
- `error_rate`/`top_errors` come from **Langfuse** (admin.py:246-290), not the DB — not filterable by
  a SQL session predicate. Langfuse caps at 100 traces, so heavy QA traffic could also hide real errors.
- v1 **missed `/metrics/chart`** (`get_chart_data` admin.py:430, `get_error_chart_data` :466) — same
  dashboard, no session filter.

## Corrected tasks
### C1 — Filter qa-auto from the DB aggregates (clean, do now)
In `admin.py`: add `AND session_id NOT LIKE 'qa-auto-%'` to the `conversation_messages` queries in
`get_metrics` (request_volume count ~L333/339, `top_queries.popular` ~L375-382) AND in
`get_chart_data` (~L440). All three read `conversation_messages` (session_id non-null). Acceptance:
seeding a `qa-auto-*` user message does not move request_volume, popular_queries, or the volume chart.

### C2 — Langfuse error metrics (the real gap)
Tag synthetic traces so they're filterable: in the per-request Langfuse handler
(`chat.py:_new_langfuse_handler`/:266), when `session_id` starts with `qa-auto-`, set the trace
session_id + `metadata={"qa_auto": true}`. Then in `fetch_langfuse_errors` (admin.py:246) and
`get_error_chart_data`, skip traces whose session/metadata marks them synthetic. **If the installed
Langfuse handler API does not cleanly support per-trace session/metadata tagging**, fall back to the
documented mitigation: cap QA error-producing chat traffic to ≤ a few requests/day (can't move the
count or crowd the 100-trace cap) and record the residual limitation in the run report. Decide at
implementation time by inspecting the handler API — do NOT force a fragile tagging hack.

### C3 — affiliate CTR (future-proof only)
Leave a `# QA: exclude session_id LIKE 'qa-auto-%' when real CTR is implemented` comment at the
hardcoded literals (admin.py:366-369). No functional filter now — it would be vacuous.

### C4 — DROPPED from this batch: rate-limit exemption
Rate limiting is OFF in prod and `check_rate_limit` keys on IP/JWT and never reads `session_id`
(dependencies.py:98-125) — the v1 exemption was structurally misplaced. Defer to whenever rate
limiting is actually enabled; then implement the `X-QA-Token` (constant-time compare) check in the
dependency, not the limiter. Documented, not built.

### C5 — Tests + note
`tests/test_qa_containment.py`: seed a qa-auto conversation_messages row → assert get_metrics volume
+ popular and get_chart_data exclude it. Note in the plan: the marker is client-controlled, which is
fine for the EXCLUSION path (a real user self-excluding from metrics is harmless); server-set
`is_synthetic` is future hardening, not needed now.

## Net: smaller + honest. C1 is the clean win; C2 is the one real subtlety (Langfuse), decided at
## build time; C3/C4 are documented deferrals, not code. Scope: admin.py + chat.py (C2) + new test.

---
# RECONCILED v3 — dual-model verify (Kimi K3 + GPT-5.6-sol, 2026-08-19)

Both reviewers agree C1 is the clean part; Sol pinned the hard parts precisely and found a
load-bearing flaw neither prior pass caught. Reconciled findings:

## Confirmed
- **C1 = exactly 4 SQL statements**, all `conversation_messages`, no hidden table: 1h count
  (admin.py:333), 24h count (admin.py:339), popular grouped (admin.py:375), chart bucket
  (admin.py:442). Add `AND session_id NOT LIKE 'qa-auto-%'` to all four. This part is safe.

## Sharpened / corrected
- **C2 Langfuse — v2's integration point was wrong (Sol).** `langfuse==3.9.1`; `CallbackHandler()`
  is bare (chat.py:130) and its ctor does NOT take session_id/metadata. Per-trace tagging must go
  through **LangGraph runnable metadata at BOTH astream calls (chat.py:460 AND :632)** via keys
  `langfuse_session_id` / `langfuse_tags`; with `update_trace=False` (default) arbitrary metadata
  won't stick — use tags or enable update_trace. AND: skipping AFTER `trace.list(limit=100)`
  (admin.py:247) does NOT stop QA traces crowding real ones out of the 100-row window — the filter
  must be **server-side in the list call or paginate the time window**; and `fetch_langfuse_errors`
  currently discards session/metadata (admin.py:285) so it must retain them to filter.
  → Given this real complexity, the **volume-cap fallback is now the default** for phase 1 (keep QA
  error-producing chat ≤ a few/day so it can't move counts or hit the cap); proper Langfuse tag-filtering
  is its own follow-up task, not blocking.

## NEW leak (Sol — missed by v2 and Kimi)
- **C3 must exclude qa-auto from `GET /conversations`.** Admin callers get every conversation's first
  user-message `content` + count; the qa-auto/ownership filter is applied ONLY to non-admin callers
  (chat.py:1136, content at :1151). Add the exclusion to the admin listing branch. (Separate
  pre-existing finding to log, NOT fix here: anon callers can request arbitrary session_ids without
  ownership check at chat.py:1095.)

## Operational guard (Sol)
- **C4 stays dropped, but the RUNNER must preflight `/health/ready`** (exposes `rate_limiting_enabled`
  via startup_manifest, health.py:114) and abort / expect 429s if rate limiting is ON. Repo+Docker
  DEFAULT is true (config.py:108, docker-compose.yml:105); prod is currently false — don't assume.

## HIGHEST RISK (Sol #5) — the marker is NOT stable across anonymous multi-turn, which defeats EVERYTHING
- When a supplied session already exists, an anonymous request that does NOT echo the returned
  `user_id` has its `session_id` **silently replaced with a random UUID** (chat.py:1338, :1357), and
  that UUID is persisted to `conversation_messages` (chat.py:1030) — so turn 2+ of a multi-turn QA
  script lands under a RANDOM session_id, NOT `qa-auto-*`, defeating every exclusion filter above.
- **MANDATORY runner contract (not app code):** the QA chat runner MUST capture the `user_id` from
  the done event (chat.py:949) and resend it (with the qa-auto session_id) on every subsequent turn.
- **Gate:** a multi-turn acceptance test must PROVE every persisted `conversation_messages` row for a
  QA multi-turn script retains the `qa-auto-` prefix. Until that passes, containment is not real and
  the loop must NOT run multi-turn chat against prod.

## Net build scope (backend, this batch)
C1 (4 filters) + C3 (/conversations admin branch) + a test module asserting exclusion incl. a
multi-turn-prefix-stability test. C2 Langfuse = volume-cap now + tagging as a follow-up. C4 = runner
preflight (runner code, later). The marker-stability finding is the true gate: the RUNNER must be
built to preserve the prefix, verified by test, before any multi-turn prod exercise.

---
# BUILD SPEC (implement exactly this — supersedes v1/v2 where they differ; v3 is the rationale)

Backend only. Keep `cd backend && python -m pytest -q` green (currently 985). Touch only the files
named. No auth/schema/migration changes. Every SQL edit is an additive WHERE filter.

## B1 — Filter synthetic QA traffic from the 4 conversation_messages aggregates (admin.py)
Add `AND session_id NOT LIKE 'qa-auto-%'` to each of these SELECTs (session_id is NOT NULL on
conversation_messages, so no OR-IS-NULL needed):
- the 1-hour request count (~L333)
- the 24-hour request count (~L339)
- the popular-queries grouped count (~L375)  [keep its existing GROUP BY/ORDER BY/LIMIT]
- the chart bucket count in get_chart_data (~L442)  [preserve the DATE_TRUNC + role='user' filter]
Do NOT touch the Langfuse error path or the hardcoded affiliate_ctr/travel_ctr literals. Leave a
one-line comment `# QA: synthetic (qa-auto-*) traffic excluded from user-visible metrics` at each.

## B2 — Exclude qa-auto from the GET /conversations admin listing (chat.py ~L1136)
The listing applies its session filter only for non-admin callers; the admin branch returns every
conversation's first-message `content`. Add: the admin listing must also exclude sessions whose id
is LIKE 'qa-auto-%' (synthetic content must never surface to a human via the dashboard). Match the
existing query style; do not change non-admin behavior or the response schema.

## B3 — Tests: backend/tests/test_qa_containment.py (new)
Follow the existing async test patterns (see tests/test_chat_api.py for the AsyncMock DB-session
pattern; the suite mocks the DB, so assert on the SQL text/params built, OR use the same fixture
approach sibling metric tests use — inspect how tests/ already tests admin metrics and match it).
Tests:
- (a) get_metrics's aggregate queries include the `qa-auto-%` exclusion predicate.
- (b) get_chart_data's query includes it.
- (c) the /conversations admin branch excludes qa-auto sessions.
- (d) a documentation test asserting the exclusion predicate string is exactly
  `session_id NOT LIKE 'qa-auto-%'` (guards against a future refactor silently dropping it).
If the suite's DB mocking makes asserting SQL text impractical, instead add a small pure helper in
admin.py (e.g. `_QA_EXCLUDE = "session_id NOT LIKE 'qa-auto-%'"`) used by all four queries and test
that constant is present in each query string — pick whichever is cleaner and say which you did.

## NOT in this batch (do not implement)
- Langfuse per-trace tagging (deferred; volume-cap handled runner-side).
- Rate-limit exemption / X-QA-Token (deferred; runner preflights /health/ready).
- The runner's user_id-resend contract (that's runner code in the P1 build, not the app).

---
# FIX ROUND (dual diff-review — Sol found a tautological test; code itself is correct)
The B1/B2 production changes are CORRECT and stay as-is (all 4 filters + /conversations verified,
991 tests pass). Fix ONLY the test quality so the tests genuinely guard the production predicate:

## FX1 — make the predicate production-owned (admin.py)
Add a module constant `_QA_EXCLUDE_PREDICATE = "session_id NOT LIKE 'qa-auto-%'"` in admin.py and
build the 4 aggregate SQL strings using it (f-string/concat into the `text(...)`), so there is ONE
source of truth. Behavior identical.

## FX2 — untautologize the tests (tests/test_qa_containment.py)
- The doc test (d) currently declares its own `QA_EXCLUDE_PREDICATE` literal and compares it to an
  identical literal — it passes even if every app filter is deleted. Instead: `from app.api.v1.admin
  import _QA_EXCLUDE_PREDICATE` and assert the 4 captured aggregate SQL strings EACH contain it
  (so deleting the filter from any query fails the test). Remove the self-comparing literal.
- The /conversations admin test (c) asserts only that `qa-auto-%` appears; an accidental inclusive
  `LIKE` would pass. Compile the statement with literal_binds and assert it contains `NOT LIKE`
  (case-insensitive) applied to session_id, not merely the pattern string.
Keep tests (a)/(b) as-is (already removal-sensitive). Do not change production behavior. Full suite
must stay green.
