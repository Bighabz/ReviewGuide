/**
 * PLAN-7 T4 (v2, corrected diagnosis) — the frontend table was already
 * capable; the gap was the backend never producing structured rows. These
 * characterization tests pin that ComparisonTable renders merchant, price,
 * and image when given them, and that wide content scrolls in-card.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import ComparisonTable from '@/components/ComparisonTable'

const data = {
  products: Array.from({ length: 5 }, (_, i) => ({
    title: `Product ${i + 1}`,
    price: 248,
    currency: 'USD',
    rating: 4.4,
    review_count: 1200,
    merchant: 'Amazon',
    url: 'https://www.amazon.com/dp/x',
    image_url: 'https://img.example/p.jpg',
  })),
  criteria: [],
  summary: '',
}

describe('ComparisonTable', () => {
  it('renders merchant, price, and image when provided', () => {
    render(<ComparisonTable data={data} />)
    expect(screen.queryByText('No Image')).toBeNull()
    expect(screen.queryByText('N/A')).toBeNull()
    expect(screen.getAllByText('Amazon').length).toBeGreaterThan(0)
  })

  it('scrolls inside its own container (already true — pin it)', () => {
    const { container } = render(<ComparisonTable data={data} />)
    expect(container.querySelector('.overflow-x-auto')).toBeTruthy()
  })
})
