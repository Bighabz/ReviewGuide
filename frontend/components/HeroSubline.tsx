'use client'

import { useState, useEffect } from 'react'

// Rotating hero subline — a fresh editorial line each visit. Voice = warm,
// "ask before you buy", a little playful. Add/edit lines here freely.
export const HERO_SUBLINES = [
  'Start messy — I’ll help you narrow it down.',
  'Name a thing, a budget, a worry. I’ll take it from there.',
  'Headphones, a hotel, a hard call — anything goes.',
  'Tell me what you’re weighing up.',
  'A budget, a deadline, a gut feeling — start anywhere.',
  'What are you trying to get right?',
  'No wrong way in. Just say what’s on your mind.',
] as const

/**
 * Renders one subline, chosen at random on mount.
 * SSR renders index 0 (stable → no hydration mismatch); the client swaps to a
 * random line in useEffect, so it "changes every time" without a flash mismatch.
 */
export default function HeroSubline({
  className,
  style,
}: {
  className?: string
  style?: React.CSSProperties
}) {
  const [line, setLine] = useState<string>(HERO_SUBLINES[0])
  useEffect(() => {
    setLine(HERO_SUBLINES[Math.floor(Math.random() * HERO_SUBLINES.length)])
  }, [])
  return (
    <p className={className} style={style}>
      {line}
    </p>
  )
}
