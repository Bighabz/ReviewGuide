// Atoms for ReviewGuide screens. Exports to window so other Babel scripts can use them.
// All sizing assumes a 390-wide artboard (iPhone 15).

const { color: rgC, font: rgF, radius: rgR, shadow: rgS } = window.RG;

// ---------- Phone shell ----------
function Phone({ children, label, height = 844, white = false }) {
  return (
    <div
      className="rg-frame"
      style={{
        width: 390,
        height,
        background: white ? rgC.paperHi : rgC.paper,
        position: 'relative',
        overflow: 'hidden',
        fontFamily: rgF.sans,
        color: rgC.ink,
      }}
    >
      <StatusBar />
      {children}
    </div>
  );
}

function StatusBar() {
  return (
    <div
      style={{
        height: 48, padding: '14px 24px 0', display: 'flex',
        alignItems: 'center', justifyContent: 'space-between',
        fontFamily: rgF.sans, fontSize: 14, fontWeight: 600, color: rgC.ink,
        position: 'relative', zIndex: 5,
      }}
    >
      <span style={{ letterSpacing: '-0.01em' }}>9:41</span>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        {/* signal */}
        <svg width="18" height="11" viewBox="0 0 18 11"><g fill={rgC.ink}>
          <rect x="0"  y="7" width="3" height="4"  rx=".5"/>
          <rect x="5"  y="5" width="3" height="6"  rx=".5"/>
          <rect x="10" y="3" width="3" height="8"  rx=".5"/>
          <rect x="15" y="0" width="3" height="11" rx=".5"/>
        </g></svg>
        {/* wifi */}
        <svg width="16" height="11" viewBox="0 0 16 11" fill="none">
          <path d="M8 9.5a1 1 0 100-2 1 1 0 000 2z" fill={rgC.ink}/>
          <path d="M4.5 6.5C5.5 5.5 6.7 5 8 5s2.5.5 3.5 1.5M2 4c1.5-1.5 3.7-2.5 6-2.5S12.5 2.5 14 4"
            stroke={rgC.ink} strokeWidth="1.4" strokeLinecap="round"/>
        </svg>
        {/* battery */}
        <svg width="26" height="12" viewBox="0 0 26 12">
          <rect x=".5" y=".5" width="22" height="11" rx="3" fill="none" stroke={rgC.ink} strokeOpacity=".4"/>
          <rect x="2"  y="2"  width="18" height="8"  rx="1.5" fill={rgC.ink}/>
          <rect x="23.5" y="3.5" width="1.5" height="5" rx=".5" fill={rgC.ink} fillOpacity=".4"/>
        </svg>
      </div>
    </div>
  );
}

// ---------- Bottom tab bar ----------
const tabIcon = {
  discover: (
    <path d="M3 11 L12 4 L21 11 V20 a1 1 0 0 1 -1 1 H4 a1 1 0 0 1 -1 -1 Z" fill="none" strokeWidth="1.4"/>
  ),
  saved: (
    <path d="M6 3 H18 V21 L12 17 L6 21 Z" fill="none" strokeWidth="1.4"/>
  ),
  ask: (
    <g fill="none" strokeWidth="1.4">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v8M8 12h8" />
    </g>
  ),
  compare: (
    <g fill="none" strokeWidth="1.4">
      <rect x="3" y="5" width="8" height="14" rx="1.5"/>
      <rect x="13" y="5" width="8" height="14" rx="1.5"/>
    </g>
  ),
  profile: (
    <g fill="none" strokeWidth="1.4">
      <circle cx="12" cy="9" r="3.5"/>
      <path d="M5 20c1.5-3.5 4.2-5 7-5s5.5 1.5 7 5"/>
    </g>
  ),
};

function TabBar({ active = 'discover' }) {
  const items = [
    { id: 'discover', label: 'Discover' },
    { id: 'saved',    label: 'Saved' },
    { id: 'ask',      label: 'Ask',      primary: true },
    { id: 'compare',  label: 'Compare' },
    { id: 'profile',  label: 'You' },
  ];
  return (
    <div style={{
      position: 'absolute', left: 0, right: 0, bottom: 0,
      paddingBottom: 22, paddingTop: 10, background: rgC.paper,
      borderTop: `1px solid ${rgC.line}`,
      display: 'grid', gridTemplateColumns: 'repeat(5,1fr)',
    }}>
      {items.map(it => {
        const isActive = it.id === active;
        const stroke = it.primary ? rgC.paper : (isActive ? rgC.ink : rgC.ink3);
        return (
          <div key={it.id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
            <div style={{
              width: it.primary ? 44 : 28, height: it.primary ? 44 : 28,
              background: it.primary ? rgC.ink : 'transparent',
              borderRadius: it.primary ? 999 : 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <svg width={it.primary ? 22 : 22} height={it.primary ? 22 : 22} viewBox="0 0 24 24" stroke={stroke}>
                {tabIcon[it.id]}
              </svg>
            </div>
            <span style={{
              fontFamily: rgF.sans, fontSize: 10, letterSpacing: '0.04em',
              color: isActive ? rgC.ink : rgC.ink3, fontWeight: isActive ? 600 : 500,
              marginTop: it.primary ? -2 : 0,
            }}>{it.label}</span>
          </div>
        );
      })}
    </div>
  );
}

// ---------- Suggestion chip (tap-to-reply, §13 #4) ----------
function Chip({ children, accent = false, full = false, leadingDot = false, style = {} }) {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 8,
      padding: '10px 14px',
      width: full ? '100%' : 'auto',
      maxWidth: '100%',
      fontFamily: rgF.sans, fontSize: 14, lineHeight: '20px', fontWeight: 500,
      color: accent ? rgC.terraInk : rgC.ink,
      background: accent ? rgC.terraSoft : rgC.paperHi,
      border: `1px solid ${accent ? rgC.terra : rgC.line2}`,
      borderRadius: 12, // rounded-rect, not capsule — looks less like multi-select
      cursor: 'pointer',
      textAlign: 'left',
      whiteSpace: 'normal',
      ...style,
    }}>
      {leadingDot && <span style={{
        width: 4, height: 4, borderRadius: 999, background: rgC.terra, flex: '0 0 auto',
      }} />}
      <span style={{ flex: '0 1 auto' }}>{children}</span>
    </div>
  );
}

// ---------- Bubble: AI / user / blog / loading ----------
function AIBubble({ children, style = {} }) {
  return (
    <div style={{
      maxWidth: 312, padding: '14px 16px',
      background: rgC.paperHi,
      border: `1px solid ${rgC.line}`,
      borderRadius: '14px 14px 14px 4px',
      fontFamily: rgF.sans, fontSize: 15, lineHeight: '22px', color: rgC.ink,
      ...style,
    }}>
      {children}
    </div>
  );
}

function UserBubble({ children }) {
  return (
    <div style={{
      maxWidth: 280, marginLeft: 'auto',
      padding: '12px 16px',
      background: rgC.ink, color: rgC.paper,
      borderRadius: '14px 14px 4px 14px',
      fontFamily: rgF.sans, fontSize: 15, lineHeight: '22px',
    }}>
      {children}
    </div>
  );
}

// The curious follow-up line — §13 #3.
function FollowUpQ({ children }) {
  return (
    <div style={{ marginTop: 14 }}>
      <div className="rg-hairline-short" style={{ marginBottom: 10 }} />
      <p style={{
        margin: 0,
        fontFamily: rgF.display, fontStyle: 'italic', fontSize: 19, lineHeight: '26px',
        color: rgC.ink, fontWeight: 400, letterSpacing: '-0.005em',
      }}>
        {children}
      </p>
    </div>
  );
}

// Loading bubble — §13 #1. Single breathing dot beside rotating copy.
function LoadingBubble({ text = 'Seeing what others are saying…' }) {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 12,
      padding: '14px 18px',
      background: rgC.paperHi,
      border: `1px solid ${rgC.line}`,
      borderRadius: '14px 14px 14px 4px',
    }}>
      <span className="rg-breath" style={{
        width: 8, height: 8, borderRadius: 999, background: rgC.terra,
        display: 'inline-block',
      }}/>
      <span style={{
        fontFamily: rgF.display, fontStyle: 'italic', fontSize: 18, lineHeight: '24px',
        color: rgC.ink2, letterSpacing: '-0.005em',
      }}>{text}</span>
    </div>
  );
}

// ---------- Inline product link (§13 #2) ----------
function ProductLink({ children }) {
  return (
    <span style={{
      color: rgC.ink, fontWeight: 500,
      textDecorationLine: 'underline',
      textDecorationStyle: 'dotted',
      textDecorationThickness: '1px',
      textDecorationColor: rgC.terra,
      textUnderlineOffset: '4px',
      cursor: 'pointer',
    }}>
      {children}
    </span>
  );
}

// ---------- Bookmark / save toggle (§13 #9) ----------
function Bookmark({ filled = false, size = 22, ring = false }) {
  return (
    <span style={{ position: 'relative', width: size + 16, height: size + 16, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
      {ring && (
        <span style={{
          position: 'absolute', inset: 4, borderRadius: 999,
          border: `1px solid ${rgC.terra}`, opacity: .4,
          transform: 'scale(1.4)',
        }}/>
      )}
      <svg width={size} height={size} viewBox="0 0 24 24" fill={filled ? rgC.terra : 'none'} stroke={filled ? rgC.terra : rgC.ink}>
        <path d="M6 3 H18 V21 L12 17 L6 21 Z" strokeWidth="1.4" strokeLinejoin="round"/>
      </svg>
    </span>
  );
}

// ---------- Sticky composer ----------
function Composer({ placeholder = 'Reply with anything', disabled = false }) {
  return (
    <div style={{
      position: 'absolute', left: 0, right: 0, bottom: 0,
      padding: '14px 18px 22px',
      background: `linear-gradient(to top, ${rgC.paper} 65%, rgba(250,247,242,0))`,
      pointerEvents: 'none',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '10px 10px 10px 16px',
        background: rgC.paperHi,
        border: `1px solid ${rgC.line2}`,
        borderRadius: 28,
        boxShadow: rgS.card,
        pointerEvents: 'auto',
      }}>
        <span style={{
          fontFamily: rgF.sans, fontSize: 15, lineHeight: '22px',
          color: disabled ? rgC.ink3 : rgC.ink3, flex: 1,
        }}>{placeholder}</span>
        <button style={{
          width: 36, height: 36, borderRadius: 999, border: 'none',
          background: rgC.ink, display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', padding: 0,
        }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M5 12h14M13 6l6 6-6 6" stroke={rgC.paper} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </div>
    </div>
  );
}

// ---------- Carousel card (§13 #7) ----------
function ProductCard({
  role = 'Top pick',
  roleAccent = true,
  name = 'Bose QuietComfort Ultra',
  brand = 'Bose',
  price = '$429',
  img,           // bg color or null
  saved = false,
  width = 240,
  compact = false,
}) {
  const tone = img || '#D4C9B7';
  return (
    <div style={{
      width, flex: `0 0 ${width}px`,
      background: rgC.paperHi,
      border: `1px solid ${rgC.line}`,
      borderRadius: 16,
      overflow: 'hidden',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* image */}
      <div style={{
        position: 'relative', height: width * 0.75,
        background: tone,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <PlaceholderProduct tint={tone} />
        <div style={{ position: 'absolute', top: 8, right: 8 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 999,
            background: 'rgba(255,253,248,.9)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Bookmark filled={saved} size={16} />
          </div>
        </div>
      </div>
      <div style={{ padding: '12px 14px 14px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{
          fontFamily: rgF.sans, fontSize: 10, fontWeight: 600,
          letterSpacing: '0.10em', textTransform: 'uppercase',
          color: roleAccent ? rgC.terra : rgC.ink2,
        }}>{role}</div>
        <div style={{
          fontFamily: rgF.serif, fontSize: 17, lineHeight: '22px', color: rgC.ink,
          fontWeight: 500, letterSpacing: '-0.01em',
        }}>{name}</div>
        {!compact && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 2 }}>
            <span style={{ fontFamily: rgF.sans, fontSize: 12, color: rgC.ink3 }}>{brand}</span>
            <span style={{ fontFamily: rgF.sans, fontSize: 14, color: rgC.ink, fontWeight: 500 }}>{price}</span>
          </div>
        )}
      </div>
    </div>
  );
}

// Subtle striped placeholder — never hand-draw products.
function PlaceholderProduct({ tint = '#D4C9B7' }) {
  return (
    <svg width="100%" height="100%" viewBox="0 0 100 75" preserveAspectRatio="xMidYMid slice" style={{ position: 'absolute', inset: 0 }}>
      <defs>
        <pattern id={'stripe-' + tint.replace('#','')} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="6" height="6" fill={tint}/>
          <line x1="0" y1="0" x2="0" y2="6" stroke="rgba(255,255,255,.16)" strokeWidth="1"/>
        </pattern>
      </defs>
      <rect width="100" height="75" fill={`url(#stripe-${tint.replace('#','')})`}/>
      <text x="50" y="40" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="3.2" fill="rgba(26,24,22,.45)" letterSpacing="0.08em">PRODUCT IMG</text>
    </svg>
  );
}

// ---------- Section eyebrow ----------
function Eyebrow({ children, action }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
      <span className="rg-eyebrow">{children}</span>
      {action && <span style={{ fontFamily: rgF.sans, fontSize: 12, color: rgC.ink2 }}>{action}</span>}
    </div>
  );
}

// ---------- Header (back arrow + title) ----------
function Header({ title, right = null, back = true }) {
  return (
    <div style={{
      padding: '6px 18px 14px',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      gap: 12,
    }}>
      <div style={{ width: 28, height: 28, display: 'flex', alignItems: 'center' }}>
        {back && (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path d="M15 6l-6 6 6 6" stroke={rgC.ink} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        )}
      </div>
      <div style={{
        flex: 1, textAlign: 'center', fontFamily: rgF.sans, fontSize: 14, fontWeight: 500,
        color: rgC.ink2, letterSpacing: '0.02em',
      }}>{title}</div>
      <div style={{ width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>{right}</div>
    </div>
  );
}

// ---------- Annotation pill (used in canvas to mark which §13 Q each screen addresses) ----------
function Annotation({ children, kind = 'note' }) {
  const accent = kind === 'decision' ? rgC.terra : rgC.ink2;
  return (
    <div style={{
      padding: '6px 10px',
      background: 'rgba(255,253,248,.95)',
      border: `1px solid ${rgC.line}`,
      borderLeft: `2px solid ${accent}`,
      borderRadius: 4,
      fontFamily: rgF.mono, fontSize: 10, lineHeight: '14px',
      color: rgC.ink2,
    }}>{children}</div>
  );
}

Object.assign(window, {
  Phone, StatusBar, TabBar,
  Chip, AIBubble, UserBubble, FollowUpQ, LoadingBubble,
  ProductLink, Bookmark, Composer, ProductCard, PlaceholderProduct,
  Eyebrow, Header, Annotation,
});
