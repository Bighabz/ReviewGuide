/**
 * PLAN-6 T2+T3 — errors attach to the message that failed, and a superseding
 * action aborts the live stream instead of racing two.
 *
 * Note on the supersede vector: every composer entry point guards on
 * isStreaming, so "two sends back to back" is unreachable through the UI.
 * The reachable interleave is a SESSION SWITCH mid-stream (conversation
 * drawer — no isStreaming guard on that effect), which is exactly the
 * Task 4b case; it exercises Task 3's controller ref end to end.
 */
import { describe, it, expect, vi, beforeEach, Mock } from 'vitest'
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import ChatContainer from '@/components/ChatContainer'
import * as chatApi from '@/lib/chatApi'

vi.mock('@/lib/chatApi', () => ({
  streamChat: vi.fn(),
  fetchConversationHistory: vi.fn(),
}))

const SESSION_B = '22222222-2222-4222-8222-222222222222'

async function sendMessage(text: string) {
  const textarea = await screen.findByPlaceholderText(/ask anything/i)
  fireEvent.change(textarea, { target: { value: text } })
  fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })
  await waitFor(() => expect(chatApi.streamChat).toHaveBeenCalled())
}

describe('stream error targeting + supersede abort', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(localStorage.getItem as Mock).mockReturnValue(null)
    ;(chatApi.fetchConversationHistory as Mock).mockResolvedValue({ success: true, messages: [] })
  })

  it('attaches the error to the message whose stream failed', async () => {
    let capturedOnError: (msg: string) => void = () => {}
    ;(chatApi.streamChat as Mock).mockImplementation((opts: any) => {
      capturedOnError = opts.onError
      return new Promise(() => {})
    })

    render(<ChatContainer />)
    await sendMessage('best espresso machine')

    // The thinking assistant bubble exists — its DOM id carries the message id.
    const bubbles = Array.from(document.querySelectorAll('[id^="message-"]'))
      .filter((el) => /^message-[0-9a-f-]{36}$/i.test(el.id))
    const assistantDomId = bubbles[bubbles.length - 1].id.replace('message-', '')

    await act(async () => { capturedOnError('Hit a wall pulling info on this one') })

    const banner = screen.getByTestId('chat-error-banner')
    expect(banner.getAttribute('data-message-id')).toBe(assistantDomId)
  })

  it('aborts the live stream when the session switches mid-stream', async () => {
    const aborted: boolean[] = []
    ;(chatApi.streamChat as Mock).mockImplementation((opts: any) => {
      opts.signal?.addEventListener('abort', () => aborted.push(true))
      return new Promise(() => {})
    })

    const { rerender } = render(<ChatContainer />)
    await sendMessage('best espresso machine')

    await act(async () => {
      rerender(<ChatContainer externalSessionId={SESSION_B} />)
    })

    expect(aborted).toHaveLength(1)
    // The switch resets the FSM — composer usable again, no stuck spinner.
    await waitFor(() => {
      const textarea = screen.getByPlaceholderText(/ask anything/i) as HTMLTextAreaElement
      expect(textarea.disabled).toBe(false)
    })
  })

  it('suppresses a stale error from a superseded stream', async () => {
    let capturedOnError: (msg: string) => void = () => {}
    ;(chatApi.streamChat as Mock).mockImplementation((opts: any) => {
      capturedOnError = opts.onError
      return new Promise(() => {})
    })

    const { rerender } = render(<ChatContainer />)
    await sendMessage('best espresso machine')

    await act(async () => {
      rerender(<ChatContainer externalSessionId={SESSION_B} />)
    })

    // The old stream's late error must not surface in the new session.
    await act(async () => { capturedOnError('late failure from a dead stream') })
    expect(screen.queryByTestId('chat-error-banner')).toBeNull()
  })
})
