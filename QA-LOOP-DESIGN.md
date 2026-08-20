# ReviewGuide Continuous QA Loop — design (for route-verification before build)

**Author:** Fable 5 (orchestrator). **Date:** 2026-08-19. **Status:** DRAFT → route-verify → build.
**Purpose:** a daily, cron-driven system that audits + tests + exercises every feature of
reviewguide.ai, saves a dated report each run, diffs against history, then plans and implements
fixes through the /route worker loop — with a human gate before anything touches production.

## Non-negotiable principles
1. **Prod is never auto-deployed.** The loop may auto-write + auto-test fixes on a branch; a human
   approves the merge/deploy. reviewguide.ai is a live revenue site — the same adversarial review
   that caught 2 Kimi bugs today must stay in the loop. Autonomy up to a green PR; human past it.
2. **Read-heavy on prod.** Runners exercise prod like a user (chat, clicks) but perform NO
   destructive writes; all synthetic traffic is tagged `qa-auto-*` and is reconciled/prunable.
3. **Cost-bounded.** Each daily run has a hard token/$ ceiling; the fixer only spends on SAFE,
   well-scoped findings and escalates the rest. No unbounded fix loops.
4. **Regression-aware, not just pass/fail.** Every finding has a stable fingerprint; the orchestrator
   diffs today vs the last run to classify NEW / STILL-OPEN / FIXED / REGRESSED.
5. **Idempotent + resumable.** A run writes to its own dated dir; a crash never corrupts history.

## Architecture
```
Windows Task Scheduler (daily)
        │
        ├─(1) run-audits.ps1  ── spawns the runner fleet in parallel ─┐
        │        ├ api-suite      (curl: canonical scripts, provider-honesty, security probes)
        │        ├ unit-suite     (backend pytest + frontend vitest/tsc)
        │        ├ browser-qa     (Chrome-MCP self-driven OR Playwright: functional + mobile + a11y)
        │        ├ lighthouse     (a11y/SEO/best-practices/perf, desktop+mobile)
        │        ├ data-integrity (Supabase row reconciliation, KV/sweeper, click session_id)
        │        └ deps-audit     (npm audit --omit=dev, pip/advisory scan)
        │              each writes runs/<DATE>/<dimension>.json  (+ raw artifacts)
        │
        └─(2) orchestrator (headless Claude Code, claude.cmd)
                 ├ ingest runs/<DATE>/*.json
                 ├ fingerprint findings; diff vs runs/<prev>/  → NEW/OPEN/FIXED/REGRESSED
                 ├ write runs/<DATE>/SUMMARY.md + update BACKLOG.md + history.jsonl
                 ├ SAFE findings → author PLAN.md → /route (Kimi) implements on branch
                 │     qa-auto/<DATE> → run gates → if green: open PR + notify
                 ├ HIGH/risky/ambiguous findings → escalate to REVIEW.md + Telegram/TODO
                 └ NEVER deploy; NEVER merge to main
```

## Runner fleet (each is a standalone script, no LLM = cheap + deterministic)
| Runner | Tool | Exercises | Output |
|---|---|---|---|
| api-suite | bash+curl | 5 canonical product scripts, multi-turn context, gibberish/degradation, provider-honesty (completeness downgrades), security (admin auth, oversize, CORS, no stack traces) | `api-suite.json` pass/fail + evidence |
| unit-suite | pytest / vitest / tsc | full backend suite, frontend type-check + tests | `unit-suite.json` counts + failures |
| browser-qa | **Chrome DevTools MCP driven by the orchestrator**, Playwright fallback headless in cron | Discover load (0 console err), search→chat handoff, clarifier chip resume, card render, saved/compare, mobile 390px no-h-scroll, touch-target sizes, affiliate click→row | `browser-qa.json` + screenshots |
| lighthouse | chrome-mcp lighthouse / `lhci` | a11y/SEO/BP/perf on / and /chat, desktop+mobile | `lighthouse.json` category scores + failing audits |
| data-integrity | curl→Supabase mgmt API | row growth reconciles to synthetic traffic; kv namespaces+TTL; sweeper deletes expired; click session_id non-null | `data-integrity.json` |
| deps-audit | npm audit / safety | high/critical advisories + fix availability (non-breaking vs major) | `deps-audit.json` |

**Chrome-MCP vs Playwright:** the browser tools need a live Chrome + extension, which exists in an
interactive session but NOT in a headless cron. So: the orchestrator, when it runs interactively,
drives Chrome-MCP directly; the unattended cron path uses a **Playwright** script (committed to the
repo, `qa/playwright/`) that reproduces the same checks headlessly. The design ships BOTH and the
runner picks based on whether a browser bridge is present.

## State / folder layout (the "dated files" feedback store)
```
ReviewGuide/qa/
  runs/
    2026-08-19/           # one dir per day
      api-suite.json  unit-suite.json  browser-qa.json  lighthouse.json
      data-integrity.json  deps-audit.json
      SUMMARY.md          # human-readable digest, NEW/OPEN/FIXED/REGRESSED
      artifacts/          # screenshots, lighthouse html, raw logs
  BACKLOG.md              # rolling open-findings list, severity-ranked
  history.jsonl           # append-only: {date, fingerprint, dimension, severity, status}
  REVIEW.md               # findings escalated to human (HIGH/risky)
  config.json             # ceilings, targets, which dimensions on, notify channel
```
Also mirrored to the vault (`ClaudeVault/status/reviewguide-qa/`) so it syncs across machines.

## Orchestrator fix policy (what it may auto-implement)
- **AUTO (branch only):** config/env-independent code fixes with a clear acceptance test —
  a11y/contrast, touch targets, SEO metadata, missing-auth dependency, honesty/coverage plumbing,
  null-field passthrough, non-breaking `npm audit fix`. Must land green on `qa-auto/<DATE>` + PR.
- **ESCALATE (never auto):** anything needing a secret/decision (eBay campid, CJ endpoint), a major
  dependency bump (Next.js majors), a schema/data migration, auth-model changes, or a finding whose
  fix the orchestrator can't verify with a test. → REVIEW.md + notify.
- **Every auto-fix PR is /route-built (Kimi) and Fable-reviewed** before the PR opens — the loop
  reuses today's exact discipline.

## Scheduling (Windows Task Scheduler on beeep)
- Task `RG-QA-Audit` daily 06:30 → `run-audits.ps1` (runner fleet, ~10-20 min).
- Task `RG-QA-Orchestrate` daily 07:00 → `orchestrate.cmd` (headless claude.cmd, reads runs, plans,
  route-fixes, opens PR, notifies). Launched via the fleet's `hidden-launch.vbs` pattern.
- Both env-gated by `config.json` (enable/disable, dry-run). WoL/quiet-hours honored.

## Cost controls
- Runners are LLM-free except the chat-exercise calls (bounded: N scripted prompts/day).
- Orchestrator: one planning pass + at most K route fix-rounds/day (K in config, default 3), Kimi K3
  (cheapest). Hard stop at a daily token ceiling; overflow findings roll to BACKLOG for tomorrow.
- Estimated: a few $/day at K=3; tunable down to report-only (K=0) for a pure watchdog.

## Rollout phases (each shippable + verifiable on its own)
- **P1 Runners + dated store** (no LLM, no auto-fix): the fleet + folder + SUMMARY diffing. Immediate
  value: a daily health/regression report. Lowest risk.
- **P2 Orchestrator report + escalation** (LLM read-only): ingest + fingerprint + BACKLOG + notify.
  Still no code changes.
- **P3 Auto-fix on branch + PR** (route/Kimi + Fable review): the self-improving loop, human-gated deploy.
- **P4 Cron registration + notify wiring:** schedule P1-P3, Telegram/TODO integration.

## Open decisions for Habib (before build)
1. **Prod-deploy gate:** human-approved PR (recommended) vs full auto-deploy (higher risk). Default: human.
2. **Notify channel:** Telegram (@J4Digitialbot chat) / TODO.md / email — which?
3. **Daily fix ceiling K** (auto-fix rounds/day) and the token/$ cap.
4. **Machine:** run on beeep (this box)? It must be awake at 06:30 (WoL or always-on).
```

---
# REVISION v2 — after /route adversarial verification (Kimi, 2026-08-19)

The review found the ambition sound but several load-bearing mechanisms unspecified, and 3 lines
actively dangerous on a live revenue site. Accepted changes below OVERRIDE v1 where they conflict.

## Safety-critical (must ship before ANY automated run)
1. **Affiliate clicks NEVER fire a real network redirect from automation.** Daily synthetic clicks
   on real eBay/Amazon/CJ links = the exact click-fraud pattern that gets affiliate accounts
   SUSPENDED. The browser-qa affiliate check hits a QA-only tracking endpoint (or asserts the
   `<a href>` + the `/v1/affiliate/click` POST WITHOUT following the outbound redirect). No exceptions.
2. **Prod-write containment.** A dedicated `qa-auto` identity; QA-tagged requests are server-side
   blocked from destructive writes; QA sessions/messages EXCLUDED from any user-visible aggregate
   (trending, analytics, memory). A reconciliation manifest lists every synthetic row for pruning.
3. **Security probes are rate-limited + carry a QA bypass token / origin allowlist** so daily
   admin-auth/oversize/CORS probes don't trip Railway/Cloudflare WAF and self-block the box's IP
   (which would red every other runner sharing that egress).
4. **Auth changes are ESCALATE-only, never AUTO.** Remove "missing-auth dependency" from the auto-fix
   list — an LLM auto-editing auth on a revenue site (reviewed only by another LLM) can lock out
   users or fail open. Anything touching auth, secrets, schema, data migration, or a major dep bump
   → REVIEW.md + notify, human implements.

## Supervision + trigger (replaces the two-clock cron)
5. **Single supervised entrypoint:** one scheduled task runs the fleet with per-runner timeouts,
   writes `fleet.done`, then invokes the orchestrator. No second clock.
6. **Dead-man's heartbeat:** the run writes a daily heartbeat; a separate tiny check alerts if no
   completed run by 08:00. A QA loop whose failure mode is SILENCE is worse than none.
7. **Kill-switch:** every entrypoint checks a `qa/DISABLED` sentinel first; creating that file (one
   command, or a Telegram command → queue) halts the loop immediately.

## Correctness of the loop itself
8. **git worktree off clean `origin/main`** for every run — NEVER the user's dirty checkout (today
   the tree is on `merge/qa-plus-prod-fixes` with live edits; a stray `git checkout -b` would sweep
   them in). Auto-fix branch = `qa-auto/<run-id>` (run-id, not just date, so same-day reruns don't
   collide); never force-push an open PR.
9. **Flake model (gates the whole diff engine):** a check is a FINDING only after 3/3 consecutive
   failures (2 retries); per-check flake rate is itself tracked. Diff is vs the last SUCCESSFUL run.
   Fingerprint = `sha1(dimension + normalized-check-id + normalized-locus)`; runner-version bumps
   reset the baseline. This is the difference between self-healing and a daily junk-PR generator.
10. **Findings/history live in a Supabase table** (single writer = beeep), not an append-only jsonl
    mirrored through Obsidian sync (which corrupts on stale cross-machine writeback). Files hold only
    dated artifacts (screenshots, lighthouse html); vault is read-only downstream.
11. **Browser = Playwright ONLY**, one committed source of truth in `qa/playwright/`. Chrome-MCP is
    for ad-hoc human-driven sweeps, NOT an automated runner (it can't run headless in cron and would
    drift from the Playwright checks). Pin: browsers pre-installed (no first-run download in Session 0),
    node/npm on the task account's PATH, task runs "whether user logged on or not" with stored creds.
12. **Secrets:** gitignored `qa/.env` (or Windows Credential Manager). `qa/config.json` holds NO
    secrets — thresholds/toggles/target URLs only. Add `qa/.env`, `qa/DISABLED`, `qa/runs/` to .gitignore.
13. **Alert digest discipline:** ONE message/day, only if (a) new HIGH, (b) REGRESSED, or (c) a PR
    awaits review. STILL-OPEN never re-notifies. Prevents month-one channel mute.
14. **Retention:** keep N days (default 30) of artifacts; prune older. Pin UTF-8 everywhere
    (PowerShell 5.1 default encoding mangles em-dashes in fingerprints/SUMMARY diffing).
15. **Headless claude in cron:** stored credentials for the task account + non-interactive permission
    flag (or it blocks forever burning the window); explicit cwd; captured UTF-8 output.

## Revised phase order (scaffolding first, soak longest; auto-fix last + gated)
- **P1 = runners + single entrypoint + heartbeat + kill-switch + notify skeleton + cron.** Ship the
  operational spine FIRST (it's the riskiest part) so P2/P3 failures are never silent. Value: a
  supervised daily health+regression report.
- **P2 = orchestrator read-only:** ingest, fingerprint, diff, BACKLOG, escalate, digest-notify.
- **P3 = auto-fix on branch + PR (route/Kimi + Fable review), human-gated deploy** — UNLOCKED only
  after P2 runs clean for ~2 weeks (fingerprint stability + low false-NEW/REGRESSED proven).

## Deploy gate: CONFIRMED human-gated (the review independently reached the same conclusion).
