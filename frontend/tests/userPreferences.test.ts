/**
 * B-phase 3 — cache the backend interest keywords from the chat 'done' event,
 * read them back for starter biasing. Ignores empty / non-array payloads.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { cachePreferenceSummary, getPreferenceSummary } from '@/lib/userPreferences'

// The global test setup mocks localStorage with no-op vi.fn()s; install a real
// in-memory store so we can exercise the cache round-trip.
beforeEach(() => {
  const store = new Map<string, string>()
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
      setItem: (k: string, v: string) => { store.set(k, String(v)) },
      removeItem: (k: string) => { store.delete(k) },
      clear: () => store.clear(),
    },
  })
})

describe('userPreferences cache', () => {
  it('round-trips an array of keywords', () => {
    cachePreferenceSummary(['audio', 'travel', 'sony'])
    expect(getPreferenceSummary()).toEqual(['audio', 'travel', 'sony'])
  })

  it('ignores empty / non-array payloads (keeps prior value)', () => {
    cachePreferenceSummary(['audio'])
    cachePreferenceSummary([]) // empty → no write
    cachePreferenceSummary(undefined as unknown)
    cachePreferenceSummary('nope' as unknown)
    expect(getPreferenceSummary()).toEqual(['audio'])
  })

  it('filters non-strings and caps at 6', () => {
    cachePreferenceSummary(['a', 'b', 'c', 'd', 'e', 'f', 'g', 123 as unknown as string])
    const out = getPreferenceSummary()
    expect(out.length).toBe(6)
    expect(out.every((s) => typeof s === 'string')).toBe(true)
  })

  it('returns [] when nothing cached', () => {
    expect(getPreferenceSummary()).toEqual([])
  })
})
