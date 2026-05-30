# Frontend Agent Context — ReviewGuide

**Reference this file for every visual design, component, microcopy, or frontend implementation decision.**
Companions: `tone.md` (voice), `reviewguide-spec.md` (design spec), `RECONCILIATION.md` (codebase audit).
**Treat `tone.md` and `reviewguide-spec.md` as the locked sources of truth.** They supersede any prior direction in the codebase, in `.planning/`, or in earlier AI prompts.

---

## Project overview

ReviewGuide is a mobile-first conversational product that helps people decide what to buy. Users ask about a category (headphones, laptops, hotels, flights, anything researchable); the AI runs a real two-way dialogue — asking clarifying questions when needed, returning a synthesized review-blog response with a ranked product carousel, and continuing to refine via follow-up turns.

The core insight: existing chatbots blow smoke. ReviewGuide is built around an editor's voice that ranks, commits, and gently redirects. The voice is the moat.

---

## Voice anchor

You are designing/coding strings for a product that sounds like **texting an editor from CNET, Tom's Guide, or RTINGS** — knowledgeable, curious, opinionated about *fit* (not about products), constitutionally incapable of blowing smoke. Reference points: Wirecutter's ranking discipline, Costco's brand of honesty, the voice of a friend who has spent ten years reviewing this stuff.

**Reference `tone.md` for every string, label, button, microcopy, error message, and AI-generated copy decision.** This includes button labels, empty states, loading states, settings copy, modal copy, error/edge-case copy.

### Banned phrases — literal blocklist (these must never appear, in any string, anywhere)

- "Great choice!" / "Excellent pick!" / "You'll love it!" / "You can't go wrong with…" / "You're going to be so happy with…"
- "Great question!" / "What a great question!" / "Happy to help!" / "I'd be glad to…"
- "As an AI…" / "I'm just a language model…"
- "Ultimately the decision is yours." / "It really depends on your needs." / "Everyone's different."
- "Game-changer" / "Best of the best" / "Crushing it"
- "Unlock" / "Elevate" / "Empower" / "Experience the…" / "Take your [X] to the next level"

The *pattern* behind these — empty enthusiasm, hedging, corporate marketing, AI-disclaimer — is also banned even when the literal words differ.

Quick-reference rules:
1. Opinionated about fit, not about products.
2. Rank, don't trash.
3. No glazing. Earn agreement when it's earned.
4. Every AI response ends with **one** contextual curious question.
5. Strong opinions on substance; humility on taste.
6. No source citations — synthesize.
7. Loading copy is curious and ambiguous (no competitor names).
8. Sound like an editor texting a friend, not a chatbot serving a user.

---

## The conversational model — frontend implications

### Two response shapes (the AI decides, the frontend renders)

**Fast path** — user asks → loading bubble (rotating curious copy) → blog + carousel render in the conversation thread → AI bubble ends with the one contextual follow-up question.

**Quiz path** — user asks → AI asks 2–5 clarifying questions, each as an AI bubble with a chip group beneath + freeform composer always available → final answer triggers loading → blog + carousel → curious follow-up.

The frontend doesn't decide which path runs — the backend signals it via the SSE event stream. The frontend renders whichever bubble/block type arrives next. Plan for both shapes from day one.

### Sticky composer behavior

Text input + send button, sticky to the **viewport bottom** on Chat (empty / fast / quiz), Results, and Resumed chat. On Results, the blog + carousel scroll above it; the composer is anchored. Keyboard handling: the composer floats above the soft keyboard; the content above scrolls.

### The curious-follow-up pattern (one question, visually distinct)

Every AI message — including the long-form blog on Results — ends with **exactly one** contextual question. It is the second-most-important thing in the product, after recommendation quality. Visual treatment: on its own line, subtly distinct (slight italic / different weight / separator) so users register the invitation, but still inside the AI's bubble. **Do not** make it look like a separate UI element — that breaks the "the editor is texting you" feel. The backend response schema separates this question from the blog body so you can render it distinctly.

Banned: *"Anything else?"* / *"Is there anything else I can help you with?"* / any generic offer. Questions are *contextual* (e.g., *"Want me to factor in glasses fit, or are you contact-lens-only?"* / *"Open to a one-stop if it shaves $200, or strictly nonstop?"*).

### Session-scoped memory

- Within one chat session: full memory of everything said. Conversation thread scrolls above the latest blog.
- Across sessions: no memory of *content*. Only the personality profile crosses sessions.
- Tapping a past chat from Discover opens that chat *scrolled to the bottom* (latest blog visible, sticky composer ready, carousel preserved).

---

## Screen inventory — ~10 screens, one-line purpose each

Reference `reviewguide-spec.md` §7 for full layout, components, states, and interactions per screen.

| # | Screen | Purpose | Spec ref |
|---|---|---|---|
| 1 | **Discover** (home) | Entry point — inviting, populated, never empty; trending + recent chats + saved entry + profile entry. | §7.1 |
| 2 | **Chat — empty** | Blank canvas for a new conversation; starter AI prompt + suggestion chips + sticky composer. | §7.2 |
| 3 | **Chat — fast path** | Simple/low-stakes query; user bubble → loading bubble → straight to Results render in-place. | §7.3 |
| 4 | **Chat — quiz path** | Complex query; AI asks 2–5 clarifying questions as bubbles+chip groups, then loading, then Results. | §7.4 |
| 5 | **Results** | The product's payload — editorial blog + ranked carousel + sticky composer. Single most important screen. | §7.5 |
| 6 | **Product detail** | Deeper view of a single product with the AI's take, key specs (as prose), pros/cons, buy. | §7.6 |
| 7 | **Loading state in chat** | Personality moment between user message and AI response; rotating curious copy + thoughtful animation. | §7.7 |
| 8 | **Saved** | Cookie-anchored stash of bookmarked products; multi-select → Compare. | §7.8 |
| 9 | **Compare mode** | Two products side-by-side with an AI-written verdict paragraph + curated spec rows + buy. | §7.9 |
| 10 | **Personality profile (settings)** | "About you" — viewable + editable view of what the AI has learned (register, priorities, categories); reset action. | §7.10 |

---

## Component library — with current codebase state

Reference `reviewguide-spec.md` §8 for full component contracts. Status per `RECONCILIATION.md`.

| Component | Status | Notes / current file (if exists) |
|---|---|---|
| **AI bubble (short)** | ⚠ needs voice review | `frontend/components/Message.tsx` — existing bubble; ensure microcopy + statusText align with tone.md |
| **AI bubble (long-form / blog)** | ⚠ needs change | Rendered via BlockRegistry on `/chat` results; needs response-schema separation of body vs. follow-up question, plus inline-product-hyperlink support |
| **AI bubble (loading)** | ⚠ needs change | Today: `message.statusText \|\| 'Thinking...'`. Needs rotating ambiguous copy + thoughtful animation (open design Q §13 #1) |
| **User bubble** | ✓ exists | `Message.tsx` user variant |
| **Suggestion chip** (tap-to-reply, not form-option) | ⚠ exists, needs visual rework | `frontend/components/discover/CategoryChipRow.tsx` chips exist; quiz-step variant doesn't yet (must look like tap-to-reply per §13 #4) |
| **Quiz step** (AI bubble + chip group + composer) | ✗ missing | Need to build as a composite component (`QuizStep.tsx`) wired to the ClarifierAgent's question payloads |
| **Carousel container** (horizontal swipe + peek-of-next) | ⚠ partial | Swipe carousel exists in v2-with-swipe lineage on main; verify peek-of-next-card + snap behavior matches §9.2 |
| **Carousel card** (image, name, AI label, price, save) | ⚠ partial | Cards exist; verify density (§13 #7) and AI positioning label is shown |
| **Inline product hyperlink** (in blog → snaps carousel) | ✗ missing | Blog text doesn't carry structured product markers today; needs backend schema work + frontend renderer + scroll-snap (§13 #2 visual treatment) |
| **Sticky composer** | ⚠ verify | Composer exists in ChatContainer; verify sticky behavior on Results + keyboard handling per §9.4 |
| **Save toggle (bookmark)** | ⚠ verify | Card save likely exists; confirm: instant icon state change, **no toast** (§9.7) |
| **AI take block** (Product detail) | ✗ likely missing | `/results/[id]` route exists; per-product editorial paragraph in voice needs verification/build |
| **Spec lines** (Product detail) | ⚠ verify | Audit current product detail layout — must be prose-style lines, not a dense table |
| **Pros & cons block** | ⚠ verify | Audit; tone.md voice required |
| **Buy button** (outbound affiliate) | ✓ exists | Amazon affiliate / eBay; confirm prominent-but-not-screaming styling (§7.6) |
| **Two-column product header** (Compare) | ✗ missing | `app/compare/page.tsx` is a placeholder; needs full build |
| **AI comparison paragraph** (Compare) | ✗ missing | Backend endpoint + frontend render needed |
| **Curated spec comparison block** (Compare) | ✗ missing | Restrained spec rows; only specs that matter for the user's stated priorities |
| **Editable profile field** (Profile) | ✗ missing | No `/profile` page exists yet |
| **Removable chip** (Profile) | ✗ missing | Same |
| **Reset button** (Profile) | ✗ missing | Same |

---

## Interaction patterns — the ones that are easy to get wrong

(Pull from spec §9 + §13.)

1. **Quiz chips look like tap-to-reply, not form options.** Chips appear under the AI's question, look conversational, *and* the composer is always available. Visual cue: rounded, single-line, hover-tappable, no checkbox glyph, not "select an option" UI. (§9.1, §13 #4.)

2. **Blog ↔ carousel hyperlink snap.** When a product name in the blog body is tapped (e.g., *"the Sonos Ace"*), the carousel below smooth-scroll-snaps to that product's card. The blog explains; the carousel acts. The link should read like editorial writing's hyperlink, not a button. (§9.3, §13 #2.)

3. **Carousel peek-of-next-card.** A sliver of the next card is always visible on the right edge when more cards exist. This is *intentional whitespace* and a swipe affordance; not crowding. (§9.2, §11.5.)

4. **Sticky composer + keyboard.** Composer anchored to viewport bottom on Chat/Results/Resumed chat. When the soft keyboard opens, the composer floats above it; content scrolls. Composer is not blocked by the carousel or the blog. (§9.4.)

5. **Loading → Results transition.** The loading bubble *transforms into* the blog bubble — smooth transition, not a jarring swap. On a follow-up turn, the prior blog scrolls up into the thread above as a new loading bubble appears in its place, then renders the new blog. (§9.5.)

6. **Resumed chat opens scrolled to the bottom.** Past chat tapped from Discover history → opens with the latest blog visible, carousel below it, sticky composer ready. Not a summary, not a fresh start, not the top of the conversation. (§9.6, §2.5.)

7. **Save is instant, no toast.** Tap bookmark → icon state flips immediately; cookie writes async. No "Saved!" confirmation overlay. Icon state change *is* the confirmation. (§9.7.)

8. **Compare flow.** From Saved: tap-and-hold (or explicit select toggle) → multi-select mode → user picks **exactly two** → Compare button activates → brief loading → Compare mode renders. (§9.8.)

9. **Trending chip on Discover → straight to loading.** Tapping a trending chip on Discover skips the empty-chat state and goes straight into loading (chip text becomes the first user message). (§7.1 Interactions.)

10. **Loading copy rotates.** If the load takes more than ~2 seconds, the curious copy rotates ("Searching the web…" → "Cross-checking the specs…" → "Hunting for the catch…"). Never names competitor sites. (§7.7, §10.1, tone.md.)

11. **The follow-up question is one line, contextual, visually distinct, inside the bubble.** Not a separate component, not a button, not a chip. A line of italic-or-similar treatment that reads as the AI continuing the conversation. (§2.2, §11, tone.md.)

12. **Carousel is NOT sticky.** It lives at the end of the blog. The user reads, then swipes. The conversation (composer) is what's sticky, not the carousel. (§7.5.)

---

## Visual guardrails — the non-negotiables

**Overall feel:** Editorial-modern. Warm, not cute. Confidence without quirk. Generous whitespace on conversational screens; tighter on the blog (editorial layout with narrower line lengths). The blog deserves real typographic care — a serif body or serif headers is worth considering. (§11.1, §11.2, §11.5.)

**Color:** Subtle warmth — slight cream / slight off-white / slight warm gray. Not stark white-on-black. Not aggressively corporate. One or two accents, used sparingly. (§11.3.)

### What to avoid (the non-negotiable "don't" list)

- ❌ **AI sparkle / star iconography** — the universal "this is AI" cliché. Don't.
- ❌ **Source citation UI** — we don't have citations. Spec §4.2 explicit. (Note: `frontend/components/SourceCitations.tsx` currently exists and renders — RECONCILIATION.md ⚠ #2 — must be removed.)
- ❌ **Filter chip bars or refinement sidebars** — the conversation IS the filter. (Note: `frontend/components/CategorySidebar.tsx` on `/chat` violates this — RECONCILIATION.md ⚠ #3.)
- ❌ **Spec tables on Results** — the blog weaves specs into prose; tables live on Compare and Product detail in restrained form.
- ❌ **"AI" purple/blue gradients** — ReviewGuide isn't selling AI. (Note: current default accent `#1B4DFF` is a saturated blue; flag for Claude Design.)
- ❌ **Onboarding tooltips, coach marks, "did you know?" popovers** — no.
- ❌ **Gamification** — no streaks, badges, points.
- ❌ **Heavy modal overlays** — no.
- ❌ **Notification toasts for non-critical events** — no.
- ❌ **Skeleton loaders for the blog response** — use the curious loading bubble instead.

---

## Open design questions

These are deliberate decisions deferred to the design phase. **Make a call and document the reasoning** rather than defer back to the human.

1. **Loading animation form** — what does "thoughtful, slightly playful, not frantic" actually look like? High-impact for a small amount of pixels. (§13 #1.)
2. **Visual treatment of the inline product hyperlink** — underline? color shift? subtle background? Should read like editorial writing's hyperlinks. (§13 #2.)
3. **Visual treatment of the curious follow-up question** — italic? separator? own line? Subtle invitation without becoming a separate UI element. (§13 #3.)
4. **Suggestion chip styling** — must look like "tap to reply", not "select an option from a form." (§13 #4.)
5. **Blog typographic system** — serif vs. sans body, section delimiters, how the verdict lede stands apart. (§13 #5.)
6. **Discover composition** — trending products + recent chats + saved entry without feeling like a crowded feed. (§13 #6.)
7. **Carousel card density** — enough info to differentiate at a glance, not cluttered. (§13 #7.)
8. **Personality profile aesthetic** — calm and transparent, not buried; distinct from a generic settings page. (§13 #8.)
9. **Save toggle motion** — must feel satisfying to tap; the state change is the confirmation. (§13 #9.)
10. **Product color identity** — subtle warmth, no AI gradients; 2–3 directions worth exploring. (§13 #10.)

---

## File-by-file map

Per `RECONCILIATION.md`. Status legend: ✓ aligned · ⚠ needs change · ✗ missing.

### Pages (Next.js App Router)
- `frontend/app/page.tsx` — Discover (homepage). ✓ exists; needs §7.1 "Popular this week" + recheck per spec.
- `frontend/app/chat/page.tsx` — Chat surface (empty/fast/quiz/Results all render here as state changes). ⚠ needs the §2.2 follow-up-question separation + §9.5 loading→Results transform + §9.6 resumed-chat scroll-to-bottom verified.
- `frontend/app/discover/page.tsx` — `/discover` → `/` redirect (introduced by PR #5; safe to keep).
- `frontend/app/browse/[category]/page.tsx` — current category landing (existing). Verify it doesn't conflict with the spec's "no filter UI" rule.
- `frontend/app/results/[id]/page.tsx` — Product detail (carousel → tap → here). ⚠ verify §7.6 AI-take block + prose specs + voice.
- `frontend/app/saved/page.tsx` — **placeholder "coming soon"**. ⚠ rebuild to §7.8 spec. PR #5 attempts to delete this — drop that deletion.
- `frontend/app/compare/page.tsx` — **placeholder "coming soon"**. ⚠ rebuild to §7.9 spec. PR #5 attempts to delete this — drop that deletion.
- `frontend/app/profile/` — ✗ does not exist; needs build per §7.10.
- `frontend/app/affiliate-disclosure/page.tsx` — ✓ exists; spec §4.4 (subtle disclosure ok).
- `frontend/app/privacy/`, `frontend/app/terms/` — ✓ exists.
- `frontend/app/login/`, `frontend/app/admin/*` — admin-only; spec §5.2 forbids *consumer* sign-in; these are ops-side, keep separate.

### Components
- `frontend/components/UnifiedTopbar.tsx` — desktop topbar. ⚠ restore Profile entry; design for mobile-first means desktop is the adapt-from, not the primary.
- `frontend/components/MobileTabBar.tsx` — mobile bottom bar (Discover/Saved/Ask FAB/Compare/Profile). ⚠ Profile tab currently a long-press popover; needs to route to a real `/profile` page.
- `frontend/components/ChatContainer.tsx` — chat orchestration. ⚠ verify §9.5 loading→Results transform.
- `frontend/components/MessageList.tsx` — message rendering. ⚠ resumed-chat scroll-to-bottom (§9.6); CONCERNS.md High #9 (scroll race).
- `frontend/components/Message.tsx` — single message bubble. ⚠ blog variant needs structured follow-up-question separation.
- `frontend/components/blocks/BlockRegistry.tsx` — block-type → renderer mapping. ⚠ remove `SourceCitations` import + render at lines 27, 108. Audit each block type against spec §11.6 (no spec tables on Results).
- `frontend/components/SourceCitations.tsx` — — out of scope per §4.2. Delete.
- `frontend/components/CategorySidebar.tsx` — quick-searches + categories sidebar on `/chat`. — out of scope per §11.6. Remove from `/chat`; consider migrating categories list to Discover navigation (design call).
- `frontend/components/discover/CategoryChipRow.tsx` — Discover chips. ✓ trending chip pattern; verify chip-to-loading is seamless (no empty-chat flash).
- `frontend/components/discover/TrendingCards.tsx` — trending products. ⚠ verify §7.1 "Popular this week" structure (thumbnail + AI take + price range).
- `frontend/components/ConversationSidebar.tsx` — chat history list. ⚠ verify resumed-chat behavior (§9.6).
- `frontend/components/ErrorBoundary.tsx` — keep; ensure error copy in voice (§10.5).

### New files to create
- `frontend/app/profile/page.tsx` — Personality profile page (§7.10).
- `frontend/components/QuizStep.tsx` — AI bubble + chip group + composer composite (§8.3).
- `frontend/components/InlineProductLink.tsx` — inline blog hyperlink + carousel snap (§8.5, §9.3).
- `frontend/lib/loadingCopy.ts` — the rotating curious-copy list (§10.1).
- `frontend/lib/bannedPhrases.ts` — banned-phrase blocklist for any client-side string validation/lint.

### Files marked for deletion / deprecation
- `frontend/components/SourceCitations.tsx` — citation UI, out of scope.
- `frontend/components/CategorySidebar.tsx` — refinement sidebar on `/chat`, out of scope (verify zero call sites after removal).

---

## Done criteria

- [ ] **Every visible string** (UI labels, buttons, headers, empty states, errors, loading copy, microcopy) passes the `tone.md` voice check. No banned phrases.
- [ ] **Every screen** matches its `reviewguide-spec.md` §7 contract (purpose, layout structure, components, states, interactions).
- [ ] **Every component** matches its §8 contract.
- [ ] No items from the "what to avoid" list appear anywhere in production code or rendered UI.
- [ ] Visual guardrails (§11) are honored consistently across screens.
- [ ] Every AI long-form response renders the curious follow-up question on its own line, inside the bubble, visually distinct.
- [ ] Quiz chips render as tap-to-reply, not as form options.
- [ ] Carousel has peek-of-next-card + snap-on-swipe-end + tap-card → Product detail + save toggle (instant, no toast).
- [ ] Blog inline product hyperlinks snap the carousel to the matching card.
- [ ] Sticky composer is anchored to viewport bottom and behaves correctly with the soft keyboard.
- [ ] Loading bubble rotates through the ambiguous curious-copy set.
- [ ] Resumed chat opens scrolled to bottom with carousel state preserved.
- [ ] Saved screen + Compare mode + Personality profile screens are built to spec (not placeholders).
- [ ] No `SourceCitations`. No `CategorySidebar` on `/chat`. No spec tables on Results. No saturated AI-blue brand color. No tooltips/coach-marks. No gamification. No notifications. No skeleton loaders for the blog.
- [ ] Reconciliation report ⚠ + ✗ items addressed or explicitly deferred with reasoning.

*End of FRONTEND_AGENT_CONTEXT.md*
