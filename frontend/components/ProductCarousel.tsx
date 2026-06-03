'use client'

import { useState, useEffect } from 'react'
import { ChevronLeft, ChevronRight, Star, Bookmark } from 'lucide-react'
import FunPlaceholder from './ui/FunPlaceholder'
import { motion } from 'framer-motion'
import { trackAffiliateClick } from '@/lib/trackAffiliate'
import { toggleSaved, isSaved, slugifyProduct, type SavedItem } from '@/lib/savedItems'

// Bookmark toggle — fill terra when saved, icon pop + expanding terra ring on tap (no toast).
// Lives inside the card's <a>, so it stops propagation to avoid following the affiliate link.
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
      className="absolute top-1 right-1 z-10 w-10 h-10 rounded-full flex items-center justify-center"
      style={{ background: 'var(--paper-hi)', border: '1px solid var(--line)' }}
    >
      {pulse > 0 && (
        <span key={pulse} className="rg-ring absolute inset-0 rounded-full" style={{ border: '1px solid var(--terra)' }} />
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

interface Product {
  product_id: string
  title: string
  price?: number
  currency: string
  affiliate_link: string
  merchant: string
  image_url?: string
  rating?: number
  review_count?: number
  description?: string
  best_price?: boolean
  savings?: number
  compared_retailer?: string
}

interface ProductCarouselProps {
  items: Product[]
  title?: string
}

function StarRatingInline({ value, size = 12 }: { value: number; size?: number }) {
  const fullStars = Math.floor(value)
  const hasHalf = value - fullStars >= 0.5
  const emptyStars = 5 - fullStars - (hasHalf ? 1 : 0)

  return (
    <div className="flex items-center gap-px">
      {Array.from({ length: fullStars }).map((_, i) => (
        <Star key={`full-${i}`} size={size} fill="#E5A100" stroke="#E5A100" strokeWidth={0} />
      ))}
      {hasHalf && (
        <div className="relative" style={{ width: size, height: size }}>
          <Star size={size} fill="none" stroke="#D6D3CD" strokeWidth={1.5} />
          <div className="absolute inset-0 overflow-hidden" style={{ width: '50%' }}>
            <Star size={size} fill="#E5A100" stroke="#E5A100" strokeWidth={0} />
          </div>
        </div>
      )}
      {Array.from({ length: emptyStars }).map((_, i) => (
        <Star key={`empty-${i}`} size={size} fill="none" stroke="#D6D3CD" strokeWidth={1.5} />
      ))}
    </div>
  )
}

function ProductImage({ item }: { item: Product }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  if (!item.image_url || error) {
    return (
      <div className="aspect-square overflow-hidden bg-[var(--surface)]">
        <FunPlaceholder productId={item.product_id || item.title} className="w-full h-full" />
      </div>
    )
  }

  return (
    <div className="aspect-square overflow-hidden bg-[var(--surface)] relative">
      {loading && (
        <div className="absolute inset-0 z-10">
          <FunPlaceholder productId={item.product_id || item.title} className="w-full h-full" />
        </div>
      )}
      <img
        src={item.image_url}
        alt={item.title}
        loading="lazy"
        className={`w-full h-full object-cover group-hover:scale-105 transition-all duration-300 ${loading ? 'opacity-0' : 'opacity-100'}`}
        onLoad={() => setLoading(false)}
        onError={() => { setError(true); setLoading(false) }}
      />
    </div>
  )
}

export default function ProductCarousel({ items, title }: ProductCarouselProps) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [itemsPerPage, setItemsPerPage] = useState(3)

  if (!items || items.length === 0) return null

  useEffect(() => {
    const updateItemsPerPage = () => {
      if (window.innerWidth < 640) setItemsPerPage(1)
      else if (window.innerWidth < 1024) setItemsPerPage(2)
      else setItemsPerPage(3)
    }
    updateItemsPerPage()
    window.addEventListener('resize', updateItemsPerPage)
    return () => window.removeEventListener('resize', updateItemsPerPage)
  }, [])

  const handlePrev = () => {
    setCurrentIndex((prev) => (prev === 0 ? items.length - 1 : prev - 1))
  }

  const handleNext = () => {
    setCurrentIndex((prev) => (prev === items.length - 1 ? 0 : prev + 1))
  }

  const visibleItems = items.slice(currentIndex, currentIndex + itemsPerPage)
  if (visibleItems.length < itemsPerPage && items.length >= itemsPerPage) {
    visibleItems.push(...items.slice(0, itemsPerPage - visibleItems.length))
  }

  return (
    <div className="w-full mb-6">
      {/* Section Title */}
      {title && (
        <div className="flex items-center gap-3 mb-4">
          <h3 className="font-serif text-lg sm:text-xl text-[var(--text)]">{title}</h3>
          <div className="flex-1 h-px bg-[var(--border)]" />
        </div>
      )}

      <div className="relative">
        {/* Navigation Arrows */}
        {items.length > itemsPerPage && (
          <>
            <button
              onClick={handlePrev}
              className="absolute -left-3 top-1/2 -translate-y-1/2 z-10 w-9 h-9 rounded-full bg-[var(--surface-elevated)] border border-[var(--border)] shadow-card flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text)] hover:shadow-card-hover transition-all"
              aria-label="Previous"
            >
              <ChevronLeft size={18} />
            </button>
            <button
              onClick={handleNext}
              className="absolute -right-3 top-1/2 -translate-y-1/2 z-10 w-9 h-9 rounded-full bg-[var(--surface-elevated)] border border-[var(--border)] shadow-card flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text)] hover:shadow-card-hover transition-all"
              aria-label="Next"
            >
              <ChevronRight size={18} />
            </button>
          </>
        )}

        {/* Product Grid */}
        <div className="flex gap-4 overflow-hidden px-1">
          {visibleItems.map((item, idx) => (
            <motion.div
              key={`${item.product_id}-${idx}`}
              className="flex-1 min-w-0"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: idx * 0.05 }}
            >
              <a
                href={item.affiliate_link}
                target="_blank"
                rel="noopener noreferrer"
                className="block group"
                onClick={(e) => {
                  e.preventDefault()
                  trackAffiliateClick({
                    provider: item.merchant || 'unknown',
                    product_name: item.title,
                    url: item.affiliate_link,
                  })
                }}
              >
                <div
                  className="rounded-[14px] overflow-hidden product-card-hover"
                  style={{ background: 'var(--paper-hi)', border: '1px solid var(--line)' }}
                >
                  {/* Image (top) + floating terra save toggle */}
                  <div className="relative">
                    <ProductImage item={item} />
                    <SaveToggle
                      item={{
                        id: slugifyProduct(item.title),
                        name: item.title,
                        price: item.price,
                        imageUrl: item.image_url,
                        url: item.affiliate_link,
                        role: item.best_price ? 'Best price' : item.merchant,
                      }}
                    />
                  </div>

                  {/* Content */}
                  <div className="px-3.5 pt-3 pb-3.5 flex flex-col gap-1.5">
                    {/* Role label (small-caps) — terra for the best-price pick */}
                    <span
                      className="uppercase"
                      style={{
                        fontSize: 10, fontWeight: 600, letterSpacing: '0.08em',
                        color: item.best_price ? 'var(--terra)' : 'var(--ink-2)',
                      }}
                    >
                      {item.best_price ? 'Best price · ' : ''}{item.merchant}
                    </span>

                    {/* Name — Newsreader */}
                    <h4 className="rg-serif line-clamp-2" style={{ fontSize: 17, lineHeight: '22px', fontWeight: 500, color: 'var(--ink)' }}>
                      {item.title}
                    </h4>

                    {/* Rating */}
                    {item.rating && (
                      <div className="flex items-center gap-1.5">
                        <StarRatingInline value={item.rating} size={13} />
                        <span className="text-xs" style={{ color: 'var(--ink-3)' }}>
                          {item.rating}
                          {item.review_count && ` (${item.review_count.toLocaleString()})`}
                        </span>
                      </div>
                    )}

                    {/* Price + CTA */}
                    <div className="flex items-center justify-between pt-2 mt-auto">
                      <div>
                        <span style={{ fontSize: 14, fontWeight: 500, color: item.price && item.price > 0 ? 'var(--ink)' : 'var(--ink-3)' }}>
                          {item.price && item.price > 0
                            ? `${item.currency === 'USD' ? '$' : item.currency}${item.price.toFixed(2)}`
                            : 'Check price'}
                        </span>
                        {item.best_price && item.savings != null && item.savings > 0 && (
                          <p className="text-[11px] font-medium" style={{ color: 'var(--terra)' }}>
                            Save ${item.savings.toFixed(2)}{item.compared_retailer ? ` vs ${item.compared_retailer}` : ''}
                          </p>
                        )}
                      </div>
                      <span className="text-[12px] font-medium px-3 py-1.5 rounded-pill" style={{ background: 'var(--ink)', color: 'var(--paper)' }}>
                        Buy
                      </span>
                    </div>
                  </div>
                </div>
              </a>
            </motion.div>
          ))}
        </div>

        {/* Pagination Dots — each visual dot sits inside a ≥40px hit area
            (Mobile QA Round 8: 6px dots were untappable on touch screens) */}
        {items.length > itemsPerPage && (
          <div className="flex justify-center mt-2">
            {Array.from({ length: Math.ceil(items.length / itemsPerPage) }).map((_, idx) => (
              <button
                key={idx}
                onClick={() => setCurrentIndex(idx * itemsPerPage)}
                className="min-w-[40px] min-h-[40px] flex items-center justify-center"
                aria-label={`Page ${idx + 1}`}
              >
                <span
                  className={`h-1.5 rounded-full transition-all ${Math.floor(currentIndex / itemsPerPage) === idx
                    ? 'w-6 bg-[var(--primary)]'
                    : 'w-1.5 bg-[var(--border-strong)]'
                    }`}
                />
              </button>
            ))}
          </div>
        )}
      </div>
      <p className="text-xs text-[var(--text-muted)] mt-3 px-1">
        Disclosure: We may earn commissions from qualifying purchases.
      </p>
    </div>
  )
}
