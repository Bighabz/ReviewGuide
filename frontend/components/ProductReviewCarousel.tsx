'use client'

import { useRef, useState, useCallback, useEffect } from 'react'
import { ArrowRight, ArrowLeft } from 'lucide-react'

interface ProductReviewCarouselProps {
  children: React.ReactNode[]
}

/**
 * Highlight + peek product rail. The top pick (index 0) sits as a prominent
 * focused card; the next card peeks at the right edge to signal "there's more,"
 * and a terracotta arrow (plus tapping the peek itself, swipe, dots, and ←/→
 * keys) advances. Terracotta tokens only.
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

  return (
    <div
      className="relative"
      role="group"
      aria-roledescription="carousel"
      aria-label="Recommended products"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'ArrowRight') { e.preventDefault(); next() }
        if (e.key === 'ArrowLeft') { e.preventDefault(); prev() }
      }}
    >
      {/* Header — top-pick badge on the first card, position elsewhere */}
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
        <span className="hidden sm:block text-xs font-medium text-[var(--text-muted)]">
          {current + 1} / {total}
        </span>
      </div>

      {/* Rail — focused card centered, next card peeking at the edge */}
      <div className="relative">
        <div
          ref={scrollRef}
          className="flex gap-4 overflow-x-auto snap-x snap-mandatory scrollbar-hide pb-1"
          style={{ scrollBehavior: 'smooth', scrollPaddingInline: '0px' }}
          onTouchStart={handleTouchStart}
          onTouchEnd={handleTouchEnd}
        >
          {children.map((child, idx) => {
            const isActive = idx === current
            return (
              <div
                key={idx}
                onClick={() => { if (!isActive) scrollToIndex(idx) }}
                className="snap-center flex-shrink-0 w-[86%] sm:w-[82%] lg:w-[74%] transition-all duration-300"
                style={{
                  opacity: isActive ? 1 : 0.55,
                  transform: isActive ? 'scale(1)' : 'scale(0.965)',
                  cursor: isActive ? 'default' : 'pointer',
                  filter: isActive ? 'none' : 'saturate(0.92)',
                }}
                aria-hidden={!isActive}
              >
                {child}
              </div>
            )
          })}
        </div>

        {/* Advance arrow — terracotta FAB at the right peek edge */}
        {!atEnd && (
          <button
            onClick={next}
            aria-label="Next product"
            className="absolute right-1 top-[120px] -translate-y-1/2 z-10 w-11 h-11 rounded-full flex items-center justify-center transition-all hover:scale-105 active:scale-95"
            style={{ background: 'var(--terra)', color: '#fff', boxShadow: 'var(--shadow-float)' }}
          >
            <ArrowRight size={18} strokeWidth={2.2} />
          </button>
        )}
        {/* Back arrow — quiet, only past the first card */}
        {!atStart && (
          <button
            onClick={prev}
            aria-label="Previous product"
            className="absolute left-1 top-[120px] -translate-y-1/2 z-10 w-10 h-10 rounded-full flex items-center justify-center transition-all hover:scale-105 active:scale-95"
            style={{ background: 'var(--paper-hi)', color: 'var(--ink)', border: '1px solid var(--line)', boxShadow: 'var(--shadow-soft, 0 2px 8px rgba(0,0,0,0.08))' }}
          >
            <ArrowLeft size={16} strokeWidth={2.2} />
          </button>
        )}
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
