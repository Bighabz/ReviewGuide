# ReviewGuide — Mobile-First Design Spec

> Source of truth for the ReviewGuide product design. Companion to `tone.md` (voice & personality — referenced throughout, not duplicated here).
> Intended for handoff to Claude Design (visual design) → Claude Code (build to spec).

---

## 1. Product overview

**ReviewGuide** is a mobile-first, conversational AI product that helps people decide what to buy. Users ask about a category (headphones, laptops, hotels, flights, anything researchable), and the AI runs a real two-way conversation — asking clarifying questions when needed, returning a synthesized review-blog response with a ranked product carousel underneath, and continuing to refine via follow-up turns.

The product's core insight: **the existing chatbot category does a poor job of purchase advice because chatbots are trained to affirm users.** A purchase advisor must be willing to rank, commit, and gently redirect. ReviewGuide is built around that voice (see `tone.md`).

**Who it's for:** Mixed audience, leaning toward considered and aspirational purchases. The AI calibrates to user depth over time via a growing personality profile.

**What it competes with:** Wirecutter (slow, static), Amazon's own recommendations (untrustworthy, sales-floor energy), ChatGPT/Perplexity for shopping queries (hedgy, glazing, fact-dumps), traditional review sites (require user to synthesize across sources).

**What makes it defensible:** The voice. The recommendation quality. The personality memory that compounds over time. The refusal to glaze.

---

## 2. The conversational model

The conversation *is* the product. Every screen serves the dialogue; the dialogue is never confined to a single screen.

### 2.1 Two response shapes

The AI judges question complexity on the fly and chooses between two shapes:

**Fast path** (simple, low-stakes purchases, or sufficient context already present):
- User asks → loading state → blog + carousel renders → AI ends with curious follow-up
- Example: "best wired earbuds under $50"

**Quiz path** (complex purchases, aspirational/considered categories, or insufficient context):
- User asks → AI asks 2–5 clarifying questions (chips + freeform) → loading state → blog + carousel renders → AI ends with curious follow-up
- Example: "I need a new laptop" / "Looking at hotels in Kyoto for April"

The AI decides which path based on category, prior chat context, and user signals (vocabulary, message length, prior history). This decision is invisible to the user — it just happens.

### 2.2 The curious follow-up (pattern, not feature)

**Every AI response — including the blog response — ends with a contextual question.** This is the single most important pattern in the product (see `tone.md`). It is the signal that the chat is alive and the conversation can continue. It is never "Anything else?" — always specific to what was just discussed.

### 2.3 Sticky chat input

The chat composer is **sticky at the bottom of the Results screen**. The conversation continues on the same screen — user types a follow-up, the blog and carousel update (re-rendered, not appended). The conversation thread above the input scrolls.

### 2.4 Session-scoped memory

- **Within a chat session**: full memory. The LG TVs chat remembers everything said in the LG TVs chat.
- **Across chat sessions**: no memory. The headphones chat does not know about the LG TVs chat.
- **Personality profile**: separate, persistent layer that grows across sessions. Shapes register and depth, never opinions. (See `tone.md` and §5.)

### 2.5 Resumed sessions

Tapping a past chat in history opens it **scrolled to the bottom**, latest blog visible, sticky input ready. Not a summary. Not a fresh start. The user picks up exactly where they left off, including any unsaved items still in the carousel.

---

## 3. Voice & personality

**See `tone.md` — that is the single source of truth.** This section captures the *design implications* of the voice, not the voice itself.

Design implications:

- **Microcopy across every screen must honor the voice.** Loading states, empty states, button labels, error messages, settings copy — all of it is in the curious-editor voice. No corporate marketing. No banned phrases (see `tone.md` blocklist).
- **Loading states are personality moments**, not filler. Use the ambiguous-curious vocabulary in `tone.md` (e.g., "Seeing what others are saying…"). Rotate. Never name competitor sites.
- **Empty states are never empty.** First-open Discover shows trending content. Empty saved shows a curious prompt. The product never has a "Nothing here" dead-end.
- **Every AI message bubble ends with a follow-up question.** This must be visually distinct enough that users register the invitation but not so distinct that it feels like a separate UI element. A subtle treatment — e.g., the question on its own line, slightly different weight or italic — is probably right.

---

## 4. Data & trust model

### 4.1 Sources

- **SerpAPI** for web-wide product specs and review content
- **Amazon Product Advertising API (PA-API)** for Amazon-side review summaries, product metadata, and affiliate links
- **No scraping** of any site (including Amazon's web property)
- **No direct user-facing citations.** ReviewGuide synthesizes from these sources and forms its own conclusion. No "according to RTINGS" — the AI speaks in its own voice.

### 4.2 Why no citations

This is a deliberate design and product decision (also legally defensible):

- The product's voice is "an editor with a take," not "an aggregator routing to other sites."
- Trust comes from the *quality of the recommendation*, not from "I can verify this against the source."
- Avoiding republication of competitor review content keeps the product on safer copyright ground.
- The user's job ends at the carousel. They came for a verdict, not a reading list.

### 4.3 Loading copy

Loading states use the ambiguous vocabulary from `tone.md` ("Seeing what others are saying…", "Digging for answers…", etc.). Never names specific competitor sites or review brands.

### 4.4 Affiliate links

Carousel product cards link out to purchase pages (Amazon affiliate links via PA-API; non-Amazon products link to the manufacturer or appropriate retailer). The affiliate relationship is **not hidden** — a subtle disclosure is fine in the settings or footer — but it is not foregrounded. The voice's honesty is the disclosure that matters.

---

## 5. Memory & personalization

### 5.1 What persists

| Layer | Scope | Storage | User-visible |
|-------|-------|---------|--------------|
| Chat session memory | Within one chat | Server (session-scoped) | Yes — it's the chat |
| Chat history | List of past chats | Cookie + server | Yes — Discover history section |
| Saved items / collections | Across the device | Cookie-anchored | Yes — Saved screen |
| Personality profile | Growing over time | Cookie + server-backed (Honcho/Obsidian-style) | Yes — viewable & editable |
| Recently viewed | — | — | **Not implemented** |

### 5.2 No accounts

- No sign-in for v1. No onboarding screens.
- Cookie-anchored persistence for everything user-specific.
- Soft sign-in gate may be added later when users hit a moment of friction (e.g., "want these to follow you to another device?"). Out of scope for this spec.

### 5.3 Personality profile

The personality profile is **viewable and editable** by the user. This is on-brand — a product that treats users as smart adults does not learn invisibly. A lightweight settings/profile screen shows:

- What the AI has learned about the user's vocabulary and depth ("You're comfortable with technical specs — I'll keep it short.")
- Recurring stated priorities ("You usually cap budgets around $300.")
- Categories the user has researched
- An option to reset the profile or correct specific entries

The profile shapes **register and depth**, never **opinions**. The AI does not learn to agree with the user. (See `tone.md` §personality memory model.)

---

## 6. Information architecture & flow map

### 6.1 Top-level screens

```
Discover (home)
├── New chat
│   ├── Chat — empty (composer only, no messages yet)
│   ├── Chat — fast path
│   │   └── Loading → Results
│   ├── Chat — quiz path
│   │   └── Clarifying questions (chips + freeform) → Loading → Results
│   └── Results (blog + carousel + sticky input)
│       ├── Continue conversation → blog re-renders
│       ├── Tap carousel card → Product detail
│       ├── Tap hyperlinked product in blog → carousel jumps to that card
│       └── Save product → Saved
├── Trending (always visible on Discover; doubles as empty state)
├── Recent chats (history list)
│   └── Tap → resumed chat session (scrolled to bottom)
├── Saved
│   ├── Saved items grid/list
│   └── Compare two → Compare mode
├── Personality profile (settings)
```

### 6.2 The happy path (clickable spine)

The path Claude Design and Claude Code should treat as the "designed and wired" core flow:

1. **Discover** (first open, with trending)
2. **New chat — empty** (user taps "ask anything" or a trending prompt)
3. **Chat — fast path** OR **Chat — quiz path** (depending on the prompt)
4. **Loading state** (curious copy)
5. **Results** (blog + carousel + sticky input)
6. **Product detail** (tap a carousel card)
7. **Back to Results**
8. **Continue conversation** (type a follow-up → results re-render)
9. **Save a product**
10. **Return to Discover** (chat now appears in recent chats)
11. **Resumed chat** (tap recent chat → opens at bottom)

Secondary screens (Saved, Compare, Personality profile) are part of the design set but do not need to be wired in a clickable prototype. They are reachable from Discover.

---

## 7. Screen-by-screen spec

Each screen is described by purpose, layout structure (in words), components used, content & states, and interactions.

> **Note for Claude Design:** layout descriptions intentionally avoid prescribing visual styling. Use the visual guardrails in §11 to make those decisions. Layouts describe *what is on the screen and in what relationship*, not how it looks.

---

### 7.1 Discover (home)

**Purpose:** Entry point. Inviting, populated, never empty. Establishes the curious voice on first impression.

**Layout structure (top to bottom):**

- App identity / wordmark (subtle, top)
- Primary prompt / search-style input ("Ask about anything you're researching" — or similar curious phrasing per `tone.md`)
- **Trending right now** — horizontal scrolling row of trending search prompts as chips ("Best wireless earbuds 2026", "Tokyo hotels for cherry blossom", "Laptops under $1500 for design work", etc.). Mix categories — headphones, hotels/flights, laptops — so the product's range is visible.
- **Popular this week** — vertical list or grid of trending products with thumbnail, name, brief AI take ("Most-recommended ANC pick this week"), price range
- **Your recent chats** — list of resumable past sessions, each showing a 1-line title (auto-generated from the topic), timestamp, and a brief preview of the last AI message
- **Saved** entry point (link or section)
- **Personality profile** entry point (subtle, possibly in a header avatar or footer)

**Components used:** prompt input, trending chip row, product card (small), chat history row, navigation entry points.

**States:**
- **First-ever open** (no history, no saves): trending content fills the screen. No "Nothing yet." The trending section *is* the empty state.
- **Returning user**: recent chats and (if applicable) saved items appear above the trending content.

**Interactions:**
- Tap prompt input → opens **Chat — empty** with cursor in composer
- Tap a trending chip → opens **Chat — empty** with the chip text pre-filled and submitted (skips straight to loading)
- Tap a trending product → opens **Product detail**
- Tap a recent chat → opens **Resumed chat** (scrolled to bottom)
- Tap Saved → opens **Saved**
- Tap profile → opens **Personality profile**

---

### 7.2 Chat — empty (new chat)

**Purpose:** The blank canvas of a new conversation. Inviting, low-friction, no premature commitment.

**Layout structure:**

- Top: minimal header (back arrow to Discover, possibly a "new chat" label)
- Middle / large empty area: a single curious prompt from the AI as a starter bubble (rotating, e.g., *"What are you trying to figure out?"* / *"What are you researching?"* / *"What's on your mind?"*)
- Below the prompt: optional **suggested starters** as tappable chips (a handful, rotated based on trending: "Find me wireless earbuds under $100", "Hotels in Tokyo for April", etc.) — these collapse or hide once the user starts typing
- Bottom: sticky composer (text input, send button)

**Components:** chat bubble (AI starter), suggestion chips, composer.

**States:**
- Default: starter prompt visible, suggestion chips visible
- User typing: chips fade or collapse

**Interactions:**
- Tap a suggestion chip → submits as the user's first message → transitions to Chat — fast path or quiz path
- Type and send → submits → transitions to Chat — fast path or quiz path

---

### 7.3 Chat — fast path

**Purpose:** Handle simple/low-stakes queries that don't need clarification. Brief loading, then straight to Results.

**Layout structure:**

- Top: minimal header
- Conversation thread:
  - User's message bubble
  - AI loading state (curious copy, animated — see §9.3)
- Sticky composer at bottom

**Components:** user bubble, AI loading bubble, composer.

**States:**
- Loading: AI loading bubble with rotating curious copy
- After loading: transitions to **Results** (which is conceptually the same screen with the blog and carousel rendered — see §7.5)

**Interactions:**
- Loading is non-interactive; ideally cancellable via a subtle "stop" affordance (out of scope to design in detail).

---

### 7.4 Chat — quiz path

**Purpose:** Handle complex queries that need clarification before the AI can give a useful answer. Feels like a conversation, not a form.

**Layout structure:**

- Top: minimal header
- Conversation thread (scrollable):
  - User's initial message bubble
  - AI clarifying message bubble — short framing ("Happy to help narrow this. A few questions:") followed by the first question
  - **Tappable chip group** of suggested answers for the question (2–5 chips)
  - Freeform option always available via the composer
- After the user answers (tap or type):
  - User's answer appears as a bubble
  - AI follows up with the next question (and chips)
- Continues for 2–5 turns total, then transitions to loading and Results

**Components:** AI bubble, user bubble, suggestion chip group, composer.

**States:**
- Mid-quiz: previous Q&A turns scroll up, current question is at the bottom with its chips
- Final question answered: chips disappear, AI loading state appears, then transitions to Results

**Interactions:**
- Tap a chip → submits as user answer → next question appears
- Type freeform answer → submits → next question appears
- Composer always available; user can interject at any point ("actually let me also mention…")

**Important design note:** the quiz must feel like a *curious editor asking questions*, not a *form gathering data*. Visual treatment of chips and bubbles should reinforce that — chips should look more like "tap to reply" than "select an option." Tone in the AI bubbles should be conversational and contextual to prior answers, not generic.

---

### 7.5 Results (blog + carousel + sticky input)

**Purpose:** The product's payload. A long-form, editorial review-blog response that synthesizes the AI's research into a clear ranking, followed by the carousel of products. Conversation continues from here via the sticky input.

**Layout structure (top to bottom):**

1. **Top: minimal header** (back arrow to Discover, chat title)
2. **Conversation thread above the blog** — the prior user and AI messages from this chat session remain visible if the user scrolls up. The blog response itself is the most recent AI bubble, expanded.
3. **Blog response** (vertical scroll, long-form):
   - **Verdict lead** — short opening that states the top pick and the rationale in 1–3 sentences. Always reads like an editor's lede.
   - **Body sections** — depending on category, may include:
     - "Why [top pick] wins for you" — synthesis section explaining the recommendation against the user's stated priorities
     - Per-product mini-sections for ranked alternatives ("If you want X instead…")
     - Tradeoff explainers ("Sound vs. ANC: here's how the contenders sort")
     - Specs and facts woven into prose, not tabled (this is editorial, not a spec sheet)
   - **Inline product hyperlinks** — when a product is named in the blog (e.g., "the Bose QC Ultra"), it is a tappable link. Tapping it scrolls/snaps the carousel below to that product's card.
   - **Closing curious question** — the blog ends with a contextual follow-up question from the AI, inviting the next turn. Visually distinct (own line, slightly different treatment) but still part of the AI's voice.
4. **Product carousel** (horizontal swipe, at the end of the blog):
   - Cards for each ranked product (typically 3–6)
   - **Peek of next card** visible on the right edge — signals "more to swipe"
   - Each card: product image, name, brief AI-positioned label ("Top pick — best all-rounder"), price (or price range), save button (bookmark icon)
   - Tap card → **Product detail**
5. **Sticky composer at bottom** — always visible, conversation continues here

**Components:** AI bubble (long-form blog variant), inline product link, carousel, carousel card, save toggle, composer.

**States:**
- Default rendered state
- After user sends a follow-up: composer state shifts to loading, the entire blog + carousel is replaced/re-rendered with the new response (the prior blog scrolls up into the conversation thread above)
- Saved state of a carousel card: bookmark icon filled

**Interactions:**
- Scroll the blog vertically
- Tap an inline product name → carousel below jumps/snaps to that product card
- Swipe carousel horizontally; tap a card → Product detail
- Tap save on a card → product is added to Saved (cookie-anchored)
- Type in composer → submits a follow-up → loading state → re-rendered Results

**Important design notes:**
- The carousel is **not sticky**. It lives at the end of the article. The user reads first, then swipes.
- The conversation is the primary interaction model. The sticky composer makes that visible at all times.
- This screen does the heaviest lift in the entire product. It must feel rich (editorial), actionable (carousel + save), and alive (sticky input, follow-up question). The voice is doing the work — the layout must give the voice room.

---

### 7.6 Product detail

**Purpose:** Where the user lands after tapping a carousel card. Deeper view of a single product, with the AI's take on it specifically.

**Layout structure (top to bottom):**

- Top: header (back arrow to Results, save button in the corner)
- Hero image (or image gallery — swipeable)
- Product name, brand
- AI's positioning label ("Top pick — best all-rounder for your situation")
- Price + outbound buy link(s) (Amazon affiliate or appropriate retailer)
- **The AI's take on this product specifically** — a short editorial paragraph (2–4 sentences) explaining why it's the pick (or the alternative) for this user. Voice consistent with the blog.
- Key specs section — facts woven into short readable lines, not a dense table. Limited to the specs that actually matter for the user's stated priorities.
- Pros & cons — short, honest, both written in editor voice. No "this product is amazing!" — instead, concrete observations ("Excellent for plane drone. The case is bulkier than the XM5's, which matters if your bag is tight.")
- Related / alternatives — a brief link back to the Results blog or a small horizontal mini-carousel of the other ranked products

**Components:** image gallery, save toggle, buy button (outbound), AI take block, spec lines, pros & cons block, mini-carousel.

**States:**
- Default
- Saved: bookmark filled

**Interactions:**
- Swipe images in hero
- Tap save
- Tap buy → outbound affiliate link (new tab / external browser handoff)
- Tap back → returns to Results, scroll position preserved, carousel position preserved
- Tap a related product → navigates to that product's detail

---

### 7.7 Loading state in chat

**Purpose:** A personality moment between the user's message and the AI's response. The AI is doing real work; the loading state communicates that with curiosity, not anxiety.

**Layout:**
- AI bubble at the bottom of the conversation thread, containing the curious copy ("Seeing what others are saying…")
- Subtle animation — could be a typing-dots variant, a subtle pulse, or something more characterful that Claude Design defines. The animation should feel *thoughtful*, not *frantic*.
- Copy rotates if the loading takes more than a few seconds (e.g., "Seeing what others are saying…" → "Cross-checking the specs…" → "Sorting the contenders…")
- Composer remains visible but disabled (or accepts input that queues for after the response)

**Components:** AI loading bubble, rotating copy, animation.

**Note:** This is a high-impact screen for a small amount of pixels. The voice and motion together establish whether the AI feels alive or feels like a spinner. Worth real design attention.

---

### 7.8 Saved (collection management)

**Purpose:** A place users return to for products they've bookmarked. Cookie-anchored, no account required.

**Layout structure:**

- Top: header ("Saved" or curious equivalent — never just "Saved Items")
- A subtle line of microcopy clarifying device-scoped persistence ("Saved on this device" — small, footer-y, not a disclaimer alarm)
- Grid or list of saved products, each card showing image, name, price, the AI's original positioning label for that product (so users remember *why* they saved it)
- Multi-select affordance — tap-and-hold or a "compare" entry point that lets the user pick two products to compare side-by-side
- Sort / filter affordance is **out of scope** — conversation handles filtering elsewhere; Saved is a simple stash

**Components:** product card (saved variant — includes original positioning label), select toggle, compare button.

**States:**
- Default with items
- Empty: a curious empty-state per `tone.md` ("Nothing saved yet. When you find something worth coming back to, tap the bookmark.")

**Interactions:**
- Tap a card → Product detail (preserved from when it was saved)
- Tap-and-hold (or tap a select toggle) → enters multi-select mode → user picks two → Compare button activates → tap Compare → Compare mode
- Tap unsave on a card → removes from saved

---

### 7.9 Compare mode (two products side-by-side)

**Purpose:** Let the user directly compare two products they've shortlisted. Helpful for high-consideration purchases where the user is down to a final two.

**Layout structure:**

- Top: header ("Comparing")
- Two-column layout (each column is roughly half the screen width):
  - Product image at top of each column
  - Product name, brand
  - Price
  - The AI's positioning label for each
- Below the two columns: **AI-written comparison paragraph** — short, editorial, takes a position. "For your priorities, the [X] is the pick because [Y]. The [Z] would be the right call if [edge case]." This is the unique value of Compare mode — not a spec grid, but an actual verdict between the two.
- Below the AI's verdict: a comparison block, line-by-line, of the specs that *actually matter* for this user's stated priorities. Not a dump of every spec — a curated set. Each row shows the spec name and the value for each product, with the better one subtly indicated.
- Bottom: two buy buttons (one per product), or a single "Go with [pick]" button that links out to the AI's recommended pick.

**Components:** two-column product header, AI comparison paragraph, curated spec comparison block, buy buttons.

**States:**
- Default (both products loaded)
- Loading (briefly, while the AI generates the comparison verdict)

**Interactions:**
- Tap either product image/name → that product's detail
- Tap buy → outbound affiliate
- Tap back → returns to Saved (with selection preserved or cleared, depending on what feels right — Claude Design's call)

**Important design notes:**
- Compare mode is **not a spec table**. It's an *opinion* about which of two products is right for the user. The spec block supports the opinion; the opinion leads.
- The voice in the AI comparison paragraph is the same editor voice. Commits to a pick. Conditions on use case. No "they're both great!"

---

### 7.10 Personality profile (settings)

**Purpose:** The user-facing view of what the AI has learned about them. Editable. Reset-able. Transparent.

**Layout structure:**

- Top: header ("About you" or similar curious framing — not "Settings" or "Profile")
- Short intro line in voice: *"Here's what I've picked up from our conversations. Edit anything that's off."*
- Sections:
  - **How you like to be talked to** — derived register: technical depth, jargon comfort, preferred response length. Each shown as a brief description with an "edit" or "looks right" affordance.
  - **Your usual priorities** — recurring constraints the AI has noticed ("You usually cap budgets around $300.", "You prefer wireless over wired.", "Reliability matters more to you than features."). Each editable or removable.
  - **Categories you've explored** — a simple list (headphones, hotels, laptops). Read-only.
  - **Reset everything** — a destructive action, clearly labeled. Resets the personality profile but preserves chat history and saved items.
- Below: brief settings (notifications toggle if applicable, affiliate disclosure, terms/privacy links). Kept minimal.

**Components:** editable profile field, removable chip, reset button, supporting links.

**States:**
- New user with little learned: shows a friendly version ("Still getting to know you. Ask a few things and this fills in.")
- Established user: populated

**Interactions:**
- Tap to edit any learned attribute (opens a small editor — text field or chip group)
- Remove an attribute
- Reset all

**Important design notes:**
- This screen is doing trust work. Transparency *is* the feature. The visual treatment should feel calm and considered, not buried or hidden away. Worth being a real surface in the IA, not a back-of-the-drawer settings page.

---

## 8. Component library

Reusable components referenced across the screen specs. Defined once here; Claude Design styles them consistently.

### 8.1 Chat bubbles

- **AI bubble (short)** — one or two sentences. Used in fast-path early turns, quiz-path questions, follow-up turns.
- **AI bubble (long-form / blog)** — the Results blog response. Multi-section, supports inline product hyperlinks, ends with the curious follow-up question on its own line.
- **AI bubble (loading)** — contains the rotating curious copy and the loading animation.
- **User bubble** — short, right-aligned (or whatever convention Claude Design picks for direction).

### 8.2 Suggestion chip

Tappable chip used for AI-suggested replies in quiz path, suggested starters in Chat — empty, and trending prompts on Discover. Should *not* look like a multi-select form option — it should look like a tap-to-reply.

### 8.3 Quiz step

Composite component: AI bubble (containing the question) + suggestion chip group below it. Composer remains available for freeform answers.

### 8.4 Carousel & carousel card

- **Carousel container** — horizontal swipe, peek-of-next-card on the right edge.
- **Card** — image, product name, AI positioning label, price, save toggle. Tap target = whole card → Product detail.

### 8.5 Inline product hyperlink

When a product is named in the blog (e.g., "the Bose QC Ultra"), it is a tappable, visually distinct inline link. Tapping it scrolls/snaps the carousel to that product's card. Visually subtle — not a button, more like a hyperlinked product mention in editorial writing.

### 8.6 Sticky composer

Text input + send button, persistently anchored at the bottom of conversational screens (Chat, Results, Resumed chat). On Results, sits below the carousel in the layout but is sticky to the viewport bottom.

### 8.7 Save toggle (bookmark)

Used on carousel cards and Product detail. Two states: unsaved and saved. Cookie-anchored.

### 8.8 Product detail components

- **AI take block** — editorial paragraph specific to this product, in voice.
- **Spec lines** — facts as short readable lines, not a dense table.
- **Pros & cons block** — short lists, honest, voice-consistent.
- **Buy button** — outbound affiliate link, prominent but not screaming.

### 8.9 Compare components

- **Two-column product header** — image, name, price for each.
- **AI comparison paragraph** — voice-consistent verdict between the two.
- **Curated spec comparison block** — rows with spec name and per-product values, subtly indicating the better.

### 8.10 Profile components

- **Editable profile field** — display of a learned attribute with an edit affordance.
- **Removable chip** — for stated priorities the user can clear.
- **Reset button** — destructive action, clearly labeled.

---

## 9. Interaction patterns

### 9.1 Quiz chip behavior

- Chips appear under the AI's question.
- Tap a chip → it's submitted as the user's answer → the chip group disappears, the user's message appears as a bubble, and the next question loads.
- Composer is always available — user can type a freeform answer instead of tapping a chip. Freeform answer behaves identically (submits, becomes user bubble, advances).
- Chips are *suggested* answers, not the only valid answers. The voice in the AI's question should make this clear ("…or just type if none of these quite match").

### 9.2 Carousel mechanics

- Horizontal swipe, native momentum.
- Peek of next card visible on the right edge at all times (when more cards exist).
- Snap-to-card behavior on swipe end — cards center cleanly, no awkward partial views.
- Tap = navigate to Product detail. Save toggle is a separate small tap target on the card.

### 9.3 Blog ↔ carousel hyperlink

- Inline product mentions in the blog (e.g., "the Sonos Ace") are hyperlinks.
- Tap → smooth-scroll the carousel below to center on that product's card.
- This creates a two-way relationship between the editorial reading and the actionable swiping. The blog explains; the carousel acts.

### 9.4 Sticky composer behavior

- Always visible on conversational screens (Chat — empty, Chat — fast/quiz path, Results, Resumed chat).
- On Results: composer is sticky to the viewport bottom even as the blog and carousel scroll above it.
- On send: the composer briefly shows loading state, then the AI response renders in the conversation thread (with loading state, then blog).
- Keyboard handling: composer floats above the keyboard when keyboard is open, content above scrolls accordingly.

### 9.5 Loading → Results transition

- Loading state is the AI bubble; rotating curious copy.
- When the response arrives, the loading bubble transforms into the blog response (smooth transition, not a jarring swap). The carousel renders below.
- For a follow-up turn (not the first one), the prior blog scrolls up into the conversation thread as the new loading state and then new blog render in its place.

### 9.6 Resumed chat behavior

- Tapping a recent chat on Discover opens the chat scrolled to the bottom (latest blog visible, carousel below, sticky composer ready).
- All state preserved: the carousel is exactly as it was, saved items still saved, the conversation thread fully scrollable upward.
- User can immediately type a follow-up and continue.

### 9.7 Save behavior

- Tap bookmark on a carousel card or Product detail → saved (state changes immediately, cookie writes async).
- Saved items appear in Saved screen, ordered by most-recently-saved.
- No "saved!" toast or confirmation — the icon state change is the confirmation. Avoid notification noise.

### 9.8 Compare flow

- From Saved, user enters multi-select mode (tap-and-hold or explicit select toggle).
- User selects exactly two products → Compare button activates.
- Tap Compare → brief loading state while AI generates the comparison verdict → Compare mode screen renders.

---

## 10. Microcopy library

Concrete copy to use across the product. Voice per `tone.md`. This is a starting set — Claude Design and Claude Code can extend it, but should preserve the tone.

### 10.1 Loading states (rotate)

- "Searching the web…"
- "Looking through partner reviews…"
- "Digging for answers…"
- "Seeing what others are saying…"
- "Comparing the contenders…"
- "Reading the room…"
- "Weighing the tradeoffs…"
- "Pulling the receipts…"
- "Sorting the contenders…"
- "Cross-checking the specs…"
- "Hunting for the catch…"
- "Asking around…"

### 10.2 Empty / first-time states

- **Discover, first open**: trending content fills the screen. Heading: *"What are you researching?"* or *"Let's find you something good."*
- **Saved, empty**: *"Nothing saved yet. When you find something worth coming back to, tap the bookmark."*
- **Chat history, empty**: *"Your past conversations will land here. Pick up any of them anytime."*
- **Personality profile, sparse**: *"Still getting to know you. Ask a few things and this fills in."*

### 10.3 Chat starter prompts (rotate on Chat — empty)

- *"What are you trying to figure out?"*
- *"What are you researching?"*
- *"What's on your mind?"*
- *"What are we looking at?"*

### 10.4 Curious follow-up questions (pattern examples — AI generates contextually)

After a headphones blog:
- *"Want me to factor in glasses fit, or are you contact-lens-only when you're wearing these?"*
- *"Want me to narrow this to under $200, or is budget flexible?"*

After a hotel blog:
- *"Should I check prices for a few different dates, or are these locked in?"*
- *"Want me to also pull options in [neighborhood], or are we staying central?"*

After a flight blog:
- *"Open to a one-stop if it shaves $200, or strictly nonstop?"*
- *"Curious if you have airline loyalty anywhere — that could shift the pick."*

After a user pushes back:
- *"Fair — what's pulling you toward [X]? I'll re-weigh."*

After a simple verdict:
- *"Want me to compare this against anything else you've been eyeing?"*

The principle: contextual, specific, curious. Never "Anything else?"

### 10.5 Error / edge cases (out of scope to fully spec, but voice guidance)

- API failure / no results: *"Hit a wall pulling info on this one. Want to try a different angle?"* — never "An error occurred."
- Offline: *"Looks like the connection dropped. Try again when you're back."* — voice-consistent, not alarming.
- Ambiguous query: rare — the AI should default to the quiz path rather than erroring. But if needed: *"Want to tell me a bit more about what you're looking for?"*

### 10.6 Banned phrases

See `tone.md` for the full literal blocklist. Worth reiterating the most important ones for the design team: no "Great choice!", no "You'll love it!", no "Great question!", no "As an AI…", no "It depends," no marketing verbs ("elevate," "unlock," "empower," "experience").

---

## 11. Visual principles & guardrails

> Claude Design owns visual design. These guardrails preserve the product's identity across that handoff.

### 11.1 Overall feel

- **Editorial-modern.** The product is a knowledgeable editor, not a chatbot or a shopping app. Lean toward magazine sensibilities — generous whitespace, considered typography, restrained color.
- **Warm, not cute.** Confidence without quirk. No mascots, no winking icons, no playful illustrations that undercut the editor voice. A subtle warmth in color and type — not stark white-on-black, not aggressively corporate.
- **Conversational density.** Chat screens breathe. The blog response on Results is the densest screen and should still feel readable, not cramped.

### 11.2 Typography

- **The blog response deserves real typographic care.** This is editorial long-form. A serif for body or for headers is worth considering — it signals "this is written, not generated." Whatever the choice, the blog should *read* like an article.
- **UI text** (buttons, labels, chips, navigation) — sans, clean, sized for mobile readability.
- **Hierarchy matters more than ornament.** Strong contrast between the verdict lede, body sections, and the curious follow-up question.

### 11.3 Color

- **Subtle warmth.** Not stark white backgrounds. Slight cream, slight off-white, slight warm gray — something that doesn't feel like a chat interface or a developer tool.
- **Accent color used sparingly.** One or two accents, used for action affordances (save, buy, send) and the inline product hyperlinks in the blog. Not as background washes or gradients.
- **No "AI" purple/blue gradients.** Avoid the visual cliché of AI products. ReviewGuide isn't selling AI — it's selling good purchase advice.

### 11.4 Motion

- **Considered, not eager.** Animations exist to support understanding (loading transitions, carousel snap, blog-to-carousel scroll). Avoid decorative motion.
- **The loading animation is the most important motion in the product.** It establishes the AI's character. Thoughtful, slightly playful, not frantic. Worth real design exploration.
- **Transitions between screens** — calm and quick. The user is in a conversation; transitions should not interrupt the flow.

### 11.5 Density & spacing

- **Generous on conversational screens.** The chat needs room to breathe.
- **Tighter on the blog.** Editorial layout — narrower line lengths for readability, generous line height, clear section breaks.
- **Carousel cards should feel substantial.** Not tiny. Big enough that the product image actually sells the product. The peek of the next card is intentional whitespace, not crowding.

### 11.6 What to avoid

- AI sparkle / star iconography (the universal "this is AI" cliché)
- Source citation UI (we don't have citations)
- Filter chip bars or refinement sidebars (the conversation IS the filter)
- Spec tables on Results (the blog weaves specs into prose; tables live on Compare and Product detail in restrained form)
- Heavy modal overlays
- Notification toasts for non-critical events
- Onboarding tooltips, coach marks, or "did you know?" popovers
- Gamification (no streaks, badges, points)
- Skeleton loaders for the blog response — use the curious loading bubble instead, which is more on-voice

---

## 12. Out of scope / future

Explicitly deferred for this version, to keep the spec focused. These are valid product directions, but not designed here:

- **User authentication.** No sign-in, no accounts. Cookie-anchored persistence only. A soft sign-in gate may be added later at a moment of friction (e.g., "want your saves on another device?"), but is not in this spec.
- **Cross-chat memory.** Personality profile crosses chats; chat content does not. The headphones chat does not know about the LG TVs chat. (May change with explicit user opt-in features later.)
- **Citations.** Removed deliberately (legal + product positioning). May reconsider if licensing deals make sourcing viable later.
- **Recently viewed carousel** on Discover. Considered, declined.
- **Filters and refinement UI.** The conversation handles filtering. No traditional filter chips.
- **Notifications / price alerts.** Out of scope for v1.
- **Paywall / upgrade.** No premium tier in this version.
- **Error and offline states (full spec).** Voice guidance provided in §10.5; full visual design deferred to a follow-up.
- **Settings (beyond personality profile).** Notifications toggle, disclosure, links to terms — minimal, deferred.
- **Desktop / responsive web.** Mobile-first only. Desktop may follow but is out of scope here.
- **Tablet layouts.** Out of scope.
- **Accessibility detailed spec.** Voice and structure should be inherently accessible (semantic structure, real text not images, sufficient contrast). Detailed a11y review (screen reader behavior, focus order, ARIA) deferred but should be considered throughout.
- **Internationalization.** English-only for v1. Voice and tone are written for English; localization is its own project.

---

## 13. Open questions for Claude Design

Things deliberately left open for Claude Design to explore and decide. Make a call, document the reasoning.

1. **The loading animation form.** What does "thoughtful, slightly playful, not frantic" actually look like? Worth real exploration — this is a personality moment.
2. **Visual treatment of the inline product hyperlink in the blog.** Underline? Color? Subtle background? Should feel like editorial writing's hyperlinks, not like a button.
3. **The curious follow-up question's visual treatment.** It's part of the AI's bubble but should be registered as an *invitation*. Slight italic? Own line? Subtle separator? Worth a few iterations.
4. **Suggestion chip styling.** Critical — must look like "tap to reply," not like "select an option from a form." This visual distinction matters more than it sounds.
5. **The blog's typographic system.** Serif or sans for body? How are mini-sections delimited? How does the verdict lede stand apart? This is the heart of the editorial feel.
6. **The Discover screen's overall composition.** Trending should feel inviting, not algorithmic. How do trending products and chats coexist visually without becoming a crowded feed?
7. **Carousel card density.** How much info on a card? Too much = cluttered, too little = users can't differentiate at a glance. Balance to find.
8. **Personality profile screen aesthetic.** Trust work. Should feel calm and transparent, not buried. How is this distinct from a generic settings page?
9. **Save toggle visual.** Must feel satisfying to tap. State change is the confirmation — make it land.
10. **The product's color identity.** Subtle warmth, no AI gradients — but what specifically? Worth exploring 2–3 directions.

---

## 14. Reference summary

- `tone.md` — voice & personality (this spec defers to it on all voice questions)
- This document — design spec
- Source figma — the original ReviewGuide.ai concept frames (reference only; the mobile-first conversational direction in this spec supersedes the desktop layouts)
- Next steps: this spec → Claude Design (visual design with guardrails) → Claude Code (build to spec)
