# QA Loop P1 — the supervised runner spine (plan for dual-model /route verification)

**Scope of P1:** the operational spine + the six runners producing dated results, with supervision
(heartbeat + kill-switch), the runner-side marker contract that makes containment actually hold, a
minimal RingCentral notify, retention, and Windows Task Scheduler registration. **P1 is
REPORT-ONLY** — it writes raw results; the smart fingerprint/diff/digest is P2, auto-fix is P3.
Reference: QA-LOOP-DESIGN.md (v2) + QA-CONTAINMENT-PLAN.md (marker findings). Decisions locked in
memory reviewguide-qa-loop: human-gated, RC text to 5542, Supabase store (RLS, done), $10→$5/day,
beeep now / VPS later.

## Design constraints carried from the dual-verifies (non-negotiable)
- **Affiliate checks never follow the real outbound redirect** — assert the `<a href>` + the
  `/v1/affiliate/click` POST only.
- **Security probes rate-limited + preflight `/health/ready`** (reads `rate_limiting_enabled`); abort
  or expect 429 if limiting is ON. Never hammer prod.
- **Marker stability is the gate:** multi-turn chat MUST capture `user_id` from the done event and
  resend it every turn, or turn 2+ loses the `qa-auto-` prefix (server replaces session_id with a
  UUID) and bypasses containment. A post-run check must prove EVERY persisted row kept the prefix.
- **Portable** (beeep now, VPS later): runners are plain Python/Node + curl; Windows Task Scheduler
  is only the launcher (swap for cron on the VPS). No hard OS coupling in the runner logic.
- **UTF-8 pinned everywhere** (PS 5.1 mangles em-dashes in fingerprints/reports).
- **No secrets in the repo:** `qa/.env` (gitignored) holds the Supabase service key + RC creds
  pointer + optional QA token; `qa/config.json` holds only thresholds/URLs/toggles.

## Repo layout (new `qa/` tree)
```
qa/
  config.json            # targets (prod URLs), thresholds, cadence, cost caps — NO secrets
  .env                   # GITIGNORED — SUPABASE_QA_KEY, RC pointer, QA_BYPASS_TOKEN (opt)
  DISABLED               # kill-switch sentinel (absent = enabled); checked by every entrypoint
  run.ps1                # the single supervised entrypoint
  heartbeat-check.ps1    # dead-man's switch (separate task; alerts if no run by 08:00)
  lib/
    marker.py            # qa-auto session_id mint + user_id-resend chat helper + breach check
    store.py             # write runs/findings/heartbeats to Supabase qa.* (mgmt API, curl/UA)
    notify.py            # RingCentral SMS to 5542 (calls me\morning-brief\bin\ringcentral.ps1)
    flake.py             # 3/3-failure gate + fingerprint (sha1(dimension+check+locus))
  runners/
    api_suite.py         # canonical chat scripts, provider-honesty, security probes (marker-safe)
    unit_suite.py        # backend pytest + frontend tsc/vitest (LOCAL, no prod)
    browser_qa.py        # thin wrapper -> qa/playwright
    lighthouse.py        # lhci / chrome headless a11y+SEO+BP+perf on / and /chat
    data_integrity.py    # Supabase reconciliation, kv/TTL/sweeper, click session_id
    deps_audit.py        # npm audit --omit=dev + advisory classification
  playwright/            # committed headless browser checks (Discover, chat, mobile 390px, affiliate-assert-no-redirect)
    package.json  checks.spec.ts  playwright.config.ts
  runs/<run-id>/         # GITIGNORED — artifacts: screenshots, lighthouse html, raw runner JSON
.gitignore += qa/.env, qa/DISABLED, qa/runs/
```

## Tasks
### P1-1 — Marker contract + breach check (`qa/lib/marker.py`) — BUILD FIRST, it gates everything
- `mint_session()` → `qa-auto-<utc>-<rand>` (rand varies per turn/run; time passed in, never Date.now in-loop).
- `chat_turn(session_id, message, user_id=None)` → POST /v1/chat/stream, parse the done event, RETURN
  the `user_id` it assigned (chat.py:958). Caller threads that user_id into the next turn.
- `assert_marker_intact(session_id)` → query Supabase: every `conversation_messages` row for this
  session has session_id LIKE 'qa-auto-%'. Returns pass/fail; a FAIL is a CONTAINMENT BREACH →
  abort the run + HIGH alert. This is the test that must pass before ANY multi-turn prod exercise.
- Unit test with a mocked chat endpoint proving a 2-turn convo keeps the prefix when user_id is
  resent, and FAILS (detected) when it is not.

### P1-2 — Supabase store (`qa/lib/store.py`)
Write to the existing `qa.runs` / `qa.findings` / `qa.heartbeats` tables (project qvowmjjcotdonezdtvur,
RLS on, service-role). `start_run(run_id, host)`, `beat(run_id)`, `record_finding(fp, dim, sev,
summary, locus, status)`, `finish_run(run_id, counts)`. Idempotent upsert on fingerprint. Uses the
Cloudflare-UA workaround (curl or browser UA) per memory supabase-mgmt-api-cloudflare-ua. Key from
qa/.env, never logged.

### P1-3 — Notify (`qa/lib/notify.py`)
Send one SMS to 310-951-5542 via `me\morning-brief\bin\ringcentral.ps1` Send-RcSms. P1 sends: (a)
run-complete summary (counts), (b) run-FAILED alert, (c) CONTAINMENT-BREACH alert (from P1-1).
Cadence from config: week-1 aggressive (every run), then mild (once/day). Digest discipline lands in
P2; P1 keeps it minimal. Never texts prospects, Habib-only.

### P1-4 — The six runners (`qa/runners/*.py`)
Each: read config, run its checks with the 3/3 flake gate (qa/lib/flake), write findings via store,
drop artifacts to runs/<run-id>/. api_suite + browser_qa use the marker contract. api_suite security
probes are rate-limited + preflight /health/ready. browser_qa affiliate check asserts href + click
POST but never follows the redirect. unit_suite runs the LOCAL suites (backend pytest via the WSL
venv, frontend tsc). Each runner is independently runnable for debugging.

### P1-5 — Playwright checks (`qa/playwright/`)
Headless committed checks reproducing the manual browser sweep: Discover 0-console-err, search→chat
handoff, clarifier chip resume, 5-card render, saved/compare, mobile 390px no-horizontal-scroll,
touch-target >=44px, affiliate link assert (NO navigation). Browsers PRE-INSTALLED (documented setup
step; no first-run download in the scheduled window). Config pins base URL from qa/config.json.

### P1-6 — Supervised entrypoint (`qa/run.ps1`)
1. If `qa/DISABLED` exists → exit 0 immediately (kill-switch). 2. Mint run-id (timestamp arg).
3. start_run + first heartbeat. 4. Run the six runners with per-runner timeouts; beat between each.
5. On marker breach from api_suite → abort remaining prod runners, alert, mark run failed. 6.
finish_run with counts; write runs/<run-id>/SUMMARY.txt (raw, human-readable). 7. notify. UTF-8
output encoding pinned. Runs whether-logged-on-or-not concerns documented.

### P1-7 — Dead-man's heartbeat (`qa/heartbeat-check.ps1`)
A separate small task at 08:00: if `qa.heartbeats` has no completed run for today → SMS alert
"QA loop did not run." Silence is the worst failure mode; this is the supervisor.

### P1-8 — Task Scheduler registration (`qa/install-tasks.ps1`)
Register two tasks via the fleet's hidden-launch.vbs pattern: `RG-QA-Run` (daily, the entrypoint)
and `RG-QA-Heartbeat` (daily 08:00). "Run whether user is logged on or not," stored creds, node/npm
+ python on the task account PATH verified, working dir pinned. A matching `uninstall-tasks.ps1`.
Idempotent. Document the one-time Playwright browser install + PATH prerequisites.

### P1-9 — Retention + cost guard
Prune `qa/runs/` older than 30 days (in run.ps1 or a weekly task). api_suite caps chat-exercise
prompts per day (config, default small) so LLM spend stays under the $10/day week-1 cap; log
estimated spend into qa.runs.notes.

## Gates / acceptance (P1)
- `qa/run.ps1` completes a full local dry-run (config `dry_run: true` skips prod writes) and writes a
  run row + heartbeats + a SUMMARY, with the kill-switch honored.
- Marker breach check (P1-1) unit test passes AND a real 2-turn prod exercise proves every persisted
  row kept the `qa-auto-` prefix.
- One real RC SMS delivered to 5542 from a run.
- Backend suite still green (P1 adds no app code; unit_suite just RUNS it).
- No secrets in git; qa/.env + qa/runs/ + qa/DISABLED gitignored.

## Explicitly NOT in P1
- Fingerprint DIFF classification (NEW/OPEN/FIXED/REGRESSED) + digest discipline → P2.
- Any LLM planning / auto-fix / PR-opening → P3 (gated on P2 soaking ~2 weeks).
- Langfuse trace tagging, rate-limit exemption backend work (deferred earlier).

---
# REVISED v2 — dual-model verify (Kimi K3 + GPT-5.6-sol, 2026-08-21) — both said REVISE, CONVERGED on #1

## CRITICAL (both reviewers, independently) — the breach check is blind to its own breach
`assert_marker_intact(session_id)` as written queries the pristine `qa-auto-*` id — but the failure
mode PERSISTS breached rows under a NEW UUID (chat.py:1059/1352-1361), so the query finds only turn 1
and passes VACUOUSLY while containment is broken. FIX — a green requires ALL of:
  (a) row count for the qa-auto session == expected turns,
  (b) NEGATIVE scan: zero conversation_messages rows for the returned user_id under any
      non-`qa-auto-%` session_id within the run window,
  (c) the qa-auto session's rows all carry the prefix.
Any of these failing = CONTAINMENT BREACH → abort + HIGH alert. This is P1's true gate.

## Marker discipline (Kimi #1/#4, Sol #5)
- ONE session per conversation; `rand` varies per CONVERSATION, not per turn; `user_id` from the done
  event threaded into EVERY subsequent turn.
- `api_suite` runs conversations STRICTLY SEQUENTIALLY. Parallelizing turns of one conversation (or
  reusing a user across concurrent convos) detonates the UUID-swap race. This DELIBERATELY overrides
  QA-LOOP-DESIGN's "parallel fleet" — write it down; parallelizing api_suite is FORBIDDEN.
- The real gate is a **live 2-turn prod proof** (assert_marker_intact against real persistence), and
  **P1-4's prod runners are BLOCKED until it passes** — a mock only proves the runner SENDS user_id.

## Build sequence fixed + missing tasks added (Sol #4)
New **P1-0 scaffolding FIRST:** config.json, gitignored .env + ACL, .gitignore entries (and verify
nothing is already tracked; block `git add -f`), dependency pinning, `lib/flake.py`, the cost cap.
Then order: P1-2 store + P1-3 notify → P1-1 marker (needs store/notify for its alert) → P1-5
Playwright → P1-4 runners (api_suite BEFORE browser_qa; both blocked on the live marker proof) →
P1-6 entrypoint → P1-7 heartbeat → P1-8 tasks → P1-9 retention. Cost cap precedes any prod exercise.

## Windows unattended hardening (Kimi #5, Sol #6) — add to P1-8 + an acceptance test
`WakeToRun` + `StartWhenAvailable` + allow-on-battery; ABSOLUTE paths for node/npm/npx/python/curl/
pwsh/wsl.exe (interactive PATH is absent under the task account); pin `PLAYWRIGHT_BROWSERS_PATH`
(browsers may be in another user's cache); pin cwd (default is System32 → breaks the relative RC
path); verify the WSL distro + rgvenv exist under the task account; ensure `hidden-launch.vbs`
PROPAGATES the child exit code (it can swallow it → Scheduler shows false success); exec-policy under
the stored-cred account; "Log on as a batch job" right; stored-password expiry. **Acceptance:** an
install test that launches both tasks UNDER THE ACTUAL TASK ACCOUNT, waits, checks `LastTaskResult`
+ real artifacts + a completed-run heartbeat. NB: if beeep is off, the same-box 08:00 heartbeat
ALSO can't fire — documented limitation until the VPS move (VPS/cron solves it).

## Secrets hardening (Kimi #6, Sol #7)
- ACL-restrict `qa/.env`; never pass secrets as process/task ARGUMENTS (Scheduler + shell history
  leak them); use secure credential handling for task registration.
- **No auth headers in artifacts:** disable Playwright trace/HAR (or scrub), no `curl -v` header dumps,
  centralized recursive redaction on all runs/<id> output.
- Secret-scan acceptance gate over tracked files AND artifacts before any push. Verify + pin the
  external RC script path (me\morning-brief\bin\ringcentral.ps1) at install.

## Store = immutable observations, not overwriting upserts (both #8) — SCHEMA CHANGE
The existing `qa.findings unique(fingerprint)` would OVERWRITE prior-run observations and destroy the
history P2 needs. Change P1-2 to write IMMUTABLE per-run observations keyed `(run_id, fingerprint)`
(add a `qa.observations` table or make findings' unique key composite), and add a `runner_version`
column so a runner-version bump resets P2's baseline instead of poisoning it. Lifecycle
classification (NEW/OPEN/FIXED/REGRESSED) stays deferred to P2.

## Scope note (Sol #8)
"Report-only" is honest for reads, but browser saved/compare + affiliate click POST DO write. Those
synthetic writes must be qa-auto-tagged, isolated, and reconciled (listed in a per-run manifest for
pruning) — same containment as chat. Playwright touch-target check REUSES `frontend/playwright.config.ts`
device profile (Kimi #9), not a second 390px source of truth.

## Verdict: REVISE accepted in full. Rebuild order + the breach-check fix + immutable observations are
## the load-bearing changes. After these, P1 is buildable safely.

---
# FOUNDATION BUILD SPEC (increment 1 of P1 — build EXACTLY this; runners/entrypoint/tasks are later increments)
Python 3.11 (matches backend). Pure library code + unit tests with MOCKS ONLY — NO real prod/Supabase
calls in this increment. Create under `qa/`. Follow v2 revisions above.

F0 — Scaffolding:
- `qa/config.json`: {"prod_backend":"https://backend-production-0ae7.up.railway.app","prod_frontend":"https://www.reviewguide.ai","supabase_ref":"qvowmjjcotdonezdtvur","dry_run":true,"cadence":"aggressive","daily_usd_cap":10,"chat_prompts_per_day":6,"flake_retries":2} — NO secrets.
- `qa/.env.example` (NOT .env): documents SUPABASE_QA_KEY=, RC_SCRIPT_PATH=, QA_BYPASS_TOKEN= . Do NOT create qa/.env.
- `.gitignore` (repo root): append `qa/.env`, `qa/DISABLED`, `qa/runs/`. Verify none already tracked.
- `qa/lib/__init__.py`.

F1 — `qa/lib/flake.py`: `fingerprint(dimension, check, locus) -> sha1 hex`; `run_with_retries(fn, retries)` returning FAIL only after N+1 consecutive failures (default from config), else PASS; tracks attempt count. Pure, unit-tested.

F2 — `qa/lib/store.py`: functions start_run/beat/record_observation/finish_run that BUILD the SQL/HTTP payloads for Supabase qa.* but take an injectable `executor` (so tests pass a fake). record_observation writes IMMUTABLE rows keyed (run_id, fingerprint) + a runner_version arg (per v2). Reads key from env `SUPABASE_QA_KEY`, never logs it. Uses a browser User-Agent header (Cloudflare-UA workaround). No network in unit tests.

F3 — `qa/lib/marker.py` (THE critical piece — implement the v2 corrected breach check):
- `mint_session(now_iso, rand)` -> `qa-auto-{now_iso}-{rand}` (both passed in; never Date.now/random inside).
- `chat_turn(post_fn, session_id, message, user_id=None)` -> calls injectable post_fn, parses the done event, returns (assistant_ok, returned_user_id). Caller threads returned_user_id into the next turn.
- `assert_marker_intact(query_fn, session_id, expected_turns, user_id, window_start)` -> returns (ok, reason). GREEN requires ALL: (a) count of qa-auto rows for session == expected_turns, (b) NEGATIVE scan via query_fn finds ZERO conversation_messages rows for `user_id` under any non-`qa-auto-%` session_id since window_start, (c) all the session's rows carry the prefix. Any miss -> (False, reason). query_fn injectable.
- Docstring: api_suite MUST run conversations sequentially; one session per conversation; user_id threaded every turn.

F4 — `qa/lib/notify.py`: `send_sms(runner, text, kind)` where runner is an injectable callable (real impl shells to RC_SCRIPT_PATH Send-RcSms; tests pass a fake). kinds: run_complete, run_failed, breach. Never logs creds. Habib-only.

F5 — Tests `qa/tests/` (pytest): flake gate (passes on transient, fails on 3/3); fingerprint stable+distinct; store builds correct immutable payloads incl runner_version; **marker: a 2-turn convo that threads user_id stays intact (green); a 2-turn convo that does NOT thread user_id and lands turn-2 under a UUID is DETECTED (red) — including the negative-orphan-scan path**; notify routes each kind. All mocked, no network.

Gate: `cd qa && python -m pytest tests/ -q` green. No qa/.env created. .gitignore updated. Print files changed + the marker red-path test name proving the breach is caught.

---
# INCREMENT 2 — BUILT + REVIEWED 2026-08-22 (Claude build; route waived for P1 by Habib)
Status: DONE, 73 qa tests green. Built by Claude under ultracode; adversarially reviewed by a
5-lens Claude workflow (containment/python/spec/tests/frontend) → 38 confirmed findings → 18
distinct defects, ALL FIXED. Two containment-critical fixes independently re-verified against the
live backend:
  - CRITICAL SSE parser: the first parser only read `data:` lines + inferred type from an inline
    `type` key, but the real backend puts the type on the `event:` line (event: done\ndata:{...},
    no type key). It would have returned user_id=None on prod → fired turn 2 unthreaded → caused
    the exact containment breach on the live site. FIXED (marker._parse_stream_full now honors
    `event:` framing, matching chatApi.ts) + test mocks rewritten to the real wire shape.
  - CRITICAL orphan scan: conversation_messages has NO user_id column, so the user_id-based scan
    would 400 forever AND couldn't attribute the re-key (lands under a new user). REDESIGNED to a
    CONTENT scan: api_suite embeds "[qa-ref:<qa-auto-session>]" in each probe message; a leaked row
    carries that marker under a non-qa-auto session. Verified the backend persists the raw message
    verbatim as content.
Other fixes: crash→EXIT_BREACH (not CRASH) so findings/alerts survive; turn-2 refused if no user_id
captured; marker settle-poll for the fire-and-forget save race; oversized probe carries a qa-auto
session id; browser_qa env whitelisted + stdout redacted; non-zero-exit-with-no-failures = finding;
Playwright: global default-deny network lockdown, history-restore seeding (localStorage seed is
wiped by switchToSession), qa-auto-pw session-id assertion, mobile forced onto chromium.
OPEN (needs a live run to validate, not blockers to commit): the Playwright specs are DELIVERED but
unexecuted (need npm ci + playwright install); the live marker gate (--prove-marker) still requires
the Supabase key on this box.

# INCREMENT 2 BUILD SPEC (P1-5 Playwright + P1-4 api_suite/browser_qa + observations DDL — build EXACTLY this)

Python 3.11, STDLIB ONLY (urllib/json/time/argparse — no requests/httpx). All new code under `qa/`
(+ two `.gitignore` lines). DO NOT modify anything in `frontend/` or `backend/` — read them freely.
DO NOT run npm install, DO NOT execute qa/sql/*.sql, DO NOT make any network call to prod from tests.
Unit tests are MOCKS ONLY. Follow the injectable-dependency style already used in qa/lib/*.

## Verified facts to build against (scouted 2026-08-22 — cite-checked, trust these)
- Frontend session id: localStorage key `chat_session_id`; ChatContainer.tsx:202-207 DELETES it on
  mount unless it matches a UUIDv4 regex — BUT `/chat?session=<raw>` (app/chat/page.tsx:115-126)
  bypasses the regex, writes the raw value to localStorage, and ChatContainer uses it unchecked.
  This is THE containment lever for browser flows: enter via `/chat?session=qa-auto-<...>`.
- Affiliate anchors (ProductCarousel.tsx:190-203, ProductReview.tsx:419-445): `target="_blank"`,
  onClick does `e.preventDefault()` then `trackAffiliateClick` (lib/trackAffiliate.ts:16-37) which
  POSTs `{provider, product_name?, category?, url, session_id}` to `/v1/affiliate/click`
  (session_id lazily read from localStorage `chat_session_id`) and then `window.open(url,'_blank')`
  (trackAffiliate.ts:36) — navigation is a POPUP, not an anchor nav.
- POST /v1/chat/stream body (chat.py:138-144): message (1..5000 chars), session_id (any str),
  user_id (int, reused only if it maps to an ANONYMOUS user), country_code, action. SSE `done`
  event (chat.py:949-970) carries: session_id, user_id, completeness, response_metadata
  (with provider_coverage per-provider status / missing_sources / degraded), ui_blocks, followups.
  `provider_errors` is NOT top-level; degradation shows as completeness != "full" and
  provider_coverage entries with status "error"/"timed_out".
- GET /health → 200 always, fields: status, database, redis, version (= git sha).
  GET /health/ready → {status, manifest, timestamp}; rate limiting flag is
  `manifest.rate_limiting_enabled`. 503 possible when degraded — treat as "abort probes".
- Admin endpoints expected to reject unauthenticated: GET /v1/admin/config, GET /v1/admin/metrics,
  GET /v1/admin/users (401); GET /v1/admin/qos/summary (401/403).
  KNOWN GAP: GET /v1/admin/metrics/errors/chart currently has NO auth (admin.py:478-482) and
  returns 200 — probe it expecting 401/403 so it produces a HIGH finding. Do NOT fix the backend.
- CORS rejection is Starlette-style: disallowed Origin → response WITHOUT
  Access-Control-Allow-Origin header (preflight 400), NEVER 403. Probe the header's absence.
- Oversized chat message: 5001 chars → 422.
- frontend/playwright.config.ts is the device source of truth: projects `chromium-desktop`
  (Desktop Chrome, 1440x900) and `chromium-mobile` (devices['iPhone 14 Pro']). Mirror EXACTLY
  those two project definitions (comment pointing at frontend/playwright.config.ts).

## I2-0 — Scaffolding
- qa/config.json: ADD keys `"marker_gate_proven": false`, `"security_probe_interval_s": 1.5`,
  `"runner_version": "1"` (keep existing keys untouched).
- qa/lib/envfile.py: `load_env(path)` — parse KEY=VALUE lines (ignore blanks/#), set into
  os.environ only if not already set. No secrets logged. Unit-tested with a tmp file.
- qa/lib/httpio.py: the REAL executor + query_fn implementations, all built on urllib:
  - `execute(request)` — takes the dict shape store.py builds ({method,url,headers,query,json}),
    urlencodes query, sends, returns {"status": int, "json": parsed-or-None}. Raises on transport
    error. NEVER logs headers (they carry the service key).
  - `sse_post(url, payload, timeout_s)` — POST JSON, stream the response, return the list of raw
    lines (marker._parse_stream consumes them).
  - `pg_rest_query(kind, params)` — the real query_fn for marker.assert_marker_intact, over
    PostgREST with Accept-Profile: public, service key from SUPABASE_QA_KEY, browser UA (reuse
    store.USER_AGENT): kind "rows_for_session" → GET /rest/v1/conversation_messages
    ?select=session_id&session_id=eq.<id>; kind "orphan_scan" → GET /rest/v1/conversation_messages
    ?select=id,session_id&user_id=eq.<user_id>&created_at=gte.<window_start>&session_id=not.like.qa-auto*
    Any HTTP error → RAISE (the caller treats an exception as gate-NOT-passed; never silently green).
  - Unit tests: request building + query-string encoding only (executor injected/mocked, no network).
- qa/sql/0002_observations.sql (FILE ONLY — never executed by code or tests):
  CREATE TABLE IF NOT EXISTS qa.observations (id bigint generated always as identity primary key,
  run_id text not null, fingerprint text not null, dimension text not null, severity text not null,
  summary text not null, locus text, status text not null, runner_version text not null,
  created_at timestamptz not null default now(), unique (run_id, fingerprint));
  ALTER TABLE qa.observations ENABLE ROW LEVEL SECURITY;  -- no policies: service-role only
- .gitignore: append `qa/playwright/node_modules/`, `qa/playwright/test-results/`.

## I2-1 — Runner protocol (qa/runners/__init__.py + qa/runners/_base.py)
- `RunnerContext`: config dict, run_id, artifacts_dir, executor (store), post_fn/query_fn
  (marker), sleep_fn, now_fn — ALL injectable, real defaults from httpio/time. A `dry_run` ctx
  never touches network: post_fn/query_fn/executor raise if called (tests prove it).
- `finding(dimension, check, locus, severity, summary, status)` helper → dict + fingerprint via
  qa/lib/flake.fingerprint.
- `emit(ctx, findings)`: write `<artifacts_dir>/<runner>.json` (UTF-8, ensure_ascii=False) AND, when
  not dry_run, store.record_observation per finding with runner_version from config.
- Exit-code contract (each runner is `python -m runners.<name> --run-id X --artifacts-dir DIR`
  runnable from qa/): 0 = completed (findings or not), 2 = crashed, 3 = CONTAINMENT BREACH.
  Each runner loads qa/.env via envfile if present.
- Artifact redaction rule: nothing written to artifacts may contain an Authorization/apikey header
  or any env secret value — grep-style unit test over emitted sample artifacts.

## I2-2 — qa/runners/api_suite.py (marker-gated, STRICTLY SEQUENTIAL)
- HARD GATE at entry for any real chat exercise: refuse (finding "marker-gate-unproven", exit 0,
  zero prod chat calls) unless config `marker_gate_proven` is true. `--prove-marker` mode is the
  ONLY exception: it runs EXACTLY ONE 2-turn conversation live, then assert_marker_intact via the
  real query_fn; on green it prints MARKER_GATE_GREEN + instructions to flip config; on ANY failure
  or exception it exits 3 with a breach/failed report. It does NOT flip config itself.
- Conversations (only when gated open, and capped by config chat_prompts_per_day): C1 espresso
  machine 1-turn (assert done event + completeness field + >=1 products ui_block); C2 cordless
  vacuum clarifier 2-turn halt→resume; C3 robot vacuum 2-turn follow-up. One mint_session per
  conversation (rand varies per conversation), user_id from turn-1 done threaded into turn 2 —
  sequential, NEVER concurrent (module docstring states parallelizing is FORBIDDEN).
- After conversations: assert_marker_intact per conversation (real query_fn); any fail → exit 3,
  breach finding, and the summary marks the run failed.
- Provider honesty check on every done event: completeness key present; if any provider_coverage
  entry has status error/timed_out then completeness != "full", else finding (dimension
  "provider-honesty", severity high).
- Security probes (always run, even when marker gate is closed — they are single stateless
  requests, not conversations): preflight GET /health/ready first — on 503/unreachable, skip
  probes with an INFO finding; read manifest.rate_limiting_enabled and tolerate 429s when true.
  Probes, spaced `security_probe_interval_s` apart via ctx.sleep_fn:
  1-4. the four admin endpoints above expecting 401/403 (a 200 → HIGH finding, esp. errors/chart);
  5. POST /v1/chat/stream 5001-char message → expect 422 (this is a rejected request, no chat);
  6. OPTIONS /v1/chat/stream with Origin https://qa-evil.invalid + Access-Control-Request-Method:
     POST → expect NO Access-Control-Allow-Origin in response headers.
- dry_run=true: NO network at all — emit a skipped summary artifact (tests prove post_fn/query_fn
  never called).
- Estimated spend note (prompt count) appended to the summary artifact.

## I2-3 — qa/playwright/ (Tier A only — ZERO real chat, ZERO real outbound affiliate traffic)
- package.json: `{"private": true, "devDependencies": {"@playwright/test": "1.50.0"}}` (exact pin),
  scripts: `"test": "playwright test"`. No install step performed by you.
- playwright.config.ts: baseURL from env BASE_URL (default https://www.reviewguide.ai — comment:
  qa/config.json prod_frontend is the source; browser_qa passes it in), the two mirrored projects,
  `trace: 'off'`, `video: 'off'`, screenshot only-on-failure, outputDir from env QA_RUN_DIR
  (default ./test-results). NO trace/HAR ever (secrets rule).
- fixtures/: SSE stream fixtures derived from chat.py's real event builder shapes + what
  frontend/lib/chatApi.ts parses — `stream-5cards.txt` (status events + done with ui_blocks
  containing a products carousel of 5 items incl. affiliate_link fields) and
  `stream-clarifier.txt` (halt/clarifier done with chips + a resume done). Keep fixtures honest to
  chatApi.ts's parser (data: lines).
- checks.spec.ts — every test that opens /chat enters via `/chat?session=qa-auto-pw-<runid>-<n>`;
  route-mock `**/v1/chat/stream` to fulfill from fixtures (content-type text/event-stream) so NO
  real chat request ever leaves; also route-abort any request to non-reviewguide.ai hosts except
  the backend origin. Tests:
  A1 Discover `/` loads, console clean (fail on console errors minus an explicit small allowlist
     for known nav-abort noise; allowlist documented inline);
  A2 search input on Discover navigates to /chat and auto-submits (mocked stream renders);
  A3 5-card render from stream-5cards fixture (assert 5 product cards);
  A4 clarifier chips render + chip click resumes (stream-clarifier fixture);
  A5 affiliate assert: from the mocked 5-card state, intercept POST **/v1/affiliate/click and
     ABORT it after capturing the payload; click a card CTA; assert (i) anchor href is a plausible
     affiliate URL, (ii) the click POST fired with session_id starting `qa-auto-pw-`, (iii) any
     popup/external nav was blocked (context route-abort on amazon/ebay/external hosts) — the
     window.open at trackAffiliate.ts:36 must never reach the network;
  A6 saved/compare: seed localStorage saved items (same shape smoke.spec.ts uses), open /saved and
     /compare, assert cards render;
  A7 mobile (chromium-mobile project): /chat mocked 5-card state has NO horizontal scroll
     (documentElement.scrollWidth <= clientWidth) and every visible interactive control in the
     chat composer + clarifier chips has bounding box >= 44x44 px.
- README.md (short): one-time `npm ci` + `npx playwright install chromium` note,
  PLAYWRIGHT_BROWSERS_PATH note for the scheduled-task account.

## I2-4 — qa/runners/browser_qa.py
- Thin wrapper: builds the `npx playwright test` invocation (cwd qa/playwright) with env
  BASE_URL=config prod_frontend, QA_RUN_DIR=<artifacts_dir>/playwright, QA_RUN_ID=run_id;
  `--reporter=json` captured to <artifacts_dir>/playwright-report.json; parses it into findings
  (one per failed test, dimension "browser", locus = test title; severity medium). Subprocess
  runner injectable (tests mock it; no real npx in tests). dry_run → skip with artifact, no
  subprocess. Node/npx path taken from config key `"npx_path"` default "npx" (absolute path comes
  at install time). Timeout per config `"browser_timeout_s"` default 900 → add both keys to
  config.json.
- Tier B (real-chat browser E2E) is deliberately NOT here — deferred until after the live marker
  gate; leave a docstring note.

## I2-5 — Tests (qa/tests/, mocked only, pytest)
- test_api_suite.py: sequencing (two conversations run strictly one-after-another — assert via
  recorded call order), user_id threading turn1→turn2, marker-gate refusal (no post_fn call when
  marker_gate_proven false), --prove-marker green path + red path (orphan present → exit 3), probe
  spacing uses sleep_fn with configured interval, 200-on-admin → HIGH finding, CORS check keys off
  header absence, dry_run makes zero network calls, breach aborts remaining conversations.
- test_browser_qa.py: command/env construction, JSON report → findings mapping, dry_run skip.
- test_httpio.py + test_envfile.py + runner-protocol tests (exit codes via run() return, emit
  writes artifact + calls store per finding, redaction test).
- ALL existing 29 tests stay green.

Gate: `wsl pytest qa/tests -q` green (target: 29 + ~20 new). Print: files changed, test count,
and the names of (a) the marker-gate-refusal test, (b) the prove-marker red-path test.

---
# INCREMENT 3 BUILD SPEC (remaining runners + supervised spine — build AFTER Increment 2 is merged)

Same ground rules as Increment 2: stdlib-only Python, injectable deps, mocked tests, nothing
outside qa/, no installs, no prod calls from tests. PowerShell scripts MUST be Windows
PowerShell 5.1-compatible (beeep has NO pwsh 7): no `&&`, no ternary; pin UTF-8 via
`[Console]::OutputEncoding = [Text.Encoding]::UTF8` + `$OutputEncoding` at the top.

## Beeep facts (verified 2026-08-22 — bake in as config defaults, keep overridable)
- lighthouse CLI: `C:\Users\habib\AppData\Roaming\npm\lighthouse.cmd` (global install).
- node/npx: `C:\Program Files\nodejs\`; wsl: `C:\Windows\system32\wsl.exe`;
  PS 5.1: `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`.
- Backend tests: `wsl -d kali-linux -u root -- bash -c 'cd /mnt/c/Users/habib/projects/ReviewGuide/backend && /root/rgvenv/bin/python -m pytest -q'`.
- Frontend: `npm run test:run` (vitest) + `npx tsc --noEmit` (there is NO typecheck script), cwd frontend/.
- hidden-launch.vbs pattern that PROPAGATES exit codes (clone it, do not invent):
  `WScript.Quit shell.Run(cmd, 0, True)` (see C:\Users\habib\me\sam-qa\hidden-launch.vbs).
- Scheduler neighbors on beeep: SamQA 06:30, MorningBrief 07:57 → default run time 05:45,
  heartbeat check 08:00.

## I3-1 — qa/runners/unit_suite.py (LOCAL only, no prod)
Config-driven command list `unit_suite_cmds` (defaults = the three commands above, absolute
paths). Runs each via injectable subprocess runner with per-command timeout, captures exit code +
tail of output to artifacts, one finding per failed suite (dimension "unit", severity high).
dry_run still RUNS these (they are local and free) unless `dry_run_skip_local: true`.

## I3-2 — qa/runners/lighthouse.py
Targets `/` and `/chat` on prod_frontend, desktop+mobile presets, via lighthouse.cmd (config
`lighthouse_path`), `--output=json --quiet --chrome-flags="--headless=new"`, artifacts to
<run>/lighthouse/. Findings when: any category < 90 (medium), CLS > 0.1 or LCP > 4s (medium).
Parse defensively — a lighthouse crash is a finding (severity low, "lighthouse-unavailable"),
not a runner crash. Injectable subprocess runner; tests feed canned lighthouse JSON.

## I3-3 — qa/runners/deps_audit.py
`npm audit --omit=dev --json` in frontend/ (injectable runner). Findings: counts by severity;
severity high finding when high/critical > baseline config `deps_accepted_high` (default 8 — the
currently-known, Habib-deferred set), info finding otherwise listing counts. Artifact = raw JSON.

## I3-4 — qa/runners/data_integrity.py (needs SUPABASE_QA_KEY; skip cleanly without it)
Read-only PostgREST reconciliation (public schema, service key, browser UA):
(a) qa-auto sessions/messages/metrics counts consistent with each other (orphan messages without
a session row = finding); (b) kv_cache rows expired > 1h still present = sweeper finding (high —
the sweeper job should have pruned them); (c) affiliate_clicks rows with session_id LIKE
'qa-auto-%' listed into <run>/qa-writes-manifest.json (the prune manifest). No writes, ever.

## I3-5 — qa/run.ps1 (the single supervised entrypoint)
PS 5.1. Order: kill-switch (qa/DISABLED → exit 0) → load qa/.env (KEY=VALUE parser, no logging)
→ run-id `utc yyyyMMdd-HHmmss` → mkdir qa/runs/<run-id> → runctl start_run + beat → run runners
SEQUENTIALLY via `python -m runners.<name>` (config `python_path`), each with a per-runner
timeout (config `runner_timeout_s` default 900; kill on expiry = finding) — order: unit_suite,
deps_audit, api_suite, browser_qa, lighthouse, data_integrity; beat after each → exit-code 3
from api_suite = CONTAINMENT BREACH: skip remaining PROD runners (browser_qa, lighthouse,
data_integrity), send breach SMS immediately → aggregate runner JSONs into SUMMARY.txt (counts
by severity + failures list, UTF-8) → finish_run → notify (run_complete or run_failed per
cadence config) → retention: prune qa/runs/* older than `retention_days` (30). A tiny
qa/lib/runctl.py CLI (`python -m lib.runctl start|beat|finish --run-id X`) wraps store.* with the
real executor so PS never touches secrets beyond passing env. Cost cap: before api_suite, if
today's estimated spend (sum of `spend_estimate` in today's run summaries) >= daily_usd_cap →
skip api_suite chat with an INFO finding.

## I3-6 — qa/heartbeat-check.ps1 (dead-man switch, separate task)
PS 5.1. Query qa.heartbeats via `python -m lib.runctl last-beat`; if no beat today → Send-RcSms
"[qa:dead-man] QA loop did not run by 08:00" via RC_SCRIPT_PATH. Known limitation (documented):
same-box as the run task — if beeep is off neither fires; solved at VPS migration.

## I3-7 — Tests
Mocked: runner JSON parsing (lighthouse/npm-audit fixtures), unit_suite command building +
timeout finding, data_integrity reconciliation logic (fake query results incl. the orphan and
stale-kv red paths), runctl arg building. PS scripts get a syntax smoke only
(`powershell -NoProfile -Command "Get-Command -Syntax"`-style parse or documented manual step).

Gate: full qa pytest green; `qa/run.ps1` dry-run completes end-to-end on beeep writing a run dir
+ SUMMARY.txt with store/notify in dry mode; kill-switch honored (create qa/DISABLED → exit 0).

# INCREMENT 4 (last): qa/install-tasks.ps1 + uninstall + acceptance
Windows hardening per the v2 review: schtasks RG-QA-Run daily 05:45 + RG-QA-Heartbeat 08:00 via
cloned hidden-launch.vbs; WakeToRun, StartWhenAvailable, battery-allowed, absolute paths
everywhere, PLAYWRIGHT_BROWSERS_PATH pinned, cwd pinned to qa/, "run whether logged on or not"
with creds prompted at registration (NEVER passed as arguments), "Log on as a batch job" check,
exec-policy, WSL distro + rgvenv verified under the task account, acceptance test that launches
both tasks for real and checks LastTaskResult + artifacts + a completed-run heartbeat.
