'use client'

/**
 * FrontPage — the proposed Discover homepage: a magazine front page.
 *   MastheadHero    — identity-first hero with a real search input
 *   CategoryIndex   — all categories ON the homepage as a numbered table of contents
 *   TodaysBriefing  — trending with editorial hierarchy: one lead story + dateline list
 */

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowRight, Search } from 'lucide-react'
import { categories } from '@/lib/categoryConfig'
import { briefingStories } from '../fixtures'

const STARTER_QUERIES = [
  'Best noise-cancelling headphones under $400',
  'Dyson vs Shark — which vacuum wins?',
  'When to book flights to Japan',
]

export function MastheadHero() {
  const router = useRouter()
  const [query, setQuery] = useState('')
  const submit = () => {
    const q = query.trim()
    router.push(q ? `/chat?q=${encodeURIComponent(q)}&new=1` : '/chat?new=1')
  }

  return (
    <header className="pt-12 sm:pt-20 pb-12 sm:pb-16 text-center px-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.24em] mb-5" style={{ color: 'var(--accent)' }}>
        Independent buying advice · Researched live
      </p>
      <h1
        className="font-serif tracking-tight text-balance mx-auto max-w-3xl"
        style={{ color: 'var(--text)', fontSize: 'clamp(2.25rem, 6vw, 4rem)', lineHeight: 1.08 }}
      >
        Ask before <em style={{ color: 'var(--accent)' }}>you buy.</em>
      </h1>
      <p className="text-base sm:text-lg mt-5 max-w-xl mx-auto" style={{ color: 'var(--text-secondary)' }}>
        We read the reviews — Wirecutter, RTINGS, Reddit, the lot — so you get a straight answer with receipts.
      </p>

      {/* Real input, terracotta submit */}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
        className="mt-9 mx-auto max-w-xl flex items-center gap-2 rounded-md p-1.5 pl-4 shadow-editorial"
        style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border)' }}
      >
        <Search size={18} style={{ color: 'var(--text-muted)' }} className="shrink-0" aria-hidden="true" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Best espresso machine under $500…"
          aria-label="Ask a product research question"
          className="flex-1 min-w-0 bg-transparent text-[15px] outline-none h-11"
          style={{ color: 'var(--text)' }}
        />
        <button
          type="submit"
          className="h-11 px-5 rounded-md text-sm font-semibold shrink-0 transition-colors"
          style={{ background: 'var(--accent)', color: '#FFF8F4' }}
        >
          Ask
        </button>
      </form>

      {/* Starter queries set as citations, not chips */}
      <p className="mt-5 text-[13px] flex flex-wrap justify-center gap-x-5 gap-y-1.5" style={{ color: 'var(--text-muted)' }}>
        <span className="uppercase tracking-[0.16em] text-[10px] font-semibold self-center">Try</span>
        {STARTER_QUERIES.map((q) => (
          <button
            key={q}
            onClick={() => router.push(`/chat?q=${encodeURIComponent(q)}&new=1`)}
            className="italic font-serif hover:underline underline-offset-4 decoration-1"
            style={{ color: 'var(--text-secondary)' }}
          >
            “{q}”
          </button>
        ))}
      </p>
    </header>
  )
}

/** The structural fix: categories on the homepage, as a table of contents */
export function CategoryIndex() {
  const router = useRouter()
  return (
    <section className="px-4">
      <div className="flex items-baseline gap-4 mb-6">
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em]" style={{ color: 'var(--accent)' }}>
          The Index
        </p>
        <div className="editorial-rule flex-1 self-center" />
        <p className="text-[11px] uppercase tracking-[0.14em]" style={{ color: 'var(--text-muted)' }}>
          {categories.length} sections
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-10">
        {categories.map((cat, i) => (
          <button
            key={cat.slug}
            onClick={() => router.push(`/browse/${cat.slug}`)}
            className="group flex items-center gap-4 py-3.5 text-left min-h-[64px]"
            style={{ borderBottom: '1px solid var(--border)' }}
          >
            <span className="font-serif italic text-xl w-8 shrink-0 text-right" style={{ color: 'var(--border-strong)' }}>
              {String(i + 1).padStart(2, '0')}
            </span>
            <span
              className="w-12 h-12 rounded-md overflow-hidden shrink-0"
              style={{ background: 'var(--surface)' }}
            >
              <img src={cat.image} alt="" loading="lazy" className="w-full h-full object-cover" />
            </span>
            <span className="flex-1 min-w-0">
              <span className="block font-serif text-lg leading-tight group-hover:underline underline-offset-4 decoration-1" style={{ color: 'var(--text)' }}>
                {cat.name}
              </span>
              <span className="block text-xs truncate mt-0.5" style={{ color: 'var(--text-muted)' }}>
                {cat.tagline}
              </span>
            </span>
            <ArrowRight
              size={15}
              className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
              style={{ color: 'var(--accent)' }}
              aria-hidden="true"
            />
          </button>
        ))}
      </div>
    </section>
  )
}

/** Trending, rebuilt with hierarchy: one lead story + a numbered dateline list */
export function TodaysBriefing() {
  const router = useRouter()
  const [lead, ...rest] = briefingStories
  return (
    <section className="px-4">
      <div className="flex items-baseline gap-4 mb-6">
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em]" style={{ color: 'var(--accent)' }}>
          Today’s Briefing
        </p>
        <div className="editorial-rule flex-1 self-center" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
        {/* Lead story */}
        <button
          onClick={() => router.push(`/chat?q=${encodeURIComponent(lead.query)}&new=1`)}
          className="lg:col-span-3 group text-left rounded-md overflow-hidden shadow-editorial"
          style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border)' }}
        >
          <span className="block aspect-[16/9] overflow-hidden" style={{ background: 'var(--surface)' }}>
            <img
              src={lead.image}
              alt=""
              loading="lazy"
              className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-500"
            />
          </span>
          <span className="block p-5 sm:p-6">
            <span className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--accent)' }}>
              {lead.kicker}
            </span>
            <span className="block font-serif text-2xl sm:text-[1.7rem] leading-tight tracking-tight mt-2 group-hover:underline underline-offset-4 decoration-1" style={{ color: 'var(--text)' }}>
              {lead.title}
            </span>
            <span className="block text-sm mt-2 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              {lead.dek}
            </span>
          </span>
        </button>

        {/* Dateline list */}
        <div className="lg:col-span-2 flex flex-col" style={{ borderTop: '1px solid var(--border)' }}>
          {rest.map((story, i) => (
            <button
              key={story.title}
              onClick={() => router.push(`/chat?q=${encodeURIComponent(story.query)}&new=1`)}
              className="group flex items-start gap-4 py-4 text-left flex-1 min-h-[64px]"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <span className="font-serif italic text-2xl w-7 shrink-0 leading-none" style={{ color: 'var(--border-strong)' }}>
                {i + 2}
              </span>
              <span className="flex-1 min-w-0">
                <span className="text-[10px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--accent)' }}>
                  {story.kicker}
                </span>
                <span className="block font-serif text-[17px] leading-snug mt-0.5 group-hover:underline underline-offset-4 decoration-1" style={{ color: 'var(--text)' }}>
                  {story.title}
                </span>
                <span className="block text-xs mt-1 leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                  {story.dek}
                </span>
              </span>
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}

export default function FrontPage() {
  return (
    <div className="space-y-14 sm:space-y-20 pb-8">
      <MastheadHero />
      <CategoryIndex />
      <TodaysBriefing />
    </div>
  )
}
