/**
 * PLAN-7 T3 — the affiliate disclosure must be visible where the links are.
 *
 * An /affiliate-disclosure page exists, but its only link lives in Footer,
 * and NavLayout hides the footer on /chat — the one screen where every
 * Amazon/eBay/Expedia outbound link actually appears.
 */
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
