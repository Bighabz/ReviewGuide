/**
 * Phase 14 — Chat Screen: RED tests for CHAT-01, CHAT-03, CHAT-05, CHAT-06
 *
 * Tests covering:
 *   CHAT-01 — Render order: text content → UIBlocks → suggestion chips
 *   CHAT-03 — Status display: statusText shown when isThinking, hidden when not
 *   CHAT-05 — Bubble alignment: user right-aligned with iMessage tail, AI left-aligned with label
 *   CHAT-06 — Chip restyle: pill styling, horizontal scrollable row, outside AI bubble
 *
 * These tests are in the RED state — they define the behavioral contracts that
 * Plan 02/03 must satisfy. They will FAIL until production code is updated.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// ── Module-level mocks (must be before any component imports) ────────────────

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    span: ({ children, ...props }: any) => <span {...props}>{children}</span>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

vi.mock('react-markdown', () => ({
  default: ({ children }: any) => <span data-testid="markdown-content">{children}</span>,
}))

vi.mock('@/lib/normalizeBlocks', () => ({
  normalizeBlocks: (blocks: any[]) => blocks ?? [],
}))

vi.mock('@/components/blocks/BlockRegistry', () => ({
  UIBlocks: ({ blocks }: any) => (
    <div data-testid="ui-blocks-container">
      {blocks?.map((_: any, i: number) => (
        <div key={i} data-testid={`ui-block-${i}`} />
      ))}
    </div>
  ),
}))

vi.mock('@/components/MessageRecoveryUI', () => ({
  default: () => <div data-testid="message-recovery-ui" />,
}))

vi.mock('@/lib/trackAffiliate', () => ({
  trackAffiliate: vi.fn(),
}))

vi.mock('@/lib/utils', () => ({
  formatTimestamp: () => 'just now',
  formatFullTimestamp: () => '2026-01-01 12:00:00',
  SUGGESTION_CLICK_PREFIX: '> ',
}))

vi.mock('lucide-react', () => ({
  User: () => <span data-testid="icon-user" />,
  Copy: () => <span data-testid="icon-copy" />,
  Check: () => <span data-testid="icon-check" />,
  ArrowRight: () => <span data-testid="icon-arrow-right" />,
}))

import Message from '@/components/Message'
import MessageList from '@/components/MessageList'

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeUserMessage(overrides = {}) {
  return {
    id: 'msg-user-1',
    role: 'user' as const,
    content: 'Best wireless headphones under $200?',
    timestamp: Date.now(),
    ...overrides,
  }
}

function makeAssistantMessage(overrides = {}) {
  return {
    id: 'msg-ai-1',
    role: 'assistant' as const,
    content: 'Here are the best wireless headphones.',
    timestamp: Date.now(),
    ...overrides,
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// CHAT-05 — Bubble alignment and label
// ─────────────────────────────────────────────────────────────────────────────

describe('CHAT-05 — Bubble alignment and label', () => {
  it('user message container renders right-aligned (justify-end or items-end)', () => {
    const { container } = render(<Message message={makeUserMessage()} />)
    // The user bubble wrapper should push content to the right side
    const hasRightAlignment =
      container.querySelector('.justify-end') !== null ||
      container.querySelector('.items-end') !== null ||
      container.querySelector('[class*="justify-end"]') !== null ||
      container.querySelector('[class*="items-end"]') !== null
    expect(hasRightAlignment).toBe(true)
  })

  it('user bubble has ink background color (bg-[var(--ink)]) per blueprint §4', () => {
    const { container } = render(<Message message={makeUserMessage()} />)
    const bubbleWithInk = container.querySelector('[class*="bg-[var(--ink)]"]')
    expect(bubbleWithInk).toBeTruthy()
  })

  it('user bubble has blueprint asymmetric corners (rounded-tl-[14px])', () => {
    const { container } = render(<Message message={makeUserMessage()} />)
    // Blueprint user bubble: 14/14/4/14 — top corners 14px, bottom-right squared
    const hasAsymmetricCorners =
      container.querySelector('[class*="rounded-tl-[14px]"]') !== null
    expect(hasAsymmetricCorners).toBe(true)
  })

  it('user bubble has truncated tail corner (rounded-br-[4px] or rounded-tr-md)', () => {
    const { container } = render(<Message message={makeUserMessage()} />)
    const hasTailCorner =
      container.querySelector('[class*="rounded-br-[4px]"]') !== null ||
      container.querySelector('[class*="rounded-tr-md"]') !== null ||
      container.querySelector('[class*="rounded-tr-sm"]') !== null ||
      container.querySelector('[class*="rounded-br-sm"]') !== null
    expect(hasTailCorner).toBe(true)
  })

  it('AI message renders left-aligned (default document flow, no justify-end on main wrapper)', () => {
    const { container } = render(<Message message={makeAssistantMessage()} />)
    // AI messages should be left-aligned — the message container uses mr-auto
    const messageContainer = container.querySelector('#message-container')
    if (messageContainer) {
      const classes = messageContainer.className
      // Should NOT have justify-end at the top-level message container
      // AI content renders left by default
      expect(classes).not.toContain('justify-end')
    } else {
      // Fallback: check that mr-auto is present (left alignment)
      const hasLeftAlign =
        container.querySelector('[class*="mr-auto"]') !== null ||
        container.querySelector('[class*="text-left"]') !== null
      expect(hasLeftAlign).toBe(true)
    }
  })

  it('AI message bubble has the "ReviewGuide" label visible', () => {
    render(<Message message={makeAssistantMessage()} />)
    // The AI bubble must show the "ReviewGuide" label or badge
    const reviewGuideLabel = screen.queryByText(/ReviewGuide/i)
    expect(reviewGuideLabel).toBeTruthy()
  })

  it('AI bubble has a hairline border (border-[var(--line)])', () => {
    const { container } = render(<Message message={makeAssistantMessage()} />)
    const borderEl = container.querySelector('[class*="border-[var(--line)]"]')
    expect(borderEl).toBeTruthy()
  })

  it('AI bubble squares the bottom-left corner (rounded-bl-[4px]) per blueprint 14/14/14/4', () => {
    const { container } = render(<Message message={makeAssistantMessage()} />)
    // Blueprint AI bubble squares the BOTTOM-left (not top-left, which was the pre-blueprint bug)
    const hasFlatBL =
      container.querySelector('[class*="rounded-bl-[4px]"]') !== null
    expect(hasFlatBL).toBe(true)
  })

  it('AI bubble max-width is 85% (via style attribute or max-w class)', () => {
    const { container } = render(<Message message={makeAssistantMessage()} />)
    // Check style attribute for maxWidth: '85%'
    const allEls = Array.from(container.querySelectorAll('*'))
    const hasMaxWidth85 = allEls.some((el) => {
      const style = (el as HTMLElement).style?.maxWidth
      const classes = (el as HTMLElement).className ?? ''
      return (
        style === '85%' ||
        classes.includes('max-w-[85%]') ||
        classes.includes('max-w-[85vw]')
      )
    })
    expect(hasMaxWidth85).toBe(true)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// CHAT-01 — Render order: text → UIBlocks → suggestion chips
// ─────────────────────────────────────────────────────────────────────────────

describe('CHAT-01 — Render order: text content then UIBlocks then suggestion chips', () => {
  it('text content, UIBlocks, and suggestion chips all render for an AI message with all three', () => {
    const message = makeAssistantMessage({
      content: 'Here is a great selection.',
      ui_blocks: [{ type: 'product_cards', data: [] }],
      next_suggestions: [
        { id: 's1', question: 'Tell me more about option A?', category: 'compare' },
      ],
    })
    const { container } = render(<Message message={message} />)

    const textEl = container.querySelector('[data-testid="markdown-content"]')
    const blocksEl = container.querySelector('[data-testid="ui-blocks-container"]')
    const chipsEl = container.querySelector('[data-testid="next-suggestions-container"]')

    expect(textEl).toBeTruthy()
    expect(blocksEl).toBeTruthy()
    expect(chipsEl).toBeTruthy()
  })

  it('text content appears before UIBlocks in DOM order', () => {
    const message = makeAssistantMessage({
      content: 'Here is a great selection.',
      ui_blocks: [{ type: 'product_cards', data: [] }],
      next_suggestions: [
        { id: 's1', question: 'Compare options?', category: 'compare' },
      ],
    })
    const { container } = render(<Message message={message} />)

    const textEl = container.querySelector('[data-testid="markdown-content"]')
    const blocksEl = container.querySelector('[data-testid="ui-blocks-container"]')

    expect(textEl).toBeTruthy()
    expect(blocksEl).toBeTruthy()

    // DOM position check: text must come before blocks
    const position = textEl!.compareDocumentPosition(blocksEl!)
    // Node.DOCUMENT_POSITION_FOLLOWING = 4 means blocksEl follows textEl
    expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('UIBlocks appears before suggestion chips in DOM order', () => {
    const message = makeAssistantMessage({
      content: 'Here is a great selection.',
      ui_blocks: [{ type: 'product_cards', data: [] }],
      next_suggestions: [
        { id: 's1', question: 'Compare options?', category: 'compare' },
      ],
    })
    const { container } = render(<Message message={message} />)

    const blocksEl = container.querySelector('[data-testid="ui-blocks-container"]')
    const chipsEl = container.querySelector('[data-testid="next-suggestions-container"]')

    expect(blocksEl).toBeTruthy()
    expect(chipsEl).toBeTruthy()

    // DOM position check: blocks must come before chips
    const position = blocksEl!.compareDocumentPosition(chipsEl!)
    expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// CHAT-03 — Status display
// ─────────────────────────────────────────────────────────────────────────────

describe('CHAT-03 — Status display', () => {
  it('renders statusText in DOM when isThinking=true and statusText is set', () => {
    const message = makeAssistantMessage({
      content: '',
      isThinking: true,
      statusText: 'Researching 4 sources',
    })
    render(<Message message={message} />)
    expect(screen.getByText('Researching 4 sources')).toBeTruthy()
  })

  it('renders a §10.1 loading phrase when isThinking=true but statusText is empty', () => {
    // B.1: 'Thinking...' fallback removed. The empty-statusText path now
    // shows the first phrase from tone.md §10.1 — "Searching the web…" —
    // and the useRotatingLoadingCopy hook cycles thereafter.
    const message = makeAssistantMessage({
      content: '',
      isThinking: true,
      statusText: '',
    })
    render(<Message message={message} />)
    expect(screen.getByText('Searching the web…')).toBeTruthy()
  })

  it('does NOT render status text when isThinking=false', () => {
    const message = makeAssistantMessage({
      content: 'Done.',
      isThinking: false,
      statusText: 'Researching 4 sources',
    })
    render(<Message message={message} />)
    expect(screen.queryByText('Researching 4 sources')).toBeNull()
  })

  it('does NOT render status text element when message has content and isThinking=false', () => {
    const message = makeAssistantMessage({
      content: 'Here are the results.',
      isThinking: false,
    })
    const { container } = render(<Message message={message} />)
    const statusEl = container.querySelector('.stream-status-text')
    expect(statusEl).toBeNull()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// B.3 — Curious follow-up question as a structurally separate field
// ─────────────────────────────────────────────────────────────────────────────

describe('B.3 — Curious follow-up question rendering', () => {
  it('renders followUpQuestion below body when present', () => {
    const message = makeAssistantMessage({
      content: 'The Bose QC Ultra is the pick for your situation.',
      followUpQuestion: 'Want me to factor in glasses fit too?',
    })
    render(<Message message={message} />)
    expect(screen.getByText('Want me to factor in glasses fit too?')).toBeTruthy()
  })

  it('does NOT render any follow-up element when followUpQuestion is undefined', () => {
    const message = makeAssistantMessage({
      content: 'Here you go.',
    })
    const { container } = render(<Message message={message} />)
    // Sanity: no italic text-secondary span with a paragraph in it.
    // (The render uses italic + text-[var(--text-secondary)]; absence
    // of any "?" italic paragraph proves the block didn't render.)
    const italics = container.querySelectorAll('p.italic')
    for (const p of Array.from(italics)) {
      expect(p.textContent).not.toMatch(/\?$/)
    }
  })

  it('followUpQuestion renders AFTER the UI blocks (carousel) in DOM order', () => {
    const message = makeAssistantMessage({
      content: 'Top pick is the QC Ultra.',
      followUpQuestion: 'Open to a Sonos alternative?',
      ui_blocks: [{ type: 'carousel', data: { items: [] } }],
    })
    const { container } = render(<Message message={message} />)
    const fuEl = screen.getByText('Open to a Sonos alternative?')
    const blocksEl = container.querySelector('[data-testid="ui-blocks-container"]')
    expect(fuEl).toBeTruthy()
    expect(blocksEl).toBeTruthy()
    // Founder request 2026-06-10: the reader sees the recommendation cards
    // first, then the conversational nudge — follow-up sits BELOW the blocks.
    const position = fuEl.compareDocumentPosition(blocksEl!)
    expect(position & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// CHAT-06 — Chip restyle: pill shape, horizontal row, outside AI bubble
// ─────────────────────────────────────────────────────────────────────────────

describe('CHAT-06 — Chip restyle', () => {
  function renderWithChips() {
    const message = makeAssistantMessage({
      content: 'Here are some options.',
      next_suggestions: [
        { id: 's1', question: 'Option A?', category: 'compare' },
        { id: 's2', question: 'Option B?', category: 'clarify' },
      ],
    })
    return render(<Message message={message} />)
  }

  it('suggestion chips are rounded-rect 12px (NOT pill) per blueprint §4/#4', () => {
    const { container } = renderWithChips()
    const chip0 = container.querySelector('[data-testid="suggestion-chip-0"]')
    expect(chip0).toBeTruthy()
    const classes = chip0!.className
    // Blueprint: rounded-rect radius 12, explicitly NOT a pill/capsule
    expect(classes).toContain('rounded-[12px]')
    expect(classes.includes('rounded-full')).toBe(false)
  })

  it('chips have a line2 border (border-[var(--line-2)])', () => {
    const { container } = renderWithChips()
    const chip0 = container.querySelector('[data-testid="suggestion-chip-0"]')
    expect(chip0).toBeTruthy()
    const classes = chip0!.className
    expect(classes).toContain('border-[var(--line-2)]')
  })

  it('chips have ink-colored text and a terra leading dot', () => {
    const { container } = renderWithChips()
    const chip0 = container.querySelector('[data-testid="suggestion-chip-0"]')
    expect(chip0).toBeTruthy()
    const classes = chip0!.className
    expect(classes).toContain('text-[var(--ink)]')
    // 4px terracotta leading dot present
    const dot = chip0!.querySelector('[class*="rounded-full"]')
    expect(dot).toBeTruthy()
  })

  it('chips container is a horizontal scrollable row (flex + overflow-x-auto or flex-row)', () => {
    const { container } = renderWithChips()
    const chipsContainer = container.querySelector('[data-testid="next-suggestions-container"]')
    expect(chipsContainer).toBeTruthy()
    const classes = chipsContainer!.className
    // Must be flex row, not vertical stack
    const isHorizontal =
      classes.includes('flex') &&
      (classes.includes('overflow-x-auto') ||
        classes.includes('flex-row') ||
        classes.includes('flex-nowrap'))
    expect(isHorizontal).toBe(true)
  })

  it('chips render OUTSIDE the AI bubble container (not a descendant of the bubble div)', () => {
    const message = makeAssistantMessage({
      content: 'Here are some options.',
      next_suggestions: [
        { id: 's1', question: 'Option A?', category: 'compare' },
      ],
    })
    const { container } = render(<Message message={message} />)

    // Find the AI bubble element (has the border and rounded corners)
    const bubbleEl = container.querySelector('[class*="rounded-tl-[4px]"]') ||
      container.querySelector('[class*="rounded-xl"][class*="border"]')

    const chipsContainer = container.querySelector('[data-testid="next-suggestions-container"]')
    expect(chipsContainer).toBeTruthy()

    // Chips must NOT be inside the bubble
    if (bubbleEl) {
      const chipsInsideBubble = bubbleEl.querySelector('[data-testid="next-suggestions-container"]')
      expect(chipsInsideBubble).toBeNull()
    }
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// In-chat conversational Results flow — TransitionalBubble, blog card, collapse
// ─────────────────────────────────────────────────────────────────────────────

describe('In-chat Results flow', () => {
  it('renders the TransitionalBubble when transitionalReasoning is present', () => {
    render(
      <Message
        message={makeAssistantMessage({
          transitionalReasoning: '$200 puts the mid-tier on the table — that changes the pick.',
        })}
        isLast
      />
    )
    expect(
      screen.getByText('$200 puts the mid-tier on the table — that changes the pick.')
    ).toBeTruthy()
  })

  it('renders the editorial blog card (THE PICK eyebrow) for product-results turns', () => {
    render(
      <Message
        message={makeAssistantMessage({ ui_blocks: [{ type: 'products', products: [{ name: 'Sony' }] }] })}
        isLast
      />
    )
    expect(screen.getByText('The pick')).toBeTruthy()
  })

  it('does NOT render the blog eyebrow for ordinary (non-product) answers', () => {
    render(<Message message={makeAssistantMessage()} isLast />)
    expect(screen.queryByText('The pick')).toBeNull()
  })

  it('collapses a PRIOR blog (not last) with a "Show the full take" toggle', () => {
    render(
      <Message
        message={makeAssistantMessage({ ui_blocks: [{ type: 'products', products: [{ name: 'Sony' }] }] })}
        isLast={false}
      />
    )
    expect(screen.getByText('Show the full take ↓')).toBeTruthy()
  })

  it('does NOT collapse the live (last) blog', () => {
    render(
      <Message
        message={makeAssistantMessage({ ui_blocks: [{ type: 'products', products: [{ name: 'Sony' }] }] })}
        isLast
      />
    )
    expect(screen.queryByText('Show the full take ↓')).toBeNull()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// CHAT — Message scroller clears the fixed mobile header (header-overlap bug)
// The mobile header is position:fixed h-12 (48px); the scroller must offset its
// top padding AND scroll-padding below md so messages (and scrollIntoView's
// block:'start' landing) are never clipped under it. Desktop (md+) resets.
// ─────────────────────────────────────────────────────────────────────────────

describe('CHAT — MessageList clears the fixed mobile header', () => {
  it('scroll container has the mobile top offset + scroll-padding, reset at md', () => {
    const { container } = render(
      <MessageList messages={[makeUserMessage(), makeAssistantMessage()]} />
    )
    const scroller = container.querySelector('.overflow-y-auto') as HTMLElement
    expect(scroller).toBeTruthy()
    const cls = scroller.className
    // mobile: pushed below the 48px fixed header (48 + 12 gap)
    expect(cls).toContain('pt-[60px]')
    expect(cls).toContain('scroll-pt-[60px]')
    // desktop: in-flow topbar — no extra offset
    expect(cls).toContain('md:pt-6')
    expect(cls).toContain('md:scroll-pt-0')
  })
})
