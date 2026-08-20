import { CHAT_CONFIG } from './constants'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface TrackClickParams {
  provider: string
  product_name?: string
  category?: string
  url: string
  session_id?: string
}

/**
 * Fire-and-forget POST to track an affiliate click, then open the URL.
 */
export function trackAffiliateClick(params: TrackClickParams) {
  // T3 (2026-08-19): attach the current chat session so backend rows carry
  // their originating session_id instead of NULL. Read lazily — the session
  // id is created on the first /chat visit, not at module load.
  const session_id =
    params.session_id ??
    (typeof window !== 'undefined'
      ? localStorage.getItem(CHAT_CONFIG.SESSION_STORAGE_KEY) ?? undefined
      : undefined)

  // Fire tracking request (non-blocking)
  fetch(`${API_URL}/v1/affiliate/click`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...params, session_id }),
  }).catch(() => {
    // Silently ignore tracking failures — don't block navigation
  })

  // Open affiliate link in new tab
  window.open(params.url, '_blank', 'noopener,noreferrer')
}

// RFC §2.4 — General-purpose event tracker for non-affiliate interactions
type TrackableEvent = 'suggestion_click' | 'affiliate_click' | 'view'

interface TrackEventPayload {
  [key: string]: unknown
}

/**
 * Fire-and-forget POST to track a named UI event (e.g., suggestion_click).
 * Does not open any URL — pure telemetry.
 */
export function trackAffiliate(event: TrackableEvent, payload: TrackEventPayload): void {
  fetch(`${API_URL}/v1/affiliate/event`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event, payload }),
  }).catch(() => {
    // Silently ignore tracking failures — telemetry is best-effort
  })
}
