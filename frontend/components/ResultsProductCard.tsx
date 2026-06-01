'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { ShoppingCart, Bookmark } from 'lucide-react'
import { lookupCuratedProduct } from '@/lib/curatedProductLookup'
import type { ExtractedProduct } from '@/lib/extractResultsData'
import { toggleSaved, isSaved, slugifyProduct, type SavedItem } from '@/lib/savedItems'
import { stashProductDetail } from '@/lib/productDetail'

interface ResultsProductCardProps {
  product: ExtractedProduct
  index: number
}

function roleLabel(index: number): string {
  if (index === 0) return 'Top pick · for you'
  if (index === 1) return 'Best value'
  if (index === 2) return 'Premium pick'
  return `Pick #${index + 1}`
}

function ProductImage({ name, imageUrl }: { name: string; imageUrl: string | null }) {
  const [errored, setErrored] = useState(false)
  if (!imageUrl || errored) {
    return (
      <div data-testid="product-image-placeholder" className="w-full h-full flex items-center justify-center">
        <ShoppingCart size={28} style={{ color: 'var(--ink-3)' }} />
      </div>
    )
  }
  return (
    <img src={imageUrl} alt={name} className="w-full h-full object-contain p-4" onError={() => setErrored(true)} />
  )
}

// Bookmark toggle — fill terra when saved, icon pop + expanding terra ring on tap (no toast).
function SaveToggle({ item }: { item: Omit<SavedItem, 'savedAt'> }) {
  const [saved, setSaved] = useState(false)
  const [pulse, setPulse] = useState(0)
  // Sync initial + cross-component saved state from the store
  useEffect(() => {
    setSaved(isSaved(item.id))
    const sync = () => setSaved(isSaved(item.id))
    window.addEventListener('saveditems:changed', sync)
    return () => window.removeEventListener('saveditems:changed', sync)
  }, [item.id])
  return (
    <button
      onClick={(e) => { e.preventDefault(); e.stopPropagation(); setSaved(toggleSaved(item)); setPulse((p) => p + 1) }}
      aria-label={saved ? 'Remove bookmark' : 'Save'}
      className="absolute top-2 right-2 w-8 h-8 rounded-full flex items-center justify-center"
      style={{ background: 'var(--paper-hi)', border: '1px solid var(--line)' }}
    >
      {pulse > 0 && (
        <span
          key={pulse}
          className="rg-ring absolute inset-0 rounded-full"
          style={{ border: '1px solid var(--terra)' }}
        />
      )}
      <Bookmark
        key={`${saved}-${pulse}`}
        size={15}
        strokeWidth={1.8}
        className={pulse > 0 ? 'rg-bookmark-pop' : ''}
        style={{ color: 'var(--terra)', fill: saved ? 'var(--terra)' : 'transparent' }}
      />
    </button>
  )
}

export default function ResultsProductCard({ product, index }: ResultsProductCardProps) {
  const router = useRouter()
  const { imageUrl: curatedImage, affiliateUrl: curatedUrl } = lookupCuratedProduct(product.name)
  const imageUrl = curatedImage || product.image_url || null
  const affiliateUrl = curatedUrl || product.url || null
  const isTop = index === 0
  const slug = slugifyProduct(product.name)

  const ctaHref =
    affiliateUrl ||
    `https://www.amazon.com/s?k=${encodeURIComponent(product.name)}&tag=revguide-20`

  function openDetail() {
    try {
      sessionStorage.setItem('active_product', JSON.stringify({
        id: slug, name: product.name, price: product.price,
        imageUrl: imageUrl ?? undefined, url: ctaHref, role: roleLabel(index),
      }))
      // E1: results cards only carry a short description (no pros/cons), so the
      // detail page shows the summary + buy link and an honest note for the rest.
      stashProductDetail({
        id: slug,
        name: product.name,
        role: roleLabel(index),
        summary: product.description,
        imageUrl: imageUrl ?? undefined,
        price: product.price,
        url: ctaHref,
        buyLinks: ctaHref ? [{ merchant: product.merchant || 'Online', price: product.price, url: ctaHref }] : [],
      })
    } catch { /* ignore */ }
    router.push(`/product/${slug}`)
  }

  return (
    <div
      className="rounded-[14px] overflow-hidden product-card-hover flex flex-col"
      style={{ background: 'var(--paper-hi)', border: '1px solid var(--line)' }}
    >
      {/* Image — top, ~75% of width tall, full bleed */}
      <div className="relative w-full" style={{ height: 180, background: 'var(--paper-alt)' }}>
        <ProductImage name={product.name} imageUrl={imageUrl} />
        <SaveToggle
          item={{
            id: slugifyProduct(product.name),
            name: product.name,
            price: product.price,
            imageUrl: imageUrl ?? undefined,
            url: ctaHref,
            role: roleLabel(index),
          }}
        />
      </div>

      {/* Body */}
      <div className="px-3.5 pt-3 pb-3.5 flex flex-col gap-1.5 flex-1">
        <div
          className="uppercase"
          style={{
            fontSize: 10, fontWeight: 600, letterSpacing: '0.08em',
            color: isTop ? 'var(--terra)' : 'var(--ink-2)',
          }}
        >
          {roleLabel(index)}
        </div>

        <button onClick={openDetail} className="text-left">
          <p className="rg-serif line-clamp-2 hover:underline" style={{ fontSize: 17, lineHeight: '22px', fontWeight: 500, color: 'var(--ink)' }}>
            {product.name}
          </p>
        </button>

        <div className="flex items-baseline justify-between mt-auto pt-1">
          {product.price != null && product.price > 0 ? (
            <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--ink)' }}>${product.price}</span>
          ) : <span />}
          <a
            href={ctaHref}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="text-[12px] font-medium px-3 py-1.5 rounded-pill"
            style={{ background: 'var(--ink)', color: 'var(--paper)' }}
          >
            Buy
          </a>
        </div>
      </div>
    </div>
  )
}
