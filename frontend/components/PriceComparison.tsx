'use client'

import { ExternalLink, BadgeCheck, TrendingDown } from 'lucide-react'
import { trackAffiliateClick } from '@/lib/trackAffiliate'

interface Offer {
  merchant: string
  price: number
  url: string
  image_url?: string
  rating?: number
  review_count?: number
  best: boolean
}

interface PriceComparisonProduct {
  product_name: string
  image_url?: string
  savings: number
  offers: Offer[]
}

interface PriceComparisonProps {
  items: PriceComparisonProduct[]
  title?: string
}

export default function PriceComparison({ items, title = 'Price Comparison' }: PriceComparisonProps) {
  if (!items || items.length === 0) return null

  return (
    <div className="w-full mb-6">
      <h3 className="font-serif text-lg font-semibold text-[var(--text)] mb-3 tracking-tight">
        {title}
      </h3>
      <div className="space-y-4">
        {items.map((product, idx) => (
          <div
            key={idx}
            className="border border-[var(--border)] rounded-xl bg-[var(--surface)] shadow-card overflow-hidden"
          >
            {/* Product header */}
            <div className="flex items-center gap-3 px-4 pt-4 pb-3">
              {product.image_url && (
                <img
                  src={product.image_url}
                  alt={product.product_name}
                  className="w-12 h-12 object-contain rounded-lg bg-[var(--surface)] flex-shrink-0"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                />
              )}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-[var(--text)] truncate">
                  {product.product_name}
                </p>
                {product.savings > 0 && (
                  <div className="flex items-center gap-1 mt-0.5">
                    <TrendingDown size={13} className="text-emerald-600 dark:text-emerald-400" />
                    <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
                      Save ${product.savings.toFixed(2)} by comparing
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Offers table */}
            <div className="border-t border-[var(--border)]">
              {product.offers.map((offer, oIdx) => (
                <a
                  key={oIdx}
                  href={offer.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`flex items-center justify-between px-4 py-2.5 transition-colors hover:bg-[var(--background)] ${
                    oIdx !== product.offers.length - 1 ? 'border-b border-[var(--border)]' : ''
                  }`}
                  onClick={(e) => {
                    e.preventDefault()
                    trackAffiliateClick({
                      provider: offer.merchant,
                      product_name: product.product_name,
                      url: offer.url,
                    })
                  }}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="text-sm font-medium text-[var(--text)]">
                      {offer.merchant}
                    </span>
                    {offer.best && (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 whitespace-nowrap">
                        <BadgeCheck size={10} />
                        Best Price
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`text-sm font-semibold ${
                      offer.best
                        ? 'text-emerald-600 dark:text-emerald-400'
                        : 'text-[var(--text)]'
                    }`}>
                      ${offer.price.toFixed(2)}
                    </span>
                    <span className="inline-flex items-center gap-1 text-xs text-[var(--primary)] font-medium whitespace-nowrap">
                      View Deal
                      <ExternalLink size={11} />
                    </span>
                  </div>
                </a>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
