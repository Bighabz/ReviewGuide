import { safeHref } from './safeHref'

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
  // Fire tracking request (non-blocking)
  fetch(`${API_URL}/v1/affiliate/click`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  }).catch(() => {
    // Silently ignore tracking failures — don't block navigation
  })

  // Open affiliate link in new tab — scheme-guarded so a poisoned provider URL
  // can't execute `javascript:`/`data:` in our origin.
  const target = safeHref(params.url, '')
  if (target) window.open(target, '_blank', 'noopener,noreferrer')
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
