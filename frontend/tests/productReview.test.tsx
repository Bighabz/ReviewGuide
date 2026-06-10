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

describe('ProductReview — offers (Verdict layout)', () => {
  it('renders the best offer as the money row + CTA, the rest as ledger links', () => {
    render(<ProductReview product={makeProduct()} />)

    // Best (lowest-priced) offer leads: $40 eBay price + "via eBay" + CTA link.
    expect(screen.getByText('$40.00')).toBeInTheDocument()
    expect(screen.getByText('via eBay')).toBeInTheDocument()
    // Remaining offer renders as a slim merchant-ledger row.
    expect(screen.getByText('Amazon')).toBeInTheDocument()
    expect(screen.getByText('$99.00')).toBeInTheDocument()
    // One outbound link per offer: the CTA + one ledger row.
    expect(screen.getAllByRole('link')).toHaveLength(2)
  })

  it('shows the "Under budget" badge only on offers flagged below_budget_floor', () => {
    render(<ProductReview product={makeProduct()} />)

    const badges = screen.getAllByTestId('under-budget-badge')
    expect(badges).toHaveLength(1)
    expect(badges[0]).toHaveTextContent('Under budget')

    // The badge belongs to the $40 eBay offer (money row), not the $99 Amazon
    // ledger row.
    const amazonLink = screen.getByText('$99.00').closest('a')
    expect(amazonLink).not.toContainElement(badges[0])
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

  it('renders a "Check price" CTA instead of a zero price', () => {
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

    const cta = screen.getByRole('link')
    expect(cta).toHaveTextContent(/Check price/)
    expect(cta).not.toHaveTextContent('$0')
  })
})

describe('ProductReview - condition badges ($407-class honesty)', () => {
  it('shows the condition label badge on non-new offers', () => {
    const product = makeProduct({
      affiliate_links: [
        {
          product_id: 'ebay-1',
          title: 'eBay - iPhone 15 Pro',
          price: 407.0,
          currency: 'USD',
          affiliate_link: 'https://www.ebay.com/itm/iphone-used',
          merchant: 'eBay',
          condition_label: 'Used',
        },
        {
          product_id: 'amazon-1',
          title: 'Amazon - iPhone 15 Pro',
          price: 999.0,
          currency: 'USD',
          affiliate_link: 'https://www.amazon.com/dp/iphone',
          merchant: 'Amazon',
          condition_label: null,
        },
      ],
    })
    render(<ProductReview product={product} />)

    const badges = screen.getAllByTestId('condition-badge')
    expect(badges).toHaveLength(1)
    expect(badges[0]).toHaveTextContent('Used')

    // The badge belongs to the $407 eBay offer (the lead money row), not the
    // $999 Amazon ledger row.
    expect(screen.getByText('$407.00')).toBeInTheDocument()
    const amazonLink = screen.getByText('$999.00').closest('a')
    expect(amazonLink).not.toContainElement(badges[0])
  })

  it('renders Renewed and Open box labels verbatim', () => {
    const product = makeProduct({
      affiliate_links: [
        {
          product_id: 'ebay-1',
          title: 'eBay - iPhone 15 Pro Refurb',
          price: 450.0,
          currency: 'USD',
          affiliate_link: 'https://www.ebay.com/itm/refurb',
          merchant: 'eBay',
          condition_label: 'Renewed',
        },
        {
          product_id: 'ebay-2',
          title: 'eBay - iPhone 15 Pro Open Box',
          price: 700.0,
          currency: 'USD',
          affiliate_link: 'https://www.ebay.com/itm/openbox',
          merchant: 'Best Buy',
          condition_label: 'Open box',
        },
      ],
    })
    render(<ProductReview product={product} />)

    const badges = screen.getAllByTestId('condition-badge')
    expect(badges.map((b) => b.textContent)).toEqual(['Renewed', 'Open box'])
  })

  it('renders no condition badge when all offers are new', () => {
    render(<ProductReview product={makeProduct()} />)
    expect(screen.queryByTestId('condition-badge')).not.toBeInTheDocument()
  })

  it('condition badge and under-budget badge can coexist on one offer', () => {
    const product = makeProduct({
      affiliate_links: [
        {
          product_id: 'ebay-1',
          title: 'eBay - cheap renewed below budget floor',
          price: 60.0,
          currency: 'USD',
          affiliate_link: 'https://www.ebay.com/itm/cheap-renewed',
          merchant: 'eBay',
          below_budget_floor: true,
          condition_label: 'Renewed',
        },
      ],
    })
    render(<ProductReview product={product} />)

    expect(screen.getByTestId('under-budget-badge')).toBeInTheDocument()
    expect(screen.getByTestId('condition-badge')).toHaveTextContent('Renewed')
  })
})
