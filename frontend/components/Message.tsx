'use client'

import { User, Copy, Check, ArrowRight } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { motion } from 'framer-motion'
import { Message as MessageType } from './ChatContainer'
import { NextSuggestion, SuggestionCategory } from '@/lib/chatApi'
import { normalizeBlocks } from '@/lib/normalizeBlocks'
import { UIBlocks } from '@/components/blocks/BlockRegistry'
import MessageRecoveryUI from './MessageRecoveryUI'
import LoadingStatusText from './LoadingStatusText'
import { TransitionalBubble } from './Brand'

import { useState, useEffect, useMemo } from 'react'
import { formatTimestamp, formatFullTimestamp, SUGGESTION_CLICK_PREFIX } from '@/lib/utils'
import { trackAffiliate } from '@/lib/trackAffiliate'

// RFC §2.4 — Category sort priority: clarify > refine_* > alternate_destination > compare > deeper_research
const CATEGORY_SORT_ORDER: Record<SuggestionCategory, number> = {
  clarify: 0,
  refine_budget: 1,
  refine_features: 2,
  alternate_destination: 3,
  compare: 4,
  deeper_research: 5,
}

// RFC §2.4 — Human-readable category labels for editorial chips
const CATEGORY_LABELS: Record<string, string> = {
  clarify: 'Clarify',
  compare: 'Compare',
  refine_budget: 'Budget',
  refine_features: 'Features',
  deeper_research: 'Deep dive',
  alternate_destination: 'Alternatives',
}

/**
 * RFC §2.4 — Sort suggestions by category priority.
 * Suggestions without a category are treated as lowest priority (after deeper_research).
 */
function sortSuggestions(suggestions: NextSuggestion[]): NextSuggestion[] {
  return [...suggestions].sort((a, b) => {
    const orderA = a.category !== undefined ? CATEGORY_SORT_ORDER[a.category] : 99
    const orderB = b.category !== undefined ? CATEGORY_SORT_ORDER[b.category] : 99
    return orderA - orderB
  })
}

/**
 * RFC §2.4 — Track a suggestion chip click with provenance data.
 */
function trackSuggestionClick(suggestion: NextSuggestion, messageId: string, index: number): void {
  trackAffiliate('suggestion_click', {
    suggestion_id: suggestion.id,
    category: suggestion.category ?? 'unknown',
    message_id: messageId,
    position: index,
  })
}

// ─── Clarifier card (QA Round 5, external bugs 1+2) ─────────────────────────
//
// The clarifying questions render as ONE card that behaves like a form:
//   - every question group accumulates a selection (radio for single-select,
//     checkboxes for multi-select) WITHOUT sending anything
//   - one "Get recommendations →" button submits all answers as a single turn
//     ("Road running; Max cushion, Lightweight; $80–$130") — one round-trip
//     instead of one per question
//   - single-question cards keep the lighter interactions: single-select chips
//     send on tap; a lone multi-select keeps its "Done →" button
// After submit the whole card locks (QA Round 4 F0b — feedback + no duplicates).

const CHIP_SELECTED =
  'inline-flex items-center gap-2 rounded-[12px] border border-[var(--terra)] bg-[var(--terra)] transition-all px-3.5 py-2 text-[14px] font-medium text-white'
const CHIP_LOCKED =
  'inline-flex items-center gap-2 rounded-[12px] border border-[var(--line-2)] bg-[var(--paper-hi)] transition-all px-3.5 py-2 text-[14px] font-medium text-[var(--ink-3)] opacity-60'
const CHIP_IDLE =
  'inline-flex items-center gap-2 rounded-[12px] border border-[var(--line-2)] bg-[var(--paper-hi)] hover:border-[var(--terra)] hover:bg-[var(--terra-soft)] transition-all px-3.5 py-2 text-[14px] font-medium text-[var(--ink)]'

/** One question's chip row. Fully controlled — selection lives in ClarifierCard. */
function ClarifierQuestionGroup({
  question,
  options,
  hint,
  multiSelect,
  selected,
  onSelect,
  locked,
  preferenceOption,
}: {
  question: string
  options: string[]
  hint: string
  multiSelect: boolean
  selected: string[]
  onSelect: (next: string[]) => void
  locked: boolean
  /** Outcome 7: the user's stored past answer — rendered with "(like last time)" */
  preferenceOption?: string
}) {
  const toggle = (option: string) => {
    if (locked) return
    if (multiSelect) {
      onSelect(
        selected.includes(option) ? selected.filter((o) => o !== option) : [...selected, option]
      )
    } else {
      // Radio behavior: tap selects, tapping the same chip again deselects
      onSelect(selected.includes(option) ? [] : [option])
    }
  }

  return (
    <div className="space-y-2" data-testid="clarifier-question">
      <p className="text-[14px] leading-[20px] text-[var(--ink)]">{question}</p>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const isSelected = selected.includes(option)
          return (
            <button
              key={option}
              onClick={() => toggle(option)}
              disabled={locked}
              data-testid="clarifier-option-chip"
              aria-pressed={isSelected}
              className={isSelected ? CHIP_SELECTED : locked ? CHIP_LOCKED : CHIP_IDLE}
            >
              <span
                className="w-1 h-1 rounded-full flex-shrink-0"
                style={{ background: isSelected ? '#fff' : 'var(--terra)' }}
              />
              {option}
              {/* Outcome 7: returning users see their past answer tagged */}
              {option === preferenceOption && (
                <span
                  data-testid="clarifier-preference-tag"
                  className="text-[11px] italic"
                  style={{ opacity: 0.7 }}
                >
                  (like last time)
                </span>
              )}
            </button>
          )
        })}
      </div>
      <p className="text-[12px] italic text-[var(--ink-3)]">{hint}</p>
    </div>
  )
}

interface ClarifierQuestion {
  slot: string
  question: string
  options?: string[]
  free_text_hint?: string
  type?: string
  /** Outcome 7: the stored past answer the backend moved to the front of options */
  preference_chip?: string
}

/** The whole clarifying-questions card: question groups + one submit. */
function ClarifierCard({
  intro,
  questions,
  closing,
  onSubmit,
}: {
  intro?: string
  questions: ClarifierQuestion[]
  closing?: string
  onSubmit: (text: string) => void
}) {
  // selections: slot -> chosen option(s)
  const [selections, setSelections] = useState<Record<string, string[]>>({})
  const [submitted, setSubmitted] = useState(false)

  // Resolve each question's chips (legacy budget payloads fall back to generic tiers).
  const resolved = questions.map((q) => {
    const isBudget = q.slot === 'budget' || /budget|price range|how much|spend/i.test(q.question)
    const options =
      q.options && q.options.length > 0
        ? q.options
        : isBudget
          ? ['Under $50', '$50–$100', '$100–$250', '$250–$500', '$500+']
          : null
    const hint = q.free_text_hint || (isBudget ? 'or just type a number' : 'or just type your answer')
    return { ...q, resolvedOptions: options, resolvedHint: hint }
  })

  const chipQuestions = resolved.filter((q) => q.resolvedOptions !== null)
  const isSingleQuestionCard = chipQuestions.length === 1
  const answeredSlots = chipQuestions.filter((q) => (selections[q.slot] ?? []).length > 0)

  // Combined answer: each answered question's value(s), question order preserved.
  // Multi-select values join with ", " inside a part; parts join with "; ".
  const buildCombinedAnswer = (sel: Record<string, string[]>) =>
    chipQuestions
      .map((q) => (sel[q.slot] ?? []).join(', '))
      .filter(Boolean)
      .join('; ')

  const submitCard = () => {
    if (submitted || answeredSlots.length === 0) return
    setSubmitted(true)
    onSubmit(buildCombinedAnswer(selections))
  }

  const handleSelect = (q: (typeof resolved)[number], next: string[]) => {
    if (submitted) return
    const nextSelections = { ...selections, [q.slot]: next }
    setSelections(nextSelections)
    // Single-question card + single-select → keep the one-tap-sends UX
    if (isSingleQuestionCard && q.type !== 'multi_select' && next.length === 1) {
      setSubmitted(true)
      onSubmit(next[0])
    }
  }

  // Submit button: multi-question cards always get one; a lone multi-select
  // question keeps its "Done" (same behavior, familiar label + testid).
  const needsSubmitButton = !isSingleQuestionCard || chipQuestions[0]?.type === 'multi_select'

  return (
    <div className="w-full mt-5">
      <div className="rounded-[14px] p-4">
        {intro && (
          <p className="text-[15px] font-medium text-[var(--ink)] mb-3">{intro}</p>
        )}
        <div className="space-y-3">
          {resolved.map((q, idx) => {
            if (q.resolvedOptions) {
              return (
                <ClarifierQuestionGroup
                  key={idx}
                  question={q.question}
                  options={q.resolvedOptions}
                  hint={q.resolvedHint}
                  multiSelect={q.type === 'multi_select'}
                  selected={selections[q.slot] ?? []}
                  onSelect={(next) => handleSelect(q, next)}
                  locked={submitted}
                  preferenceOption={q.preference_chip}
                />
              )
            }
            // Legacy payloads without options: plain tap-to-reply button
            return (
              <button
                key={idx}
                className="w-full text-left px-3.5 py-2.5 rounded-[12px] border border-[var(--line-2)] bg-[var(--paper-hi)] hover:border-[var(--terra)] hover:bg-[var(--terra-soft)] transition-all text-[14px] leading-[20px] font-medium text-[var(--ink)] flex items-center gap-2.5 group"
                onClick={() => onSubmit(q.question)}
              >
                {/* 4px terracotta leading dot — reads as "tap to reply" */}
                <span className="w-1 h-1 rounded-full flex-shrink-0" style={{ background: 'var(--terra)' }} />
                <span className="flex-1">{q.question}</span>
                <ArrowRight size={14} strokeWidth={1.5} className="opacity-0 group-hover:opacity-100 transition-opacity text-[var(--terra)]" />
              </button>
            )
          })}
        </div>
        {/* The card's single submit */}
        {needsSubmitButton && answeredSlots.length > 0 && !submitted && (
          <button
            onClick={submitCard}
            data-testid={isSingleQuestionCard ? 'clarifier-multiselect-done' : 'clarifier-card-submit'}
            className="mt-4 inline-flex items-center gap-2 rounded-[12px] border border-[var(--terra)] bg-[var(--terra)] hover:opacity-90 transition-all px-4 py-2.5 text-[14px] font-semibold text-white"
          >
            {isSingleQuestionCard ? 'Done' : 'Get recommendations'}
            <ArrowRight size={14} strokeWidth={1.5} />
          </button>
        )}
        {/* Progress nudge: answered some but not all, submit available */}
        {needsSubmitButton && !submitted && answeredSlots.length > 0 && answeredSlots.length < chipQuestions.length && (
          <p className="mt-2 text-[12px] italic text-[var(--ink-3)]">
            You can answer the rest or submit now — I&apos;ll work with what you give me.
          </p>
        )}
        {/* Outcome 8 — skip-all escape hatch: proceed with no constraints at all */}
        {!submitted && (
          <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--line)' }}>
            <button
              onClick={() => {
                setSubmitted(true)
                onSubmit('Just show me the best overall')
              }}
              data-testid="clarifier-skip-all"
              className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[var(--ink-2)] hover:text-[var(--terra)] transition-colors"
            >
              <span className="underline underline-offset-4 decoration-[var(--line-2)]">
                Just show me the best overall
              </span>
              <ArrowRight size={13} strokeWidth={1.5} />
            </button>
          </div>
        )}
        {closing && (
          <p className="mt-3 text-[12px] italic text-[var(--ink-3)]">{closing}</p>
        )}
      </div>
    </div>
  )
}

interface MessageProps {
  message: MessageType
  isLast?: boolean
}

export default function Message({ message, isLast = false }: MessageProps) {
  const isUser = message.role === 'user'
  const [copied, setCopied] = useState(false)
  const [relativeTime, setRelativeTime] = useState(() => formatTimestamp(message.timestamp))
  // Blueprint §7 — prior blogs collapse to a short lede on a later turn; only the
  // live (last) blog stays full-size. Tap to re-expand.
  const [blogExpanded, setBlogExpanded] = useState(false)

  // RFC §2.4 — Memoize suggestion sort to avoid re-sorting on every render during streaming
  const sortedSuggestions = useMemo(
    () => sortSuggestions(message.next_suggestions ?? []),
    [message.next_suggestions]
  )

  // Update relative timestamp every minute.
  // D3 (perf): in a long thread every message keeps its own 60s ticker; pause
  // them while the tab is hidden (and resync on return) so a backgrounded chat
  // does no per-minute work.
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null
    const tick = () => setRelativeTime(formatTimestamp(message.timestamp))
    const start = () => {
      if (!interval) interval = setInterval(tick, 60000)
    }
    const stop = () => {
      if (interval) {
        clearInterval(interval)
        interval = null
      }
    }
    const onVisibility = () => {
      if (typeof document === 'undefined' || document.visibilityState === 'visible') {
        tick() // resync the time we missed while hidden
        start()
      } else {
        stop()
      }
    }
    onVisibility()
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisibility)
    }
    return () => {
      stop()
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', onVisibility)
      }
    }
  }, [message.timestamp])

  const handleCopy = async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(message.content)
      } else {
        const textArea = document.createElement('textarea')
        textArea.value = message.content
        textArea.style.position = 'fixed'
        textArea.style.left = '-999999px'
        textArea.style.top = '-999999px'
        document.body.appendChild(textArea)
        textArea.focus()
        textArea.select()
        try {
          document.execCommand('copy')
        } finally {
          document.body.removeChild(textArea)
        }
      }
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy text:', err)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      id={`message-${message.id}`}
      className="w-full py-4 sm:py-5 px-3 sm:px-4"
    >
      <div id="message-container" className="mr-auto flex gap-2 sm:gap-4 items-start flex-row overflow-hidden max-w-full" style={{ maxWidth: '780px' }}>
        {/* Avatar - Only show for assistant */}
        {!isUser && (
          <div className="flex-shrink-0 mt-0.5">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-[var(--primary)] shadow-sm">
              <img
                src="/images/8f4c1971-a5b0-474e-9fb1-698e76324f0b.png"
                alt="AI"
                className="w-4 h-4 rounded"
              />
            </div>
          </div>
        )}

        {/* Message Content */}
        <div className={`flex-1 min-w-0 ${isUser ? 'flex flex-col items-end' : 'text-left'}`}>
          {isUser ? (
            message.isSuggestionClick ? (
              // Suggestion click: show as subtle pill
              <div className="w-full flex justify-end">
                <div className="text-xs sm:text-sm py-2 px-4 rounded-full border border-[var(--border)] bg-[var(--surface)] text-[var(--text-secondary)]">
                  <span className="opacity-60">{SUGGESTION_CLICK_PREFIX}</span>{' '}
                  <span className="font-medium text-[var(--text)]">
                    {message.content.startsWith(SUGGESTION_CLICK_PREFIX)
                      ? message.content.slice(SUGGESTION_CLICK_PREFIX.length).trim()
                      : message.content}
                  </span>
                </div>
              </div>
            ) : (
              // Regular user message: editorial bubble
              <>
                <div className="relative group flex items-start justify-end max-w-full gap-2.5">
                  {/* Blueprint user bubble: ink bg, paper text, asymmetric 14/14/4/14 (bottom-right squared) */}
                  <div className="px-4 py-3 rounded-tl-[14px] rounded-tr-[14px] rounded-br-[4px] rounded-bl-[14px] bg-[var(--ink)] text-[var(--paper)] shadow-card max-w-[80%]">
                    <p className="whitespace-pre-wrap text-[15px] leading-[22px]">
                      {message.content}
                    </p>
                  </div>

                  {/* User Avatar */}
                  <div className="flex-shrink-0 mt-0.5">
                    <div className="w-7 h-7 rounded-full flex items-center justify-center bg-[var(--surface-hover)] text-[var(--text-muted)] border border-[var(--border)]">
                      <User size={14} strokeWidth={1.5} />
                    </div>
                  </div>
                </div>
                {/* Timestamp */}
                <div className="text-[10px] text-[var(--text-muted)] text-right mt-1.5 mr-10">
                  {relativeTime}
                </div>
              </>
            )
          ) : (
            <div className="w-full">
              {/* Blueprint quiz-path: transitional reasoning beat before the AI turn */}
              {message.transitionalReasoning && (
                <div className="mb-3">
                  <TransitionalBubble>{message.transitionalReasoning}</TransitionalBubble>
                </div>
              )}
              {/* AI bubble wrapper */}
              <div
                className="rounded-tl-[14px] rounded-tr-[14px] rounded-br-[14px] rounded-bl-[4px] border border-[var(--line)] px-4 py-3.5"
                style={{ background: 'var(--paper-hi)', maxWidth: '85%' }}
              >
                {/* ReviewGuide byline */}
                <div className="text-[12px] font-semibold mb-2" style={{ color: 'var(--primary)' }}>
                  ✦ ReviewGuide
                </div>

                {/* Status indicator — shown while tools are working.
                    Copy: server-emitted statusText for first ~4s of each
                    tool, then rotates through the tone.md §10.1
                    vocabulary while the tool keeps running. Never
                    "Thinking..." — that fallback was the most visible
                    voice violation on the chat screen pre-B.1. */}
                {!message.content && message.isThinking && (
                  <div className="flex items-center gap-2.5 py-1.5">
                    {/* Blueprint loading: single 8px terra dot, breathing 1.6s */}
                    <span className="w-2 h-2 rounded-full bg-[var(--terra)] rg-breath flex-shrink-0" />
                    <LoadingStatusText
                      statusText={message.statusText}
                      className="rg-display text-[18px] leading-[24px] text-[var(--ink-2)]"
                    />
                  </div>
                )}

                {/* 1. Render text content FIRST. For product-results turns, render
                    as the blueprint editorial blog card: "THE PICK" terra eyebrow +
                    Newsreader (font-serif) body. Ordinary chat answers stay plain. */}
                {message.content && (() => {
                  const isBlogResult =
                    Array.isArray(message.ui_blocks) &&
                    message.ui_blocks.some(
                      (b: any) => typeof b?.type === 'string' && b.type.toLowerCase().includes('product')
                    )
                  // Prior blogs (not the live/last one) collapse to a short lede.
                  const collapsed = isBlogResult && !isLast && !blogExpanded
                  return (
                    <div className="w-full rg-blog-in">
                      {isBlogResult && (
                        <>
                          <div className="rg-eyebrow rg-eyebrow--terra mb-2">The pick</div>
                          <div className="rg-hairline mb-3" />
                        </>
                      )}
                      <div className={
                        (collapsed ? 'line-clamp-2 ' : '') +
                        (isBlogResult
                          ? `prose prose-sm sm:prose-base max-w-none
                            prose-headings:font-display prose-headings:not-italic prose-headings:text-[var(--ink)]
                            prose-p:font-serif prose-p:text-[var(--ink)] prose-p:text-[16px] prose-p:leading-[26px]
                            prose-strong:text-[var(--ink)] prose-strong:font-semibold
                            prose-li:font-serif prose-li:text-[var(--ink)] prose-li:leading-[26px]
                            prose-a:text-[var(--ink)] prose-a:decoration-dotted prose-a:decoration-[var(--terra)] prose-a:underline-offset-4`
                          : `prose prose-sm sm:prose-base max-w-none
                            text-[var(--text)]
                            prose-headings:font-serif prose-headings:tracking-tight prose-headings:text-[var(--text)]
                            prose-p:text-[var(--text)] prose-p:leading-relaxed prose-p:text-[15px]
                            prose-strong:text-[var(--text)] prose-strong:font-semibold
                            prose-li:text-[var(--text)] prose-li:marker:text-[var(--text-muted)]
                            prose-pre:bg-[var(--surface)] prose-pre:border prose-pre:border-[var(--border)] prose-pre:rounded-xl
                            prose-a:text-[var(--primary)] prose-a:no-underline hover:prose-a:underline`)
                      }>
                        <ReactMarkdown>{message.content}</ReactMarkdown>
                      </div>
                      {isBlogResult && !isLast && (
                        <button
                          onClick={() => setBlogExpanded((v) => !v)}
                          className="rg-eyebrow rg-eyebrow--terra mt-2 cursor-pointer"
                        >
                          {blogExpanded ? 'Show less ↑' : 'Show the full take ↓'}
                        </button>
                      )}
                    </div>
                  )
                })()}

                {/* B.3 — Curious follow-up question. Lives between the body
                    and the UI blocks (carousel) so it's still inside the
                    AI bubble per spec §11. Visual treatment is the restrained
                    baseline noted in plan B.3: italic + medium weight + muted
                    color + small top margin + thin hairline above. Design
                    review (§13 #3 open question) may iterate on this. */}
                {message.followUpQuestion && (
                  <div className="mt-4">
                    {/* Blueprint §13 #3: 24px terra hairline above, then the question on its own line */}
                    <div className="rg-hairline-short mb-3" />
                    <p className="rg-display text-[19px] leading-[26px] text-[var(--ink)]">
                      {message.followUpQuestion}
                    </p>
                  </div>
                )}

                {/* 2. Render all UI blocks via registry-driven dispatcher */}
                <UIBlocks
                  blocks={normalizeBlocks(message.ui_blocks ?? [])}
                  itinerary={message.itinerary}
                />

                {/* 3. Render clarifier follow-up questions as ONE form-style card:
                    all question groups accumulate selections, a single submit sends
                    the combined answer (QA Round 5, external bugs 1+2). */}
                {message.followups && typeof message.followups === 'object' && !Array.isArray(message.followups) && (
                  <ClarifierCard
                    intro={message.followups.intro}
                    questions={(message.followups.questions ?? []) as ClarifierQuestion[]}
                    closing={message.followups.closing}
                    onSubmit={(text: string) =>
                      window.dispatchEvent(new CustomEvent('sendSuggestion', { detail: { question: text } }))
                    }
                  />
                )}

                {/* RFC §2.3: degraded completeness indicator */}
                {message.completeness === 'degraded' && (
                  <MessageRecoveryUI
                    completeness="degraded"
                  />
                )}

                {/* Timestamp for assistant */}
                <div
                  className="text-[10px] text-[var(--text-muted)] mt-2 ml-0.5"
                  title={formatFullTimestamp(message.timestamp)}
                >
                  {relativeTime}
                </div>
              </div>

              {/* RFC §2.4: next_suggestions — horizontal pill chips OUTSIDE the bubble */}
              {message.next_suggestions && message.next_suggestions.length > 0 && (
                <div
                  className="flex flex-row flex-wrap gap-2 mt-3"
                  data-testid="next-suggestions-container"
                >
                  {sortedSuggestions.map((suggestion, idx) => (
                    <button
                      key={suggestion.id}
                      data-testid={`suggestion-chip-${idx}`}
                      data-category={suggestion.category}
                      className="inline-flex items-center gap-2 rounded-[12px] border border-[var(--line-2)] bg-[var(--paper-hi)] text-[var(--ink)] px-3.5 py-2.5 text-[14px] leading-[20px] font-medium text-left transition-all hover:border-[var(--terra)] hover:bg-[var(--terra-soft)]"
                      onClick={() => {
                        trackSuggestionClick(suggestion, message.id, idx)
                        const event = new CustomEvent('sendSuggestion', {
                          detail: { question: suggestion.question }
                        })
                        window.dispatchEvent(event)
                      }}
                    >
                      {/* quiz-path 4px terracotta leading dot */}
                      <span className="w-1 h-1 rounded-full flex-shrink-0" style={{ background: 'var(--terra)' }} />
                      {suggestion.question}
                    </button>
                  ))}
                </div>
              )}

              {/* "or ask me anything" — only on the last completed assistant message with no chips */}
              {isLast && message.content && !message.isThinking && !(message.next_suggestions?.length) && (
                <p className="text-[13px] text-[var(--text-muted)] mt-3 leading-relaxed">
                  or ask me anything
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}
