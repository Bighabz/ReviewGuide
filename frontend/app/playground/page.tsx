'use client'

/**
 * /playground — Fable 5 UX prototype (see FABLE_UX_CRITIQUE.md at repo root).
 *
 * Renders the CURRENT components and the PROPOSED redesign from the same
 * fixture data, side by side, with a light/dark toggle. Fully local — no
 * backend needed. Production code is untouched; everything proposed lives
 * in components/_playground/.
 *
 * Verify at 375px / 768px / 1280px via browser devtools (Ctrl+Shift+M).
 */

import { useEffect, useState } from 'react'
import { Moon, Sun, ExternalLink } from 'lucide-react'

// Current production components (rendered as-is for comparison)
import ProductCards from '@/components/ProductCards'
import ProductCarousel from '@/components/ProductCarousel'
import InlineProductCard from '@/components/InlineProductCard'
import AffiliateLinks from '@/components/AffiliateLinks'
import DiscoverSearchBar from '@/components/discover/DiscoverSearchBar'
import CategoryChipRow from '@/components/discover/CategoryChipRow'
import TrendingCards from '@/components/discover/TrendingCards'

// Proposed redesign
import VerdictList, { VerdictRail, VerdictLedger, OfferLedger } from '@/components/_playground/proposed/VerdictList'
import FrontPage from '@/components/_playground/proposed/FrontPage'
import SectionOpener from '@/components/_playground/proposed/SectionOpener'

// Shared fixtures
import {
  shortlistProducts,
  carouselItems,
  inlineProducts,
  affiliateLinksFixture,
  SHORTLIST_QUERY,
} from '@/components/_playground/fixtures'

/* ── Scaffolding ── */

function ThemeToggle() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  useEffect(() => {
    setTheme((document.documentElement.getAttribute('data-theme') as 'light' | 'dark') || 'light')
  }, [])
  const toggle = () => {
    const next = theme === 'light' ? 'dark' : 'light'
    document.documentElement.setAttribute('data-theme', next)
    try {
      localStorage.setItem('theme', next)
    } catch {}
    setTheme(next)
  }
  return (
    <button
      onClick={toggle}
      className="inline-flex items-center gap-2 h-9 px-3.5 rounded-md text-xs font-semibold shrink-0"
      style={{ background: 'var(--accent)', color: '#FFF8F4' }}
      aria-label="Toggle light/dark theme"
    >
      {theme === 'light' ? <Moon size={14} /> : <Sun size={14} />}
      {theme === 'light' ? 'Dark' : 'Light'}
    </button>
  )
}

/** Labeled specimen frame: CURRENT (muted) vs PROPOSED (accent) */
function Specimen({ kind, note, children }: { kind: 'current' | 'proposed'; note?: string; children: React.ReactNode }) {
  const isProposed = kind === 'proposed'
  return (
    <div>
      <div className="flex items-baseline gap-3 mb-3">
        <span
          className="text-[10px] font-bold uppercase tracking-[0.22em] px-2 py-1 rounded-sm"
          style={
            isProposed
              ? { background: 'var(--accent-light)', color: 'var(--accent)' }
              : { background: 'var(--surface-hover)', color: 'var(--text-muted)' }
          }
        >
          {isProposed ? 'Proposed' : 'Current'}
        </span>
        {note && (
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {note}
          </span>
        )}
      </div>
      <div
        className="rounded-lg p-4 sm:p-6"
        style={{
          border: isProposed ? '1px solid var(--accent-light)' : '1px dashed var(--border-strong)',
          background: 'var(--background)',
        }}
      >
        {children}
      </div>
    </div>
  )
}

function SectionHeader({ index, title, dek, id }: { index: string; title: string; dek: string; id: string }) {
  return (
    <header id={id} className="pt-16 sm:pt-24 mb-8 scroll-mt-24">
      <div className="flex items-baseline gap-4">
        <span className="font-serif italic text-4xl sm:text-5xl leading-none" style={{ color: 'var(--accent)' }}>
          {index}
        </span>
        <div className="flex-1 min-w-0">
          <h2 className="font-serif text-2xl sm:text-4xl tracking-tight" style={{ color: 'var(--text)' }}>
            {title}
          </h2>
          <p className="text-sm sm:text-base mt-2 max-w-2xl leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            {dek}
          </p>
        </div>
      </div>
      <div className="editorial-rule mt-6" />
    </header>
  )
}

const NAV = [
  { id: 'cards', label: '1 · Cards' },
  { id: 'discover', label: '2 · Discover' },
  { id: 'category', label: '3 · Category' },
]

/* ── Page ── */

export default function PlaygroundPage() {
  return (
    <div className="min-h-full" style={{ background: 'var(--background)', color: 'var(--text)' }}>
      {/* Sticky toolbar */}
      <div
        className="sticky top-0 z-40 glass"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center gap-3 sm:gap-5">
          <p className="font-serif italic text-base sm:text-lg shrink-0" style={{ color: 'var(--text)' }}>
            The Playground
          </p>
          <nav className="flex items-center gap-1 sm:gap-2 overflow-x-auto scrollbar-hide">
            {NAV.map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                className="text-xs font-semibold whitespace-nowrap px-2.5 py-2 rounded-md hover:underline underline-offset-4"
                style={{ color: 'var(--text-secondary)' }}
              >
                {item.label}
              </a>
            ))}
          </nav>
          <span className="flex-1" />
          <span className="hidden lg:block text-[11px]" style={{ color: 'var(--text-muted)' }}>
            Resize to 375 / 768 / 1280 px
          </span>
          <ThemeToggle />
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 pb-24">
        {/* Intro */}
        <header className="pt-10 sm:pt-14">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em]" style={{ color: 'var(--accent)' }}>
            Fable 5 · UX prototype · fixtures only, no backend
          </p>
          <h1 className="font-serif tracking-tight mt-3" style={{ fontSize: 'clamp(2rem, 5vw, 3.25rem)', lineHeight: 1.1 }}>
            Current vs. proposed, from the same data.
          </h1>
          <p className="text-sm sm:text-base mt-4 max-w-2xl leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            Every pair below renders the production component and its proposed replacement from identical
            fixture payloads (the exact <code className="text-xs">ui_blocks</code> product contract,
            including a missing-image case). The argument for each decision is in{' '}
            <code className="text-xs">FABLE_UX_CRITIQUE.md</code>. Flip the theme — the differences get louder in the dark.
          </p>
        </header>

        {/* ════ Section 1 — Chat product cards ════ */}
        <SectionHeader
          id="cards"
          index="1"
          title="The product cards"
          dek={`The payload for “${SHORTLIST_QUERY}”. One card system replaces six components: rank as serif typography, a real Top Pick treatment driven by badge data, FOR/AGAINST ledgers, and terracotta reserved for the one action that earns revenue.`}
        />

        <div className="space-y-10">
          <Specimen kind="current" note="ProductCards.tsx — the ranked answer today: prose pros/cons, text-link CTA, rating dropped, image hidden when missing">
            <ProductCards products={shortlistProducts as any} />
          </Specimen>

          <Specimen kind="proposed" note="VerdictList — feature card for the winner, standard cards for the field; #4 shows the designed missing-image monogram">
            <VerdictList products={shortlistProducts} title="Noise-cancelling headphones" context="Five contenders under $400, judged on cancellation, comfort and battery across 38 sources." />
          </Specimen>

          <div className="editorial-rule" />

          <Specimen kind="current" note="ProductCarousel.tsx — picks #2–5 hidden behind chevrons; emoji placeholder on slow/missing images">
            <ProductCarousel items={carouselItems} title="Top Noise-Cancelling Headphones" />
          </Specimen>

          <Specimen kind="proposed" note="VerdictRail — for overflow only (“also considered”), native scroll-snap, no carousel state">
            <VerdictRail products={shortlistProducts} title="Also considered" />
          </Specimen>

          <div className="editorial-rule" />

          <Specimen kind="current" note="InlineProductCard.tsx — position-based 🏆⚡✨ badges, 12px “Buy on Amazon” link">
            <InlineProductCard products={inlineProducts} />
          </Specimen>

          <Specimen kind="proposed" note="VerdictLedger — serif numerals, badge data from the backend, 44px price targets">
            <VerdictLedger products={shortlistProducts.slice(0, 3)} />
          </Specimen>

          <div className="editorial-rule" />

          <Specimen kind="current" note="AffiliateLinks.tsx — “Where to buy” box">
            <AffiliateLinks
              productName={affiliateLinksFixture.product_name}
              affiliateLinks={affiliateLinksFixture.affiliate_links}
              rank={affiliateLinksFixture.rank}
            />
          </Specimen>

          <Specimen kind="proposed" note="OfferLedger — merchant ledger with a Best price marker, prices in serif">
            <OfferLedger productName={affiliateLinksFixture.product_name} offers={affiliateLinksFixture.affiliate_links} />
          </Specimen>
        </div>

        {/* ════ Section 2 — Discover homepage ════ */}
        <SectionHeader
          id="discover"
          index="2"
          title="The Discover homepage"
          dek="From chatbot lobby to magazine front page: identity-first masthead, the category index finally on the homepage, and trending rebuilt with a lead story instead of six identical rows."
        />

        <div className="space-y-10">
          <Specimen kind="current" note="app/page.tsx — search-only hero, chips that fire chat queries, templated trending rows; no path to /browse anywhere">
            <div className="flex flex-col pb-6 px-2 sm:px-4">
              <div className="flex flex-col items-center pt-8 pb-8">
                <h1 className="font-serif text-2xl sm:text-3xl md:text-4xl text-center leading-tight tracking-tight" style={{ color: 'var(--text)' }}>
                  What are you <span className="italic" style={{ color: 'var(--primary)' }}>researching</span> today?
                </h1>
                <p className="text-sm text-center mt-3 max-w-md" style={{ color: 'var(--text-secondary)' }}>
                  Expert reviews, real data, zero fluff.
                </p>
                <div className="w-full max-w-xl mx-auto mt-8">
                  <DiscoverSearchBar />
                </div>
              </div>
              <div className="mt-8">
                <CategoryChipRow hasHistory={false} />
              </div>
              <div className="mt-10">
                <TrendingCards />
              </div>
            </div>
          </Specimen>

          <Specimen kind="proposed" note="FrontPage — MastheadHero + CategoryIndex (the structural fix) + Today’s Briefing">
            <FrontPage />
          </Specimen>
        </div>

        {/* ════ Section 3 — Category browse page ════ */}
        <SectionHeader
          id="category"
          index="3"
          title="The category page"
          dek="From text-on-photo overlay to a magazine section opener: split hero with a framed photo, a featured “start here” question, and other categories as an honest colophon."
        />

        <div className="space-y-10">
          <Specimen kind="current" note="app/browse/[category]/page.tsx — open the live page for comparison (it renders inside the full browse layout)">
            <a
              href="/browse/electronics"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-sm font-semibold hover:underline underline-offset-4"
              style={{ color: 'var(--primary)' }}
            >
              Open /browse/electronics in a new tab <ExternalLink size={14} />
            </a>
            <p className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
              What to notice: img + black gradient hero with white text on the photo, a flat 2×2 question
              grid with no lead, and 200px “other category” micro-cards.
            </p>
          </Specimen>

          <Specimen kind="proposed" note="SectionOpener — same data from categoryConfig.ts, restructured">
            <SectionOpener slug="electronics" />
          </Specimen>
        </div>

        {/* Footer */}
        <footer className="mt-20 pt-6 text-center" style={{ borderTop: '1px solid var(--border)' }}>
          <p className="font-serif italic text-sm" style={{ color: 'var(--text-muted)' }}>
            Built from fixtures on branch fable/ux-prototype · production rendering untouched
          </p>
        </footer>
      </div>
    </div>
  )
}
