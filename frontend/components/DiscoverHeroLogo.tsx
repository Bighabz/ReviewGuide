'use client';

// Discover-hero animated logo. Plays the recolored intro video (terracotta
// wordmark on white) once on open, then settles on its final logo frame.
// The source MP4 has a white background (no alpha — H.264), so we use
// `mix-blend-mode: multiply` to melt that white into the cream Discover
// background while keeping the terracotta logo. The video frame has ~20% dead
// whitespace around the logo, so we scale it up and clip with overflow-hidden
// to land the logo at roughly the same footprint as the old <LogoHero>.
//
// Mobile autoplay: browsers only allow muted autoplay, and they evaluate the
// `muted` state at mount — but React sets the `muted` *property* a tick late,
// so the browser sees an unmuted video and shows a tap-to-play button. We fix
// that by setting muted synchronously in a ref callback (before the autoplay
// decision), retrying play() on canplay/loadedmetadata, and — as a last resort
// for iOS Low Power Mode — kicking playback on the first scroll/tap.
//
// Respects prefers-reduced-motion: falls back to the static recolored wordmark
// PNG instead of autoplaying.

import { useCallback, useEffect, useRef, useState } from 'react';

const STATIC_LOGO = '/images/8f4c1971-a5b0-474e-9fb1-698e76324f0b.png';
const VIDEO_SRC = '/images/animated_logo.mp4';

export default function DiscoverHeroLogo({ width = 340 }: { width?: number }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [reduced, setReduced] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Set muted synchronously at mount so the browser's own autoplay attempt
  // (mobile requires muted) sees it *before* deciding — React's `muted` prop
  // is applied too late on its own.
  const setVideoRef = useCallback((el: HTMLVideoElement | null) => {
    videoRef.current = el;
    if (el) {
      el.muted = true;
      el.defaultMuted = true;
      el.setAttribute('muted', '');
      el.setAttribute('playsinline', '');
      el.setAttribute('webkit-playsinline', '');
    }
  }, []);

  useEffect(() => {
    setMounted(true);
    if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
      setReduced(window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    }
  }, []);

  useEffect(() => {
    const v = videoRef.current;
    if (!v || reduced) return;
    v.muted = true;

    const tryPlay = () => {
      try {
        // play() can throw synchronously (jsdom) or reject (autoplay blocked).
        const p = v.play();
        if (p && typeof p.catch === 'function') p.catch(() => {});
      } catch {
        /* no-op */
      }
    };

    tryPlay();
    v.addEventListener('loadedmetadata', tryPlay);
    v.addEventListener('canplay', tryPlay);

    // Last-resort fallback (e.g. iOS Low Power Mode blocks even muted autoplay):
    // start playback on the first user interaction, then detach.
    const onGesture = () => {
      tryPlay();
      detachGestures();
    };
    const detachGestures = () => {
      document.removeEventListener('touchstart', onGesture);
      document.removeEventListener('pointerdown', onGesture);
      document.removeEventListener('scroll', onGesture);
    };
    document.addEventListener('touchstart', onGesture, { passive: true });
    document.addEventListener('pointerdown', onGesture, { passive: true });
    document.addEventListener('scroll', onGesture, { passive: true });

    return () => {
      v.removeEventListener('loadedmetadata', tryPlay);
      v.removeEventListener('canplay', tryPlay);
      detachGestures();
    };
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
          ref={setVideoRef}
          autoPlay
          muted
          playsInline
          preload="auto"
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
