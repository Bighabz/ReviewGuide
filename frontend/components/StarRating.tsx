import { Star } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * StarRating — blueprint-palette star row (terracotta fill, warm-neutral empty).
 *
 * Single-accent system: filled stars are terra, empty stars are the line-2
 * border neutral. No yellow/amber/gray Tailwind palette colors (spec §11.6).
 */

interface StarRatingProps {
    value: number
    max?: number
    size?: number
    className?: string
    showCount?: boolean
    count?: number
}

export function StarRating({
    value,
    max = 5,
    size = 16,
    className,
    showCount = false,
    count
}: StarRatingProps) {
    const clamped = Math.min(Math.max(value, 0), max)
    const fullStars = Math.floor(clamped)
    const hasHalfStar = clamped % 1 >= 0.5
    const emptyStars = max - fullStars - (hasHalfStar ? 1 : 0)

    return (
        <div
            className={cn("flex items-center gap-1", className)}
            role="img"
            aria-label={`Rated ${clamped} out of ${max}`}
        >
            <div className="flex" style={{ color: 'var(--terra)' }}>
                {[...Array(fullStars)].map((_, i) => (
                    <Star key={`full-${i}`} size={size} fill="currentColor" strokeWidth={0} />
                ))}
                {hasHalfStar && (
                    <div className="relative">
                        <Star size={size} fill="none" stroke="var(--line-2)" strokeWidth={1.5} />
                        <div className="absolute top-0 left-0 overflow-hidden w-1/2">
                            <Star size={size} fill="currentColor" strokeWidth={0} />
                        </div>
                    </div>
                )}
                {[...Array(emptyStars)].map((_, i) => (
                    <Star key={`empty-${i}`} size={size} fill="none" stroke="var(--line-2)" strokeWidth={1.5} />
                ))}
            </div>

            {showCount && (
                <span className="text-xs font-medium ml-1" style={{ color: 'var(--ink-2)' }}>
                    {clamped.toFixed(1)} {count !== undefined && `(${count})`}
                </span>
            )}
        </div>
    )
}
