'use client'

import { useRouter } from 'next/navigation'
import { ShoppingCart } from 'lucide-react'
import { HeaderBrand } from '@/components/Brand'
import { useSavedItems, type SavedItem } from '@/lib/savedItems'

function HeaderCard({ item }: { item: SavedItem }) {
  return (
    <div className="rounded-[14px] overflow-hidden" style={{ background: 'var(--paper-hi)', border: '1px solid var(--line)' }}>
      <div className="w-full flex items-center justify-center" style={{ height: 120, background: 'var(--paper-alt)' }}>
        {item.imageUrl ? (
          <img src={item.imageUrl} alt={item.name} className="w-full h-full object-contain p-3" />
        ) : (
          <ShoppingCart size={22} style={{ color: 'var(--ink-3)' }} />
        )}
      </div>
      <div className="px-3 py-3 flex flex-col gap-1">
        <p className="rg-serif line-clamp-2" style={{ fontSize: 15, lineHeight: '20px', fontWeight: 500, color: 'var(--ink)' }}>
          {item.name}
        </p>
        {item.price != null && item.price > 0 && <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink)' }}>${item.price}</span>}
      </div>
    </div>
  )
}

export default function ComparePage() {
  const router = useRouter()
  const { items, compare } = useSavedItems()
  const selected = compare.map((id) => items.find((i) => i.id === id)).filter(Boolean) as SavedItem[]

  if (selected.length < 2) {
    return (
      <div className="mx-auto w-full max-w-xl px-5 pb-28 pt-2">
        <HeaderBrand back onBack={() => router.push('/saved')} context="Comparing two" />
        <div className="flex flex-col items-center justify-center text-center gap-4 mt-24">
          <h1 className="rg-display" style={{ fontSize: 30, lineHeight: '34px', color: 'var(--ink)' }}>
            Pick two to compare.
          </h1>
          <p className="rg-serif" style={{ fontSize: 16, lineHeight: '24px', color: 'var(--ink-2)', maxWidth: 320 }}>
            Head to Saved and tap two cards — they&apos;ll stack up side by side here.
          </p>
          <button
            onClick={() => router.push('/saved')}
            className="rounded-pill px-5 py-2.5 text-[14px] font-medium mt-1"
            style={{ background: 'var(--ink)', color: 'var(--paper)' }}
          >
            Go to Saved
          </button>
        </div>
      </div>
    )
  }

  const [a, b] = selected
  // Real-data verdict: frame the price tradeoff (no fabricated specs).
  const priceA = a.price ?? null
  const priceB = b.price ?? null
  const cheaper = priceA != null && priceB != null ? (priceA <= priceB ? a : b) : null
  const pricier = cheaper ? (cheaper === a ? b : a) : null
  const gap = priceA != null && priceB != null ? Math.abs(priceA - priceB) : null

  const verdict =
    cheaper && pricier && gap != null
      ? gap === 0
        ? `Same price — so it comes down to which one fits your situation better.`
        : `The ${cheaper.name} saves you $${gap}. The ${pricier.name} is the splurge — worth it only if its edge matters to you.`
      : `Two solid picks. Open each to see how they stack up on the things you care about.`

  return (
    <div className="mx-auto w-full max-w-xl px-5 pb-28 pt-2">
      <HeaderBrand back onBack={() => router.push('/saved')} context="Comparing two" />

      {/* Header cards */}
      <div className="grid grid-cols-2 gap-3.5 mt-2">
        <HeaderCard item={a} />
        <HeaderCard item={b} />
      </div>

      {/* The verdict for you */}
      <div className="rounded-[14px] px-4 py-4 mt-5" style={{ background: 'var(--terra-soft)' }}>
        <div className="rg-eyebrow" style={{ color: 'var(--terra-ink)' }}>The verdict for you</div>
        <p className="rg-serif mt-2" style={{ fontSize: 17, lineHeight: '24px', fontWeight: 500, color: 'var(--ink)' }}>
          {verdict}
        </p>
      </div>

      {/* What matters for you — Price is real; deeper rows come from a full analysis */}
      <div className="mt-7">
        <div className="rg-eyebrow mb-3">What matters for you</div>

        {/* Price row */}
        <div className="mb-4">
          <div className="rg-eyebrow mb-2" style={{ color: 'var(--ink-3)' }}>Price</div>
          <div className="grid grid-cols-2 gap-3.5">
            {[a, b].map((item) => {
              const isWinner = cheaper?.id === item.id
              return (
                <div key={item.id} className="flex items-start gap-2">
                  <span
                    className="mt-1.5 w-1 h-1 rounded-full flex-shrink-0"
                    style={{ background: isWinner ? 'var(--terra)' : 'transparent' }}
                  />
                  <span className="rg-serif" style={{ fontSize: 14, lineHeight: '20px', color: 'var(--ink)' }}>
                    {item.price != null ? `$${item.price}` : '—'}
                    {isWinner && <span style={{ color: 'var(--ink-2)' }}> · easier on the wallet</span>}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        <p className="text-[12px] italic" style={{ color: 'var(--ink-3)' }}>
          Deeper spec-by-spec comparison comes from a full analysis — ask in chat to generate it.
        </p>
      </div>

      {/* Dual CTA */}
      <div className="flex items-stretch gap-3 mt-7">
        <a
          href={a.url || '#'}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 flex items-center justify-center rounded-pill py-2.5 text-[14px] font-medium"
          style={{ border: '1px solid var(--line-2)', color: 'var(--ink)' }}
        >
          Buy {a.name.split(' ').slice(0, 2).join(' ')}
        </a>
        <a
          href={b.url || '#'}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center rounded-pill py-2.5 px-5 text-[14px] font-medium"
          style={{ background: 'var(--ink)', color: 'var(--paper)', flexGrow: 1.6 }}
        >
          Go with {b.name.split(' ').slice(0, 2).join(' ')} →
        </a>
      </div>
    </div>
  )
}
