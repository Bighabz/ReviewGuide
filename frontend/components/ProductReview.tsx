'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { ExternalLink, Star, Bookmark } from 'lucide-react'
import { toggleSaved, isSaved, slugifyProduct, type SavedItem } from '@/lib/savedItems'

// Bookmark toggle — terra fill when saved, pop + ring on tap, no toast.
function SaveToggle({ item }: { item: Omit<SavedItem, 'savedAt'> }) {
  const [saved, setSaved] = useState(false)
  const [pulse, setPulse] = useState(0)
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
      className="relative w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
      style={{ background: 'var(--paper-hi)', border: '1px solid var(--line)' }}
    >
      {pulse > 0 && <span key={pulse} className="rg-ring absolute inset-0 rounded-full" style={{ border: '1px solid var(--terra)' }} />}
      <Bookmark key={`${saved}-${pulse}`} size={15} strokeWidth={1.8} className={pulse > 0 ? 'rg-bookmark-pop' : ''} style={{ color: 'var(--terra)', fill: saved ? 'var(--terra)' : 'transparent' }} />
    </button>
  )
}

const FALLBACK_KEYWORDS: Record<string, string> = {
  headphone: '/images/products/fallback-headphones.webp',
  earbuds: '/images/products/fallback-headphones.webp',
  laptop: '/images/products/fallback-laptop.webp',
  notebook: '/images/products/fallback-laptop.webp',
  vacuum: '/images/products/fallback-kitchen.webp',
  kitchen: '/images/products/fallback-kitchen.webp',
  fitness: '/images/products/fallback-fitness.webp',
  shoe: '/images/products/fallback-fitness.webp',
  running: '/images/products/fallback-fitness.webp',
  car: '/images/products/fallback-car.webp',
  hotel: '/images/products/fallback-hotel.webp',
  flight: '/images/products/fallback-flight.webp',
}

function getFallbackImage(productName: string): string {
  const lower = productName.toLowerCase()
  for (const [keyword, src] of Object.entries(FALLBACK_KEYWORDS)) {
    if (lower.includes(keyword)) return src
  }
  return '/images/products/fallback-default.webp'
}

interface AffiliateLink {
  product_id: string
  title: string
  price: number
  currency: string
  affiliate_link: string
  merchant: string
  image_url?: string
  rating?: number
  review_count?: number
}

interface ProductReviewProps {
  product: {
    product_name: string
    rating: string
    summary: string
    image_url?: string
    features: string[]
    pros: Array<{
      description: string
      source_ids?: number[]
      citations?: Array<{
        id: number
        url: string
        title: string
      }>
    }>
    cons: Array<{
      description: string
      source_ids?: number[]
      citations?: Array<{
        id: number
        url: string
        title: string
      }>
    }>
    affiliate_links: AffiliateLink[]
    rank: number
  }
}

export default function ProductReview({ product }: ProductReviewProps) {
  const {
    product_name,
    rating,
    summary,
    image_url,
    features,
    pros,
    cons,
    affiliate_links,
    rank,
  } = product

  const router = useRouter()
  const slug = slugifyProduct(product_name)
  const roleLabel = rank === 1 ? 'Top pick · for you' : rank ? `Pick #${rank}` : ''
  const firstLink = affiliate_links && affiliate_links[0]

  function openDetail() {
    try {
      sessionStorage.setItem('active_product', JSON.stringify({
        id: slug, name: product_name,
        price: firstLink?.price, imageUrl: image_url, url: firstLink?.affiliate_link,
        role: roleLabel,
      }))
    } catch { /* ignore */ }
    router.push(`/product/${slug}`)
  }

  return (
    <div className="rounded-[14px] p-5 shadow-rg-card" style={{ background: 'var(--paper-hi)', border: '1px solid var(--line)' }}>
      {/* Product Header with Image */}
      <div className="mb-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-shrink-0">
            <img
              src={image_url || getFallbackImage(product_name)}
              alt={product_name}
              className="w-16 h-16 sm:w-24 sm:h-24 object-contain rounded-[10px]"
              style={{ background: 'var(--paper-alt)' }}
              loading="lazy"
            />
          </div>
          <div className="w-full sm:flex-1 sm:min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                {roleLabel && (
                  <div className="uppercase mb-1" style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.08em', color: rank === 1 ? 'var(--terra)' : 'var(--ink-2)' }}>
                    {roleLabel}
                  </div>
                )}
                <button onClick={openDetail} className="text-left">
                  <h3 className="rg-serif hover:underline" style={{ fontSize: 18, lineHeight: '22px', fontWeight: 600, color: 'var(--ink)' }}>{product_name}</h3>
                </button>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {rating && rating !== 'N/A' && rating !== '0/5' && (
                  <div className="flex items-center gap-1" style={{ color: '#C08A2E' }}>
                    <Star size={14} fill="currentColor" />
                    <span className="text-sm font-medium">{rating}</span>
                  </div>
                )}
                <SaveToggle item={{ id: slug, name: product_name, price: firstLink?.price, imageUrl: image_url, url: firstLink?.affiliate_link, role: roleLabel }} />
              </div>
            </div>
            {summary && (
              <p className="rg-serif mt-2" style={{ fontSize: 14, lineHeight: '20px', color: 'var(--ink-2)' }}>{summary}</p>
            )}
          </div>
        </div>
      </div>

      {/* Features */}
      {features && features.length > 0 && (
        <div className="mb-4">
          <h4 className="rg-eyebrow mb-2">What matters here</h4>
          <ul className="list-disc list-inside space-y-1">
            {features.map((feature, idx) => (
              <li key={idx} className="text-sm text-[var(--text-secondary)]">{feature}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Pros and Cons */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        {/* Pros — blueprint HONEST NOTES: + in terra */}
        {pros && pros.length > 0 && (
          <div>
            <h4 className="rg-eyebrow mb-2">The good</h4>
            <ul className="space-y-2">
              {pros.map((pro, idx) => (
                <li key={idx} className="rg-serif flex items-start gap-2" style={{ fontSize: 14, lineHeight: '20px', color: 'var(--ink)' }}>
                  <span className="mt-0.5" style={{ color: 'var(--terra)' }}>+</span>
                  <span>{pro.description}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Cons — blueprint: em-dash in ink2 */}
        {cons && cons.length > 0 && (
          <div>
            <h4 className="rg-eyebrow mb-2">The catch</h4>
            <ul className="space-y-2">
              {cons.map((con, idx) => (
                <li key={idx} className="rg-serif flex items-start gap-2" style={{ fontSize: 14, lineHeight: '20px', color: 'var(--ink-2)' }}>
                  <span className="mt-0.5">&#8212;</span>
                  <span>{con.description}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Affiliate Links */}
      {affiliate_links && affiliate_links.length > 0 && (
        <div className="mt-4 pt-4 border-t border-[var(--border)]">
          <h4 className="rg-eyebrow mb-3">Where to buy</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {affiliate_links.map((link, idx) => (
              <a
                key={idx}
                href={link.affiliate_link}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between p-3 border border-[var(--border)] rounded-lg hover:border-[var(--border-strong)] hover:bg-[var(--surface-hover)] transition-colors group"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-medium text-[var(--text-muted)] uppercase">{link.merchant}</span>
                    {link.rating && (
                      <div className="flex items-center gap-0.5 text-amber-500">
                        <Star size={10} fill="currentColor" />
                        <span className="text-xs">{link.rating}</span>
                      </div>
                    )}
                  </div>
                  <p className="text-sm font-semibold text-[var(--text)] truncate">{link.title}</p>
                  <p className="text-lg font-bold text-[var(--text)] mt-1">
                    {link.price > 0 ? `${link.currency} ${link.price.toFixed(2)}` : 'Check price →'}
                  </p>
                </div>
                <ExternalLink size={16} className="text-[var(--text-muted)] group-hover:text-[var(--text-secondary)] flex-shrink-0 ml-2" />
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
