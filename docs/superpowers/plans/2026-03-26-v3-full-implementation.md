# ReviewGuide.ai v3 Full Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all critical bugs (streaming, bubble wrapping, markdown, duplicate cards), overhaul the theme/color system for a rich dark-mode-first experience, redesign the homepage as a visual product catalog, and add performance polish across the entire frontend.

**Architecture:** Eight phases executed sequentially by dependency. Phase 1 (bugs) unblocks everything. Phase 2 (streaming) is the highest-impact backend change. Phases 3-5 (cards, theme, homepage) are frontend-only. Phases 6-8 (images, micro-UX, performance) are polish. Each phase produces independently shippable commits.

**Tech Stack:** Next.js 14, React 18, TypeScript, Tailwind CSS, FastAPI (Python), LangGraph, SSE streaming, CSS custom properties.

**Spec:** `docs/superpowers/specs/2026-03-26-v3-full-implementation-spec.md`

---

## File Map

### Phase 1 — Bug Fixes
| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `frontend/components/Message.tsx:152` | Widen user message bubble max-width |
| Modify | `frontend/components/ProductCards.tsx:111-114` | Strip markdown from product snippets |
| Modify | `frontend/components/InlineProductCard.tsx:111-117` | Strip markdown from descriptions |
| Modify | `frontend/components/TopPickBlock.tsx:60-63` | Strip markdown from headline |
| Create | `frontend/lib/stripMarkdown.ts` | Utility to strip markdown syntax from plain text |
| Modify | `frontend/components/AffiliateLinks.tsx:52-53` | Fix truncated product names |
| Modify | `frontend/components/ConversationSidebar.tsx:46-51` | Fix history panel session tracking |

### Phase 2 — Streaming
| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/mcp_server/tools/product_compose.py:734-770` | Stream blog_article tokens via callback |
| Modify | `backend/mcp_server/tools/product_compose.py:502-510,621-629` | Remove redundant opener/conclusion LLM calls |
| Modify | `backend/app/api/v1/chat.py:441-483` | Yield content tokens mid-workflow from stream_chunk_data |
| Modify | `backend/app/api/v1/chat.py:612-622` | Remove post-workflow text chunking fallback |
| Modify | `frontend/components/ChatContainer.tsx:432-446` | Add streaming cursor + stop button |
| Modify | `frontend/components/Message.tsx:184-191` | Replace "Thinking..." with pulsing dots after 1s |

### Phase 3 — Product Cards
| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `frontend/components/TopPickBlock.tsx` | Add price, rating, buy button, expandable pros/cons |
| Modify | `frontend/components/blocks/BlockRegistry.tsx:35-43` | Pass price/rating/pros/cons to TopPickBlock |
| Modify | `frontend/components/AffiliateLinks.tsx` | Standardize buy cards with "Best Price" badge |
| Modify | `frontend/components/ProductCards.tsx` | Add buy button, consistent price display |

### Phase 4 — Theme & Color Overhaul
| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `frontend/app/globals.css:102-158` | New dark mode palette (#0C0E14 base) |
| Modify | `frontend/app/globals.css:5-100` | Refine light mode (#F7F5F0 base) |
| Modify | `frontend/app/globals.css:160-191` | Expand accent themes to affect full mood |
| Modify | `frontend/components/UnifiedTopbar.tsx:9-15,89-98` | Themed accent names, broader CSS var impact |
| Modify | `frontend/app/globals.css:357-364` | Enhanced hover effects: glow, lift, transitions |
| Modify | `frontend/components/CategorySidebar.tsx:129-131` | Richer hover states |
| Modify | `frontend/components/discover/TrendingCards.tsx:47-58` | Richer hover with arrow slide |
| Modify | `frontend/components/AffiliateLinks.tsx:49` | Glow hover on buy links |

### Phase 5 — Homepage Redesign
| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `frontend/app/page.tsx` | Add sidebar, remove chips, add catalog rows |
| Create | `frontend/components/discover/CatalogRow.tsx` | Netflix-style horizontal scrollable product row |
| Create | `frontend/components/discover/CatalogProductCard.tsx` | Product card for catalog grid (image, name, rating, price) |
| Modify | `frontend/components/discover/TrendingCards.tsx` | Add hero images to trending cards |
| Modify | `frontend/components/Footer.tsx` | Compact single-line or useful footer |
| Modify | `frontend/components/discover/DiscoverSearchBar.tsx` | Convert to sticky bottom bar |

### Phase 6 — Product Images
| Action | File | Responsibility |
|--------|------|----------------|
| Create | `frontend/lib/productImages.ts` | Image fallback chain: API -> Serper -> placeholder |
| Modify | `frontend/components/InlineProductCard.tsx:48-71` | Use image fallback chain |
| Modify | `frontend/components/ProductCards.tsx:64-76` | Use image fallback chain with category icons |
| Modify | `frontend/components/TopPickBlock.tsx:34-42` | Larger image (140x140), fallback |

### Phase 7 — Micro-UX
| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `frontend/components/ChatInput.tsx:48-76` | Focus glow, placeholder icons, send animation |
| Create | `frontend/app/saved/page.tsx` | Placeholder saved page with empty state |
| Create | `frontend/app/compare/page.tsx` | Placeholder compare page with empty state |
| Modify | `frontend/components/Footer.tsx` | Add category links, top searches |
| Modify | `frontend/components/MobileTabBar.tsx` | Prominent "Ask" button, active indicators |

### Phase 8 — Performance & Polish
| Action | File | Responsibility |
|--------|------|----------------|
| Create | `frontend/components/ui/Skeleton.tsx` | Reusable shimmer skeleton component |
| Modify | `frontend/app/globals.css` | prefers-reduced-motion, smooth scroll, click feedback |
| Modify | `frontend/components/discover/CatalogRow.tsx` | Lazy-load images, preload first 5 |

---

## Task 1: Strip Markdown Utility

**Files:**
- Create: `frontend/lib/stripMarkdown.ts`

- [ ] **Step 1: Create the stripMarkdown utility**

```typescript
// frontend/lib/stripMarkdown.ts

/**
 * Strip markdown syntax from text intended for plain-text display.
 * Removes headers (#), bold (**), italic (*_), links, images, code blocks.
 */
export function stripMarkdown(text: string): string {
  if (!text) return ''
  return text
    // Remove headers: "# Title" -> "Title"
    .replace(/^#{1,6}\s+/gm, '')
    // Remove bold: **text** or __text__ -> text
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/__(.+?)__/g, '$1')
    // Remove italic: *text* or _text_ -> text
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/_(.+?)_/g, '$1')
    // Remove inline code: `code` -> code
    .replace(/`(.+?)`/g, '$1')
    // Remove links: [text](url) -> text
    .replace(/\[(.+?)\]\(.+?\)/g, '$1')
    // Remove images: ![alt](url) -> alt
    .replace(/!\[(.+?)\]\(.+?\)/g, '$1')
    // Remove blockquotes: > text -> text
    .replace(/^>\s+/gm, '')
    // Remove horizontal rules
    .replace(/^---+$/gm, '')
    // Collapse multiple newlines
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/stripMarkdown.ts
git commit -m "feat: add stripMarkdown utility for plain-text product card rendering"
```

---

## Task 2: Fix User Message Bubble Two-Line Wrapping

**Files:**
- Modify: `frontend/components/Message.tsx:152`

The user message bubble at line 152 has `max-w-[80%]` inside a 780px container, giving 624px max. Short queries like "Best wireless earbuds under $100" (40 chars at ~8px/char = 320px) should fit on one line but wrap due to padding + border-radius eating space. Widen to `max-w-[85%]` (663px) and set `min-width: fit-content` so short messages don't wrap.

- [ ] **Step 1: Widen the user message bubble**

In `frontend/components/Message.tsx`, find line 152:

```tsx
// OLD (line 152):
<div className="px-4 py-3 rounded-tl-[20px] rounded-tr-[20px] rounded-br-[4px] rounded-bl-[20px] bg-[var(--primary)] text-white shadow-card max-w-[80%]">
```

Replace with:

```tsx
// NEW:
<div className="px-4 py-3 rounded-tl-[20px] rounded-tr-[20px] rounded-br-[4px] rounded-bl-[20px] bg-[var(--primary)] text-white shadow-card max-w-[85%]" style={{ minWidth: 'fit-content' }}>
```

- [ ] **Step 2: Verify visually**

Run: `cd frontend && npm run dev`

Test with these queries in the chat input or click a trending topic:
- "Best wireless earbuds under $100" — should be ONE line
- "Best noise-cancelling headphones 2026" — should be ONE line
- "Top all-inclusive resorts in the Caribbean" — should be ONE line

- [ ] **Step 3: Commit**

```bash
git add frontend/components/Message.tsx
git commit -m "fix: widen user message bubble to prevent unnecessary two-line wrapping"
```

---

## Task 3: Fix Raw Markdown Leaking in Product Cards

**Files:**
- Modify: `frontend/components/ProductCards.tsx:111-114`
- Modify: `frontend/components/InlineProductCard.tsx:111-117`
- Modify: `frontend/components/TopPickBlock.tsx:60-63`

Product descriptions show literal `# Bose Noise Cancelling Headphones 700` because these components render text directly without parsing markdown. Since these are short text fields (not rich content), strip markdown rather than render it.

- [ ] **Step 1: Fix ProductCards.tsx snippet rendering**

In `frontend/components/ProductCards.tsx`, add import at top:

```typescript
import { stripMarkdown } from '@/lib/stripMarkdown'
```

Find lines 111-114:

```tsx
// OLD:
{product.snippet && (
  <p className="text-sm text-[var(--text-secondary)] leading-relaxed mt-3 mb-4">
    {product.snippet}
  </p>
)}
```

Replace with:

```tsx
// NEW:
{product.snippet && (
  <p className="text-sm text-[var(--text-secondary)] leading-relaxed mt-3 mb-4">
    {stripMarkdown(product.snippet)}
  </p>
)}
```

- [ ] **Step 2: Fix InlineProductCard.tsx description rendering**

In `frontend/components/InlineProductCard.tsx`, add import at top:

```typescript
import { stripMarkdown } from '@/lib/stripMarkdown'
```

Find lines 111-117:

```tsx
// OLD:
{product.description && (
  <p
    className="text-xs truncate mt-0.5"
    style={{ color: 'var(--text-secondary)' }}
  >
    {product.description}
  </p>
)}
```

Replace with:

```tsx
// NEW:
{product.description && (
  <p
    className="text-xs truncate mt-0.5"
    style={{ color: 'var(--text-secondary)' }}
  >
    {stripMarkdown(product.description)}
  </p>
)}
```

- [ ] **Step 3: Fix TopPickBlock.tsx headline rendering**

In `frontend/components/TopPickBlock.tsx`, add import at top:

```typescript
import { stripMarkdown } from '@/lib/stripMarkdown'
```

Find lines 60-63:

```tsx
// OLD:
{headline && (
  <p className="text-sm text-[var(--text)] leading-relaxed mb-3">
    {headline}
  </p>
)}
```

Replace with:

```tsx
// NEW:
{headline && (
  <p className="text-sm text-[var(--text)] leading-relaxed mb-3">
    {stripMarkdown(headline)}
  </p>
)}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/components/ProductCards.tsx frontend/components/InlineProductCard.tsx frontend/components/TopPickBlock.tsx
git commit -m "fix: strip markdown from product card text fields to prevent raw # leaking"
```

---

## Task 4: Fix Truncated Product Names in Buy Cards

**Files:**
- Modify: `frontend/components/AffiliateLinks.tsx:51-54`

The merchant name + product title in buy cards gets truncated because the merchant label is inside a `min-w-0` flex container. Fix: show only the merchant name (the product name is already in the parent card header).

- [ ] **Step 1: Simplify affiliate link merchant display**

In `frontend/components/AffiliateLinks.tsx`, find lines 51-54:

```tsx
// OLD:
<div className="flex items-center gap-3 min-w-0">
  <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] shrink-0">
    {link.merchant}
  </span>
```

No change needed to the merchant display itself — the truncation is the browser cutting off text. The issue is that the merchant name is `shrink-0` but the surrounding div has `min-w-0`. The real fix: remove seller ratings that appear inconsistently, and ensure the merchant name doesn't get squeezed.

Replace lines 43-76 (the entire map body):

```tsx
{affiliateLinks.map((link, idx) => {
  const isLowest = idx === 0 // First link is sorted as best price by backend
  return (
    <a
      key={idx}
      href={link.affiliate_link}
      target="_blank"
      rel="noopener noreferrer"
      className={`flex items-center justify-between p-3 rounded-lg border transition-all group/link ${
        isLowest
          ? 'border-green-500/30 bg-green-500/5 hover:bg-green-500/10'
          : 'border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] hover:border-[var(--primary)]/30'
      }`}
    >
      <div className="flex items-center gap-2">
        {isLowest && (
          <span className="text-[10px] font-bold uppercase tracking-wider text-green-600 bg-green-100 px-1.5 py-0.5 rounded dark:text-green-400 dark:bg-green-900/30">
            Best Price
          </span>
        )}
        <span className="text-sm font-semibold text-[var(--text)]">
          {link.merchant}
        </span>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <span className={`text-base font-bold font-serif ${isLowest ? 'text-green-600 dark:text-green-400' : 'text-[var(--text)]'}`}>
          {link.currency} {link.price.toFixed(2)}
        </span>
        <span className="text-xs font-medium text-[var(--primary)] group-hover/link:text-[var(--primary-hover)] flex items-center gap-1">
          Buy &rarr;
        </span>
      </div>
    </a>
  )
})}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/AffiliateLinks.tsx
git commit -m "fix: simplify buy cards — show merchant + Best Price badge, remove inconsistent ratings"
```

---

## Task 5: Fix Conversation History Panel

**Files:**
- Modify: `frontend/components/ConversationSidebar.tsx:46-51`

The history panel shows "0 conversations" because it reads `chat_all_session_ids` from localStorage but nothing writes to it during normal chat. The ChatContainer creates `session_id` but doesn't persist it to the tracking key.

- [ ] **Step 1: Track session IDs in ChatContainer**

In `frontend/components/ChatContainer.tsx`, find the `onComplete` handler that processes the `done` event (around line 457-498). After the line that sets `session_id`:

Find the block around line 457 (`onComplete: (data) => {`). After line 458 (`if (data.user_id && data.user_id !== userId) {`), look for where `data.session_id` is available. In the `done` event handler (around line 499), add session tracking.

Find in ChatContainer.tsx the `onComplete` callback where `data.session_id` is handled. Add after `session_id` is received:

```typescript
// Track session for history sidebar
if (data.session_id) {
  try {
    const stored = JSON.parse(localStorage.getItem('chat_all_session_ids') || '[]')
    if (!stored.includes(data.session_id)) {
      stored.unshift(data.session_id)
      // Keep last 50 sessions
      localStorage.setItem('chat_all_session_ids', JSON.stringify(stored.slice(0, 50)))
    }
  } catch { /* ignore localStorage errors */ }
}
```

Search ChatContainer.tsx for `session_id` assignments to find the exact location. The `done` SSE event delivers `data.session_id` — the tracking code goes wherever that value is first consumed.

- [ ] **Step 2: Commit**

```bash
git add frontend/components/ChatContainer.tsx
git commit -m "fix: persist session IDs to localStorage for conversation history sidebar"
```

---

## Task 6: Backend Streaming — Remove Redundant LLM Calls

**Files:**
- Modify: `backend/mcp_server/tools/product_compose.py`

The spec says product_compose makes 6+ LLM calls totaling ~24s. The fix: remove `product_opener` and `product_conclusion` LLM calls (their output is redundant with `blog_article`), and cap `review_consensus` to top 3 products.

- [ ] **Step 1: Remove opener LLM call**

In `backend/mcp_server/tools/product_compose.py`, find the section that queues the `opener` LLM task (around lines 565-573 based on research). This generates a "warm intro" that duplicates blog_article's opening paragraph.

Find the line like:
```python
llm_tasks['opener'] = ...
```

Comment it out or remove it. Instead, set `assistant_text` directly from the concierge result (which is already queued as a shorter 2-3 sentence summary):

```python
# REMOVED: opener LLM call — blog_article already generates an intro
# The concierge summary (2-3 sentences) serves as assistant_text
```

- [ ] **Step 2: Remove conclusion LLM call**

Find the section that queues the `conclusion` LLM task (around lines 621-629). This generates a 2-sentence conclusion that duplicates blog_article's closing.

Remove or comment out:
```python
# REMOVED: conclusion LLM call — blog_article already has a conclusion
```

Update the assembly section that reads `results['conclusion']` to skip it:

Find where `conclusion_text` is used in the response assembly (after the gather). Remove any references to `results.get('conclusion')` from `ui_blocks` or `assistant_text` construction.

- [ ] **Step 3: Cap review_consensus to 3 products**

Find the loop that creates `review_consensus` LLM tasks (around lines 532-546). It creates one task per product with review data. Add a cap:

```python
# Cap review_consensus to top 3 products by quality score
consensus_products = sorted(
    [p for p in products_with_reviews],
    key=lambda p: p.get('quality_score', 0),
    reverse=True
)[:3]
```

Use `consensus_products` instead of the full list when creating consensus tasks.

- [ ] **Step 4: Commit**

```bash
git add backend/mcp_server/tools/product_compose.py
git commit -m "perf: remove opener/conclusion LLM calls, cap review_consensus to 3 — cuts compose from 6+ to 3-4 calls"
```

---

## Task 7: Backend Streaming — Stream blog_article Tokens via SSE

**Files:**
- Modify: `backend/mcp_server/tools/product_compose.py` (blog_article section)
- Modify: `backend/app/api/v1/chat.py:441-483` (event processing)

Currently, blog_article generates the full text synchronously, then the entire response is chunked post-workflow. Instead: stream blog_article tokens into `stream_chunk_data` as they generate, and have chat.py yield them as `content` SSE events mid-workflow.

- [ ] **Step 1: Add streaming callback to blog_article LLM call**

In `product_compose.py`, find the blog_article LLM task creation (around lines 734-770). Currently it calls something like `model_service.generate()` and awaits the full result.

Modify to use streaming. The pattern depends on the model_service API, but the goal is:

```python
# Instead of: result = await model_service.generate(prompt, ...)
# Use: stream tokens through state['stream_chunk_data']

async def stream_blog_article(state, prompt, model_service):
    """Stream blog_article tokens into GraphState for real-time SSE."""
    full_text = []
    async for chunk in model_service.generate_stream(prompt, max_tokens=500):
        token = chunk.content if hasattr(chunk, 'content') else str(chunk)
        full_text.append(token)
        # Push each token into stream_chunk_data for SSE emission
        state['stream_chunk_data'] = {
            'type': 'content_token',
            'token': token,
        }
    return ''.join(full_text)
```

If `model_service` doesn't have a `generate_stream` method, use the underlying OpenAI/Anthropic client directly with `stream=True`.

- [ ] **Step 2: Handle content_token in chat.py event loop**

In `backend/app/api/v1/chat.py`, find the event processing section (lines 441-483) where `on_chain_end` events check for `stream_chunk_data`.

Add handling for the new `content_token` type (around line 461, after checking `stream_chunk_data`):

```python
# Inside the on_chain_end handler, after getting stream_chunk_data:
chunk_data = output.get("stream_chunk_data")
if chunk_data:
    chunk_type = chunk_data.get("type", "")
    if chunk_type == "content_token":
        # Stream text token directly to frontend
        token = chunk_data.get("token", "")
        if token:
            data_already_streamed = True
            yield _sse_event("content", {"token": token})
    elif chunk_type == "tool_citation":
        # existing citation handling...
```

- [ ] **Step 3: Skip post-workflow text chunking when already streamed**

In `chat.py`, the post-workflow chunking at lines 615-620 already checks `data_already_streamed`. Verify that when `data_already_streamed` is `True`, the `should_stream_text` flag at line 613 evaluates to `False` (it checks `not data_already_streamed`). This is already correct — no change needed.

- [ ] **Step 4: Commit**

```bash
git add backend/mcp_server/tools/product_compose.py backend/app/api/v1/chat.py
git commit -m "feat: stream blog_article tokens via SSE in real-time — first tokens visible in <2s"
```

---

## Task 8: Frontend Streaming — Pulsing Dots + Stop Button

**Files:**
- Modify: `frontend/components/Message.tsx:184-191`
- Modify: `frontend/components/ChatContainer.tsx`
- Modify: `frontend/app/globals.css`

Replace the static "Thinking..." text with a pulsing 3-dot animation. Add a "Stop generating" button during streaming.

- [ ] **Step 1: Replace "Thinking..." with pulsing dots**

In `frontend/components/Message.tsx`, find lines 184-191:

```tsx
// OLD:
{!message.content && message.isThinking && (
  <div className="flex items-center gap-2 py-1.5">
    <span className="w-1.5 h-1.5 rounded-full bg-[var(--primary)] animate-pulse" />
    <span className="stream-status-text tracking-tight">
      {message.statusText || 'Thinking...'}
    </span>
  </div>
)}
```

Replace with:

```tsx
// NEW:
{!message.content && message.isThinking && (
  <div className="flex items-center gap-2 py-1.5">
    <div className="flex items-center gap-1">
      <span className="w-1.5 h-1.5 rounded-full bg-[var(--primary)] animate-bounce-dot" style={{ animationDelay: '0ms' }} />
      <span className="w-1.5 h-1.5 rounded-full bg-[var(--primary)] animate-bounce-dot" style={{ animationDelay: '150ms' }} />
      <span className="w-1.5 h-1.5 rounded-full bg-[var(--primary)] animate-bounce-dot" style={{ animationDelay: '300ms' }} />
    </div>
    {message.statusText && message.statusText !== 'Thinking...' && (
      <span className="stream-status-text tracking-tight">
        {message.statusText}
      </span>
    )}
  </div>
)}
```

- [ ] **Step 2: Add bounce-dot animation to globals.css**

In `frontend/app/globals.css`, add after the existing `@keyframes pulse-subtle` block (around line 306):

```css
@keyframes bounce-dot {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.4;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.animate-bounce-dot {
  animation: bounce-dot 1.4s ease-in-out infinite;
}
```

- [ ] **Step 3: Add streaming cursor to content**

In `frontend/components/Message.tsx`, find the content rendering section (line 194-207). After the `<ReactMarkdown>` block, add a blinking cursor that shows only during streaming:

Find line 205:

```tsx
// OLD:
<ReactMarkdown>{message.content}</ReactMarkdown>
```

Replace with:

```tsx
// NEW:
<ReactMarkdown>{message.content}</ReactMarkdown>
{message.isThinking && message.content && (
  <span className="inline-block w-0.5 h-4 bg-[var(--primary)] animate-pulse ml-0.5 align-text-bottom" />
)}
```

- [ ] **Step 4: Add "Stop generating" button in ChatContainer**

In `frontend/components/ChatContainer.tsx`, find the chat input wrapper (around line 861-868). Before the `ChatInput` component, add a stop button that shows during streaming.

The `isStreaming` state already exists in ChatContainer. Add before the `<ChatInput>` component inside the sticky input wrapper:

```tsx
{isStreaming && (
  <div className="flex justify-center mb-2">
    <button
      onClick={handleStopStreaming}
      className="px-4 py-1.5 rounded-full text-xs font-medium border border-[var(--border)] bg-[var(--surface)] text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-[var(--surface-hover)] transition-all"
    >
      Stop generating
    </button>
  </div>
)}
```

The `handleStopStreaming` function needs to abort the ongoing fetch. Find the existing `abortControllerRef` (it should exist for the SSE connection) and call `abortControllerRef.current?.abort()`.

If no abort controller exists, add one:

```typescript
const abortControllerRef = useRef<AbortController | null>(null)

const handleStopStreaming = () => {
  abortControllerRef.current?.abort()
  setIsStreaming(false)
}
```

Pass `abortControllerRef.current?.signal` to the `streamChat` call in `chatApi.ts`.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/Message.tsx frontend/components/ChatContainer.tsx frontend/app/globals.css
git commit -m "feat: pulsing dot indicator, streaming cursor, and stop-generating button"
```

---

## Task 9: Dark Mode Overhaul — Rich Blue-Black Palette

**Files:**
- Modify: `frontend/app/globals.css:102-158`

Replace the warm charcoal dark mode (#1A1816) with a rich blue-black (#0C0E14) that has depth and layering per the spec.

- [ ] **Step 1: Update dark mode CSS variables**

In `frontend/app/globals.css`, replace the entire `[data-theme="dark"]` block (lines 102-158) with:

```css
[data-theme="dark"] {
  /* ═══════════════════════════════════════════
     V3 DARK MODE — Rich Blue-Black
     Deep, immersive, with blue undertone
     ═══════════════════════════════════════════ */

  /* Primary: Electric Blue */
  --primary: #3B82F6;
  --primary-hover: #60A5FA;
  --primary-light: rgba(59, 130, 246, 0.12);

  /* Accent: Warm Amber */
  --accent: #F59E0B;
  --accent-hover: #FBBF24;
  --accent-light: rgba(245, 158, 11, 0.12);
  --success: #22C55E;
  --success-light: rgba(34, 197, 94, 0.12);

  /* Backgrounds: Rich Blue-Black with depth */
  --background: #0C0E14;
  --surface: #151822;
  --surface-hover: #1C2030;
  --surface-elevated: #1A1E2E;
  --surface-float: rgba(12, 14, 20, 0.95);

  /* Text: Cool White */
  --text: #E8EAED;
  --text-secondary: #8892A4;
  --text-muted: #5A6478;

  /* Card accent tints — dark mode */
  --card-accent-1: #1A1520;
  --card-accent-2: #101828;
  --card-accent-3: #101A18;
  --card-accent-4: #181028;

  /* Borders: Subtle blue-tinted */
  --border: #1C2233;
  --border-strong: #2A3348;

  /* Shadows: Blue-tinted depth */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.5);
  --shadow-float: 0 12px 32px rgba(59, 130, 246, 0.12);

  /* Glass */
  --gpt-glass-bg: rgba(12, 14, 20, 0.92);

  /* Price & rating colors (semantic, dark-only) */
  --price-deal: #22C55E;
  --rating-star: #F59E0B;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/globals.css
git commit -m "feat: v3 dark mode — rich blue-black (#0C0E14) with depth and blue undertone"
```

---

## Task 10: Light Mode Refinement

**Files:**
- Modify: `frontend/app/globals.css:5-100`

The spec calls for warm cream (#F7F5F0) instead of the current warm ivory (#FAFAF7), plus tinted shadows.

- [ ] **Step 1: Update light mode background and shadows**

In `frontend/app/globals.css`, update these values in the `:root` block:

```css
/* Change --background from #FAFAF7 to #F7F5F0 */
--background: #F7F5F0;

/* Change shadows to warm-tinted */
--shadow-sm: 0 1px 2px rgba(180, 160, 130, 0.06);
--shadow-md: 0 4px 12px rgba(180, 160, 130, 0.08);
--shadow-lg: 0 8px 24px rgba(180, 160, 130, 0.10);
--shadow-xl: 0 16px 40px rgba(180, 160, 130, 0.12);

/* Add price/rating semantic colors for light mode too */
--price-deal: #16A34A;
--rating-star: #D97706;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/globals.css
git commit -m "feat: v3 light mode — warm cream background, tinted shadows"
```

---

## Task 11: Make Dark Mode the Default

**Files:**
- Modify: `frontend/components/UnifiedTopbar.tsx:54-63`
- Modify: `frontend/components/MobileTabBar.tsx` (theme init section)

- [ ] **Step 1: Change default theme to dark**

In `frontend/components/UnifiedTopbar.tsx`, find lines 54-63:

```typescript
// OLD:
const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | null
const savedAccent = localStorage.getItem('accent') || 'indigo'
const initialTheme = savedTheme || 'light'
```

Replace with:

```typescript
// NEW:
const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | null
const savedAccent = localStorage.getItem('accent') || 'indigo'
const initialTheme = savedTheme || 'dark'
```

Also change the `useState` default on line 32:

```typescript
// OLD:
const [theme, setTheme] = useState<'light' | 'dark'>('light')
// NEW:
const [theme, setTheme] = useState<'light' | 'dark'>('dark')
```

Apply the same change to `MobileTabBar.tsx` if it has an independent theme initialization (search for `'light'` default there).

- [ ] **Step 2: Prevent flash of light theme on load**

In `frontend/app/layout.tsx`, add an inline script to the `<head>` that sets the theme attribute before React hydrates:

Find the `<html>` tag and add a script:

```tsx
<html lang="en" suppressHydrationWarning>
  <head>
    <script dangerouslySetInnerHTML={{
      __html: `
        (function() {
          var theme = localStorage.getItem('theme') || 'dark';
          document.documentElement.setAttribute('data-theme', theme);
          var accent = localStorage.getItem('accent');
          if (accent && accent !== 'indigo') {
            document.documentElement.setAttribute('data-accent', accent);
          }
        })();
      `
    }} />
  </head>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/UnifiedTopbar.tsx frontend/components/MobileTabBar.tsx frontend/app/layout.tsx
git commit -m "feat: make dark mode the default, prevent flash of light theme on load"
```

---

## Task 12: Enhanced Hover States & Micro-Interactions

**Files:**
- Modify: `frontend/app/globals.css:357-364`
- Modify: `frontend/components/CategorySidebar.tsx:129-131`
- Modify: `frontend/components/discover/TrendingCards.tsx:47-58`
- Modify: `frontend/components/AffiliateLinks.tsx`

- [ ] **Step 1: Enhance product-card-hover in globals.css**

In `frontend/app/globals.css`, replace the `.product-card-hover` rules (lines 357-364):

```css
/* OLD */
.product-card-hover {
  transition: transform 200ms cubic-bezier(0.16, 1, 0.3, 1), box-shadow 200ms ease;
}
.product-card-hover:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 24px rgba(28, 25, 23, 0.08);
}
```

```css
/* NEW — v3 enhanced with glow */
.product-card-hover {
  transition: transform 250ms cubic-bezier(0.16, 1, 0.3, 1),
              box-shadow 250ms ease,
              border-color 250ms ease;
}
.product-card-hover:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(28, 25, 23, 0.08),
              0 0 20px var(--primary-light);
  border-color: color-mix(in srgb, var(--primary) 25%, transparent);
}
[data-theme="dark"] .product-card-hover:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3),
              0 0 20px rgba(59, 130, 246, 0.15);
}
```

- [ ] **Step 2: Enhance sidebar hover states**

In `frontend/components/CategorySidebar.tsx`, find lines 129-131:

```tsx
// OLD:
className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-colors group
  text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-[var(--surface-hover)]"
```

Replace with:

```tsx
// NEW:
className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-all duration-200 group
  text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-[var(--primary-light)] hover:scale-[1.01]"
```

- [ ] **Step 3: Enhance trending card hover — arrow slides right**

In `frontend/components/discover/TrendingCards.tsx`, find the ChevronRight icon (line 114-118):

```tsx
// OLD:
<ChevronRight
  size={16}
  aria-hidden="true"
  style={{ color: 'var(--text-muted)', flexShrink: 0 }}
/>
```

Replace with:

```tsx
// NEW:
<ChevronRight
  size={16}
  aria-hidden="true"
  className="transition-transform duration-200 group-hover:translate-x-1"
  style={{ color: 'var(--text-muted)', flexShrink: 0 }}
/>
```

Also add `group` class to the button element (line 41):

```tsx
// Find the button's className:
className="product-card-hover w-full text-left"
// Replace with:
className="product-card-hover w-full text-left group"
```

- [ ] **Step 4: Commit**

```bash
git add frontend/app/globals.css frontend/components/CategorySidebar.tsx frontend/components/discover/TrendingCards.tsx
git commit -m "feat: v3 hover states — glow borders, arrow slides, sidebar accent highlights"
```

---

## Task 13: Expand Accent Color Picker to Full Theme Mood

**Files:**
- Modify: `frontend/app/globals.css:160-191`
- Modify: `frontend/components/UnifiedTopbar.tsx:9-15`

- [ ] **Step 1: Expand accent CSS to include card glow, gradient, sidebar tints**

In `frontend/app/globals.css`, replace the accent theme blocks (lines 160-191) with expanded versions:

```css
/* ═══════════════════════════════════════════
   V3 THEMED ACCENTS — Full mood shift
   Each accent affects: primary, accent, card glow,
   button gradients, sidebar highlights, hero tint
   ═══════════════════════════════════════════ */

[data-accent="ocean"] {
  --primary: #0EA5E9;
  --primary-hover: #38BDF8;
  --primary-light: rgba(14, 165, 233, 0.10);
  --accent: #06B6D4;
  --accent-hover: #22D3EE;
  --accent-light: rgba(6, 182, 212, 0.10);
  --shadow-float: 0 12px 32px rgba(14, 165, 233, 0.12);
}

[data-accent="sunset"] {
  --primary: #F97316;
  --primary-hover: #FB923C;
  --primary-light: rgba(249, 115, 22, 0.10);
  --accent: #EF4444;
  --accent-hover: #F87171;
  --accent-light: rgba(239, 68, 68, 0.10);
  --shadow-float: 0 12px 32px rgba(249, 115, 22, 0.12);
}

[data-accent="neon"] {
  --primary: #A855F7;
  --primary-hover: #C084FC;
  --primary-light: rgba(168, 85, 247, 0.10);
  --accent: #EC4899;
  --accent-hover: #F472B6;
  --accent-light: rgba(236, 72, 153, 0.10);
  --shadow-float: 0 12px 32px rgba(168, 85, 247, 0.12);
}

[data-accent="forest"] {
  --primary: #10B981;
  --primary-hover: #34D399;
  --primary-light: rgba(16, 185, 129, 0.10);
  --accent: #14B8A6;
  --accent-hover: #2DD4BF;
  --accent-light: rgba(20, 184, 166, 0.10);
  --shadow-float: 0 12px 32px rgba(16, 185, 129, 0.12);
}

[data-accent="berry"] {
  --primary: #E11D48;
  --primary-hover: #FB7185;
  --primary-light: rgba(225, 29, 72, 0.10);
  --accent: #DB2777;
  --accent-hover: #EC4899;
  --accent-light: rgba(219, 39, 119, 0.10);
  --shadow-float: 0 12px 32px rgba(225, 29, 72, 0.12);
}
```

- [ ] **Step 2: Update accent color picker labels and IDs**

In `frontend/components/UnifiedTopbar.tsx`, replace lines 9-15:

```typescript
// OLD:
const ACCENT_COLORS = [
  { id: 'indigo', label: 'Indigo', color: '#1B4DFF' },
  { id: 'teal', label: 'Teal', color: '#0D9488' },
  { id: 'rose', label: 'Rose', color: '#E11D48' },
  { id: 'amber', label: 'Amber', color: '#D97706' },
  { id: 'violet', label: 'Violet', color: '#7C3AED' },
] as const
```

```typescript
// NEW:
const ACCENT_COLORS = [
  { id: 'indigo', label: 'Default', color: '#3B82F6' },
  { id: 'ocean', label: 'Ocean', color: '#0EA5E9' },
  { id: 'sunset', label: 'Sunset', color: '#F97316' },
  { id: 'neon', label: 'Neon', color: '#A855F7' },
  { id: 'forest', label: 'Forest', color: '#10B981' },
  { id: 'berry', label: 'Berry', color: '#E11D48' },
] as const
```

Also update MobileTabBar.tsx if it has a separate `ACCENT_COLORS` definition.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/globals.css frontend/components/UnifiedTopbar.tsx
git commit -m "feat: v3 themed accent picker — Ocean, Sunset, Neon, Forest, Berry with full mood shift"
```

---

## Task 14: TopPickBlock Redesign — Add Price, Rating, Buy Button

**Files:**
- Modify: `frontend/components/TopPickBlock.tsx`
- Modify: `frontend/components/blocks/BlockRegistry.tsx:35-43`

The "Our Top Pick" card currently shows only name + headline + bestFor/notFor. The spec requires price, rating, and a prominent buy button.

- [ ] **Step 1: Expand TopPickBlock props and UI**

Replace the entire `frontend/components/TopPickBlock.tsx`:

```tsx
'use client'

import { useState } from 'react'
import { Award, ExternalLink, Star, ChevronDown, ChevronUp } from 'lucide-react'
import { stripMarkdown } from '@/lib/stripMarkdown'

interface TopPickBlockProps {
  productName: string
  headline: string
  bestFor: string
  notFor: string
  imageUrl?: string
  affiliateUrl?: string
  price?: number
  currency?: string
  merchant?: string
  rating?: number
  pros?: string[]
  cons?: string[]
}

export default function TopPickBlock({
  productName,
  headline,
  bestFor,
  notFor,
  imageUrl,
  affiliateUrl,
  price,
  currency = 'USD',
  merchant = 'Amazon',
  rating,
  pros = [],
  cons = [],
}: TopPickBlockProps) {
  const [showDetails, setShowDetails] = useState(false)

  if (!productName) return null

  return (
    <div className="rounded-xl border-2 border-[var(--primary)] bg-[var(--surface-elevated)] p-5 mb-4 shadow-card product-card-hover">
      {/* Badge */}
      <div className="flex items-center gap-2 mb-3">
        <Award size={16} className="text-[var(--primary)]" />
        <span className="text-xs font-bold uppercase tracking-wider text-[var(--primary)]">
          Our Top Pick
        </span>
      </div>

      <div className="flex gap-4">
        {/* Image — 140x140 min */}
        <div className="flex-shrink-0 w-[140px] h-[140px] rounded-lg overflow-hidden bg-[var(--surface)]">
          {imageUrl ? (
            <img
              src={imageUrl}
              alt={productName}
              className="w-full h-full object-contain p-2"
              loading="lazy"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Award size={40} className="text-[var(--text-muted)]" />
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-serif font-bold text-[var(--text)] mb-1">
            {affiliateUrl ? (
              <a
                href={affiliateUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-[var(--primary)] transition-colors"
              >
                {productName}
              </a>
            ) : (
              productName
            )}
          </h3>

          {/* Rating */}
          {rating && (
            <div className="flex items-center gap-1.5 mb-2">
              <div className="flex items-center">
                {[1, 2, 3, 4, 5].map((s) => (
                  <Star
                    key={s}
                    size={14}
                    fill={s <= Math.round(rating) ? 'currentColor' : 'none'}
                    className={s <= Math.round(rating) ? 'text-amber-500' : 'text-[var(--text-muted)]'}
                  />
                ))}
              </div>
              <span className="text-sm font-medium text-[var(--text)]">{rating.toFixed(1)}/5</span>
            </div>
          )}

          {headline && (
            <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-3">
              {stripMarkdown(headline)}
            </p>
          )}

          {/* Buy Button */}
          {affiliateUrl && (
            <a
              href={affiliateUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold text-white transition-all hover:brightness-110 active:scale-[0.97]"
              style={{
                background: 'linear-gradient(135deg, var(--primary), var(--accent))',
              }}
            >
              {price ? `Buy on ${merchant} — ${currency === 'USD' ? '$' : currency}${price.toFixed(2)}` : `Buy on ${merchant}`}
              <ExternalLink size={14} />
            </a>
          )}
        </div>
      </div>

      {/* Best for / Not for */}
      <div className="mt-3 space-y-1.5 text-sm">
        {bestFor && (
          <p className="text-[var(--text-secondary)]">
            <span className="font-semibold text-emerald-600 dark:text-emerald-400">Best for:</span>{' '}
            {bestFor}
          </p>
        )}
        {notFor && (
          <p className="text-[var(--text-secondary)]">
            <span className="font-semibold text-[var(--accent)]">Look elsewhere if:</span>{' '}
            {notFor}
          </p>
        )}
      </div>

      {/* Expandable Pros/Cons */}
      {(pros.length > 0 || cons.length > 0) && (
        <div className="mt-3 pt-3 border-t border-[var(--border)]">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="flex items-center gap-1 text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text)] transition-colors"
          >
            {showDetails ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {showDetails ? 'Hide details' : 'Show pros & cons'}
          </button>
          {showDetails && (
            <div className="mt-2 space-y-2 text-sm">
              {pros.length > 0 && (
                <p className="text-[var(--text)]">
                  <span className="font-semibold text-green-600">Pros:</span>{' '}
                  {pros.join('. ')}.
                </p>
              )}
              {cons.length > 0 && (
                <p className="text-[var(--text)]">
                  <span className="font-semibold text-red-500">Cons:</span>{' '}
                  {cons.join('. ')}.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Update BlockRegistry to pass new props**

In `frontend/components/blocks/BlockRegistry.tsx`, replace lines 35-43:

```tsx
// OLD:
top_pick: (b) => (
    <TopPickBlock
        productName={(b.data as any)?.product_name ?? ''}
        headline={(b.data as any)?.headline ?? ''}
        bestFor={(b.data as any)?.best_for ?? ''}
        notFor={(b.data as any)?.not_for ?? ''}
        imageUrl={(b.data as any)?.image_url}
        affiliateUrl={(b.data as any)?.affiliate_url}
    />
),
```

```tsx
// NEW:
top_pick: (b) => (
    <TopPickBlock
        productName={(b.data as any)?.product_name ?? ''}
        headline={(b.data as any)?.headline ?? ''}
        bestFor={(b.data as any)?.best_for ?? ''}
        notFor={(b.data as any)?.not_for ?? ''}
        imageUrl={(b.data as any)?.image_url}
        affiliateUrl={(b.data as any)?.affiliate_url}
        price={(b.data as any)?.price}
        currency={(b.data as any)?.currency}
        merchant={(b.data as any)?.merchant}
        rating={(b.data as any)?.rating}
        pros={(b.data as any)?.pros}
        cons={(b.data as any)?.cons}
    />
),
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/TopPickBlock.tsx frontend/components/blocks/BlockRegistry.tsx
git commit -m "feat: TopPickBlock v3 — price, rating, gradient buy button, expandable pros/cons"
```

---

## Task 15: Add Buy Button to ProductCards

**Files:**
- Modify: `frontend/components/ProductCards.tsx:136-145`

The current CTA is a text link ("Check price on Amazon ->"). Replace with a prominent button.

- [ ] **Step 1: Replace text CTA with gradient button**

In `frontend/components/ProductCards.tsx`, find lines 136-145:

```tsx
// OLD:
<div className="flex justify-start pt-3 border-t border-[var(--border)]">
  <a
    href={displayLink}
    target="_blank"
    rel="noopener noreferrer"
    className="inline-flex items-center gap-2 text-sm font-medium text-[var(--primary)] hover:text-[var(--primary-hover)] transition-colors"
  >
    Check price{displayMerchant ? ` on ${displayMerchant}` : ''} &rarr;
  </a>
</div>
```

Replace with:

```tsx
// NEW:
<div className="flex items-center justify-between pt-3 border-t border-[var(--border)]">
  <a
    href={displayLink}
    target="_blank"
    rel="noopener noreferrer"
    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-all hover:brightness-110 active:scale-[0.97]"
    style={{
      background: 'linear-gradient(135deg, var(--primary), var(--accent))',
    }}
  >
    {displayPrice !== undefined
      ? `Buy on ${displayMerchant || 'Amazon'} — $${displayPrice.toFixed(2)}`
      : `Check price on ${displayMerchant || 'Amazon'}`}
    <ExternalLink size={14} />
  </a>
</div>
```

Also add the ExternalLink import at the top of the file:

```typescript
import { ExternalLink } from 'lucide-react'
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/ProductCards.tsx
git commit -m "feat: gradient buy button on product cards with price + merchant"
```

---

## Task 16: Homepage — Add Sidebar, Remove Category Pills

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Restructure homepage with sidebar layout**

Replace the entire `frontend/app/page.tsx`:

```tsx
'use client'

import { useState, useEffect } from 'react'
import { getRecentSearches } from '@/lib/recentSearches'
import DiscoverSearchBar from '@/components/discover/DiscoverSearchBar'
import TrendingCards from '@/components/discover/TrendingCards'
import CategorySidebar from '@/components/CategorySidebar'

export default function DiscoverPage() {
  const [hasHistory, setHasHistory] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    setHasHistory(getRecentSearches().length > 0)
  }, [])

  return (
    <div className="flex min-h-[calc(100vh-64px)]">
      {/* Sidebar — same as chat page */}
      <div className="hidden lg:block">
        <CategorySidebar isOpen={true} />
      </div>
      {/* Mobile sidebar */}
      <div className="lg:hidden">
        <CategorySidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col pb-28 px-4 sm:px-6 md:px-8">
        {/* Hero section */}
        <div className="flex flex-col items-center pt-8 sm:pt-12 pb-8">
          <h1
            className="font-serif text-3xl sm:text-4xl md:text-5xl text-center leading-tight tracking-tight"
            style={{ color: 'var(--text)' }}
          >
            What are you{' '}
            <span
              className="italic"
              style={{ color: 'var(--primary)' }}
            >
              researching
            </span>
            {' '}today?
          </h1>
          <p
            className="text-sm text-center mt-3 max-w-md"
            style={{ color: 'var(--text-secondary)' }}
          >
            Expert reviews, real data, zero fluff.
          </p>
        </div>

        {/* Trending cards — category pills removed, they live in sidebar now */}
        <div className="mt-6">
          <TrendingCards />
        </div>
      </div>

      {/* Sticky bottom search bar */}
      <div className="fixed bottom-0 left-0 right-0 z-50 p-3 sm:p-4 lg:pl-56"
        style={{
          background: 'var(--surface-float)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          borderTop: '1px solid var(--border)',
        }}
      >
        <div className="max-w-xl mx-auto">
          <DiscoverSearchBar />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat: homepage v3 — sidebar, no category pills, sticky bottom search bar, larger hero"
```

---

## Task 17: Compact Footer

**Files:**
- Modify: `frontend/components/Footer.tsx`

The spec says: make the footer useful or minimize to a single line.

- [ ] **Step 1: Replace with compact single-line footer**

Replace `frontend/components/Footer.tsx`:

```tsx
import Link from 'next/link'

export default function Footer() {
  return (
    <footer className="w-full border-t border-[var(--border)] bg-[var(--surface)]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-[var(--text-muted)]">
          <div className="flex items-center gap-1">
            <span className="font-serif font-semibold text-[var(--text-secondary)]">ReviewGuide.ai</span>
            <span>&copy; {new Date().getFullYear()}</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/privacy" className="hover:text-[var(--text)] transition-colors">Privacy</Link>
            <Link href="/terms" className="hover:text-[var(--text)] transition-colors">Terms</Link>
            <Link href="/affiliate-disclosure" className="hover:text-[var(--text)] transition-colors">Affiliate Disclosure</Link>
            <a href="mailto:mike@reviewguide.ai" className="hover:text-[var(--text)] transition-colors">Contact</a>
          </div>
        </div>
      </div>
    </footer>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/Footer.tsx
git commit -m "feat: compact single-line footer — brand, legal, contact in one row"
```

---

## Task 18: Product Image Fallback Chain

**Files:**
- Create: `frontend/lib/productImages.ts`
- Modify: `frontend/components/InlineProductCard.tsx`
- Modify: `frontend/components/ProductCards.tsx`
- Modify: `frontend/components/TopPickBlock.tsx`

Create a centralized image resolution utility with a fallback chain: curated ASIN image -> product data image -> category placeholder icon. Never show blank space.

- [ ] **Step 1: Create the image fallback utility**

```typescript
// frontend/lib/productImages.ts

import { curatedLinks } from '@/lib/curatedLinks'

// Category placeholder icons (SVG data URIs) — never show blank space
const CATEGORY_PLACEHOLDERS: Record<string, string> = {
  headphones: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%238892A4" stroke-width="1.5"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>',
  laptop: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%238892A4" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M2 20h20"/></svg>',
  default: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%238892A4" stroke-width="1.5"><rect x="2" y="2" width="20" height="20" rx="2"/><path d="m16 8-4 4-4-4"/></svg>',
}

/**
 * Detect product category from name for placeholder selection.
 */
function detectCategory(name: string): string {
  const lower = name.toLowerCase()
  if (lower.match(/headphone|earbud|speaker|audio|airpod|bose|sony wh|jabra/)) return 'headphones'
  if (lower.match(/laptop|macbook|chromebook|notebook|computer/)) return 'laptop'
  return 'default'
}

/**
 * Look up curated Amazon image by product name.
 */
function lookupCuratedImage(name: string): string | null {
  const nameLower = name.toLowerCase()
  for (const category of Object.values(curatedLinks)) {
    for (const topic of category) {
      for (const product of topic.products) {
        if (
          product.name?.toLowerCase().includes(nameLower) ||
          nameLower.includes(product.name?.toLowerCase() || '')
        ) {
          if (product.asin) {
            return `https://images-na.ssl-images-amazon.com/images/I/${product.asin}._SL300_.jpg`
          }
        }
      }
    }
  }
  return null
}

/**
 * Resolve a product image using fallback chain:
 * 1. Direct image_url from API
 * 2. Curated ASIN image from curatedLinks
 * 3. Category placeholder icon
 */
export function resolveProductImage(
  name: string,
  imageUrl?: string | null,
): string {
  if (imageUrl) return imageUrl
  const curated = lookupCuratedImage(name)
  if (curated) return curated
  const category = detectCategory(name)
  return CATEGORY_PLACEHOLDERS[category] || CATEGORY_PLACEHOLDERS.default
}

/**
 * Returns true if the image is a placeholder (SVG data URI).
 */
export function isPlaceholderImage(url: string): boolean {
  return url.startsWith('data:image/svg+xml')
}
```

- [ ] **Step 2: Use in InlineProductCard**

In `frontend/components/InlineProductCard.tsx`, add import:

```typescript
import { resolveProductImage, isPlaceholderImage } from '@/lib/productImages'
```

Replace the `ProductImage` component (lines 48-71) with:

```tsx
function ProductImage({ name, imageUrl }: { name: string; imageUrl: string | null }) {
  const [errored, setErrored] = useState(false)
  const resolvedUrl = resolveProductImage(name, errored ? null : imageUrl)
  const isPlaceholder = isPlaceholderImage(resolvedUrl)

  return isPlaceholder ? (
    <div
      className="w-16 h-16 rounded-lg flex-shrink-0 flex items-center justify-center"
      style={{ backgroundColor: 'var(--surface-hover)' }}
    >
      <img src={resolvedUrl} alt="" className="w-8 h-8 opacity-50" />
    </div>
  ) : (
    <img
      src={resolvedUrl}
      alt={name}
      className="w-16 h-16 rounded-lg object-cover flex-shrink-0"
      onError={() => setErrored(true)}
    />
  )
}
```

Remove the old `lookupCuratedProduct` function and the `ShoppingCart` import if no longer used.

- [ ] **Step 3: Use in ProductCards**

In `frontend/components/ProductCards.tsx`, add import:

```typescript
import { resolveProductImage, isPlaceholderImage } from '@/lib/productImages'
```

Replace the image section (lines 64-76). Currently the image block is wrapped in `{displayImage && ...}` which hides it when there's no image. Change to always show:

```tsx
{/* Product image — always show, use fallback chain */}
<a href={displayLink} target="_blank" rel="noopener noreferrer" className="shrink-0">
  <div className="w-20 h-20 sm:w-24 sm:h-24 rounded-lg overflow-hidden bg-[var(--surface)] border border-[var(--border)]">
    {(() => {
      const imgSrc = resolveProductImage(displayTitle, displayImage || null)
      return isPlaceholderImage(imgSrc) ? (
        <div className="w-full h-full flex items-center justify-center">
          <img src={imgSrc} alt="" className="w-10 h-10 opacity-40" />
        </div>
      ) : (
        <img
          src={imgSrc}
          alt={displayTitle}
          className="w-full h-full object-contain p-1"
          loading="lazy"
          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
        />
      )
    })()}
  </div>
</a>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/productImages.ts frontend/components/InlineProductCard.tsx frontend/components/ProductCards.tsx
git commit -m "feat: product image fallback chain — curated, API, category placeholder — never blank"
```

---

## Task 19: Chat Input Polish

**Files:**
- Modify: `frontend/components/ChatInput.tsx`

Add placeholder mic/attachment icons and enhance the send button animation per spec.

- [ ] **Step 1: Add placeholder icons and enhance send button**

In `frontend/components/ChatInput.tsx`, add imports:

```typescript
import { ArrowUp, Mic, Paperclip } from 'lucide-react'
```

After the `<textarea>` element and before the send button, add placeholder icons:

```tsx
{/* Placeholder icons — left of send button */}
<div className="absolute right-14 bottom-3.5 flex items-center gap-1">
  <button
    type="button"
    className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors opacity-50 cursor-default"
    title="Voice input (coming soon)"
    disabled
  >
    <Mic size={16} />
  </button>
  <button
    type="button"
    className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors opacity-50 cursor-default"
    title="Attach image (coming soon)"
    disabled
  >
    <Paperclip size={16} />
  </button>
</div>
```

For the send button, update the `pr-14` on the textarea to `pr-28` to make room for the icons.

- [ ] **Step 2: Commit**

```bash
git add frontend/components/ChatInput.tsx
git commit -m "feat: chat input polish — placeholder mic/attachment icons, wider padding"
```

---

## Task 20: Saved & Compare Placeholder Pages

**Files:**
- Create: `frontend/app/saved/page.tsx`
- Create: `frontend/app/compare/page.tsx`

- [ ] **Step 1: Create saved page placeholder**

```tsx
// frontend/app/saved/page.tsx
'use client'

import { Bookmark } from 'lucide-react'

export default function SavedPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4 text-center">
      <div
        className="w-20 h-20 rounded-2xl flex items-center justify-center mb-6"
        style={{ background: 'var(--primary-light)' }}
      >
        <Bookmark size={36} className="text-[var(--primary)]" />
      </div>
      <h1 className="font-serif text-2xl font-bold text-[var(--text)] mb-2">
        Saved Products
      </h1>
      <p className="text-sm text-[var(--text-secondary)] max-w-sm mb-6">
        Save products during your research to compare later. Your saved items will appear here.
      </p>
      <div className="w-full max-w-md space-y-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-16 rounded-xl border border-dashed border-[var(--border)] animate-pulse"
            style={{ background: 'var(--surface)', opacity: 0.5 }}
          />
        ))}
      </div>
      <p className="text-xs text-[var(--text-muted)] mt-6">Coming soon</p>
    </div>
  )
}
```

- [ ] **Step 2: Create compare page placeholder**

```tsx
// frontend/app/compare/page.tsx
'use client'

import { ArrowLeftRight } from 'lucide-react'

export default function ComparePage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4 text-center">
      <div
        className="w-20 h-20 rounded-2xl flex items-center justify-center mb-6"
        style={{ background: 'var(--primary-light)' }}
      >
        <ArrowLeftRight size={36} className="text-[var(--primary)]" />
      </div>
      <h1 className="font-serif text-2xl font-bold text-[var(--text)] mb-2">
        Compare Products
      </h1>
      <p className="text-sm text-[var(--text-secondary)] max-w-sm mb-6">
        Add products to your comparison board to see specs, prices, and ratings side by side.
      </p>
      <div className="w-full max-w-lg">
        <div className="grid grid-cols-3 gap-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-40 rounded-xl border border-dashed border-[var(--border)] flex items-center justify-center"
              style={{ background: 'var(--surface)', opacity: 0.5 }}
            >
              <span className="text-2xl text-[var(--text-muted)]">+</span>
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs text-[var(--text-muted)] mt-6">Coming soon</p>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/saved/page.tsx frontend/app/compare/page.tsx
git commit -m "feat: placeholder pages for Saved and Compare with empty state illustrations"
```

---

## Task 21: Reusable Shimmer Skeleton Component

**Files:**
- Create: `frontend/components/ui/Skeleton.tsx`

- [ ] **Step 1: Create the skeleton component**

```tsx
// frontend/components/ui/Skeleton.tsx
'use client'

interface SkeletonProps {
  className?: string
  /** Shape variant */
  variant?: 'text' | 'circular' | 'rectangular' | 'card'
  /** Width — accepts CSS value */
  width?: string
  /** Height — accepts CSS value */
  height?: string
}

export default function Skeleton({
  className = '',
  variant = 'text',
  width,
  height,
}: SkeletonProps) {
  const baseClasses = 'animate-shimmer rounded'
  const variantClasses = {
    text: 'h-4 rounded-md',
    circular: 'rounded-full',
    rectangular: 'rounded-lg',
    card: 'rounded-xl h-40',
  }

  return (
    <div
      className={`${baseClasses} ${variantClasses[variant]} ${className}`}
      style={{
        width: width || (variant === 'circular' ? '40px' : '100%'),
        height: height || undefined,
        background: 'linear-gradient(90deg, var(--surface) 25%, var(--surface-hover) 50%, var(--surface) 75%)',
        backgroundSize: '200% 100%',
      }}
    />
  )
}

/**
 * Pre-composed skeleton for a product card.
 */
export function ProductCardSkeleton() {
  return (
    <div className="p-5 rounded-xl border border-[var(--border)]" style={{ background: 'var(--surface-elevated)' }}>
      <div className="flex gap-4">
        <Skeleton variant="rectangular" width="96px" height="96px" />
        <div className="flex-1 space-y-2">
          <Skeleton variant="text" width="70%" height="20px" />
          <Skeleton variant="text" width="40%" height="14px" />
          <Skeleton variant="text" width="90%" height="14px" />
          <Skeleton variant="text" width="30%" height="32px" className="mt-2" />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/ui/Skeleton.tsx
git commit -m "feat: reusable Skeleton shimmer component with product card variant"
```

---

## Task 22: Performance — Click Feedback, Smooth Scroll, Reduced Motion

**Files:**
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Add click feedback utility class**

In `frontend/app/globals.css`, add after the `.product-card-hover` section:

```css
/* ═══════════════════════════════════════════
   V3 — Click feedback & interactions
   ═══════════════════════════════════════════ */

.click-feedback:active {
  transform: scale(0.97);
  transition: transform 100ms ease;
}

/* Smooth scroll site-wide */
html {
  scroll-behavior: smooth;
}

/* Respect reduced motion */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }

  .product-card-hover:hover {
    transform: none;
  }

  .animate-shimmer {
    animation: none;
    background: var(--surface-hover);
  }
}
```

- [ ] **Step 2: Remove the old reduced motion block**

Remove the existing `@media (prefers-reduced-motion: reduce)` block at lines 430-437 since the new one above is more comprehensive.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/globals.css
git commit -m "feat: click feedback, comprehensive reduced-motion support, smooth scroll"
```

---

## Task 23: Verify Build

- [ ] **Step 1: Run the build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no TypeScript errors. Warnings about unused vars are acceptable.

- [ ] **Step 2: Fix any build errors**

Address any import errors, missing types, or broken references.

- [ ] **Step 3: Visual verification**

```bash
cd frontend && npm run dev
```

Check:
- Dark mode loads by default (no flash of light)
- Trending cards have glow hover
- Sidebar visible on homepage (desktop)
- Footer is compact single line
- User message bubble doesn't wrap short queries
- "Thinking..." shows pulsing dots

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "fix: address any build errors from v3 implementation"
```

---

## Dependency Graph

```
Task 1 (stripMarkdown) ──→ Task 3 (use in product cards)
                        ──→ Task 14 (use in TopPickBlock)

Task 2 (bubble fix)     ── independent
Task 4 (buy cards)      ── independent
Task 5 (history fix)    ── independent

Task 6 (remove LLM)     ──→ Task 7 (stream blog_article)
Task 7 (stream backend) ──→ Task 8 (stream frontend)

Task 9 (dark mode)      ──→ Task 11 (default dark)
Task 10 (light mode)    ── independent
Task 12 (hover states)  ── depends on Task 9 (dark mode vars)
Task 13 (accent picker) ── depends on Task 9 (new base vars)

Task 14 (TopPickBlock)  ── depends on Task 1
Task 15 (buy button)    ── independent

Task 16 (homepage)      ── independent
Task 17 (footer)        ── independent

Task 18 (images)        ── independent
Task 19 (chat input)    ── independent
Task 20 (placeholder)   ── independent
Task 21 (skeleton)      ── independent
Task 22 (performance)   ── independent
Task 23 (verify)        ── depends on all above
```

**Parallelizable groups:**
- Group A: Tasks 1, 2, 4, 5 (independent bug fixes)
- Group B: Tasks 6 → 7 → 8 (streaming pipeline, sequential)
- Group C: Tasks 9, 10 → 11, 12, 13 (theme, semi-sequential)
- Group D: Tasks 14, 15, 16, 17, 18, 19, 20, 21 (independent frontend)
- Group E: Task 22, 23 (final polish)

---

## Summary

| Phase | Tasks | Impact | Effort |
|-------|-------|--------|--------|
| Bug fixes | 1-5 | Critical — fixes broken UX | Low |
| Streaming | 6-8 | Highest — perceived speed 10x | High (backend) |
| Theme | 9-13 | High — visual transformation | Medium |
| Product cards | 14-15 | High — buy conversion | Medium |
| Homepage | 16-17 | Medium — first impression | Medium |
| Images | 18 | Medium — product trust | Low |
| Micro-UX | 19-20 | Low — polish | Low |
| Performance | 21-23 | Medium — perceived quality | Low |
