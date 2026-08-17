/**
 * PLAN-7 T1 — the History button must OPEN the conversation drawer.
 *
 * Root cause: NavLayout's handleHistory called router.push('/chat') and nothing
 * ever set ConversationSidebar open — ten conversations were created during QA
 * and none were reachable. Extended per Habib (2026-08-17): mobile previously
 * had NO history entry point at all, so MobileHeader gets one too.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

let currentPathname = '/chat'

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

import NavLayout from '@/components/NavLayout'

describe('history drawer', () => {
  beforeEach(() => {
    currentPathname = '/chat'
  })

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
    // The close control is mobile-only (lg:hidden) but jsdom applies no media
    // queries, so it is reachable here.
    fireEvent.click(screen.getByLabelText('Close history'))
    expect(screen.queryByLabelText('Close history')).toBeNull()
  })

  it('opens from the mobile header history button on chat routes', () => {
    render(<NavLayout><div /></NavLayout>)
    fireEvent.click(screen.getByTestId('mobile-history-button'))
    expect(screen.getByLabelText('Close history')).toBeTruthy()
  })
})
