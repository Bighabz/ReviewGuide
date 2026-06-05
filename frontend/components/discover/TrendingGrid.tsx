'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowUpRight } from 'lucide-react'
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

const GRADIENT =
  'linear-gradient(180deg, rgba(26,24,22,0) 30%, rgba(26,24,22,0.5) 62%, rgba(26,24,22,0.9) 100%)'

function TopicCard({
  topic,
  featured = false,
  eager = false,
  onOpen,
}: {
  topic: DiscoverTopic
  featured?: boolean
  eager?: boolean
  onOpen: () => void
}) {
  return (
    <button
      data-testid="trending-card"
      onClick={onOpen}
      aria-label={`${topic.title} — ${topic.hook}`}
      className="group relative block w-full overflow-hidden rounded-2xl text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--terra)] focus-visible:ring-offset-2"
      style={{ boxShadow: 'var(--shadow-float)', border: '1px solid var(--line)', cursor: 'pointer' }}
    >
      <div className={featured ? 'relative aspect-[2/1]' : 'relative aspect-[4/5] lg:aspect-square'}>
        <img
          src={topic.image}
          alt={topic.title}
          loading={eager ? 'eager' : 'lazy'}
          className="w-full h-full object-cover transition-transform duration-[600ms] ease-out group-hover:scale-[1.06]"
          style={{ background: 'var(--paper-alt)' }}
        />
        <div className="absolute inset-0" aria-hidden="true" style={{ background: GRADIENT }} />

        {/* Hover affordance — a small "open" chip top-right (desktop only) */}
        <span
          className="hidden lg:flex absolute top-3 right-3 w-8 h-8 rounded-full items-center justify-center opacity-0 -translate-y-1 transition-all duration-300 group-hover:opacity-100 group-hover:translate-y-0"
          style={{ background: 'rgba(250,250,247,0.92)', color: 'var(--terra)' }}
          aria-hidden="true"
        >
          <ArrowUpRight size={16} strokeWidth={2.4} />
        </span>

        <div className={featured ? 'absolute inset-x-0 bottom-0 p-5 sm:p-6' : 'absolute inset-x-0 bottom-0 p-3.5'}>
          <div
            className="uppercase mb-1"
            style={{ fontSize: featured ? 11 : 10, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--terra-soft)' }}
          >
            {topic.category}
          </div>
          <p
            className="rg-serif text-white"
            style={{ fontSize: featured ? 26 : 17, lineHeight: featured ? '30px' : '21px', fontWeight: 600 }}
          >
            {topic.title}
          </p>
          <p
            className="text-white/85"
            style={{
              fontSize: featured ? 14 : 12,
              lineHeight: featured ? '20px' : '16px',
              marginTop: featured ? 6 : 2,
              maxWidth: featured ? '46ch' : undefined,
            }}
          >
            {topic.hook}
          </p>
        </div>
      </div>
    </button>
  )
}

/**
 * Discover "Popular this week". Mobile stays a dense 2-up poster grid (so the
 * first row + a peek of the next clears the tab bar — the page's deliberate
 * "scroll for more" cue). From md up, the lead topic becomes a wide featured
 * banner above a 3-up grid. Browse-only: a tap opens /topic/[slug]. Terracotta
 * tokens only.
 */
export default function TrendingGrid() {
  const router = useRouter()
  const topics = useRotatedTopics(8)
  if (topics.length === 0) return null

  const lead = topics[0]
  const rest = topics.slice(1)
  const open = (slug: string) => router.push(`/topic/${slug}`)

  return (
    <div>
      <div className="flex items-baseline justify-between mb-3">
        <div className="rg-eyebrow">Popular this week</div>
        <span className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Tap to explore</span>
      </div>

      {/* Featured banner — desktop only (md+); keeps mobile dense */}
      <div className="hidden md:block mb-3">
        <TopicCard topic={lead} featured eager onOpen={() => open(lead.slug)} />
      </div>

      {/* Poster grid — 2-up mobile, 3-up desktop. The lead topic appears as a
          normal grid card on mobile only (md:hidden) since the banner shows it
          on desktop. */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <div className="md:hidden">
          <TopicCard topic={lead} eager onOpen={() => open(lead.slug)} />
        </div>
        {rest.map((topic) => (
          <TopicCard key={topic.slug} topic={topic} onOpen={() => open(topic.slug)} />
        ))}
      </div>
    </div>
  )
}
