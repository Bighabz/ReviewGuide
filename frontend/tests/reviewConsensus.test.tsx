/**
 * ReviewConsensus — the "How They Compare" block.
 *
 * Covers: rendering per-product rows (name, rating, review count, consensus),
 * review-count formatting, star clamping for broken >5 ratings, the
 * no-source-citations rule (no external links), and the empty-state null render.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ReviewConsensus from '@/components/ReviewConsensus'

const TWO_PRODUCTS = {
  products: [
    {
      name: 'Sony WH-1000XM5',
      avg_rating: 4.7,
      total_reviews: 12500,
      consensus: 'Reviewers consistently praise the class-leading noise cancellation.',
      rank: 1,
    },
    {
      name: 'Bose QuietComfort 45',
      avg_rating: 4.5,
      total_reviews: 840,
      consensus: 'A comfortable, dependable pick with slightly warmer sound.',
      rank: 2,
    },
  ],
}

describe('ReviewConsensus', () => {
  it('renders a row per product with name and consensus text', () => {
    render(<ReviewConsensus data={TWO_PRODUCTS} />)

    expect(screen.getByText('Sony WH-1000XM5')).toBeInTheDocument()
    expect(screen.getByText('Bose QuietComfort 45')).toBeInTheDocument()
    expect(
      screen.getByText('Reviewers consistently praise the class-leading noise cancellation.')
    ).toBeInTheDocument()
  })

  it('renders the default section title and accepts an override', () => {
    const { rerender } = render(<ReviewConsensus data={TWO_PRODUCTS} />)
    expect(screen.getByText('How They Compare')).toBeInTheDocument()

    rerender(<ReviewConsensus data={TWO_PRODUCTS} title="The Contenders" />)
    expect(screen.getByText('The Contenders')).toBeInTheDocument()
    expect(screen.queryByText('How They Compare')).not.toBeInTheDocument()
  })

  it('formats review counts: thousands get a K suffix, small counts stay numeric', () => {
    render(<ReviewConsensus data={TWO_PRODUCTS} />)

    expect(screen.getByText('12.5K reviews')).toBeInTheDocument()
    expect(screen.getByText('840 reviews')).toBeInTheDocument()
  })

  it('renders star ratings with accessible labels', () => {
    render(<ReviewConsensus data={TWO_PRODUCTS} />)

    expect(screen.getByRole('img', { name: 'Rated 4.7 out of 5' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Rated 4.5 out of 5' })).toBeInTheDocument()
  })

  it('clamps broken >5 ratings to the 5-star scale', () => {
    render(
      <ReviewConsensus
        data={{
          products: [
            { name: 'Broken Bundle', avg_rating: 6.8, total_reviews: 10, consensus: 'Text.', rank: 1 },
          ],
        }}
      />
    )

    // Displayed numeric and aria label are clamped — never "6.8 out of 5"
    expect(screen.getByText('5.0')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Rated 5 out of 5' })).toBeInTheDocument()
    expect(screen.queryByText('6.8')).not.toBeInTheDocument()
  })

  it('contains no links — tone.md: synthesis only, no source citations', () => {
    const { container } = render(<ReviewConsensus data={TWO_PRODUCTS} />)

    expect(container.querySelectorAll('a')).toHaveLength(0)
  })

  it('skips products with empty consensus and renders nothing when none remain', () => {
    const { container } = render(
      <ReviewConsensus
        data={{
          products: [
            { name: 'No Consensus Product', avg_rating: 4.0, total_reviews: 5, consensus: '', rank: 1 },
          ],
        }}
      />
    )

    expect(container.firstChild).toBeNull()
  })

  it('renders nothing for missing/empty data', () => {
    const { container } = render(<ReviewConsensus data={{ products: [] }} />)
    expect(container.firstChild).toBeNull()
  })

  it('shows the "Editor\'s pick" badge only on the product flagged editors_pick', () => {
    render(
      <ReviewConsensus
        data={{
          products: [
            {
              name: 'Shark AI Ultra',
              avg_rating: 4.4,
              total_reviews: 900,
              consensus: 'The prose pick — pinned to rank 1 by the backend.',
              rank: 1,
              editors_pick: true,
            },
            {
              name: 'Roomba j7+',
              avg_rating: 4.6,
              total_reviews: 2100,
              consensus: 'The review-score leader, ranked 2 here.',
              rank: 2,
            },
          ],
        }}
      />
    )

    const badges = screen.getAllByTestId('editors-pick-badge')
    expect(badges).toHaveLength(1)
    expect(badges[0]).toHaveTextContent("Editor's pick")
    // The badge sits in the same article row as the pinned product
    expect(badges[0].closest('article')).toHaveTextContent('Shark AI Ultra')
  })

  it('renders no badge when no product is flagged', () => {
    render(<ReviewConsensus data={TWO_PRODUCTS} />)
    expect(screen.queryByTestId('editors-pick-badge')).not.toBeInTheDocument()
  })
})
