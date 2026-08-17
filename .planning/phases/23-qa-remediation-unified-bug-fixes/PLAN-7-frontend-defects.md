# Frontend Defects Implementation Plan

> **⚠ VALIDATION CORRECTIONS (Kimi, 2026-07-31) — binding on executors:**
>
> - **T1:** `ConversationSidebar` already has `isOpen`/`onClose` — but requires
>   THREE more props (`currentSessionId`, `onSelectConversation`,
>   `onNewConversation`, `ConversationSidebar.tsx:19-25`) that NavLayout cannot
>   supply from its own state (it holds none; the real handlers live in
>   `app/chat/page.tsx:138-160`). Wire `onSelectConversation` to
>   `router.push('/chat?session=<id>')` and `onNewConversation` to the existing
>   `handleNewChat`. The drawer renders ALWAYS today (closed = CSS
>   `translate-x-full lg:hidden`, `:132`) — Step 4's "render nothing when
>   closed" must be implemented as an early `if (!isOpen) return null` INSIDE
>   the sidebar or the test's `queryByLabelText → null` assertion is
>   meaningless. The close button is mobile-only (`lg:hidden`, `:145`) — fine
>   in jsdom (no media queries) but note it in the test. **Known gap, explicitly
>   out of scope unless Habib says otherwise:** MobileHeader/MobileTabBar have
>   NO History entry at all — on mobile the drawer stays unreachable even after
>   this fix.
> - **T5:** key staleness on "a newer CLARIFIER card exists", NOT "any newer
>   assistant message" — the ask-more flow deliberately keeps the older card's
>   slots open and answerable (`clarifier_agent.py:999-1004`); locking every
>   superseded card breaks that designed path. `MessageList` already computes
>   `lastAiMessage` (`MessageList.tsx:21`) — derive "last clarifier card"
>   similarly. Message takes `{message, isLast}` only; thread the new prop.
> - **T6:** there is no `inputRef` and no `chat-input` testid — the input ref is
>   `textareaRef` INSIDE `ChatInput` (`ChatInput.tsx:22`). Fix via an
>   `autoFocus`-on-mount prop on ChatInput (or expose focus imperatively);
>   adapt the test to query the real textarea (`aria-label` on it, or add a
>   testid as part of the fix).
> - Testids referenced anywhere in this plan that don't exist yet
>   (`topbar-history-button`, `chat-error-banner`) are ADDED as part of the fix
>   steps — that part of v1 was intentional and stands.

> **For agentic workers:** Use superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the eight frontend defects the audit found — a history drawer that never
opens, a dead Regenerate button, a missing affiliate disclosure, a broken comparison
table, stale interactive widgets, dropped keystrokes, clipped text, and ambiguous rank
numerals.

**Architecture:** These are independent component-level bugs with no shared cause. Each
task is self-contained and can ship alone. Two have root causes already identified in
source; the rest start with a reproduce step.

**Tech Stack:** Next.js 14 / React 18 / TypeScript / Tailwind, vitest.

## Global Constraints

- Terracotta-on-cream design tokens: `--terra #B8543A`, `--ink #1A1816`,
  `--paper #FAFAF7`, `--line #E8E6E1`. **No blue.**
- Component duplication is the #1 time-sink in this repo. Product cards exist in three
  render contexts — `ProductCarousel.tsx` (chat carousel), `ProductReview.tsx` (rich
  review card), `ResultsProductCard.tsx` (`/results/[id]` only). Confirm which one
  renders before editing.
- Discover is `app/page.tsx` served at `/`. `/discover` and `/browse` redirect to it.
- **No orphan lines** in any copy added here.
- Never use `Math.random()` or `Date.now()` in server-rendered components — it causes
  hydration mismatches.
- Tests: `cd frontend && npx vitest run <file>`

## File Structure

- Modify: `frontend/components/NavLayout.tsx` — history drawer state (T1), disclosure (T3)
- Modify: `frontend/components/ChatContainer.tsx` — Regenerate guard (T2), focus (T6)
- Modify: `frontend/components/ComparisonTable.tsx` — data + overflow (T4)
- Modify: `frontend/components/Message.tsx` — stale widgets (T5), numerals (T8)
- Create: `frontend/tests/historyDrawer.test.tsx`, `frontend/tests/regenerate.test.tsx`

---

### Task 1: The history drawer must open

**Root cause — confirmed.** `frontend/components/NavLayout.tsx:42-44`:

```tsx
  const handleHistory = () => {
    router.push('/chat')
  }
```

The topbar's History button (`UnifiedTopbar.tsx:187`) calls this, which navigates instead
of opening the drawer. `ConversationSidebar` renders its own "Close history" control
(`ConversationSidebar.tsx:144`) but nothing ever sets it open. The `display: none` the
audit saw is the drawer's default closed state — there is no open-state wiring at all.

**Files:**
- Modify: `frontend/components/NavLayout.tsx`
- Create: `frontend/tests/historyDrawer.test.tsx`

**Interfaces:**
- Consumes: `UnifiedTopbar`'s `onHistoryClick?: () => void` (`UnifiedTopbar.tsx:13`)
- Produces: `historyOpen` state in `NavLayout`, passed to `ConversationSidebar`

- [ ] **Step 1: Read the sidebar's open/close contract**

```bash
cd frontend && grep -n "interface\|Props\|isOpen\|onClose\|export default" components/ConversationSidebar.tsx | head -20
```

Use its real prop names below. If it has no `isOpen` prop, add one rather than toggling
CSS from outside.

- [ ] **Step 2: Write the failing test**

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import NavLayout from '@/components/NavLayout'

vi.mock('next/navigation', () => ({
  usePathname: () => '/chat',
  useRouter: () => ({ push: vi.fn() }),
}))

describe('history drawer', () => {
  it('is closed initially', () => {
    render(<NavLayout><div /></NavLayout>)
    expect(screen.queryByLabelText('Close history')).toBeNull()
  })

  it('opens when the topbar History button is clicked', () => {
    render(<NavLayout><div /></NavLayout>)
    fireEvent.click(screen.getByTestId('topbar-history-button'))
    expect(screen.getByLabelText('Close history')).toBeTruthy()
  })

  it('closes again from the drawer control', () => {
    render(<NavLayout><div /></NavLayout>)
    fireEvent.click(screen.getByTestId('topbar-history-button'))
    fireEvent.click(screen.getByLabelText('Close history'))
    expect(screen.queryByLabelText('Close history')).toBeNull()
  })
})
```

Add `data-testid="topbar-history-button"` to the History button at
`UnifiedTopbar.tsx:187` if it has none.

- [ ] **Step 3: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/historyDrawer.test.tsx`
Expected: FAIL — the drawer never appears.

- [ ] **Step 4: Wire the state**

In `NavLayout.tsx`, replace the navigating handler:

```tsx
  const [historyOpen, setHistoryOpen] = useState(false)

  // The History button opens the conversation drawer. It used to router.push('/chat'),
  // which navigated without ever opening the drawer — so ten conversations were
  // created during QA and none were reachable.
  const handleHistory = () => setHistoryOpen((open) => !open)
```

Render the sidebar inside the layout, below the topbar:

```tsx
        <ConversationSidebar
          isOpen={historyOpen}
          onClose={() => setHistoryOpen(false)}
        />
```

Add `import { useState } from 'react'` and the `ConversationSidebar` import. When closed,
render nothing rather than a hidden node, so the test's `queryByLabelText` is meaningful.

- [ ] **Step 5: Run to verify it passes**

Run: `cd frontend && npx vitest run tests/historyDrawer.test.tsx`
Expected: all 3 PASS.

- [ ] **Step 6: Verify live**

Start the dev server, create two chats, open History, and confirm both are listed and
selectable.

- [ ] **Step 7: Commit**

```bash
git add frontend/components/NavLayout.tsx frontend/components/UnifiedTopbar.tsx \
        frontend/components/ConversationSidebar.tsx frontend/tests/historyDrawer.test.tsx
git commit -m "fix(ui): History button opens the conversation drawer"
```

---

### Task 2: Regenerate must do something — or say why it can't

**Root cause — confirmed.** `frontend/components/ChatContainer.tsx:666-667`:

```tsx
  const handleRetry = async () => {
    if (!pendingUserMessage || isStreaming) return
```

A silent early return. In the audit's scenario the first stream had hung, so `isStreaming`
was still `true` when the error banner appeared — every Regenerate click hit this guard
and did nothing, with no feedback. PLAN-6 Task 1 fixes the stuck `isStreaming`; this task
makes the button honest even when the guard is legitimately hit.

**Files:**
- Modify: `frontend/components/ChatContainer.tsx:666-674`
- Modify: `frontend/components/ErrorBanner.tsx`
- Create: `frontend/tests/regenerate.test.tsx`

**Interfaces:**
- Consumes: `ErrorBanner`'s `onRetry: () => void` (`ErrorBanner.tsx:5`), rendered at
  `ChatContainer.tsx:905-908`
- Produces: a `disabled` prop on `ErrorBanner` so the button reflects its own state

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ErrorBanner from '@/components/ErrorBanner'

describe('ErrorBanner regenerate', () => {
  it('calls onRetry when enabled', () => {
    const onRetry = vi.fn()
    render(<ErrorBanner message="Hit a wall" onRetry={onRetry} />)
    fireEvent.click(screen.getByRole('button', { name: /regenerate/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('is disabled and explains itself while a request is in flight', () => {
    const onRetry = vi.fn()
    render(<ErrorBanner message="Hit a wall" onRetry={onRetry} disabled />)
    const button = screen.getByRole('button', { name: /regenerate/i })
    expect(button).toHaveProperty('disabled', true)
    fireEvent.click(button)
    expect(onRetry).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/regenerate.test.tsx`
Expected: the first test PASSES, the second FAILS — no `disabled` prop exists.

- [ ] **Step 3: Add the disabled state**

In `ErrorBanner.tsx`, extend the props and the button:

```tsx
interface ErrorBannerProps {
  message: string
  onRetry: () => void
  disabled?: boolean
}
```

```tsx
      <button
        onClick={onRetry}
        disabled={disabled}
        title={disabled ? 'Still finishing the last request…' : undefined}
        className="mt-3 px-4 py-2 rounded-md text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
```

Keep the existing inline `style` block and hover handlers; guard the hover handlers on
`!disabled` so a disabled button does not light up.

- [ ] **Step 4: Pass the state from ChatContainer**

At `ChatContainer.tsx:905-908`:

```tsx
            <ErrorBanner
              message={errorMessage}
              onRetry={handleRetry}
              disabled={isStreaming || !pendingUserMessage}
            />
```

And make the guard log instead of returning in silence:

```tsx
  const handleRetry = async () => {
    if (isStreaming) {
      console.warn('[retry] ignored — a stream is still in flight')
      return
    }
    if (!pendingUserMessage) {
      console.warn('[retry] ignored — no pending message to retry')
      return
    }
    setIsRetrying(true)
    setShowErrorBanner(false)
    await handleStream(pendingUserMessage, false)
  }
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd frontend && npx vitest run tests/regenerate.test.tsx`
Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/ErrorBanner.tsx frontend/components/ChatContainer.tsx \
        frontend/tests/regenerate.test.tsx
git commit -m "fix(ui): Regenerate works, and shows why when it cannot"
```

---

### Task 3: Affiliate disclosure must be visible where the links are

**Root cause — confirmed.** An `/affiliate-disclosure` route exists — it is listed in
`NavLayout.tsx:10`'s `EXCLUDED_PREFIXES`. The link to it lives in `Footer`, and
`NavLayout.tsx:78` renders the footer only when `!isChat`. Chat is exactly where every
Amazon/eBay/Expedia outbound link appears, so the disclosure is absent from the one screen
that needs it.

**Files:**
- Modify: `frontend/components/ChatContainer.tsx` — persistent disclosure line
- Create: `frontend/tests/affiliateDisclosure.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ChatContainer from '@/components/ChatContainer'

describe('affiliate disclosure', () => {
  it('is visible on the chat screen', () => {
    render(<ChatContainer />)
    const disclosure = screen.getByTestId('affiliate-disclosure')
    expect(disclosure.textContent).toMatch(/commission/i)
    expect(disclosure.querySelector('a')?.getAttribute('href'))
      .toBe('/affiliate-disclosure')
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/affiliateDisclosure.test.tsx`
Expected: FAIL — `affiliate-disclosure` not found.

- [ ] **Step 3: Add the disclosure**

Render it once, beneath the composer, so it is present on every chat turn:

```tsx
<p
  data-testid="affiliate-disclosure"
  className="px-4 pb-2 text-center text-[11px] leading-relaxed text-[var(--ink-3)]"
>
  We may earn a commission when you buy through our links, at no extra cost to you.{' '}
  <a href="/affiliate-disclosure" className="underline underline-offset-2 hover:text-[var(--terra)]">
    How this works
  </a>
</p>
```

Both lines fill the column at mobile width — no orphan. Verify at 390px after rendering.

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run tests/affiliateDisclosure.test.tsx`
Expected: PASS.

- [ ] **Step 5: Check the other link surfaces**

Confirm a disclosure is reachable from `/results/[id]`, `/saved`, and `/compare` — all
carry affiliate links. Add the same line where missing.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/ChatContainer.tsx frontend/tests/affiliateDisclosure.test.tsx
git commit -m "fix(ui): show affiliate disclosure on chat and other link surfaces"
```

---

### Task 4: Repair the comparison table (v2 — corrected diagnosis)

> **v2 after validation.** v1's "passthrough drop" story was wrong: the backend
> NEVER emits the fields. `product_comparison` returns
> `{"products": product_names, "comparison_table": comparison_html}` from an
> LLM HTML generation (`product_comparison.py:161-166`) — there is no
> `image_url`/`merchant` to drop through any layer. Populating them is a NEW
> capability, not a repair. Also: `overflow-x-auto` ALREADY exists
> (`ComparisonTable.tsx:82`), and the component's props are `{ data, title }`
> with `data.products[i] = { title, price: number, currency, merchant,
> image_url?, ... }` (`:7-30`) — v1's fixture was wrong-shaped in three ways.

**Scope decision:** the frontend component is already capable — it renders
merchant/image/price when given them. The gap is the backend never producing
structured rows. Feed the table from data compose already has (the assembled
offers, post-PLAN-1: elected headline price, merchant, image per product)
instead of teaching `product_comparison`'s LLM call to emit them.

**Files:**
- Modify: `backend/mcp_server/tools/product_compose.py` — build structured
  comparison `data` from assembled offers where the comparison block is emitted
- Create: `frontend/tests/comparisonTable.test.tsx` — characterization + gap
- Test: extend `backend/tests/test_price_resolution.py` (PLAN-1's file — this
  task depends on PLAN-1 Task 4's `_assemble_offers_for_product`)

**Ordering:** after PLAN-1 Tasks 3-4 (needs the deterministic elected offer).

- [ ] **Step 1: Characterize the component with the REAL shape**

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ComparisonTable from '@/components/ComparisonTable'

const data = {
  products: Array.from({ length: 5 }, (_, i) => ({
    title: `Product ${i + 1}`,
    price: 248,
    currency: 'USD',
    merchant: 'Amazon',
    image_url: 'https://img.example/p.jpg',
  })),
  criteria: [],
  summary: '',
}

describe('ComparisonTable', () => {
  it('renders merchant, price, and image when provided', () => {
    render(<ComparisonTable data={data} />)
    expect(screen.queryByText('No Image')).toBeNull()
    expect(screen.queryByText('N/A')).toBeNull()
    expect(screen.getAllByText('Amazon').length).toBeGreaterThan(0)
  })

  it('scrolls inside its own container (already true — pin it)', () => {
    const { container } = render(<ComparisonTable data={data} />)
    expect(container.querySelector('.overflow-x-auto')).toBeTruthy()
  })
})
```

Adapt field names to the real `ComparisonProduct` interface (`:7-18`) before
running. Expected: **both PASS** — this pins that the component works and the
gap is upstream.

- [ ] **Step 2: Write the failing backend test**

In the PLAN-1 compose harness: drive a comparison query end-to-end and assert
the emitted comparison block carries structured `products` with `merchant`,
numeric `price` (matching the card's elected headline), and `image_url` from
the assembled offers — not just LLM HTML.

- [ ] **Step 3: Implement**

Where compose emits the comparison block (find it:
`grep -n "comparison_table\|HOW THEY COMPARE\|comparison" mcp_server/tools/product_compose.py | head`),
attach `data.products` built from each product's `best_offer` (title, elected
price, merchant, image_url, currency). Keep the LLM HTML as the prose/criteria
source if the block consumes both; the structured fields come from offer data
so the table can never disagree with the cards above it.

- [ ] **Step 4: Run both suites, then commit**

```bash
cd backend && python -m pytest tests/test_price_resolution.py -k comparison -v
cd frontend && npx vitest run tests/comparisonTable.test.tsx
git add backend/mcp_server/tools/product_compose.py frontend/tests/comparisonTable.test.tsx
git commit -m "feat(compare): comparison table rows built from assembled offer data"
```

---

### Task 5: Superseded clarifier cards must go inert

**Root cause:** each clarifier card tracks its own `submitted` state
(`Message.tsx:281,300`), so a card from an earlier turn stays clickable after a newer
question has been asked. Clicking a stale chip submits an answer into the current
question's state.

**Files:**
- Modify: `frontend/components/Message.tsx`
- Create: `frontend/tests/staleClarifier.test.tsx`

**Interfaces:**
- Produces: an `isStale` prop on the clarifier card, true when the message is not the
  most recent assistant message

- [ ] **Step 1: Write the failing test (v2 — real props, banner-consistent staleness)**

**Final-validation correction (Kimi):** `Message` has no `onSubmit` and no
`isStale` prop today (`MessageProps` is `{message, isLast?}`), and submission
goes through the `sendSuggestion` CustomEvent — use the `clarifierChips.test.tsx`
harness (mock block + `makeClarifierMessage`) and listen for the event:

```tsx
it('does not submit from a superseded clarifier card', () => {
  const heard: string[] = []
  const listener = (e: Event) => heard.push((e as CustomEvent).detail.question)
  window.addEventListener('sendSuggestion', listener)

  // isStale is the NEW prop this task adds to Message and threads from
  // MessageList — true only when a NEWER CLARIFIER CARD exists (see Step 3).
  render(<Message message={makeClarifierMessage()} isStale {...({} as any)} />)
  fireEvent.click(screen.getByTestId('clarifier-skip-all'))

  expect(heard).toEqual([])
  window.removeEventListener('sendSuggestion', listener)
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/staleClarifier.test.tsx`
Expected: FAIL — `isStale` is not a prop yet, and the card still submits.

- [ ] **Step 3: Implement — staleness = a newer CLARIFIER card exists**

Add `isStale?: boolean` to `MessageProps` and treat it like `submitted` — it
already gates every control in the card (`Message.tsx:281`, `:292`, `:300`):

```tsx
const isLocked = submitted || isStale
```

Replace `!submitted` with `!isLocked` throughout the card, then dim it:

```tsx
<div className={isStale ? 'opacity-50 pointer-events-none' : undefined}>
```

**Derivation (binding — the banner rule, NOT "last assistant message"):** in
`MessageList`, compute the id of the LAST message carrying a clarifier card
(same pattern as `lastAiMessage` at `MessageList.tsx:21`, filtered to messages
with `followups`), and pass `isStale = message-has-followups && message.id !==
lastClarifierId`. "Not the last assistant message" would lock the ask-more
flow's deliberately-still-answerable older card (`clarifier_agent.py:999-1004`)
— an ordinary results message arriving after a card must NOT stale it; only a
newer clarifier card does.

Add the companion test:

```tsx
it('an older clarifier card stays live when only a results message follows', () => {
  // Render via MessageList: [clarifier card, ordinary ai results message].
  // The card must NOT be stale — clicking a chip still fires sendSuggestion.
})
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run tests/staleClarifier.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/Message.tsx frontend/components/MessageList.tsx \
        frontend/tests/staleClarifier.test.tsx
git commit -m "fix(ui): superseded clarifier cards go inert"
```

---

### Task 6: New Chat must not drop the first keystrokes

**Root cause to confirm:** typing immediately after New Chat silently loses the text —
consistent with the composer mounting unfocused, or a remount discarding uncontrolled
input.

- [ ] **Step 1: Reproduce**

Click New Chat and type immediately. Note whether the input has focus and whether the
value appears. Check `ChatInput.tsx` for `autoFocus` and whether `value` is controlled.

- [ ] **Step 2: Write the failing test**

```tsx
it('focuses the composer after New Chat', async () => {
  render(<ChatContainer key="new" />)
  await waitFor(() => {
    expect(document.activeElement).toBe(screen.getByTestId('chat-input'))
  })
})
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/newChatFocus.test.tsx`

- [ ] **Step 4: Fix**

Focus the input on mount and after a new-chat reset:

```tsx
  useEffect(() => {
    inputRef.current?.focus()
  }, [sessionId])
```

If the value is uncontrolled, make it controlled — an uncontrolled input remounting on
session change is the more likely cause and the focus fix alone would not solve it.

- [ ] **Step 5: Run, then commit**

```bash
git add frontend/components/ChatInput.tsx frontend/components/ChatContainer.tsx \
        frontend/tests/newChatFocus.test.tsx
git commit -m "fix(ui): focus the composer after New Chat so early keystrokes land"
```

---

### Task 7: Stop clipping answer text behind the composer

**Root cause to confirm:** the scroll container's bottom padding does not account for the
composer's height, so the last lines sit behind it. `NavLayout.tsx:73` already pads for
the mobile tab bar (`pb-[calc(64px+env(safe-area-inset-bottom))]`); the chat scroller
needs the equivalent for the composer.

- [ ] **Step 1: Reproduce**

Send a long answer and scroll to the bottom on desktop and at 390px. Measure the clipped
height in DevTools.

- [ ] **Step 2: Fix**

Pad the message scroller by the composer's height rather than a guessed constant:

```tsx
<div
  ref={scrollRef}
  className="flex-1 overflow-y-auto"
  style={{ paddingBottom: `calc(${composerHeight}px + 1.5rem + env(safe-area-inset-bottom))` }}
>
```

Measure the composer with a `ResizeObserver` so the padding tracks a multi-line input.
A fixed padding value will clip again the moment the composer grows.

- [ ] **Step 3: Verify**

Confirm the final line of a long answer is fully visible at 1440px and 390px, with the
composer at one line and at three.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/ChatContainer.tsx frontend/components/MessageList.tsx
git commit -m "fix(ui): pad the message scroller by the composer's measured height"
```

---

### Task 8: Rank numerals must not read as letters

**Root cause:** "01" renders ambiguously as "0l" — the display face's zero and the digit
spacing make the pair unreadable. Fonts are DM Sans (UI), Newsreader (body), Instrument
Serif (`.rg-display`).

- [ ] **Step 1: Reproduce**

Screenshot a rank badge at its rendered size. Confirm which font the numeral inherits.

- [ ] **Step 2: Fix**

Force lining tabular figures and a slashed zero where available:

```css
.rg-rank {
  font-variant-numeric: lining-nums tabular-nums slashed-zero;
  font-feature-settings: 'zero' 1, 'tnum' 1, 'lnum' 1;
  letter-spacing: 0.02em;
}
```

Add `.rg-rank` to `app/globals.css` beside the other `rg-*` utilities and apply it to the
rank element. If the display face lacks a slashed zero, drop the leading zero instead and
render `1`, `2`, `3` — legibility beats the editorial flourish.

- [ ] **Step 3: Verify**

Render ranks 01–10 at the real size in both themes and confirm each is unambiguous.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/globals.css frontend/components/Message.tsx
git commit -m "fix(ui): tabular slashed-zero numerals so 01 no longer reads as 0l"
```

---

### Task 9: Verification pass

- [ ] **Step 1: Run the suite**

Run: `cd frontend && npx vitest run`
Expected: no new failures.

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: clean build, no type errors.

- [ ] **Step 3: Walk the eight defects**

With the stack running, confirm each: History opens and lists chats; Regenerate re-sends
or is visibly disabled; the disclosure is on screen; the comparison table shows images,
merchants, and prices and scrolls in-card; stale clarifier cards are dimmed and inert;
typing right after New Chat lands; the last line of a long answer clears the composer;
ranks 01–10 are legible.

- [ ] **Step 4: Commit**

```bash
git commit --allow-empty -m "test: PLAN-7 verified — all eight frontend defects walked"
```
