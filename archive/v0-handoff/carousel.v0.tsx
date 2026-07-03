'use client'

/**
 * ReviewGuide product-results carousel — SELF-CONTAINED for v0.
 *
 * This is the in-chat carousel of product review cards (the thing that shows
 * after a product search). It's a faithful copy of the real UI with the
 * terracotta palette inlined and sample data baked in, so it renders instantly
 * in v0 with NO external imports or data wiring.
 *
 * GOAL FOR v0: make this carousel + the review card look "way better" while
 * keeping the warm terracotta-on-cream palette below. Then hand the result back
 * and it gets wired into the real app (real product data, save/affiliate links).
 *
 * Palette (don't drift from these): terracotta #B8543A on cream #FAFAF7, warm
 * near-black ink #1A1816. Fonts: DM Sans (UI), Newsreader (serif body),
 * Instrument Serif (italic display). Falls back gracefully if not loaded.
 */
import { useState } from 'react'
import { ChevronLeft, ChevronRight, Star, Bookmark, ExternalLink } from 'lucide-react'

const C = {
  paper: '#FAFAF7',
  paperHi: '#FFFFFF',
  paperAlt: '#F5F4F0',
  ink: '#1A1816',
  ink2: '#6B6560',
  ink3: '#9B9590',
  line: '#E8E6E1',
  line2: '#D4D1CC',
  terra: '#B8543A',
  terraSoft: '#F4E2D7',
  terraInk: '#7A3624',
  textMuted: '#9B9590',
  shadowFloat: '0 12px 32px rgba(26,24,22,0.10)',
  shadowCard: '0 1px 0 rgba(26,24,22,.04), 0 8px 24px -12px rgba(26,24,22,.10)',
  serif: 'Newsreader, ui-serif, Georgia, serif',
  sans: '"DM Sans", ui-sans-serif, system-ui, sans-serif',
}

type Offer = { merchant: string; title: string; price: string; url: string }
type Product = {
  name: string
  rank: number
  rating: number
  reviewCount: number
  image: string
  summary: string
  pros: string[]
  cons: string[]
  offers: Offer[]
}

const SAMPLE: Product[] = [
  {
    name: 'Anker Soundcore Life P3',
    rank: 1,
    rating: 4.4,
    reviewCount: 38210,
    image: 'https://images.unsplash.com/photo-1606220588913-b3aacb4d2f46?w=400&q=80',
    summary:
      'The pick for most people under $100 — the ANC actually works on a commute, the app gives you real EQ control, and the case pockets easily.',
    pros: ['ANC that holds up on a noisy train', 'Genuinely useful companion app + EQ', 'Small, pocketable case'],
    cons: ['Mic is only okay for calls', 'Touch controls take learning'],
    offers: [
      { merchant: 'Amazon', title: 'Anker Soundcore Life P3', price: '$34.99', url: '#' },
      { merchant: 'eBay (AnkerDirect)', title: 'Soundcore Life P3 — new', price: '$34.99', url: '#' },
    ],
  },
  {
    name: 'JBL Tune 230NC TWS',
    rank: 2,
    rating: 4.3,
    reviewCount: 21044,
    image: 'https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=400&q=80',
    summary:
      'The pick if you want louder, bass-forward sound and care less about noise cancelling — fun and energetic for the gym.',
    pros: ['Punchy, bass-forward tuning', 'Comfortable for long sessions'],
    cons: ['ANC is weaker than the P3', 'Bulkier case'],
    offers: [{ merchant: 'Amazon', title: 'JBL Tune 230NC TWS', price: '$53.95', url: '#' }],
  },
  {
    name: 'Soundcore by Anker Space A40',
    rank: 3,
    rating: 4.5,
    reviewCount: 15890,
    image: 'https://images.unsplash.com/photo-1631867675167-90a456a90863?w=400&q=80',
    summary: 'Step-up ANC and longer battery if you can stretch the budget a little past the others.',
    pros: ['Class-leading ANC for the price', 'Long battery life'],
    cons: ['Costs more than the top pick'],
    offers: [{ merchant: 'Amazon', title: 'Soundcore Space A40', price: '$79.99', url: '#' }],
  },
]

function Eyebrow({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: C.ink3, ...style }}>
      {children}
    </div>
  )
}

function ReviewCard({ p }: { p: Product }) {
  const [saved, setSaved] = useState(false)
  return (
    <div style={{ background: C.paperHi, border: `1px solid ${C.line}`, borderRadius: 20, boxShadow: C.shadowCard, padding: 20 }}>
      <div style={{ display: 'flex', gap: 16 }}>
        <img
          src={p.image}
          alt={p.name}
          style={{ width: 96, height: 96, borderRadius: 14, objectFit: 'cover', background: C.paperAlt, flexShrink: 0 }}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <Eyebrow style={{ color: C.terra }}>{p.rank === 1 ? 'Top pick · for you' : `Pick #${p.rank}`}</Eyebrow>
          <h3 style={{ fontFamily: C.serif, fontSize: 20, lineHeight: '24px', fontWeight: 600, color: C.ink, margin: '4px 0 6px' }}>
            {p.name}
          </h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Star size={14} fill={C.terra} color={C.terra} />
            <span style={{ fontSize: 13, fontWeight: 600, color: C.ink }}>{p.rating.toFixed(1)}</span>
            <span style={{ fontSize: 12, color: C.textMuted }}>({p.reviewCount.toLocaleString()} reviews)</span>
          </div>
        </div>
        <button
          onClick={() => setSaved((s) => !s)}
          aria-label="Save"
          style={{
            width: 40, height: 40, borderRadius: 999, flexShrink: 0,
            background: C.paperHi, border: `1px solid ${C.line}`, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
          }}
        >
          <Bookmark size={15} color={C.terra} fill={saved ? C.terra : 'transparent'} />
        </button>
      </div>

      <p style={{ fontFamily: C.serif, fontSize: 15, lineHeight: '22px', color: C.ink2, margin: '14px 0 0' }}>{p.summary}</p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 14 }}>
        <div>
          <Eyebrow style={{ color: '#3F7A5A' }}>What's good</Eyebrow>
          <ul style={{ margin: '6px 0 0', padding: 0, listStyle: 'none' }}>
            {p.pros.map((t) => (
              <li key={t} style={{ fontSize: 13, lineHeight: '18px', color: C.ink2, marginBottom: 4 }}>+ {t}</li>
            ))}
          </ul>
        </div>
        <div>
          <Eyebrow style={{ color: C.terraInk }}>Worth knowing</Eyebrow>
          <ul style={{ margin: '6px 0 0', padding: 0, listStyle: 'none' }}>
            {p.cons.map((t) => (
              <li key={t} style={{ fontSize: 13, lineHeight: '18px', color: C.ink2, marginBottom: 4 }}>– {t}</li>
            ))}
          </ul>
        </div>
      </div>

      <div style={{ borderTop: `1px solid ${C.line}`, marginTop: 16, paddingTop: 14 }}>
        <Eyebrow>Where to buy</Eyebrow>
        <div style={{ display: 'flex', gap: 10, marginTop: 8, flexWrap: 'wrap' }}>
          {p.offers.map((o) => (
            <a
              key={o.merchant}
              href={o.url}
              style={{
                flex: '1 1 160px', textDecoration: 'none', border: `1px solid ${C.line}`, borderRadius: 12, padding: '10px 12px',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, background: C.paper,
              }}
            >
              <div style={{ minWidth: 0 }}>
                <Eyebrow style={{ fontSize: 10 }}>{o.merchant}</Eyebrow>
                <div style={{ fontSize: 13, fontWeight: 600, color: C.ink, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{o.title}</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: C.ink, marginTop: 2 }}>{o.price}</div>
              </div>
              <ExternalLink size={15} color={C.ink3} />
            </a>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function ProductResultsCarousel() {
  const [current, setCurrent] = useState(0)
  const total = SAMPLE.length
  const go = (i: number) => setCurrent(Math.max(0, Math.min(i, total - 1)))

  return (
    <div style={{ background: C.paper, padding: 24, fontFamily: C.sans, maxWidth: 760, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, padding: '0 4px' }}>
        {current === 0 ? (
          <Eyebrow style={{ color: C.terra }}>✦ Top pick for you</Eyebrow>
        ) : (
          <span style={{ fontSize: 12, fontWeight: 600, color: C.textMuted }}>Pick {current + 1} of {total}</span>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: C.textMuted }}>{current + 1} / {total}</span>
          {[{ d: -1, Ico: ChevronLeft, lbl: 'Previous' }, { d: 1, Ico: ChevronRight, lbl: 'Next' }].map(({ d, Ico, lbl }) => {
            const disabled = d < 0 ? current === 0 : current === total - 1
            return (
              <button
                key={lbl}
                onClick={() => go(current + d)}
                disabled={disabled}
                aria-label={lbl}
                style={{
                  width: 36, height: 36, borderRadius: 999, background: C.paperHi, border: `1px solid ${C.line}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.3 : 1,
                }}
              >
                <Ico size={16} color={C.ink} />
              </button>
            )
          })}
        </div>
      </div>

      {/* Single focused card (swap for your redesigned layout) */}
      <ReviewCard p={SAMPLE[current]} />

      {/* Dots */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: 6, marginTop: 14 }}>
        {SAMPLE.map((_, i) => (
          <button
            key={i}
            onClick={() => go(i)}
            aria-label={`Go to ${i + 1}`}
            style={{ width: i === current ? 22 : 6, height: 6, borderRadius: 999, border: 'none', cursor: 'pointer', background: i === current ? C.terra : C.line2, transition: 'all .3s' }}
          />
        ))}
      </div>
    </div>
  )
}
