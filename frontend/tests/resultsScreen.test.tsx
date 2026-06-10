/**
 * Phase 15 — Results Screen
 *
 * Tests covering:
 *   extractResultsData — data extraction utility (GREEN after Task 1)
 *   RES-01 — Route and data loading
 *   RES-02, RESP-01, RESP-02 — Responsive layout
 *   RES-03, RES-04 — Product cards
 *   RES-05 — Quick actions
 *   RES-06 — Sources section
 *
 * extractResultsData tests are GREEN (utility implemented in Task 1).
 * Component tests (RES-01 through RES-06) are RED — ResultsPage,
 * ResultsProductCard, and ResultsQuickActions do not exist until Plan 02.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

// ── Per-test navigation overrides ─────────────────────────────────────────────
// These variables are set in beforeEach so each describe block can override them.
let currentPathname = '/results/test-session-id'
let currentParams: Record<string, string> = { id: 'test-session-id' }
let mockRouterReplace = vi.fn()
let mockRouterPush = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockRouterPush,
    replace: mockRouterReplace,
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => currentPathname,
  useParams: () => currentParams,
  useSearchParams: () => new URLSearchParams(),
}))

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    span: ({ children, ...props }: any) => <span {...props}>{children}</span>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

vi.mock('lucide-react', () => ({
  ArrowLeft: () => <span data-testid="icon-arrow-left" />,
  Share2: () => <span data-testid="icon-share" />,
  BarChart2: () => <span data-testid="icon-compare" />,
  Download: () => <span data-testid="icon-export" />,
  ExternalLink: () => <span data-testid="icon-external" />,
  Star: () => <span data-testid="icon-star" />,
  BookOpen: () => <span data-testid="icon-bookopen" />,
  ChevronDown: () => <span data-testid="icon-chevron-down" />,
  Bookmark: () => <span data-testid="icon-bookmark" />,
  RefreshCw: () => <span data-testid="icon-refresh" />,
  ShoppingCart: () => <span data-testid="icon-shopping-cart" />,
}))

// ── Shared mock data ────────────────────────────────────────────────────────

const mockProducts = [
  {
    name: 'Sony WH-1000XM5',
    price: 348,
    url: 'https://amazon.com/dp/B09XS7JWHH',
    image_url: 'https://example.com/sony.jpg',
    merchant: 'Amazon',
    description: 'Industry-leading noise cancellation',
  },
  {
    name: 'Bose QC45',
    price: 279,
    url: 'https://amazon.com/dp/B098FKXT8L',
    image_url: 'https://example.com/bose.jpg',
    merchant: 'Amazon',
    description: 'High-fidelity audio with ANC',
  },
  {
    name: 'AirPods Max',
    price: 549,
    url: 'https://amazon.com/dp/B08PZHYWJS',
    image_url: 'https://example.com/airpods.jpg',
    merchant: 'Amazon',
    description: 'Apple premium over-ear headphones',
  },
]

const mockSources = [
  {
    site_name: 'Wirecutter',
    url: 'https://wirecutter.com/reviews/best-noise-canceling-headphones',
    title: 'The Best Noise-Canceling Headphones',
    snippet: 'After 200+ hours of testing...',
  },
  {
    site_name: "Tom's Guide",
    url: 'https://tomsguide.com/best-picks/best-headphones',
    title: 'Best Headphones 2026',
    snippet: 'We tested 50 pairs of headphones...',
  },
  {
    site_name: 'RTINGS',
    url: 'https://rtings.com/headphones/reviews/best',
    title: 'Best Headphones of 2026',
    snippet: 'Our top picks based on objective testing...',
  },
]

const mockMessages = [
  {
    id: 'u1',
    role: 'user',
    content: 'Best noise cancelling headphones',
    timestamp: '2026-01-01',
  },
  {
    id: 'a1',
    role: 'assistant',
    content: 'I researched 5 sources to find the best options.',
    timestamp: '2026-01-01',
    ui_blocks: [
      {
        type: 'inline_product_card',
        data: { products: mockProducts },
      },
      {
        type: 'review_sources',
        data: {
          products: [
            { name: 'Sony WH-1000XM5', sources: [mockSources[0], mockSources[1]] },
            { name: 'Bose QC45', sources: [mockSources[2], mockSources[0]] }, // Wirecutter duplicate
          ],
        },
      },
    ],
  },
]

// ── extractResultsData — GREEN tests (utility implemented in Task 1) ──────────

import extractResultsData from '@/lib/extractResultsData'

describe('extractResultsData — empty messages', () => {
  it('returns default ResultsData when given empty array', () => {
    const result = extractResultsData([])
    expect(result.sessionTitle).toBe('Research Results')
    expect(result.summaryText).toBe('')
    expect(result.products).toEqual([])
    expect(result.sources).toEqual([])
  })
})

describe('extractResultsData — sessionTitle and summaryText', () => {
  it('uses first user message content as sessionTitle', () => {
    const result = extractResultsData(mockMessages as any)
    expect(result.sessionTitle).toBe('Best noise cancelling headphones')
  })

  it('uses first assistant message content as summaryText', () => {
    const result = extractResultsData(mockMessages as any)
    expect(result.summaryText).toBe('I researched 5 sources to find the best options.')
  })

  it('falls back to "Research Results" when no user message', () => {
    const assistantOnly = [
      { id: 'a1', role: 'assistant', content: 'Here are the results.', timestamp: '2026-01-01', ui_blocks: [] },
    ]
    const result = extractResultsData(assistantOnly as any)
    expect(result.sessionTitle).toBe('Research Results')
  })
})

describe('extractResultsData — product extraction', () => {
  it('extracts products from inline_product_card blocks', () => {
    const result = extractResultsData(mockMessages as any)
    expect(result.products).toHaveLength(3)
    expect(result.products[0].name).toBe('Sony WH-1000XM5')
    expect(result.products[1].name).toBe('Bose QC45')
    expect(result.products[2].name).toBe('AirPods Max')
  })

  it('extracted product has name, price, url, image_url fields', () => {
    const result = extractResultsData(mockMessages as any)
    const first = result.products[0]
    expect(first.name).toBe('Sony WH-1000XM5')
    expect(first.price).toBe(348)
    expect(first.url).toContain('amazon.com')
    expect(first.image_url).toContain('sony.jpg')
  })

  it('extracts products from "products" block type', () => {
    const msgs = [
      {
        id: 'u1', role: 'user', content: 'Test query', timestamp: '2026-01-01',
      },
      {
        id: 'a1', role: 'assistant', content: 'Results.', timestamp: '2026-01-01',
        ui_blocks: [
          { type: 'products', data: { products: [{ name: 'Widget Pro', price: 99 }] } },
        ],
      },
    ]
    const result = extractResultsData(msgs as any)
    expect(result.products).toHaveLength(1)
    expect(result.products[0].name).toBe('Widget Pro')
  })

  it('handles blocks where products are at block.products (no .data wrapper)', () => {
    const msgs = [
      {
        id: 'u1', role: 'user', content: 'Test query', timestamp: '2026-01-01',
      },
      {
        id: 'a1', role: 'assistant', content: 'Results.', timestamp: '2026-01-01',
        ui_blocks: [
          { type: 'inline_product_card', products: [{ name: 'Flat Widget', price: 49 }] },
        ],
      },
    ]
    const result = extractResultsData(msgs as any)
    expect(result.products).toHaveLength(1)
    expect(result.products[0].name).toBe('Flat Widget')
  })
})

describe('extractResultsData — review_sources blocks are ignored (tone.md)', () => {
  // tone.md: "No source citations. Synthesize." The backend stopped emitting
  // review_sources blocks (PR #9), but OLD persisted sessions in localStorage
  // can still carry them — they must not resurface as a citation list.
  it('returns no sources even when old persisted messages carry review_sources blocks', () => {
    const result = extractResultsData(mockMessages as any)
    expect(result.sources).toHaveLength(0)
  })
})

// ── Component tests — GREEN after Plan 02 implements the components ──────────

import ResultsPage from '@/app/results/[id]/page'

// ── Mock localStorage with session data for component tests ──────────────────

function setupLocalStorageMock(returnNull = false) {
  const localStorageMock = (window as any).localStorage
  if (returnNull) {
    localStorageMock.getItem.mockReturnValue(null)
  } else {
    localStorageMock.getItem.mockReturnValue(JSON.stringify(mockMessages))
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RES-01: Route and data loading
// ─────────────────────────────────────────────────────────────────────────────

describe('RES-01: Route and data loading', () => {
  beforeEach(() => {
    currentPathname = '/results/test-session-id'
    currentParams = { id: 'test-session-id' }
    mockRouterReplace = vi.fn()
    mockRouterPush = vi.fn()
    setupLocalStorageMock()
  })

  it('renders results page with session title from first user message', () => {
    render(<ResultsPage params={{ id: 'test-session-id' }} />)
    // The session title should be rendered as a heading with font-serif class
    // Blueprint: verdict lede renders in the rg-display (Instrument Serif Italic) face
    const heading = screen.getByRole('heading', { name: 'Best noise cancelling headphones' })
    expect(heading).toBeTruthy()
    const hasDisplayClass =
      heading.className?.includes('rg-display') ||
      heading.closest('[class*="rg-display"]') !== null
    expect(hasDisplayClass).toBe(true)
  })

  it('redirects to / when session not found in localStorage', () => {
    setupLocalStorageMock(true)
    render(<ResultsPage params={{ id: 'nonexistent-id' }} />)
    expect(mockRouterReplace).toHaveBeenCalledWith('/')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// RES-02, RESP-01, RESP-02: Responsive layout
// ─────────────────────────────────────────────────────────────────────────────

describe('RES-02: Responsive layout', () => {
  beforeEach(() => {
    currentPathname = '/results/test-session-id'
    currentParams = { id: 'test-session-id' }
    mockRouterReplace = vi.fn()
    setupLocalStorageMock()
  })

  it('renders THE SHORTLIST as a horizontal peek carousel (blueprint §5.5)', () => {
    const { container } = render(<ResultsPage params={{ id: 'test-session-id' }} />)
    // Blueprint replaces the 3-col grid with a peek carousel: flex + overflow-x + snap
    const carousel =
      container.querySelector('[class*="overflow-x-auto"][class*="snap-x"]') !== null ||
      (container.querySelector('[class*="overflow-x-auto"]') !== null &&
        container.querySelector('[class*="snap"]') !== null)
    expect(carousel).toBe(true)
  })

  it('renders horizontal scroll container on mobile', () => {
    const { container } = render(<ResultsPage params={{ id: 'test-session-id' }} />)
    const hasOverflowX =
      container.querySelector('.overflow-x-auto') !== null ||
      container.querySelector('[class*="overflow-x-auto"]') !== null
    expect(hasOverflowX).toBe(true)
  })

  it('renders a HeaderBrand band with a back control and the context line', () => {
    render(<ResultsPage params={{ id: 'test-session-id' }} />)
    // Blueprint: back is a 28px icon button (aria-label "Back"), title shown in the context line
    const backBtn = screen.getByLabelText('Back')
    expect(backBtn).toBeTruthy()
    // Title appears in the HeaderBrand context line (and the blog lede)
    expect(screen.getAllByText(/Best noise cancelling headphones/).length).toBeGreaterThan(0)
  })

  it('content area has max-width 1200px constraint', () => {
    const { container } = render(<ResultsPage params={{ id: 'test-session-id' }} />)
    const hasMaxWidth =
      container.querySelector('.max-w-\\[1200px\\]') !== null ||
      container.querySelector('[class*="max-w-"]') !== null ||
      (() => {
        const allEls = Array.from(container.querySelectorAll('*'))
        return allEls.some(
          (el) =>
            (el as HTMLElement).style?.maxWidth === '1200px' ||
            (el as HTMLElement).className?.includes('max-w-[1200px]')
        )
      })()
    expect(hasMaxWidth).toBe(true)
  })
})

describe('RESP-01: Mobile horizontal scroll', () => {
  beforeEach(() => {
    setupLocalStorageMock()
  })

  it('mobile product scroll container has snap-x behavior', () => {
    const { container } = render(<ResultsPage params={{ id: 'test-session-id' }} />)
    const hasSnap =
      container.querySelector('.snap-x') !== null ||
      container.querySelector('[class*="snap"]') !== null
    expect(hasSnap).toBe(true)
  })
})

describe('RESP-02: Desktop grid layout', () => {
  beforeEach(() => {
    setupLocalStorageMock()
  })

  it('product list is laid out as a flex carousel row', () => {
    const { container } = render(<ResultsPage params={{ id: 'test-session-id' }} />)
    const hasFlexRow = container.querySelector('[class*="flex"][class*="overflow-x-auto"]') !== null
    expect(hasFlexRow).toBe(true)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// RES-03 + RES-04: Product cards
// ─────────────────────────────────────────────────────────────────────────────

describe('RES-03: Product cards render', () => {
  beforeEach(() => {
    setupLocalStorageMock()
  })

  it('renders product cards with names from extracted data', () => {
    render(<ResultsPage params={{ id: 'test-session-id' }} />)
    expect(screen.getByText('Sony WH-1000XM5')).toBeTruthy()
  })

  it('product card shows a role label (blueprint replaces the score bar)', () => {
    render(<ResultsPage params={{ id: 'test-session-id' }} />)
    // Blueprint card has no score bar; the top pick carries a "Top pick · for you" role label
    expect(screen.getByText('Top pick · for you')).toBeTruthy()
  })

  it('product card shows a Buy CTA linking out', () => {
    render(<ResultsPage params={{ id: 'test-session-id' }} />)
    const ctaLinks = screen.getAllByText('Buy')
    expect(ctaLinks.length).toBeGreaterThan(0)
    const link = ctaLinks[0].closest('a') as HTMLAnchorElement
    const href = link?.href || link?.getAttribute('href') || ''
    expect(href).toContain('amazon')
  })

  it('product card shows price', () => {
    const { container } = render(<ResultsPage params={{ id: 'test-session-id' }} />)
    const allText = container.textContent ?? ''
    expect(allText).toContain('$348')
  })
})

describe('RES-04: Product card rank badges', () => {
  beforeEach(() => {
    setupLocalStorageMock()
  })

  it('top product card carries the "Top pick" role label', () => {
    const { container } = render(<ResultsPage params={{ id: 'test-session-id' }} />)
    const allText = container.textContent ?? ''
    // Blueprint role label (small-caps), not a numeric rank badge
    expect(allText.toLowerCase()).toContain('top pick')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// RES-05: Quick actions
// ─────────────────────────────────────────────────────────────────────────────

describe('RES-05: Quick actions', () => {
  beforeEach(() => {
    setupLocalStorageMock()
    // Mock clipboard
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      writable: true,
      configurable: true,
    })
  })

  it('renders Compare, Export, and Share quick action buttons', () => {
    render(<ResultsPage params={{ id: 'test-session-id' }} />)
    expect(screen.getByText('Compare')).toBeTruthy()
    expect(screen.getByText('Export')).toBeTruthy()
    expect(screen.getByText('Share')).toBeTruthy()
  })

  it('Share button copies URL to clipboard when clicked', async () => {
    render(<ResultsPage params={{ id: 'test-session-id' }} />)
    const shareBtn = screen.getByText('Share')
    fireEvent.click(shareBtn)
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining('results')
    )
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// RES-06: Sources section
// ─────────────────────────────────────────────────────────────────────────────

describe('RES-06: no client-facing citation surface (tone.md)', () => {
  beforeEach(() => {
    setupLocalStorageMock()
  })

  it('never renders competitor review-site names, even from old persisted sessions', () => {
    const { container } = render(<ResultsPage params={{ id: 'test-session-id' }} />)
    expect(container.textContent).not.toMatch(
      /wirecutter|rtings|cnet|tom['’]?s guide|techradar|the verge|engadget|pcmag|soundguys/i
    )
  })

  it('does not render a "Sources analyzed" section', () => {
    render(<ResultsPage params={{ id: 'test-session-id' }} />)
    expect(screen.queryByText(/sources analyzed/i)).toBeNull()
  })
})
