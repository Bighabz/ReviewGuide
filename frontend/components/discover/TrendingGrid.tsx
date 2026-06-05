'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { DISCOVER_TOPICS, type DiscoverTopic } from '@/lib/discoverTopics'

/**
 * Returns a rotated subset of topics. SSR + first client paint = the first
 * `count` in array order (deterministic → no hydration mismatch); the client
 * shuffles the full pool on mount and shows a fresh `count`. Mirrors
 * HeroSubline.tsx — never call Math.random() during render.
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

/**
 * Discover "Popular this week" — a 2-up vertical grid of topic posters
 * (8 per visit, freshly rotated). Replaced the horizontal carousel. Each card
 * is browse-only: a tap opens the topic's /topic/[slug] blog page, where the
 * "Research this in chat" CTA enters a new session with that context.
 * Terracotta tokens only.
 */
export default function TrendingGrid() {
  const router = useRouter()
  const topics = useRotatedTopics(8)

  return (
    <div>
      {/* Section header — blueprint eyebrow */}
      <div className="flex items-center justify-between mb-3">
        <div className="rg-eyebrow">Popular this week</div>
      </div>

      {/* 2-up grid (4 rows × 2 = 8) on mobile/tablet; 4-up (2 rows × 4) on desktop.
          Scrolls with the page. Cards are 4:5 posters below lg and squares on
          desktop — square keeps the row short enough that a slice of the second
          row shows above the fold (the "scroll for more" cue). */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {topics.map((topic) => (
          <button
            key={topic.slug}
            data-testid="trending-card"
            onClick={() => router.push(`/topic/${topic.slug}`)}
            aria-label={`${topic.title} — ${topic.hook}`}
            className="group relative overflow-hidden rounded-2xl text-left"
            style={{ boxShadow: 'var(--shadow-float)', border: '1px solid var(--line)', cursor: 'pointer' }}
          >
            <div className="relative aspect-[4/5] lg:aspect-square">
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
              <div className="absolute inset-x-0 bottom-0 p-3.5">
                <div
                  className="uppercase mb-1"
                  style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--terra-soft)' }}
                >
                  {topic.category}
                </div>
                <p className="rg-serif" style={{ fontSize: 17, lineHeight: '21px', fontWeight: 600, color: '#fff' }}>
                  {topic.title}
                </p>
                <p style={{ fontSize: 12, lineHeight: '16px', color: 'rgba(255,255,255,0.84)', marginTop: 2 }}>
                  {topic.hook}
                </p>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
