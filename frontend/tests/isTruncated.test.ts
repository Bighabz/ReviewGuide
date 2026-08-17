/**
 * PLAN-6 T4 — a truncated answer must be labelled, not shipped silently.
 * The audit's answer ended "…is the pick if you have" with no error.
 */
import { describe, it, expect } from 'vitest'
import { isLikelyTruncated } from '@/lib/isTruncated'

describe('isLikelyTruncated', () => {
  it('flags prose ending mid-sentence', () => {
    expect(isLikelyTruncated(
      'The Shark Rocket Pet Pro Cordless Stick Vacuum is the pick if you have'
    )).toBe(true)
  })

  it('accepts prose ending in terminal punctuation', () => {
    expect(isLikelyTruncated('It is the pick for small flats.')).toBe(false)
    expect(isLikelyTruncated('Which room is it for?')).toBe(false)
  })

  it('accepts prose ending in a list item or table row', () => {
    expect(isLikelyTruncated('- Built-in burr grinder\n- Fast heat-up\n')).toBe(false)
  })

  it('does not flag empty text', () => {
    expect(isLikelyTruncated('')).toBe(false)
    expect(isLikelyTruncated('   ')).toBe(false)
  })

  it('flags a dangling conjunction even with a period elsewhere', () => {
    expect(isLikelyTruncated('It is quiet. It also handles pet hair and')).toBe(true)
  })
})
