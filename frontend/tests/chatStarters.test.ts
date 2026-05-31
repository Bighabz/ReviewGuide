/**
 * Group B — dynamic chat starter content. Locks the pool invariants that keep
 * the chat empty state hydration-safe and well-formed.
 */
import { describe, it, expect } from 'vitest'
import { STARTER_SETS } from '@/lib/chatStarters'

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
