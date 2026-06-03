'use client'

import { StarRating } from '@/components/StarRating'

/**
 * ReviewConsensus — "How They Compare" block.
 *
 * One ruled row per product: rank, name, aggregated star rating, review count,
 * and a synthesized consensus paragraph. This is the comparison surface that
 * replaces the old HTML comparison table (and the pre-blueprint ReviewSources
 * card it descends from) — but per tone.md it surfaces NO source names:
 * synthesis only, no citations.
 *
 * Renders `review_consensus` ui_blocks emitted by product_compose.
 */

interface ConsensusProduct {
  name: string
  avg_rating: number
  total_reviews: number
  consensus: string
  rank: number
  // QA Round 6: the product the prose names as its #1 — pinned to rank 1 by
  // the backend and badged here so the ranking visibly agrees with the guide.
  editors_pick?: boolean
}

interface ReviewConsensusProps {
  data: { products: ConsensusProduct[] }
  title?: string
}

function formatReviewCount(count: number): string {
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1).replace(/\.0$/, '')}K`
  }
  return count.toLocaleString()
}

export default function ReviewConsensus({ data, title = 'How They Compare' }: ReviewConsensusProps) {
  const products = (data?.products ?? []).filter((p) => p && p.consensus)

  if (products.length === 0) return null

  return (
    <section className="w-full my-6 rg-blog-in" aria-label={title}>
      {/* Section eyebrow */}
      <div className="flex items-center gap-3 mb-3">
        <span className="rg-eyebrow rg-eyebrow--terra">{title}</span>
        <span className="flex-1 h-px" style={{ background: 'var(--line)' }} aria-hidden="true" />
      </div>

      {/* Ruled list of consensus rows */}
      <div
        className="rounded-xl overflow-hidden"
        style={{
          background: 'var(--paper-hi)',
          border: '1px solid var(--line)',
          boxShadow: 'var(--shadow-card)',
        }}
      >
        {products.map((product, i) => (
          <article
            key={`${product.name}-${i}`}
            className="p-4 sm:p-5"
            style={i > 0 ? { borderTop: '1px solid var(--line)' } : undefined}
          >
            {/* Header row: rank + name + rating + count */}
            <div className="flex items-baseline flex-wrap gap-x-3 gap-y-1 mb-2">
              <span
                className="rg-display text-lg leading-none"
                style={{ color: 'var(--terra)' }}
                aria-hidden="true"
              >
                {String(product.rank).padStart(2, '0')}
              </span>
              {/* font-serif (Tailwind → Newsreader) rather than rg-serif: the
                  globals.css h1–h6 element rule assigns Instrument Serif and
                  would win the cascade over a same-specificity utility class. */}
              <h4 className="font-serif text-base font-semibold tracking-tight" style={{ color: 'var(--ink)' }}>
                {product.name}
              </h4>
              {product.editors_pick && (
                <span
                  data-testid="editors-pick-badge"
                  className="uppercase px-1.5 py-0.5 rounded-full whitespace-nowrap rg-sans"
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    letterSpacing: '0.06em',
                    color: 'var(--paper-hi)',
                    background: 'var(--terra)',
                  }}
                >
                  Editor&apos;s pick
                </span>
              )}
              {product.avg_rating > 0 && (
                <span className="flex items-center gap-1.5">
                  {/* Clamp defensively — upstream normalizes mixed /10 + /5
                      scales, but a broken bundle must never render >5 stars. */}
                  <StarRating value={Math.min(5, product.avg_rating)} size={13} className="gap-px" />
                  <span className="text-sm font-medium rg-sans" style={{ color: 'var(--ink)' }}>
                    {Math.max(0, Math.min(5, product.avg_rating)).toFixed(1)}
                  </span>
                </span>
              )}
              {product.total_reviews > 0 && (
                <span className="text-xs rg-sans" style={{ color: 'var(--ink-3)' }}>
                  {formatReviewCount(product.total_reviews)} reviews
                </span>
              )}
            </div>

            {/* Synthesized consensus — serif body, no source names */}
            <p className="rg-serif text-[15px] leading-relaxed" style={{ color: 'var(--ink-2)' }}>
              {product.consensus}
            </p>
          </article>
        ))}
      </div>
    </section>
  )
}
