# Reconciliation — Codebase vs. `tone.md` + `reviewguide-spec.md`

**Date:** 2026-05-23
**Compared against:** `tone.md` (19,464 bytes) and `reviewguide-spec.md` (43,025 bytes), both at `C:\Users\habib\desktop\smartshop\`. Both supersede prior voice direction / planning per the human.
**Branch analyzed:** `main` at `ca1a9ec` (which is v2-with-swipe lineage + recent stabilization fixes incl. Fix 1 affiliate match-by-name).
**Reading guide:** ✓ Aligned · ⚠ Needs change · ✗ Missing · — Now out of scope.

A note on PR #5 (`fix/frontend-stabilization-2026-05`, open): its Fix 4 deletes `app/saved/` + `app/compare/` and removes those nav links. **The new spec mandates those screens** (§7.8, §7.9). PR #5 needs reshaping — keep Fixes 2/3/5 + CI green-up, drop Fix 4 — before merge. Flagged in the summary at the end of this file.

---

## ✓ Aligned — keep and refine

| Area | Codebase | Spec ref |
|---|---|---|
| Mobile-first Next.js 14 stack | `frontend/` (Next.js 14.2.35, Tailwind, framer-motion) | §1, §11 |
| Discover-as-homepage | `frontend/app/page.tsx` exports `DiscoverPage()`; `/browse` and `/discover` (in PR #5) redirect to `/` | §6.1, §7.1 |
| Two-way conversational chat with SSE | `frontend/components/ChatContainer.tsx`, `backend/app/api/v1/chat.py` (`/v1/chat/stream`, SSE) | §2 |
| Session-scoped chat memory (server) | `session_id` flows through SSE; `CHAT_CONFIG.SESSION_STORAGE_KEY` in localStorage | §2.4, §5.1 |
| Cookie-anchored persistence (no auth) | localStorage usage in `frontend/app/chat/page.tsx`, no user-auth on shopping flow | §5.2, §12 (no auth) |
| Affiliate via Amazon PA-API + curated `amzn.to` | `backend/app/services/affiliate/providers/amazon_provider.py`, `curated_amazon_links.py` | §4.1, §4.4 |
| Affiliate match-by-name (no positional mismatch) | `backend/mcp_server/tools/product_affiliate.py` `_match_curated_entry` (Fix 1, `5738cd1`, verified live) | §4.4 |
| Trending content on Discover (homepage isn't empty) | `frontend/components/discover/CategoryChipRow.tsx`, `TrendingCards.tsx` | §7.1 first-open empty state |
| BlockRegistry-driven `ui_blocks` rendering | `frontend/components/blocks/BlockRegistry.tsx` — extensible block types | §7.5 layout, §8.1 long-form bubble |
| Carousel rendering for product cards | swipe carousel exists in v2-with-swipe lineage (now on `main`) | §7.5 step 4, §8.4 |
| Affiliate disclosure page exists | `frontend/app/affiliate-disclosure/page.tsx` | §4.4 (subtle disclosure ok) |
| Chat history list on Discover | "Your recent chats" rendered in homepage | §7.1, §5.1 |
| Followup-question pattern *exists at the prompt level* (but wrong shape — see ⚠ #1) | `backend/mcp_server/tools/product_compose.py:623`, `:852` | §2.2 (right pattern, wrong count) |

---

## ⚠ Needs change — call-outs with file refs

### 1. Curious follow-up: spec mandates **one** contextual question, code emits **three**

**Spec:** `tone.md` §"The curious follow-up question" and `reviewguide-spec.md` §2.2 — every AI response ends with **one** contextual question. Example: *"Want me to factor in glasses fit, or are you contact-lens-only?"* (one question, branching inside it). Banned: *"Anything else?"*
**Codebase:**
- `backend/mcp_server/tools/product_compose.py:623` — system prompt: *"End with **2-3** specific follow-up questions like 'Want to compare the top two?' or 'Looking for budget alternatives?'"*
- `backend/mcp_server/tools/product_compose.py:852` — *"ALWAYS end with exactly **3** conversational follow-up questions … starting with something like 'Want to dig deeper?'"*
- `:869` — *"The follow-up questions at the end are REQUIRED — never skip them"*

**Change required:** reduce to **one** contextual follow-up question; rewrite the prompts to inject the tone.md voice and the *contextual specificity* rule (no "Want to dig deeper?" generic openers — must reference what was just discussed). Separate the question from the blog body in the response schema so the frontend can treat it distinctly (per spec §11 visual treatment).

### 2. Source citations rendered in UI — direct spec violation

**Spec:** §4.2 — "No direct user-facing citations. ReviewGuide synthesizes from these sources and forms its own conclusion. No 'according to RTINGS' — the AI speaks in its own voice." §11.6 "What to avoid → Source citation UI".
**Codebase:**
- `frontend/components/blocks/BlockRegistry.tsx:27` imports `SourceCitations`.
- `frontend/components/blocks/BlockRegistry.tsx:108` renders it for blocks with `data.products`.
- `frontend/components/SourceCitations.tsx` exists (the citation UI component).
- Backend `GraphState` carries `citations`, `tool_citations`, `evidence_citations` (`Annotated[List, operator.add]` reducers) and `chat.py` SSE emits citation events.

**Change required:** remove the `SourceCitations` import/render from BlockRegistry; delete the component file; stop emitting citation events from `chat.py`. **Keep** the internal `citations` / `tool_citations` plumbing inside the backend for logging/eval purposes if useful, but never surface to the client.

### 3. Filter / refinement sidebar on `/chat` — direct spec violation

**Spec:** §11.6 — "No filter chip bars / refinement sidebars (the conversation IS the filter)." §2.3 sticky composer, not a sidebar, drives refinement.
**Codebase:** `frontend/components/CategorySidebar.tsx` — a fixed sidebar on `/chat` with:
- 9 `QUICK_SEARCHES` chips (Budget Picks, Premium Finds, Trending Now, Top Rated, New Releases, Under $100, Under $500, Gift Ideas, Everyday Carry)
- A categories list (Travel, Electronics, Home Appliances, Health & Wellness, Outdoor & Fitness, Fashion & Style, Smart Home, Kids & Toys, Baby, Big & Tall)

These behave like a quick-filter / refinement panel. Rendered fixed-left on desktop and overlay on mobile (`frontend/app/chat/page.tsx:135`).

**Change required:** remove `CategorySidebar` from `/chat`. The conversation handles narrowing. The Categories list could survive on Discover as a *navigation* row (debate per design), but the Quick Searches sidebar leaves entirely.

### 4. AI voice in system prompts — pre-tone.md baseline

**Spec:** `tone.md` is the single source of truth; supersedes existing direction. Voice = editor (CNET/Wirecutter/RTINGS), no glazing, no hedging, no marketing verbs, no AI disclaimers. Banned-phrases blocklist applies to all AI outputs.
**Codebase:**
- `backend/mcp_server/tools/product_compose.py:623` — *"You are ReviewGuide, a friendly and knowledgeable AI shopping assistant."* Generic chatbot register.
- `:852` block uses *"Write them as a short paragraph starting with something like 'Want to dig deeper?'"* — borderline generic.
- All composer/agent prompts (`backend/app/agents/*.py`, `mcp_server/tools/*.py`) need a tone-rules block injected.

**Change required:** every AI-facing system/instruction prompt must include the tone.md voice rules + the banned-phrases blocklist + the curious-follow-up-question rule. Centralize as a shared `VOICE_PROMPT` constant so it's injected uniformly. Re-test outputs against the tone.md example exchanges.

### 5. `app/saved/page.tsx` and `app/compare/page.tsx` are placeholders, not the spec'd screens

**Spec:** §7.8 Saved with grid/list of saved products, AI positioning labels, multi-select → Compare. §7.9 Compare with two-column header, **AI-generated comparison verdict paragraph**, curated spec block, buy buttons.
**Codebase:** both pages exist as "coming soon" placeholders (per the 2026-05-19 handoff). PR #5 (open) tries to delete them entirely — that PR's Fix 4 now **conflicts with the spec** and must be reshaped before merge.

**Change required:** build out both pages to spec. **Drop the deletion** from PR #5 before merging it. Keep Fixes 2/3/5 and the CI green-up from PR #5.

### 6. Nav layout: desktop topbar + mobile bottom bar both include Saved + Compare — but spec also adds Profile

**Spec:** Discover, Saved, Compare, Personality profile are reachable; `tone.md` §personality memory model + spec §7.10 mandate a Profile entry point.
**Codebase:**
- `frontend/components/UnifiedTopbar.tsx` desktop nav: Discover, Saved, Ask, Compare. **No Profile entry**.
- `frontend/components/MobileTabBar.tsx` mobile bar: Discover, Saved, Ask (FAB), Compare, Profile (the Profile tab routes to a long-press popover, not a real screen).
- A Profile link comment in UnifiedTopbar: *"Profile link hidden 2026-04-21 — href was /browse (→ redirects to /), misleading."*

**Change required:** restore Profile as a real nav entry, pointing to a real `/profile` page (see Missing #1). Reshape PR #5's deletions so Saved + Compare stay.

### 7. Discover trending chips ≠ "tap-to-reply" + skip-to-loading spec behavior

**Spec:** §7.1 "Tap a trending chip → opens **Chat — empty** with the chip text pre-filled and submitted (skips straight to loading)."
**Codebase:** `frontend/components/discover/CategoryChipRow.tsx:32-38` — `handleChipClick` does `router.push(`/chat?q=${...}&new=1`)`. Then `frontend/app/chat/page.tsx:33` processes the param. End result is similar, but the *visual transition* is "navigate to chat, then loading" — verify it lands on the loading state cleanly without a flash of empty composer.

**Change required:** verify the chip-to-loading transition is seamless (no empty-chat flash). If not, route the chip directly to the loading state in `Chat — empty` or pre-mount the loading bubble before the LLM call.

### 8. Loading copy is generic, not the rotating ambiguous-curious vocabulary

**Spec:** §10.1 and tone.md "Loading state vocabulary" — rotate through "Searching the web…", "Seeing what others are saying…", "Cross-checking the specs…", "Hunting for the catch…", etc. Never name competitor sites.
**Codebase:**
- `frontend/components/Message.tsx` shows `message.statusText || 'Thinking...'` for the loading bubble.
- Backend tool contracts in `mcp_server/tools/*.py` define a generic `citation_message` per tool (e.g., "Comparing prices across retailers...", "Searching for products...", "Analyzing reviews..."). Per-tool, no rotation.

**Change required:** drive the loading bubble from a server-pushed rotating copy list (the §10.1 set), or rotate client-side from a constant. Make sure tool-specific phrases stay ambiguous (no provider names emitted to UI).

### 9. Quiz path — chip-as-tap-to-reply pattern is unverified

**Spec:** §7.4 — when the AI asks a clarifying question, it surfaces 2–5 chips as suggested answers, plus freeform composer. Chips must visually read as "tap to reply", not "select an option". Spec §13 #4 calls this out as an *open design question*.
**Codebase:** the `ClarifierAgent` exists (`backend/app/agents/clarifier_agent.py`) and generates clarifying questions, but the *chip group under each question* rendering isn't established as a distinct frontend pattern (the only chips on `/chat` today are the QUICK_SEARCHES in `CategorySidebar` — which the spec removes).

**Change required:** build a `QuizStep` component (spec §8.3) — AI bubble + chip group beneath it + freeform composer. Wire to clarifier agent's questions/options. Visual treatment per spec §9.1 + §13 #4.

### 10. Results blog: inline product hyperlinks that snap the carousel — likely missing

**Spec:** §7.5 step 3 + §9.3 — inline product name mentions in the blog (e.g., "the Bose QC Ultra") are tappable; tap snaps the carousel below to that product's card.
**Codebase:** `backend/mcp_server/tools/product_compose.py` generates the blog as prose; the response schema does not (currently) include structured markers mapping inline mentions to carousel card IDs.

**Change required:** extend the response schema so the blog includes inline product references as structured markers (anchor IDs that resolve to carousel card IDs). Frontend renders them as inline hyperlinks; tap → carousel `scrollIntoView` on the matching card. Spec §13 #2 (visual treatment) is an open question.

### 11. Spec table rendering on Results — risk

**Spec:** §11.6 "No spec tables on Results" — specs woven into prose. Tables live on Compare and Product detail (restrained).
**Codebase:** unconfirmed in this turn — `BlockRegistry.tsx` supports multiple block types including `comparison_html` and may render spec tables in product blocks. **Verify before changing.**

**Change required:** audit each block type renderer in `BlockRegistry.tsx`. Ensure spec-table-like layouts only appear on Compare and Product detail.

### 12. AI "purple/blue gradient" risk in current accent system

**Spec:** §11.3 — no "AI" purple/blue gradients; ReviewGuide isn't selling AI.
**Codebase:** `frontend/components/UnifiedTopbar.tsx` `ACCENT_COLORS = [{ id: 'indigo', color: '#1B4DFF' }, …]` and the default is `indigo` (`#1B4DFF` is a saturated blue). The chat's "New Chat" button uses `var(--primary)` ≈ that blue.

**Change required:** the brand identity is now a Claude Design open question (spec §13 #10). The current saturated indigo is the visual cliché. Defer specifics to design, but flag the current default as non-compliant with §11.3.

### 13. Resumed-chat opens scrolled to bottom — unverified

**Spec:** §2.5 + §7.6 — tapping a past chat opens it scrolled to bottom with sticky composer, all state preserved.
**Codebase:** the chat page reads `SESSION_STORAGE_KEY` and re-mounts `ChatContainer`. Scroll position on resume isn't explicitly anchored to bottom in `frontend/components/MessageList.tsx`'s current architecture (CONCERNS.md High #9 — "scroll architecture still race-prone").

**Change required:** verify resumed chat lands at the latest blog. May need explicit `scrollIntoView` on the latest assistant message after rehydrate.

### 14. Saved state confirmation: spec says no toast — verify

**Spec:** §9.7 — save = icon state change only, no "Saved!" toast.
**Codebase:** unconfirmed. **Verify** the current save flow.

### 15. The "happy path" pre-mounting (empty → fast/quiz → loading → Results)

**Spec:** §6.2 — explicit clickable spine. The product is one continuous chat surface; current architecture has `/chat` page rendering ChatContainer which shifts states. **Likely aligned, but verify** the transition is seamless (no page navigations between Chat → Loading → Results — they're the same surface re-rendering).

---

## ✗ Missing — gap list with spec section

| # | Spec ref | Gap |
|---|---|---|
| 1 | §7.10 + tone.md §personality memory | **Personality profile screen** at `/profile`. Viewable + editable. Shows learned register, vocabulary, stated priorities, categories explored, reset action. Currently no `app/profile/` dir; backend has zero `personality` or `Honcho` references. |
| 2 | §5.3 + tone.md §personality memory | **Personality profile *data layer*** — Honcho or equivalent memory store. Backend storage, read API (inject into system prompt for returning users), write API (post-conversation observations of register/vocab/priorities), edit/reset API. **Entirely missing**. |
| 3 | §7.5 step 3 + §9.3 | **Inline product hyperlink → carousel snap** behavior — see ⚠ #10. |
| 4 | §7.4 + §8.3 + §9.1 | **`QuizStep` component** (AI bubble + chip group + composer) — see ⚠ #9. |
| 5 | §7.9 | **Compare mode AI verdict** — backend endpoint that takes 2 product IDs (from Saved) and returns an editorial comparison paragraph in voice + curated spec rows. |
| 6 | §7.8 | **Saved-screen `compare` multi-select flow** — tap-and-hold or explicit select, exactly-2 constraint, Compare button activation. |
| 7 | §7.1 | **"Popular this week"** product list on Discover with thumbnail + AI take + price range. Currently Discover shows chips + trending cards; the spec'd "Popular this week" with the editorial AI take per product isn't explicitly there. |
| 8 | §2.2, §10.4, tone.md | **One contextual follow-up question per response** — see ⚠ #1 (change required + structural separation in response schema). |
| 9 | §10.1 + tone.md | **Rotating ambiguous loading copy** — see ⚠ #8. |
| 10 | §7.10 reset behavior | **Profile reset endpoint** — preserves chat history and saved items; only clears personality profile. |
| 11 | §7.6 | **Per-product "AI's take on this product specifically"** editorial block on `Product detail` route. Currently the route `/results/[id]` exists but unverified whether it has this per-product editorial paragraph in voice. |
| 12 | §6.1, §11.4 | **Loading animation as personality moment** — design open question (§13 #1), no current production-grade implementation. |
| 13 | §4.4 + tone.md | **Subtle affiliate disclosure** in settings/footer — exists at `/affiliate-disclosure` but verify it's reachable from Discover/profile, not just buried. |
| 14 | §2.5 | **Resumed-chat preserves carousel state + unsaved items in carousel** — verify the per-session carousel snapshot is rehydrated. |
| 15 | §10.5 | **Error / offline copy in voice** (e.g., *"Hit a wall pulling info on this one. Want to try a different angle?"*). Currently generic error strings (e.g., `[product_affiliate] Failed to get affiliate links` in `mcp_server/tools/product_affiliate.py:35`). |

---

## — Now out of scope — candidates for removal / deprecation

| Item | Spec ref | Codebase | Disposition |
|---|---|---|---|
| Source citation UI | §4.2, §11.6 | `frontend/components/SourceCitations.tsx`, `BlockRegistry.tsx:27,108`, citation SSE events from `backend/app/api/v1/chat.py` | Remove client-side. Keep internal backend reasoning, never surface. |
| Filter / refinement sidebar | §11.6, §12 | `frontend/components/CategorySidebar.tsx` on `/chat` | Remove from `/chat`. Categories list optionally migrates to Discover navigation. |
| Onboarding tooltips / coach marks | §11.6 | None observed | Confirm absence; do not add. |
| Spec tables on Results | §11.6 | Possibly in `BlockRegistry.tsx` block types | Audit + remove if present on Results layout. Tables ok on Compare + Product detail in restrained form. |
| Notifications / price alerts | §12 | None observed in product surface | Do not add. |
| Paywall / premium tier | §12 | None observed | Do not add. |
| Recently-viewed tracking | §5.1, §12 | None observed | Do not add. |
| User authentication (consumer-side) | §5.2, §12 | `frontend/app/login/page.tsx` (admin-side only); cookie-anchored shopping flow has no auth ✓ | Keep admin auth for ops; do **not** add consumer sign-in. |
| Gamification (streaks/badges/points) | §11.6 | None observed | Do not add. |
| Desktop-first layout assumptions | §1, §12 | `UnifiedTopbar` is a desktop-first nav; mobile-first design supersedes | Rebalance during Claude Design pass — desktop adapts down from a mobile-first system, not the other way. |
| Cross-chat memory (in chat content) | §2.4, §12 | Session memory is correctly scoped today (per session_id) | Confirm and hold. |
| Skeleton loaders for blog response | §11.6 | Unverified | Replace with the curious-loading bubble pattern (§7.7). |
| Sentry SDK on backend (per memory of past hotfix `d7581fc`) | — (out-of-scope-of-this-spec, but flag) | currently removed from `requirements.txt` per `d7581fc` hotfix; CONCERNS #2 wants it back | Not addressed by this spec; defer to CONCERNS handling. |

---

## Top-of-stack: what needs a human decision before code work begins

1. **PR #5 fate.** Its Fix 4 deletes `app/saved/` + `app/compare/`, which the new spec mandates. Reshape PR #5 (keep Fixes 2/3/5 + CI green-up, drop Fix 4) before merging — or close PR #5 and split into smaller PRs. (Pre-flight P2 question #2.)
2. **Personality profile data layer.** Spec says Honcho or Obsidian-style; nothing exists. Choose: Honcho (cloud-hosted, matches SAM Crew lessons), Obsidian-style (local markdown), or another local-first store. This decision blocks Backend Task 3.
3. **`SourceCitations` removal scope.** Confirm: remove the client UI but keep `citations`/`tool_citations` plumbing internal for ops/eval. Or fully strip.
4. **`CategorySidebar` removal scope.** Remove entirely, migrate the categories list to Discover, or keep as a hidden-by-default drawer? Spec is unambiguous about no filter sidebar on chat; the categories-as-navigation question is design's call.
5. **Brand color identity.** §11.3 forbids saturated "AI" indigo/blue. Current default accent is `#1B4DFF`. Defer to Claude Design, but flag now that the default needs to change before launch.
6. **Pre-flight P1–P4 decisions from prior turn.** Still unanswered: canonical branch (P2), v3 backlog disposition (P2), Milestone 1 Priority 1 (revisited now that the spec moves description-shift + travel-hang up the list — and the spec arguably reframes Milestone 1 as "build to the new spec" rather than the prior 5-fix punch list), secrets rotation timing (P3), stale-doc archive (P4).

---

*End of reconciliation. Next steps: review this report, lock the decisions above, then the FRONTEND_AGENT_CONTEXT.md and BACKEND_AGENT_CONTEXT.md (written alongside this report) become the working briefs for the build crew.*
