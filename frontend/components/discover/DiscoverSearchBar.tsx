'use client'

import { useRouter } from 'next/navigation'
import { Search } from 'lucide-react'

export default function DiscoverSearchBar() {
  const router = useRouter()

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
        Ask anything — best headphones, Tokyo trip, laptop deals...
      </span>
    </button>
  )
}
