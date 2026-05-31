'use client';

// ReviewGuide brand/logo system — faithful React port of frontend/design/lib/logo.jsx.
// Colors come from CSS vars (--terra / --ink / --ink-2 / --ink-3) so light & dark both work.
// (The animated Discover-hero logo now lives in components/DiscoverHeroLogo.tsx.)

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
          style={{ fontSize: 9, fontWeight: 500, letterSpacing: '0.16em', color: 'var(--ink-2)' }}
        >
          Ask before you buy
        </span>
      )}
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
          <span className="font-sans uppercase" style={{ fontSize: 8, fontWeight: 500, letterSpacing: '0.2em', color: 'var(--ink-2)', marginTop: 2 }}>
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
