/**
 * ProductReview — the rich review card (image-left, pros/cons, "Where to buy").
 *
 * Covers the F2 "Under budget" badge (QA Round 6): offers flagged
 * below_budget_floor by the backend render a badge next to the merchant name;
 * unflagged offers don't. Also covers basic card rendering so regressions in
 * the Where-to-buy list surface here.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ProductReview from '@/components/ProductReview'

function makeProduct(overrides: Record<string, unknown> = {}) {
  return {
    product_name: 'New Balance Fresh Foam 1080v13',
    rating: '4.4/5',
    summary: 'A straightforward daily trainer that nails the fundamentals.',
    image_url: 'https://img.example.com/nb1080.jpg',
    features: ['Best Overall'],
    pros: [{ description: 'Soft, stable ride with a durable outsole.' }],
    cons: [],
    rank: 1,
    affiliate_links: [
      {
        product_id: 'ebay-1',
        title: 'eBay - New Balance Fresh Foam 1080v13',
        price: 40.0,
        currency: 'USD',
        affiliate_link: 'https://www.ebay.com/itm/123',
        merchant: 'eBay',
        below_budget_floor: true,
      },
      {
        product_id: 'amazon-1',
        title: 'Amazon - New Balance Fresh Foam 1080v13',
        price: 99.0,
        currency: 'USD',
        affiliate_link: 'https://www.amazon.com/s?k=nb1080&tag=revguide-20',
        merchant: 'Amazon',
        below_budget_floor: false,
      },
    ],
    ...overrides,
  }
}

describe('ProductReview — Where to buy', () => {
  it('renders one link per offer with merchant and price', () => {
    render(<ProductReview product={makeProduct()} />)

    expect(screen.getByText('Where to buy')).toBeInTheDocument()
    expect(screen.getByText('eBay')).toBeInTheDocument()
    expect(screen.getByText('Amazon')).toBeInTheDocument()
    expect(screen.getByText('USD 40.00')).toBeInTheDocument()
    expect(screen.getByText('USD 99.00')).toBeInTheDocument()
  })

  it('shows the "Under budget" badge only on offers flagged below_budget_floor', () => {
    render(<ProductReview product={makeProduct()} />)

    const badges = screen.getAllByTestId('under-budget-badge')
    expect(badges).toHaveLength(1)
    expect(badges[0]).toHaveTextContent('Under budget')

    // The badge belongs to the $40 eBay offer, not the $99 Amazon one
    const ebayLink = screen.getByText('USD 40.00').closest('a')
    expect(ebayLink).toContainElement(badges[0])
  })

  it('renders no badge when no offer is flagged', () => {
    const product = makeProduct({
      affiliate_links: [
        {
          product_id: 'amazon-1',
          title: 'Amazon - New Balance Fresh Foam 1080v13',
          price: 99.0,
          currency: 'USD',
          affiliate_link: 'https://www.amazon.com/s?k=nb1080&tag=revguide-20',
          merchant: 'Amazon',
        },
      ],
    })
    render(<ProductReview product={product} />)

    expect(screen.queryByTestId('under-budget-badge')).not.toBeInTheDocument()
  })

  it('renders "Check price →" instead of a zero price', () => {
    const product = makeProduct({
      affiliate_links: [
        {
          product_id: 'amazon-1',
          title: 'Amazon - New Balance Fresh Foam 1080v13',
          price: 0,
          currency: 'USD',
          affiliate_link: 'https://www.amazon.com/s?k=nb1080&tag=revguide-20',
          merchant: 'Amazon',
        },
      ],
    })
    render(<ProductReview product={product} />)

    expect(screen.getByText('Check price →')).toBeInTheDocument()
  })
})
