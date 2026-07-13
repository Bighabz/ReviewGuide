# QA Round 4 — Full Prod Sweep After the 2026-06-01/02 Shipping Burst

**Use:** paste into a fresh Claude Code session (or feed to `/goal`).
**Mission:** agent-driven Playwright sweep of https://www.reviewguide.ai covering everything shipped in PRs #57–#82, find bugs, fix them, ship the fixes. QA Round 3 (PR #35) found 5 bugs this way; the verification discipline also caught #73 and #78. Assume there are more.

---

## Part 1 — What shipped (the QA surface)

Three parallel sessions landed ~20 PRs in 12 hours. Main is at `18ed849`. Everything below is LIVE and individually verified once — but **never swept together, never on mobile, and mostly only with 1–2 happy-path queries each**.

### Conversational engine (PRs #57–#82)
| Feature | What to expect |
|---|---|
| Category question packs (#62/#64/#80/#82) | 20 categories (laptops, phones, TVs, headphones, mattresses, bikes, monitors, coffee machines, vacuums, air purifiers, strollers, watches, cameras, keyboards, desks, chairs, grills, luggage, running shoes, tablets) ask curated specialist questions: use-case FIRST, budget LAST, category-realistic brackets |
| Clarifier chips (#62) | Every question has tappable chips (`[data-testid="clarifier-option-chip"]`); tapping resumes the flow |
| Multi-select (#69) | Features questions: chips toggle (pressed state), "Done" button submits joined answer; combined answer shapes results |
| Budget enforcement (#64) | A "$100–$250" tap → results actually in range; out-of-range prices ONLY as editorial comparisons |
| Price hygiene (#68) | No scam/accessory prices (the "$13.87 iPhone" class) on any card |
| Refinement chips (#77/#78) | After results: "Show cheaper options" / "More premium picks" / "Only [brand]" / "Different use case" — one tap re-runs search, NOTHING re-asked |
| Topic guard | "best mattress" typed after laptop results → normal clarification (not slot inheritance from laptops) |
| Crash hardening (#73) | Dict-valued provider fields never crash card building |

### Compose / evidence (PRs #60–#76)
| Feature | What to expect |
|---|---|
| Review grounding (#60/#63/#66) | Prose cites real review ratings/snippets (via SerpApi.com failover) |
| "How They Compare" block (#75) | Ranked consensus rows: terracotta numerals, product name, star rating (**must be ≤5**), review count, consensus paragraph |
| Amazon-only buy links (#65) | Every "Where to buy" link = Amazon with `revguide-20` tag; ZERO google.com/shopping links; eBay links may appear (known-unmonetized, not a bug) |
| Personality memory (#76) | Returning-user profile injection (hard to test anonymously — skip) |

### Recent UI (PRs #37–#47, #57–#61, QA R3 #35)
Discover grid + rotating placeholder, `/topic/[slug]`, Product Detail (E1), mobile fixes, hydration fixes, tap targets ≥40px, favicon.

---

## Part 2 — The sweep (run all of it)

**Setup:** Playwright MCP against prod. Console + network monitoring on every page. Test BOTH desktop (1280px) and mobile (375px). Each chat flow takes 1–3 min of real backend time — use `browser_wait_for` generously.

### A. Core clarifier → results flows (desktop)
1. **Pack category, full flow:** `chat?q=best+coffee+machine&new=1` → verify pack questions (use-case first, realistic brackets) → answer via chips → results render → "How They Compare" present → refinement chips present
2. **Multi-select:** `best wireless earbuds` → toggle 2 features + Done → verify joined answer consumed, no re-ask loop
3. **Non-pack category** (generalization): `best electric toothbrush` → questions still sensible, chips present, flow completes
4. **Each refinement chip** (one session, laptops): results → "Show cheaper options" → verify cheaper results + no re-asked questions → "More premium picks" → verify → "Only [brand]" → verify → "Different use case" → verify it re-asks use case only
5. **Topic guard:** after results, type `best mattress` → must get mattress clarification, not inherit laptop slots
6. **Free-text answers:** answer a chip question by TYPING instead ("I ride mostly on trails") → flow must still work
7. **Budget integrity:** pick the lowest bracket → check every card price is in/under range (editorial exceptions in prose are OK, card prices are not)

### B. Non-product flows (regression — the clarifier changes must not have broken these)
8. **Travel:** `plan a 5 day trip to Tokyo` → itinerary renders, no clarifier crash
9. **General question:** `how does noise cancelling actually work` → prose answer, no product cards forced
10. **Greeting/intro:** `hi` → intro response
11. **Comparison query:** `iPhone 15 vs Pixel 8` → should NOT crash; comparison-mode clarification isn't built yet (Outcome 5) so generic flow is acceptable — note what it does today as baseline

### C. Evidence & monetization integrity (inspect DOM/network on results from A)
12. Every star rating ≤ 5.0
13. No $0, $NaN, or absurd prices (<25% or >400% of product median)
14. All "Where to buy" hrefs: Amazon with affiliate tag; zero Google Shopping; count eBay links (report, don't fix)
15. "How They Compare" consensus text names NO sources (tone.md rule)

### D. Mobile sweep (375×812, repeat the critical paths)
16. Flow A1 end-to-end on mobile: chips tappable (≥40px), wrap correctly, Done button reachable, consensus block readable, refinement chips don't overflow
17. MobileTabBar: 5 tabs work, "You" tab
18. Discover → search → chat handoff on mobile

### E. Static/secondary pages + console hygiene
19. `/`, `/saved`, `/compare`, `/topic/coffee-machines` (or any topic), `/results/[id]` (save a result first), `/login` — zero console errors, zero hydration warnings (#418/#423 class), zero 404s (favicon included)
20. Save a product → check `/saved` → unsave → check again
21. Dark mode toggle + accent color toggle on chat with results rendered
22. Run axe (via CDN injection, NOT npm — Windows gotcha) on Discover, chat-with-results, and one topic page. Known issue, don't report: `--ink-3`/`--text-muted` #9B9590 AA contrast (needs its own design PR)

---

## Part 3 — Triage & fix protocol

**Severity:** P0 = breaks a core flow (search→results, crash, infinite loop) · P1 = visible wrong behavior (bad prices, broken chips, rating >5, non-affiliate leak, mobile unusable) · P2 = polish (spacing, copy, contrast)

**Protocol:**
1. Document EVERY finding first (file `QA_ROUND4_FINDINGS.md`, repo root): severity, repro steps, screenshot path, suspected file
2. Fix P0s and P1s, one PR each (or batch trivially-related ones), in severity order
3. P2s: list them, fix only if trivial, otherwise leave documented
4. Every fix: prod-verify after deploy before moving to the next

**Known issues — do NOT report as bugs:**
- eBay campaign ID is a placeholder (monetization gap, user is fixing)
- transitional_reasoning sometimes empty (#46, known LLM issue)
- Search runs on free-tier SerpApi keys (may exhaust → reviews degrade gracefully; if you see `all N key(s) exhausted` in Railway logs, note it and continue)
- `--ink-3` contrast, prettier hook, /login video (documented, deferred)
- Comparison queries get generic flow (Outcome 5 not built)

---

## Part 4 — Workflow facts (don't rediscover)

- **No local backend** — API keys live only in Railway. All verification on prod. Backend logs: `railway logs --service backend` via Bash (limited retention, grep right after the query).
- **Ship flow:** worktree branch off `origin/main` → commit → push → `gh pr create` → CI green (pytest is the hard gate; ruff/black SOFT — don't run black) → `gh pr merge --squash --subject "...(#NN)"` → watch "Deploy backend" workflow → Playwright prod verify. **Autonomous merge+deploy is authorized** (CI green, verify each deploy, stop on failure/regression).
- **Frontend deploys via Vercel** automatically on merge; backend via Railway GitHub workflow.
- **Component map is in CLAUDE.md** — read it before editing UI; there are duplicate components (3 product cards, 3 logos).
- **Backend passthrough trap:** new composer→frontend fields need 5-layer wiring (see CLAUDE.md). Clarifier fields do NOT (they ride `assistant_text` → SSE `followups`).
- **Clarifier internals:** `backend/app/agents/clarifier_agent.py` (`_generate_followup_questions`, `_handle_user_answer` — slot names DEDUPED, `_handle_new_plan`, `_detect_refinement_action`); packs in `backend/app/agents/category_question_packs.py`; compose/prices/budget in `backend/mcp_server/tools/product_compose.py`; refinement chip generation in `backend/mcp_server/tools/next_step_suggestion.py`.
- **Frontend chat internals:** `components/ChatContainer.tsx`, `components/Message.tsx` (chips, MultiSelectQuestion), `components/blocks/BlockRegistry.tsx`, `components/ReviewConsensus.tsx`.
- **Git gotchas:** working dir may be shared with another session — check `git branch --show-current` before committing; use worktrees for isolation (`git worktree add ../rg-qa -b fix/qa-round4-X origin/main`). Bash-tool here-strings break → `git commit -F msgfile` / `gh pr create --body-file`. gitleaks scans per-commit → never let secret-shaped literals into any commit. Pre-squash branch trap: branch only off fresh `origin/main`.
- **Port 3000 = a DIFFERENT project.** Frontend dev (if ever needed) on 3001. The localhost:3003 stack is a demo the user is keeping — don't touch it.
- **Windows:** `/tmp` is flaky (write temp files to repo dir); `next/og` ImageResponse breaks the build; axe via CDN not npm.

## Part 5 — Deliverable

End the session with:
1. `QA_ROUND4_FINDINGS.md` — every finding, status (FIXED via PR #N / DOCUMENTED-DEFERRED), screenshots
2. All P0/P1 fixes merged + prod-verified
3. A short handoff block listing anything left open, appended to the findings file
