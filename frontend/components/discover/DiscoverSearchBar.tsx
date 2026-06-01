'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Search } from 'lucide-react'

// Pool of short example queries for the placeholder line. Three show per
// visit ("Ask anything — a, b, c..."), freshly rotated on each page load.
// Keep entries short — the line truncates on narrow screens. Add freely.
export const PLACEHOLDER_EXAMPLES = [
  'best headphones',
  'Tokyo trip',
  'laptop deals',
  'robot vacuums',
  'a weekend in Lisbon',
  'standing desks',
  '4K TVs under $500',
  'espresso machines',
  'running shoes',
  'noise-cancelling earbuds',
  'family hotels in Orlando',
  'air purifiers',
  'mattresses for back pain',
  'iPhone vs Pixel',
  'a beginner road bike',
]

/**
 * Returns `count` example queries. SSR + first client paint = the first
 * `count` in array order (deterministic → no hydration mismatch); the client
 * shuffles the full pool on mount and shows a fresh trio. Mirrors
 * HeroSubline.tsx / TrendingGrid.tsx — never call Math.random() during render.
 */
function useRotatedExamples(count = 3): string[] {
  const [examples, setExamples] = useState<string[]>(() => PLACEHOLDER_EXAMPLES.slice(0, count))
  useEffect(() => {
    const shuffled = [...PLACEHOLDER_EXAMPLES]
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1))
      ;[shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
    }
    setExamples(shuffled.slice(0, count))
  }, [count])
  return examples
}

export default function DiscoverSearchBar() {
  const router = useRouter()
  const examples = useRotatedExamples(3)

  return (
    <button
      data-testid="discover-search-bar"
      aria-label="Start a research session"
      onClick={() => router.push('/chat?new=1')}
      className="w-full flex items-center gap-3 px-4 text-left transition-colors"
      style={{
        height: '56px',
        border: '1px solid var(--border)',
        borderRadius: '16px',
        background: 'var(--surface-elevated)',
        boxShadow: 'var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.06))',
        cursor: 'pointer',
      }}
      onMouseEnter={(e) => {
        const el = e.currentTarget as HTMLButtonElement
        el.style.borderColor = 'color-mix(in srgb, var(--primary) 40%, transparent)'
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLButtonElement
        el.style.borderColor = 'var(--border)'
      }}
    >
      <Search
        size={18}
        style={{ color: 'var(--ink-2)', flexShrink: 0 }}
        aria-hidden="true"
      />
      <span
        className="text-sm truncate"
        style={{ color: 'var(--ink-2)' }}
      >
        Ask anything — {examples.join(', ')}...
      </span>
    </button>
  )
}
