/**
 * Phase 13 — DISC-01 through DISC-05
 *
 * Behavioral contracts for the Discover screen.
 * Components expected at:
 *   - frontend/app/page.tsx  (DiscoverPage — default export)
 *
 * These tests are in the RED state — they will fail until Plan 02 creates
 * the production components. That is expected and correct.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

// ────────────────────────────────────────────────────────────────
// Module-level router mock (captured before any import of components)
// ────────────────────────────────────────────────────────────────
const mockPush = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}))

// Mock recentSearches lib so DISC-04 tests can control the data.
vi.mock('@/lib/recentSearches', () => ({
  getRecentSearches: vi.fn(() => []),
}))

import { getRecentSearches } from '@/lib/recentSearches'
import DiscoverPage from '@/app/page'

// ────────────────────────────────────────────────────────────────
// DISC-01 — Hero section
// ────────────────────────────────────────────────────────────────
describe('DiscoverPage — hero section (DISC-01)', () => {
  beforeEach(() => {
    mockPush.mockClear()
  })

  it('renders the blueprint greeting in the display (Instrument Serif Italic) face', () => {
    render(<DiscoverPage />)
    // Blueprint Discover greeting: "What are you researching?" in the rg-display face
    const heading = screen.getByRole('heading', { name: /what are you researching\?/i })
    expect(heading).toBeTruthy()
    expect(heading.className).toContain('rg-display')
  })

  it('renders the blueprint subline', () => {
    render(<DiscoverPage />)
    expect(screen.getByText('A category, a budget, a vibe — anything works.')).toBeTruthy()
  })
})

// ────────────────────────────────────────────────────────────────
// DISC-02 — Category chip row
// ────────────────────────────────────────────────────────────────
describe('DiscoverPage — category chip row (DISC-02)', () => {
  beforeEach(() => {
    mockPush.mockClear()
  })

  it('renders at least 8 category chips (Popular, Tech, Travel, Kitchen, Fitness, Home, Fashion, Outdoor)', () => {
    render(<DiscoverPage />)
    // Chips are interactive — rendered as role="button" or role="option" or anchor/link.
    // Count all chip-like interactive elements in the chip row region.
    // Minimum 8 required by DISC-02.
    const chipLabels = ['Popular', 'Tech', 'Travel', 'Kitchen', 'Fitness', 'Home', 'Fashion', 'Outdoor']
    const found = chipLabels.filter(
      (label) => screen.queryByText(label) !== null
    )
    expect(found.length).toBeGreaterThanOrEqual(8)
  })

  it('tapping a category chip calls router.push with /chat?q=...&new=1', () => {
    render(<DiscoverPage />)
    // Find ANY chip that is a button (or has a click handler).
    // We use "Popular" or the first available chip from the expected list.
    const chipLabels = ['Popular', 'Tech', 'Travel', 'Kitchen', 'Fitness', 'Home', 'Fashion', 'Outdoor']
    let chipButton: HTMLElement | null = null
    for (const label of chipLabels) {
      const el = screen.queryByText(label)
      if (el) {
        chipButton = el.closest('button') ?? el.closest('[role="button"]') ?? el as HTMLElement
        break
      }
    }
    expect(chipButton).toBeTruthy()
    fireEvent.click(chipButton!)
    expect(mockPush).toHaveBeenCalledTimes(1)
    const calledUrl: string = mockPush.mock.calls[0][0]
    expect(calledUrl).toMatch(/^\/chat\?q=.+&new=1$/)
  })
})

// ────────────────────────────────────────────────────────────────
// DISC-03 — Trending cards
// ────────────────────────────────────────────────────────────────
describe('DiscoverPage — trending cards (DISC-03)', () => {
  beforeEach(() => {
    mockPush.mockClear()
  })

  it('renders at least 3 trending cards, each with title and subtitle text', () => {
    render(<DiscoverPage />)
    // Trending cards must have a title and a subtitle.
    // They are grouped in a section — query cards by role="article", data-testid, or
    // by their structural pattern (h3/p pairs inside a list or grid).
    const cards =
      document.querySelectorAll('[data-testid="trending-card"]').length > 0
        ? document.querySelectorAll('[data-testid="trending-card"]')
        : document.querySelectorAll('[class*="trending"]')
    // Must have at least 3.
    expect(cards.length).toBeGreaterThanOrEqual(3)
    // Each card must have non-empty text content (title + subtitle).
    Array.from(cards).forEach((card) => {
      expect(card.textContent?.trim().length).toBeGreaterThan(0)
    })
  })

  it('tapping a trending card calls router.push with an encoded query parameter', () => {
    render(<DiscoverPage />)
    const cards =
      document.querySelectorAll('[data-testid="trending-card"]').length > 0
        ? document.querySelectorAll('[data-testid="trending-card"]')
        : document.querySelectorAll('[class*="trending"]')
    expect(cards.length).toBeGreaterThan(0)
    const firstCard = cards[0] as HTMLElement
    // Find the closest clickable element.
    const clickable =
      firstCard.closest('button') ??
      firstCard.querySelector('button') ??
      firstCard
    fireEvent.click(clickable)
    expect(mockPush).toHaveBeenCalledTimes(1)
    const calledUrl: string = mockPush.mock.calls[0][0]
    // URL must contain a query parameter (q=...).
    expect(calledUrl).toContain('q=')
  })
})

// ────────────────────────────────────────────────────────────────
// DISC-04 — "For You" personalisation chip
// ────────────────────────────────────────────────────────────────
describe('DiscoverPage — "For You" chip (DISC-04)', () => {
  beforeEach(() => {
    mockPush.mockClear()
    vi.mocked(getRecentSearches).mockReturnValue([])
  })

  it('does NOT render "For You" chip when localStorage has no recent searches', () => {
    vi.mocked(getRecentSearches).mockReturnValue([])
    render(<DiscoverPage />)
    expect(screen.queryByText('For You')).toBeNull()
  })

  it('renders "For You" chip when localStorage returns at least one recent search', () => {
    vi.mocked(getRecentSearches).mockReturnValue([
      {
        query: 'best headphones',
        productNames: ['Sony WH-1000XM5'],
        category: 'electronics',
        timestamp: Date.now(),
      },
    ])
    render(<DiscoverPage />)
    expect(screen.getByText('For You')).toBeTruthy()
  })
})

// ────────────────────────────────────────────────────────────────
// DISC-05 — Search bar
// ────────────────────────────────────────────────────────────────
describe('DiscoverPage — search bar (DISC-05)', () => {
  beforeEach(() => {
    mockPush.mockClear()
  })

  it('clicking the search bar calls router.push("/chat?new=1")', () => {
    render(<DiscoverPage />)
    // The search bar is a button (not an input) that navigates to chat.
    const searchBar =
      document.querySelector('[data-testid="discover-search-bar"]') ??
      document.querySelector('[aria-label*="search" i]') ??
      document.querySelector('[placeholder*="search" i]')
    expect(searchBar).toBeTruthy()
    fireEvent.click(searchBar as HTMLElement)
    expect(mockPush).toHaveBeenCalledWith('/chat?new=1')
  })

  it('search bar renders as a button element (not input or textarea)', () => {
    render(<DiscoverPage />)
    // The "search bar" on Discover is a decorative button — clicking opens chat.
    // It must NOT be an <input> or <textarea>.
    const searchBar =
      document.querySelector('[data-testid="discover-search-bar"]') ??
      document.querySelector('[aria-label*="search" i]')
    expect(searchBar).toBeTruthy()
    const tagName = (searchBar as HTMLElement).tagName.toLowerCase()
    expect(tagName).not.toBe('input')
    expect(tagName).not.toBe('textarea')
    // Must be a button (or role="button").
    const isButtonLike =
      tagName === 'button' ||
      (searchBar as HTMLElement).getAttribute('role') === 'button'
    expect(isButtonLike).toBe(true)
  })
})
