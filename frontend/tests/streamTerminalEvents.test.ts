/**
 * PLAN-6 T4 Step 6 — the two verified paths that ended a stream
 * "finished mid-sentence, no error":
 *   (a) a done event without session_id skipped onComplete entirely
 *   (b) SSE parse failures were swallowed and the stream closed silently
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { streamChat } from '@/lib/chatApi'

function sseStream(frames: string[]) {
  let i = 0
  const encoder = new TextEncoder()
  return {
    getReader: () => ({
      read: async () => {
        if (i < frames.length) {
          return { done: false, value: encoder.encode(frames[i++]) }
        }
        return { done: true, value: undefined }
      },
      cancel: vi.fn(),
    }),
  }
}

function stubFetch(frames: string[]) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    body: sseStream(frames),
  }))
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('terminal events always fire', () => {
  it('a done event without session_id still calls onComplete once', async () => {
    stubFetch([
      'event: done\n',
      'data: {"status": "completed", "ui_blocks": []}\n',
      '\n',
    ])
    const onComplete = vi.fn()
    await streamChat({
      message: 'q',
      onToken: vi.fn(), onComplete, onError: vi.fn(),
    } as any)
    expect(onComplete).toHaveBeenCalledTimes(1)
    expect(onComplete.mock.calls[0][0].session_id).toBeUndefined()
  })

  it('a stream that closes after malformed frames surfaces an error', async () => {
    stubFetch([
      'event: content\n',
      'data: {not valid json\n',
      '\n',
    ])
    const onError = vi.fn()
    await streamChat({
      message: 'q',
      onToken: vi.fn(), onComplete: vi.fn(), onError,
    } as any)
    expect(onError).toHaveBeenCalledTimes(1)
    expect(String(onError.mock.calls[0][0])).toMatch(/malformed/i)
  })

  it('a clean close with a proper done event raises no error', async () => {
    stubFetch([
      'event: done\n',
      'data: {"session_id": "s1", "status": "completed"}\n',
      '\n',
    ])
    const onError = vi.fn()
    const onComplete = vi.fn()
    await streamChat({
      message: 'q',
      onToken: vi.fn(), onComplete, onError,
    } as any)
    expect(onError).not.toHaveBeenCalled()
    expect(onComplete).toHaveBeenCalledTimes(1)
  })
})
