# Compose Single-Call Consolidation — Handoff (PRIORITY: next session)

**Date:** 2026-06-03 · **Main:** `bbc117f` · **User directive:** "get rid of all the requests, keep one call/stream, on the best model (Sonnet candidate) — ASAP"
**Use:** feed this to `/goal` in a fresh session. This is **Tiers 2/3 of the compose roadmap** (`COMPOSE_IMPROVEMENT_HANDOFF.md`), updated with everything that changed since (PRs #99–#106) and with the **verified** current model routing.
**Companion:** `QA_ROUND8_HANDOFF.md` (the other open work — smaller items, lower priority than this).

---

## Part 0 — The verified current state (do NOT re-discover; checked 2026-06-03)

### What model actually writes what (this confuses every session — here is the truth)

`model_service.generate_compose()` routing, in priority order:

1. **OpenRouter route** — `USE_OPENROUTER_COMPOSE` (default **true** in code) + `OPENROUTER_API_KEY` (✅ set on Railway) → **ALL prod compose calls run on `OPENROUTER_COMPOSE_MODEL` = `anthropic/claude-haiku-4.5`** (the bake-off winner, 4.77). Handles json_object (strips md fences).
2. Native Anthropic route — `USE_ANTHROPIC_COMPOSE=true` on Railway but **skipped whenever json_object is requested** → effectively unused for the main calls.
3. OpenAI fallback — `COMPOSER_MODEL=gpt-4o-mini`. Used only when OpenRouter is unkeyed → **this is what CI tests** (no OPENROUTER_API_KEY secret in GitHub Actions) → **CI tests a different model than prod runs**. Known gap, fix in this session (Part 2, step 6).

Everything that is NOT generate_compose — clarifier questions, slot extraction, intent, planner — uses `generate()` → **gpt-4o-mini via OpenAI** in prod.

### The fan-out being consolidated (per response with review data, post-#105)

| # | Call | agent_name | Model today | Notes |
|---|---|---|---|---|
| 1 | Blog article (prose + follow_up + transitional + top_pick) | `blog_article_composer` | Haiku 4.5 via OpenRouter | json_object; the moat |
| 2–4 | Review consensus ×3 (top products) | `product_compose` consensus | Haiku 4.5 via OpenRouter | one per product |
| 5 | Product descriptions | `product_compose` | Haiku 4.5 via OpenRouter | when carousel products exist |
| 6 | Voice pass (draft→revise) | `voice_pass_reviser` | Haiku 4.5 via OpenRouter | **now ON in prod** (enabled 2026-06-03) — an extra round-trip |
| (1b) | Concierge summary | `product_compose` | Haiku | only when NO review data (replaces 2–4) |
| — | (top_pick editorial — **removed in #105**) | — | — | one call already eliminated |

Plus, outside compose: clarifier question gen + slot extraction (gpt-4o-mini), next_step_suggestion.

**Target: calls 1–6 → ONE call.**

### Relevant Railway flags (all verified ON)
`USE_REVIEW_GROUNDING`, `USE_GROUNDED_COMPOSE`, `USE_PRODUCT_VERIFICATION`, `USE_TWO_SPEED_COMPOSE`, `USE_VOICE_PASS`, `USE_ANTHROPIC_COMPOSE`, `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `ENABLE_SERPAPI`, `SERPAPI_FALLBACK_ENABLED`. Rate limiting OFF (dogfooding).

### Evidence/tooling that already exists
- `backend/eval/voice_eval.py` — OpenRouter model bake-off (Haiku 4.5 won at 4.77; Sonnet 4.6 is in the matrix). `OPENROUTER_API_KEY` lives in `backend/.env` + Railway.
- `backend/eval/AB_claim_support.md` — grounding A/B proof (4.57 vs 2.57).
- `backend/eval/clarifier_eval.py` (#99) — clarifier question-quality eval + CI job.
- `eval/test_eval_smoke.py::test_blog_role_in_sync_with_production` — pins `blog_role` byte-identical to `BLOG_ROLE`.

---

## Part 1 — The goal

One LLM request produces everything the response needs; the model is chosen from bake-off data (Sonnet 4.6 vs Haiku 4.5); prose can stream. Result: lower latency (5-6 round-trips → 1), lower cost, one log stream per response, and a single prompt to maintain.

---

## Part 2 — Execution order (each = one PR, shipped + prod-verified before the next)

1. **Model decision — re-run the bake-off with the consolidated workload in mind.**
   `python -m eval.voice_eval --models anthropic/claude-sonnet-4.6,anthropic/claude-haiku-4.5,openai/gpt-4o-mini` from `backend/` (OPENROUTER_API_KEY in `backend/.env`). The user wants **Sonnet** evaluated seriously: judge score AND latency AND cost per response at the consolidated call's larger output size (~1.5–2× tokens of today's blog call). Record the decision + numbers in `eval/results/`. (If Sonnet wins on quality but loses on latency, present the tradeoff to the user before step 5.)

2. **Tier 3a — fold consensus + descriptions into the blog call.**
   Extend the blog JSON schema: `{body, follow_up_question, transitional_reasoning, top_pick, consensus: {product_name: "..."}, descriptions: {title: "..."}}`. The consensus/description data the separate calls received (review bundles, product list) already rides `blog_data` — the writer sees it all anyway. Delete `llm_tasks['consensus:*']` and `llm_tasks['descriptions']`; assembly reads from the parsed blog JSON instead of `result_map`. CLARIFIER_MAX_TOKENS-style bump needed (blog call max_tokens ~700 → ~1400). The `_template_consensus` path (non-top products) stays — it's already free.

3. **Tier 3b — fold the voice pass into the single call.**
   The revise-pass instructions (`_voice_revise_body`'s prompt) become part of the single call's role prompt ("write, then self-edit before emitting"). Delete the second round-trip. `USE_VOICE_PASS` flag then gates a prompt section, not a call.

4. **Tier 2 — prose/JSON decouple (unlocks streaming + any model).**
   Restructure the single call so the prose body streams as plain tokens and the structured fields (consensus, top_pick, follow-up...) arrive in a tagged tail section (e.g. `<data>...</data>` JSON block after the prose) parsed post-stream. This removes the json_object dependency entirely → any model works natively (including direct Anthropic API with prompt caching) → `generate_compose_with_streaming` (currently dead code) becomes usable.

5. **Model swap.** Set `OPENROUTER_COMPOSE_MODEL` to the step-1 winner on Railway (zero code — or change the config default + CI pin in lockstep). If the winner is Sonnet and step 4 is done, consider direct `ANTHROPIC_API_KEY` + prompt caching instead of OpenRouter (cheaper at volume).

6. **CI honesty.** The "prod-model gate" currently tests the OpenAI fallback, not what prod runs. Fix: add `OPENROUTER_API_KEY` as a GitHub Actions secret + a voice-integration job that runs the live compliance tests through the real OpenRouter path with the pinned `OPENROUTER_COMPOSE_MODEL`; update the pin-assertion to check the EFFECTIVE model, not just `COMPOSER_MODEL`. (User also still needs to set `OPENAI_API_KEY` secret for the clarifier eval — see QA_ROUND8 handoff item 1.)

7. **(Stretch) Tier 2.1 — true token streaming** of the prose body through the SSE channel (frontend `stream_chunk_data` already exists). Scoped project; only start if steps 1–6 land cleanly.

---

## Part 3 — Constraints that WILL bite (each one has broken a session before)

- **`blog_role` is pinned byte-identical** to `eval/voice_eval.py BLOG_ROLE` (`test_blog_role_in_sync_with_production`). Any prompt change = update both in the same PR. The consolidated schema changes the prompt → the eval harness AND its smoke tests need the same update.
- **Everything that rides blog_data must survive**: VALUE RANKING directive (#100), DECIDING FACTOR comparison directive (#98), profile_inject (#76), review excerpts (A1), budget phrasing (#94). Grep for `blog_data_parts.append` before touching assembly.
- **Prose/cards/consensus agreement (#93)**: `prose_top_pick` pins card #1 + consensus rank 1. The consolidated call's `top_pick` + `consensus` fields must keep that wiring.
- **The 5-layer passthrough trap** for any NEW field that must reach the frontend (composer → validator → _extract_results → plan_executor_node → chat.py).
- **Two-speed (#71)**: depth routing changes max_tokens/length directive at the call site — must compose with the consolidated call's larger budget.
- **product_compose.py has NO module-level logger** — helpers import `get_logger` locally.
- **gitleaks scans every PR commit** — use `test-` prefixed placeholders; squash-rewrite if flagged.
- **Don't run prod Playwright during a deploy rollout** — in-flight SSE gets cut and looks like a P0.
- Backend tests: 721+ must stay green (`python -m pytest tests/ -q` from `backend/`); eval smoke too (`python -m pytest eval/ -q`).

---

## Part 4 — Open loops carried over (unchanged, not this session's job)

- eBay `EBAY_CAMPAIGN_ID=1234567890` is still the EPN placeholder → eBay links earn $0
- SerpApi.com keys are free-tier (250/mo each); Serper.dev still out of credits
- Rotate transcript-exposed keys (OpenRouter, SerpApi ×2)
- Re-enable rate limiting before launch (`RATE_LIMIT_ENABLED=true`)
- `OPENAI_API_KEY` GitHub Actions secret (user; lights up clarifier eval + voice fallback gate)
- Outcome 6 prototype stays dormant (user decision 2026-06-03)
