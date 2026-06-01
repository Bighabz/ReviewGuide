/**
 * E1 — /product/[id] real content. The detail page must render the analysis
 * handed off from a product card (summary, pros/cons, features, buy links) and
 * fall back to an honest note when only basic data is present.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn() }),
}))

import { stashProductDetail, readProductDetail, hasAnalysis, type ProductDetail } from '@/lib/productDetail'
import ProductDetailPage from '@/app/product/[id]/page'

const RICH: ProductDetail = {
  id: 'sony-wh-1000xm5',
  name: 'Sony WH-1000XM5',
  role: 'Top pick · for you',
  rating: '4.7/5',
  summary: 'The class-leading noise cancelling for frequent flyers.',
  imageUrl: 'https://img.example.com/xm5.jpg',
  price: 328,
  url: 'https://buy.example.com/xm5',
  features: ['30h battery', 'Multipoint Bluetooth'],
  pros: [{ description: 'Best-in-class ANC', citations: [{ id: 1, url: 'https://r.com', title: 'Rtings' }] }],
  cons: [{ description: 'No folding hinge' }],
  buyLinks: [{ merchant: 'eBay', price: 328, url: 'https://buy.example.com/xm5' }],
}

beforeEach(() => {
  sessionStorage.clear()
  localStorage.clear()
})

describe('productDetail helpers', () => {
  it('stashes and reads back by matching slug only', () => {
    stashProductDetail(RICH)
    expect(readProductDetail('sony-wh-1000xm5')?.name).toBe('Sony WH-1000XM5')
    expect(readProductDetail('some-other-slug')).toBeNull()
  })

  it('hasAnalysis is true with summary/pros and false for bare payloads', () => {
    expect(hasAnalysis(RICH)).toBe(true)
    expect(hasAnalysis({ id: 'x', name: 'X', price: 10 })).toBe(false)
  })
})

describe('ProductDetailPage', () => {
  it('renders real sections from the handed-off analysis', () => {
    stashProductDetail(RICH)
    render(<ProductDetailPage params={{ id: 'sony-wh-1000xm5' }} />)
    expect(screen.getByRole('heading', { name: 'Sony WH-1000XM5' })).toBeTruthy()
    expect(screen.getByText(/class-leading noise cancelling/i)).toBeTruthy()
    expect(screen.getByText('Best-in-class ANC')).toBeTruthy()
    expect(screen.getByText('No folding hinge')).toBeTruthy()
    expect(screen.getByText('30h battery')).toBeTruthy()
    expect(screen.getByText('What reviewers love')).toBeTruthy()
    expect(screen.getByText('The honest tradeoffs')).toBeTruthy()
    // The honest "no analysis" fallback must NOT show when we have real content.
    expect(screen.queryByText(/generated from a live analysis/i)).toBeNull()
  })

  it('shows the honest fallback when only basic data is present', () => {
    stashProductDetail({ id: 'basic-thing', name: 'Basic Thing', price: 20 })
    render(<ProductDetailPage params={{ id: 'basic-thing' }} />)
    expect(screen.getByRole('heading', { name: 'Basic Thing' })).toBeTruthy()
    expect(screen.getByText(/generated from a live analysis/i)).toBeTruthy()
    expect(screen.getByText(/Get the full breakdown/i)).toBeTruthy()
  })
})
