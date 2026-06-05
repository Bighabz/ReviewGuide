'use client'

import { useRef, useState, useCallback, useEffect } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface ProductReviewCarouselProps {
  children: React.ReactNode[]
}

export default function ProductReviewCarousel({ children }: ProductReviewCarouselProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [current, setCurrent] = useState(0)
  const [touchStart, setTouchStart] = useState<number | null>(null)
  const total = children.length

  const scrollToIndex = useCallback((idx: number) => {
    const container = scrollRef.current
    if (!container) return
    const card = container.children[idx] as HTMLElement
    if (!card) return
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' })
    setCurrent(idx)
  }, [])

  const next = useCallback(() => {
    scrollToIndex(Math.min(current + 1, total - 1))
  }, [current, total, scrollToIndex])

  const prev = useCallback(() => {
    scrollToIndex(Math.max(current - 1, 0))
  }, [current, scrollToIndex])

  // Touch swipe handling
  const handleTouchStart = (e: React.TouchEvent) => {
    setTouchStart(e.touches[0].clientX)
  }

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStart === null) return
    const diff = touchStart - e.changedTouches[0].clientX
    if (Math.abs(diff) > 50) {
      diff > 0 ? next() : prev()
    }
    setTouchStart(null)
  }

  // Update current index on scroll (for snap alignment)
  useEffect(() => {
    const container = scrollRef.current
    if (!container) return
    const handleScroll = () => {
      const scrollLeft = container.scrollLeft
      const cardWidth = container.children[0]?.clientWidth || 1
      const idx = Math.round(scrollLeft / cardWidth)
      setCurrent(Math.min(idx, total - 1))
    }
    container.addEventListener('scrollend', handleScroll)
    return () => container.removeEventListener('scrollend', handleScroll)
  }, [total])

  if (total <= 1) {
    return <div>{children}</div>
  }

  return (
    <div className="relative">
      {/* Counter badge */}
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-xs font-medium text-[var(--text-muted)]">
          {current + 1} of {total} products
        </span>
        {/* Desktop arrows */}
        <div className="hidden sm:flex gap-1">
          <button
            onClick={prev}
            disabled={current === 0}
            className="w-7 h-7 rounded-full flex items-center justify-center transition-colors disabled:opacity-30"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
            aria-label="Previous product"
          >
            <ChevronLeft size={14} />
          </button>
          <button
            onClick={next}
            disabled={current === total - 1}
            className="w-7 h-7 rounded-full flex items-center justify-center transition-colors disabled:opacity-30"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
            aria-label="Next product"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {/* Swipeable card container */}
      <div
        ref={scrollRef}
        className="flex gap-4 overflow-x-auto snap-x snap-mandatory scrollbar-hide"
        style={{ scrollBehavior: 'smooth' }}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        {children.map((child, idx) => (
          <div
            key={idx}
            className="snap-start flex-shrink-0 w-full"
          >
            {child}
          </div>
        ))}
      </div>

      {/* Dot indicators */}
      <div className="flex justify-center gap-1.5 mt-3">
        {children.map((_, i) => (
          <button
            key={i}
            onClick={() => scrollToIndex(i)}
            className="transition-all duration-300 rounded-full"
            style={{
              width: i === current ? '20px' : '6px',
              height: '6px',
              background: i === current ? 'var(--primary)' : 'var(--border-strong, #D4D1CC)',
            }}
            aria-label={`Go to product ${i + 1}`}
          />
        ))}
      </div>

      {/* Swipe hint on mobile (first visit only) */}
      <p className="text-center text-[10px] text-[var(--text-muted)] mt-1 sm:hidden">
        Swipe to browse products
      </p>
    </div>
  )
}
