/**
 * PLAN-6 T1 (v2) — bound the read loop: the zombie-fetch fix.
 *
 * The 120s AbortController dies the moment fetch() resolves — it covers
 * headers only. Nothing bounded `await reader.read()`: a stalled connection
 * hung the streamChat promise forever, and its late callbacks corrupted a
 * newer stream's state.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { streamChat, READ_IDLE_TIMEOUT_MS } from '@/lib/chatApi'

describe('read-loop idle timeout', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('errors out when the body stream goes silent forever', async () => {
    // Headers arrive fine; the body reader never resolves — the zombie fetch.
    const neverReader = { read: () => new Promise(() => {}), cancel: vi.fn() }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: { getReader: () => neverReader },
    }))

    const onError = vi.fn()
    const done = streamChat({
      message: 'best espresso machine',
      onToken: vi.fn(),
      onComplete: vi.fn(),
      onError,
    } as any)

    await vi.advanceTimersByTimeAsync(READ_IDLE_TIMEOUT_MS + 1000)
    await done
    expect(onError).toHaveBeenCalled()
    expect(String(onError.mock.calls[0][0])).toMatch(/timed out|silent|stalled/i)
    expect(neverReader.cancel).toHaveBeenCalled()
  })

  it('a stall is never auto-retried — one fetch, one error', async () => {
    // A retry would re-POST the full message and double-append content the UI
    // already rendered. StallError must be non-retryable by construction.
    const neverReader = { read: () => new Promise(() => {}), cancel: vi.fn() }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: { getReader: () => neverReader },
    })
    vi.stubGlobal('fetch', fetchMock)

    const onError = vi.fn()
    const done = streamChat({
      message: 'best espresso machine',
      onToken: vi.fn(),
      onComplete: vi.fn(),
      onError,
    } as any)

    // Advance far past every possible backoff window.
    await vi.advanceTimersByTimeAsync(READ_IDLE_TIMEOUT_MS * 4)
    await done
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(onError).toHaveBeenCalledTimes(1)
  })
})
