/**
 * Today's Briefing — editorial trending stories for the Discover front page.
 * Replaces lib/trendingTopics.ts in the homepage redesign (kept for any other consumers).
 */

export interface BriefingStory {
  kicker: string
  title: string
  dek: string
  query: string
  image: string
}

export const briefingStories: BriefingStory[] = [
  {
    kicker: 'Audio',
    title: 'The headphone hierarchy just changed',
    dek: 'Sony’s XM6 resets the benchmark — and makes three rivals suddenly look overpriced.',
    query: 'Best noise-cancelling headphones 2026',
    image: '/images/products/mosaic-headphones.webp',
  },
  {
    kicker: 'Travel',
    title: 'Tokyo, without the tourist tax',
    dek: 'When to book, where to stay, what the guidebooks miss.',
    query: 'Tokyo travel guide flights hotels hidden gems',
    image: '/images/travel/hero-asia.webp',
  },
  {
    kicker: 'Computing',
    title: 'Student laptops worth four years',
    dek: 'Five machines that survive a degree.',
    query: 'Best laptops for students 2026',
    image: '/images/products/mosaic-laptop.webp',
  },
  {
    kicker: 'Home',
    title: 'Robot vacuums vs. pet hair',
    dek: 'Three actually cope. Two pretend.',
    query: 'Best robot vacuums for pet hair',
    image: '/images/products/mosaic-espresso.webp',
  },
  {
    kicker: 'Fitness',
    title: 'Running shoes, ranked honestly',
    dek: 'From trail to treadmill, minus the hype.',
    query: 'Best running shoes trail treadmill 2026',
    image: '/images/products/mosaic-sneakers.webp',
  },
]
