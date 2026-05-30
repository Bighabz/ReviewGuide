'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { ShoppingCart } from 'lucide-react'
import { HeaderBrand } from '@/components/Brand'
import { getSavedItems, toggleSaved, isSaved, slugifyProduct, type SavedItem } from '@/lib/savedItems'

interface Props {
  params: { id: string }
}

// Resolve the product: prefer a sessionStorage handoff (set when tapping a card),
// fall back to the saved-items store by slug.
function resolveProduct(slug: string): SavedItem | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = sessionStorage.getItem('active_product')
    if (raw) {
      const p = JSON.parse(raw) as SavedItem
      if (p && slugifyProduct(p.name) === slug) return p
    }
  } catch { /* ignore */ }
  return getSavedItems().find((i) => i.id === slug) ?? null
}

export default function ProductDetailPage({ params }: Props) {
  const router = useRouter()
  const [product] = useState<SavedItem | null>(() => resolveProduct(params.id))
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (product) setSaved(isSaved(product.id))
  }, [product])

  if (!product) {
    return (
      <div className="mx-auto w-full max-w-xl px-5 pb-28 pt-2">
        <HeaderBrand back onBack={() => router.back()} />
        <div className="flex flex-col items-center text-center gap-4 mt-24">
          <h1 className="rg-display" style={{ fontSize: 28, lineHeight: '32px', color: 'var(--ink)' }}>
            Open a product from a list.
          </h1>
          <p className="rg-serif" style={{ fontSize: 16, color: 'var(--ink-2)', maxWidth: 320 }}>
            Tap any pick in a result or your saved items to see its full breakdown here.
          </p>
        </div>
      </div>
    )
  }

  const buyHref = product.url || `https://www.amazon.com/s?k=${encodeURIComponent(product.name)}&tag=revguide-20`

  return (
    <div className="mx-auto w-full max-w-xl px-5 pb-28 pt-2">
      <HeaderBrand
        back
        onBack={() => router.back()}
        right={
          <button
            onClick={() => setSaved(toggleSaved(product))}
            aria-label={saved ? 'Remove bookmark' : 'Save'}
            style={{ color: 'var(--terra)' }}
          >
            {/* simple bookmark glyph */}
            <svg width="20" height="20" viewBox="0 0 24 24" fill={saved ? 'var(--terra)' : 'none'} stroke="var(--terra)" strokeWidth="1.8">
              <path d="M6 4h12v16l-6-4-6 4z" strokeLinejoin="round" />
            </svg>
          </button>
        }
      />

      {/* Hero image */}
      <div className="relative w-full rounded-[18px] overflow-hidden mt-2" style={{ height: 320, background: 'var(--paper-alt)' }}>
        {product.imageUrl ? (
          <img src={product.imageUrl} alt={product.name} className="w-full h-full object-contain p-8" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <ShoppingCart size={40} style={{ color: 'var(--ink-3)' }} />
          </div>
        )}
      </div>

      {/* Eyebrow + name */}
      {product.role && <div className="rg-eyebrow rg-eyebrow--terra mt-5">{product.role}</div>}
      <h1 className="rg-serif mt-2" style={{ fontSize: 26, lineHeight: '32px', fontWeight: 600, color: 'var(--ink)' }}>
        {product.name}
      </h1>

      {/* Price + buy */}
      <div className="flex items-center justify-between mt-4">
        {product.price != null && product.price > 0 ? (
          <span className="rg-serif" style={{ fontSize: 24, fontWeight: 600, color: 'var(--ink)' }}>${product.price}</span>
        ) : <span />}
        <a
          href={buyHref}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-pill px-5 py-2.5 text-[14px] font-medium"
          style={{ background: 'var(--ink)', color: 'var(--paper)' }}
        >
          Buy now
        </a>
      </div>

      {/* Deeper sections — honest empty states (rich specs/notes come from a full analysis) */}
      <div className="rg-hairline my-6" />
      <div className="rg-eyebrow">Why it&apos;s your pick</div>
      <p className="rg-serif mt-2" style={{ fontSize: 16, lineHeight: '26px', color: 'var(--ink-2)' }}>
        The full reasoning — what matters after six months, the tradeoff nobody talks about, the honest
        pros and cons — is generated from a live analysis.
      </p>
      <button
        onClick={() => router.push(`/chat?new=1&q=${encodeURIComponent('Tell me more about the ' + product.name)}`)}
        className="rounded-pill px-5 py-2.5 text-[14px] font-medium mt-4"
        style={{ background: 'var(--terra)', color: 'var(--paper)' }}
      >
        Get the full breakdown
      </button>
    </div>
  )
}
