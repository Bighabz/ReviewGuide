/**
 * PLAN-7 T6 — typing immediately after New Chat must not drop keystrokes.
 *
 * The composer mounted unfocused, so text typed right after New Chat went
 * nowhere. The welcome composer now autofocuses on mount and refocuses when
 * the session rotates.
 */
import { describe, it, expect } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import ChatContainer from '@/components/ChatContainer'

describe('new chat focus', () => {
  it('focuses the composer after New Chat', async () => {
    render(<ChatContainer key="new" />)
    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByTestId('chat-input'))
    })
  })
})
