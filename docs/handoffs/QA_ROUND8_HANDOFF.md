# Chat Quality — Session Handoff (QA Round 7 Part 2 complete → Round 8 follow-ups)

**Date:** 2026-06-03 · **Main:** PR #106 merge · **Prod:** live & verified
**Use:** feed this to `/goal` in a fresh session. Part 1 is DONE (don't redo), Part 2 is the remaining work, Part 3 is workflow facts.
**Supersedes:** `QA_ROUND7_HANDOFF.md`. Companion docs: `CONVERSATIONAL_ENGINE_HANDOFF_V2.md` (original Outcomes spec), `COMPOSE_IMPROVEMENT_HANDOFF.md` (compose flags).

> ⚠️ **PRIORITY NOTE (user, 2026-06-03):** the NEXT session should run
> **`COMPOSE_SINGLE_CALL_HANDOFF.md`** (single-call compose consolidation + model
> decision Sonnet-vs-Haiku) — the user wants that ASAP. This doc's Part 2 items
> are the queue AFTER that.

---

## Part 1 — Where things stand (all shipped 2026-06-03, this session)

Eight PRs in one session, every one merged + deployed; #100/#101/#103 also Playwright prod-verified:

| PR | What | Prod proof |
|---|---|---|
| #99 | **Outcome 10 — clarifier eval harness** (`backend/eval/clarifier_eval.py` + 18 smoke tests + non-blocking `clarifier-eval` CI job) | CI job runs on every clarifier-touching PR; live eval skips until OPENAI_API_KEY secret is set |
| #100 | **Outcome 9 — budget-aware value ranking** (rating-per-dollar in budget; product_ranking joined the standard plan; compose mirrors value order) | "$500–$800 laptops": $635 Lenovo (4.7★/7K) led over $699 ASUS and a 1-review 5.0★ HP; prose argued performance-per-dollar |
| #101 | **Outcome 7 — "(like last time)" preference chips** (built on PR #76's preference_service; option-membership gate prevents cross-category leaks) | Repeat laptop search: "Gaming" + "$800–$1,200" moved to first chip with tags |
| #102 | **Outcome 6 — answer-aware follow-ups PROTOTYPE** (USE_ANSWER_AWARE_FOLLOWUPS, default OFF; features_by_use_case pack branches for laptops+headphones) | Dormant by design — see "Needs the user" below |
| #103 | **F4 — model-code dedup** (regex identity; offers merged; false-positive guards) | Headphones + laptop sweeps: 0 duplicate cards, 9/10 cards carry both Amazon + eBay offers |
| #104 | **$407-class condition labels** (Renewed/Used/Open box badges via eBay condition field + title keywords; new offers lead cards) | Backend-tested; visual confirmation is data-dependent (needs non-new listings in results) |
| #105 | **Cleanup — dead top_pick ui_block** + its wasted LLM call removed | One fewer LLM call per composed response |
| #106 | **Mobile QA Round 8 fixes** (tap targets ≥40px, aria-labels, sr-only h1, "You chose:" contrast, armrest accessory filter) | Sweep findings fixed; re-sweep recommended next session |

Also this session: **USE_TWO_SPEED_COMPOSE + USE_VOICE_PASS enabled on Railway** (user-approved, prod-verified healthy — instant take + full editorial article, 5 real-price cards, zero console errors).

### Architecture facts added this session (do not re-discover)

- **product_ranking is no longer dead code**: it runs in the STANDARD plan (after affiliate, before compose) and compose consumes `ranked_products` when items carry `value_per_dollar`. No budget → legacy scoring → compose ignores it (no reorder).
- **`_extract_model_codes` / `_dedupe_by_model_code`** (product_compose.py, module-level): the F4 identity dedup. Products with no model code are NEVER merged.
- **`_offer_condition_label`** (product_compose.py): eBay condition field first, title keywords second. Serper/Google Shopping offers always arrive condition="new" — title is the only signal there.
- **`condition` + `title` now survive into compose's offer dicts** (they were dropped at the offer-copy boundary before #104).
- **preference_chip** rides the clarifier question objects → frontend renders "(like last time)" (data-testid="clarifier-preference-tag"). Biasing happens AFTER pack enforcement; option membership is the cross-category safety gate.
- **The clarifier eval harness calls the production agent** with a transport-swapped `generate` — the drift guard is `test_production_enforcement_satisfies_scorer` (runs real normalization with mocked sloppy LLM output; scorer must pass it clean).
- **gitleaks scans every commit in a PR** — a "leaked" placeholder in an early commit fails CI even after a fix commit; squash-rewrite the branch. Use "test-"-prefixed placeholder secrets.
- **Rolling deploys cut in-flight SSE streams** — a compose running during a Railway deploy shows "Response interrupted"; Retry hits the new instance. This is the explanation for the sweep's P0 (not a code bug).

---

## Part 2 — REMAINING WORK

### Needs the user first

1. **OPENAI_API_KEY GitHub Actions secret** — the voice-live CI gates AND the new clarifier eval have been silently skipping forever because this secret was never set. Set it (repo → Settings → Secrets → Actions) and the live LLM gates light up. (Autonomous attempt was blocked by the permission classifier — correctly, it's a credential propagation.)
2. **Outcome 6 measurement decision** — the prototype is shipped dormant. To measure: set `USE_ANSWER_AWARE_FOLLOWUPS=true` on Railway, run a timed Playwright comparison (sequential 2-card flow vs the single-card baseline), then decide ship/drop. RECOMMENDATION from this session: **keep dormant** — QA Round 5's single-card design exists because multi-turn clarification caused abandonment; the meaningful measurement is an A/B completion-rate test with real traffic, not synthetic timing.
3. **Standing items** (unchanged): Skimlinks publisher ID (activates #95's dormant code), real eBay EPN campaign ID (links still earn $0 — sweep confirmed campid is still the placeholder `1234567890`), rotate transcript-exposed keys (OpenRouter, SerpApi×2), search-credit funding, **re-enable rate limiting before launch** (`RATE_LIMIT_ENABLED=true`).

### Ready to execute (no user input needed)

4. **Stale error stub after Retry** (sweep P1): when a compose fails and the user taps Retry, the failed "incomplete results" bubble stays above the successful retry. Fix the retry handler in `frontend/components/ChatContainer.tsx` to replace/collapse the failed message.
5. **"Only Herman" refinement chip** (sweep P1): the refinement-chip generator (next_step_suggestion lineage, PRs #77/#78) produced a truncated brand chip ("Only Herman" = Herman Miller) for a brand NOT present in the results. Fix: brand chips only for brands that appear in the shortlist; never truncate multi-word brands.
6. **`--ink-3` AA contrast token** (deferred-for-cause since Round 7): axe still flags 3 nodes at ~2.95 contrast (post-#106 re-audit). Needs its own design-wide PR with visual verification across all surfaces.
7. ~~**Mobile re-sweep** after #106~~ **DONE (final verification, 2026-06-03)**: all tap targets ≥40px, axe critical `button-name` + `page-has-heading-one` GONE, comparison flow completes cleanly, condition badges confirmed live, 0 console errors. Two NEW minor findings from the re-audit:
   - axe moderate `heading-order` (1 node) on the results view — heading levels skip somewhere in the blocks.
   - **Comparison cards show only one side**: "iPhone 15 vs Pixel 8" prose compares both, but the cards rendered were Pixel 8 + Pixel 8 Pro only — no iPhone card. Pre-existing (not from today's PRs); the comparison card selection likely follows search results rather than the named pair.
8. **Clarifier eval live baseline**: once the OPENAI_API_KEY secret exists (item 1), trigger voice-integration.yml manually (workflow_dispatch) and record the first live clarifier-eval pass rate as the baseline.

---

## Part 3 — Workflow facts

(Same as QA_ROUND7_HANDOFF.md Part 3, still accurate. Key ones:)

- **Test as the 2nd search in a session**; use REAL Playwright clicks on clarifier cards.
- **No local backend** — verify on prod: `https://www.reviewguide.ai/chat?q=<query>&new=1`.
- **Ship flow**: branch off origin/main → `git commit -F msgfile` → `gh pr create --body-file` → CI green → `gh pr merge --squash --subject "...(#NN)" --delete-branch` → Deploy backend auto-runs + Vercel → verify → next. **Autonomous merge+deploy authorized.**
- **Test suites**: backend 721+ (`python -m pytest tests/ -q` from `backend/`), frontend 340+ (`npx vitest run` from `frontend/`), eval smoke (`python -m pytest eval/ -q`).
- **Don't schedule prod Playwright tests while a deploy is rolling out** — the SSE cut mid-compose looks like a P0 but isn't.
- A parallel Claude session may share the working directory — check `git branch --show-current` before committing.
- The local demo stack on **localhost:3003 must never be torn down**.
