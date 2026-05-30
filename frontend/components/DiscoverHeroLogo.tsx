'use client';

// Discover-hero animated logo. Plays the recolored intro video (terracotta
// wordmark on white) once on open, then settles on its final logo frame.
// The source MP4 has a white background (no alpha — H.264), so we use
// `mix-blend-mode: multiply` to melt that white into the cream Discover
// background while keeping the terracotta logo. The video frame has ~20% dead
// whitespace around the logo, so we scale it up and clip with overflow-hidden
// to land the logo at roughly the same footprint as the old <LogoHero>.
//
// Respects prefers-reduced-motion: falls back to the static recolored wordmark
// PNG instead of autoplaying.

import { useEffect, useRef, useState } from 'react';

const STATIC_LOGO = '/images/8f4c1971-a5b0-474e-9fb1-698e76324f0b.png';
const VIDEO_SRC = '/images/animated_logo.mp4';

export default function DiscoverHeroLogo({ width = 360 }: { width?: number }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [reduced, setReduced] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
      setReduced(window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    }
  }, []);

  useEffect(() => {
    const v = videoRef.current;
    if (!v || reduced) return;
    // Ensure muted (React attr can be unreliable) then autoplay from the start.
    v.muted = true;
    try {
      v.currentTime = 0;
      // play() can throw synchronously (jsdom has no media impl) or reject
      // (autoplay blocked) — swallow both; the first frame still shows the logo.
      const p = v.play();
      if (p && typeof p.catch === 'function') p.catch(() => {});
    } catch {
      /* no-op */
    }
  }, [reduced, mounted]);

  // Reduced-motion or pre-hydration: static recolored wordmark.
  if (!mounted || reduced) {
    return (
      <img
        src={STATIC_LOGO}
        alt="ReviewGuide.ai"
        style={{ width: '100%', maxWidth: width - 40, height: 'auto' }}
      />
    );
  }

  return (
    <div style={{ width: '100%', maxWidth: width, margin: '0 auto' }}>
      <div style={{ position: 'relative', width: '100%', aspectRatio: '16 / 7', overflow: 'hidden' }}>
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          aria-label="ReviewGuide.ai"
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            width: '150%',
            transform: 'translate(-50%, -50%)',
            mixBlendMode: 'multiply',
          }}
        >
          <source src={VIDEO_SRC} type="video/mp4" />
        </video>
      </div>
    </div>
  );
}
