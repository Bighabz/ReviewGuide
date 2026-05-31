'use client'

import { useEffect, useState } from 'react'

export interface StarterSet {
  /** Italic-serif headline shown on the chat empty state. */
  greeting: string
  /** Three auto-send suggestion chips (real, sensible queries). */
  chips: [string, string, string]
}

// Curated pool of cohesive "greeting + 3 chips" starter sets for the chat
// empty state. Set 0 is the SSR-stable default — it renders on the server and
// on the first client paint, so there is NO hydration mismatch. The client
// swaps to a random set on mount (see useChatStarter). Mirrors HeroSubline.tsx.
//
// Voice: warm, "ask before you buy", a little playful. Add/edit sets freely;
// keep chips as queries that make sense to auto-send.
export const STARTER_SETS: StarterSet[] = [
  {
    greeting: 'What are you trying to figure out?',
    chips: ['Best wireless earbuds under $100', 'Plan a 5-day trip to Tokyo', 'Compare MacBook Air vs Pro'],
  },
  {
    greeting: 'What are you shopping for?',
    chips: ['Best robot vacuum under $300', 'Top air purifiers for allergies', 'Sony vs Bose noise-cancelling'],
  },
  {
    greeting: 'Where are we headed?',
    chips: ['Plan a 4-day trip to Lisbon', 'Best time to visit Japan', 'Family-friendly hotels in Orlando'],
  },
  {
    greeting: 'Looking for the best value?',
    chips: ['Best budget 4K TV', 'Best running shoes under $120', 'Best value robot mop'],
  },
  {
    greeting: 'Stuck between two options?',
    chips: ['iPhone 15 vs Pixel 8', 'Best laptop for college', 'Peloton vs a cheaper exercise bike'],
  },
  {
    greeting: 'What’s on your mind?',
    chips: ['Best espresso machine for beginners', 'Top mattresses for back pain', 'Weekend trip ideas from NYC'],
  },
]

/**
 * Returns one starter set. SSR + first client paint = set 0 (stable → no
 * hydration mismatch); the client picks a random set on mount, so the greeting
 * and chips feel fresh each visit. Mirrors HeroSubline.tsx — never call
 * Math.random() during render.
 */
export function useChatStarter(): StarterSet {
  const [set, setSet] = useState<StarterSet>(STARTER_SETS[0])
  useEffect(() => {
    setSet(STARTER_SETS[Math.floor(Math.random() * STARTER_SETS.length)])
  }, [])
  return set
}
