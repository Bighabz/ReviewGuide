# Chat Quality — Session Handoff (QA Round 6 complete → Round 7)

**Date:** 2026-06-03 · **Main:** PR #97 merge (`422115e`) · **Prod:** live & verified
**Use:** feed this to `/goal` in a fresh session. Part 1 is DONE (don't redo), Part 2 is the remaining work, Part 3 is workflow facts.
**Supersedes:** `QA_ROUND6_HANDOFF.md`. Companion docs: `CONVERSATIONAL_ENGINE_HANDOFF_V2.md` (Outcomes 5-10), `COMPOSE_IMPROVEMENT_HANDOFF.md` (compose flags), `QA_ROUND4_FINDINGS.md` (original findings).

---

## Part 1 — Where things stand (all shipped & prod-verified 2026-06-03)

Six PRs in one session, every one merged + deployed + Playwright-verified on prod:

| PR | Fix | Prod proof |
|---|---|---|
| #92 | **F2 — "Under budget" badge** (user decision: keep below-floor offers as deals, badge them). Range budgets ($80–$130): ceiling hard, floor soft+badged. Floor-only budgets ($500+): both hard (quality intent). | 4 badges exactly on below-floor offers, in-budget offers unbadged |
| #93 | **Prose/consensus/cards agreement**: blog JSON gains `top_pick` → pinned to consensus rank 1 (`editors_pick` → "Editor's pick" badge) + card #1 reorder | Prose pick (ASICS Gel-Nimbus 25) = consensus #1 w/ badge = card #1 |
| #94 | **Budget ranges survive slot extraction** (found in #92's prod verify — extraction LLM collapsed "$80–$130"→100). Prompt fix + deterministic `_find_budget_phrase` guard | Prose says "At your $80–$130 budget" AND badges fire |
| #95 | **Affiliate provider harmony Steps 1+2**: Serper Shopping bolt-on → registered `SerperShoppingProvider`; Amazon curated cheat gated on `not AMAZON_API_ENABLED`; **dormant Skimlinks** wrapping (needs `SKIMLINKS_PUBLISHER_ID` + `SKIMLINKS_API_ENABLED=true` on Railway to activate, zero code) | Real prices flowing through the provider path, 0 skimresources URLs (dormant) |
| #96 | **Outcome 8 — skip-all chip**: "Just show me the best overall" on every clarifier card → skips extraction → straight to results | Tap → 5 office-chair cards in ~13s, zero questions answered |
| #97 | **Proxy-IP logging fix**: request logs use `get_real_client_ip` (was: Railway's proxy IP on every line) | Deployed (log-only change) |

### Architecture facts added this session (do not re-discover)

- **Budget slot is now a STRING** preserving ranges/qualifiers ("$80–$130", "under $100", "$500+"). `_parse_budget` still accepts legacy numbers. Anything new reading `slots["budget"]` must handle both.
- **`_find_budget_phrase(text)`** (clarifier_agent.py, module-level): pulls the literal budget phrase from an answer; prefers dollar-denominated, right-most matches (budget is the card's last question).
- **Prose top pick**: blog JSON `top_pick` field; `prose_top_pick` pre-parsed in compose before block assembly; pins consensus rank 1 + card order. `eval/voice_eval.py` `BLOG_ROLE` must stay byte-identical to `blog_role` (test_blog_role_in_sync_with_production).
- **`SerperShoppingProvider`** (`app/services/affiliate/providers/serper_shopping_provider.py`): registered as "serper_shopping", self-gates on `settings.ENABLE_SERPAPI + SERPAPI_API_KEY` (NOT loader env-var check — see code comment). Skimlinks wrapping inside `wrap_with_skimlinks()`; Amazon/eBay never wrapped.
- **Skimlinks-wrapped URLs are buy links** in compose (`skimresources.com` exception to the serper_shopping context-only rule).
- **Skip-all**: `_is_skip_all()` (clarifier_agent.py) + early return in `_handle_user_answer` BEFORE extraction. Frontend: `data-testid="clarifier-skip-all"` in ClarifierCard.
- **`top_pick` ui_block (type:"top_pick") has NO frontend renderer** — emitted but never rendered. Cleanup candidate.
- **Playwright + ClarifierCard**: use REAL Playwright clicks (element refs), not synchronous JS `.click()` — React state races make only the last click register.

---

## Part 2 — REMAINING WORK (priority order)

### Needs the user first

1. **Compose flags**: `USE_PRODUCT_VERIFICATION=true` was ENABLED on Railway 2026-06-03 (user-approved) and prod-verified. Still default-off, needing user OK + measurement: `USE_TWO_SPEED_COMPOSE` (prose-length behavior change), `USE_VOICE_PASS` (adds ~1 LLM round-trip — eval it first per `COMPOSE_IMPROVEMENT_HANDOFF.md`).
2. **Skimlinks activation** (zero code): user signs up at skimlinks.com → set `SKIMLINKS_PUBLISHER_ID` + `SKIMLINKS_API_ENABLED=true` on Railway → multi-merchant monetized offers light up.
3. **Standing items**: real eBay EPN campaign ID (eBay links still earn $0), rotate transcript-exposed keys (OpenRouter, SerpApi×2), search-credit funding (Serper $50 vs SerpApi $75/mo), **re-enable rate limiting before launch** (`RATE_LIMIT_ENABLED=true` — per-IP fix already in place).

### Ready to execute (no user input needed)

4. ~~**Outcome 5 — comparison-mode clarification**~~ **SHIPPED (PR #98, 2026-06-03)** + prod-verified with 2 comparison queries + QA Round 7 swept (see `QA_ROUND7_FINDINGS.md` — all pass).

**Execution order for the next session (each = one PR, shipped + prod-verified before the next):**

5. **Outcome 10 — clarifier eval harness** ← START HERE: `backend/eval/` gains a clarifier-quality eval — for each category in `CATEGORY_QUESTION_PACKS`, generate questions and score them against the pack (slot order, options, multi-select flags, brackets). Run in CI as a non-blocking signal alongside the voice checks. Nearly mechanical now that packs exist.
6. **Outcome 9 — budget-aware ranking**: within the stated budget range, ranking favors value (rating per dollar) — a $550/4.5★ pick beats a $999/4.6★ pick on a "$500–$1,000" ask. Touches `product_ranking` tool; respect existing prose-pick pinning (#93).
7. **Outcome 7 — preference-biased clarifier**: returning users see their past answer as the FIRST chip with "(like last time)". Source: `preference_service` / `profile_inject` (check what PR #76 already stores before building).
8. **Outcome 6 — answer-aware follow-ups**: PROTOTYPE ONLY first — features question adapts to the use_case answer (sequential generation). It doubles conversation turns; measure before committing. Question packs are where per-answer branches would live.
9. **F4 near-duplicate dedup, done right**: extract model codes (regex `\b[A-Z]{1,4}-?\d{3,}\w*\b`) from product names; dedupe ONLY when model codes match. This is the identity signal the URL-based attempt (reverted in #97's branch) lacked.
10. **$407-class listing detection**: use the eBay `condition` field — offers that aren't "new" get a "Renewed/Used" label on the card (or excluded from the headline price). Honest, not hidden.
11. **Mobile QA sweep (Round 8)**: comparison flow + clarifier cards + skip-all at 375×812; tap targets ≥40px; axe pass via CDN injection. Findings → fix → ship.
12. **Cleanup**: remove the dead `top_pick` ui_block emission (compose emits it; no frontend renderer exists).

### Deferred for cause (don't retry the same way)

- **F4 near-duplicate card dedup**: URL-based dedup REVERTED in #97's branch — fuzzy offer attachment makes similar-but-distinct products ("Cheap Laptop A"/"B", "iPhone 15 Pro"/"Pro Max") share identical offer sets → false positives on real products. Needs model-number-level identity (regex extract model codes, dedupe only on code match).
- **`--ink-3` AA contrast token**: needs its own design-wide PR with visual verification across all surfaces.
- **$407 iPhone listing detection**: the median price check can't catch refurb/accessory listings at 30-40% of median. Needs condition-field-based logic (eBay offers carry `condition`) — label or exclude non-"new" offers.

---

## Part 3 — Workflow facts

- **Test as the 2nd search in a session** (the rounds-4/5 meta-lesson) and under LLM latency variance.
- **No local backend** (API keys live in Railway). Verify on prod with Playwright: `https://www.reviewguide.ai/chat?q=<query>&new=1`. Use REAL Playwright clicks on clarifier cards (not JS evaluate clicks).
- **Rate limiting is OFF** — prod testing unthrottled.
- **Ship flow**: branch off `origin/main` → commit (`git commit -F msgfile`, Write tool for the msgfile) → push → `gh pr create --body-file` → CI green (~2 min, pytest hard gate, ruff/black soft) → `gh pr merge --squash --subject "...(#NN)" --delete-branch` → "Deploy backend" auto-runs (~45s) + Vercel Production (~2 min) → verify both SHAs via `gh api repos/Bighabz/ReviewGuide/deployments` → Playwright verify. **Autonomous merge+deploy authorized** (CI green, verify each, stop on failure).
- **Test suites**: backend 651+ (`python -m pytest tests/ -q` from `backend/`), frontend 336+ (`npx vitest run` from `frontend/`). Run `eval/` tests too when touching `blog_role`.
- **Windows gotchas**: `cat >> file << 'EOF'` heredocs work in the Bash tool; `/tmp` flaky; absolute paths or `cd` per call.
- **A parallel Claude session may share the working directory** — check `git branch --show-current` before committing.
- The local demo stack on **localhost:3003 must never be torn down** (user keeps it permanently).
