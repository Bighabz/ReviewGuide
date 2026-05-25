'use client'

import { useRotatingLoadingCopy } from '@/lib/loadingCopy'

/**
 * The single span of text shown inside a loading bubble or status pill.
 * Wraps `useRotatingLoadingCopy` in a component so the timer effects only
 * mount when this is actually rendered (i.e., loading is active),
 * avoiding stray intervals running while a message isn't in a thinking state.
 *
 * Consumed by Message.tsx (chat AI bubble loading state) and
 * MobileHeader.tsx (top-bar status pill).
 */
export default function LoadingStatusText({
  statusText,
  className,
  intervalMs,
}: {
  statusText?: string | null
  className?: string
  /** Per-instance override; defaults to 4000ms inside the hook. */
  intervalMs?: number
}) {
  const text = useRotatingLoadingCopy(statusText, intervalMs)
  return <span className={className}>{text}</span>
}
