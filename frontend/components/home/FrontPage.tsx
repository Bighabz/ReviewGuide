'use client'

/**
 * FrontPage — the Discover homepage as a magazine front page.
 *   MastheadHero    — the brand's animated logo as the masthead + a REAL search input
 *   CategoryIndex   — all categories on the homepage as a numbered table of contents
 *   TodaysBriefing  — Discover topics with editorial hierarchy: one lead story +
 *                     dateline list, all routing to /topic/[slug] landing pages
 *
 * Terracotta tokens only (the semantic --accent vars resolve to --terra).
 */

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowRight, Search } from 'lucide-react'
import DiscoverHeroLogo from '@/components/DiscoverHeroLogo'
import { PLACEHOLDER_EXAMPLES } from '@/components/discover/DiscoverSearchBar'
import { categories } from '@/lib/categoryConfig'
import { DISCOVER_TOPICS, type DiscoverTopic } from '@/lib/discoverTopics'

/** SSR-deterministic rotation (mirrors TrendingGrid/HeroSubline — no Math.random in render) */
function useRotated<T>(pool: readonly T[], count: number): T[] {
  const [items, setItems] = useState<T[]>(() => pool.slice(0, count))
  useEffect(() => {
    const shuffled = [...pool]
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1))
      ;[shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
    }
    setItems(shuffled.slice(0, count))
  }, [pool, count])
  return items
}

export function MastheadHero() {
  const router = useRouter()
  const [query, setQuery] = useState('')
  const examples = useRotated(PLACEHOLDER_EXAMPLES, 2)
  const submit = () => {
    const q = query.trim()
    router.push(q ? `/chat?q=${encodeURIComponent(q)}&new=1` : '/chat?new=1')
  }

  return (
    <header className="pt-[56px] md:pt-10 pb-10 sm:pb-14 text-center px-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.24em] mb-4" style={{ color: 'var(--accent)' }}>
        Independent buying advice · Researched live
      </p>

      {/* The brand mark IS the masthead — the existing animated hero logo */}
      <div className="w-full max-w-[280px] md:max-w-[340px] mx-auto">
        <DiscoverHeroLogo width={340} />
      </div>

      <p className="text-base sm:text-lg mt-4 max-w-xl mx-auto" style={{ color: 'var(--text-secondary)' }}>
        We read the reviews — Wirecutter, RTINGS, Reddit, the lot — so you get a straight answer with receipts.
      </p>

      {/* Real input, terracotta submit */}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
        className="mt-7 mx-auto max-w-xl flex items-center gap-2 rounded-md p-1.5 pl-4 shadow-editorial"
        style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border)' }}
      >
        <Search size={18} style={{ color: 'var(--text-muted)' }} className="shrink-0" aria-hidden="true" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={`Ask anything — ${examples.join(', ')}…`}
          aria-label="Ask a product research question"
          className="flex-1 min-w-0 bg-transparent text-[15px] outline-none h-11"
          style={{ color: 'var(--text)' }}
        />
        <button
          type="submit"
          className="h-11 px-5 rounded-md text-sm font-semibold shrink-0 transition-colors"
          style={{ background: 'var(--accent)', color: 'var(--surface-elevated)' }}
        >
          Ask
        </button>
      </form>
    </header>
  )
}

/** All categories on the homepage, as a numbered table of contents */
export function CategoryIndex() {
  const router = useRouter()
  return (
    <section id="the-index" className="px-4 scroll-mt-20">
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
            <span className="w-12 h-12 rounded-md overflow-hidden shrink-0" style={{ background: 'var(--surface)' }}>
              <img src={cat.image} alt="" loading="lazy" className="w-full h-full object-cover" />
            </span>
            <span className="flex-1 min-w-0">
              <span
                className="block font-serif text-lg leading-tight group-hover:underline underline-offset-4 decoration-1"
                style={{ color: 'var(--text)' }}
              >
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

/** Discover topics with hierarchy: one lead story + a numbered dateline list → /topic/[slug] */
export function TodaysBriefing() {
  const router = useRouter()
  const topics = useRotated(DISCOVER_TOPICS, 5)
  const [lead, ...rest] = topics
  if (!lead) return null

  const open = (topic: DiscoverTopic) => router.push(`/topic/${topic.slug}`)

  return (
    <section className="px-4">
      <div className="flex items-baseline gap-4 mb-6">
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em]" style={{ color: 'var(--accent)' }}>
          Today’s Briefing
        </p>
        <div className="editorial-rule flex-1 self-center" />
        <p className="text-[11px] uppercase tracking-[0.14em]" style={{ color: 'var(--text-muted)' }}>
          Fresh each visit
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
        {/* Lead story */}
        <button
          onClick={() => open(lead)}
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
              {lead.category}
            </span>
            <span
              className="block font-serif text-2xl sm:text-[1.7rem] leading-tight tracking-tight mt-2 group-hover:underline underline-offset-4 decoration-1"
              style={{ color: 'var(--text)' }}
            >
              {lead.title}
            </span>
            <span className="block text-sm mt-2 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              {lead.blurb}
            </span>
          </span>
        </button>

        {/* Dateline list */}
        <div className="lg:col-span-2 flex flex-col" style={{ borderTop: '1px solid var(--border)' }}>
          {rest.map((topic, i) => (
            <button
              key={topic.slug}
              onClick={() => open(topic)}
              className="group flex items-start gap-4 py-4 text-left flex-1 min-h-[64px]"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <span className="font-serif italic text-2xl w-7 shrink-0 leading-none" style={{ color: 'var(--border-strong)' }}>
                {i + 2}
              </span>
              <span className="flex-1 min-w-0">
                <span className="text-[10px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--accent)' }}>
                  {topic.category}
                </span>
                <span
                  className="block font-serif text-[17px] leading-snug mt-0.5 group-hover:underline underline-offset-4 decoration-1"
                  style={{ color: 'var(--text)' }}
                >
                  {topic.title}
                </span>
                <span className="block text-xs mt-1 leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                  {topic.hook}
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
    <div className="max-w-5xl mx-auto space-y-12 sm:space-y-16 pb-24 md:pb-16">
      <MastheadHero />
      <TodaysBriefing />
      <CategoryIndex />
    </div>
  )
}
