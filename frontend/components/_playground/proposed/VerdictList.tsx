'use client'

/**
 * VerdictList — "The Shortlist": the proposed container for ranked answers.
 * Masthead kicker + serif title + editorial rule, feature card for #1,
 * standard cards for the rest, colophon disclosure at the foot.
 *
 * Production note: this is what BlockRegistry's `product_cards` entry would
 * point at — <VerdictList products={(b.data as any)?.products ?? []} />.
 */

import VerdictCard, { normalizeProduct } from './VerdictCard'
import type { FixtureProduct } from '../fixtures'

export default function VerdictList({
  products,
  title = 'The Shortlist',
  context,
}: {
  products: FixtureProduct[]
  title?: string
  context?: string
}) {
  if (!products || products.length === 0) return null
  const normalized = products.map((p, i) => normalizeProduct(p, i))

  return (
    <section className="w-full">
      {/* Masthead */}
      <header className="mb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] mb-1.5" style={{ color: 'var(--accent)' }}>
          The Shortlist · {normalized.length} contenders
        </p>
        <div className="flex items-baseline gap-4">
          <h2 className="font-serif text-2xl sm:text-3xl tracking-tight" style={{ color: 'var(--text)' }}>
            {title}
          </h2>
          <div className="editorial-rule flex-1 self-center" />
        </div>
        {context && (
          <p className="text-sm mt-2" style={{ color: 'var(--text-secondary)' }}>
            {context}
          </p>
        )}
      </header>

      <div className="space-y-4">
        {normalized.map((product) => (
          <VerdictCard key={product.id} product={product} variant={product.rank === 1 ? 'feature' : 'standard'} />
        ))}
      </div>

      {/* Colophon */}
      <footer className="mt-5 pt-3 flex items-baseline justify-between gap-4" style={{ borderTop: '1px solid var(--border)' }}>
        <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
          Prices checked at publication. We may earn commissions from qualifying purchases.
        </p>
      </footer>
    </section>
  )
}

/** Horizontal "also considered" rail — native scroll-snap, no chevron state */
export function VerdictRail({ products, title = 'Also considered' }: { products: FixtureProduct[]; title?: string }) {
  if (!products || products.length === 0) return null
  return (
    <section className="w-full">
      <div className="flex items-baseline gap-4 mb-4">
        <h3 className="font-serif text-xl tracking-tight" style={{ color: 'var(--text)' }}>
          {title}
        </h3>
        <div className="editorial-rule flex-1 self-center" />
      </div>
      <div className="flex gap-4 overflow-x-auto snap-x snap-mandatory pb-2 -mx-1 px-1 scrollbar-hide">
        {products.map((p, i) => (
          <VerdictCard key={p.id || i} product={normalizeProduct(p, i)} variant="rail" />
        ))}
      </div>
      <p className="text-[11px] mt-2" style={{ color: 'var(--text-muted)' }}>
        We may earn commissions from qualifying purchases.
      </p>
    </section>
  )
}

/** Inline ledger — replaces InlineProductCard's stack of rows */
export function VerdictLedger({ products }: { products: FixtureProduct[] }) {
  if (!products || products.length === 0) return null
  return (
    <div className="w-full" style={{ borderTop: '1px solid var(--border)' }}>
      {products.map((p, i) => (
        <VerdictCard key={p.id || i} product={normalizeProduct(p, i)} variant="compact" />
      ))}
      <p className="text-[11px] pt-2" style={{ color: 'var(--text-muted)' }}>
        We may earn commissions from qualifying purchases.
      </p>
    </div>
  )
}

/** Cross-retailer offers — replaces AffiliateLinks' "Where to buy" box */
export function OfferLedger({
  productName,
  offers,
}: {
  productName: string
  offers: Array<{ merchant: string; price: number; currency: string; affiliate_link: string; rating?: number; review_count?: number }>
}) {
  if (!offers || offers.length === 0) return null
  const lowest = Math.min(...offers.map((o) => o.price))
  return (
    <section className="w-full rounded-md p-5" style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border)' }}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.2em] mb-1" style={{ color: 'var(--accent)' }}>
        Where to buy
      </p>
      <h4 className="font-serif text-lg tracking-tight mb-4" style={{ color: 'var(--text)' }}>
        {productName}
      </h4>
      <div style={{ borderTop: '1px solid var(--border)' }}>
        {offers.map((offer) => {
          const isBest = offer.price === lowest
          return (
            <a
              key={offer.merchant}
              href={offer.affiliate_link}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 py-3 min-h-[52px] group"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <span className="text-xs font-semibold uppercase tracking-[0.12em] w-24 shrink-0" style={{ color: 'var(--text)' }}>
                {offer.merchant}
              </span>
              {isBest && (
                <span
                  className="text-[10px] font-semibold uppercase tracking-[0.14em] px-2 py-0.5 rounded-sm"
                  style={{ background: 'var(--accent-light)', color: 'var(--accent)' }}
                >
                  Best price
                </span>
              )}
              <span className="flex-1" />
              <span className="font-serif text-lg" style={{ color: 'var(--text)' }}>
                {offer.currency === 'USD' ? '$' : `${offer.currency} `}
                {offer.price.toFixed(2)}
              </span>
              <span
                className="text-xs font-semibold group-hover:underline underline-offset-4"
                style={{ color: 'var(--accent)' }}
              >
                Go ↗
              </span>
            </a>
          )
        })}
      </div>
      <p className="text-[11px] mt-3" style={{ color: 'var(--text-muted)' }}>
        We may earn commissions from qualifying purchases.
      </p>
    </section>
  )
}
