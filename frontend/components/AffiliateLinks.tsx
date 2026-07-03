'use client'

import { ExternalLink, Star } from 'lucide-react'
import { safeHref } from '@/lib/safeHref'

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

interface AffiliateLinksProps {
  productName: string
  affiliateLinks: AffiliateLink[]
  rank?: number
}

export default function AffiliateLinks({ productName, affiliateLinks, rank }: AffiliateLinksProps) {
  if (!affiliateLinks || affiliateLinks.length === 0) {
    return null
  }

  return (
    <div className="border border-[var(--border)] rounded-xl p-4 my-4 shadow-card">
      {/* Product Header */}
      <div className="mb-3 pb-3 border-b border-[var(--border)]">
        <h3 className="text-base font-semibold font-serif text-[var(--text)]">
          {rank && `${rank}. `}{productName}
        </h3>
      </div>

      {/* Where to Buy — editorial heading */}
      <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-3">
        Where to buy
      </h4>

      <div className="space-y-2">
        {affiliateLinks.map((link, idx) => (
          <a
            key={idx}
            href={safeHref(link.affiliate_link)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-between p-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] hover:border-[var(--primary)]/30 transition-all group/link"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] shrink-0">
                {link.merchant}
              </span>
              {link.rating && (
                <div className="flex items-center gap-1">
                  <Star size={12} fill="currentColor" className="text-amber-500" />
                  <span className="text-xs text-[var(--text-muted)]">{link.rating}</span>
                </div>
              )}
              {link.review_count && link.review_count > 0 && (
                <span className="text-xs text-[var(--text-muted)]">
                  ({link.review_count.toLocaleString()} reviews)
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <span className="text-base font-bold font-serif text-[var(--text)]">
                {link.currency} {link.price.toFixed(2)}
              </span>
              <span className="text-xs font-medium text-[var(--primary)] group-hover/link:text-[var(--primary-hover)] flex items-center gap-1">
                View <ExternalLink size={12} />
              </span>
            </div>
          </a>
        ))}
      </div>
      <p className="text-xs text-[var(--text-muted)] mt-3 px-1">
        Disclosure: We may earn commissions from qualifying purchases.
      </p>
    </div>
  )
}
