'use client'

import { useRef, useState, useCallback, useEffect } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface ProductReviewCarouselProps {
  children: React.ReactNode[]
}

/**
 * Product review rail. The top pick (index 0) leads; a "Top pick for you" badge
 * marks it. On phones each card is FULL WIDTH (these cards are dense — image,
 * pros/cons, buy links — so cramping them for a peek hurts readability). From
 * lg up, the focused card narrows so the next card peeks, signalling "more."
 * Controls live in the header (never over the card); swipe, dots, and ←/→ keys
 * also advance. No dim/scale on the cards (they stay fully readable + tappable).
 * Terracotta tokens only.
 */
export default function ProductReviewCarousel({ children }: ProductReviewCarouselProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [current, setCurrent] = useState(0)
  const [touchStart, setTouchStart] = useState<number | null>(null)
  const total = children.length

  const scrollToIndex = useCallback((idx: number) => {
    const container = scrollRef.current
    if (!container) return
    const clamped = Math.max(0, Math.min(idx, total - 1))
    const card = container.children[clamped] as HTMLElement
    if (!card) return
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
    setCurrent(clamped)
  }, [total])

  const next = useCallback(() => scrollToIndex(current + 1), [current, scrollToIndex])
  const prev = useCallback(() => scrollToIndex(current - 1), [current, scrollToIndex])

  const handleTouchStart = (e: React.TouchEvent) => setTouchStart(e.touches[0].clientX)
  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStart === null) return
    const diff = touchStart - e.changedTouches[0].clientX
    if (Math.abs(diff) > 50) (diff > 0 ? next() : prev())
    setTouchStart(null)
  }

  // Keep `current` in sync with manual scroll/swipe (snap settle).
  useEffect(() => {
    const container = scrollRef.current
    if (!container) return
    const onScrollEnd = () => {
      const center = container.scrollLeft + container.clientWidth / 2
      let best = 0, bestDist = Infinity
      Array.from(container.children).forEach((c, i) => {
        const el = c as HTMLElement
        const mid = el.offsetLeft + el.clientWidth / 2
        const d = Math.abs(mid - center)
        if (d < bestDist) { bestDist = d; best = i }
      })
      setCurrent(best)
    }
    container.addEventListener('scrollend', onScrollEnd)
    return () => container.removeEventListener('scrollend', onScrollEnd)
  }, [total])

  if (total <= 1) return <div>{children}</div>

  const atStart = current === 0
  const atEnd = current === total - 1

  const ArrowBtn = ({
    onClick, disabled, label, children: ico,
  }: { onClick: () => void; disabled: boolean; label: string; children: React.ReactNode }) => (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className="w-9 h-9 rounded-full flex items-center justify-center transition-all hover:scale-105 active:scale-95 disabled:opacity-30 disabled:hover:scale-100"
      style={{ background: 'var(--paper-hi)', border: '1px solid var(--line)', color: 'var(--ink)' }}
    >
      {ico}
    </button>
  )

  return (
    <div
      role="group"
      aria-roledescription="carousel"
      aria-label="Recommended products"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'ArrowRight') { e.preventDefault(); next() }
        if (e.key === 'ArrowLeft') { e.preventDefault(); prev() }
      }}
    >
      {/* Header — badge + count on the left, controls on the right (never over the card) */}
      <div className="flex items-center justify-between mb-2.5 px-1">
        {atStart ? (
          <span className="inline-flex items-center gap-1.5 rg-eyebrow" style={{ color: 'var(--terra)' }}>
            <span aria-hidden="true" style={{ fontSize: 12 }}>✦</span> Top pick for you
          </span>
        ) : (
          <span className="text-xs font-medium text-[var(--text-muted)]">
            Pick {current + 1} of {total}
          </span>
        )}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-[var(--text-muted)] tabular-nums">{current + 1} / {total}</span>
          <ArrowBtn onClick={prev} disabled={atStart} label="Previous product"><ChevronLeft size={16} strokeWidth={2.2} /></ArrowBtn>
          <ArrowBtn onClick={next} disabled={atEnd} label="Next product"><ChevronRight size={16} strokeWidth={2.2} /></ArrowBtn>
        </div>
      </div>

      {/* Rail — full-width cards on mobile; from lg the focus card narrows so the next peeks */}
      <div
        ref={scrollRef}
        className="flex gap-4 overflow-x-auto snap-x snap-mandatory scrollbar-hide pb-1"
        style={{ scrollBehavior: 'smooth' }}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        {children.map((child, idx) => (
          <div key={idx} className="snap-center flex-shrink-0 w-full lg:w-[74%]">
            {child}
          </div>
        ))}
      </div>

      {/* Dots — elongated terracotta active pill */}
      <div className="flex justify-center items-center gap-1.5 mt-3">
        {children.map((_, i) => (
          <button
            key={i}
            onClick={() => scrollToIndex(i)}
            className="transition-all duration-300 rounded-full"
            style={{
              width: i === current ? '22px' : '6px',
              height: '6px',
              background: i === current ? 'var(--terra)' : 'var(--line-2, #D4D1CC)',
            }}
            aria-label={`Go to product ${i + 1}`}
            aria-current={i === current}
          />
        ))}
      </div>
    </div>
  )
}
