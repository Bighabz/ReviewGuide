'use client'

import { ThumbsUp, ThumbsDown, ExternalLink, Star } from 'lucide-react'

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
  } = product

  return (
    <div className="border border-[var(--border)] rounded-xl p-6 bg-[var(--surface-elevated)] shadow-card">
      {/* Product Header with Image */}
      <div className="mb-4">
        <div className="flex gap-4">
          <div className="flex-shrink-0">
            <img
              src={image_url || getFallbackImage(product_name)}
              alt={product_name}
              className="w-24 h-24 object-contain rounded-lg bg-[var(--surface)]"
              loading="lazy"
            />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between">
              <h3 className="text-xl font-semibold font-serif text-[var(--text)]">{product_name}</h3>
              {rating && rating !== 'N/A' && rating !== '0/5' && (
                <div className="flex items-center gap-1 text-amber-500">
                  <Star size={16} fill="currentColor" />
                  <span className="text-sm font-medium">{rating}</span>
                </div>
              )}
            </div>
            {summary && (
              <p className="mt-2 text-[var(--text-secondary)] text-sm">{summary}</p>
            )}
          </div>
        </div>
      </div>

      {/* Features */}
      {features && features.length > 0 && (
        <div className="mb-4">
          <h4 className="text-sm font-semibold font-serif text-[var(--text-secondary)] mb-2">Key Features</h4>
          <ul className="list-disc list-inside space-y-1">
            {features.map((feature, idx) => (
              <li key={idx} className="text-sm text-[var(--text-secondary)]">{feature}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Pros and Cons */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        {/* Pros */}
        {pros && pros.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold font-serif text-green-700 mb-2 flex items-center gap-1">
              <ThumbsUp size={14} />
              Pros
            </h4>
            <ul className="space-y-2">
              {pros.map((pro, idx) => (
                <li key={idx} className="text-sm text-[var(--text-secondary)] flex items-start gap-2">
                  <span className="text-green-600 mt-0.5">&#10003;</span>
                  <span>{pro.description}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Cons */}
        {cons && cons.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold font-serif text-red-700 mb-2 flex items-center gap-1">
              <ThumbsDown size={14} />
              Cons
            </h4>
            <ul className="space-y-2">
              {cons.map((con, idx) => (
                <li key={idx} className="text-sm text-[var(--text-secondary)] flex items-start gap-2">
                  <span className="text-red-600 mt-0.5">&#10007;</span>
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
          <h4 className="text-sm font-semibold font-serif text-[var(--text-secondary)] mb-3">Where to Buy</h4>
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
