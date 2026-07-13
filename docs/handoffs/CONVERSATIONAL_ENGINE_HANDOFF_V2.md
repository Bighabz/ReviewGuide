# Conversational Recommendation Engine — Session Handoff V2

**Date:** 2026-06-02 · **Main:** `18ed849` · **Prod:** live & verified
**Use:** feed this to `/goal` in a fresh session. Part 1 is DONE (context — don't redo), Part 2 is the remaining DESIRED OUTCOMES, Part 3 is the suggested execution order.
**Supersedes:** `CONVERSATIONAL_ENGINE_HANDOFF.md` (its Tier 1 + Outcome 4 are now shipped).

---

## Part 1 — Where things stand (all shipped & prod-verified 2026-06-02)

### This roadmap's PRs (conversational engine)

| PR | What | Prod proof |
|---|---|---|
| #68 | **Price hygiene**: `_drop_price_outliers` — offers <25% / >400% of the product's median market price are dropped before card building (and before the price backfill) | Railway log: `Price hygiene: dropped 1 outlier offer(s) for iPhone 15: ['$13.87 (Walmart)']` |
| #69 | **Multi-select questions**: clarifier emits `"type": "multi_select"` (features questions); frontend chips toggle + "Done" submits joined answer; extractor maps the combined answer to ONE slot | Headphones: "Noise cancelling, Wireless" consumed, results prose explicitly addressed both |
| #73 | **Hotfix**: card building never crashes on non-string provider fields (`_str_or` coercion + `_fuzzy_product_match` guard + provider-naming warning log) | Same query class that crashed (dict url) renders fine |
| #77 | **Refinement chips**: after results, "Show cheaper options" / "More premium picks" / "Only [brand]" / "Different use case" chips re-run the search with adjusted slots — nothing re-asked | Laptops $152–$398 → tap cheaper → `budget=under $122` → Chromebooks $35–$120 |
| #78 | **Hotfix**: extraction slot-name dedup (required ∩ optional duplicates → duplicate JSON keys → answers silently lost → infinite re-ask loop) | Chip answers consume correctly |
| #79 | **Docs**: DESIGN.md §8 — budget-first rule replaced by the specialist-flow description | n/a (docs) |
| #80 + #82 | **Category question packs**: 20 curated packs (`app/agents/category_question_packs.py`), multi-signal matching (category → product_type → product_name → raw query) | 5/5 tested categories (mattresses, running shoes, coffee machines, grills, monitors) produce exact pack questions |

### Concurrent session's PRs (compose roadmap — do not redo)

#70 A2 anti-hallucination, #71 two-speed routing, #72 voice pass, #74 eval A/B, #75 review-consensus cards, #76 personality memory — all flag-gated compose work.

### Live behavior today

"best mattress" → "How do you usually sleep?" (pack) → firmness → mattress-realistic brackets → shortlist with sane prices → refinement chips → "Show cheaper options" re-runs instantly with a lower ceiling. Multi-select features questions toggle + Done. All of it works on https://www.reviewguide.ai/chat.

### Architecture facts (do not re-discover)

- **`last_search_context` now PERSISTS across turns.** The vehicle: chat.py saves a **context-only halt state** (`followups: []`) to Redis after every completed product search; the next turn's `initial_state` restores it (chat.py ~line 384). The workflow treats followups-less halt states as "new query" but chat.py now *preserves* the context fields instead of nulling them. Full 5-layer wiring: composer → validator (already had the fields) → `_extract_results` → `plan_executor_node` → chat.py persist.
- **Refinement chips** are generated *deterministically* in `next_step_suggestion.py` (`_build_refinement_suggestions`) from the fresh context — the LLM call is **skipped** entirely when product results were just shown. They ride the existing `next_suggestions` SSE field (zero frontend changes were needed).
- **Refinement taps** are detected in `clarifier_agent.py` → `_detect_refinement_action()` / `_apply_refinement_action()` (module-level helpers). Chip text arrives as `"You chose: Show cheaper options"`. Budget math: cheaper = `under $(0.8 × min shown price)`; premium = `over $(1.2 × max shown price)`.
- **Topic guard**: because context now persists, the clarifier's "short message = follow-up" rule has a guard — a short query naming a *different* category ("best mattress" after laptops) goes to normal clarification, not slot inheritance.
- **Question packs**: `app/agents/category_question_packs.py` — `CATEGORY_QUESTION_PACKS` (20 packs with aliases), `get_category_pack()` (word-boundary matching; never let "headphones" match the phones pack), `format_pack_hint()`. Injected into `_generate_followup_questions`'s prompt per-category (no prompt bloat).
- **Clarifier question flow**: `_generate_followup_questions` (prompt + normalization, preserves `type: multi_select`), `_handle_user_answer` (extraction — slot names are DEDUPED, see #78), `_handle_new_plan` (expert-flow slot injection).
- **Multi-select frontend**: `MultiSelectQuestion` component in `Message.tsx`; `FollowupQuestion.type` in `ChatContainer.tsx`.
- **Tests**: `test_refinement_chips.py` (19), `test_category_question_packs.py` (33), `test_clarifier_expert_questions.py` (21), `test_product_compose.py` (35), plus passthrough tests in `test_plan_executor_extract_results.py` / `test_plan_executor_node.py`. Full backend suite ~600 tests.

### Workflow facts

- **No local backend** (API keys live in Railway only). Verify on production with Playwright: `https://www.reviewguide.ai/chat?q=<query>&new=1`. Backend logs: `railway logs --service backend | grep ...` (limited retention — grep soon after the query).
- **Ship flow**: worktree branch → commit → push → `gh pr create` → CI green → `gh pr merge --squash --subject "...(#NN)"` → `gh run watch` on "Deploy backend" → `railway deployment list --service backend` (CLI-upload deploys report `version: "unknown"` in /health — check timestamps instead) → Playwright verify → `railway logs` grep for the feature's log line.
- **A concurrent Claude session shares the main working directory** (it was on `feat/richer-personality-memory` at session end). Use **git worktrees** for isolation: `git worktree add ../rg-<name> -b <branch> origin/main`. NEVER use plain write-tree without checking `git diff --cached --stat` first (it absorbs their staged files — caused PR #67's gitleaks failure).
- **Pre-squash branch trap**: a branch cut from another un-squash-merged branch becomes CONFLICTING after that PR's squash lands. Recreate via cherry-pick onto fresh `origin/main` (PR #81 → #82).
- Port 3000 = a DIFFERENT project; frontend dev on **3001**. Repo remote: `Bighabz/ReviewGuide`.
- Autonomous merge+deploy is authorized (CI green, verify each deploy, stop on failure/prod regression).

---

## Part 2 — REMAINING DESIRED OUTCOMES

### 🎯 Tier 2 — expertise depth (continue here)

**Outcome 5: Comparison-mode clarification**
"iPhone 15 vs Pixel 8" (any "X vs Y" query) asks "What matters most to you?" (Camera / Battery / Ecosystem / Price chips) instead of use_case/budget, and the comparison output weights the chosen dimension. Done means:
- An "X vs Y" detector routes to a comparison-specific question (one question, 3-5 dimension chips appropriate to the product pair)
- The chosen dimension is passed to the comparison/compose path and visibly weights the verdict prose
- Verified on prod with 2 comparison queries
- NOTE: `product_extractor` tool + `_is_comparison_follow_up` (product_compose) already exist for comparisons — build on them

**Outcome 6: Answer-aware follow-ups**
The features question adapts to the use_case answer: picking "Gaming" for laptops makes the next question about GPU/refresh rate; "Side sleeper" makes the firmness question reference shoulder pressure. Requires sequential question generation (ask use_case alone → generate features after the answer arrives). **Trade-off to evaluate FIRST: this doubles conversation turns — prototype and compare before committing.** The question packs (#80) are the natural place to encode per-answer branches.

### 🎯 Tier 3 — personalization

**Outcome 7: Preference-biased clarifier**
Returning users see their past answers as the FIRST chip with a "(like last time)" suffix, sourced from the existing `userPreferences` / `preference_summary` infra (note: PR #76 from the concurrent session enriched `profile_inject` — check what's there now before building).

**Outcome 8: Skip-all affordance**
Every clarifier message includes one final chip: "Just show me the best overall" — proceeds immediately with category defaults (no budget filter, most popular use case). Smallest remaining outcome; could ride along with any PR.

### 🎯 Tier 4 — trust & measurement

**Outcome 9: Budget-aware ranking**
Within the budget range, ranking favors value (rating per dollar) so a $550/4.5★ pick beats a $999/4.6★ pick on a "$500–$1,000" ask. Touches `product_ranking` tool.

**Outcome 10: Per-category eval harness**
`backend/eval/` gains a clarifier-quality eval: for each category in the question packs, score whether generated questions match the pack (LLM-judged rubric). Run in CI as non-blocking signal. The packs (#80) make this nearly mechanical: generate → compare against `CATEGORY_QUESTION_PACKS`.

### 🧹 Small open items

- **Rotate the OpenRouter API key** — NEEDS THE USER (account access); then update `OPENROUTER_API_KEY` on the Railway `backend` service
- **Global `--ink-3`/`--text-muted` contrast token bump** (#9B9590 fails AA) — needs its own design-wide PR with visual verification (UnifiedTopbar nav links themselves were already fixed in #35)
- Optional: F3 prettier pre-commit hook, F4 /login video swap

---

## Part 3 — Suggested execution order

1. **Outcome 8 (skip-all chip)** — smallest, immediate UX win, warms up on the clarifier code
2. **Outcome 5 (comparison mode)** — highest-impact remaining Tier 2 item
3. **Outcome 10 (eval harness)** — cheap now that packs exist; protects everything shipped so far
4. **Outcome 9 (budget-aware ranking)** — backend-only, well-scoped
5. **Outcome 6 (answer-aware follow-ups)** — prototype first, evaluate the turn-count trade-off, then decide
6. **Outcome 7 (preference-biased clarifier)** — after checking what PR #76's personality memory already provides

Each outcome = one PR, shipped and prod-verified before starting the next. Two prod bugs were found by doing exactly this last session (#73, #78) — the verification step is what catches them.
