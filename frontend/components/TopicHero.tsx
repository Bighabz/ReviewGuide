'use client'

import { useState, useEffect } from 'react'
import { hasGeneratedHero } from '@/lib/generatedHeroes'

/**
 * Dreambeans-inspired topic hero.
 *
 * Dreambeans gives every "story" a unique, context-matched AI illustration.
 * The analog here: prefer an AI-generated, palette-matched hero illustration at
 * `public/images/topics/hero/<slug>.webp` when one exists, and gracefully fall
 * back to the stock category image, then to the gradient alone — so the page
 * never breaks while the generated library is still being filled in.
 *
 * Generated assets are produced OFFLINE via the nano-banana pipeline
 * (`scripts/gen-topic-heroes.mjs`), which needs a Gemini key with image-gen
 * quota. Until those assets land, this renders identically to the old inline
 * hero (it falls straight through to `fallbackImage`).
 */
export default function TopicHero({
  slug,
  title,
  category,
  hook,
  fallbackImage,
}: {
  slug: string
  title: string
  category: string
  hook: string
  fallbackImage: string
}) {
  const generated = `/images/topics/hero/${slug}.webp`
  // Only point at the generated asset when we actually have one (manifest in
  // lib/generatedHeroes). Otherwise start at the stock image so we don't fire a
  // guaranteed 404 + broken-image flash on every topic view. onError still
  // degrades generated → stock → gradient if a listed asset is missing.
  const initialSrc = hasGeneratedHero(slug) ? generated : fallbackImage
  const [src, setSrc] = useState(initialSrc)

  // Next reuses this component instance when navigating between /topic/[slug]
  // pages (e.g. via "More to explore"), so without this the hero keeps the
  // previous topic's image while the title/hook update. Reset on slug change.
  useEffect(() => { setSrc(initialSrc) }, [initialSrc])

  return (
    <div
      className="relative h-60 sm:h-80 mx-4 sm:mx-6 md:mx-8 mt-4 rounded-2xl overflow-hidden"
      style={{ boxShadow: 'var(--shadow-float)' }}
    >
      <img
        src={src}
        alt={title}
        className="w-full h-full object-cover"
        style={{ background: 'var(--paper-alt)' }}
        onError={(e) => {
          // generated asset missing → drop to stock image → drop to gradient
          if (src !== fallbackImage) setSrc(fallbackImage)
          else (e.currentTarget as HTMLImageElement).style.display = 'none'
        }}
      />
      <div
        className="absolute inset-0"
        aria-hidden="true"
        style={{ background: 'linear-gradient(180deg, rgba(26,24,22,0) 28%, rgba(26,24,22,0.55) 62%, rgba(26,24,22,0.88) 100%)' }}
      />
      <div className="absolute bottom-0 left-0 right-0 p-6 sm:p-8">
        <div className="uppercase mb-2" style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--terra-soft)' }}>
          {category}
        </div>
        <h1 className="rg-display tracking-tight text-white" style={{ fontSize: 34, lineHeight: '38px' }}>
          {title}
        </h1>
        <p className="text-sm sm:text-base text-white/80 mt-2 max-w-md">{hook}</p>
      </div>
    </div>
  )
}
