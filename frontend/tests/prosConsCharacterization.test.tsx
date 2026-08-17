/**
 * PLAN-3 T4 — characterization: behaviours v1 wrongly planned to build.
 *
 * Empty-cons hiding already works (ForAgainst, VerdictCard.tsx): pin it so
 * PLAN-1/PLAN-8's compose edits can't regress the card rendering contract.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ProductReview from '@/components/ProductReview'

function makeProduct(overrides: Record<string, unknown> = {}) {
  return {
    product_name: 'Breville Barista Express',
    rating: '4.3/5',
    summary: 'The all-in-one pick for first espresso setups.',
    image_url: 'https://img.example.com/breville.jpg',
    features: ['Best Overall'],
    pros: [{ description: 'Built-in burr grinder', citations: [] }],
    cons: [],
    rank: 1,
    affiliate_links: [
      {
        product_id: 'amazon-1',
        title: 'Amazon - Breville Barista Express',
        price: 599.0,
        currency: 'USD',
        affiliate_link: 'https://www.amazon.com/dp/x?tag=revguide-20',
        merchant: 'Amazon',
      },
    ],
    ...overrides,
  }
}

describe('ProductReview pros/cons (characterization)', () => {
  it('renders no "The catch" heading when cons are empty', () => {
    render(<ProductReview product={makeProduct({ cons: [] })} />)
    expect(screen.getByText('The good')).toBeInTheDocument()
    expect(screen.queryByText('The catch')).toBeNull()
  })

  it('renders the cons text when cons are present', () => {
    render(
      <ProductReview
        product={makeProduct({
          cons: [{ description: 'Struggles at very fine espresso grind', citations: [] }],
        })}
      />
    )
    expect(screen.getByText('The catch')).toBeInTheDocument()
    expect(screen.getByText('Struggles at very fine espresso grind')).toBeInTheDocument()
  })

  it('renders neither column when both lists are empty', () => {
    render(<ProductReview product={makeProduct({ pros: [], cons: [] })} />)
    expect(screen.queryByText('The good')).toBeNull()
    expect(screen.queryByText('The catch')).toBeNull()
  })
})
