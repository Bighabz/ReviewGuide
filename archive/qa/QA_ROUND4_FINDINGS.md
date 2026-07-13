# QA Round 4 — Findings & Fixes (2026-06-02)

**Sweep target:** https://www.reviewguide.ai · started at main `18ed849`, ended at main `2af410a`+ (PRs #83–#86)
**Inputs:** `QA_ROUND4_PROMPT.md` sweep + external QA handoff (user-forwarded, 4 reported bugs)
**Severity:** P0 = breaks core flow · P1 = visible wrong behavior · P2 = polish

---

## Fixed & shipped this session

| # | Finding | Severity | PR | Status |
|---|---|---|---|---|
| F0 | **Chip answers hijacked in multi-search sessions** — clarifier's follow-up/refinement shortcuts ran BEFORE the pending-questions check; a short chip answer ("You chose: Side sleeper") in any 2nd+ search skipped remaining questions and searched with stale slots. External Bug 1 / the original user complaint. | **P0** | **#83** | ✅ Merged, deployed, regression-tested (4 tests) |
| F0c | **"New Chat" button no-op after first use** — one-shot `NEW_EMPTY_SESSION` sentinel never reset; session never rotated; old Redis context leaked into "new" chats. External Bug 3. | P1 | **#84** | ✅ Merged, deployed, **prod-verified with discriminating test** (2nd New Chat click clears) |
| F0b | **Chips: no feedback, no lock, double-submit race** — single-select chips gave no visual feedback and stayed clickable; async isStreaming guard let rapid clicks commit phantom duplicate turns ("Mountain" + "Beach"). External Bugs 1a + 2. | P1 | **#85** | ✅ Merged, deployed (selected state + question lock + synchronous send guard, 4 tests) |
| F6 | **8s clarifier timeout silently kills clarification** — the stage budget couldn't fit 2 sequential LLM calls; the timeout fallback skipped questions and ran the search. THE mechanism behind "questions appear inconsistently" (external Bug 4). Caught live in Railway logs. | P1 | **#86** | ✅ Merged pending CI (budget 8s→20s + no-LLM fast path for "best X" queries, 6 tests) |

---

# QA Round 5 — Q&A flow verification (2026-06-02, post #83–#86)

**Goal:** verify questions are asked and answered properly after the fixes; find bugs.

## Q&A mechanics — ALL PASS ✅

| Check | Result |
|---|---|
| Questions asked reliably (F6 fix) | ✅ "best running shoes" → full pack (running type / feel / budget) appeared in <15s. F6 fast path confirmed in prod logs (`product_name='vacuum' extracted heuristically` — real user traffic) |
| Chip answer → chip locks + pressed (#85) | ✅ Instant `[disabled] [pressed]` on tap, siblings disabled |
| Chip answer treated as answer, not hijacked (#83) | ✅ "You chose: Road running" → remaining 2 questions re-asked, answered one not repeated. Prod log: `Resumed session - extracting slots from user answer → Extracted 3/10 slots` (real traffic) |
| Free-text answer mixed with chips | ✅ "I want maximum cushioning for long distances" → feel slot extracted, only budget remained |
| Answers shape results | ✅ Prose: "At $80–$130, you're in the sweet spot for maximum cushioning"; all 5 products are max-cushion road shoes |
| Error handling under rate limit | ✅ Clean error banner + Regenerate button (no crash, no blank screen) |

## NEW FINDING

### F7 [P0 for real traffic] Rate limiter keys on Railway's proxy IP — all users share one bucket
**Evidence:** `Rate limit exceeded for guest user: ip:100.64.0.4 (20/20 in 900s)` — 100.64.x.x is Railway's internal CGNAT range, not a client IP.
**Root cause:** `TRUSTED_PROXY_CIDRS` defaults to `[]` and was never set on Railway → `ip_utils.get_real_client_ip()` never trusts `X-Forwarded-For` → falls back to `request.client.host` = the proxy's internal IP → **every anonymous user behind that proxy instance shares a single 20-req/15-min bucket.**
**Impact:** the product can't serve more than ~1 concurrent anonymous user without collective 429s. My QA traffic and a real user's traffic were consuming each other's quota.
**Fix (config-only, no code change):** set `TRUSTED_PROXY_CIDRS=["100.64.0.0/10","10.0.0.0/8"]` on the Railway `backend` service. The extraction code already handles the rest. (Needs user OK for prod var write.)

## Known bugs re-confirmed with stronger evidence

- **F1 (now P1, urgent):** running-shoes flow — **4 of 5 cards have ONLY unmonetized eBay links** (Hoka, Brooks, NB top pick, Asics); only Saucony has Amazon. 80% of the shortlist earns $0.
- **F2:** "$80–$130" budget → offers at $35.99 / $40 / $72.23 shown (3 of 5 below floor); prose celebrates "$40 — a steal."
- **F5:** "best blender" as 2nd search in session → no questions (slots bled from running-shoes conversation). Topic guard correctly searched blenders; clarification skipped.

## QA Round 5 — second wave (external QA round 2: 10 categories, 6 bugs) — ALL ADDRESSED

The user forwarded a second external QA handoff mid-session. Final state (main `9186429`):

| External bug | Fix | PR | Prod verification |
|---|---|---|---|
| **1+2: card looks like a form but isn't; multi-select inconsistent** | Form-style ClarifierCard: chips accumulate (radio/checkbox), one "Get recommendations →" submit, combined answer in one round-trip. Backend: pack options/flags/brackets ENFORCED post-LLM (not just prompted). | **#87** | ✅ Office chair flow: 4 taps accumulated → "You chose: 4–8 hours; Lumbar support, Breathable mesh; $150–$350" → all 3 slots extracted → results, zero re-asking. Chairs' features = multi-select (the exact reported failure). |
| **3: inconsistent microcopy** | Deterministic hints per question kind ("Select all that apply — or type your own" / "or type an amount" / "or type your own answer") | **#87** | ✅ All three hints verified in prod |
| **4: input focus race on ?new=1** | New sessions skip the history fetch + spinner (no welcome-screen unmount; also kills the guaranteed-401 console noise) | **#88** | Mechanism-verified; deployed |
| **5: stream interruption** | Not reproducible on demand; existing reconnect + Retry recovery confirmed working by external QA. Documented for monitoring. | — | — |
| **6: consensus contradicts prose/cards** | Consensus block only ranks products with real offers that survived budget pruning; ranks renumbered | **#89** | Regression-tested (611 backend); deploys with #89 |
| **NEW — F7: shared rate-limit bucket** | `TRUSTED_PROXY_CIDRS` set on Railway (user-approved) — rate limiter now keys on real client IPs via X-Forwarded-For | env var | ✅ 7+ rapid requests post-fix with zero 429s (pre-fix: shared 20/15min bucket across ALL users) |

**QA-5 Q&A mechanics verification (scenario 1, running shoes):** questions asked reliably (F6 fast path confirmed in prod logs), chip answers extracted, free-text answers extracted, prose reflects all answers, error handling under rate limit clean (banner + Regenerate).

## Documented — needs next session (in priority order)

### F5 [P1] Cross-category slot bleed — clarification effectively only exists for the FIRST search of a session
Two mechanisms, both confirmed:
1. `_handle_new_plan`'s conversation extraction fills use_case/budget from PRIOR turns about a DIFFERENT category ("best office chair" inherits "espresso drinks" + "Under $100" from the coffee conversation → no questions).
2. The expert-flow checks (`clarifier_agent.py` ~line 553) treat `last_search_context.budget/use_case/features` as "already answered" even when the context is for a different category.
**Fix direction:** only let prior context/conversation satisfy slots when the context category relates to the current query (reuse the topic-guard word-match). Needs careful tests — interacts with the legitimate same-category inheritance.

### F1 [P1] Some product cards have NO Amazon buy link — only unmonetized eBay
Cards #1 (AirPods Pro 2 — the top pick) and #4 in the earbuds flow had ONLY placeholder-campid eBay links. PR #65's intent was "every product falls back to a tagged Amazon search URL". Suspect: the Amazon-fallback in `product_compose.py` is skipped when an eBay offer exists.
**Evidence:** `.playwright-mcp/prod-verify-consensus-snapshot.md` lines 237-239 vs 486-504.

### F2 [P1] Budget floor not enforced on offers
"$100–$250" earbuds search returned cards with $29/$45/$59/$91 offers (4 of 5 cards below floor). Needs a product decision first: is an under-floor deal a bug or a feature? If a bug: `_parse_budget`/offer filter in `product_compose.py`.

### F3 [P1] Cards ≠ consensus ≠ prose — three different product sets in one response
Worst case seen: espresso-machine query → prose recommends Gaggia/Breville, "How They Compare" ranks espresso machines, cards show drip machines. Consensus block should be built from the post-prune card list; cards should match the prose's category.

### F0d [P2] Remaining "inconsistent rendering" cases (external Bug 4 residue)
After F6+F5 are fixed, the remaining cases are: vague queries ("something cheap but also really good") guessing a category, and dual-category queries answering one half. Needs intent-agent work — route vague product queries to a "what are you shopping for?" question.

### Smaller P2s
- **401 console errors** on `/v1/chat/history/<id>` for anonymous sessions (3 per session) — frontend should skip the fetch or backend should 200-empty.
- **Near-duplicate cards**: "Black+Decker Mill and Brew" + "BLACK+DECKER 12 Cup Mill Brew CM5000B" in one shortlist (F4).
- **iPhone 15 Pro Max at $407** on a comparison query — possible accessory/refurb listing the median check can't catch.
- **Sub-40px tap targets** on mobile header icon buttons ("Back to Discover", "Expand results", Save buttons — all 32×32).
- Known/deferred: `--ink-3` AA contrast, eBay placeholder campaign ID, free-tier search keys, prettier hook, /login video.

---

## Scenario log

| # | Scenario | Result |
|---|---|---|
| A1 | Coffee machine pack full flow | ✅ PASS — pack questions, consensus block, refinement chips, budget-aware prose |
| A2 | Earbuds multi-select | ✅ PASS (pre-sweep this session) — toggle+Done, joined answer consumed, ratings ≤5 |
| A3 | Non-pack category | ⚠️ Not run as planned (replaced by office-chair test which exposed F5) |
| A4 | Refinement chips | ✅ Rendered correctly in 3 flows (taps not individually exercised — context-persistence verified in coffee flow) |
| A5 | Topic guard | ✅ PASS — "best office chair" after coffee = new query (but see F5: no questions asked) |
| A6 | Free-text answer instead of chips | ✅ PASS — typed use-case answer consumed correctly |
| A7 | Budget integrity (ceiling) | ✅ PASS on cards (Under $100 → all cards ≤$100); ⚠️ consensus block violates (F3); floor not enforced (F2) |
| B8 | Travel: Tokyo trip | ✅ PASS — full itinerary, hotels, attractions, no clarifier crash |
| B9 | General: how does ANC work | ✅ PASS — educational prose, no forced product cards |
| B10 | Greeting: hi | ✅ PASS — intro response |
| B11 | Comparison baseline | ✅ Captured — generic product flow (no comparison mode yet, as expected pre-Outcome-5); iPhone+Pixel cards with refinement chips |
| C12 | Ratings ≤ 5 | ✅ PASS everywhere (4.2–4.7 range observed) |
| C13 | Price sanity | ⚠️ See F2, and $407 iPhone Pro Max note |
| C14 | Buy links | ✅ Zero Google Shopping; Amazon all tagged; ⚠️ F1 (missing Amazon on some cards); eBay all placeholder-campid (known) |
| C15 | Consensus names no sources | ✅ PASS |
| D16 | Mobile chip flow | ⚠️ Partially blocked by F6 (questions didn't appear on mobile run); chip components verified at desktop; same component renders both |
| D17 | MobileTabBar | ✅ PASS — 5 tabs, all ≥40px |
| D18 | Mobile Discover | ✅ PASS — hero, grid, tab bar render correctly; zero console errors |
| E19 | Static pages (/,/saved,/compare,/login) | ✅ PASS — no hydration errors, no 404s; only the 401-history P2 |
| E20 | Save/unsave flow | ⏭️ SKIPPED (time) |
| E21 | Dark mode / accent | ⏭️ SKIPPED (time) |
| E22 | axe a11y | ⏭️ SKIPPED — known `--ink-3` contrast issue already documented; no new structural a11y changes shipped |

---

## Handoff for the next session

**Recommended order:**
1. **F5 (cross-category slot bleed)** — the biggest remaining UX gap; makes clarification work in ongoing sessions. Touches `_handle_new_plan` conversation extraction + the `_ctx` checks. Test thoroughly against same-category inheritance (which must keep working).
2. **F1 (missing Amazon links)** — direct monetization impact, small fix in `product_compose.py`.
3. **F3 (consensus/cards/prose mismatch)** — build `review_consensus` from the post-prune card list.
4. **F2 (budget floor)** — needs the user's product decision first.
5. P2 sweep (401 console noise, dedup, tap targets) — batch into any PR.

**Verification notes for the next agent:**
- The F6 fix (#86) makes clarifier questions RELIABLE — re-run the mobile chip flow (D16) after it deploys; it should now consistently show questions.
- The fixes in #83–#86 are all covered by regression tests (backend: test_refinement_chips.py, test_clarifier_expert_questions.py; frontend: clarifierChips.test.tsx).
- Multi-search sessions are now the critical test surface — always test flows as the SECOND search in a session, not just fresh sessions. That's where F0, F5, and F6 all hid.
- Artifacts from this sweep: `.playwright-mcp/prod-verify-*.{md,png}`, `qa-coffee-results-snapshot.md`, `qa-mobile-mattress-snapshot.md`, `qa-mobile-discover.png` (all untracked).
