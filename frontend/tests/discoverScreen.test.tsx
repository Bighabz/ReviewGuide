/**
 * Discover screen — behavioral contracts for the FrontPage redesign
 * (2026-06-10): logo masthead + REAL search input, Today's Briefing
 * (lead story + dateline list → /topic/[slug]), and The Index
 * (all categories on the homepage → /browse/[slug]).
 *
 * Component under test: frontend/app/page.tsx → components/home/FrontPage.tsx
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
import { categories } from '@/lib/categoryConfig'

beforeEach(() => {
  mockPush.mockClear()
})

// ────────────────────────────────────────────────────────────────
// Masthead — brand logo + real search input
// ────────────────────────────────────────────────────────────────
describe('DiscoverPage — masthead', () => {
  it('renders the brand logo as the masthead', () => {
    render(<DiscoverPage />)
    expect(screen.getAllByAltText(/reviewguide/i).length).toBeGreaterThan(0)
  })

  it('renders a REAL search input (not a decorative button)', () => {
    render(<DiscoverPage />)
    const input = screen.getByLabelText('Ask a product research question')
    expect(input.tagName.toLowerCase()).toBe('input')
  })

  it('submitting a query routes to a new chat with the query', () => {
    render(<DiscoverPage />)
    const input = screen.getByLabelText('Ask a product research question')
    fireEvent.change(input, { target: { value: 'best espresso machines' } })
    fireEvent.submit(input.closest('form') as HTMLFormElement)
    expect(mockPush).toHaveBeenCalledWith('/chat?q=best%20espresso%20machines&new=1')
  })

  it('submitting empty routes to a fresh chat session', () => {
    render(<DiscoverPage />)
    const input = screen.getByLabelText('Ask a product research question')
    fireEvent.submit(input.closest('form') as HTMLFormElement)
    expect(mockPush).toHaveBeenCalledWith('/chat?new=1')
  })

  it('contains no competitor names in the masthead copy', () => {
    const { container } = render(<DiscoverPage />)
    expect(container.textContent).not.toMatch(/wirecutter|rtings|cnet|tom's guide/i)
  })
})

// ────────────────────────────────────────────────────────────────
// Today's Briefing — lead story + dateline list → /topic/[slug]
// ────────────────────────────────────────────────────────────────
describe('DiscoverPage — Today’s Briefing', () => {
  it('renders the briefing section with a lead story and dateline items', () => {
    render(<DiscoverPage />)
    expect(screen.getByText(/today’s briefing/i)).toBeTruthy()
    // 1 lead + 4 dateline = 5 topic buttons minimum on first paint
    const buttons = screen.getAllByRole('button')
    expect(buttons.length).toBeGreaterThanOrEqual(5)
  })

  it('tapping a briefing story opens its /topic/[slug] landing page (no chat preload)', () => {
    render(<DiscoverPage />)
    // The lead story button carries the topic title as a serif headline.
    const briefingHeader = screen.getByText(/today’s briefing/i)
    const section = briefingHeader.closest('section') as HTMLElement
    const storyButton = section.querySelector('button') as HTMLElement
    fireEvent.click(storyButton)
    expect(mockPush).toHaveBeenCalledTimes(1)
    expect(mockPush.mock.calls[0][0]).toMatch(/^\/topic\//)
  })
})

// ────────────────────────────────────────────────────────────────
// The Index — all categories on the homepage → /browse/[slug]
// ────────────────────────────────────────────────────────────────
describe('DiscoverPage — The Index', () => {
  it('lists every category from categoryConfig', () => {
    render(<DiscoverPage />)
    expect(screen.getByText(/the index/i)).toBeTruthy()
    for (const cat of categories) {
      // getAllByText: a category name can also appear as a briefing kicker
      expect(screen.getAllByText(cat.name).length).toBeGreaterThan(0)
    }
  })

  it('tapping a category routes to its /browse/[slug] page', () => {
    render(<DiscoverPage />)
    const indexHeader = screen.getByText(/the index/i)
    const section = indexHeader.closest('section') as HTMLElement
    fireEvent.click(section.querySelector('button') as HTMLElement)
    expect(mockPush).toHaveBeenCalledWith(`/browse/${categories[0].slug}`)
  })
})
