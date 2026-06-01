'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { ShoppingCart, Star, ExternalLink, Check, X } from 'lucide-react'
import { HeaderBrand } from '@/components/Brand'
import { getSavedItems, toggleSaved, isSaved, slugifyProduct, type SavedItem } from '@/lib/savedItems'
import { readProductDetail, hasAnalysis, type ProductDetail, type DetailPoint } from '@/lib/productDetail'

interface Props {
  params: { id: string }
}

// Resolve the product: prefer the rich detail handoff (set when tapping a card),
// then a basic sessionStorage handoff, then the saved-items store by slug.
function resolveProduct(slug: string): ProductDetail | null {
  if (typeof window === 'undefined') return null

  const rich = readProductDetail(slug)
  if (rich) return rich

  try {
    const raw = sessionStorage.getItem('active_product')
    if (raw) {
      const p = JSON.parse(raw) as SavedItem
      if (p && slugifyProduct(p.name) === slug) {
        return { id: p.id, name: p.name, price: p.price, imageUrl: p.imageUrl, url: p.url, role: p.role }
      }
    }
  } catch { /* ignore */ }

  const saved = getSavedItems().find((i) => i.id === slug)
  if (saved) {
    return { id: saved.id, name: saved.name, price: saved.price, imageUrl: saved.imageUrl, url: saved.url, role: saved.role }
  }
  return null
}

function Citations({ point }: { point: DetailPoint }) {
  if (!point.citations || point.citations.length === 0) return null
  return (
    <span className="inline-flex gap-1 ml-1 align-middle">
      {point.citations.slice(0, 3).map((c) => (
        <a
          key={c.id}
          href={c.url}
          target="_blank"
          rel="noopener noreferrer"
          title={c.title}
          className="text-[11px] leading-none px-1 rounded"
          style={{ color: 'var(--terra)', border: '1px solid var(--line)' }}
        >
          {c.id}
        </a>
      ))}
    </span>
  )
}

function PointList({ points, kind }: { points: DetailPoint[]; kind: 'pro' | 'con' }) {
  const color = kind === 'pro' ? '#2b5337' : '#9b3a2d'
  const Icon = kind === 'pro' ? Check : X
  return (
    <ul className="mt-3 space-y-2.5">
      {points.map((p, i) => (
        <li key={i} className="flex gap-2.5">
          <Icon size={16} strokeWidth={2.2} style={{ color, flexShrink: 0, marginTop: 3 }} />
          <span className="rg-serif" style={{ fontSize: 15, lineHeight: '22px', color: 'var(--ink-2)' }}>
            {p.description}
            <Citations point={p} />
          </span>
        </li>
      ))}
    </ul>
  )
}

export default function ProductDetailPage({ params }: Props) {
  const router = useRouter()
  // Mount guard: resolveProduct reads sessionStorage, which is client-only.
  // Reading it during the initial render makes SSR (empty) disagree with the
  // client (populated) → React #418/#423 hydration mismatch. So SSR + first
  // client paint render a stable placeholder, then we resolve after mount.
  const [mounted, setMounted] = useState(false)
  const [product, setProduct] = useState<ProductDetail | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    const resolved = resolveProduct(params.id)
    setProduct(resolved)
    setMounted(true)
    if (resolved) setSaved(isSaved(resolved.id))
  }, [params.id])

  if (!mounted) {
    return (
      <div className="mx-auto w-full max-w-xl px-5 pb-28 pt-2">
        <HeaderBrand back onBack={() => router.back()} />
        <div className="w-full rounded-[18px] mt-2" style={{ height: 320, background: 'var(--paper-alt)' }} />
      </div>
    )
  }

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
  const ratingValue = product.rating && product.rating !== 'N/A' && product.rating !== '0/5' ? product.rating : null
  const analysis = hasAnalysis(product)
  const buyLinks = (product.buyLinks ?? []).filter((l) => l.url)
  const savedItem: Omit<SavedItem, 'savedAt'> = {
    id: product.id, name: product.name, price: product.price, imageUrl: product.imageUrl, url: product.url, role: product.role,
  }

  return (
    <div className="mx-auto w-full max-w-xl px-5 pb-28 pt-2">
      <HeaderBrand
        back
        onBack={() => router.back()}
        right={
          <button
            onClick={() => setSaved(toggleSaved(savedItem))}
            aria-label={saved ? 'Remove bookmark' : 'Save'}
            style={{ color: 'var(--terra)' }}
          >
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

      {/* Eyebrow + name + rating */}
      {product.role && <div className="rg-eyebrow rg-eyebrow--terra mt-5">{product.role}</div>}
      <h1 className="rg-serif mt-2" style={{ fontSize: 26, lineHeight: '32px', fontWeight: 600, color: 'var(--ink)' }}>
        {product.name}
      </h1>
      {ratingValue && (
        <div className="flex items-center gap-1.5 mt-2" style={{ color: '#c08a2e' }}>
          <Star size={16} fill="currentColor" />
          <span className="text-sm font-medium">{ratingValue}</span>
        </div>
      )}

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

      {/* Why it's your pick — real summary when we have it */}
      {product.summary && product.summary.trim() && (
        <>
          <div className="rg-hairline my-6" />
          <div className="rg-eyebrow">Why it&apos;s your pick</div>
          <p className="rg-serif mt-2" style={{ fontSize: 16, lineHeight: '26px', color: 'var(--ink-2)' }}>
            {product.summary}
          </p>
        </>
      )}

      {/* Pros / Cons */}
      {product.pros && product.pros.length > 0 && (
        <>
          <div className="rg-hairline my-6" />
          <div className="rg-eyebrow">What reviewers love</div>
          <PointList points={product.pros} kind="pro" />
        </>
      )}
      {product.cons && product.cons.length > 0 && (
        <>
          <div className="rg-hairline my-6" />
          <div className="rg-eyebrow">The honest tradeoffs</div>
          <PointList points={product.cons} kind="con" />
        </>
      )}

      {/* Key features / specs */}
      {product.features && product.features.length > 0 && (
        <>
          <div className="rg-hairline my-6" />
          <div className="rg-eyebrow">Key features</div>
          <ul className="mt-3 space-y-2">
            {product.features.map((f, i) => (
              <li key={i} className="flex gap-2.5">
                <span style={{ color: 'var(--terra)', marginTop: 7, width: 4, height: 4, borderRadius: 9999, background: 'var(--terra)', flexShrink: 0 }} />
                <span className="rg-serif" style={{ fontSize: 15, lineHeight: '22px', color: 'var(--ink-2)' }}>{f}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {/* Where to buy */}
      {buyLinks.length > 0 && (
        <>
          <div className="rg-hairline my-6" />
          <div className="rg-eyebrow">Where to buy</div>
          <div className="mt-3 space-y-2">
            {buyLinks.map((l, i) => (
              <a
                key={i}
                href={l.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between rounded-[12px] px-4 py-3"
                style={{ background: 'var(--paper-hi)', border: '1px solid var(--line)' }}
              >
                <span className="text-sm font-medium" style={{ color: 'var(--ink)' }}>{l.merchant}</span>
                <span className="flex items-center gap-2">
                  {l.price != null && l.price > 0 && (
                    <span className="rg-serif" style={{ fontSize: 15, fontWeight: 600, color: 'var(--ink)' }}>${l.price}</span>
                  )}
                  <ExternalLink size={15} style={{ color: 'var(--terra)' }} />
                </span>
              </a>
            ))}
          </div>
        </>
      )}

      {/* Honest fallback when we only have a name/price (no analysis flowed in) */}
      {!analysis && (
        <>
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
        </>
      )}
    </div>
  )
}
