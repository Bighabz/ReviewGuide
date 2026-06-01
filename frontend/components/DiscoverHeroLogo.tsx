'use client';

// Discover-hero animated logo. Renders the recolored intro animation as an
// animated WebP (not a <video>) — images animate inline on every device with
// no autoplay policy, no tap-to-play button, no muting required. Mobile Safari
// (incl. Low Power Mode) blocked muted-video autoplay and showed a play button,
// so an animated image is the bulletproof fix.
//
// The WebP has a TRANSPARENT background (the white/halo pixels are keyed out via
// ffmpeg lumakey), so the page's paper color shows through exactly — no visible
// rectangle, no blend mode. This replaced an earlier `mix-blend-mode: multiply`
// on a white-background WebP, which rendered inconsistently (mobile Safari showed
// the raw white as a cold box that didn't match the cream page). It's scaled up
// inside an overflow-clipped box to drop the frame's dead margin and match the
// old <LogoHero> footprint.
//
// Respects prefers-reduced-motion: swaps to the static recolored wordmark PNG.

import { useEffect, useState } from 'react';

const STATIC_LOGO = '/images/8f4c1971-a5b0-474e-9fb1-698e76324f0b.png';
const ANIMATED_LOGO = '/images/animated_logo.webp';

export default function DiscoverHeroLogo({ width = 340 }: { width?: number }) {
  const [reducedMotion, setReducedMotion] = useState(false);
  // D1 (perf): the animated WebP is ~2.26MB. SSR + first paint show the 34KB
  // static poster instantly; we preload the heavy WebP and only swap it in once
  // it has decoded, so first contentful paint is never blocked on 2.26MB.
  const [animatedReady, setAnimatedReady] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  // Preload the animated WebP off the critical path, then swap it in.
  useEffect(() => {
    if (reducedMotion || typeof window === 'undefined') return;
    const img = new window.Image();
    img.onload = () => setAnimatedReady(true);
    img.src = ANIMATED_LOGO;
    return () => {
      img.onload = null;
    };
  }, [reducedMotion]);

  // Reduced motion: static recolored wordmark (no animation).
  if (reducedMotion) {
    return (
      <img
        src={STATIC_LOGO}
        alt="ReviewGuide.ai"
        style={{ width: '100%', maxWidth: width - 40, height: 'auto' }}
      />
    );
  }

  // Default (incl. SSR): a fixed-aspect box (no layout shift) showing the static
  // poster until the animated WebP has decoded, then the animation.
  return (
    <div style={{ width: '100%', maxWidth: width, margin: '0 auto' }}>
      <div style={{ position: 'relative', width: '100%', aspectRatio: '16 / 7', overflow: 'hidden' }}>
        {animatedReady ? (
          <img
            src={ANIMATED_LOGO}
            alt="ReviewGuide.ai"
            style={{
              position: 'absolute',
              left: '50%',
              top: '50%',
              width: '150%',
              transform: 'translate(-50%, -50%)',
            }}
          />
        ) : (
          <img
            src={STATIC_LOGO}
            alt="ReviewGuide.ai"
            decoding="async"
            style={{
              position: 'absolute',
              left: '50%',
              top: '50%',
              maxWidth: '92%',
              maxHeight: '82%',
              transform: 'translate(-50%, -50%)',
            }}
          />
        )}
      </div>
    </div>
  );
}
