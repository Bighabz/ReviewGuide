/**
 * PLAN-7 T5 — superseded clarifier cards must go inert.
 *
 * Each card tracks its own `submitted` state, so a card from an earlier turn
 * stayed clickable after a newer question was asked, submitting answers into
 * the CURRENT question's state.
 *
 * Staleness rule (binding, Kimi validation): a card is stale only when a
 * NEWER CLARIFIER CARD exists — an ordinary results message arriving after a
 * card must NOT lock it, because the ask-more flow deliberately keeps the
 * older card's slots open and answerable (clarifier_agent.py:999-1004).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    span: ({ children, ...props }: any) => <span {...props}>{children}</span>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

vi.mock('react-markdown', () => ({
  default: ({ children }: any) => <span data-testid="markdown-content">{children}</span>,
}))

vi.mock('@/lib/normalizeBlocks', () => ({
  normalizeBlocks: (blocks: any[]) => blocks ?? [],
}))

vi.mock('@/components/blocks/BlockRegistry', () => ({
  UIBlocks: () => <div data-testid="ui-blocks-container" />,
}))

vi.mock('@/components/MessageRecoveryUI', () => ({
  default: () => <div data-testid="message-recovery-ui" />,
}))

vi.mock('@/lib/trackAffiliate', () => ({
  trackAffiliate: vi.fn(),
}))

vi.mock('@/lib/utils', () => ({
  formatTimestamp: () => 'just now',
  formatFullTimestamp: () => '2026-01-01 12:00:00',
  SUGGESTION_CLICK_PREFIX: '> ',
}))

vi.mock('lucide-react', () => ({
  User: () => <span data-testid="icon-user" />,
  Copy: () => <span data-testid="icon-copy" />,
  Check: () => <span data-testid="icon-check" />,
  ArrowRight: () => <span data-testid="icon-arrow-right" />,
  ChevronDown: () => <span data-testid="icon-chevron-down" />,
}))

import Message from '@/components/Message'
import MessageList from '@/components/MessageList'

const USE_CASE_QUESTION = {
  slot: 'use_case',
  question: 'What will you mainly use it for?',
  options: ['Student / everyday', 'Gaming'],
  free_text_hint: 'or describe your own use',
}

function makeClarifierMessage(id: string, overrides = {}) {
  return {
    id,
    role: 'assistant' as const,
    content: '',
    timestamp: 1735689600000,
    followups: {
      intro: 'A couple of quick questions:',
      questions: [USE_CASE_QUESTION],
      closing: "Then I'll pull together a shortlist.",
    },
    ...overrides,
  }
}

function makeResultsMessage(id: string) {
  return {
    id,
    role: 'assistant' as const,
    content: 'Here are the picks.',
    timestamp: 1735689600000,
  }
}

describe('stale clarifier cards', () => {
  const heard: string[] = []
  const listener = (e: Event) => heard.push((e as CustomEvent).detail.question)

  beforeEach(() => {
    heard.length = 0
    window.addEventListener('sendSuggestion', listener)
  })

  afterEach(() => {
    window.removeEventListener('sendSuggestion', listener)
  })

  it('does not submit from a superseded clarifier card', () => {
    render(<Message message={makeClarifierMessage('m1') as any} isStale />)

    // A stale card renders no footer/submit affordances at all…
    expect(screen.queryByTestId('clarifier-skip-all')).toBeNull()
    expect(screen.queryByTestId('clarifier-ask-more')).toBeNull()

    // …and its chips are inert.
    fireEvent.click(screen.getAllByTestId('clarifier-option-chip')[0])
    expect(heard).toEqual([])
  })

  it('an older clarifier card stays live when only a results message follows', () => {
    render(
      <MessageList
        messages={[makeClarifierMessage('m1'), makeResultsMessage('m2')] as any}
      />
    )

    // The banner rule: an ordinary results message must NOT stale the card.
    fireEvent.click(screen.getByTestId('clarifier-skip-all'))
    expect(heard).toEqual(['Just show me the best overall'])
  })

  it('only the newest clarifier card is live when two exist', () => {
    render(
      <MessageList
        messages={[makeClarifierMessage('m1'), makeClarifierMessage('m2')] as any}
      />
    )

    // Exactly one live footer — the newer card's.
    const skips = screen.getAllByTestId('clarifier-skip-all')
    expect(skips).toHaveLength(1)
    fireEvent.click(skips[0])
    expect(heard).toEqual(['Just show me the best overall'])
  })
})
