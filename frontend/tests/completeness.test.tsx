/**
 * PLAN-8 T4 (frontend half) — the done payload's completeness must reach the
 * message. ChatContainer used to overwrite it with the literal 'full' on
 * every done event, so the backend's derived "degraded" never rendered.
 */
import { describe, it, expect, vi, beforeEach, Mock } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import ChatContainer from '@/components/ChatContainer'
import * as chatApi from '@/lib/chatApi'

vi.mock('@/lib/chatApi', () => ({
  streamChat: vi.fn(),
  fetchConversationHistory: vi.fn(),
}))

describe('completeness threading', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(localStorage.getItem as Mock).mockReturnValue(null)
    ;(chatApi.fetchConversationHistory as Mock).mockResolvedValue({ success: true, messages: [] })
  })

  async function sendWithDone(donePayload: Record<string, unknown>) {
    ;(chatApi.streamChat as Mock).mockImplementation(async (opts: any) => {
      opts.onChunk?.({ text: 'Partial answer text.' })
      opts.onComplete?.(donePayload)
    })
    render(<ChatContainer />)
    const textarea = await screen.findByPlaceholderText(/ask anything/i)
    fireEvent.change(textarea, { target: { value: 'best espresso machine' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })
    await waitFor(() => expect(chatApi.streamChat).toHaveBeenCalled())
  }

  it('a degraded done payload renders the degraded indicator', async () => {
    await sendWithDone({
      session_id: '11111111-1111-1111-1111-111111111111',
      completeness: 'degraded',
      ui_blocks: [],
      citations: [],
    })
    await waitFor(() => {
      expect(screen.getByTestId('incomplete-results-indicator')).toBeInTheDocument()
    })
  })

  it('a full done payload renders no degraded indicator', async () => {
    await sendWithDone({
      session_id: '11111111-1111-1111-1111-111111111111',
      completeness: 'full',
      ui_blocks: [],
      citations: [],
    })
    await waitFor(() => {
      expect(screen.queryByTestId('incomplete-results-indicator')).toBeNull()
    })
  })

  it('a done payload without completeness defaults to full', async () => {
    await sendWithDone({
      session_id: '11111111-1111-1111-1111-111111111111',
      ui_blocks: [],
      citations: [],
    })
    await waitFor(() => {
      expect(screen.queryByTestId('incomplete-results-indicator')).toBeNull()
    })
  })
})
