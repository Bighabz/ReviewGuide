'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { ExternalLink, Star, Bookmark } from 'lucide-react'
import { toggleSaved, isSaved, slugifyProduct, type SavedItem } from '@/lib/savedItems'
import { stashProductDetail } from '@/lib/productDetail'
import { useChatStatus } from '@/lib/chatStatusContext'

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
      className="relative w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
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

// Dreambeans-inspired inline refinement: a "this doesn't match — here's why"
// affordance on every card. Each chip re-frames the search relative to THIS
// product and dispatches the same `sendSuggestion` event the next_suggestions
// chips use (Message.tsx), so the existing re-rank path
// (ChatContainer.handleSuggestionClick → POST /v1/chat/stream) handles it with
// no backend or API change.
function RefineRow({ productName }: { productName: string }) {
  const [custom, setCustom] = useState('')
  // Read live streaming state so chips don't become silent dead-clicks while a
  // previous request is in flight (ChatContainer.handleSuggestionClick no-ops
  // when isStreaming — without this the user gets zero feedback).
  const { isStreaming } = useChatStatus()
  const send = (question: string) => {
    if (isStreaming) return
    const q = question.trim()
    if (!q) return
    window.dispatchEvent(new CustomEvent('sendSuggestion', { detail: { question: q } }))
  }
  // Slug keeps test ids unique even if multiple RefineRows ever co-exist.
  const slug = slugifyProduct(productName) || 'product'
  const chips = [
    { label: 'Cheaper', q: `Show me cheaper alternatives to the ${productName}` },
    { label: 'Higher-end', q: `Show me higher-end alternatives to the ${productName}` },
    { label: 'Different brand', q: `Show me options from a different brand than the ${productName}` },
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
      <form
        className="flex items-center gap-2 mt-2"
        onSubmit={(e) => { e.preventDefault(); send(`Like the ${productName}, but I also care about: ${custom}`); setCustom('') }}
      >
        <input
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          disabled={isStreaming}
          aria-label="Tell us what to change about this recommendation"
          placeholder="…or tell me what to change"
          className="flex-1 min-w-0 rounded-[12px] border border-[var(--line-2)] bg-[var(--paper)] px-3.5 py-2.5 text-[14px] leading-[20px] text-[var(--ink)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--terra)] disabled:opacity-40"
        />
        <button
          type="submit"
          disabled={!custom.trim() || isStreaming}
          className="rounded-[12px] px-3.5 py-2.5 text-[14px] font-medium transition-all disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
          style={{ background: 'var(--terra)', color: 'white' }}
        >
          Refine
        </button>
      </form>
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
  // The inline "Not quite right?" refine affordance only makes sense for a
  // single, coherent recommendation. It's suppressed in the multi-card review
  // carousel (BlockRegistry) so we don't stack one refine block per card.
  showRefine?: boolean
}

export default function ProductReview({ product, showRefine = true }: ProductReviewProps) {
  const {
    product_name,
    rating,
    summary,
    image_url,
    features,
    pros,
    cons,
    affiliate_links,
    rank,
  } = product

  const router = useRouter()
  const slug = slugifyProduct(product_name)
  const roleLabel = rank === 1 ? 'Top pick · for you' : rank ? `Pick #${rank}` : ''
  const firstLink = affiliate_links && affiliate_links[0]

  function openDetail() {
    try {
      // Basic payload (back-compat + bookmark fallback).
      sessionStorage.setItem('active_product', JSON.stringify({
        id: slug, name: product_name,
        price: firstLink?.price, imageUrl: image_url, url: firstLink?.affiliate_link,
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
        price: firstLink?.price,
        url: firstLink?.affiliate_link,
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

  return (
    <div className="rounded-[14px] p-5 shadow-rg-card" style={{ background: 'var(--paper-hi)', border: '1px solid var(--line)' }}>
      {/* Product Header with Image */}
      <div className="mb-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-shrink-0">
            <img
              src={image_url || getFallbackImage(product_name)}
              alt={product_name}
              className="w-16 h-16 sm:w-24 sm:h-24 object-contain rounded-[10px]"
              style={{ background: 'var(--paper-alt)' }}
              loading="lazy"
            />
          </div>
          <div className="w-full sm:flex-1 sm:min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                {roleLabel && (
                  <div className="uppercase mb-1" style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.08em', color: rank === 1 ? 'var(--terra)' : 'var(--ink-2)' }}>
                    {roleLabel}
                  </div>
                )}
                <button onClick={openDetail} className="text-left">
                  <h3 className="rg-serif hover:underline" style={{ fontSize: 18, lineHeight: '22px', fontWeight: 600, color: 'var(--ink)' }}>{product_name}</h3>
                </button>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {rating && rating !== 'N/A' && rating !== '0/5' && (
                  <div className="flex items-center gap-1" style={{ color: '#C08A2E' }}>
                    <Star size={14} fill="currentColor" />
                    <span className="text-sm font-medium">{rating}</span>
                  </div>
                )}
                <SaveToggle item={{ id: slug, name: product_name, price: firstLink?.price, imageUrl: image_url, url: firstLink?.affiliate_link, role: roleLabel }} />
              </div>
            </div>
            {summary && (
              <p className="rg-serif mt-2" style={{ fontSize: 14, lineHeight: '20px', color: 'var(--ink-2)' }}>{summary}</p>
            )}
          </div>
        </div>
      </div>

      {/* Features */}
      {features && features.length > 0 && (
        <div className="mb-4">
          <h4 className="rg-eyebrow mb-2">What matters here</h4>
          <ul className="list-disc list-inside space-y-1">
            {features.map((feature, idx) => (
              <li key={idx} className="text-sm text-[var(--text-secondary)]">{feature}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Pros and Cons */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        {/* Pros — blueprint HONEST NOTES: + in terra */}
        {pros && pros.length > 0 && (
          <div>
            <h4 className="rg-eyebrow mb-2">The good</h4>
            <ul className="space-y-2">
              {pros.map((pro, idx) => (
                <li key={idx} className="rg-serif flex items-start gap-2" style={{ fontSize: 14, lineHeight: '20px', color: 'var(--ink)' }}>
                  <span className="mt-0.5" style={{ color: 'var(--terra)' }}>+</span>
                  <span>{pro.description}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Cons — blueprint: em-dash in ink2 */}
        {cons && cons.length > 0 && (
          <div>
            <h4 className="rg-eyebrow mb-2">The catch</h4>
            <ul className="space-y-2">
              {cons.map((con, idx) => (
                <li key={idx} className="rg-serif flex items-start gap-2" style={{ fontSize: 14, lineHeight: '20px', color: 'var(--ink-2)' }}>
                  <span className="mt-0.5">&#8212;</span>
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
          <h4 className="rg-eyebrow mb-3">Where to buy</h4>
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
                    {link.below_budget_floor && (
                      <span
                        data-testid="under-budget-badge"
                        className="uppercase px-1.5 py-0.5 rounded-full whitespace-nowrap"
                        style={{
                          fontSize: 10,
                          fontWeight: 600,
                          letterSpacing: '0.06em',
                          color: 'var(--terra)',
                          background: 'var(--paper-alt)',
                          border: '1px solid var(--line)',
                        }}
                      >
                        Under budget
                      </span>
                    )}
                    {link.condition_label && (
                      <span
                        data-testid="condition-badge"
                        className="uppercase px-1.5 py-0.5 rounded-full whitespace-nowrap"
                        style={{
                          fontSize: 10,
                          fontWeight: 600,
                          letterSpacing: '0.06em',
                          color: 'var(--ink-2)',
                          background: 'var(--paper-alt)',
                          border: '1px solid var(--line)',
                        }}
                      >
                        {link.condition_label}
                      </span>
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

      {/* Dreambeans: inline "doesn't match" refine affordance — single review
          cards only (suppressed in the carousel to avoid one block per card) */}
      {showRefine && <RefineRow productName={product_name} />}
    </div>
  )
}
