'use client'

import { safeHref } from '@/lib/safeHref'

interface ProductCard {
  // Old format fields
  rank?: number
  title?: string
  price?: number
  currency?: string
  image_url?: string
  affiliate_link?: string
  merchant?: string
  specs?: string[]
  pros?: string[]
  cons?: string[]
  rating?: number
  review_count?: number

  // New format fields (from MCP)
  id?: string
  name?: string
  url?: string
  snippet?: string
  score?: number
  best_offer?: {
    merchant: string
    price: number
    currency: string
    url: string
  }
  badges?: string[]
}

interface ProductCardsProps {
  products: ProductCard[]
}

export default function ProductCards({ products }: ProductCardsProps) {
  if (!products || products.length === 0) {
    return null
  }

  return (
    <div className="space-y-4 w-full">
      {products.map((product, index) => {
        // Support both old and new formats
        const displayTitle = product.title || product.name || 'Product'
        const displayRank = product.rank !== undefined ? product.rank : index + 1
        const displayPrice = product.price || product.best_offer?.price
        const displayCurrency = product.currency || product.best_offer?.currency || 'USD'
        const displayMerchant = product.merchant || product.best_offer?.merchant
        const displayLink = product.affiliate_link || product.best_offer?.url || product.url || '#'
        const displayImage = product.image_url || (product.best_offer as any)?.image_url || ''
        const displayPros = product.pros || []
        const displayCons = product.cons || []

        return (
          <div
            key={product.id || product.rank || index}
            className="group bg-[var(--surface-elevated)] border border-[var(--border)] rounded-xl overflow-hidden hover:shadow-md transition-all duration-300"
          >
            <div className="p-5 sm:p-6">
              <div className="flex gap-4">
                {/* Product image */}
                {displayImage && (
                  <a href={safeHref(displayLink)} target="_blank" rel="noopener noreferrer" className="shrink-0">
                    <div className="w-20 h-20 sm:w-24 sm:h-24 rounded-lg overflow-hidden bg-[var(--surface)] border border-[var(--border)]">
                      <img
                        src={displayImage}
                        alt={displayTitle}
                        className="w-full h-full object-contain p-1"
                        loading="lazy"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                      />
                    </div>
                  </a>
                )}
                <div className="flex-1 min-w-0">
              {/* Editorial heading */}
              <div className="flex items-start justify-between gap-4 mb-2">
                <div className="flex-1 min-w-0">
                  <h3 className="font-serif text-xl font-semibold text-[var(--text)] leading-snug tracking-tight">
                    <span className="text-[var(--primary)]">{displayRank}.</span>{' '}
                    <a href={safeHref(displayLink)} target="_blank" rel="noopener noreferrer" className="hover:underline decoration-1 underline-offset-4">
                      {displayTitle}
                    </a>
                  </h3>
                  {/* Badges as editorial labels */}
                  <div className="flex items-center gap-2 mt-1.5">
                    {product.badges?.map((badge, bIdx) => (
                      <span key={bIdx} className="text-xs font-semibold text-[var(--accent)] italic">
                        {badge}
                      </span>
                    ))}
                    {displayMerchant && (
                      <span className="text-[10px] uppercase font-medium tracking-wider text-[var(--text-muted)]">
                        via {displayMerchant}
                      </span>
                    )}
                  </div>
                </div>
                {displayPrice !== undefined && (
                  <div className="text-right shrink-0">
                    <p className="text-xl font-bold text-[var(--text)] font-serif">
                      ${displayPrice.toFixed(2)}
                    </p>
                  </div>
                )}
              </div>

              {/* Snippet / description */}
              {product.snippet && (
                <p className="text-sm text-[var(--text-secondary)] leading-relaxed mt-3 mb-4">
                  {product.snippet}
                </p>
              )}

              {/* Pros & cons as flowing text */}
              {(displayPros.length > 0 || displayCons.length > 0) && (
                <div className="mt-3 mb-4 space-y-2 text-sm leading-relaxed">
                  {displayPros.length > 0 && (
                    <p className="text-[var(--text)]">
                      <span className="font-semibold text-green-600">What we like:</span>{' '}
                      {displayPros.join('. ')}.
                    </p>
                  )}
                  {displayCons.length > 0 && (
                    <p className="text-[var(--text)]">
                      <span className="font-semibold text-red-500">Watch out for:</span>{' '}
                      {displayCons.join('. ')}.
                    </p>
                  )}
                </div>
              )}

              {/* CTA */}
              <div className="flex justify-start pt-3 border-t border-[var(--border)]">
                <a
                  href={safeHref(displayLink)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm font-medium text-[var(--primary)] hover:text-[var(--primary-hover)] transition-colors"
                >
                  Check price{displayMerchant ? ` on ${displayMerchant}` : ''} &rarr;
                </a>
              </div>
                </div>{/* end flex-1 */}
              </div>{/* end flex gap-4 */}
            </div>
          </div>
        )
      })}
      <p className="text-xs text-[var(--text-muted)] mt-3 px-1">
        Disclosure: We may earn commissions from qualifying purchases.
      </p>
    </div>
  )
}
