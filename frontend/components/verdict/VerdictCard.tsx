'use client'

/**
 * VerdictCard — the unified product card system (production).
 *
 * One base component, four variants:
 *   feature  — Top Pick; the magazine-spread treatment
 *   standard — ranks 2–N in a ranked shortlist
 *   compact  — ledger row for inline use in flowing prose
 *   rail     — vertical card for a horizontal merchant/overflow rail
 *
 * Design rules (see FABLE_UX_CRITIQUE.md):
 *   - Terracotta (--accent) is reserved for money actions; blue for navigation.
 *   - Rank is typography (serif numeral), never a badge chip.
 *   - Badges come from data (badges[]), never from array position.
 *   - Missing images get a designed monogram tile, not an apology.
 *   - Tokens only — no raw hex, no Tailwind `dark:` variants.
 */

import { useState } from 'react'
import { ArrowUpRight } from 'lucide-react'
import { lookupCuratedProduct } from '@/lib/curatedProductLookup'
import { trackAffiliateClick } from '@/lib/trackAffiliate'

/** Accepts every product shape the backend emits (legacy, MCP, carousel items, inline rows). */
export interface ProductInput {
  // legacy / ranked-list fields
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
  // MCP fields
  id?: string
  name?: string
  url?: string
  snippet?: string
  score?: number
  best_offer?: { merchant?: string; price?: number; currency?: string; url?: string; image_url?: string }
  badges?: string[]
  // carousel-item fields (ProductCarousel legacy shape)
  product_id?: string
  description?: string
  best_price?: boolean
  savings?: number
  compared_retailer?: string
}

export interface NormalizedProduct {
  id: string
  rank?: number
  title: string
  snippet?: string
  price?: number
  currency: string
  merchant?: string
  link: string
  imageUrl?: string
  pros: string[]
  cons: string[]
  specs: string[]
  rating?: number
  reviewCount?: number
  badges: string[]
}

export function normalizeProduct(p: ProductInput, index = 0): NormalizedProduct {
  const title = p.title || p.name || 'Product'

  // Image/link fallback chain matches production InlineProductCard behavior:
  // explicit data first, curated catalog second, tagged Amazon search last —
  // every product must end with a working buy link.
  let imageUrl = p.image_url || p.best_offer?.image_url
  let link = p.affiliate_link || p.best_offer?.url || p.url
  if (!imageUrl || !link) {
    const curated = lookupCuratedProduct(title)
    imageUrl = imageUrl || curated.imageUrl || undefined
    link = link || curated.affiliateUrl || undefined
  }
  if (!link) {
    link = `https://www.amazon.com/s?k=${encodeURIComponent(title)}&tag=revguide-20`
  }

  const badges = p.badges ? [...p.badges] : []
  if (p.best_price && !badges.some((b) => /best price/i.test(b))) {
    badges.push('Best price')
  }

  return {
    id: p.id || p.product_id || `product-${index}`,
    rank: p.rank ?? index + 1,
    title,
    snippet: p.snippet || p.description,
    price: p.price ?? p.best_offer?.price,
    currency: p.currency || p.best_offer?.currency || 'USD',
    merchant: p.merchant || p.best_offer?.merchant,
    link,
    imageUrl,
    pros: p.pros || [],
    cons: p.cons || [],
    specs: p.specs || [],
    rating: p.rating,
    reviewCount: p.review_count,
    badges,
  }
}

const formatPrice = (price?: number, currency = 'USD') =>
  price == null ? undefined : `${currency === 'USD' ? '$' : `${currency} `}${price.toFixed(price % 1 === 0 ? 0 : 2)}`

/* ── Shared primitives ── */

/** Single rating treatment for the whole system: warning-token stars + serif numeral */
export function Rating({ value, count, size = 13 }: { value?: number; count?: number; size?: number }) {
  if (!value) return null
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="inline-flex" style={{ color: 'var(--warning)' }} aria-hidden="true">
        {[1, 2, 3, 4, 5].map((i) => {
          const fill = Math.max(0, Math.min(1, value - (i - 1)))
          return (
            <svg key={i} width={size} height={size} viewBox="0 0 24 24" className="shrink-0">
              <defs>
                <linearGradient id={`star-${i}-${Math.round(fill * 100)}`}>
                  <stop offset={`${fill * 100}%`} stopColor="currentColor" />
                  <stop offset={`${fill * 100}%`} stopColor="var(--border-strong)" />
                </linearGradient>
              </defs>
              <path
                fill={`url(#star-${i}-${Math.round(fill * 100)})`}
                d="M12 2l2.9 6.26 6.6.7-4.95 4.5 1.4 6.54L12 16.7 6.05 20l1.4-6.54L2.5 8.96l6.6-.7L12 2z"
              />
            </svg>
          )
        })}
      </span>
      <span className="font-serif text-sm leading-none" style={{ color: 'var(--text)' }}>
        {value.toFixed(1)}
      </span>
      {count != null && (
        <span className="text-xs leading-none" style={{ color: 'var(--text-muted)' }}>
          {count.toLocaleString()} reviews
        </span>
      )}
    </span>
  )
}

/** Designed missing-image fallback: serif monogram on accent-light — an editorial drop cap, not an emoji */
function MonogramTile({ title }: { title: string }) {
  return (
    <div
      data-testid="monogram-tile"
      className="w-full h-full flex flex-col items-center justify-center gap-1"
      style={{ background: 'var(--accent-light)' }}
    >
      <span className="font-serif italic leading-none select-none" style={{ color: 'var(--accent)', fontSize: 'clamp(2.5rem, 8vw, 4rem)' }}>
        {title.trim().charAt(0).toUpperCase()}
      </span>
      <span className="text-[10px] uppercase tracking-[0.18em]" style={{ color: 'var(--text-muted)' }}>
        No photo yet
      </span>
    </div>
  )
}

function ProductImage({ product, className = '' }: { product: NormalizedProduct; className?: string }) {
  const [errored, setErrored] = useState(false)
  return (
    <div className={`overflow-hidden ${className}`} style={{ background: 'var(--surface)' }}>
      {product.imageUrl && !errored ? (
        <img
          src={product.imageUrl}
          alt={product.title}
          loading="lazy"
          className="w-full h-full object-cover"
          onError={() => setErrored(true)}
        />
      ) : (
        <MonogramTile title={product.title} />
      )}
    </div>
  )
}

/** Tracked outbound click: telemetry + open in new tab (href kept for middle-click). */
function useAffiliateClick(product: NormalizedProduct) {
  return (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault()
    trackAffiliateClick({
      provider: product.merchant || 'unknown',
      product_name: product.title,
      url: product.link,
    })
  }
}

/** Money CTA — the only filled-terracotta element in the system. ≥44px tall. */
function BuyButton({ product, full = false }: { product: NormalizedProduct; full?: boolean }) {
  const onClick = useAffiliateClick(product)
  return (
    <a
      href={product.link}
      target="_blank"
      rel="noopener noreferrer"
      onClick={onClick}
      className={`inline-flex items-center justify-center gap-1.5 h-11 px-5 rounded-md text-sm font-semibold transition-colors ${full ? 'w-full sm:w-auto' : ''}`}
      style={{ background: 'var(--accent)', color: '#FFF8F4' }}
      onMouseEnter={(e) => ((e.currentTarget as HTMLAnchorElement).style.background = 'var(--accent-hover)')}
      onMouseLeave={(e) => ((e.currentTarget as HTMLAnchorElement).style.background = 'var(--accent)')}
    >
      See price{product.merchant ? ` at ${product.merchant}` : ''}
      <ArrowUpRight size={15} strokeWidth={2.25} />
    </a>
  )
}

/** Editorial kicker label — first badge in accent, the rest muted */
function Badges({ badges, merchant }: { badges: string[]; merchant?: string }) {
  if (badges.length === 0 && !merchant) return null
  return (
    <p className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1 text-[11px] font-semibold uppercase tracking-[0.16em]">
      {badges.map((b, i) => (
        <span key={b} style={{ color: i === 0 ? 'var(--accent)' : 'var(--text-muted)' }}>
          {b}
        </span>
      ))}
      {merchant && badges.length === 0 && (
        <span style={{ color: 'var(--text-muted)' }}>via {merchant}</span>
      )}
    </p>
  )
}

/** FOR / AGAINST ledger — scannable in two seconds, neutral ink, colored glyphs only */
export function ForAgainst({
  pros,
  cons,
  forLabel = 'For',
  againstLabel = 'Against',
}: {
  pros: string[]
  cons: string[]
  forLabel?: string
  againstLabel?: string
}) {
  if (pros.length === 0 && cons.length === 0) return null
  const Col = ({ label, items, glyph, glyphColor }: { label: string; items: string[]; glyph: string; glyphColor: string }) =>
    items.length === 0 ? null : (
      <div className="flex-1 min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] mb-1.5" style={{ color: 'var(--text-muted)' }}>
          {label}
        </p>
        <ul className="space-y-1">
          {items.slice(0, 3).map((item) => (
            <li key={item} className="flex gap-2 text-[13px] leading-snug" style={{ color: 'var(--text-secondary)' }}>
              <span className="font-serif shrink-0" style={{ color: glyphColor }} aria-hidden="true">
                {glyph}
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    )
  return (
    <div className="flex flex-col sm:flex-row gap-4 sm:gap-8">
      <Col label={forLabel} items={pros} glyph="+" glyphColor="var(--success)" />
      <Col label={againstLabel} items={cons} glyph="–" glyphColor="var(--error)" />
    </div>
  )
}

function RankNumeral({ rank, accent = false, className = '' }: { rank?: number; accent?: boolean; className?: string }) {
  if (rank == null) return null
  return (
    <span
      aria-label={`Ranked number ${rank}`}
      className={`font-serif italic leading-none select-none ${className}`}
      style={{ color: accent ? 'var(--accent)' : 'var(--border-strong)' }}
    >
      {rank}
    </span>
  )
}

/* ── Variants ── */

export type VerdictVariant = 'feature' | 'standard' | 'compact' | 'rail'

export default function VerdictCard({
  product,
  variant = 'standard',
  forLabel,
  againstLabel,
  showRank = true,
}: {
  product: NormalizedProduct
  variant?: VerdictVariant
  forLabel?: string
  againstLabel?: string
  showRank?: boolean
}) {
  if (variant === 'feature') return <FeatureCard product={product} forLabel={forLabel} againstLabel={againstLabel} showRank={showRank} />
  if (variant === 'compact') return <CompactRow product={product} />
  if (variant === 'rail') return <RailCard product={product} />
  return <StandardCard product={product} />
}

/** The Top Pick spread — earns its size; the one loud moment in the list */
function FeatureCard({
  product,
  forLabel,
  againstLabel,
  showRank,
}: {
  product: NormalizedProduct
  forLabel?: string
  againstLabel?: string
  showRank?: boolean
}) {
  return (
    <article
      className="rounded-md overflow-hidden shadow-editorial"
      style={{
        background: 'var(--surface-elevated)',
        border: '1px solid var(--border)',
        borderTop: '3px solid var(--accent)',
      }}
    >
      <div className="flex flex-col md:flex-row">
        <ProductImage product={product} className="md:w-[42%] aspect-[4/3] md:aspect-auto md:min-h-[320px] shrink-0" />

        <div className="flex-1 min-w-0 p-5 sm:p-7 flex flex-col gap-4">
          <Badges badges={product.badges} />

          <div className="flex items-start gap-3">
            {showRank && <RankNumeral rank={product.rank} accent className="text-5xl sm:text-6xl -mt-1" />}
            <div className="min-w-0">
              <h3 className="font-serif text-2xl sm:text-[1.75rem] leading-tight tracking-tight" style={{ color: 'var(--text)' }}>
                <a href={product.link} target="_blank" rel="noopener noreferrer" className="hover:underline decoration-1 underline-offset-4">
                  {product.title}
                </a>
              </h3>
              <div className="mt-1.5">
                <Rating value={product.rating} count={product.reviewCount} />
              </div>
            </div>
          </div>

          {/* The verdict line — one sentence, the editor's call */}
          {product.snippet && (
            <p
              className="font-serif italic text-[1.05rem] leading-relaxed pl-4"
              style={{ color: 'var(--text)', borderLeft: '2px solid var(--accent)' }}
            >
              {product.snippet}
            </p>
          )}

          <ForAgainst pros={product.pros} cons={product.cons} forLabel={forLabel} againstLabel={againstLabel} />

          {product.specs.length > 0 && (
            <p
              className="text-xs pt-3 flex flex-wrap gap-x-4 gap-y-1"
              style={{ color: 'var(--text-muted)', borderTop: '1px solid var(--border)' }}
            >
              {product.specs.map((s) => (
                <span key={s}>{s}</span>
              ))}
            </p>
          )}

          {/* Money row */}
          <div className="mt-auto pt-4 flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-5" style={{ borderTop: '1px solid var(--border)' }}>
            {product.price != null && (
              <p className="flex items-baseline gap-2">
                <span className="font-serif text-3xl" style={{ color: 'var(--text)' }}>
                  {formatPrice(product.price, product.currency)}
                </span>
                {product.merchant && (
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    via {product.merchant}
                  </span>
                )}
              </p>
            )}
            <div className="sm:ml-auto">
              <BuyButton product={product} full />
            </div>
          </div>
        </div>
      </div>
    </article>
  )
}

/** Ranks 2–N — same DNA, half the volume */
function StandardCard({ product }: { product: NormalizedProduct }) {
  return (
    <article
      className="rounded-md overflow-hidden"
      style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border)' }}
    >
      <div className="flex">
        <ProductImage product={product} className="w-28 sm:w-40 shrink-0 self-stretch min-h-[9rem]" />
        <div className="flex-1 min-w-0 p-4 sm:p-5 flex flex-col gap-3">
          <Badges badges={product.badges} />
          <div className="flex items-start gap-2.5">
            <RankNumeral rank={product.rank} className="text-3xl sm:text-4xl -mt-0.5" />
            <div className="min-w-0 flex-1">
              <h3 className="font-serif text-lg sm:text-xl leading-snug tracking-tight" style={{ color: 'var(--text)' }}>
                <a href={product.link} target="_blank" rel="noopener noreferrer" className="hover:underline decoration-1 underline-offset-4">
                  {product.title}
                </a>
              </h3>
              <div className="mt-1">
                <Rating value={product.rating} count={product.reviewCount} size={12} />
              </div>
            </div>
            {product.price != null && (
              <p className="font-serif text-xl sm:text-2xl shrink-0" style={{ color: 'var(--text)' }}>
                {formatPrice(product.price, product.currency)}
              </p>
            )}
          </div>

          {product.snippet && (
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              {product.snippet}
            </p>
          )}

          <ForAgainst pros={product.pros} cons={product.cons} />

          <div className="mt-auto pt-3 flex items-center gap-4" style={{ borderTop: '1px solid var(--border)' }}>
            <BuyButton product={product} />
          </div>
        </div>
      </div>
    </article>
  )
}

/** Ledger row for inline prose — replaces InlineProductCard */
function CompactRow({ product }: { product: NormalizedProduct }) {
  const onClick = useAffiliateClick(product)
  return (
    <div className="flex items-center gap-3 sm:gap-4 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
      <RankNumeral rank={product.rank} accent={product.rank === 1} className="text-2xl w-6 text-center shrink-0" />
      <ProductImage product={product} className="w-14 h-14 rounded-md shrink-0" />
      <div className="flex-1 min-w-0">
        {product.badges[0] && (
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--accent)' }}>
            {product.badges[0]}
          </p>
        )}
        <p className="font-serif text-[15px] leading-snug truncate" style={{ color: 'var(--text)' }}>
          {product.title}
        </p>
        {product.snippet && (
          <p className="text-xs truncate mt-0.5" style={{ color: 'var(--text-muted)' }}>
            {product.snippet}
          </p>
        )}
      </div>
      <div className="flex flex-col items-end gap-1 shrink-0">
        {product.price != null && (
          <span className="font-serif text-base" style={{ color: 'var(--text)' }}>
            {formatPrice(product.price, product.currency)}
          </span>
        )}
        <a
          href={product.link}
          target="_blank"
          rel="noopener noreferrer"
          onClick={onClick}
          className="inline-flex items-center justify-center h-9 min-w-[44px] px-3 rounded-md text-xs font-semibold"
          style={{ background: 'var(--accent-light)', color: 'var(--accent)' }}
        >
          Price <ArrowUpRight size={12} className="ml-0.5" />
        </a>
      </div>
    </div>
  )
}

/** Rail card — native CSS scroll-snap rail, no carousel state machine */
function RailCard({ product }: { product: NormalizedProduct }) {
  const onClick = useAffiliateClick(product)
  return (
    <article
      className="w-[230px] sm:w-[250px] shrink-0 snap-start rounded-md overflow-hidden flex flex-col"
      style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border)' }}
    >
      <ProductImage product={product} className="aspect-[4/3]" />
      <div className="p-4 flex flex-col gap-2 flex-1">
        <Badges badges={product.badges} merchant={product.merchant} />
        <h4 className="font-serif text-[15px] leading-snug line-clamp-2" style={{ color: 'var(--text)' }}>
          {product.title}
        </h4>
        <Rating value={product.rating} size={11} />
        <div className="mt-auto pt-3 flex items-center justify-between gap-2" style={{ borderTop: '1px solid var(--border)' }}>
          <span className="font-serif text-lg" style={{ color: 'var(--text)' }}>
            {formatPrice(product.price, product.currency) ?? ''}
          </span>
          <a
            href={product.link}
            target="_blank"
            rel="noopener noreferrer"
            onClick={onClick}
            className="inline-flex items-center justify-center h-9 px-3 rounded-md text-xs font-semibold"
            style={{ background: 'var(--accent)', color: '#FFF8F4' }}
          >
            Price <ArrowUpRight size={12} className="ml-0.5" />
          </a>
        </div>
      </div>
    </article>
  )
}
