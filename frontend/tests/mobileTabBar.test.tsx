/**
 * Phase 12 — NAV-01 (mobile tab bar) + NAV-05 (safe area)
 *
 * Tests for MobileTabBar component (to be created at frontend/components/MobileTabBar.tsx).
 *
 * These tests are in the RED state — they will fail until Plan 02 creates the
 * production component. That is expected and correct.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

// Capture the router.push mock so individual tests can assert against it.
const mockPush = vi.fn()

let currentPathname = '/'

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => currentPathname,
  useSearchParams: () => new URLSearchParams(),
}))

import MobileTabBar from '@/components/MobileTabBar'

describe('MobileTabBar — tab count and labels (NAV-01)', () => {
  beforeEach(() => {
    currentPathname = '/'
    mockPush.mockClear()
  })

  it('renders exactly 5 tab items', () => {
    render(<MobileTabBar />)
    // Each tab is a button — query all buttons and expect 5.
    const buttons = screen.getAllByRole('button')
    expect(buttons).toHaveLength(5)
  })

  it('renders Discover label', () => {
    render(<MobileTabBar />)
    expect(screen.getByText('Discover')).toBeTruthy()
  })

  it('renders Saved label', () => {
    render(<MobileTabBar />)
    expect(screen.getByText('Saved')).toBeTruthy()
  })

  it('renders Ask label', () => {
    render(<MobileTabBar />)
    expect(screen.getByText('Ask')).toBeTruthy()
  })

  it('renders Compare label', () => {
    render(<MobileTabBar />)
    expect(screen.getByText('Compare')).toBeTruthy()
  })

  it('renders You label', () => {
    render(<MobileTabBar />)
    expect(screen.getByText('You')).toBeTruthy()
  })
})

describe('MobileTabBar — FAB navigation (NAV-01)', () => {
  beforeEach(() => {
    currentPathname = '/'
    mockPush.mockClear()
  })

  it('FAB button calls router.push with /chat?new=1 on click', () => {
    render(<MobileTabBar />)
    // The Ask/FAB button is the central raised button.
    const askButton = screen.getByText('Ask').closest('button')
    expect(askButton).toBeTruthy()
    fireEvent.click(askButton!)
    expect(mockPush).toHaveBeenCalledWith('/chat?new=1')
  })

  it('FAB button click does not navigate to any other route', () => {
    render(<MobileTabBar />)
    const askButton = screen.getByText('Ask').closest('button')
    fireEvent.click(askButton!)
    expect(mockPush).toHaveBeenCalledTimes(1)
    const callArg = mockPush.mock.calls[0][0]
    expect(callArg).toBe('/chat?new=1')
  })
})

describe('MobileTabBar — active tab highlighting (NAV-01)', () => {
  it('Discover tab has active styling when pathname is /browse', () => {
    currentPathname = '/browse'
    render(<MobileTabBar />)
    const discoverButton = screen.getByText('Discover').closest('button')
    expect(discoverButton).toBeTruthy()
    // Active tab should have blue color class or aria-selected/aria-current.
    // Accept either aria-current="page" or a CSS class containing "active" / "blue" / "#1B4DFF".
    const isActive =
      discoverButton!.getAttribute('aria-current') === 'page' ||
      discoverButton!.className.includes('active') ||
      discoverButton!.className.includes('blue') ||
      discoverButton!.getAttribute('data-active') === 'true'
    expect(isActive).toBe(true)
  })

  it('Discover tab does NOT have active styling when pathname is /chat', () => {
    currentPathname = '/chat'
    render(<MobileTabBar />)
    const discoverButton = screen.getByText('Discover').closest('button')
    const isActive =
      discoverButton!.getAttribute('aria-current') === 'page' ||
      discoverButton!.getAttribute('data-active') === 'true'
    expect(isActive).toBe(false)
  })
})

describe('MobileTabBar — safe area padding (NAV-05)', () => {
  it('nav element has paddingBottom that includes env(safe-area-inset-bottom)', () => {
    render(<MobileTabBar />)
    // The root nav element should include env(safe-area-inset-bottom) in its inline style.
    const nav = document.querySelector('nav')
    expect(nav).toBeTruthy()
    const pb = nav!.style.paddingBottom
    expect(pb).toContain('env(safe-area-inset-bottom)')
  })
})

describe('MobileTabBar — keyboard hide behavior (NAV-01)', () => {
  let originalVisualViewport: VisualViewport | null

  beforeEach(() => {
    currentPathname = '/'
    originalVisualViewport = window.visualViewport
  })

  afterEach(() => {
    // Restore visualViewport after each test.
    Object.defineProperty(window, 'visualViewport', {
      value: originalVisualViewport,
      writable: true,
      configurable: true,
    })
  })

  it('tab bar is hidden when keyboard is open (viewport height < 75% of innerHeight)', () => {
    // Simulate keyboard open: visualViewport.height is less than 75% of window.innerHeight.
    const resizeListeners: Array<() => void> = []
    const mockViewport = {
      height: window.innerHeight * 0.5, // keyboard open: only 50% visible
      addEventListener: (_event: string, handler: () => void) => {
        resizeListeners.push(handler)
      },
      removeEventListener: vi.fn(),
    }
    Object.defineProperty(window, 'visualViewport', {
      value: mockViewport,
      writable: true,
      configurable: true,
    })

    const { container } = render(<MobileTabBar />)

    // Trigger the resize listener to simulate keyboard appearing.
    act(() => {
      resizeListeners.forEach((handler) => handler())
    })

    // The nav element should be hidden (display:none or aria-hidden or removed from DOM).
    const nav = container.querySelector('nav')
    if (nav) {
      const hidden =
        nav.style.display === 'none' ||
        nav.getAttribute('aria-hidden') === 'true' ||
        nav.getAttribute('data-keyboard-open') === 'true' ||
        nav.className.includes('hidden') ||
        nav.className.includes('translate-y')
      expect(hidden).toBe(true)
    } else {
      // Nav removed from DOM entirely — also valid.
      expect(nav).toBeNull()
    }
  })

  it('tab bar is visible when keyboard is closed (full viewport height)', () => {
    // Normal state: visualViewport.height close to innerHeight.
    const mockViewport = {
      height: window.innerHeight * 0.95,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }
    Object.defineProperty(window, 'visualViewport', {
      value: mockViewport,
      writable: true,
      configurable: true,
    })

    render(<MobileTabBar />)
    // Tab bar should be visible — tab labels should be in the document.
    expect(screen.getByText('Discover')).toBeTruthy()
  })
})
