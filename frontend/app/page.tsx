'use client'

import { useState, useEffect } from 'react'
import { getRecentSearches } from '@/lib/recentSearches'
import DiscoverSearchBar from '@/components/discover/DiscoverSearchBar'
import CategoryChipRow from '@/components/discover/CategoryChipRow'
import TrendingCards from '@/components/discover/TrendingCards'
import { LogoHero } from '@/components/Brand'

export default function DiscoverPage() {
  const [hasHistory, setHasHistory] = useState(false)

  useEffect(() => {
    setHasHistory(getRecentSearches().length > 0)
  }, [])

  return (
    <div className="flex flex-col pb-20 px-4 sm:px-6 md:px-8">
      {/* Hero section — blueprint Discover: LogoHero bubble, then italic-display greeting */}
      <div className="flex flex-col items-center pt-8 sm:pt-12 pb-8">
        <LogoHero width={300} />
        <h1
          className="rg-display text-center"
          style={{ fontSize: 28, lineHeight: '32px', color: 'var(--ink)', marginTop: 28 }}
        >
          What are you researching?
        </h1>
        <p
          className="text-sm text-center mt-3 max-w-md"
          style={{ color: 'var(--ink-2)' }}
        >
          A category, a budget, a vibe — anything works.
        </p>
        <div className="w-full max-w-xl mx-auto mt-8">
          <DiscoverSearchBar />
        </div>
      </div>

      {/* Category chips */}
      <div className="mt-8">
        <CategoryChipRow hasHistory={hasHistory} />
      </div>

      {/* Trending cards */}
      <div className="mt-10">
        <TrendingCards />
      </div>
    </div>
  )
}
