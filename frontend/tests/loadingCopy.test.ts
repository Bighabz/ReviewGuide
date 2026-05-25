import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { LOADING_COPY, useRotatingLoadingCopy } from '../lib/loadingCopy'

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('LOADING_COPY constant', () => {
  it('is the §10.1 tone.md vocabulary, non-empty', () => {
    expect(LOADING_COPY.length).toBeGreaterThan(0)
  })

  it('does not name competitor review sites', () => {
    const competitorPattern =
      /\b(?:RTINGS|Wirecutter|Reddit|Tom['’]?s Guide|CNET|TechRadar|The Verge|Engadget)\b/i
    for (const phrase of LOADING_COPY) {
      expect(phrase).not.toMatch(competitorPattern)
    }
  })

  it('every phrase ends with an ellipsis (…)', () => {
    // Visual rhythm — the ellipsis signals "the AI is still thinking."
    for (const phrase of LOADING_COPY) {
      expect(phrase.endsWith('…')).toBe(true)
    }
  })
})

describe('useRotatingLoadingCopy — behavior contract', () => {
  it('shows serverText immediately when present', () => {
    const { result } = renderHook(() => useRotatingLoadingCopy('Looking up reviews…', 4000))
    expect(result.current).toBe('Looking up reviews…')
  })

  it('starts rotating from LOADING_COPY when serverText is empty/null/undefined', () => {
    const { result } = renderHook(() => useRotatingLoadingCopy(null, 4000))
    // First render: rotation already active, shows index 0.
    expect(result.current).toBe(LOADING_COPY[0])
  })

  it('hands off from serverText to rotation after the interval', () => {
    const { result } = renderHook(() => useRotatingLoadingCopy('Same tool running…', 4000))
    expect(result.current).toBe('Same tool running…')

    // Advance just past the handoff threshold.
    act(() => {
      vi.advanceTimersByTime(4100)
    })
    // Rotation takes over starting from index 0.
    expect(result.current).toBe(LOADING_COPY[0])

    // Continues advancing one phrase per intervalMs.
    act(() => {
      vi.advanceTimersByTime(4000)
    })
    expect(result.current).toBe(LOADING_COPY[1])
  })

  it('resets rotation when serverText changes mid-flight', () => {
    const { result, rerender } = renderHook(
      ({ statusText }: { statusText: string | null }) =>
        useRotatingLoadingCopy(statusText, 4000),
      { initialProps: { statusText: 'First tool…' as string | null } },
    )
    expect(result.current).toBe('First tool…')

    // Let rotation kick in.
    act(() => {
      vi.advanceTimersByTime(5000)
    })
    expect(result.current).toBe(LOADING_COPY[0])
    act(() => {
      vi.advanceTimersByTime(4000)
    })
    expect(result.current).toBe(LOADING_COPY[1])

    // Server sends a new tool's status — hook resets to "show server text".
    rerender({ statusText: 'Second tool…' as string | null })
    expect(result.current).toBe('Second tool…')

    // After the interval, rotation restarts from index 0 (not where it left off).
    act(() => {
      vi.advanceTimersByTime(4100)
    })
    expect(result.current).toBe(LOADING_COPY[0])
  })

  it('treats whitespace-only serverText as empty (rotates immediately)', () => {
    const { result } = renderHook(() => useRotatingLoadingCopy('   ', 4000))
    expect(result.current).toBe(LOADING_COPY[0])
  })

  it('cycles back to LOADING_COPY[0] after walking the full list', () => {
    const { result } = renderHook(() => useRotatingLoadingCopy(null, 1000))
    expect(result.current).toBe(LOADING_COPY[0])
    // Advance through every phrase.
    for (let i = 1; i < LOADING_COPY.length; i++) {
      act(() => {
        vi.advanceTimersByTime(1000)
      })
      expect(result.current).toBe(LOADING_COPY[i])
    }
    // One more tick wraps to the start.
    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(result.current).toBe(LOADING_COPY[0])
  })
})
