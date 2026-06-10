'use client'

/**
 * VerdictBlocks — block-level containers for the VerdictCard system.
 * These are what BlockRegistry points ui_block types at:
 *   VerdictList   ← product_cards (rich ranked answers)
 *   VerdictRail   ← carousel / products / *_products (merchant rails)
 *   VerdictLedger ← inline_product_card (compact rows in prose)
 *   OfferLedger   ← affiliate_links ("Where to buy")
 *   TopPickCard   ← top_pick (renderer kept in case the block returns; backend
 *                   removed the emitter in #105 but old saved chats may carry it)
 */

import VerdictCard, { normalizeProduct, type ProductInput, type NormalizedProduct } from './VerdictCard'
import { trackAffiliateClick } from '@/lib/trackAffiliate'

const Disclosure = ({ className = '' }: { className?: string }) => (
  <p className={`text-[11px] ${className}`} style={{ color: 'var(--text-muted)' }}>
    We may earn commissions from qualifying purchases.
  </p>
)

/** Ranked shortlist: masthead, feature card for #1, standard cards for the field */
export default function VerdictList({
  products,
  title = 'The Shortlist',
  context,
}: {
  products: ProductInput[]
  title?: string
  context?: string
}) {
  if (!products || products.length === 0) return null
  const normalized = products.map((p, i) => normalizeProduct(p, i))

  return (
    <section className="w-full">
      <header className="mb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] mb-1.5" style={{ color: 'var(--accent)' }}>
          The Shortlist · {normalized.length} contender{normalized.length === 1 ? '' : 's'}
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

      <footer className="mt-5 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
        <Disclosure />
      </footer>
    </section>
  )
}

/** Horizontal merchant/overflow rail — native scroll-snap, no chevron state */
export function VerdictRail({ products, title }: { products: ProductInput[]; title?: string }) {
  if (!products || products.length === 0) return null
  return (
    <section className="w-full">
      {title && (
        <div className="flex items-baseline gap-4 mb-4">
          <h3 className="font-serif text-xl tracking-tight" style={{ color: 'var(--text)' }}>
            {title}
          </h3>
          <div className="editorial-rule flex-1 self-center" />
        </div>
      )}
      <div className="flex gap-4 overflow-x-auto snap-x snap-mandatory pb-2 -mx-1 px-1 scrollbar-hide">
        {products.map((p, i) => (
          <VerdictCard key={p.id || p.product_id || i} product={normalizeProduct(p, i)} variant="rail" />
        ))}
      </div>
      <Disclosure className="mt-2" />
    </section>
  )
}

/** Inline ledger — compact rows inside flowing prose */
export function VerdictLedger({ products }: { products: ProductInput[] }) {
  if (!products || products.length === 0) return null
  return (
    <div className="w-full" style={{ borderTop: '1px solid var(--border)' }}>
      {products.map((p, i) => (
        <VerdictCard key={p.id || p.product_id || i} product={normalizeProduct(p, i)} variant="compact" />
      ))}
      <Disclosure className="pt-2" />
    </div>
  )
}

interface Offer {
  merchant: string
  price: number
  currency: string
  affiliate_link: string
  title?: string
  rating?: number
  review_count?: number
}

/** Cross-retailer offers — "Where to buy" merchant ledger */
export function OfferLedger({
  productName,
  offers,
  rank,
}: {
  productName: string
  offers: Offer[]
  rank?: number
}) {
  if (!offers || offers.length === 0) return null
  const priced = offers.filter((o) => o.price > 0)
  const lowest = priced.length > 0 ? Math.min(...priced.map((o) => o.price)) : null
  return (
    <section className="w-full rounded-md p-5" style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border)' }}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.2em] mb-1" style={{ color: 'var(--accent)' }}>
        Where to buy
      </p>
      <h4 className="font-serif text-lg tracking-tight mb-4" style={{ color: 'var(--text)' }}>
        {rank ? `${rank}. ` : ''}
        {productName}
      </h4>
      <div style={{ borderTop: '1px solid var(--border)' }}>
        {offers.map((offer, idx) => {
          const isBest = lowest != null && offer.price === lowest && offers.length > 1
          return (
            <a
              key={`${offer.merchant}-${idx}`}
              href={offer.affiliate_link}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => {
                e.preventDefault()
                trackAffiliateClick({
                  provider: offer.merchant || 'unknown',
                  product_name: productName,
                  url: offer.affiliate_link,
                })
              }}
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
                {offer.price > 0
                  ? `${offer.currency === 'USD' ? '$' : `${offer.currency} `}${offer.price.toFixed(2)}`
                  : 'Check price'}
              </span>
              <span className="text-xs font-semibold group-hover:underline underline-offset-4" style={{ color: 'var(--accent)' }}>
                Go ↗
              </span>
            </a>
          )
        })}
      </div>
      <Disclosure className="mt-3" />
    </section>
  )
}

interface TopPickData {
  product_name?: string
  headline?: string
  best_for?: string
  not_for?: string
  image_url?: string
  affiliate_url?: string
}

/** Renders a top_pick block as the feature card (legacy chats / future re-enable) */
export function TopPickCard({ data }: { data: TopPickData }) {
  if (!data?.product_name) return null
  const product: NormalizedProduct = normalizeProduct(
    {
      name: data.product_name,
      snippet: data.headline,
      image_url: data.image_url || undefined,
      url: data.affiliate_url || undefined,
      merchant: data.affiliate_url && /amazon|amzn\.to/i.test(data.affiliate_url) ? 'Amazon' : undefined,
      pros: data.best_for ? [data.best_for] : [],
      cons: data.not_for ? [data.not_for] : [],
      badges: ['Top Pick'],
    },
    0
  )
  return <VerdictCard product={product} variant="feature" forLabel="Best for" againstLabel="Not for" showRank={false} />
}
