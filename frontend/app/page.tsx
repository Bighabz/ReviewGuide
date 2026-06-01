'use client'

import DiscoverSearchBar from '@/components/discover/DiscoverSearchBar'
import TrendingGrid from '@/components/discover/TrendingGrid'
import DiscoverHeroLogo from '@/components/DiscoverHeroLogo'
import HeroSubline from '@/components/HeroSubline'

export default function DiscoverPage() {
  return (
    <div className="flex flex-col pb-20 px-4 sm:px-6 md:px-8">
      {/* Hero section — animated intro video (recolored terracotta), then italic-display greeting.
          The mobile header is a fixed 48px bar that overlays the top; anything under pt-[48px]
          tucks the logo partly under it. Mobile uses pt-[56px] (header + 8px gap) and tighter
          gaps below (h1 mt-4, search mt-5, pb-4, grid mt-2) so the first row of "Popular this
          week" cards — plus a peek of the second row — clears the bottom tab bar on phones,
          matching desktop's "scroll for more" cue. Desktop spacing (md:) is unchanged. */}
      <div className="flex flex-col items-center pt-[56px] md:pt-12 pb-4 md:pb-8">
        {/* Logo renders at 280px on phones (saves ~24px of height for the cards
            below); full 340px from md up. */}
        <div className="w-full max-w-[280px] md:max-w-[340px]">
          <DiscoverHeroLogo width={340} />
        </div>
        <h1
          className="rg-display text-center mt-4 md:mt-7"
          style={{ fontSize: 28, lineHeight: '32px', color: 'var(--ink)' }}
        >
          What are you researching?
        </h1>
        <HeroSubline className="text-sm text-center mt-3 max-w-md" style={{ color: 'var(--ink-2)' }} />
        <div className="w-full max-w-xl mx-auto mt-5 md:mt-8">
          <DiscoverSearchBar />
        </div>
      </div>

      {/* Popular this week — 2-up vertical grid of topic posters → /topic/[slug] */}
      <div className="mt-2 md:mt-10">
        <TrendingGrid />
      </div>
    </div>
  )
}
