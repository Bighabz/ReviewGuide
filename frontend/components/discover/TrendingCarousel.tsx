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
function useRotatedTopics(count = 12): DiscoverTopic[] {
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
 * - Terracotta tokens only.
 */
export default function TrendingCarousel() {
  const router = useRouter()
  const topics = useRotatedTopics(12)

  return (
    <div>
      {/* Section header — blueprint eyebrow */}
      <div className="flex items-center justify-between mb-3">
        <div className="rg-eyebrow">Popular this week</div>
      </div>

      {/* Horizontal poster rail — bleeds to the screen edge, hides scrollbar */}
      <div
        className="flex gap-3 overflow-x-auto snap-x snap-mandatory pb-2 -mx-4 px-4 sm:-mx-6 sm:px-6 md:-mx-8 md:px-8 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {topics.map((topic) => (
          <button
            key={topic.slug}
            data-testid="trending-card"
            onClick={() => router.push(`/topic/${topic.slug}`)}
            aria-label={`${topic.title} — ${topic.hook}`}
            className="group relative flex-shrink-0 snap-start w-[150px] sm:w-[172px] overflow-hidden rounded-[14px] text-left"
            style={{ boxShadow: 'var(--shadow-float)', border: '1px solid var(--line)', cursor: 'pointer' }}
          >
            <div className="relative aspect-[3/4]">
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
                style={{ background: 'linear-gradient(180deg, rgba(26,24,22,0) 32%, rgba(26,24,22,0.55) 64%, rgba(26,24,22,0.85) 100%)' }}
              />
              <div className="absolute inset-x-0 bottom-0 p-3">
                <div
                  className="uppercase mb-1"
                  style={{ fontSize: 9, fontWeight: 600, letterSpacing: '0.09em', color: 'var(--terra-soft)' }}
                >
                  {topic.category}
                </div>
                <p className="rg-serif" style={{ fontSize: 14, lineHeight: '17px', fontWeight: 600, color: '#fff' }}>
                  {topic.title}
                </p>
                <p style={{ fontSize: 11, lineHeight: '14px', color: 'rgba(255,255,255,0.82)', marginTop: 2 }}>
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
