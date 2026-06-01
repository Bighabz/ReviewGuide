'use client'

// B-phase 3: cache the user's interest keywords (top categories / brands /
// use-cases) returned in the chat 'done' event, so the chat empty-state starter
// can bias toward what they research — even across sessions / after recent
// searches rotate out. localStorage-backed, SSR-guarded.

const KEY = 'rg_pref_summary'

/** Persist the interest keywords from a chat 'done' event (ignores empties). */
export function cachePreferenceSummary(summary: unknown): void {
  if (!Array.isArray(summary)) return
  const clean = summary.filter((s): s is string => typeof s === 'string' && s.trim().length > 0).slice(0, 6)
  if (clean.length === 0) return
  try {
    localStorage.setItem(KEY, JSON.stringify(clean))
  } catch {
    /* localStorage unavailable */
  }
}

/** Read the cached interest keywords (empty array if none / unavailable). */
export function getPreferenceSummary(): string[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((s) => typeof s === 'string') : []
  } catch {
    return []
  }
}
