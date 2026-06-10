'use client'

/**
 * Block Registry & UIBlocks Dispatcher
 *
 * Registry-driven renderer that maps normalized block types to their
 * corresponding React components. Replaces 14 inline renderXxx() functions
 * that were previously in Message.tsx.
 */

import type { NormalizedBlock } from '@/lib/normalizeBlocks'
import VerdictList, { VerdictRail, VerdictLedger, OfferLedger, TopPickCard } from '@/components/verdict/VerdictBlocks'
import ProductReview from '@/components/ProductReview'
import ProductRecommendations from '@/components/ProductRecommendations'
import HotelCards from '@/components/HotelCards'
import FlightCards from '@/components/FlightCards'
import ItineraryView from '@/components/ItineraryView'
import ComparisonTable from '@/components/ComparisonTable'
import ListBlock from '@/components/ListBlock'
import DestinationInfo from '@/components/DestinationInfo'
import CarRentalCard from '@/components/CarRentalCard'
// NOTE: ReviewSources + SourceCitations removed (PR #9). They rendered
// review-site names as user-visible badges, contradicting tone.md's
// "No source citations. Synthesize." rule. Backend no longer emits
// `review_sources` ui_blocks. ReviewConsensus is their tone-compliant
// successor: synthesized comparison prose + aggregate ratings, no sources.
import ReviewConsensus from '@/components/ReviewConsensus'
import PriceComparison from '@/components/PriceComparison'
import { RefineRow } from '@/components/ProductReview'
import DOMPurify from 'dompurify'

/** Each renderer receives the normalized block and returns JSX or null */
type BlockRenderer = (block: NormalizedBlock) => JSX.Element | null

const BLOCK_RENDERERS: Record<string, BlockRenderer> = {
    carousel: (b) => (
        <VerdictRail products={(b.data as any)?.items ?? b.data ?? []} title={b.title} />
    ),
    products: (b) => {
        // Handle both array format and {products: [...]} object format;
        // normalizeProduct inside VerdictRail merges best_offer/legacy fields.
        const rawItems = Array.isArray(b.data) ? b.data : (b.data as any)?.products ?? []
        return <VerdictRail products={rawItems as any[]} title={b.title} />
    },
    product_cards: (b) => (
        <VerdictList products={(b.data as any)?.products ?? []} title={b.title ?? 'The Shortlist'} />
    ),
    top_pick: (b) => <TopPickCard data={(b.data as any) ?? {}} />,
    product_review: (b) => (
        <ProductReview product={(b.data as any) ?? {}} />
    ),
    product_recommendations: (b) => (
        <ProductRecommendations content={(b.data as any)?.content ?? ''} />
    ),
    affiliate_links: (b) => (
        <OfferLedger
            productName={(b.data as any)?.product_name ?? ''}
            offers={(b.data as any)?.affiliate_links ?? []}
            rank={(b.data as any)?.rank}
        />
    ),
    hotels: (b) => <HotelCards hotels={(b.data as any[]) ?? []} />,
    flights: (b) => <FlightCards flights={(b.data as any[]) ?? []} />,
    cars: (b) => <CarRentalCard cars={(b.data as any[]) ?? []} />,
    itinerary: (b) => (
        <ItineraryView days={(b.data as any[]) ?? []} />
    ),
    product_comparison: (b) => <ComparisonTable data={b.data as any} title={b.title} />,
    // Review-grounded comparison rows (rating + review count + consensus per
    // product). Emitted instead of comparison_html when review data exists.
    review_consensus: (b) => <ReviewConsensus data={(b.data as any) ?? { products: [] }} title={b.title} />,
    comparison_html: (b) => {
        const html = DOMPurify.sanitize((b.data as any)?.html ?? '', {
            ADD_TAGS: ['style'],
            ADD_ATTR: ['target', 'rel'],
        })
        return (
            <div
                className="comparison-html-container rounded-xl overflow-x-auto shadow-card border border-[var(--border)] max-w-full"
                style={{ background: 'var(--surface)' }}
                dangerouslySetInnerHTML={{ __html: html }}
            />
        )
    },
    activities: (b) => (
        <ListBlock title={b.title ?? 'Things to Do'} items={(b.data as string[]) ?? []} type="activities" />
    ),
    attractions: (b) => (
        <ListBlock title={b.title ?? 'Must-See Attractions'} items={(b.data as string[]) ?? []} type="attractions" />
    ),
    restaurants: (b) => (
        <ListBlock title={b.title ?? 'Recommended Restaurants'} items={(b.data as string[]) ?? []} type="restaurants" />
    ),
    destination_info: (b) => <DestinationInfo data={(b.data as any) ?? {}} />,
    inline_product_card: (b) => (
        <VerdictLedger products={(b.data as any)?.products ?? []} />
    ),
    price_comparison: (b) => (
        <div>
            <PriceComparison items={(b.data as any[]) ?? []} title={b.title} />
            <p className="text-xs text-[var(--text-muted)] mt-3 px-1">
                Disclosure: We may earn commissions from qualifying purchases.
            </p>
        </div>
    ),
    conclusion: (b) => (
        <div className="mt-4 px-3 sm:px-4 py-3 rounded-2xl rounded-tl-md bg-[var(--surface-elevated)] border border-[var(--border)] text-[14px] sm:text-[15px] leading-relaxed text-[var(--text)]">
            {(b.data as any)?.text}
        </div>
    ),
}

interface UIBlocksProps {
    blocks: NormalizedBlock[]
    /** Direct itinerary data from message.itinerary (legacy format) */
    itinerary?: any[]
}

export function UIBlocks({ blocks, itinerary }: UIBlocksProps) {
    // Group hotels + flights together for side-by-side layout
    const hasHotels = blocks.some(b => b.type === 'hotels')
    const hasFlights = blocks.some(b => b.type === 'flights')
    const showTravelGrid = hasHotels && hasFlights

    // Track whether grouped blocks have been rendered
    let travelGridRendered = false
    let productReviewCarouselRendered = false

    // Collect product_review blocks for carousel grouping
    const productReviewBlocks = blocks.filter(b => b.type === 'product_review')
    const hasMultipleReviews = productReviewBlocks.length > 1

    const elements: (JSX.Element | null)[] = blocks.map((block, idx) => {
        // Side-by-side travel grid
        if (showTravelGrid && (block.type === 'hotels' || block.type === 'flights')) {
            if (!travelGridRendered) {
                travelGridRendered = true
                const hotelBlocks = blocks.filter(b => b.type === 'hotels')
                const flightBlocks = blocks.filter(b => b.type === 'flights')
                return (
                    <div key={`travel-grid-${idx}`}>
                        {/* Desktop: side by side grid with equal height */}
                        <div className="hidden md:grid md:grid-cols-2 gap-4 items-stretch">
                            <div className="flex flex-col">
                                {hotelBlocks.map((b, i) => <HotelCards key={i} hotels={(b.data as any[]) ?? []} fullHeight />)}
                            </div>
                            <div className="flex flex-col">
                                {flightBlocks.map((b, i) => <FlightCards key={i} flights={(b.data as any[]) ?? []} fullHeight />)}
                            </div>
                        </div>
                        {/* Mobile: stacked vertically */}
                        <div className="md:hidden space-y-4">
                            {hotelBlocks.map((b, i) => <HotelCards key={`hm-${i}`} hotels={(b.data as any[]) ?? []} />)}
                            {flightBlocks.map((b, i) => <FlightCards key={`fm-${i}`} flights={(b.data as any[]) ?? []} />)}
                        </div>
                    </div>
                )
            }
            return null // already rendered in grid above
        }

        // Group product_review blocks into the stacked Shortlist (feature card
        // for rank #1, standard cards for the field) — replaced the swipe
        // carousel 2026-06-10: no picks hidden behind chevrons. One RefineRow
        // closes the stack (the refine contract operates on the whole list).
        if (block.type === 'product_review' && hasMultipleReviews) {
            if (!productReviewCarouselRendered) {
                productReviewCarouselRendered = true
                const sorted = [...productReviewBlocks].sort(
                    (a, b) => ((a.data as any)?.rank ?? 99) - ((b.data as any)?.rank ?? 99)
                )
                const firstName = (sorted[0]?.data as any)?.product_name ?? 'product'
                return (
                    <section key={`product-shortlist-${idx}`} className="w-full">
                        <header className="mb-4">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] mb-1.5" style={{ color: 'var(--terra)' }}>
                                The Shortlist · {sorted.length} contender{sorted.length === 1 ? '' : 's'}
                            </p>
                            <div className="editorial-rule" />
                        </header>
                        <div className="space-y-4">
                            {sorted.map((b, i) => (
                                <ProductReview key={`review-${i}`} product={(b.data as any) ?? {}} showRefine={false} />
                            ))}
                        </div>
                        <RefineRow productName={firstName} />
                    </section>
                )
            }
            return null // already rendered in the shortlist above
        }

        // Find renderer — check exact match first, then _products wildcard
        const renderer = BLOCK_RENDERERS[block.type] ??
            (block.type?.endsWith('_products') ? BLOCK_RENDERERS['products'] : null)

        if (!renderer) return null

        return <div key={`block-${block.type}-${idx}`}>{renderer(block)}</div>
    })

    // Handle legacy direct itinerary field (message.itinerary)
    if (itinerary && itinerary.length > 0 && !blocks.some(b => b.type === 'itinerary')) {
        elements.push(
            <div key="legacy-itinerary">
                <ItineraryView days={itinerary} />
            </div>
        )
    }

    // Filter nulls and check if there's anything to render
    const filtered = elements.filter(Boolean)
    if (filtered.length === 0) return null

    return (
        <div className="space-y-6 mt-4 w-full">
            {filtered}
        </div>
    )
}
