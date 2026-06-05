'use client'

import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ProductReviewCarouselProps {
  children: React.ReactNode[]
}

/**
 * "Deck of cards" product rail (design from v0). The top pick sits on top; the
 * next picks fan out behind it with depth, and decorative card edges below
 * reinforce the stack. Wraps the real <ProductReview> children, so all product
 * data, save, and affiliate wiring is unchanged — only the carousel chrome is
 * new. Header pill + nav arrows + dots advance; non-active cards are `inert`
 * (not focusable/clickable) so the deck behind can't be mis-tapped.
 */
export default function ProductReviewCarousel({ children }: ProductReviewCarouselProps) {
  const [current, setCurrent] = useState(0)
  const total = children.length
  const go = (i: number) => setCurrent(Math.max(0, Math.min(i, total - 1)))

  if (total <= 1) return <div>{children}</div>

  return (
    <div
      role="group"
      aria-roledescription="carousel"
      aria-label="Recommended products"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'ArrowRight') { e.preventDefault(); go(current + 1) }
        if (e.key === 'ArrowLeft') { e.preventDefault(); go(current - 1) }
      }}
      className="font-sans"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4 px-1">
        {current === 0 ? (
          <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--terra-soft)] text-[var(--terra)] text-xs font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--terra)] animate-pulse" />
            Top pick for you
          </span>
        ) : (
          <span className="text-sm font-medium text-[var(--ink-3)]">Pick {current + 1} of {total}</span>
        )}
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-[var(--ink-3)] tabular-nums mr-1">{current + 1}/{total}</span>
          <button
            onClick={() => go(current - 1)}
            disabled={current === 0}
            aria-label="Previous product"
            className="w-8 h-8 rounded-full bg-[var(--paper-hi)] ring-1 ring-[var(--line)] flex items-center justify-center transition-all hover:ring-[var(--terra)]/50 hover:bg-[var(--terra-soft)]/30 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:ring-[var(--line)] disabled:hover:bg-[var(--paper-hi)]"
          >
            <ChevronLeft size={16} className="text-[var(--ink)]" />
          </button>
          <button
            onClick={() => go(current + 1)}
            disabled={current === total - 1}
            aria-label="Next product"
            className="w-8 h-8 rounded-full bg-[var(--paper-hi)] ring-1 ring-[var(--line)] flex items-center justify-center transition-all hover:ring-[var(--terra)]/50 hover:bg-[var(--terra-soft)]/30 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:ring-[var(--line)] disabled:hover:bg-[var(--paper-hi)]"
          >
            <ChevronRight size={16} className="text-[var(--ink)]" />
          </button>
        </div>
      </div>

      {/* Stacked deck */}
      <div className="relative">
        <div className="relative">
          {children.map((child, index) => {
            const offset = index - current
            const isActive = offset === 0
            const isBehind = offset > 0
            const isHidden = offset < 0 || offset > 2
            return (
              <div
                key={index}
                ref={(el) => { if (el) (el as any).inert = !isActive }}
                className={cn(
                  'transition-all duration-500 ease-out',
                  isActive ? 'relative z-30' : 'absolute inset-x-0 top-0',
                  isBehind && offset === 1 && 'z-20',
                  isBehind && offset === 2 && 'z-10',
                  isHidden && 'opacity-0 pointer-events-none',
                )}
                style={{
                  transform: isBehind
                    ? `translateY(${offset * 12}px) scale(${1 - offset * 0.04})`
                    : offset < 0
                      ? 'translateX(-110%)'
                      : undefined,
                  opacity: isBehind ? 1 - offset * 0.25 : offset < 0 ? 0 : 1,
                }}
              >
                {child}
              </div>
            )
          })}
        </div>

        {/* Decorative stacked-edge shadows for depth */}
        {current < total - 1 && (
          <>
            <div className="absolute -bottom-2 left-3 right-3 h-4 bg-[var(--paper-hi)] rounded-b-2xl ring-1 ring-[var(--line)] -z-10 opacity-60" style={{ transform: 'translateY(8px)' }} />
            {current < total - 2 && (
              <div className="absolute -bottom-2 left-6 right-6 h-4 bg-[var(--paper-hi)] rounded-b-2xl ring-1 ring-[var(--line)] -z-20 opacity-30" style={{ transform: 'translateY(16px)' }} />
            )}
          </>
        )}
      </div>

      {/* Dots */}
      <div className="flex justify-center items-center gap-1.5 mt-8">
        {children.map((_, i) => (
          <button
            key={i}
            onClick={() => go(i)}
            aria-label={`Go to pick ${i + 1}`}
            aria-current={i === current}
            className={cn(
              'h-1.5 rounded-full transition-all duration-300',
              i === current ? 'w-6 bg-[var(--terra)]' : 'w-1.5 bg-[var(--line-2)] hover:bg-[var(--terra)]/40',
            )}
          />
        ))}
      </div>
    </div>
  )
}
