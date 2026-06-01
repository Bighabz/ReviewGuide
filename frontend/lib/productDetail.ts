'use client'

// E1: richer product-detail handoff. When a product card is tapped we stash the
// full analysis the chat already computed (summary, pros/cons with sources,
// features, buy links) in sessionStorage, so /product/[id] can render real
// sections instead of a hard-coded placeholder — no backend round-trip.

export interface DetailCitation {
  id: number
  url: string
  title: string
}

export interface DetailPoint {
  description: string
  citations?: DetailCitation[]
}

export interface DetailBuyLink {
  merchant: string
  price?: number
  url: string
}

export interface ProductDetail {
  id: string // slug — must match the /product/[id] route param
  name: string
  role?: string
  rating?: string
  summary?: string
  imageUrl?: string
  price?: number
  url?: string
  features?: string[]
  pros?: DetailPoint[]
  cons?: DetailPoint[]
  buyLinks?: DetailBuyLink[]
}

const KEY = 'active_product_detail'

export function stashProductDetail(detail: ProductDetail): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(detail))
  } catch {
    /* sessionStorage unavailable — page falls back to the saved-items store */
  }
}

/** Read the stashed detail, but only if it matches the requested slug. */
export function readProductDetail(slug: string): ProductDetail | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return null
    const detail = JSON.parse(raw) as ProductDetail
    if (detail && detail.id === slug) return detail
  } catch {
    /* ignore */
  }
  return null
}

/** True when the payload carries real analysis (not just name/price/image). */
export function hasAnalysis(d: ProductDetail | null | undefined): boolean {
  if (!d) return false
  return Boolean(
    (d.summary && d.summary.trim()) ||
      (d.pros && d.pros.length) ||
      (d.cons && d.cons.length) ||
      (d.features && d.features.length)
  )
}
