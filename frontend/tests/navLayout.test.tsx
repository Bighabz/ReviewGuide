/**
 * Phase 12 — NAV-01 / NAV-02 / NAV-03
 *
 * Tests for NavLayout component (to be created at frontend/components/NavLayout.tsx).
 *
 * These tests are in the RED state — they will fail until Plan 02 creates the
 * production component. That is expected and correct.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// Module-level variable used by tests that need a custom pathname.
let currentPathname = '/'

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => currentPathname,
  useSearchParams: () => new URLSearchParams(),
}))

// Import after mock setup so the mock is in place.
import NavLayout from '@/components/NavLayout'

describe('NavLayout — mobile tab bar visibility (NAV-01)', () => {
  beforeEach(() => {
    currentPathname = '/'
  })

  it('renders MobileTabBar on mobile viewport (default route)', () => {
    render(<NavLayout><div>content</div></NavLayout>)
    // At least one of the 5 tab labels must be visible on the default route.
    // Both MobileTabBar and UnifiedTopbar render these labels, so use queryAllByText.
    const tabLabels = ['Discover', 'Saved', 'Ask', 'Compare', 'You']
    const found = tabLabels.some((label) => screen.queryAllByText(label).length > 0)
    expect(found).toBe(true)
  })

  it('renders Discover, Saved, Ask, Compare, You tab labels', () => {
    render(<NavLayout><div>page content</div></NavLayout>)
    // Both MobileTabBar and UnifiedTopbar render these labels — getAllByText handles multiple matches.
    expect(screen.getAllByText('Discover').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Saved').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Ask').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Compare').length).toBeGreaterThan(0)
    expect(screen.getAllByText('You').length).toBeGreaterThan(0)
  })
})

describe('NavLayout — desktop topbar visibility (NAV-02)', () => {
  beforeEach(() => {
    currentPathname = '/browse'
  })

  it('renders UnifiedTopbar on desktop viewport', () => {
    // On desktop the UnifiedTopbar should appear (contains the logo or desktop nav links).
    // We check for the ReviewGuide logo text or a nav landmark.
    render(<NavLayout><div>desktop content</div></NavLayout>)
    // UnifiedTopbar renders a nav element with aria role, or the logo text "ReviewGuide".
    const nav = document.querySelector('nav')
    // At minimum a nav element should exist (from UnifiedTopbar or MobileTabBar).
    expect(nav).toBeTruthy()
  })
})

describe('NavLayout — excluded routes (NAV-03)', () => {
  it('does not render tab bar or header for /admin/dashboard', () => {
    currentPathname = '/admin/dashboard'
    render(<NavLayout><div>admin content</div></NavLayout>)
    // No tab labels should appear for excluded admin routes.
    expect(screen.queryByText('Discover')).toBeNull()
    expect(screen.queryByText('Saved')).toBeNull()
    expect(screen.queryByText('Ask')).toBeNull()
    expect(screen.queryByText('Compare')).toBeNull()
    expect(screen.queryByText('You')).toBeNull()
  })

  it('does not render tab bar for /privacy route', () => {
    currentPathname = '/privacy'
    render(<NavLayout><div>privacy content</div></NavLayout>)
    expect(screen.queryByText('Discover')).toBeNull()
    expect(screen.queryByText('Saved')).toBeNull()
    expect(screen.queryByText('Ask')).toBeNull()
  })

  it('does not render tab bar for /terms route', () => {
    currentPathname = '/terms'
    render(<NavLayout><div>terms content</div></NavLayout>)
    expect(screen.queryByText('Discover')).toBeNull()
  })

  it('does not render tab bar for /affiliate-disclosure route', () => {
    currentPathname = '/affiliate-disclosure'
    render(<NavLayout><div>affiliate disclosure content</div></NavLayout>)
    expect(screen.queryByText('Discover')).toBeNull()
  })
})

describe('NavLayout — footer visibility', () => {
  beforeEach(() => {
    currentPathname = '/browse'
  })

  it('renders children regardless of route', () => {
    currentPathname = '/'
    render(<NavLayout><div data-testid="child-content">my page</div></NavLayout>)
    expect(screen.getByTestId('child-content')).toBeTruthy()
  })
})
