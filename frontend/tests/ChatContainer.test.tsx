/**
 * ChatContainer — behavioral tests against the current (blueprint) component.
 *
 * Replaces the old pre-blueprint suite (was `.skip`'d) which asserted the
 * removed welcome screen (`UI_TEXT.WELCOME_TITLE`, `TRENDING_SEARCHES` pills).
 * The current empty state is the §7.2 italic-serif greeting + composer.
 */
import { describe, it, expect, vi, beforeEach, Mock } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import ChatContainer from '@/components/ChatContainer'
import * as chatApi from '@/lib/chatApi'
import { UI_TEXT } from '@/lib/constants'
import { STARTER_SETS } from '@/lib/chatStarters'

vi.mock('@/lib/chatApi', () => ({
  streamChat: vi.fn(),
  fetchConversationHistory: vi.fn(),
}))

// Group B: the empty-state greeting is now drawn from a pool (set 0 on SSR,
// random on mount). The heading must always be one of these.
const GREETINGS = STARTER_SETS.map((s) => s.greeting)

describe('ChatContainer (blueprint)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(localStorage.getItem as Mock).mockReturnValue(null)
    ;(chatApi.fetchConversationHistory as Mock).mockResolvedValue({ success: true, messages: [] })
    ;(chatApi.streamChat as Mock).mockResolvedValue(undefined)
  })

  it('renders an empty-state greeting from the starter pool when there are no messages', async () => {
    render(<ChatContainer />)
    // After mount, useChatStarter may swap set 0 → a random set; the heading
    // must always be one of the curated greetings.
    const heading = await screen.findByRole('heading', { level: 1 })
    await waitFor(() => {
      expect(GREETINGS).toContain(heading.textContent)
    })
  })

  it('renders the composer (editable, not auto-sending)', async () => {
    render(<ChatContainer />)
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask anything/i)).toBeInTheDocument()
    })
    expect(chatApi.streamChat).not.toHaveBeenCalled()
  })

  it('shows the loading-history state while history is being fetched', async () => {
    // Hang the fetch so isLoadingHistory stays true on the externalSessionId path.
    ;(chatApi.fetchConversationHistory as Mock).mockImplementation(() => new Promise(() => {}))
    render(<ChatContainer externalSessionId="11111111-1111-1111-1111-111111111111" />)
    await waitFor(() => {
      expect(screen.getByText(UI_TEXT.LOADING_HISTORY)).toBeInTheDocument()
    })
  })

  it('sending a message calls streamChat with that message', async () => {
    render(<ChatContainer />)
    const textarea = await screen.findByPlaceholderText(/ask anything/i)
    fireEvent.change(textarea, { target: { value: 'best wireless earbuds' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })
    await waitFor(() => {
      expect(chatApi.streamChat).toHaveBeenCalledWith(
        expect.objectContaining({ message: 'best wireless earbuds' })
      )
    })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// QA5 bug 4 — brand-new sessions skip the history fetch + spinner
// ─────────────────────────────────────────────────────────────────────────────

describe('ChatContainer — brand-new external session (QA5 bug 4)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(localStorage.getItem as Mock).mockReturnValue(null)
    ;(chatApi.fetchConversationHistory as Mock).mockResolvedValue({ success: true, messages: [] })
    ;(chatApi.streamChat as Mock).mockResolvedValue(undefined)
  })

  it('does NOT fetch history and does NOT show the spinner for a new session', async () => {
    render(
      <ChatContainer
        externalSessionId="22222222-2222-4222-a222-222222222222"
        externalSessionIsNew={true}
      />
    )

    // Welcome screen renders without a loading phase stealing the mount
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask anything/i)).toBeInTheDocument()
    })
    // The guaranteed-401 history fetch for anonymous users never fires
    expect(chatApi.fetchConversationHistory).not.toHaveBeenCalled()
  })

  it('still fetches history for existing sessions (sidebar switches)', async () => {
    render(
      <ChatContainer
        externalSessionId="33333333-3333-4333-a333-333333333333"
        externalSessionIsNew={false}
      />
    )

    await waitFor(() => {
      expect(chatApi.fetchConversationHistory).toHaveBeenCalledWith(
        '33333333-3333-4333-a333-333333333333'
      )
    })
  })
})
