/**
 * PLAN-5 T2 — the clarifier card's "or type your own answer" hint must have a
 * real input. The only escape used to be the skip link; typed answers now
 * submit through the same sendSuggestion CustomEvent the chips use.
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
}))

import Message from '@/components/Message'

function makeClarifierMessage() {
  return {
    id: 'msg-clarifier-1',
    role: 'assistant' as const,
    content: '',
    timestamp: 1735689600000,
    followups: {
      intro: 'A couple of quick questions:',
      questions: [{
        slot: 'departure_city',
        question: 'Which city are you flying from?',
        options: ['London', 'Birmingham'],
        free_text_hint: 'or type your own answer',
      }],
      closing: "Then I'll pull together a shortlist.",
    },
  }
}

describe('clarifier free-text answer', () => {
  const heard: string[] = []
  const listener = (e: Event) => heard.push((e as CustomEvent).detail.question)

  beforeEach(() => {
    heard.length = 0
    window.addEventListener('sendSuggestion', listener)
  })

  afterEach(() => {
    window.removeEventListener('sendSuggestion', listener)
  })

  it('submits a typed answer through the sendSuggestion event', () => {
    render(<Message message={makeClarifierMessage() as any} />)
    fireEvent.change(screen.getByTestId('clarifier-freetext-input'),
                     { target: { value: 'Manchester, UK' } })
    fireEvent.submit(screen.getByTestId('clarifier-freetext-form'))

    expect(heard).toEqual(['Manchester, UK'])
  })

  it('does not submit an empty or whitespace answer', () => {
    render(<Message message={makeClarifierMessage() as any} />)
    fireEvent.change(screen.getByTestId('clarifier-freetext-input'),
                     { target: { value: '   ' } })
    fireEvent.submit(screen.getByTestId('clarifier-freetext-form'))

    expect(heard).toEqual([])
  })

  it('renders no input on a stale card', () => {
    render(<Message message={makeClarifierMessage() as any} isStale />)
    expect(screen.queryByTestId('clarifier-freetext-form')).toBeNull()
  })
})
