'use client'

/**
 * ProductReview — the chat result card for a reviewed product, in the Verdict
 * editorial treatment (2026-06-10): rank #1 renders as the feature spread
 * (terra top rule, large image, verdict line, money row), ranks 2+ as the
 * tighter standard card. All existing wiring is preserved: SaveToggle,
 * product-detail handoff (/product/[slug]), refine-chip contract, offer
 * badges (Under budget / condition labels), affiliate click tracking.
 */

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowUpRight, Bookmark } from 'lucide-react'
import { toggleSaved, isSaved, slugifyProduct, type SavedItem } from '@/lib/savedItems'
import { stashProductDetail } from '@/lib/productDetail'
import { useChatStatus } from '@/lib/chatStatusContext'
import { trackAffiliateClick } from '@/lib/trackAffiliate'
import { Rating, ForAgainst } from '@/components/verdict/VerdictCard'

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
      className="absolute top-1.5 right-1.5 z-10 w-10 h-10 rounded-full flex items-center justify-center"
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

// Dreambeans-inspired inline refinement: a "not quite right?" affordance below
// a single review card. Each chip sends the EXACT phrase the clarifier's
// refinement detector recognizes (`_detect_refinement_action` in
// backend/app/agents/clarifier_agent.py — verified against the canonical chips
// in mcp_server/tools/next_step_suggestion.py). The backend re-ranks the prior
// shortlist with adjusted slots WITHOUT re-asking — no backend or API change.
//
// IMPORTANT: these strings are a contract. The detector is an exact-match
// allowlist ("Show cheaper options", "More premium picks", "Different use
// case", "Only <Brand>"), so any reword here silently drops back to a fresh
// query (the "Cheaper" chip would stop making results cheaper). Keep them in
// sync with that allowlist; the backend operates on the whole shortlist, so
// these deliberately carry no product name.
export function RefineRow({ productName }: { productName: string }) {
  // Read live streaming state so chips don't become silent dead-clicks while a
  // previous request is in flight (ChatContainer.handleSuggestionClick no-ops
  // when isStreaming — without this the user gets zero feedback).
  const { isStreaming } = useChatStatus()
  const send = (question: string) => {
    if (isStreaming) return
    window.dispatchEvent(new CustomEvent('sendSuggestion', { detail: { question } }))
  }
  // Slug keeps test ids unique even if multiple RefineRows ever co-exist.
  const slug = slugifyProduct(productName) || 'product'
  const chips = [
    { label: 'Cheaper', q: 'Show cheaper options' },
    { label: 'More premium', q: 'More premium picks' },
    { label: 'Different use case', q: 'Different use case' },
  ]
  return (
    <div className="mt-4 pt-4 border-t border-[var(--border)]" data-testid={`refine-row-${slug}`}>
      <h4 className="rg-eyebrow mb-2">Not quite right?</h4>
      <div className="flex flex-row flex-wrap gap-2">
        {chips.map((c) => (
          <button
            key={c.label}
            data-testid={`refine-chip-${slug}-${c.label.toLowerCase().replace(/\s+/g, '-')}`}
            onClick={() => send(c.q)}
            disabled={isStreaming}
            className="inline-flex items-center gap-2 rounded-[12px] border border-[var(--line-2)] bg-[var(--paper-hi)] text-[var(--ink)] px-3.5 py-2.5 text-[14px] leading-[20px] font-medium text-left transition-all hover:border-[var(--terra)] hover:bg-[var(--terra-soft)] disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:border-[var(--line-2)] disabled:hover:bg-[var(--paper-hi)]"
          >
            {/* quiz-path 4px terracotta leading dot — matches next_suggestions */}
            <span className="w-1 h-1 rounded-full flex-shrink-0" style={{ background: 'var(--terra)' }} />
            {c.label}
          </button>
        ))}
      </div>
    </div>
  )
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
  // F2: offer priced below the user's stated budget range — shown as a deal
  // with an "Under budget" badge rather than hidden.
  below_budget_floor?: boolean
  // $407-class honesty: "Renewed" / "Used" / "Open box" for non-new listings —
  // the low price is real, the user just deserves to know why.
  condition_label?: string | null
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
      citations?: Array<{ id: number; url: string; title: string }>
    }>
    cons: Array<{
      description: string
      source_ids?: number[]
      citations?: Array<{ id: number; url: string; title: string }>
    }>
    affiliate_links: AffiliateLink[]
    rank: number
  }
  // The inline "Not quite right?" refine affordance only makes sense for a
  // single, coherent recommendation. It's suppressed in the multi-card review
  // list (BlockRegistry renders one RefineRow after the whole shortlist).
  showRefine?: boolean
}

/** "4.5/5" | "4.5" → 4.5; "N/A"/"0/5" → undefined */
function parseRating(rating: string): number | undefined {
  if (!rating || rating === 'N/A' || rating === '0/5') return undefined
  const value = parseFloat(rating)
  return Number.isFinite(value) && value > 0 ? value : undefined
}

/** Lowest real price wins the CTA; unpriced offers fall back to first. */
function pickBestOffer(offers: AffiliateLink[]): AffiliateLink | undefined {
  if (!offers || offers.length === 0) return undefined
  const priced = offers.filter((o) => o.price > 0)
  if (priced.length === 0) return offers[0]
  return priced.reduce((best, o) => (o.price < best.price ? o : best))
}

function OfferBadges({ offer }: { offer: AffiliateLink }) {
  return (
    <>
      {offer.below_budget_floor && (
        <span
          data-testid="under-budget-badge"
          className="uppercase px-1.5 py-0.5 rounded-full whitespace-nowrap"
          style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', color: 'var(--terra)', background: 'var(--paper-alt)', border: '1px solid var(--line)' }}
        >
          Under budget
        </span>
      )}
      {offer.condition_label && (
        <span
          data-testid="condition-badge"
          className="uppercase px-1.5 py-0.5 rounded-full whitespace-nowrap"
          style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', color: 'var(--ink-2)', background: 'var(--paper-alt)', border: '1px solid var(--line)' }}
        >
          {offer.condition_label}
        </span>
      )}
    </>
  )
}

// QA 2026-06-10 #3: showRefine defaults OFF — the in-card RefineRow duplicated
// the next_suggestions chip row below the message. RefineRow stays exported
// for surfaces with no suggestion row.
export default function ProductReview({ product, showRefine = false }: ProductReviewProps) {
  const { product_name, rating, summary, image_url, features, pros, cons, affiliate_links, rank } = product

  const router = useRouter()
  const slug = slugifyProduct(product_name)
  const isFeature = rank === 1 || !rank
  const roleLabel = rank === 1 ? 'Top pick · for you' : rank ? `Pick #${rank}` : ''
  const bestOffer = pickBestOffer(affiliate_links)
  const otherOffers = (affiliate_links ?? []).filter((o) => o !== bestOffer)
  const ratingValue = parseRating(rating)
  const prosText = (pros ?? []).map((p) => p.description)
  const consText = (cons ?? []).map((c) => c.description)

  function openDetail() {
    try {
      // Basic payload (back-compat + bookmark fallback).
      sessionStorage.setItem('active_product', JSON.stringify({
        id: slug, name: product_name,
        price: bestOffer?.price, imageUrl: image_url, url: bestOffer?.affiliate_link,
        role: roleLabel,
      }))
      // E1: full analysis handoff so /product/[id] renders real sections.
      stashProductDetail({
        id: slug,
        name: product_name,
        role: roleLabel,
        rating,
        summary,
        imageUrl: image_url,
        price: bestOffer?.price,
        url: bestOffer?.affiliate_link,
        features: Array.isArray(features) ? features : [],
        pros: (pros ?? []).map((p) => ({ description: p.description, citations: p.citations })),
        cons: (cons ?? []).map((c) => ({ description: c.description, citations: c.citations })),
        buyLinks: (affiliate_links ?? []).map((l) => ({
          merchant: l.merchant, price: l.price, url: l.affiliate_link,
        })),
      })
    } catch { /* ignore */ }
    router.push(`/product/${slug}`)
  }

  const buyClick = (offer: AffiliateLink) => (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault()
    trackAffiliateClick({ provider: offer.merchant || 'unknown', product_name, url: offer.affiliate_link })
  }

  const productImage = (
    <div
      className={`relative overflow-hidden shrink-0 ${
        isFeature ? 'md:w-[38%] aspect-[4/3] md:aspect-auto md:min-h-[300px]' : 'w-28 sm:w-40 self-stretch min-h-[9rem]'
      }`}
      style={{ background: 'var(--paper-alt)' }}
    >
      <img
        src={image_url || getFallbackImage(product_name)}
        alt={product_name}
        loading="lazy"
        className="absolute inset-0 w-full h-full object-contain p-4"
      />
      <SaveToggle item={{ id: slug, name: product_name, price: bestOffer?.price, imageUrl: image_url, url: bestOffer?.affiliate_link, role: roleLabel }} />
    </div>
  )

  return (
    <article
      className={`rounded-md overflow-hidden ${isFeature ? 'shadow-editorial' : ''}`}
      style={{
        background: 'var(--paper-hi)',
        border: '1px solid var(--line)',
        ...(isFeature ? { borderTop: '3px solid var(--terra)' } : {}),
      }}
    >
      <div className={`flex ${isFeature ? 'flex-col md:flex-row' : ''}`}>
        {productImage}

        <div className={`flex-1 min-w-0 flex flex-col ${isFeature ? 'p-5 sm:p-7 gap-4' : 'p-4 sm:p-5 gap-3'}`}>
          {/* Kicker + title + rating */}
          <div>
            {roleLabel && (
              <p
                className="uppercase mb-1.5"
                style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.16em', color: rank === 1 ? 'var(--terra)' : 'var(--ink-2)' }}
              >
                {roleLabel}
              </p>
            )}
            <div className="flex items-start gap-3">
              {rank > 0 && (
                <span
                  aria-label={`Ranked number ${rank}`}
                  className={`font-serif italic leading-none select-none ${isFeature ? 'text-5xl sm:text-6xl -mt-1' : 'text-3xl sm:text-4xl -mt-0.5'}`}
                  style={{ color: rank === 1 ? 'var(--terra)' : 'var(--line-2)' }}
                >
                  {rank}
                </span>
              )}
              <div className="min-w-0 flex-1">
                <button onClick={openDetail} className="text-left">
                  <h3
                    className={`font-serif leading-tight tracking-tight hover:underline decoration-1 underline-offset-4 ${isFeature ? 'text-2xl sm:text-[1.75rem]' : 'text-lg sm:text-xl'}`}
                    style={{ color: 'var(--ink)' }}
                  >
                    {product_name}
                  </h3>
                </button>
                <div className="mt-1.5">
                  <Rating value={ratingValue} count={bestOffer?.review_count} size={isFeature ? 13 : 12} />
                </div>
              </div>
            </div>
          </div>

          {/* The verdict line — one sentence, the editor's call */}
          {summary && (
            <p
              className={`font-serif italic leading-relaxed pl-4 ${isFeature ? 'text-[1.05rem]' : 'text-[15px]'}`}
              style={{ color: 'var(--ink)', borderLeft: '2px solid var(--terra)' }}
            >
              {summary}
            </p>
          )}

          {/* The good / the catch ledger */}
          <ForAgainst pros={prosText} cons={consText} forLabel="The good" againstLabel="The catch" />

          {/* Hairline spec row from features */}
          {features && features.length > 0 && (
            <p
              className="text-xs pt-3 flex flex-wrap gap-x-4 gap-y-1"
              style={{ color: 'var(--ink-3)', borderTop: '1px solid var(--line)' }}
            >
              {features.slice(0, 4).map((f) => (
                <span key={f}>{f}</span>
              ))}
            </p>
          )}

          {/* Money row — best offer price + terracotta CTA */}
          {bestOffer && (
            <div
              className="mt-auto pt-4 flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-3 sm:gap-5"
              style={{ borderTop: '1px solid var(--line)' }}
            >
              <p className="flex items-baseline gap-2 flex-wrap">
                {bestOffer.price > 0 && (
                  <span className={`font-serif ${isFeature ? 'text-3xl' : 'text-2xl'}`} style={{ color: 'var(--ink)' }}>
                    {bestOffer.currency === 'USD' ? '$' : `${bestOffer.currency} `}
                    {bestOffer.price.toFixed(2)}
                  </span>
                )}
                <span className="text-xs" style={{ color: 'var(--ink-3)' }}>
                  via {bestOffer.merchant}
                </span>
                <OfferBadges offer={bestOffer} />
              </p>
              <div className="sm:ml-auto">
                <a
                  href={bestOffer.affiliate_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={buyClick(bestOffer)}
                  className={`inline-flex items-center justify-center gap-1.5 min-h-[44px] px-5 py-2 rounded-md text-sm font-semibold whitespace-nowrap shrink-0 transition-colors ${isFeature ? 'w-full sm:w-auto' : ''}`}
                  style={{ background: 'var(--terra)', color: 'var(--paper-hi)' }}
                >
                  {bestOffer.price > 0 ? 'See price' : 'Check price'} at {bestOffer.merchant}
                  <ArrowUpRight size={15} strokeWidth={2.25} className="shrink-0" />
                </a>
              </div>
            </div>
          )}

          {/* Other retailers — slim merchant ledger with honesty badges */}
          {otherOffers.length > 0 && (
            <div style={{ borderTop: '1px solid var(--line)' }}>
              {otherOffers.map((offer, idx) => (
                <a
                  key={`${offer.merchant}-${idx}`}
                  href={offer.affiliate_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={buyClick(offer)}
                  className="flex items-center gap-2.5 py-2.5 min-h-[44px] group"
                  style={{ borderBottom: idx < otherOffers.length - 1 ? '1px solid var(--line)' : 'none' }}
                >
                  <span className="text-xs font-semibold uppercase tracking-[0.12em] shrink-0" style={{ color: 'var(--ink)' }}>
                    {offer.merchant}
                  </span>
                  <OfferBadges offer={offer} />
                  <span className="flex-1 min-w-[8px]" />
                  {/* QA #2: prices were wrapping one character per line in the
                      squeezed mobile column — never let a price break. */}
                  <span className="font-serif text-base whitespace-nowrap shrink-0" style={{ color: 'var(--ink)' }}>
                    {offer.price > 0
                      ? `${offer.currency === 'USD' ? '$' : `${offer.currency} `}${offer.price.toFixed(2)}`
                      : 'Check price'}
                  </span>
                  <span className="text-xs font-semibold group-hover:underline underline-offset-4" style={{ color: 'var(--terra)' }}>
                    Go ↗
                  </span>
                </a>
              ))}
            </div>
          )}

          {/* Dreambeans: inline "doesn't match" refine affordance — single review
              cards only (the shortlist renders one RefineRow after the stack) */}
          {showRefine && <RefineRow productName={product_name} />}
        </div>
      </div>
    </article>
  )
}
