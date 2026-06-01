'use client'

import DiscoverSearchBar from '@/components/discover/DiscoverSearchBar'
import TrendingGrid from '@/components/discover/TrendingGrid'
import DiscoverHeroLogo from '@/components/DiscoverHeroLogo'
import HeroSubline from '@/components/HeroSubline'

export default function DiscoverPage() {
  return (
    <div className="flex flex-col pb-20 px-4 sm:px-6 md:px-8">
      {/* Hero section — animated intro video (recolored terracotta), then italic-display greeting.
          The mobile header is a fixed 48px bar that overlays the top; pt-8 tucked the logo
          partly under it. pt-[76px] (<md) centers the logo between the header and the tagline
          (~28px gap above, matching the gap below); desktop's in-flow topbar needs no offset. */}
      <div className="flex flex-col items-center pt-[76px] md:pt-12 pb-8">
        <DiscoverHeroLogo width={340} />
        <h1
          className="rg-display text-center"
          style={{ fontSize: 28, lineHeight: '32px', color: 'var(--ink)', marginTop: 28 }}
        >
          What are you researching?
        </h1>
        <HeroSubline className="text-sm text-center mt-3 max-w-md" style={{ color: 'var(--ink-2)' }} />
        <div className="w-full max-w-xl mx-auto mt-8">
          <DiscoverSearchBar />
        </div>
      </div>

      {/* Popular this week — 2-up vertical grid of topic posters → /topic/[slug] */}
      <div className="mt-10">
        <TrendingGrid />
      </div>
    </div>
  )
}
