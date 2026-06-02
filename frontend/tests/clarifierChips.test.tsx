/**
 * Clarifier option chips — category-aware tappable answers on EVERY question.
 *
 * The backend clarifier now emits `options` (+ `free_text_hint`) per question.
 * Message.tsx must:
 *   1. Render a chip per option for ANY question that carries options
 *   2. Dispatch sendSuggestion with the chip text on tap
 *   3. Show the free-text affordance under the chips
 *   4. Fall back to the legacy hardcoded budget tiers for budget questions
 *      WITHOUT options (old halt states / older backend)
 *   5. Render non-budget questions without options as plain tap-to-reply buttons
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

// ── Module-level mocks (must be before any component imports) ────────────────

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

// ── Helpers ───────────────────────────────────────────────────────────────────

const LAPTOP_USE_CASE_QUESTION = {
  slot: 'use_case',
  question: 'What will you mainly use it for?',
  options: ['Student / everyday', 'Gaming', 'Creative / video editing', 'Business / office'],
  free_text_hint: 'or describe your own use',
}

const LAPTOP_BUDGET_QUESTION = {
  slot: 'budget',
  question: "What's your budget?",
  options: ['Under $500', '$500–$800', '$800–$1,200', '$1,200+'],
  free_text_hint: 'or type an amount',
}

function makeClarifierMessage(questions: any[], overrides = {}) {
  return {
    id: 'msg-clarifier-1',
    role: 'assistant' as const,
    content: '',
    timestamp: Date.now(),
    followups: {
      intro: 'A couple of quick questions:',
      questions,
      closing: "Then I'll pull together a shortlist.",
    },
    ...overrides,
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. Backend-provided options render as chips for ANY question
// ─────────────────────────────────────────────────────────────────────────────

describe('Clarifier chips — backend-provided options', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders one chip per option for a non-budget question', () => {
    render(<Message message={makeClarifierMessage([LAPTOP_USE_CASE_QUESTION]) as any} />)

    const chips = screen.getAllByTestId('clarifier-option-chip')
    expect(chips).toHaveLength(4)
    expect(screen.getByText('Student / everyday')).toBeTruthy()
    expect(screen.getByText('Gaming')).toBeTruthy()
    expect(screen.getByText('Creative / video editing')).toBeTruthy()
    expect(screen.getByText('Business / office')).toBeTruthy()
  })

  it('renders the question text as a prompt above the chips', () => {
    render(<Message message={makeClarifierMessage([LAPTOP_USE_CASE_QUESTION]) as any} />)
    expect(screen.getByText('What will you mainly use it for?')).toBeTruthy()
  })

  it('renders backend budget options instead of the hardcoded tiers', () => {
    render(<Message message={makeClarifierMessage([LAPTOP_BUDGET_QUESTION]) as any} />)

    expect(screen.getByText('Under $500')).toBeTruthy()
    expect(screen.getByText('$1,200+')).toBeTruthy()
    // The nonsensical generic tier must NOT appear when the backend sent realistic ones
    expect(screen.queryByText('Under $50')).toBeNull()
  })

  it('renders the free_text_hint under the chips', () => {
    render(<Message message={makeClarifierMessage([LAPTOP_USE_CASE_QUESTION]) as any} />)
    expect(screen.getByText('or describe your own use')).toBeTruthy()
  })

  it('falls back to a default hint when free_text_hint is absent', () => {
    const q = { ...LAPTOP_USE_CASE_QUESTION, free_text_hint: undefined }
    render(<Message message={makeClarifierMessage([q]) as any} />)
    expect(screen.getByText('or just type your answer')).toBeTruthy()
  })

  it('tapping a chip dispatches sendSuggestion with the option text', () => {
    const dispatched: any[] = []
    const spy = vi
      .spyOn(window, 'dispatchEvent')
      .mockImplementation((event: Event) => {
        dispatched.push(event)
        return true
      })

    render(<Message message={makeClarifierMessage([LAPTOP_USE_CASE_QUESTION]) as any} />)
    fireEvent.click(screen.getByText('Gaming'))

    const sendEvents = dispatched.filter((e) => e.type === 'sendSuggestion')
    expect(sendEvents).toHaveLength(1)
    expect((sendEvents[0] as CustomEvent).detail.question).toBe('Gaming')
    spy.mockRestore()
  })

  it('renders chips for multiple questions at once (use case + budget)', () => {
    render(
      <Message
        message={makeClarifierMessage([LAPTOP_USE_CASE_QUESTION, LAPTOP_BUDGET_QUESTION]) as any}
      />
    )

    const questions = screen.getAllByTestId('clarifier-question')
    expect(questions).toHaveLength(2)
    const chips = screen.getAllByTestId('clarifier-option-chip')
    expect(chips).toHaveLength(8)
  })

  it('chips use the blueprint rounded-[12px] terra style', () => {
    const { container } = render(
      <Message message={makeClarifierMessage([LAPTOP_USE_CASE_QUESTION]) as any} />
    )
    const chip = container.querySelector('[data-testid="clarifier-option-chip"]')
    expect(chip?.className).toContain('rounded-[12px]')
    expect(chip?.className).toContain('border-[var(--line-2)]')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 2. Backward compatibility — legacy payloads without options
// ─────────────────────────────────────────────────────────────────────────────

describe('Clarifier chips — legacy fallbacks (no options from backend)', () => {
  it('budget question without options falls back to the hardcoded tiers', () => {
    const legacyBudget = { slot: 'budget', question: "What's your budget?" }
    render(<Message message={makeClarifierMessage([legacyBudget]) as any} />)

    expect(screen.getByText('Under $50')).toBeTruthy()
    expect(screen.getByText('$500+')).toBeTruthy()
    expect(screen.getByText('or just type a number')).toBeTruthy()
  })

  it('non-budget question without options renders as a plain tap-to-reply button (no chips)', () => {
    const legacyQuestion = { slot: 'destination', question: 'Where are you going?' }
    render(<Message message={makeClarifierMessage([legacyQuestion]) as any} />)

    expect(screen.queryAllByTestId('clarifier-option-chip')).toHaveLength(0)
    // The plain button still shows the question text
    expect(screen.getByText('Where are you going?')).toBeTruthy()
  })

  it('intro and closing still render around the questions', () => {
    render(<Message message={makeClarifierMessage([LAPTOP_USE_CASE_QUESTION]) as any} />)
    expect(screen.getByText('A couple of quick questions:')).toBeTruthy()
    expect(screen.getByText("Then I'll pull together a shortlist.")).toBeTruthy()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 3. Multi-select questions — chips toggle, "Done" submits the joined answer
// ─────────────────────────────────────────────────────────────────────────────

const HEADPHONES_FEATURES_MULTISELECT = {
  slot: 'features',
  question: 'Which features matter to you?',
  options: ['Noise cancelling', 'Waterproof', 'Wireless', 'No strong preference'],
  free_text_hint: 'or type your own',
  type: 'multi_select',
}

describe('Clarifier chips — multi-select questions', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('tapping a multi-select chip toggles selection instead of sending', () => {
    const dispatched: any[] = []
    const spy = vi
      .spyOn(window, 'dispatchEvent')
      .mockImplementation((event: Event) => {
        dispatched.push(event)
        return true
      })

    render(<Message message={makeClarifierMessage([HEADPHONES_FEATURES_MULTISELECT]) as any} />)
    const chip = screen.getByText('Noise cancelling')
    fireEvent.click(chip)

    // No send event — the chip is now selected (aria-pressed)
    expect(dispatched.filter((e) => e.type === 'sendSuggestion')).toHaveLength(0)
    expect(chip.closest('button')?.getAttribute('aria-pressed')).toBe('true')
    spy.mockRestore()
  })

  it('tapping a selected chip deselects it', () => {
    render(<Message message={makeClarifierMessage([HEADPHONES_FEATURES_MULTISELECT]) as any} />)
    const chip = screen.getByText('Waterproof')
    fireEvent.click(chip)
    expect(chip.closest('button')?.getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(chip)
    expect(chip.closest('button')?.getAttribute('aria-pressed')).toBe('false')
  })

  it('shows no Done button until something is selected', () => {
    render(<Message message={makeClarifierMessage([HEADPHONES_FEATURES_MULTISELECT]) as any} />)
    expect(screen.queryByTestId('clarifier-multiselect-done')).toBeNull()
    fireEvent.click(screen.getByText('Wireless'))
    expect(screen.getByTestId('clarifier-multiselect-done')).toBeTruthy()
  })

  it('Done submits the joined answer of all selected chips', () => {
    const dispatched: any[] = []
    const spy = vi
      .spyOn(window, 'dispatchEvent')
      .mockImplementation((event: Event) => {
        dispatched.push(event)
        return true
      })

    render(<Message message={makeClarifierMessage([HEADPHONES_FEATURES_MULTISELECT]) as any} />)
    fireEvent.click(screen.getByText('Noise cancelling'))
    fireEvent.click(screen.getByText('Waterproof'))
    fireEvent.click(screen.getByTestId('clarifier-multiselect-done'))

    const sendEvents = dispatched.filter((e) => e.type === 'sendSuggestion')
    expect(sendEvents).toHaveLength(1)
    expect((sendEvents[0] as CustomEvent).detail.question).toBe('Noise cancelling, Waterproof')
    spy.mockRestore()
  })

  it('selected chips render in terracotta (filled bg)', () => {
    render(<Message message={makeClarifierMessage([HEADPHONES_FEATURES_MULTISELECT]) as any} />)
    const chip = screen.getByText('Noise cancelling').closest('button')!
    expect(chip.className).not.toContain('bg-[var(--terra)]')
    fireEvent.click(chip)
    expect(chip.className).toContain('bg-[var(--terra)]')
  })

  it('single-select questions still send on first tap (regression)', () => {
    const dispatched: any[] = []
    const spy = vi
      .spyOn(window, 'dispatchEvent')
      .mockImplementation((event: Event) => {
        dispatched.push(event)
        return true
      })

    // Same question WITHOUT type: multi_select → tap sends immediately
    render(<Message message={makeClarifierMessage([LAPTOP_USE_CASE_QUESTION]) as any} />)
    fireEvent.click(screen.getByText('Gaming'))

    const sendEvents = dispatched.filter((e) => e.type === 'sendSuggestion')
    expect(sendEvents).toHaveLength(1)
    expect((sendEvents[0] as CustomEvent).detail.question).toBe('Gaming')
    spy.mockRestore()
  })

  it('renders a multi-select and single-select question side by side', () => {
    render(
      <Message
        message={makeClarifierMessage([HEADPHONES_FEATURES_MULTISELECT, LAPTOP_BUDGET_QUESTION]) as any}
      />
    )
    const questions = screen.getAllByTestId('clarifier-question')
    expect(questions).toHaveLength(2)
    // 4 multi-select chips + 4 budget chips
    expect(screen.getAllByTestId('clarifier-option-chip')).toHaveLength(8)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 4. QA Round 4 F0b — question locking: chips give feedback and can't double-submit
// ─────────────────────────────────────────────────────────────────────────────

describe('Clarifier chips — question locking after an answer (QA4 F0b)', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('tapping a single-select chip marks it selected (terracotta) and disables the question', () => {
    render(<Message message={makeClarifierMessage([LAPTOP_USE_CASE_QUESTION]) as any} />)
    const chip = screen.getByText('Gaming').closest('button')!
    fireEvent.click(chip)

    // The tapped chip is highlighted…
    expect(chip.className).toContain('bg-[var(--terra)]')
    expect(chip.getAttribute('aria-pressed')).toBe('true')
    // …and every chip in the question is now disabled
    const chips = screen.getAllByTestId('clarifier-option-chip')
    chips.forEach((c) => expect((c as HTMLButtonElement).disabled).toBe(true))
  })

  it('a second tap on another chip in the same question does NOT dispatch a second send', () => {
    const dispatched: any[] = []
    const spy = vi
      .spyOn(window, 'dispatchEvent')
      .mockImplementation((event: Event) => {
        dispatched.push(event)
        return true
      })

    render(<Message message={makeClarifierMessage([LAPTOP_USE_CASE_QUESTION]) as any} />)
    fireEvent.click(screen.getByText('Gaming'))
    fireEvent.click(screen.getByText('Business / office'))
    fireEvent.click(screen.getByText('Gaming')) // double-tap the same chip too

    const sendEvents = dispatched.filter((e) => e.type === 'sendSuggestion')
    expect(sendEvents).toHaveLength(1)
    expect((sendEvents[0] as CustomEvent).detail.question).toBe('Gaming')
    spy.mockRestore()
  })

  it('answering one question does not lock a different question in the same block', () => {
    const dispatched: any[] = []
    const spy = vi
      .spyOn(window, 'dispatchEvent')
      .mockImplementation((event: Event) => {
        dispatched.push(event)
        return true
      })

    render(
      <Message
        message={makeClarifierMessage([LAPTOP_USE_CASE_QUESTION, LAPTOP_BUDGET_QUESTION]) as any}
      />
    )
    fireEvent.click(screen.getByText('Gaming'))
    // The budget question is its own component instance — still answerable
    fireEvent.click(screen.getByText('Under $500'))

    const sendEvents = dispatched.filter((e) => e.type === 'sendSuggestion')
    expect(sendEvents).toHaveLength(2)
    expect((sendEvents[1] as CustomEvent).detail.question).toBe('Under $500')
    spy.mockRestore()
  })

  it('multi-select Done locks the question — chips and Done go inert after submit', () => {
    const dispatched: any[] = []
    const spy = vi
      .spyOn(window, 'dispatchEvent')
      .mockImplementation((event: Event) => {
        dispatched.push(event)
        return true
      })

    render(<Message message={makeClarifierMessage([HEADPHONES_FEATURES_MULTISELECT]) as any} />)
    fireEvent.click(screen.getByText('Noise cancelling'))
    fireEvent.click(screen.getByTestId('clarifier-multiselect-done'))

    // Done button disappears after submit; chips are disabled
    expect(screen.queryByTestId('clarifier-multiselect-done')).toBeNull()
    const chips = screen.getAllByTestId('clarifier-option-chip')
    chips.forEach((c) => expect((c as HTMLButtonElement).disabled).toBe(true))

    // Toggling a chip after submit must not change selection or re-send
    fireEvent.click(screen.getByText('Waterproof'))
    const sendEvents = dispatched.filter((e) => e.type === 'sendSuggestion')
    expect(sendEvents).toHaveLength(1)
    spy.mockRestore()
  })
})
