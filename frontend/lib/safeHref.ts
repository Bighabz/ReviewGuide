/**
 * URL-scheme guard for links whose target comes from LLM output or third-party
 * provider data (affiliate links, "Where to buy" URLs, citations, hotel/flight
 * search URLs, merchant links). A poisoned provider record or an injected
 * model response could otherwise smuggle a `javascript:` / `data:` / `vbscript:`
 * URI into an href and execute script in our origin on click.
 *
 * Returns the URL only if it parses as http(s); otherwise returns a safe
 * fallback (`#` by default) so the link renders inert instead of dangerous.
 *
 * Relative URLs and site-internal paths (`/foo`, `#anchor`) are allowed — they
 * can't carry a dangerous scheme.
 */
export function safeHref(url: string | null | undefined, fallback = '#'): string {
  if (!url) return fallback
  const trimmed = String(url).trim()
  if (!trimmed) return fallback

  // Allow site-relative links — no scheme, so no scheme-based attack surface.
  if (trimmed.startsWith('/') || trimmed.startsWith('#') || trimmed.startsWith('?')) {
    return trimmed
  }

  try {
    // Resolve against the current origin so protocol-relative and relative
    // URLs normalize; then hard-gate on the resulting protocol.
    const base = typeof window !== 'undefined' ? window.location.origin : 'https://www.reviewguide.ai'
    const parsed = new URL(trimmed, base)
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return parsed.href
    }
  } catch {
    // Unparseable → treat as unsafe.
  }
  return fallback
}
