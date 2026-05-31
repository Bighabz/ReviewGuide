'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { DISCOVER_TOPICS, type DiscoverTopic } from '@/lib/discoverTopics'

/**
 * Returns a rotated subset of topics. SSR + first client paint = the first
 * `count` in array order (deterministic → no hydration mismatch); the client
 * shuffles the full pool on mount and shows a fresh `count`. Mirrors
 * HeroSubline.tsx — never call Math.random() during render.
 */
function useRotatedTopics(count = 10): DiscoverTopic[] {
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

/**
 * Netflix-style horizontally-swiping topic picker for Discover.
 *
 * - Pool of ~50 topics; a fresh rotated subset is shown each visit
 *   (SSR-stable order on first paint, shuffled on mount — see useRotatedTopics).
 * - Cards are browse-only: a tap opens the topic's /topic/[slug] landing page.
 *   The "into research" CTA lives on that page (NO chat preload here).
 * - Large feature tiles; a row of pagination dots (not a sliced card) signals
 *   "there's more to swipe" and tracks scroll position. Terracotta tokens only.
 */
export default function TrendingCarousel() {
  const router = useRouter()
  const topics = useRotatedTopics(10)
  const railRef = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(0)

  // Track which card is at the rail's left edge → drives the active dot.
  const syncActive = useCallback(() => {
    const rail = railRef.current
    if (!rail) return
    const railLeft = rail.getBoundingClientRect().left
    const cards = Array.from(rail.querySelectorAll<HTMLElement>('[data-testid="trending-card"]'))
    let nearest = 0
    let min = Infinity
    cards.forEach((c, i) => {
      const d = Math.abs(c.getBoundingClientRect().left - railLeft)
      if (d < min) {
        min = d
        nearest = i
      }
    })
    setActive((prev) => (prev === nearest ? prev : nearest))
  }, [])

  useEffect(() => {
    syncActive()
  }, [topics, syncActive])

  const goTo = (i: number) => {
    const rail = railRef.current
    if (!rail) return
    const card = rail.querySelectorAll<HTMLElement>('[data-testid="trending-card"]')[i]
    card?.scrollIntoView({ behavior: 'smooth', inline: 'start', block: 'nearest' })
  }

  return (
    <div>
      {/* Section header — blueprint eyebrow */}
      <div className="flex items-center justify-between mb-3">
        <div className="rg-eyebrow">Popular this week</div>
      </div>

      {/* Horizontal poster rail — bleeds to the screen edge, hides scrollbar */}
      <div
        ref={railRef}
        onScroll={syncActive}
        className="flex gap-3 overflow-x-auto snap-x snap-mandatory pb-1 -mx-4 px-4 sm:-mx-6 sm:px-6 md:-mx-8 md:px-8 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {topics.map((topic) => (
          <button
            key={topic.slug}
            data-testid="trending-card"
            onClick={() => router.push(`/topic/${topic.slug}`)}
            aria-label={`${topic.title} — ${topic.hook}`}
            className="group relative flex-shrink-0 snap-start w-[248px] sm:w-[288px] overflow-hidden rounded-2xl text-left"
            style={{ boxShadow: 'var(--shadow-float)', border: '1px solid var(--line)', cursor: 'pointer' }}
          >
            <div className="relative aspect-[4/5]">
              <img
                src={topic.image}
                alt={topic.title}
                loading="lazy"
                className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                style={{ background: 'var(--paper-alt)' }}
              />
              {/* Terracotta-toned gradient so the copy stays legible */}
              <div
                className="absolute inset-0"
                aria-hidden="true"
                style={{ background: 'linear-gradient(180deg, rgba(26,24,22,0) 34%, rgba(26,24,22,0.55) 66%, rgba(26,24,22,0.88) 100%)' }}
              />
              <div className="absolute inset-x-0 bottom-0 p-4">
                <div
                  className="uppercase mb-1.5"
                  style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--terra-soft)' }}
                >
                  {topic.category}
                </div>
                <p className="rg-serif" style={{ fontSize: 19, lineHeight: '23px', fontWeight: 600, color: '#fff' }}>
                  {topic.title}
                </p>
                <p style={{ fontSize: 13, lineHeight: '17px', color: 'rgba(255,255,255,0.85)', marginTop: 3 }}>
                  {topic.hook}
                </p>
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Pagination dots — the "more to swipe" affordance (no sliced card).
          Each dot has a 24px tap row; the visual pip stays small. */}
      <div className="flex justify-center items-center gap-1 mt-3">
        {topics.map((topic, i) => (
          <button
            key={topic.slug}
            onClick={() => goTo(i)}
            aria-label={`Show ${topic.title}`}
            aria-current={i === active}
            className="flex items-center justify-center h-6 px-1"
          >
            <span
              className="block rounded-full transition-all duration-200"
              style={{
                width: i === active ? 18 : 6,
                height: 6,
                background: i === active ? 'var(--terra)' : 'var(--line-2)',
              }}
            />
          </button>
        ))}
      </div>
    </div>
  )
}
