'use client'

/**
 * ReviewGuide Discover page — SELF-CONTAINED for v0.
 *
 * Faithful copy of the real Discover page with the terracotta palette inlined
 * and sample topics baked in. Renders instantly in v0 — no external imports.
 *
 * HARD CONSTRAINTS (keep these — owner's requirement):
 *   • Keep the WORDMARK/logo ("ReviewGuide.Ai")
 *   • Keep the SEARCH INPUT (the "What are you researching?" bar)
 *   • Keep the warm terracotta-on-cream THEME (palette below)
 * Everything else — the "Popular this week" topic grid especially — is fair game
 * to redesign to look "way better" on BOTH mobile and desktop.
 *
 * Fonts: DM Sans (UI), Newsreader (serif), Instrument Serif (italic display).
 */
import { Search } from 'lucide-react'

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
  textMuted: '#9B9590',
  shadowFloat: '0 12px 32px rgba(26,24,22,0.10)',
  serif: 'Newsreader, ui-serif, Georgia, serif',
  display: '"Instrument Serif", Newsreader, ui-serif, Georgia, serif',
  sans: '"DM Sans", ui-sans-serif, system-ui, sans-serif',
}

type Topic = { slug: string; title: string; hook: string; category: string; image: string }

const TOPICS: Topic[] = [
  { slug: 'macbook-vs-windows', title: 'MacBook vs Windows', hook: 'Settle the debate', category: 'Computing', image: 'https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=600&q=80' },
  { slug: 'tokyo-guide', title: 'Tokyo Travel Guide', hook: 'Neon nights, hidden alleys', category: 'Travel', image: 'https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?w=600&q=80' },
  { slug: 'budget-laptops', title: 'Best Laptops Under $700', hook: 'Real value, no compromises', category: 'Computing', image: 'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=600&q=80' },
  { slug: 'caribbean', title: 'Score Cheap Caribbean Trips', hook: 'Turquoise water, tiny budget', category: 'Travel', image: 'https://images.unsplash.com/photo-1505228395891-9a51e7e86bf6?w=600&q=80' },
  { slug: 'noise-cancelling', title: 'Best Noise-Cancelling Headphones', hook: 'Silence the world, keep the music', category: 'Audio', image: 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&q=80' },
  { slug: 'robot-vacuums', title: 'Robot Vacuums, Ranked', hook: 'Never sweep again', category: 'Smart Home', image: 'https://images.unsplash.com/photo-1558317374-067fb5f30001?w=600&q=80' },
  { slug: 'budget-phones', title: 'Best Cheap Phones', hook: 'Premium feel, friendly price', category: 'Phones', image: 'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&q=80' },
  { slug: 'espresso', title: 'Home Espresso Machines', hook: 'Café shots, kitchen counter', category: 'Kitchen', image: 'https://images.unsplash.com/photo-1510707577719-ae7c14805e3a?w=600&q=80' },
]

const GRADIENT = 'linear-gradient(180deg, rgba(26,24,22,0) 34%, rgba(26,24,22,0.55) 66%, rgba(26,24,22,0.88) 100%)'

/** KEEP — the wordmark/logo. (Real app uses a recolored video; this is the static mark.) */
function Wordmark() {
  return (
    <div style={{ display: 'inline-flex', alignItems: 'baseline', fontFamily: C.sans, fontWeight: 800, fontSize: 30, letterSpacing: '-0.01em' }}>
      <span style={{ color: C.terra }}>Review</span>
      <span style={{ color: C.ink }}>Guide</span>
      <span style={{ color: C.terra }}>.Ai</span>
    </div>
  )
}

/** KEEP — the search input. */
function SearchBar() {
  return (
    <div
      style={{
        display: 'flex', alignItems: 'center', gap: 10, width: '100%', maxWidth: 576,
        background: C.paperHi, border: `1px solid ${C.line}`, borderRadius: 16, padding: '14px 18px', boxShadow: C.shadowFloat,
      }}
    >
      <Search size={18} color={C.ink3} />
      <input
        placeholder="Ask anything — running shoes, robot vacuums, 4K TVs under $500…"
        style={{ flex: 1, border: 'none', outline: 'none', background: 'transparent', fontFamily: C.sans, fontSize: 15, color: C.ink }}
      />
    </div>
  )
}

function TopicCard({ t }: { t: Topic }) {
  return (
    <button
      style={{
        position: 'relative', display: 'block', width: '100%', overflow: 'hidden', borderRadius: 16,
        border: `1px solid ${C.line}`, boxShadow: C.shadowFloat, cursor: 'pointer', padding: 0, textAlign: 'left',
      }}
    >
      <div style={{ position: 'relative', aspectRatio: '4 / 5' }}>
        <img src={t.image} alt={t.title} style={{ width: '100%', height: '100%', objectFit: 'cover', background: C.paperAlt }} />
        <div style={{ position: 'absolute', inset: 0, background: GRADIENT }} />
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, padding: 14 }}>
          <div style={{ textTransform: 'uppercase', fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', color: C.terraSoft, marginBottom: 4 }}>
            {t.category}
          </div>
          <p style={{ fontFamily: C.serif, fontSize: 17, lineHeight: '21px', fontWeight: 600, color: '#fff', margin: 0 }}>{t.title}</p>
          <p style={{ fontSize: 12, lineHeight: '16px', color: 'rgba(255,255,255,0.84)', marginTop: 2 }}>{t.hook}</p>
        </div>
      </div>
    </button>
  )
}

export default function DiscoverPage() {
  return (
    <div style={{ background: C.paper, minHeight: '100vh', fontFamily: C.sans, padding: '0 16px 80px' }}>
      {/* Hero — KEEP wordmark + search */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 48, paddingBottom: 16 }}>
        <Wordmark />
        <h1 style={{ fontFamily: C.display, fontStyle: 'italic', fontSize: 30, lineHeight: '34px', color: C.ink, textAlign: 'center', margin: '20px 0 12px' }}>
          What are you researching?
        </h1>
        <p style={{ fontSize: 14, color: C.ink2, textAlign: 'center', maxWidth: 420, marginBottom: 22 }}>
          A budget, a deadline, a gut feeling — start anywhere.
        </p>
        <SearchBar />
      </div>

      {/* Popular this week — REDESIGN ME. Currently a 2-up (mobile) / 4-up (desktop) poster grid. */}
      <div style={{ maxWidth: 1040, margin: '0 auto' }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: C.ink3, marginBottom: 12 }}>
          Popular this week
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
            gap: 12,
          }}
        >
          {TOPICS.map((t) => (
            <TopicCard key={t.slug} t={t} />
          ))}
        </div>
      </div>
    </div>
  )
}
