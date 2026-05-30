// ReviewGuide logo system — full hero bubble + small static wordmark.
// Plus the transitional reasoning bubble (new quiz-path component).

const { color: lc, font: lf } = window.RG;

// ============================================================
// Wordmark — pure type. Reused inside both treatments.
// ============================================================
//
// Structure: "Review" (terracotta) + "Guide" (ink, lighter weight)
// + ".Ai" (terracotta). The handoff specifies sans, with "Guide" in
// a different weight from "Review". DM Sans 700 for Review/.Ai,
// DM Sans 500 for Guide reads as the original "wordmark with a
// quiet middle" rhythm.
//
function Wordmark({ size = 28, color = lc.terra, inkColor = lc.ink }) {
  // approx kerning fudge so ".Ai" sits tight to "Guide"
  return (
    <span style={{
      fontFamily: lf.sans,
      fontSize: size,
      lineHeight: 1,
      letterSpacing: '-0.025em',
      color,
      whiteSpace: 'nowrap',
      display: 'inline-flex',
      alignItems: 'baseline',
    }}>
      <span style={{ fontWeight: 700 }}>Review</span>
      <span style={{ fontWeight: 500, color: inkColor, margin: '0 0.02em' }}>Guide</span>
      <span style={{ fontWeight: 700 }}>.Ai</span>
    </span>
  );
}

// ============================================================
// Small static wordmark — every page that's not Discover.
// ============================================================
//
// Composition: wordmark top-left, tagline beneath at 9pt small-caps
// in muted ink. No bubble. Sized for a header band ~52px tall.
//
function WordmarkStatic({ size = 18, showTagline = true }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'flex-start' }}>
      <Wordmark size={size} />
      {showTagline && (
        <span style={{
          fontFamily: lf.sans,
          fontSize: 9,
          fontWeight: 500,
          letterSpacing: '0.16em',
          textTransform: 'uppercase',
          color: lc.ink3,
        }}>Ask before you buy</span>
      )}
    </div>
  );
}

// ============================================================
// Discover hero — full bubble + rotating word.
// ============================================================
//
// One-time-in-the-product use of the speech-bubble container.
// Tail points down. Inside: the wordmark, then the tagline with
// the final word rotating opacity-crossfade every ~2.4s.
//
function LogoHero({
  rotate = true,
  staticWord = 'Buy',
  width = 340,
}) {
  const words = ['Buy', 'Eat', 'Fly', 'Stay', 'Book', 'Subscribe'];
  const [i, setI] = React.useState(0);
  React.useEffect(() => {
    if (!rotate) return;
    const t = setInterval(() => setI(n => (n + 1) % words.length), 2400);
    return () => clearInterval(t);
  }, [rotate]);
  const word = rotate ? words[i] : staticWord;

  // Hand-tuned bubble dimensions for editorial register.
  const h = Math.round(width * 0.48);
  const r = 28;
  const tailX = width * 0.5; // tail anchored under the wordmark center
  const tailW = 22;
  const tailH = 18;

  return (
    <div style={{ position: 'relative', width, height: h + tailH }}>
      {/* Bubble outline */}
      <svg
        width={width}
        height={h + tailH}
        viewBox={`0 0 ${width} ${h + tailH}`}
        style={{ position: 'absolute', inset: 0 }}
        fill="none"
      >
        <path
          d={[
            `M ${r} 1.25`,
            `H ${width - r}`,
            `A ${r - 1.25} ${r - 1.25} 0 0 1 ${width - 1.25} ${r}`,
            `V ${h - r}`,
            `A ${r - 1.25} ${r - 1.25} 0 0 1 ${width - r} ${h - 1.25}`,
            // tail
            `H ${tailX + tailW / 2}`,
            `L ${tailX} ${h + tailH - 1.25}`,
            `L ${tailX - tailW / 2} ${h - 1.25}`,
            `H ${r}`,
            `A ${r - 1.25} ${r - 1.25} 0 0 1 1.25 ${h - r}`,
            `V ${r}`,
            `A ${r - 1.25} ${r - 1.25} 0 0 1 ${r} 1.25`,
            `Z`,
          ].join(' ')}
          stroke={lc.terra}
          strokeWidth="2.5"
          strokeLinejoin="round"
        />
      </svg>

      {/* Bubble contents */}
      <div style={{
        position: 'absolute', inset: 0, paddingTop: h * 0.18,
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        gap: h * 0.13,
        height: h,
      }}>
        <Wordmark size={Math.round(width * 0.12)} />

        {/* Tagline: "Ask Before You [word]" */}
        <div style={{
          display: 'flex', alignItems: 'baseline', gap: 8,
          fontFamily: lf.sans, fontSize: Math.round(width * 0.052),
          color: lc.ink2, fontWeight: 500, letterSpacing: '-0.005em',
        }}>
          <span>Ask Before You</span>
          {/* Rotating word — italic display, terracotta, crossfade */}
          <span style={{
            position: 'relative', display: 'inline-block',
            minWidth: Math.round(width * 0.26),
          }}>
            <span
              key={word}
              style={{
                position: 'absolute', left: 0, top: 0,
                fontFamily: lf.display, fontStyle: 'italic',
                color: lc.terra,
                fontSize: Math.round(width * 0.072),
                lineHeight: 1,
                letterSpacing: '-0.01em',
                animation: 'rg-word-fade 2.4s ease-in-out',
              }}
            >{word}</span>
            {/* invisible spacer to reserve width */}
            <span style={{
              visibility: 'hidden',
              fontFamily: lf.display, fontStyle: 'italic',
              fontSize: Math.round(width * 0.072),
            }}>Subscribe</span>
          </span>
        </div>
      </div>
    </div>
  );
}

// Keyframes for the rotating word crossfade.
(function injectLogoCSS() {
  if (document.getElementById('rg-logo-css')) return;
  const s = document.createElement('style');
  s.id = 'rg-logo-css';
  s.textContent = `
    @keyframes rg-word-fade {
      0%   { opacity: 0; transform: translateY(4px); }
      14%  { opacity: 1; transform: translateY(0); }
      86%  { opacity: 1; transform: translateY(0); }
      100% { opacity: 0; transform: translateY(-4px); }
    }
  `;
  document.head.appendChild(s);
})();

// ============================================================
// Header — universal small-wordmark band, replaces the old back-only Header
// on pages that want the brand present.
// ============================================================
function HeaderBrand({
  back = true,
  right = null,
  context = null,   // e.g. "Wireless headphones · 4 sources"
}) {
  return (
    <div style={{
      padding: '4px 18px 12px',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      gap: 12,
    }}>
      <div style={{ width: 28, height: 28, display: 'flex', alignItems: 'center' }}>
        {back && (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path d="M15 6l-6 6 6 6" stroke={lc.ink} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        )}
      </div>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0 }}>
        <Wordmark size={15} />
        {context ? (
          <span style={{
            fontFamily: lf.sans, fontSize: 11, color: lc.ink2,
            marginTop: 3, letterSpacing: '0.01em',
          }}>{context}</span>
        ) : (
          <span style={{
            fontFamily: lf.sans, fontSize: 8, fontWeight: 500,
            letterSpacing: '0.20em', textTransform: 'uppercase',
            color: lc.ink3, marginTop: 2,
          }}>Ask before you buy</span>
        )}
      </div>
      <div style={{ width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>{right}</div>
    </div>
  );
}

// ============================================================
// Transitional reasoning bubble — new quiz-path component.
// ============================================================
//
// Distinct from a normal AI bubble: smaller, lighter, italic-leaning,
// no full bubble background — a parenthetical aside the AI says
// between turns. Leading 24px terracotta hairline (same vocabulary
// as the curious follow-up), then italic-display body. Width
// slightly inset from the chat gutter so it reads as a beat, not
// a full response.
//
function TransitionalBubble({ children }) {
  return (
    <div style={{
      maxWidth: 312, marginLeft: 8,
      padding: '4px 0 4px 14px',
      borderLeft: `1px solid ${lc.terra}`,
    }}>
      <div style={{
        fontFamily: lf.display, fontStyle: 'italic',
        fontSize: 17, lineHeight: '24px',
        color: lc.ink, letterSpacing: '-0.005em',
      }}>
        {children}
      </div>
    </div>
  );
}

Object.assign(window, {
  Wordmark, WordmarkStatic, LogoHero, HeaderBrand, TransitionalBubble,
});
