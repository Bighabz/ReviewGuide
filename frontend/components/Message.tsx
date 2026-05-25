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
                  <div className="px-4 py-3 rounded-tl-[20px] rounded-tr-[20px] rounded-br-[4px] rounded-bl-[20px] bg-[var(--primary)] text-white shadow-card max-w-[80%]">
                    <p className="whitespace-pre-wrap text-[15px] leading-relaxed">
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
              {/* AI bubble wrapper */}
              <div
                className="rounded-tl-[4px] rounded-tr-[20px] rounded-br-[20px] rounded-bl-[20px] border border-[var(--border)] p-4"
                style={{ background: 'var(--surface-elevated)', maxWidth: '85%' }}
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
                  <div className="flex items-center gap-2 py-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--primary)] animate-pulse" />
                    <LoadingStatusText
                      statusText={message.statusText}
                      className="stream-status-text tracking-tight"
                    />
                  </div>
                )}

                {/* 1. Render text content FIRST (brief summary) */}
                {message.content && (
                  <div className="w-full">
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

                {/* 2. Render all UI blocks via registry-driven dispatcher */}
                <UIBlocks
                  blocks={normalizeBlocks(message.ui_blocks ?? [])}
                  itinerary={message.itinerary}
                />

                {/* 3. Render clarifier follow-up questions (structured slot-filling) */}
                {message.followups && typeof message.followups === 'object' && !Array.isArray(message.followups) && (
                  <div className="w-full mt-5">
                    <div className="border border-[var(--border)] rounded-xl p-4 bg-[var(--surface)]">
                      {message.followups.intro && (
                        <p className="text-sm font-medium text-[var(--text)] mb-3">
                          {message.followups.intro}
                        </p>
                      )}
                      <div className="space-y-1.5">
                        {message.followups.questions && message.followups.questions.map((q: { slot: string; question: string }, idx: number) => (
                          <button
                            key={idx}
                            className="w-full text-left px-3.5 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background)] hover:border-[var(--primary)] hover:bg-[var(--primary-light)] transition-all text-sm text-[var(--text)] flex items-center justify-between group"
                            onClick={() => {
                              const event = new CustomEvent('sendSuggestion', {
                                detail: { question: q.question }
                              })
                              window.dispatchEvent(event)
                            }}
                          >
                            <span>{q.question}</span>
                            <ArrowRight size={14} strokeWidth={1.5} className="opacity-0 group-hover:opacity-100 transition-opacity text-[var(--primary)]" />
                          </button>
                        ))}
                      </div>
                      {message.followups.closing && (
                        <p className="mt-3 text-xs italic text-[var(--text-muted)]">
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
                      className="rounded-[20px] border border-[var(--primary)] text-[var(--primary)] bg-transparent px-4 py-2 text-[13px] font-medium transition-all hover:bg-[var(--primary-light)]"
                      onClick={() => {
                        trackSuggestionClick(suggestion, message.id, idx)
                        const event = new CustomEvent('sendSuggestion', {
                          detail: { question: suggestion.question }
                        })
                        window.dispatchEvent(event)
                      }}
                    >
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
