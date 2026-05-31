'use client'

import { useRouter } from 'next/navigation'
import { ChevronRight, Headphones, Plane, Laptop2, Bot, Footprints, Speaker, type LucideIcon } from 'lucide-react'
import { trendingTopics } from '@/lib/trendingTopics'

const iconMap: Record<string, LucideIcon> = {
  Headphones,
  Plane,
  Laptop2,
  Bot,
  Footprints,
  Speaker,
}

export default function TrendingCards() {
  const router = useRouter()

  return (
    <div>
      {/* Section header — blueprint eyebrow + see all */}
      <div className="flex items-center justify-between mb-1">
        <div className="rg-eyebrow">Popular this week</div>
        <button
          onClick={() => router.push('/chat?new=1')}
          className="text-[12px] inline-flex items-center min-h-[40px] px-2 -mr-2"
          style={{ color: 'var(--ink-2)', background: 'none', border: 'none', cursor: 'pointer' }}
        >
          see all
        </button>
      </div>

      {/* Editorial vertical list — thumb tile + Newsreader name + take, hairline rows */}
      <div>
        {trendingTopics.map((topic) => {
          const IconComponent = iconMap[topic.icon]
          return (
            <button
              key={topic.id}
              data-testid="trending-card"
              onClick={() => router.push(`/chat?draft=${encodeURIComponent(topic.query)}&new=1`)}
              className="w-full text-left flex items-center gap-3.5 py-3.5 group"
              style={{ borderTop: '1px solid var(--line)', cursor: 'pointer' }}
            >
              {/* Thumb tile — neutral, terracotta icon (no pastel circles) */}
              <div
                aria-hidden="true"
                className="flex items-center justify-center flex-shrink-0"
                style={{ width: 56, height: 56, borderRadius: 10, background: 'var(--paper-alt)' }}
              >
                {IconComponent && <IconComponent size={22} color="var(--terra)" aria-hidden="true" />}
              </div>

              {/* Text */}
              <div className="flex-1 min-w-0">
                <p className="rg-serif" style={{ fontSize: 16, fontWeight: 500, color: 'var(--ink)', lineHeight: '20px' }}>
                  {topic.title}
                </p>
                <p style={{ fontSize: 13, color: 'var(--ink-2)', lineHeight: '18px', marginTop: 2 }}>
                  {topic.subtitle}
                </p>
              </div>

              <ChevronRight size={16} aria-hidden="true" style={{ color: 'var(--ink-2)', flexShrink: 0 }} className="group-hover:text-[var(--terra)] transition-colors" />
            </button>
          )
        })}
      </div>
    </div>
  )
}
