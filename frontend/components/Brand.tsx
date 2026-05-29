'use client';

// ReviewGuide brand/logo system — faithful React port of frontend/design/lib/logo.jsx.
// Colors come from CSS vars (--terra / --ink / --ink-2 / --ink-3) so light & dark both work.
// The rotating-word hero uses the CSS @keyframes `rg-word-fade` (defined in globals.css)
// and advances the word in JS at `animationend` — per DESIGN.md §7 (NOT setInterval), so
// iOS low-power mode pauses the cycle correctly.

import { useEffect, useState } from 'react';

// ── prefers-reduced-motion hook ────────────────────────────────
function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    // Guard: jsdom / older environments may not implement matchMedia.
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);
  return reduced;
}

// ============================================================
// Wordmark — pure type. "Review"(700 terra) + "Guide"(500 ink) + ".Ai"(700 terra)
// ============================================================
export function Wordmark({ size = 28, className = '' }: { size?: number; className?: string }) {
  return (
    <span
      className={`font-sans whitespace-nowrap inline-flex items-baseline ${className}`}
      style={{ fontSize: size, lineHeight: 1, letterSpacing: '-0.025em' }}
    >
      <span style={{ fontWeight: 700, color: 'var(--terra)' }}>Review</span>
      <span style={{ fontWeight: 500, color: 'var(--ink)', margin: '0 0.02em' }}>Guide</span>
      <span style={{ fontWeight: 700, color: 'var(--terra)' }}>.Ai</span>
    </span>
  );
}

// ============================================================
// Static wordmark — every non-Discover surface. Tagline drops at the smallest size.
// ============================================================
export function WordmarkStatic({ size = 18, showTagline = true }: { size?: number; showTagline?: boolean }) {
  const tagline = showTagline && size > 14;
  return (
    <div className="flex flex-col items-start gap-0.5">
      <Wordmark size={size} />
      {tagline && (
        <span
          className="font-sans uppercase"
          style={{ fontSize: 9, fontWeight: 500, letterSpacing: '0.16em', color: 'var(--ink-3)' }}
        >
          Ask before you buy
        </span>
      )}
    </div>
  );
}

// ============================================================
// Discover hero — speech bubble + rotating word. Single occurrence in the product.
// ============================================================
const HERO_WORDS = ['Buy', 'Eat', 'Fly', 'Stay', 'Book', 'Subscribe'];

export function LogoHero({ width = 340, rotate = true }: { width?: number; rotate?: boolean }) {
  const reduced = usePrefersReducedMotion();
  const [i, setI] = useState(0);
  const animate = rotate && !reduced;
  const word = animate ? HERO_WORDS[i] : 'Buy';

  // Bubble geometry (matches blueprint proportions)
  const h = Math.round(width * 0.48);
  const r = 28;
  const tailX = width * 0.5;
  const tailW = 22;
  const tailH = 18;

  const bubblePath = [
    `M ${r} 1.25`,
    `H ${width - r}`,
    `A ${r - 1.25} ${r - 1.25} 0 0 1 ${width - 1.25} ${r}`,
    `V ${h - r}`,
    `A ${r - 1.25} ${r - 1.25} 0 0 1 ${width - r} ${h - 1.25}`,
    `H ${tailX + tailW / 2}`,
    `L ${tailX} ${h + tailH - 1.25}`,
    `L ${tailX - tailW / 2} ${h - 1.25}`,
    `H ${r}`,
    `A ${r - 1.25} ${r - 1.25} 0 0 1 1.25 ${h - r}`,
    `V ${r}`,
    `A ${r - 1.25} ${r - 1.25} 0 0 1 ${r} 1.25`,
    `Z`,
  ].join(' ');

  return (
    <div style={{ position: 'relative', width, height: h + tailH }}>
      <svg width={width} height={h + tailH} viewBox={`0 0 ${width} ${h + tailH}`} style={{ position: 'absolute', inset: 0 }} fill="none">
        <path d={bubblePath} stroke="var(--terra)" strokeWidth="2.5" strokeLinejoin="round" />
      </svg>

      <div
        style={{ position: 'absolute', inset: 0, paddingTop: h * 0.18, height: h }}
        className="flex flex-col items-center"
      >
        <Wordmark size={Math.round(width * 0.12)} />
        <div
          className="flex items-baseline font-sans"
          style={{ marginTop: h * 0.13, gap: 8, fontSize: Math.round(width * 0.052), color: 'var(--ink-2)', fontWeight: 500, letterSpacing: '-0.005em' }}
        >
          <span>Ask Before You</span>
          <span style={{ position: 'relative', display: 'inline-block', minWidth: Math.round(width * 0.26) }}>
            <span
              key={word}
              onAnimationEnd={animate ? () => setI((n) => (n + 1) % HERO_WORDS.length) : undefined}
              className={animate ? 'rg-word-fade' : ''}
              style={{
                position: 'absolute', left: 0, top: 0,
                fontFamily: 'var(--font-instrument), Georgia, serif', fontStyle: 'italic',
                color: 'var(--terra)', fontSize: Math.round(width * 0.072), lineHeight: 1, letterSpacing: '-0.01em',
              }}
            >
              {word}
            </span>
            {/* invisible spacer reserves width of the longest word so the line never reflows */}
            <span
              aria-hidden
              style={{ visibility: 'hidden', fontFamily: 'var(--font-instrument), Georgia, serif', fontStyle: 'italic', fontSize: Math.round(width * 0.072) }}
            >
              Subscribe
            </span>
          </span>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// HeaderBrand — universal band: [back] [centered wordmark + context] [right slot]
// ============================================================
export function HeaderBrand({
  back = true,
  onBack,
  right = null,
  context = null,
}: {
  back?: boolean;
  onBack?: () => void;
  right?: React.ReactNode;
  context?: string | null;
}) {
  return (
    <div className="flex items-center justify-between gap-3" style={{ padding: '4px 18px 12px' }}>
      <div className="flex items-center" style={{ width: 28, height: 28 }}>
        {back && (
          <button onClick={onBack} aria-label="Back" className="flex items-center justify-center w-full h-full">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path d="M15 6l-6 6 6 6" stroke="var(--ink)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        )}
      </div>
      <div className="flex-1 flex flex-col items-center">
        <Wordmark size={15} />
        {context ? (
          <span className="font-sans" style={{ fontSize: 11, color: 'var(--ink-2)', marginTop: 3, letterSpacing: '0.01em' }}>
            {context}
          </span>
        ) : (
          <span className="font-sans uppercase" style={{ fontSize: 8, fontWeight: 500, letterSpacing: '0.2em', color: 'var(--ink-3)', marginTop: 2 }}>
            Ask before you buy
          </span>
        )}
      </div>
      <div className="flex items-center justify-end" style={{ width: 28, height: 28 }}>
        {right}
      </div>
    </div>
  );
}

// ============================================================
// TransitionalBubble — quiz-path reasoning aside. No bg, terra left border only.
// ============================================================
export function TransitionalBubble({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="rg-blog-in"
      style={{ maxWidth: 312, marginLeft: 8, padding: '4px 0 4px 14px', borderLeft: '1px solid var(--terra)' }}
    >
      <div
        style={{ fontFamily: 'var(--font-instrument), Georgia, serif', fontStyle: 'italic', fontSize: 17, lineHeight: '24px', color: 'var(--ink)', letterSpacing: '-0.005em' }}
      >
        {children}
      </div>
    </div>
  );
}
