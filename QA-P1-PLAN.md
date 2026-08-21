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
