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

interface MessageProps {
  message: MessageType
  isLast?: boolean
}

export default function Message({ message, isLast = false }: MessageProps) {
  const isUser = message.role === 'user'
  const [copied, setCopied] = useState(false)
  const [relativeTime, setRelativeTime] = useState(() => formatTimestamp(message.timestamp))

  // RFC §2.4 — Memoize suggestion sort to avoid re-sorting on every render during streaming
  const sortedSuggestions = useMemo(
    () => sortSuggestions(message.next_suggestions ?? []),
    [message.next_suggestions]
  )

  // Update relative timestamp every minute
  useEffect(() => {
    const interval = setInterval(() => {
      setRelativeTime(formatTimestamp(message.timestamp))
    }, 60000) // Update every minute

    return () => clearInterval(interval)
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

                {/* 1. Render text content FIRST (brief summary) */}
                {message.content && (
                  <div className="w-full rg-blog-in">
                    <div className="prose prose-sm sm:prose-base max-w-none
                        text-[var(--text)]
                        prose-headings:font-serif prose-headings:tracking-tight prose-headings:text-[var(--text)]
                        prose-p:text-[var(--text)] prose-p:leading-relaxed prose-p:text-[15px]
                        prose-strong:text-[var(--text)] prose-strong:font-semibold
                        prose-li:text-[var(--text)] prose-li:marker:text-[var(--text-muted)]
                        prose-pre:bg-[var(--surface)] prose-pre:border prose-pre:border-[var(--border)] prose-pre:rounded-xl
                        prose-a:text-[var(--primary)] prose-a:no-underline hover:prose-a:underline"
                    >
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    </div>
                  </div>
                )}

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

                {/* 3. Render clarifier follow-up questions (structured slot-filling) */}
                {message.followups && typeof message.followups === 'object' && !Array.isArray(message.followups) && (
                  <div className="w-full mt-5">
                    <div className="rounded-[14px] p-4">
                      {message.followups.intro && (
                        <p className="text-[15px] font-medium text-[var(--ink)] mb-3">
                          {message.followups.intro}
                        </p>
                      )}
                      <div className="space-y-2">
                        {message.followups.questions && message.followups.questions.map((q: { slot: string; question: string }, idx: number) => (
                          <button
                            key={idx}
                            className="w-full text-left px-3.5 py-2.5 rounded-[12px] border border-[var(--line-2)] bg-[var(--paper-hi)] hover:border-[var(--terra)] hover:bg-[var(--terra-soft)] transition-all text-[14px] leading-[20px] font-medium text-[var(--ink)] flex items-center gap-2.5 group"
                            onClick={() => {
                              const event = new CustomEvent('sendSuggestion', {
                                detail: { question: q.question }
                              })
                              window.dispatchEvent(event)
                            }}
                          >
                            {/* 4px terracotta leading dot — reads as "tap to reply" */}
                            <span className="w-1 h-1 rounded-full flex-shrink-0" style={{ background: 'var(--terra)' }} />
                            <span className="flex-1">{q.question}</span>
                            <ArrowRight size={14} strokeWidth={1.5} className="opacity-0 group-hover:opacity-100 transition-opacity text-[var(--terra)]" />
                          </button>
                        ))}
                      </div>
                      {message.followups.closing && (
                        <p className="mt-3 text-[12px] italic text-[var(--ink-3)]">
                          {message.followups.closing}
                        </p>
                      )}
                    </div>
                  </div>
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
