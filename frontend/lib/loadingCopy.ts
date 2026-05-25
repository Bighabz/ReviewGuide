/**
 * Rotating loading-bubble copy per tone.md §"Loading state vocabulary"
 * and reviewguide-spec.md §10.1.
 *
 * The backend emits one on-voice string per tool via TOOL_CONTRACT.citation_message
 * (see backend/mcp_server/tools/*.py). When a single tool runs for more than ~4s
 * the server-side string stops feeling alive, so the hook below rotates through
 * the §10.1 vocabulary while the same serverText is sticky. As soon as the
 * server emits a new statusText, the rotation resets — the new server string
 * takes precedence again for another {@link intervalMs}, then cedes back to
 * the rotation if it stays static.
 */

import { useEffect, useState, useRef } from 'react'

/**
 * The full §10.1 vocabulary. Ambiguous, curious, no competitor sites.
 * Order matches the tone.md list. Frontend rotates linearly — random
 * shuffling would feel skittish and is not on-voice.
 */
export const LOADING_COPY: readonly string[] = [
  'Searching the web…',
  'Looking through partner reviews…',
  'Digging for answers…',
  'Seeing what others are saying…',
  'Comparing the contenders…',
  'Reading the room…',
  'Weighing the tradeoffs…',
  'Pulling the receipts…',
  'Sorting the contenders…',
  'Cross-checking the specs…',
  'Hunting for the catch…',
  'Asking around…',
] as const

/**
 * Hook that returns the current loading-bubble copy.
 *
 * Behavior:
 *   1. When {@link serverText} is present and recently changed, returns it
 *      verbatim — the backend's per-tool seed line gets {@link intervalMs}
 *      of solo screen-time.
 *   2. After {@link intervalMs} of the SAME serverText with no change,
 *      switches to cycling through {@link LOADING_COPY} (the §10.1
 *      vocabulary) one phrase per intervalMs.
 *   3. As soon as serverText changes (new tool fires), resets to step 1
 *      with the new text.
 *   4. If serverText is null/empty from the start, immediately starts
 *      cycling LOADING_COPY (no Thinking... fallback).
 *
 * Replaces the literal 'Thinking...' fallback at Message.tsx:184–191 and
 * MobileHeader.tsx:59–64 (RECONCILIATION.md ⚠ #8).
 *
 * @param serverText Latest statusText from the SSE status event.
 * @param intervalMs How long a phrase stays on screen. Default 4000ms.
 * @returns The current copy to render. Never empty.
 */
export function useRotatingLoadingCopy(
  serverText?: string | null,
  intervalMs = 4000,
): string {
  const [rotationIdx, setRotationIdx] = useState(0)
  const [showRotation, setShowRotation] = useState(() => !serverText || !serverText.trim())
  const lastServerTextRef = useRef<string | null | undefined>(serverText)

  // Detect serverText change → snap back to "show server text" for one cycle.
  useEffect(() => {
    if (serverText !== lastServerTextRef.current) {
      lastServerTextRef.current = serverText
      setRotationIdx(0)
      // If the new server text is present, show it solo for intervalMs first.
      // If it's empty/null, kick directly into rotation.
      setShowRotation(!serverText || !serverText.trim())
    }
  }, [serverText])

  // While showing server text: after intervalMs hand off to rotation.
  useEffect(() => {
    if (showRotation) return
    const handoff = window.setTimeout(() => setShowRotation(true), intervalMs)
    return () => window.clearTimeout(handoff)
  }, [showRotation, intervalMs, serverText])

  // Once in rotation: advance one phrase per intervalMs.
  useEffect(() => {
    if (!showRotation) return
    const tick = window.setInterval(() => {
      setRotationIdx(idx => (idx + 1) % LOADING_COPY.length)
    }, intervalMs)
    return () => window.clearInterval(tick)
  }, [showRotation, intervalMs])

  if (!showRotation && serverText && serverText.trim().length > 0) {
    return serverText
  }
  return LOADING_COPY[rotationIdx]
}
