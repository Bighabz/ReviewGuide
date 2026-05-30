/**
 * Phase 13 — DISC-01, DISC-03, DISC-05
 *
 * Behavioral contracts for the Discover screen.
 * Components expected at:
 *   - frontend/app/page.tsx  (DiscoverPage — default export)
 *
 * (DISC-02 category chips and DISC-04 "For You" chip were removed from the
 * Discover hero — see app/page.tsx.)
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

import DiscoverPage from '@/app/page'
import { HERO_SUBLINES } from '@/components/HeroSubline'

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

  it('renders a rotating hero subline', () => {
    render(<DiscoverPage />)
    // HeroSubline picks one of HERO_SUBLINES (random on mount; SSR/initial = index 0)
    const found = HERO_SUBLINES.some((l) => screen.queryByText(l))
    expect(found).toBe(true)
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
    // URL must seed an editable draft (draft=...), not auto-send (q=...).
    expect(calledUrl).toContain('draft=')
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
