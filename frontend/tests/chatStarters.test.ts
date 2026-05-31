/**
 * Group B — dynamic chat starter content. Locks the pool invariants that keep
 * the chat empty state hydration-safe and well-formed.
 */
import { describe, it, expect } from 'vitest'
import { STARTER_SETS, pickStarter } from '@/lib/chatStarters'

describe('STARTER_SETS', () => {
  it('has a non-trivial pool', () => {
    expect(STARTER_SETS.length).toBeGreaterThanOrEqual(4)
  })

  it('every set has a non-empty greeting and exactly 3 non-empty chips', () => {
    for (const set of STARTER_SETS) {
      expect(set.greeting.trim().length).toBeGreaterThan(0)
      expect(set.chips).toHaveLength(3)
      for (const chip of set.chips) {
        expect(chip.trim().length).toBeGreaterThan(0)
      }
    }
  })

  it('set 0 is the SSR-stable default (greeting unchanged from the blueprint)', () => {
    // ChatContainer renders set 0 on the server + first client paint, so this
    // value must stay deterministic to avoid a hydration mismatch.
    expect(STARTER_SETS[0].greeting).toBe('What are you trying to figure out?')
  })

  it('has no duplicate greetings', () => {
    const greetings = STARTER_SETS.map((s) => s.greeting)
    expect(new Set(greetings).size).toBe(greetings.length)
  })
})

describe('pickStarter (phase 2 personalization)', () => {
  // rng=0 → always picks the first eligible set, making selection deterministic.
  const firstPick = () => 0

  it('cold start (no signal) falls back to the full pool — set 0 is reachable', () => {
    expect(pickStarter(STARTER_SETS, '', firstPick)).toBe(STARTER_SETS[0])
  })

  it('a signal with no keyword hits stays cold (full pool, not skewed)', () => {
    expect(pickStarter(STARTER_SETS, 'xyzzy nothing matches here', firstPick)).toBe(STARTER_SETS[0])
  })

  it('biases to travel when recent searches mention a trip', () => {
    const pick = pickStarter(STARTER_SETS, 'plan a tokyo trip, cheap flights to japan', firstPick)
    expect(pick.greeting).toBe('Where are we headed?')
  })

  it('biases to the audio/shopping set for headphone history', () => {
    const pick = pickStarter(STARTER_SETS, 'best sony noise cancelling headphones; bose earbuds', firstPick)
    expect(pick.greeting).toBe('What are you shopping for?')
  })

  it('biases to the compare set for phone/laptop history', () => {
    const pick = pickStarter(STARTER_SETS, 'iphone 15 vs pixel; best laptop for school', firstPick)
    expect(pick.greeting).toBe('Stuck between two options?')
  })

  it('warm pick never returns the neutral default (set 0 has no match keywords)', () => {
    // Even with rng forcing the first eligible, a real keyword hit excludes set 0.
    const pick = pickStarter(STARTER_SETS, 'espresso machine and a new mattress', firstPick)
    expect(pick).not.toBe(STARTER_SETS[0])
    expect(pick.greeting).toBe('What’s on your mind?')
  })
})
