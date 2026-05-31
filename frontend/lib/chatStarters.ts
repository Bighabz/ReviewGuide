'use client'

import { useEffect, useState } from 'react'
import { getRecentSearches } from './recentSearches'
import { getSavedItems } from './savedItems'

export interface StarterSet {
  /** Italic-serif headline shown on the chat empty state. */
  greeting: string
  /** Three auto-send suggestion chips (real, sensible queries). */
  chips: [string, string, string]
  /**
   * Lowercase keywords used to bias selection toward a returning user's
   * interests (phase 2). A set is favored when the user's recent searches /
   * saved items mention any of these. Omit/empty = neutral (cold-start only).
   */
  match?: string[]
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
    // Set 0 is the SSR-stable default and stays neutral (no match keywords),
    // so it only appears via cold-start randomness, never as a warm bias.
    greeting: 'What are you trying to figure out?',
    chips: ['Best wireless earbuds under $100', 'Plan a 5-day trip to Tokyo', 'Compare MacBook Air vs Pro'],
  },
  {
    greeting: 'What are you shopping for?',
    chips: ['Best robot vacuum under $300', 'Top air purifiers for allergies', 'Sony vs Bose noise-cancelling'],
    match: ['vacuum', 'purifier', 'sony', 'bose', 'headphone', 'earbud', 'speaker', 'audio', 'appliance', 'clean'],
  },
  {
    greeting: 'Where are we headed?',
    chips: ['Plan a 4-day trip to Lisbon', 'Best time to visit Japan', 'Family-friendly hotels in Orlando'],
    match: ['travel', 'trip', 'flight', 'hotel', 'vacation', 'tokyo', 'japan', 'europe', 'lisbon', 'orlando', 'destination', 'resort'],
  },
  {
    greeting: 'Looking for the best value?',
    chips: ['Best budget 4K TV', 'Best running shoes under $120', 'Best value robot mop'],
    match: ['tv', 'television', 'shoe', 'running', 'sneaker', 'mop', 'budget', 'cheap', 'deal', 'value', 'fitness'],
  },
  {
    greeting: 'Stuck between two options?',
    chips: ['iPhone 15 vs Pixel 8', 'Best laptop for college', 'Peloton vs a cheaper exercise bike'],
    match: ['iphone', 'pixel', 'phone', 'smartphone', 'laptop', 'macbook', 'computer', 'tablet', 'peloton', 'bike', 'compare'],
  },
  {
    greeting: 'What’s on your mind?',
    chips: ['Best espresso machine for beginners', 'Top mattresses for back pain', 'Weekend trip ideas from NYC'],
    match: ['espresso', 'coffee', 'kitchen', 'blender', 'fryer', 'mattress', 'sleep', 'bed', 'desk', 'chair', 'furniture'],
  },
]

/**
 * Pure starter picker (phase 2). Scores each set by how many of its `match`
 * keywords appear in `signalText` (the user's recent searches + saved items).
 * Warm: choose randomly among the top-scoring sets. Cold (no signal / no hit):
 * choose randomly among all sets — identical to phase-1 behavior.
 * `rng` is injectable for deterministic tests.
 */
export function pickStarter(
  sets: StarterSet[],
  signalText: string,
  rng: () => number = Math.random
): StarterSet {
  const text = signalText.toLowerCase()
  let best = 0
  const scored = sets.map((s) => {
    const score = (s.match ?? []).reduce((n, kw) => (text.includes(kw) ? n + 1 : n), 0)
    if (score > best) best = score
    return { s, score }
  })
  const pool = best > 0 ? scored.filter((x) => x.score === best) : scored
  return pool[Math.floor(rng() * pool.length)].s
}

/** Build the signal string from the user's local history (client-only). */
function readUserSignal(): string {
  try {
    const recents = getRecentSearches()
    const saved = getSavedItems()
    return [
      ...recents.map((r) => `${r.query} ${r.category} ${(r.productNames ?? []).join(' ')}`),
      ...saved.map((i) => `${i.name} ${i.role ?? ''}`),
    ].join(' ')
  } catch {
    return '' // localStorage unavailable (SSR, private browsing)
  }
}

/**
 * Returns one starter set. SSR + first client paint = set 0 (stable → no
 * hydration mismatch); on mount the client picks a set biased toward the
 * returning user's interests (cold-start = random). Mirrors HeroSubline.tsx —
 * never call Math.random() during render.
 */
export function useChatStarter(): StarterSet {
  const [set, setSet] = useState<StarterSet>(STARTER_SETS[0])
  useEffect(() => {
    setSet(pickStarter(STARTER_SETS, readUserSignal()))
  }, [])
  return set
}
