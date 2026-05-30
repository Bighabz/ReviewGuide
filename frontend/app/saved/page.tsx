'use client'

import { useRouter } from 'next/navigation'
import { Bookmark, Check, ShoppingCart } from 'lucide-react'
import { HeaderBrand } from '@/components/Brand'
import { useSavedItems, toggleCompare, removeSaved } from '@/lib/savedItems'

export default function SavedPage() {
  const router = useRouter()
  const { items, compare } = useSavedItems()

  if (items.length === 0) {
    return (
      <div className="mx-auto w-full max-w-xl px-5 pb-28 pt-2">
        <HeaderBrand back={false} context="Things you bookmarked" />
        <div className="flex flex-col items-center justify-center text-center gap-4 mt-24">
          <Bookmark size={40} strokeWidth={1.5} style={{ color: 'var(--ink-3)' }} />
          <h1 className="rg-display" style={{ fontSize: 30, lineHeight: '34px', color: 'var(--ink)' }}>
            Nothing saved yet.
          </h1>
          <p className="rg-serif" style={{ fontSize: 16, lineHeight: '24px', color: 'var(--ink-2)', maxWidth: 320 }}>
            Tap the bookmark on any pick and it lands here — ready to compare side by side.
          </p>
          <button
            onClick={() => router.push('/chat?new=1')}
            className="rounded-pill px-5 py-2.5 text-[14px] font-medium mt-1"
            style={{ background: 'var(--ink)', color: 'var(--paper)' }}
          >
            Ask your first thing
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-xl px-5 pb-28 pt-2">
      <HeaderBrand back={false} context="Things you bookmarked" />

      {/* Count + Compare pill */}
      <div className="flex items-center justify-between mt-2 mb-4">
        <span className="text-[13px]" style={{ color: 'var(--ink-2)' }}>
          Saved on this device · {items.length} item{items.length === 1 ? '' : 's'}
        </span>
        {compare.length > 0 && (
          <button
            onClick={() => compare.length === 2 && router.push('/compare')}
            disabled={compare.length !== 2}
            className="rounded-pill px-3 py-1.5 text-[12px] font-semibold disabled:opacity-50"
            style={{ background: 'var(--terra-soft)', color: 'var(--terra-ink)' }}
          >
            Compare · {compare.length}
          </button>
        )}
      </div>

      {/* 2-column grid */}
      <div className="grid grid-cols-2 gap-3.5">
        {items.map((item) => {
          const selected = compare.includes(item.id)
          return (
            <div
              key={item.id}
              onClick={() => toggleCompare(item.id)}
              className="rounded-[14px] overflow-hidden cursor-pointer transition-colors"
              style={{
                background: 'var(--paper-hi)',
                border: `1px solid ${selected ? 'var(--terra)' : 'var(--line)'}`,
              }}
            >
              {/* Image + badges */}
              <div className="relative w-full" style={{ height: 110, background: 'var(--paper-alt)' }}>
                {item.imageUrl ? (
                  <img src={item.imageUrl} alt={item.name} className="w-full h-full object-contain p-3" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <ShoppingCart size={22} style={{ color: 'var(--ink-3)' }} />
                  </div>
                )}
                {/* compare-select check badge top-left */}
                {selected && (
                  <span
                    className="absolute top-2 left-2 rounded-full flex items-center justify-center"
                    style={{ width: 22, height: 22, background: 'var(--terra)' }}
                  >
                    <Check size={13} strokeWidth={3} color="var(--paper)" />
                  </span>
                )}
                {/* saved badge top-right (filled terra) */}
                <button
                  onClick={(e) => { e.stopPropagation(); removeSaved(item.id) }}
                  aria-label="Remove from saved"
                  className="absolute top-2 right-2 rounded-full flex items-center justify-center"
                  style={{ width: 28, height: 28, background: 'var(--paper-hi)', border: '1px solid var(--line)' }}
                >
                  <Bookmark size={14} strokeWidth={1.8} style={{ color: 'var(--terra)', fill: 'var(--terra)' }} />
                </button>
              </div>
              {/* Body */}
              <div className="px-3 pt-2 pb-3 flex flex-col gap-1">
                {item.role && (
                  <span className="uppercase" style={{ fontSize: 9, fontWeight: 600, letterSpacing: '0.08em', color: 'var(--ink-2)' }}>
                    {item.role}
                  </span>
                )}
                <p className="rg-serif line-clamp-2" style={{ fontSize: 15, lineHeight: '20px', fontWeight: 500, color: 'var(--ink)' }}>
                  {item.name}
                </p>
                {item.price != null && item.price > 0 && (
                  <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--ink)' }}>${item.price}</span>
                )}
              </div>
            </div>
          )
        })}
      </div>

      <p className="text-[11px] mt-5" style={{ color: 'var(--ink-3)' }}>
        Tap two cards to compare · saved only on this device.
      </p>
    </div>
  )
}
