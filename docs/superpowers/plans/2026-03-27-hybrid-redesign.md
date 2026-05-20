# Hybrid Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate ReviewGuide.ai from a chat-centric layout to a hybrid architecture: split-pane desktop (chat sidebar + results main + sources panel), editorial light-mode-first, Figma-matching product cards, 3-tab mobile nav — while preserving v3 streaming, accent picker, and gradient buttons.

**Architecture:** The chat page becomes the split-pane view on desktop (≥1024px). On mobile, chat stays inline with rich product cards injected. A new `ResultsPanel` replaces the right sidebar. The existing `ResultsProductCard` and `extractResultsData` are upgraded to match the Figma's high-density card design. The MobileTabBar drops from 5 tabs to 3.

**Tech Stack:** Next.js 14, React 18, TypeScript, Tailwind CSS, CSS custom properties.

**Design Reference:** `.superpowers/figma-mockup/index.html` — 3-screen flow (Discover → Chat → Results)

---

## File Map

### Task 1 — Desktop Split-Pane Shell
| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `frontend/app/chat/page.tsx` | Restructure to 3-column layout on desktop |
| Create | `frontend/components/ResultsMainPanel.tsx` | Center panel: editorial summary + product grid + sources |
| Create | `frontend/components/ChatSidePanel.tsx` | Left panel: condensed chat thread + input |
| Create | `frontend/components/SourcesPanel.tsx` | Right panel: sources + quick actions |

### Task 2 — Figma ProductCard Component
| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `frontend/components/ResultsProductCard.tsx` | Upgrade to Figma design: gradient image, rank badge, score bar, price footer |

### Task 3 — Homepage: Restore Chips + Improve Trending
| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `frontend/app/page.tsx` | Restore category chips with "For You", keep sidebar, improve layout |
| Modify | `frontend/components/discover/CategoryChipRow.tsx` | Add "For You" chip using localStorage history |

### Task 4 — Mobile Nav: 3 Tabs, No FAB
| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `frontend/components/MobileTabBar.tsx` | Replace 5-tab + FAB with 3-tab (Home, History, Saved) |

### Task 5 — Mobile Chat Header
| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `frontend/components/MobileHeader.tsx` | Add Figma-style topic title, source count, share button |

### Task 6 — Build Verification
| Action | File | Responsibility |
|--------|------|----------------|
| N/A | All modified files | `npm run build`, visual check |

---

## Task 1: Desktop Split-Pane Shell

The biggest architectural change. On desktop (≥1024px), the chat page becomes a 3-column layout:
- **Left (320px):** Condensed chat thread with conversation history + input
- **Center (flex-1):** Results panel with editorial summary, product grid, sources
- **Right:** Hidden for now (sources are in the center panel below the grid — simpler than a 3rd column for MVP)

On mobile (<1024px), the layout stays as-is: full-width chat with inline product cards.

**Files:**
- Modify: `frontend/app/chat/page.tsx`
- Create: `frontend/components/ResultsMainPanel.tsx`

### Step 1: Create ResultsMainPanel component

This component renders the Figma's main results area. It receives the current messages array and extracts products/sources/summary from the latest assistant message.

- [ ] **Create `frontend/components/ResultsMainPanel.tsx`:**

```tsx
'use client'

import { useMemo } from 'react'
import { ArrowUpRight, Bookmark, RefreshCw } from 'lucide-react'
import type { Message } from './ChatContainer'
import ResultsProductCard from './ResultsProductCard'
import { stripMarkdown } from '@/lib/stripMarkdown'

interface ResultsMainPanelProps {
  messages: Message[]
  sessionTitle: string
}

/** Extract products from the latest assistant message's ui_blocks */
function extractProducts(messages: Message[]): any[] {
  // Walk messages in reverse to find the latest with ui_blocks
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i]
    if (msg.role === 'assistant' && msg.ui_blocks) {
      const products: any[] = []
      for (const block of msg.ui_blocks) {
        const type = block.type || ''
        if (type === 'inline_product_card' || type === 'products' || type === 'product_cards') {
          const items = block.data?.products || block.products || (Array.isArray(block.data) ? block.data : [])
          products.push(...items)
        }
      }
      if (products.length > 0) return products
    }
  }
  return []
}

/** Extract sources from the latest assistant message's ui_blocks */
function extractSources(messages: Message[]): any[] {
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i]
    if (msg.role === 'assistant' && msg.ui_blocks) {
      for (const block of msg.ui_blocks) {
        if (block.type === 'review_sources') {
          const data = block.data || {}
          const reviewProducts = data.products || []
          const sources: any[] = []
          for (const p of reviewProducts) {
            for (const s of (p.sources || [])) {
              if (s.url && !sources.find((x: any) => x.url === s.url)) {
                sources.push(s)
              }
            }
          }
          if (sources.length > 0) return sources
        }
      }
    }
  }
  return []
}

/** Extract the editorial summary (first assistant message content) */
function extractSummary(messages: Message[]): string {
  const assistant = messages.find(m => m.role === 'assistant' && m.content)
  return assistant?.content || ''
}

const SOURCE_COLORS = ['#EF4444', '#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899']

export default function ResultsMainPanel({ messages, sessionTitle }: ResultsMainPanelProps) {
  const products = useMemo(() => extractProducts(messages), [messages])
  const sources = useMemo(() => extractSources(messages), [messages])
  const summary = useMemo(() => extractSummary(messages), [messages])

  // Don't render until we have results
  if (products.length === 0 && !summary) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--text-muted)' }}>
        <p className="text-sm">Ask a question to see results here</p>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Top bar */}
      <div
        className="sticky top-0 z-10 flex items-center justify-between px-7 py-4 border-b"
        style={{ borderColor: 'var(--border)', background: 'var(--surface-elevated)' }}
      >
        <h2 className="font-serif text-xl font-normal italic" style={{ color: 'var(--text)' }}>
          {sessionTitle || 'Research Results'}
        </h2>
        <div className="flex gap-2">
          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors hover:bg-[var(--surface-hover)]" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
            <ArrowUpRight size={14} /> Share
          </button>
          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors hover:bg-[var(--surface-hover)]" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
            <Bookmark size={14} /> Save
          </button>
          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors hover:bg-[var(--surface-hover)]" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="px-7 py-6 flex flex-col gap-5">
        {/* Editorial summary */}
        {summary && (
          <p className="text-sm leading-relaxed max-w-[680px]" style={{ color: 'var(--text-secondary)' }}>
            {stripMarkdown(summary).slice(0, 500)}
          </p>
        )}

        {/* Product grid */}
        {products.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {products.slice(0, 6).map((product: any, index: number) => (
              <ResultsProductCard
                key={product.name + index}
                product={{
                  name: product.name || product.title || '',
                  price: product.price || product.best_offer?.price,
                  url: product.url || product.best_offer?.url || product.affiliate_link,
                  image_url: product.image_url || product.best_offer?.image_url,
                  merchant: product.merchant || product.best_offer?.merchant,
                  description: product.description || product.snippet,
                }}
                index={index}
              />
            ))}
          </div>
        )}

        {/* Sources section */}
        {sources.length > 0 && (
          <div className="mt-4">
            <h4
              className="text-[11px] font-semibold uppercase tracking-[1.5px] mb-3"
              style={{ color: 'var(--text-muted)' }}
            >
              Sources Analyzed
            </h4>
            <div className="flex flex-col gap-2">
              {sources.slice(0, 8).map((source: any, idx: number) => (
                <a
                  key={source.url}
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2.5 text-sm hover:underline"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  <span
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{ backgroundColor: SOURCE_COLORS[idx % SOURCE_COLORS.length] }}
                  />
                  <span className="font-medium" style={{ color: 'var(--text)' }}>{source.site_name}</span>
                  {source.title && (
                    <span className="text-xs truncate">— {source.title}</span>
                  )}
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Commit:**
```bash
git add frontend/components/ResultsMainPanel.tsx
git commit -m "feat: ResultsMainPanel — editorial summary, product grid, sources for split-pane"
```

### Step 2: Restructure chat page to split-pane on desktop

- [ ] **Modify `frontend/app/chat/page.tsx`:**

The key change: on desktop (lg+), render a 2-column layout:
- Left: ChatContainer (narrower, acts as sidebar)
- Right: ResultsMainPanel (main stage)

On mobile: keep the current full-width ChatContainer.

Read the file first. The current structure (around lines 130-163) has:
```
flex → CategorySidebar (left) + main (ChatContainer + ConversationSidebar)
```

Replace the main content area with a split-pane that shows ResultsMainPanel on desktop. The ChatContainer needs to expose its `messages` state. Currently it's internal. We'll lift the messages display up by having ChatContainer forward messages to a callback.

Actually, the simpler approach: add a `onMessagesChange` prop to ChatContainer that fires whenever messages update. The parent can use this to feed ResultsMainPanel.

In `frontend/app/chat/page.tsx`, add:
```tsx
import ResultsMainPanel from '@/components/ResultsMainPanel'
```

Add state:
```tsx
const [chatMessages, setChatMessages] = useState<Message[]>([])
```

Pass to ChatContainer:
```tsx
<ChatContainer
  ...existing props
  onMessagesChange={setChatMessages}
/>
```

Then render the split layout. Find the `<main>` wrapper and replace its content for desktop:

```tsx
{/* Desktop: split-pane layout */}
<div className="hidden lg:flex flex-1 overflow-hidden">
  {/* Left: Chat (320px fixed) */}
  <div className="w-[380px] flex-shrink-0 border-r flex flex-col" style={{ borderColor: 'var(--border)' }}>
    <ChatContainer
      clearHistoryTrigger={clearHistoryTrigger}
      externalSessionId={switchToSessionId}
      onSessionChange={handleSessionChange}
      initialQuery={initialQuery}
      onMessagesChange={setChatMessages}
    />
  </div>
  {/* Right: Results (flex-1) */}
  <ResultsMainPanel
    messages={chatMessages}
    sessionTitle={initialQuery || 'Research Results'}
  />
</div>

{/* Mobile: full-width chat (existing behavior) */}
<div className="flex lg:hidden flex-1 flex-col overflow-hidden">
  <ChatContainer
    clearHistoryTrigger={clearHistoryTrigger}
    externalSessionId={switchToSessionId}
    onSessionChange={handleSessionChange}
    initialQuery={initialQuery}
  />
</div>
```

- [ ] **Add `onMessagesChange` prop to ChatContainer:**

In `frontend/components/ChatContainer.tsx`, add to the props interface:
```tsx
onMessagesChange?: (messages: Message[]) => void
```

Then add a useEffect that calls it whenever messages change:
```tsx
useEffect(() => {
  if (onMessagesChange) onMessagesChange(messages)
}, [messages, onMessagesChange])
```

- [ ] **Commit:**
```bash
git add frontend/app/chat/page.tsx frontend/components/ChatContainer.tsx
git commit -m "feat: desktop split-pane layout — chat sidebar left, results main right"
```

---

## Task 2: Figma-Style ProductCard

Upgrade `ResultsProductCard` to match the Figma's high-density design: gradient image area, rank badge, score bar, badge labels (Top Pick / Best Value / Premium), price footer with CTA button.

**Files:**
- Modify: `frontend/components/ResultsProductCard.tsx`

- [ ] **Rewrite `frontend/components/ResultsProductCard.tsx`:**

```tsx
'use client'

import { useState } from 'react'
import { resolveProductImage, isPlaceholderImage } from '@/lib/productImages'
import type { ExtractedProduct } from '@/lib/extractResultsData'

interface ResultsProductCardProps {
  product: ExtractedProduct
  index: number
}

const GRADIENT_BGS = [
  'linear-gradient(135deg, #EEF2FF, #E0E7FF)',
  'linear-gradient(135deg, #FEF3C7, #FDE68A)',
  'linear-gradient(135deg, #F3E8FF, #E9D5FF)',
  'linear-gradient(135deg, #DCFCE7, #BBF7D0)',
  'linear-gradient(135deg, #FFE4E6, #FECDD3)',
  'linear-gradient(135deg, #E0F2FE, #BAE6FD)',
]

const POSITION_SCORES = [94, 91, 88, 82, 78, 74]

function getBadge(index: number): { label: string; bg: string; color: string } {
  if (index === 0) return { label: 'TOP PICK', bg: '#FEF3C7', color: '#92400E' }
  if (index === 1) return { label: 'BEST VALUE', bg: '#DBEAFE', color: '#1E40AF' }
  if (index === 2) return { label: 'PREMIUM', bg: '#F3E8FF', color: '#6B21A8' }
  return { label: `#${index + 1}`, bg: 'var(--surface-elevated)', color: 'var(--text-secondary)' }
}

export default function ResultsProductCard({ product, index }: ResultsProductCardProps) {
  const [imgError, setImgError] = useState(false)
  const imageUrl = resolveProductImage(product.name, imgError ? null : product.image_url)
  const isPlaceholder = isPlaceholderImage(imageUrl)
  const badge = getBadge(index)
  const score = POSITION_SCORES[index] ?? 70
  const gradient = GRADIENT_BGS[index % GRADIENT_BGS.length]
  const linkUrl = product.url || `https://www.amazon.com/s?k=${encodeURIComponent(product.name)}&tag=revguide-20`

  return (
    <div
      className="rounded-2xl border overflow-hidden product-card-hover"
      style={{ background: 'var(--surface-elevated)', borderColor: 'var(--border)' }}
    >
      {/* Image area with gradient background */}
      <div
        className="relative h-[140px] flex items-center justify-center"
        style={{ background: gradient }}
      >
        {/* Rank badge */}
        <div
          className="absolute top-3 left-3 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
          style={{ background: 'var(--text)', color: 'var(--background)' }}
        >
          {index + 1}
        </div>
        {isPlaceholder ? (
          <img src={imageUrl} alt="" className="w-12 h-12 opacity-40" />
        ) : (
          <img
            src={imageUrl}
            alt={product.name}
            className="max-h-[100px] max-w-[140px] object-contain drop-shadow-md"
            onError={() => setImgError(true)}
            loading="lazy"
          />
        )}
      </div>

      {/* Body */}
      <div className="p-4">
        {/* Badge */}
        <span
          className="inline-block px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide mb-2"
          style={{ background: badge.bg, color: badge.color }}
        >
          {badge.label}
        </span>

        <h3 className="text-[15px] font-semibold mb-1" style={{ color: 'var(--text)' }}>
          {product.name}
        </h3>

        {product.description && (
          <p className="text-xs mb-2.5 line-clamp-1" style={{ color: 'var(--text-muted)' }}>
            {product.description}
          </p>
        )}

        {/* Score bar */}
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1 rounded-full" style={{ background: 'var(--surface)' }}>
            <div
              className="h-full rounded-full"
              style={{ width: `${score}%`, background: 'var(--primary)' }}
            />
          </div>
          <span className="text-sm font-bold" style={{ color: 'var(--primary)' }}>
            {(score / 10).toFixed(1)}
          </span>
        </div>
      </div>

      {/* Footer */}
      <div
        className="flex items-center justify-between px-4 py-3 border-t"
        style={{ borderColor: 'var(--border)' }}
      >
        <span className="text-base font-bold" style={{ color: 'var(--text)' }}>
          {product.price ? `$${product.price}` : 'Check Price'}
        </span>
        <a
          href={linkUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-white transition-all hover:brightness-110 active:scale-[0.97]"
          style={{ background: 'var(--primary)' }}
        >
          Check Price
        </a>
      </div>
    </div>
  )
}
```

- [ ] **Commit:**
```bash
git add frontend/components/ResultsProductCard.tsx
git commit -m "feat: Figma-style ProductCard — gradient image, rank badge, score bar, price footer"
```

---

## Task 3: Homepage — Restore Chips + "For You"

Bring back category chips on the homepage (removed in v3) with a "For You" chip powered by localStorage recent searches. Keep the sidebar.

**Files:**
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/components/discover/CategoryChipRow.tsx`

- [ ] **Update CategoryChipRow with "For You" from history:**

In `frontend/components/discover/CategoryChipRow.tsx`, the `FOR_YOU_CHIP` already exists (line 21) and `hasHistory` is already a prop. The component is ready — it just needs to be rendered on the homepage again.

- [ ] **Restore chips on homepage:**

In `frontend/app/page.tsx`, add the import back:
```tsx
import CategoryChipRow from '@/components/discover/CategoryChipRow'
```

Then add the chips section between the hero and trending cards:
```tsx
{/* Category chips */}
<div className="mt-6 max-w-xl mx-auto">
  <CategoryChipRow hasHistory={hasHistory} />
</div>
```

- [ ] **Commit:**
```bash
git add frontend/app/page.tsx frontend/components/discover/CategoryChipRow.tsx
git commit -m "feat: restore category chips on homepage with For You from search history"
```

---

## Task 4: Mobile Nav — 3 Tabs, No FAB

Replace the 5-tab MobileTabBar (Discover, Saved, FAB Ask, Compare, Profile) with a clean 3-tab layout (Home, History, Saved). Kill the floating FAB.

**Files:**
- Modify: `frontend/components/MobileTabBar.tsx`

- [ ] **Read MobileTabBar.tsx to understand the full structure**

- [ ] **Replace the tabs configuration:**

Find the TAB_CONFIG or tab rendering section. Replace the 5 tabs + FAB with 3 simple tabs:

```tsx
const TABS = [
  { label: 'Home', icon: Home, href: '/' },
  { label: 'History', icon: History, href: '/chat' },
  { label: 'Saved', icon: Bookmark, href: '/saved' },
] as const
```

Remove the `nav-fab` floating button entirely. Remove the Compare and Profile tabs. Keep the theme toggle and accent picker in a long-press or settings icon.

The tab rendering should be a simple flex row with 3 equal-width items, each with icon + label, active state based on pathname.

- [ ] **Commit:**
```bash
git add frontend/components/MobileTabBar.tsx
git commit -m "feat: 3-tab mobile nav (Home, History, Saved) — removed FAB and extra tabs"
```

---

## Task 5: Mobile Chat Header

Add the Figma-style topic header to the mobile chat view: back button, topic title, source count.

**Files:**
- Modify: `frontend/components/MobileHeader.tsx`

- [ ] **Read MobileHeader.tsx and enhance it:**

The existing MobileHeader shows on `/chat` and `/results` routes. Enhance it with:
- Topic title from ChatStatusContext (already has `sessionTitle`)
- Source count (new — derive from message data or show "Researching...")
- Share button (right side)

Find the header rendering section and update:

```tsx
{/* Enhanced chat header */}
<div className="flex items-center gap-3 flex-1 min-w-0">
  <div className="flex-1 min-w-0">
    <h3 className="text-sm font-semibold truncate" style={{ color: 'var(--text)' }}>
      {sessionTitle || 'New Research'}
    </h3>
    <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
      Researching
    </p>
  </div>
</div>
```

- [ ] **Commit:**
```bash
git add frontend/components/MobileHeader.tsx
git commit -m "feat: Figma-style mobile chat header — topic title and research status"
```

---

## Task 6: Build Verification

- [ ] **Run build:**
```bash
cd frontend && npm run build
```
Expected: Build succeeds with no TypeScript errors.

- [ ] **Fix any errors.**

- [ ] **Commit if needed:**
```bash
git add -A
git commit -m "fix: address build errors from hybrid redesign"
```

---

## Dependency Graph

```
Task 1 (split-pane shell) → standalone, highest priority
Task 2 (ProductCard) → standalone, used by Task 1's ResultsMainPanel
Task 3 (homepage chips) → standalone
Task 4 (mobile nav) → standalone
Task 5 (mobile header) → standalone
Task 6 (verify) → depends on all above
```

Tasks 1-5 are independent. Task 2 should go before or alongside Task 1 since ResultsMainPanel imports ResultsProductCard. All others can run in any order.

---

## What's Preserved from v3

- Streaming (pulsing dots, cursor, stop button, SSE)
- Accent picker (Ocean, Sunset, Neon, Forest, Berry)
- Gradient buy buttons (on TopPickBlock and ProductCards in chat)
- Dark mode toggle (polished, just not the default)
- Product image fallback chain
- Skeleton shimmer components
- Bug fixes (markdown stripping, bubble width, history tracking)
