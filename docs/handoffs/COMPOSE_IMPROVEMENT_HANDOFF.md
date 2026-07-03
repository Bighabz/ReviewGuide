# Compose Quality Initiative — Handoff (updated 2026-06-02)

> Paste this into a new Claude Code session to continue. Durable detail also lives in the
> auto-loaded `~/.claude/.../memory/` files (read them first):
> `project_compose_improvement_roadmap`, `project_compose_model_strategy`,
> `project_serper_credits_blocker`, `reference_railway_ops`, `reference_git_workflow_gotchas`.

## TL;DR
The moat is senior-editor prose (`frontend/design/uploads/tone.md`). Over two sessions we: swapped
the composer to **Haiku 4.5 via OpenRouter**, **grounded** it (tool_outputs/history/profile), added
**real review evidence** (A1) + **anti-hallucination** (A2), **two-speed** depth routing, a **voice
pass**, **richer personality memory**, and — when Serper.dev ran out of credits — a **cross-provider
failover to SerpApi.com** (two-key chain). An A/B **proved** evidence grounding lifts claim accuracy
2.0→5.0. Everything new is flag-gated **default-off**; the always-on path is unchanged + safe.

## Shipped & LIVE in prod (main ≈ `cc0bbab`)
| PR | What | Prod flag state |
|----|------|-----------------|
| #60 | A1: `review_search` in standard plan + `claim_support` judge dim | `USE_REVIEW_GROUNDING=true` ✅ on |
| #63 | Cross-provider failover Serper.dev→SerpApi.com + loud credit log + no-cache-on-error | `SERPAPI_FALLBACK_ENABLED=true` ✅ on |
| #65 | Google Shopping = **context-only** (price/img/rating), buy-links Amazon-only | always-on |
| #66 | Second SerpApi.com key chain | `SERPAPI_COM_API_KEY` + `_2` ✅ both set |
| #70 | A2: `USE_PRODUCT_VERIFICATION` drop unverifiable products | **default-off** (not enabled) |
| #71 | `USE_TWO_SPEED_COMPOSE` depth by complexity | **default-off** |
| #72 | `USE_VOICE_PASS` draft→revise | **default-off** |
| #74 | eval `--ungrounded` A/B flag + `eval/AB_claim_support.md` | n/a |
| #76 | richer `_profile_inject` (use-case/budget/features) | always-on (returning users) |

**Railway `backend` flags currently ON:** `USE_REVIEW_GROUNDING`, `USE_GROUNDED_COMPOSE`,
`ENABLE_SERPAPI`, `SERPAPI_FALLBACK_ENABLED`, `OPENROUTER_API_KEY`, `SERPAPI_COM_API_KEY`,
`SERPAPI_COM_API_KEY_2`. (`USE_OPENROUTER_COMPOSE` defaults true in code.)
**Live-verified:** a recommendation query returns real review ratings (4.3/4.5/4.7) + snippets via
the SerpApi.com fallback, with **0 Google-Shopping buy-links**.

## The A/B result (the payoff — `backend/eval/AB_claim_support.md`)
Haiku, judge Sonnet 4.6: **grounded 4.57 mean / claim_support 5.0** vs **ungrounded 2.57 / 2.0**.
Ungrounded, the model invents products that don't exist; grounded, every claim traces to evidence.
This is the data justifying A1's ~+8s and A2's verification backstop.

## NEXT — measure-then-enable the 3 default-off flags
Run `backend/eval/voice_eval.py` and/or live prod queries, then flip on Railway if they help:
1. `USE_PRODUCT_VERIFICATION` (A2) — hardens against residual hallucinations; near-zero latency cost. **Lowest-risk to enable next.**
2. `USE_TWO_SPEED_COMPOSE` — holds latency on quick queries; verify utility queries get terser prose.
3. `USE_VOICE_PASS` — adds ~1 compose round-trip; only enable if the revise pass measurably beats the draft (eval it first; Haiku already scores 4.77).

## Deliberately NOT shipped (reasoned holdouts)
- **Tier 2.1 streaming** — true token-streaming needs prose/JSON decouple + SSE restructure; it's
  quality-NEUTRAL (Haiku 4.77 in JSON), large, frontend-touching, risky. `generate_compose_with_streaming`
  is **dead code**; body streams post-hoc today. Treat as a scoped project, not a blind-ship.
- **Tier 5b full Honcho** — Honcho is NOT in the backend (MCP-only). `preference_service` (DB,
  keyed by user_id) already gives persistent memory → `profile_inject`. Honcho upgrade needs backend
  SDK + workspace + the anonymous-user keying gap resolved → needs your Honcho deployment.

## Open loops (non-tier)
- 🚩 **eBay**: `EBAY_CAMPAIGN_ID=1234567890` is the EPN PLACEHOLDER → live eBay buy-links earn $0.
  User is setting a real EPN campaign ID; once pasted, set `EBAY_CAMPAIGN_ID` on Railway + verify.
- 🔑 **SerpApi.com keys are free-tier (250 searches/mo EACH)** → will run dry under real traffic.
  Watch for the loud `[serpapi.com] all N key(s) exhausted` WARNING; then fund Serper.dev or add a paid key.
- 🔑 **Rotate**: OpenRouter key + both SerpApi.com keys are transcript-exposed (in `.env` + Railway).
- Serper.dev (primary) is still out of credits — the SerpApi.com fallback is carrying review+price evidence.

## Gotchas (don't relearn)
- **`main` is locked by a git worktree** (`reviewguide-review-consensus`) → can't `git checkout main`
  here. Branch off `origin/main` (`git checkout -b X origin/main`) and merge via `gh pr merge`.
- **gitleaks scans per-commit** in a PR. If a secret-shaped literal (e.g. `API_KEY="key2"`) lands in
  ANY commit, it fails even if a later commit removes it → squash history (`git reset --soft origin/main`
  + one clean commit + `git push --force-with-lease`). Use non-credential stub identifiers in tests.
- **Railway**: MCP goes stale → use the `railway` CLI via Bash (repo linked to reviewguide-backend/
  production). Prod var writes trip the safety classifier → need explicit user OK. Don't send one
  provider's key to another provider's API (classifier blocks it, correctly).
- **CI**: pytest is the hard gate; ruff/black are SOFT (don't run black). New checks exist: "Voice live
  compliance (gpt-4o-mini — prod-model gate)" + a non-blocking Claude one. Keep NEW code ruff-clean.
- **Windows bash `/tmp` is flaky** → write temp files to the repo dir. Commits unsigned (squash signs).
- **5-layer passthrough trap** for any new GraphState field (composer→validator→_extract_results→
  plan_executor_node→chat.py).
- `classify_query_complexity` is a pure <5ms heuristic → re-derive complexity in compose, no passthrough.

## Key files
- `backend/mcp_server/tools/product_compose.py` — the ~5-call fan-out; A2 prune, two-speed depth,
  voice pass (`_voice_revise_body`), `_profile_inject`, Google-Shopping context-only buy-links.
- `backend/mcp_server/tools/review_search.py` + `backend/app/services/serpapi/client.py` — review/price
  fetch; **client is Serper.dev with SerpApi.com failover** (despite the `serpapi/` dir name).
- `backend/app/agents/planner_agent.py` `_create_standard_product_plan` — A1 review_search insertion.
- `backend/app/core/config.py` — all the `USE_*` / `SERPAPI_*` flags.
- `backend/eval/` — bake-off harness + judge (`claim_support` dim, `--ungrounded`) + `AB_claim_support.md`.
- `backend/app/services/preference_service.py` — DB-backed personality memory (load/update/extract).
