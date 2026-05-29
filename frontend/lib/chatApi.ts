/**
 * Chat API Client with SSE Streaming Support
 * Includes auto-reconnect with exponential backoff
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Retry configuration
const MAX_RETRIES = 3
const INITIAL_BACKOFF_MS = 1000
const MAX_BACKOFF_MS = 10000
const REQUEST_TIMEOUT_MS = 120000 // 2 minutes

/**
 * Sleep for a specified duration
 */
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * Calculate exponential backoff with jitter
 */
function getBackoffDelay(attempt: number): number {
  const backoff = Math.min(INITIAL_BACKOFF_MS * Math.pow(2, attempt), MAX_BACKOFF_MS)
  // Add jitter (0-25% of backoff)
  const jitter = backoff * Math.random() * 0.25
  return backoff + jitter
}

// RFC §2.5 — Content trust and explainability types

export interface ProviderCoverage {
  provider: string      // "ebay" | "amazon" | "perplexity" | "serpapi" | "amadeus" | "booking" | "viator"
  status: 'ok' | 'partial' | 'unavailable' | 'timed_out'
  result_count?: number
}

export interface ResponseMetadata {
  source_count: number
  provider_coverage: ProviderCoverage[]
  confidence_score: number        // 0.0–1.0 aggregate
  omitted_sections: string[]      // e.g. ["affiliate_links", "review_ranking"]
  degraded: boolean
  missing_sources: string[]       // provider keys that had no results
  web_context_cache_age_s?: number | null
}

// RFC §2.4 — Typed suggestions with category and click provenance
export type SuggestionCategory =
  | 'clarify'
  | 'compare'
  | 'refine_budget'
  | 'refine_features'
  | 'alternate_destination'
  | 'deeper_research'

export interface NextSuggestion {
  id: string
  question: string
  /** RFC §2.4: suggestion category — used for sorting and label rendering */
  category?: SuggestionCategory
  /** RFC §2.4: LLM-estimated confidence 0.0–1.0 */
  confidence?: number
  /** RFC §2.4: tool gap that prompted this suggestion */
  tool_gap?: string
}

export interface StreamChunk {
  token?: string
  done: boolean
  error?: string
  session_id?: string
  user_id?: number  // User ID returned by backend for persistence
  status?: string
  intent?: string
  ui_blocks?: any[]
  citations?: string[]
  followups?: string[]
  itinerary?: any[]  // Travel itinerary data
  next_suggestions?: NextSuggestion[]  // Follow-up questions from next_step_suggestion tool
  // B.3 — the curious follow-up question, emitted by the backend as its own
  // SSE event (`event: follow_up_question`) after the content stream finishes.
  // Frontend renders it distinctly (own line, italic) below the message body
  // per spec §11 / §13 #3. snake_case to match the wire format.
  follow_up_question?: string
  // Quiz-path transitional reasoning — emitted as its own SSE event; frontend
  // renders it as a TransitionalBubble before the AI bubble. snake_case = wire format.
  transitional_reasoning?: string
  placeholder?: boolean
  clear?: boolean
  status_update?: string  // Agent status messages (e.g., "writing itinerary...")
  agent?: string  // Which agent sent the status
  create_new_message?: boolean  // Flag to tell frontend to create new message for subsequent data
  // RFC §1.8 named event channel fields
  text?: string          // status event: human-readable status text
  step?: number          // status event: step number
  type?: string          // artifact event: block type identifier
  blocks?: any[]         // artifact event: block data payload
  code?: string          // error event: error code
  message?: string       // error event: error message
  recoverable?: boolean  // error event: whether error is recoverable
  completeness?: string  // done event: "full" | "degraded"
  // RFC §4.1 correlation
  request_id?: string    // done event: backend request_id for trace correlation
  // RFC §2.5 content trust
  response_metadata?: ResponseMetadata  // done event: provider coverage and confidence
}

// RFC §4.1 — Render milestone timestamps for p95 time-to-first-content calculation
interface RenderMilestones {
  interaction_id: string
  request_sent_ts: number
  first_status_ts: number | null
  first_content_ts: number | null
  first_artifact_ts: number | null
  done_ts: number | null
}

/**
 * Fire-and-forget helper: POST render milestones to the telemetry endpoint.
 * Errors are intentionally swallowed — telemetry is best-effort.
 */
function sendTelemetry(milestones: RenderMilestones): void {
  fetch(`${API_URL}/v1/telemetry/render`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(milestones),
  }).catch(() => {
    // Telemetry is best-effort — swallow errors silently
  })
}

/**
 * Parsed SSE message with named event type and data payload.
 * RFC §1.8 wire format:
 *   event: <type>\n
 *   data: <json>\n
 *   \n
 */
export interface SSEMessage {
  /** Named SSE event type (status | content | artifact | done | error).
   *  Falls back to "data" for legacy unnamed events. */
  eventType: string
  data: StreamChunk
}

export interface ChatStreamOptions {
  message: string
  sessionId?: string
  userId?: number  // Send existing user_id to backend for reuse
  countryCode?: string  // User's country code for regional affiliate links
  onToken: (token: string, isPlaceholder?: boolean) => void
  onClear?: () => void
  onComplete: (data: Partial<StreamChunk>) => void
  onError: (error: string) => void
  onReconnecting?: (attempt: number, maxRetries: number) => void  // Called when retrying connection
  onReconnected?: () => void  // Called when connection is restored
  /** RFC §1.8: optional callback invoked for every named SSE message before
   *  the legacy handlers run.  Useful for routing by event type without
   *  rewriting all existing call-sites. */
  onEvent?: (msg: SSEMessage) => void
}

/**
 * Stream chat messages using Server-Sent Events (SSE)
 * Includes auto-reconnect with exponential backoff on network errors
 */
export async function streamChat({
  message,
  sessionId,
  userId,
  countryCode,
  onToken,
  onClear,
  onComplete,
  onError,
  onReconnecting,
  onReconnected,
  onEvent,
}: ChatStreamOptions): Promise<void> {
  // RFC §4.1 — Generate a unique interaction ID for this request for end-to-end trace correlation
  const interactionId = crypto.randomUUID()

  // RFC §4.1 — Track render milestones for p95 time-to-first-content calculation.
  // NOTE: request_sent_ts is captured here, before the retry loop.  On retried
  // requests this baseline therefore includes the duration of any prior failed
  // attempts, so TTFC values may appear inflated for retried connections.
  const milestones: RenderMilestones = {
    interaction_id: interactionId,
    request_sent_ts: Date.now(),
    first_status_ts: null,
    first_content_ts: null,
    first_artifact_ts: null,
    done_ts: null,
  }

  let attempt = 0

  while (attempt < MAX_RETRIES) {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

    try {
      const body: { message: string; session_id?: string; user_id?: number; country_code?: string } = { message }
      if (sessionId) {
        body.session_id = sessionId
      }
      if (userId) {
        body.user_id = userId
      }
      if (countryCode) {
        body.country_code = countryCode
      }

      const response = await fetch(`${API_URL}/v1/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Interaction-ID': interactionId,
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      // Notify if we recovered from a failed attempt
      if (attempt > 0 && onReconnected) {
        onReconnected()
      }

      if (!response.ok) {
        // Handle rate limiting with user-friendly message
        if (response.status === 429) {
          const retryAfter = response.headers.get('Retry-After')
          const seconds = retryAfter ? parseInt(retryAfter, 10) : 900
          const minutes = Math.ceil(seconds / 60)
          onError(`Rate limit reached. Please wait ${minutes} minute${minutes > 1 ? 's' : ''} before sending another message.`)
          return
        }
        // Don't retry on other 4xx errors (client errors)
        if (response.status >= 400 && response.status < 500) {
          onError(`Request failed: ${response.status}`)
          return
        }
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      // RFC §1.8: track the current named event type across multi-line SSE messages.
      // Resets to 'data' (legacy unnamed) at each blank-line boundary.
      // NOTE: this declaration is intentionally inside the try block so that it is
      // re-initialised to 'data' on every connection attempt (including retries).
      // A stale event type from a previous failed connection can never bleed into
      // the next attempt.
      let currentEventType = 'data'

      while (true) {
        const { done, value } = await reader.read()

        if (done) {
          break
        }

        // Decode and add to buffer
        buffer += decoder.decode(value, { stream: true })

        // Process complete SSE messages (split on newlines, keep partial last line)
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // Keep incomplete line in buffer

        for (const line of lines) {
          // RFC §1.8: parse the `event:` field to capture the named channel
          if (line.startsWith('event: ')) {
            currentEventType = line.slice(7).trim()
            continue
          }

          // Blank line = end of SSE message; reset event type for next message
          if (line === '') {
            currentEventType = 'data'
            continue
          }

          if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6) // Remove 'data: ' prefix
            try {
              const chunk: StreamChunk = JSON.parse(jsonStr)

              // RFC §1.8: Fire the generic onEvent callback first (if provided)
              if (onEvent) {
                onEvent({ eventType: currentEventType, data: chunk })
              }

              // ── Route by named SSE event type ─────────────────────────────
              if (currentEventType === 'status') {
                // RFC §4.1 — record first status milestone
                if (milestones.first_status_ts === null) {
                  milestones.first_status_ts = Date.now()
                }
                // status event: human-readable progress text
                const statusText = chunk.text || chunk.status_update || ''
                if (statusText) {
                  onToken(statusText, true) // isPlaceholder=true → shown as statusText
                }
                continue
              }

              if (currentEventType === 'content') {
                // RFC §4.1 — record first content milestone
                if (milestones.first_content_ts === null) {
                  milestones.first_content_ts = Date.now()
                }
                // content event: single streaming token
                if (chunk.token) {
                  onToken(chunk.token, false)
                }
                continue
              }

              if (currentEventType === 'artifact') {
                // RFC §4.1 — record first artifact milestone
                if (milestones.first_artifact_ts === null) {
                  milestones.first_artifact_ts = Date.now()
                }
                // artifact event: rich UI blocks or clear signal
                if (chunk.clear && onClear) {
                  onClear()
                }
                if (chunk.blocks || chunk.ui_blocks || chunk.itinerary) {
                  const blocks = chunk.blocks ?? chunk.ui_blocks
                  onComplete({
                    ui_blocks: Array.isArray(blocks) ? blocks : undefined,
                    itinerary: chunk.itinerary,
                    create_new_message: chunk.create_new_message,
                  })
                }
                continue
              }

              // B.3 — the curious follow-up question, emitted after the
              // content stream finishes. Routed through onComplete (no
              // session_id, so the consumer-side branch attaches to the
              // current message without flipping the FSM to finalized).
              if (currentEventType === 'follow_up_question') {
                if (chunk.text) {
                  onComplete({ follow_up_question: chunk.text })
                }
                continue
              }

              // Quiz-path transitional reasoning — routed through onComplete like
              // the follow-up (attaches to the current message without finalizing).
              if (currentEventType === 'transitional_reasoning') {
                if (chunk.text) {
                  onComplete({ transitional_reasoning: chunk.text })
                }
                continue
              }

              if (currentEventType === 'done') {
                // RFC §4.1 — record done milestone and fire-and-forget telemetry POST
                milestones.done_ts = Date.now()
                sendTelemetry(milestones)
                // done event: terminal — workflow completed
                // Guard: only dispatch RECEIVE_DONE when chunk carries a real session_id,
                // preventing artifact onComplete callbacks from triggering the FSM transition.
                if (chunk.session_id) {
                  onComplete({
                    session_id: chunk.session_id,
                    user_id: chunk.user_id,
                    status: chunk.status,
                    intent: chunk.intent,
                    ui_blocks: chunk.ui_blocks,
                    citations: chunk.citations,
                    followups: chunk.followups,
                    next_suggestions: chunk.next_suggestions,
                    completeness: chunk.completeness,
                    request_id: chunk.request_id,
                    response_metadata: chunk.response_metadata,  // RFC §2.5 content trust
                  })
                }
                return
              }

              if (currentEventType === 'error') {
                // error event: terminal — backend signalled a failure
                const errMsg = chunk.message || chunk.error || 'An error occurred'
                onError(errMsg)
                return
              }

              // ── Legacy / unnamed events (eventType === 'data') ───────────
              // Kept for backward-compatibility during the transition period.

              if (chunk.error) {
                onError(chunk.error)
                return
              }

              if (chunk.clear && onClear) {
                onClear()
              }

              // Forward legacy status updates to UI as live typing indicators
              // (e.g., "Searching reviews...", "Comparing prices...")
              if (chunk.status_update) {
                onToken(chunk.status_update, true) // true = isPlaceholder (shows as statusText)
                continue
              }

              if (chunk.token) {
                onToken(chunk.token, chunk.placeholder)
              }

              // Handle intermediate chunks (sent before done=true)
              // This includes itinerary and ui_blocks (product carousel)
              if ((chunk.itinerary || chunk.ui_blocks) && !chunk.done) {
                onComplete({
                  itinerary: chunk.itinerary,
                  ui_blocks: chunk.ui_blocks,  // Include ui_blocks from intermediate chunks
                  create_new_message: chunk.create_new_message,  // Pass the flag to frontend
                })
                // Don't return - continue processing other chunks
              }

              if (chunk.done) {
                // RFC §4.1 — record done milestone and fire-and-forget telemetry POST (legacy path).
                // TODO: remove this branch once legacy unnamed events are no longer emitted.
                milestones.done_ts = Date.now()
                sendTelemetry(milestones)
                onComplete({
                  session_id: chunk.session_id,
                  user_id: chunk.user_id,  // Pass user_id to callback for persistence
                  status: chunk.status,
                  intent: chunk.intent,
                  ui_blocks: chunk.ui_blocks,
                  citations: chunk.citations,
                  followups: chunk.followups,
                  next_suggestions: chunk.next_suggestions,  // Follow-up questions at end of response
                  request_id: chunk.request_id,
                  // Note: itinerary and product carousel are sent in intermediate chunk, not in final chunk
                })
                return
              }
            } catch (e) {
              console.error('Failed to parse SSE data:', e)
            }
          }
        }
      }

      // If we get here, stream completed successfully
      return

    } catch (error) {
      clearTimeout(timeoutId)

      const isNetworkError = error instanceof TypeError ||
        (error instanceof Error && error.name === 'AbortError') ||
        (error instanceof Error && error.message.includes('network'))

      // Only retry on network errors or timeouts
      if (isNetworkError && attempt < MAX_RETRIES - 1) {
        attempt++
        const delay = getBackoffDelay(attempt)
        console.warn(`SSE connection failed, retrying in ${Math.round(delay)}ms (attempt ${attempt}/${MAX_RETRIES})`)
        if (onReconnecting) {
          onReconnecting(attempt, MAX_RETRIES)
        }
        await sleep(delay)
        continue
      }

      // Final attempt failed or non-retryable error
      console.error('Stream error:', error)
      onError(error instanceof Error ? error.message : 'Connection failed. Please try again.')
      return
    }
  }
}

/**
 * Login to the API
 */
export async function login(username: string, password: string): Promise<{ access_token: string }> {
  const response = await fetch(`${API_URL}/v1/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ username, password }),
  })

  if (!response.ok) {
    const data = await response.json()
    throw new Error(data.detail || 'Login failed')
  }

  return response.json()
}

/**
 * Fetch conversation history for a session
 */
export async function fetchConversationHistory(sessionId: string): Promise<any> {
  try {
    const response = await fetch(`${API_URL}/v1/chat/history/${sessionId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return response.json()
  } catch (error) {
    console.error('Failed to fetch conversation history:', error)
    throw error
  }
}

/**
 * Check health of the API
 */
export async function checkHealth(): Promise<any> {
  const response = await fetch(`${API_URL}/health`)
  return response.json()
}
