/**
 * PLAN-6 T4b — the cheap confirmed bugs:
 *   1. Date.now()+1/+2 message ids collided within a millisecond → UUIDs.
 *   2. localStorage persisted isThinking:true mid-stream (frozen spinner on
 *      reload) and stringified on every token → sanitized + debounced.
 * (3. session-switch RESET + abort is covered in streamErrorTargeting.)
 */
import { describe, it, expect, vi, beforeEach, afterEach, Mock } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import ChatContainer from '@/components/ChatContainer'
import * as chatApi from '@/lib/chatApi'
import { CHAT_CONFIG } from '@/lib/constants'

vi.mock('@/lib/chatApi', () => ({
  streamChat: vi.fn(),
  fetchConversationHistory: vi.fn(),
}))

describe('message ids + persistence', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(localStorage.getItem as Mock).mockReturnValue(null)
    ;(chatApi.fetchConversationHistory as Mock).mockResolvedValue({ success: true, messages: [] })
    ;(chatApi.streamChat as Mock).mockImplementation(() => new Promise(() => {}))
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('two messages created in the same millisecond get distinct ids', async () => {
    // Freeze time: the old (Date.now()+1) scheme relied on the clock ticking.
    vi.spyOn(Date, 'now').mockReturnValue(1735689600000)

    render(<ChatContainer />)
    const textarea = await screen.findByPlaceholderText(/ask anything/i)
    fireEvent.change(textarea, { target: { value: 'best espresso machine' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })
    await waitFor(() => expect(chatApi.streamChat).toHaveBeenCalled())

    const ids = Array.from(document.querySelectorAll('[id^="message-"]'))
      .map((el) => el.id)
      .filter((id) => /^message-[0-9a-f-]{36}$/i.test(id))
    expect(ids.length).toBe(2) // user + assistant placeholder
    expect(new Set(ids).size).toBe(2)
  })

  it('mid-stream persistence strips isThinking so a reload cannot freeze the spinner', async () => {
    render(<ChatContainer />)
    const textarea = await screen.findByPlaceholderText(/ask anything/i)
    fireEvent.change(textarea, { target: { value: 'best espresso machine' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })
    await waitFor(() => expect(chatApi.streamChat).toHaveBeenCalled())

    // The debounced write fires ~500ms after the last messages change.
    await waitFor(() => {
      const writes = (localStorage.setItem as Mock).mock.calls
        .filter(([key]) => key === CHAT_CONFIG.MESSAGES_STORAGE_KEY)
      expect(writes.length).toBeGreaterThan(0)
    }, { timeout: 2000 })

    const writes = (localStorage.setItem as Mock).mock.calls
      .filter(([key]) => key === CHAT_CONFIG.MESSAGES_STORAGE_KEY)
    const persisted = JSON.parse(writes[writes.length - 1][1])
    for (const msg of persisted) {
      expect(msg.isThinking).toBeUndefined()
      expect(msg.statusText).toBeUndefined()
    }
  })
})
