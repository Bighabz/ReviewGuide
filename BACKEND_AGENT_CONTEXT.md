# Backend Agent Context — ReviewGuide

**Reference this file for every API, data, AI-orchestration, persistence, or backend implementation decision.**
Companions: `tone.md` (voice — yes, backend cares about this), `reviewguide-spec.md` (design spec), `RECONCILIATION.md` (codebase audit), `FRONTEND_AGENT_CONTEXT.md` (the other side of the schema contract).
**`tone.md` and `reviewguide-spec.md` supersede prior direction.** This includes prior system prompts in any tool, planner, clarifier, or composer.

---

## Project overview

ReviewGuide is a mobile-first conversational product that helps people decide what to buy. The backend powers a real two-way dialogue: it judges whether a question is simple or complex, asks clarifying questions when needed, synthesizes a ranked editorial response with a product carousel, and continues to refine via follow-up turns.

The core insight: chatbots blow smoke; a real purchase advisor must rank, commit, and gently redirect. The backend is where the voice and the recommendation logic live.

---

## Voice anchor — backend implications

The voice is **not** only a frontend concern. The backend generates:
- The blog response prose (Results)
- The clarifying questions (quiz path)
- The "AI's take" paragraph on Product detail
- The comparison verdict paragraph on Compare
- The contextual follow-up question at the end of every response
- Loading status text emitted via SSE (if server-driven)
- Error / edge-case messages

Every one of those strings must honor `tone.md`. The banned-phrases blocklist applies to **all** AI outputs.

### Banned phrases — literal blocklist (must never appear in any AI output)

- "Great choice!" / "Excellent pick!" / "You'll love it!" / "You can't go wrong with…" / "You're going to be so happy with…"
- "Great question!" / "What a great question!" / "Happy to help!" / "I'd be glad to…"
- "As an AI…" / "I'm just a language model…"
- "Ultimately the decision is yours." / "It really depends on your needs." / "Everyone's different."
- "Game-changer" / "Best of the best" / "Crushing it"
- "Unlock" / "Elevate" / "Empower" / "Experience the…" / "Take your [X] to the next level"

The *pattern* is also banned — empty enthusiasm, hedging, corporate marketing, AI-disclaimer — even when the literal words differ.

Quick-reference voice rules:
1. Opinionated about fit, not about products.
2. Rank, don't trash. Nothing is "bad" — things are *not the pick for you*.
3. No glazing. Earn agreement when it's earned.
4. **Every response ends with exactly one contextual curious question.** Contextual = references what was just discussed. Banned: "Anything else?", "Want to dig deeper?", or any generic offer.
5. Strong opinions on substance, humility on taste.
6. No source citations — synthesize and speak in our own voice.
7. Loading copy is ambiguous and curious (no provider names).
8. Calibrate register to the user's depth (learned via personality profile).

Centralize the voice rules + blocklist + curious-follow-up rule as a shared `VOICE_PROMPT` constant (e.g., `backend/app/services/prompts/voice.py`) and inject it into **every** system prompt — composer, clarifier, planner, intent, safety, comparison verdict.

---

## Data sources & data model

### Sources

- **SerpAPI** — web-wide product specs and review content. Used for synthesis only; review excerpts are never republished verbatim.
- **Amazon Product Advertising API (PA-API)** — product metadata, review summaries, affiliate link generation. (See `backend/app/services/affiliate/providers/amazon_provider.py`. Note: PA-API v5 retires May 15 2026 per CONCERNS.md — v3 branch has the Creators API migration that hasn't landed in `main` yet.)
- **Curated `amzn.to` short-link bucket** — `backend/app/services/affiliate/providers/curated_amazon_links.py`. Per-category dict of human-verified product listings. Matched by name post-Fix-1 (`5738cd1`), never by index.
- **eBay Browse API** — secondary affiliate source.
- **(Removed from main, lives on v3)** — Skimlinks (48,500 merchant coverage), Serper Shopping. CONCERNS.md High #13. Restoring these is Milestone 2 candidate work.

### Hard rules

- **No scraping** of any site, including Amazon's web property. Only the APIs above.
- **No direct user-facing citations.** No "according to RTINGS", no "Wirecutter says", no source attribution surface. Reasoning chains may use citations internally for grounding; never emit them as user-facing block types. Per `reviewguide-spec.md` §4.2.
- **All affiliate links** are PA-API generated (Amazon) or provider-API generated (eBay). Never scraped, never hand-rolled.
- **Loading copy never names competitor sites** — no "Searching RTINGS…", no "Checking Wirecutter…". Use the ambiguous vocabulary in `tone.md` §"Loading state vocabulary" and `reviewguide-spec.md` §10.1.

### Data model

| Layer | Scope | Storage | Notes |
|---|---|---|---|
| Chat session memory | Within one chat | Server (session-scoped, keyed by `session_id`) | Full memory within session |
| Chat history (list) | All past chats for a device | Cookie + server (existing `ConversationRepository`) | One row per chat session |
| Saved items | Across the device | Cookie-anchored (frontend), optionally server-mirrored | No account — cookie is the identity |
| **Personality profile** | Growing over time | **Postgres table (`personality_profiles`) + Redis cache (cookie_id, 30-min sliding TTL)** | Viewable + editable via `/profile` screen |
| Recently-viewed | — | — | **Not implemented; out of scope** |

### Personality profile backing — Postgres + Redis (LOCKED DECISION)

**Decision:** Postgres table as canonical store, Redis for per-session read caching.

**Reasoning:** Our spec pre-defines all personality dimensions (register, depth, vocabulary, stated priorities, categories explored). Postgres gives us:
- Native schema fit for our known dimensions
- Sub-5ms read latency on the existing Railway DB
- Native CRUD for the `/profile` screen
- Zero migration cost and no additional service dependency

### Load-bearing architecture rules (non-negotiable)

1. **Raw conversation messages are the canonical store. Profile is a derived view — never the primary record.** Decisions, corrections, and evidence tracing all flow from the message history. The profile is a summary of what the message history reveals.

2. **Redis cache pattern — read once per chat session, write-through with invalidation:**
   - On chat session start: read profile by `cookie_id` into Redis (key: `profile:{cookie_id}`, 30-min sliding TTL).
   - On every turn: inject from Redis (no Postgres hit per message).
   - On profile write: write through to Postgres AND invalidate the Redis key immediately.
   - Mid-session profile refresh is **explicitly out** — batch profile observations during the chat, flush to Postgres at session end or idle timeout (e.g., 10-min inactivity). Never re-read Postgres mid-session.

3. **Register-vs-opinions injection boundary (hard rule, unit-testable):**

| Category | Inject into system prompt? | Examples |
|---|---|---|
| Register / depth / vocabulary | ✓ Always inject | "Comfortable with technical specs", "uses 'ANC' freely", "prefers terse answers" |
| Stated priorities (substance) | ✓ Always inject | "Caps budget around $300", "prefers wireless", "reliability over features" |
| Stated opinions on products/brands | ✗ Filter out | "Dislikes Sony", "loves Apple ecosystem", "trusts Bose audio" |
| Gray area: priority disguised as brand opinion | ✓ Inject as priority weight, not brand veto | "Doesn't trust Sony reliability" → captured as "reliability-sensitive, Sony flagged" so ranking stays transparent |

This filter is a function with unit tests — not a prompt convention:

```python
def build_profile_inject_fragment(profile: Profile) -> ProfileInjectFragment:
    """
    Returns only the register/depth/vocab/stated-priorities dimensions.
    Strips any 'stated_opinions' entries (product/brand opinions).
    Gray-area reliability flags are reframed as priority weights.
    """
```

The injection layer takes a `Profile` and produces a `ProfileInjectFragment`. Unit test cases (these are the acceptance criteria for the function):

| Input profile field | Expected inject fragment output |
|---|---|
| `stated_priorities: [{key: "budget_cap", value: 300}]` | ✓ Injected as priority |
| `stated_priorities: [{key: "dislikes_sony", value: true}]` | ✗ Stripped — product opinion |
| `stated_priorities: [{key: "prefers_wireless", value: true}]` | ✓ Injected as priority |
| `stated_priorities: [{key: "loves_apple_ecosystem", value: true}]` | ✗ Stripped — brand opinion |
| `stated_priorities: [{key: "sony_reliability_concern", value: true}]` | ✓ Injected as `"reliability_sensitive: true"`, NO Sony brand reference |
| `register: {depth: "enthusiast", jargon_comfort: 0.9}` | ✓ Always injected |
| `vocabulary: ["ANC", "codec support"]` | ✓ Always injected |

---

## The AI orchestration layer (the heart of the backend)

This is where most of the product lives. The current `main` already has Anthropic SDK installed (`anthropic==0.72.0` per CONCERNS dependency table), a LangGraph 1.0 5-agent pipeline (`backend/app/services/langgraph/workflow.py`), and `model_service.py` (`backend/app/services/model_service.py`). Build on these, don't rewrite.

### Model selection (recommended)

| Use case | Model | Why |
|---|---|---|
| Blog/quiz/comparison long-form responses | **Claude Sonnet 4.6** (`claude-sonnet-4-6`) | Strong editorial voice, ranking discipline, follows tone.md rules reliably. |
| Lightweight tasks (intent detection, slot extraction, loading-copy selection) | **Claude Haiku 4.5** (`claude-haiku-4-5-20251001`) | Cheap, fast. |
| Compression / auxiliary | Sonnet (or Gemini 3.5 Flash via MCP) | Per `CREW-SETUP-LESSONS.md` — set `auxiliary.compression` explicitly so it doesn't default to the main brain. |

Existing model env vars and `model_service.py` mostly handle the routing — extend, don't replace.

### System prompt construction

A single `build_system_prompt(role, context)` helper should compose every system prompt from:

1. **`VOICE_PROMPT`** — the voice rules + banned-phrases blocklist + curious-follow-up rule (the centralized constant).
2. **`ROLE_PROMPT`** — the agent-specific role (composer, clarifier, comparison-verdict, etc.).
3. **`PERSONALITY_PROFILE_INJECT`** — the output of `build_profile_inject_fragment(profile)`. This function runs **before** the system prompt string is assembled and filters out product/brand opinions (see Data Sources section). For new users with no profile, omit this block entirely — never inject empty placeholder text.
4. **`CONVERSATION_HISTORY`** — the session memory (current chat only — no cross-chat content).
5. **`TOOL_OUTPUTS`** — the structured data from SerpAPI / PA-API / curated bucket / review search, formatted for synthesis.

Every system prompt — without exception — includes the VOICE_PROMPT. The existing prompts in `backend/mcp_server/tools/product_compose.py:623` and `:852` predate tone.md and need rewriting against the new rules.

### Conversation state management

- **Session-scoped memory** is already correctly modeled via `session_id` + `ConversationRepository`. Keep.
- **Cross-chat content sharing**: **forbidden**. A "headphones" chat must not know about an "LG TVs" chat (spec §2.4).
- **Personality profile**, however, is read into every chat's system prompt — that's the cross-session layer that grows over time.

### Response-shape decision: fast path vs. quiz path

The Planner / Clarifier agents already pick a plan. Refactor the decision so it explicitly returns one of `{ "shape": "fast" }` or `{ "shape": "quiz", "questions": [...] }` to the client. Decision inputs:
- Category complexity (e.g., "best wired earbuds under $50" → fast; "I need a new laptop" → quiz).
- Prior chat context (if priorities are already stated, can skip quiz).
- User signals — short messages, "just tell me", explicit "skip the questions" → fast path.
- User personality profile — known time-poor pragmatists default toward fast path.

Make the decision testable: a function `decide_response_shape(query, context, profile) → ShapeDecision` with unit tests covering known categories.

### The curious-follow-up enforcement (at prompt level)

The current code asks for 2–3 follow-ups (`product_compose.py:623`) or "exactly 3" (`product_compose.py:852`). **The spec mandates exactly one.** The prompt must say:

> End every response with exactly ONE contextual curious question on its own line, separated from the body. The question must reference something specific that was just discussed — never generic. Examples: *"Want me to factor in glasses fit, or are you contact-lens-only when you're wearing these?"* or *"Should I check prices for a few different dates, or are these locked in?"* Banned: "Anything else?", "Want to dig deeper?", "Is there anything I can help you with?", or any generic offer.

The response schema must structurally separate this question from the blog body (see Output schema below) so the frontend can give it the distinct visual treatment per spec §11.

### Personality profile read/write

- **Read:** at chat session start, load profile by cookie_id from Redis (cache hit) or Postgres (cache miss) → inject as `PERSONALITY_PROFILE_INJECT`. No further Postgres reads during the session.
- **Write:** run a lightweight Haiku observation step after each user turn to **accumulate observations in memory**. Flush the batch to Postgres (and invalidate Redis) at session end or 10-min idle timeout. Never write per-turn to Postgres. **Never** write product/brand opinions.
- **Edit/reset:** CRUD endpoints per spec §7.10. Each write goes to Postgres + invalidates Redis immediately.

### Loading state copy

- **Server-driven recommended** — backend SSE-emits a `loading_status` event with the current copy, rotating as work progresses (e.g., "Seeing what others are saying…" while review search runs → "Cross-checking the specs…" while PA-API runs → "Sorting the contenders…" while compose runs).
- The frontend renders the current `loading_status` value into the loading bubble.
- **Never** emit provider-specific copy ("Querying RTINGS…", "Calling Amazon…"). Use only the ambiguous vocabulary from `tone.md` / `reviewguide-spec.md` §10.1.

---

## The blog generation pipeline (Results payload)

This is the product's centerpiece. The pipeline:

1. **User query + conversation context + personality profile** enter the orchestration layer.
2. **AI orchestrator** decides shape (fast/quiz) and, if fast, gathers data:
   - Search via SerpAPI (review content for synthesis only — never republished verbatim).
   - PA-API call(s) for Amazon product metadata + review summaries.
   - Curated bucket lookup (`find_curated_links` → `_match_curated_entry` by name — the Fix 1 path).
   - eBay Browse API for secondary affiliate coverage.
3. **AI synthesizes** the gathered data into the blog response — editorial long-form, ranking-based, with inline product mentions that map structurally to carousel card IDs. Tone.md voice mandatory.
4. **Carousel cards** are assembled from the same source data — each card carries the AI's positioning label ("Top pick — best all-rounder", "Upgrade pick", "Budget alternative") that maps to the rank in the blog.
5. **Response streams back** to the client progressively. Streaming the blog renderis desirable so it feels alive — `backend/app/api/v1/chat.py`'s SSE generator already supports streaming; verify the new schema streams cleanly (per CONCERNS.md, v3 has a "Streaming Compose" pattern in commits `b30e861`/`4cb253a`/`a4013da` that hasn't landed in `main`). Worth porting once response shape is finalized.

---

## Output schema for the blog response

The frontend needs structured data, not loose markdown. Here's the canonical shape (concretize the exact field names against existing `GraphState` / `ui_blocks`, but this is the contract):

**Blog shape (LOCKED):**

```json
{
  "response_shape": "blog",
  "blog": {
    "verdict_lede": "...",
    "body": [
      {
        "kind": "section",
        "heading": "...",
        "spans": [
          { "kind": "text", "value": "..." },
          { "kind": "product_ref", "product_id": "card_1", "label": "..." }
        ]
      }
    ]
  },
  "carousel": [
    {
      "id": "card_1",
      "rank": 1,
      "ai_label": "Top pick — best all-rounder",
      "product_name": "...",
      "image_url": "...",
      "price": 79.99,
      "currency": "USD",
      "affiliate_link": "...",
      "merchant": "Amazon"
    }
  ],
  "follow_up_question": "..."
}
```

**Quiz shape (LOCKED):**

```json
{
  "response_shape": "quiz",
  "question": { "text": "...", "chips": ["...", "..."] },
  "follow_up_question": null
}
```

**Verdict shape for Compare mode (LOCKED):**

```json
{
  "response_shape": "verdict",
  "comparison": {
    "verdict_paragraph": "...",
    "spec_rows": [
      { "name": "ANC", "a_value": "...", "b_value": "...", "better": "a" }
    ],
    "pick_id": "card_1"
  },
  "follow_up_question": "..."
}
```

**Contract guarantees the backend enforces before emit:**

- Every `spans[*]` of `kind: "product_ref"` MUST have a `product_id` that exists in `carousel[*].id`. Validate before streaming — a dangling `product_id` breaks the inline hyperlink → carousel snap behavior (spec §9.3).
- `follow_up_question` is structurally separate from `blog` so the frontend renders it with distinct visual treatment (spec §11 / §13 #3). Never `null` on blog or verdict shapes.
- `follow_up_question` is always `null` on the quiz shape — the AI bubble ends with the question itself.
- Carousel is pre-ranked; `rank: 1` is the top pick. `ai_label` drives both the card label and the `/results/[id]` AI positioning label (spec §7.6).
- The quiz shape carries `question` (singular) — each quiz turn emits ONE question bubble. The "one follow-up per response" rule applies to all shapes.

**Note on IDs:** Use short IDs (`"card_1"`, `"card_2"`, ...) — not `"carousel-card-1"`. The `product_ref.product_id` and `carousel[*].id` must use the same ID scheme.

---

## The personality profile system

### Schema (proposed)

```jsonc
{
  "profile_id": "...",                       // cookie-anchored
  "created_at": "...",
  "updated_at": "...",

  "register": {                              // how the user likes to be talked to
    "depth": "novice" | "enthusiast" | "pragmatist",
    "jargon_comfort": 0.0–1.0,               // 0 = define jargon, 1 = use shorthand freely
    "preferred_length": "short" | "default" | "long"
  },

  "vocabulary": ["ANC", "codec support", "..."],   // jargon the user has demonstrated comfort with

  "stated_priorities": [
    { "key": "budget_cap", "value": 300, "evidence_session_id": "..." },
    { "key": "form_factor", "value": "wireless", "evidence_session_id": "..." },
    { "key": "reliability_over_features", "value": true, "evidence_session_id": "..." }
  ],

  "categories_explored": ["headphones", "hotels", "laptops"]
}
```

### What gets stored
- Register (depth/jargon/length)
- Vocabulary the user has used
- Recurring stated priorities
- Categories explored

### What does NOT get stored
- **Opinions on products.** The AI does not learn to agree with the user. If the user loves a brand the AI ranks lower, the AI keeps ranking it lower and explains why. The profile makes the *explanation* more efficient — it does not soften the verdict. (Per tone.md.)
- **Affirmation thresholds.** The AI doesn't get nicer to returning users.

### Storage: Postgres table

```sql
CREATE TABLE personality_profiles (
  profile_id          TEXT PRIMARY KEY,   -- cookie_id (device-scoped, no auth)
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  reset_at            TIMESTAMPTZ,        -- nullable; set when user resets profile (≠ delete-and-recreate)
  register            JSONB,              -- {depth, jargon_comfort, preferred_length}
  vocabulary          TEXT[],             -- jargon the user has demonstrated comfort with
  stated_priorities   JSONB,             -- [{key, value, evidence_session_id}] — NO product opinions
  categories_explored TEXT[]
);
```

This is the canonical store. Chat message rows are the evidence base; this table is the derived summary.

### Read path: Redis cache (per session)

Key format: `profile:{cookie_id}` — TTL: 30-min sliding (reset on each read that hits cache).

1. Chat session starts → look up `profile:{cookie_id}` in Redis.
2. Cache hit → inject directly into system prompt as `PERSONALITY_PROFILE_INJECT`.
3. Cache miss → read from Postgres, write to Redis (30-min TTL), then inject.
4. Mid-session: always read from Redis. No Postgres reads per message.
5. **Redis-down degradation:** catch connection errors, fall back to reading directly from Postgres, log the degradation event. The system must not fail hard on Redis unavailability — profile injection is important but never a hard dependency.

### Write path: write-through with invalidation

- Profile write (post-session flush or user edit) → write to Postgres + delete `profile:{cookie_id}` from Redis.
- Next session start will re-populate Redis from Postgres.
- Profile observations during an active chat session are **batched in memory**, not written per turn. Flush at: session end, 10-min idle timeout, or explicit user edit.

### Inject into system prompt

The `build_profile_inject_fragment(profile)` function (see the register-vs-opinions table in the Data Sources section above) produces the injection fragment. Example output:

> The user is an enthusiast — comfortable with technical specs. Keep it short, use shorthand, don't define jargon. Recurring priorities: budget cap around $300, prefers wireless, prioritizes reliability over feature set. Categories they've explored: headphones, hotels, laptops.

For new users with no profile: omit the `PERSONALITY_PROFILE_INJECT` block entirely (don't inject empty/placeholder text).

### User-facing editability (per spec §5.3 + §7.10)

Endpoints needed:
- `GET /v1/profile` — returns the current profile for the cookie.
- `PATCH /v1/profile` — accepts edits to register, stated priorities (add/remove/update). Writes through to Postgres, invalidates Redis.
- `POST /v1/profile/reset` — clears `personality_profiles` row for the cookie only. Preserves chat history and saved items. Invalidates Redis.

### Reset behavior

Per spec §7.10 — reset clears only the `personality_profiles` row. Chat message history and saved items are untouched.

---

## Things that are explicitly out of scope — do NOT build

Per `reviewguide-spec.md` §12. Anything that lands here is a non-goal:

- **No user authentication.** No sign-in, no accounts, no OAuth, no email collection for the shopping flow. Cookie-anchored persistence only. (Admin auth for ops stays — that's a separate concern.)
- **No cross-chat content memory.** Chat sessions are content-isolated; only the personality profile crosses.
- **No citation surface.** No source attribution in user-facing responses. Internal-only.
- **No price alerts / notifications.** No push, no email, no in-app toasts for non-critical events.
- **No paywall / premium tier.**
- **No filters / refinement APIs.** The conversation handles filtering. Do not build a `/v1/products/filter` endpoint or any filter-chip backend. (Spec §11.6.)
- **No recently-viewed tracking.**
- **No internationalization.** English-only for v1.
- **No tablet / desktop-specific layouts** as separate codepaths — the same API serves mobile-first frontend.

Do not add code paths, fields, or endpoints for any of the above.

---

## Reconciliation with existing code

Per `RECONCILIATION.md`. Backend-specific call-outs:

### ⚠ Needs change
- **`backend/mcp_server/tools/product_compose.py:623,852`** — system prompts require: (a) tone.md voice injected, (b) follow-up count reduced from 2–3 / "exactly 3" → **exactly one** contextual question, (c) structural separation of the question from the body in the response shape.
- **`backend/app/api/v1/chat.py`** — stop emitting citation SSE events to the client (keep internal reasoning if useful). Audit `tool_citations` / `evidence_citations` / `citations` emission paths.
- **`backend/app/schemas/graph_state.py`** — keep the citation reducers for internal grounding, but do not include them in client-facing payloads.
- **All composer/agent prompts** (`backend/app/agents/*.py`, `backend/mcp_server/tools/*.py`) — inject the centralized `VOICE_PROMPT`.
- **Loading status emission** — replace tool-specific `citation_message` strings with rotation over the ambiguous-curious set (no provider names).

### ✗ Missing
- **Personality profile data layer** (Postgres `personality_profiles` table, Redis per-session cache, `build_profile_inject_fragment()` filter, batch observation flush, CRUD endpoints) — entirely missing.
- **`build_system_prompt(role, context)`** helper that composes VOICE_PROMPT + ROLE_PROMPT + PROFILE_INJECT + HISTORY + TOOL_OUTPUTS.
- **`decide_response_shape(query, context, profile)`** as a testable function (currently buried inside Planner / Clarifier).
- **Comparison verdict endpoint** — `POST /v1/compare` that takes two product IDs (from Saved on the client) and returns the §7.9 verdict paragraph + spec rows in voice.
- **Structured `product_ref` markers** in the blog response schema — enables the inline hyperlink → carousel snap (spec §9.3).
- **Per-product editorial paragraph** generation for Product detail (§7.6).

### — Out of scope (don't build / remove if present)
- `frontend/components/SourceCitations.tsx` (frontend), client-facing citation events (backend) — remove.
- Filter / refinement API — do not build.
- Notifications / price alerts — do not build.
- Recently-viewed tracking — do not build.
- Consumer-facing user authentication — do not build.

---

## Done criteria

- [ ] **Every AI-generated string** passes the `tone.md` voice check. No banned phrases in *any* model output across composer / clarifier / planner / safety / comparison / per-product editorial.
- [ ] **The fast-path / quiz-path decision** is implemented as a testable function with unit tests covering canonical examples (simple utility queries → fast; "I need a new laptop" / aspirational hotels → quiz).
- [ ] **Every AI response ends with exactly one contextual follow-up question** on its own line, structurally separated from the body in the response schema. Banned: "Anything else?" / "Want to dig deeper?" / any generic offer.
- [ ] **Personality profile system** exists: Postgres `personality_profiles` table, Redis per-session cache (30-min TTL, write-through invalidation), `build_profile_inject_fragment()` with register-vs-opinions filter, batch observation flush at session end, CRUD endpoints (`GET/PATCH /v1/profile`, `POST /v1/profile/reset`) exposed for the frontend Profile screen.
- [ ] **The personality profile shapes register and depth** in observable ways across sessions (vocabulary, length, explanation density) but **never shifts opinions** on products. The `build_profile_inject_fragment()` filter function has unit tests verifying product/brand opinions are stripped and gray-area reliability signals are reframed as priority weights.
- [ ] **The blog response schema** carries `product_ref` markers in body spans that resolve to carousel card IDs (enables the inline hyperlink → carousel snap behavior).
- [ ] **Loading status copy** is ambiguous and curious; rotates as work progresses; **never** names a competitor site or specific provider.
- [ ] **All affiliate links** are PA-API-generated or provider-API-generated. **No scraping.**
- [ ] **No client-facing citation surface.** `SourceCitations` removed; SSE no longer emits citation events to the client. Internal reasoning may still use citations for grounding.
- [ ] **No out-of-scope endpoints** exist (no filter API, no notifications API, no recently-viewed API, no consumer-auth API).
- [ ] **Curated `amzn.to` matching is name-based** (Fix 1 verified live; do not regress to positional-zip).
- [ ] **Streaming the blog response** — verify the response can be streamed progressively to the client so the editorial response feels alive (consider porting the v3 "Streaming Compose" work once response shape is finalized).
- [ ] **Reconciliation ⚠ + ✗ items addressed or explicitly deferred with reasoning.**

*End of BACKEND_AGENT_CONTEXT.md*
