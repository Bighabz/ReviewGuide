'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowRight, TrendingUp } from 'lucide-react'
import { cn } from '@/lib/utils'
import { DISCOVER_TOPICS, type DiscoverTopic } from '@/lib/discoverTopics'

/**
 * Returns a rotated subset of topics. SSR + first client paint = the first
 * `count` in array order (deterministic → no hydration mismatch); the client
 * shuffles the full pool on mount. Mirrors HeroSubline — never Math.random() in
 * render.
 */
function useRotatedTopics(count = 8): DiscoverTopic[] {
  const [topics, setTopics] = useState<DiscoverTopic[]>(() => DISCOVER_TOPICS.slice(0, count))
  useEffect(() => {
    const shuffled = [...DISCOVER_TOPICS]
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1))
      ;[shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
    }
    setTopics(shuffled.slice(0, count))
  }, [count])
  return topics
}

function FeaturedHeroCard({ t, size, onOpen }: { t: DiscoverTopic; size: 'large' | 'default'; onOpen: () => void }) {
  return (
    <button
      data-testid="trending-card"
      onClick={onOpen}
      aria-label={`${t.title} — ${t.hook}`}
      className={cn(
        'group relative block w-full h-full text-left overflow-hidden rounded-2xl transition-all duration-500 cursor-pointer',
        'shadow-[0_4px_24px_-8px_rgba(26,24,22,0.12),0_0_0_1px_var(--line)]',
        'hover:shadow-[0_12px_40px_-12px_rgba(26,24,22,0.2)]',
        size === 'large' ? 'aspect-[16/10]' : 'aspect-[4/3]',
      )}
    >
      <img src={t.image} alt={t.title} loading="eager" className="absolute inset-0 w-full h-full object-cover bg-[var(--paper-alt)] transition-transform duration-700 group-hover:scale-105" />
      <div className="absolute inset-0 bg-gradient-to-t from-[var(--ink)]/85 via-[var(--ink)]/30 to-transparent" />
      <div className="absolute inset-0 flex flex-col justify-end p-5 md:p-6">
        <span className="inline-flex self-start items-center px-2.5 py-1 rounded-full bg-[var(--terra-soft)]/90 backdrop-blur-sm text-[10px] font-semibold tracking-wide uppercase text-[var(--terra-ink)] mb-3 transition-transform duration-300 group-hover:-translate-y-0.5">
          {t.category}
        </span>
        <h3 className={cn('rg-serif font-semibold text-white leading-tight', size === 'large' ? 'text-2xl md:text-3xl' : 'text-lg md:text-xl')}>
          {t.title}
        </h3>
        <p className={cn('text-white/70 mt-1.5 transition-all duration-300 group-hover:text-white/90', size === 'large' ? 'text-base' : 'text-sm')}>
          {t.hook}
        </p>
        <div className="absolute bottom-5 right-5 md:bottom-6 md:right-6 w-9 h-9 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center opacity-0 translate-y-2 transition-all duration-300 group-hover:opacity-100 group-hover:translate-y-0">
          <ArrowRight size={16} className="text-white" />
        </div>
      </div>
    </button>
  )
}

function SmallCategoryCard({ t, onOpen }: { t: DiscoverTopic; onOpen: () => void }) {
  return (
    <button
      data-testid="trending-card"
      onClick={onOpen}
      aria-label={`${t.title} — ${t.hook}`}
      className="group relative block w-full text-left overflow-hidden rounded-xl aspect-[4/5] shadow-[0_2px_12px_-4px_rgba(26,24,22,0.1),0_0_0_1px_var(--line)] hover:shadow-[0_8px_24px_-8px_rgba(26,24,22,0.15)] transition-all duration-300 cursor-pointer"
    >
      <img src={t.image} alt={t.title} loading="lazy" className="absolute inset-0 w-full h-full object-cover bg-[var(--paper-alt)] transition-transform duration-500 group-hover:scale-105" />
      <div className="absolute inset-0 bg-gradient-to-t from-[var(--ink)]/80 via-[var(--ink)]/20 to-transparent" />
      <div className="absolute inset-0 flex flex-col justify-end p-3">
        <span className="text-[9px] font-semibold tracking-[0.08em] uppercase text-white/60 mb-0.5">{t.category}</span>
        <h3 className="rg-serif text-sm font-semibold text-white leading-tight line-clamp-2">{t.title}</h3>
      </div>
    </button>
  )
}

/**
 * Discover topics (design from v0). A "Trending now" feature — one large hero
 * card + 3 list cards on desktop, a horizontal snap carousel on mobile — over an
 * "Explore more" poster grid. Browse-only: a tap opens /topic/[slug].
 * Terracotta tokens only.
 */
export default function TrendingGrid() {
  const router = useRouter()
  const topics = useRotatedTopics(8)
  const open = (slug: string) => router.push(`/topic/${slug}`)
  if (topics.length === 0) return null

  const heroMain = topics[0]
  const heroSecondary = topics.slice(1, 4)
  const categoryCards = topics.slice(4)

  return (
    <div>
      {/* Trending now */}
      <div className="flex items-center gap-3 mb-5">
        <div className="flex items-center gap-2 text-[var(--terra)]">
          <TrendingUp size={14} strokeWidth={2.5} />
          <h2 className="text-[11px] font-semibold tracking-[0.1em] uppercase">Trending now</h2>
        </div>
        <div className="flex-1 h-px bg-[var(--line)]" />
      </div>

      {/* Desktop: large card + 3 list cards */}
      <div className="hidden md:grid md:grid-cols-5 md:gap-4">
        <div className="col-span-3">
          <FeaturedHeroCard t={heroMain} size="large" onOpen={() => open(heroMain.slug)} />
        </div>
        <div className="col-span-2 flex flex-col gap-4">
          {heroSecondary.map((t) => (
            <button
              key={t.slug}
              data-testid="trending-card"
              onClick={() => open(t.slug)}
              aria-label={`${t.title} — ${t.hook}`}
              className="group flex items-center gap-4 w-full text-left p-3 rounded-xl bg-[var(--paper-hi)] ring-1 ring-[var(--line)] hover:ring-[var(--terra)]/40 hover:shadow-[0_4px_20px_-4px_rgba(26,24,22,0.1)] transition-all duration-300 cursor-pointer"
            >
              <div className="relative shrink-0 w-20 h-20 rounded-lg overflow-hidden ring-1 ring-[var(--line)]">
                <img src={t.image} alt={t.title} loading="lazy" className="w-full h-full object-cover bg-[var(--paper-alt)] transition-transform duration-500 group-hover:scale-110" />
              </div>
              <div className="flex-1 min-w-0">
                <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-[var(--terra-soft)] text-[9px] font-semibold tracking-[0.06em] uppercase text-[var(--terra-ink)] mb-1.5">{t.category}</span>
                <h3 className="rg-serif text-base font-semibold text-[var(--ink)] leading-snug">{t.title}</h3>
                <p className="text-xs text-[var(--ink-3)] mt-0.5">{t.hook}</p>
              </div>
              <ArrowRight size={16} className="shrink-0 text-[var(--ink-3)] opacity-0 -translate-x-1 transition-all duration-300 group-hover:opacity-100 group-hover:translate-x-0 mr-1" />
            </button>
          ))}
        </div>
      </div>

      {/* Mobile: horizontal snap carousel */}
      <div className="md:hidden -mx-4 px-4">
        <div className="flex gap-3 overflow-x-auto pb-4 snap-x snap-mandatory scrollbar-hide">
          {[heroMain, ...heroSecondary].map((t, i) => (
            <div key={t.slug} className={cn('shrink-0 snap-start', i === 0 ? 'w-[75vw]' : 'w-[65vw]')}>
              <FeaturedHeroCard t={t} size={i === 0 ? 'large' : 'default'} onOpen={() => open(t.slug)} />
            </div>
          ))}
        </div>
      </div>

      {/* Explore more */}
      <div className="flex items-center gap-3 mb-5 mt-8">
        <h2 className="text-[11px] font-semibold tracking-[0.1em] uppercase text-[var(--ink-3)]">Explore more</h2>
        <div className="flex-1 h-px bg-[var(--line)]" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
        {categoryCards.map((t) => (
          <SmallCategoryCard key={t.slug} t={t} onOpen={() => open(t.slug)} />
        ))}
      </div>
    </div>
  )
}
