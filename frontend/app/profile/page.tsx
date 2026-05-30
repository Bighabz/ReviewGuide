import Link from 'next/link'
import { ArrowRight } from 'lucide-react'
import { HeaderBrand } from '@/components/Brand'

// About-you — MVP empty state (DESIGN.md §5.10). Populated profile is deferred post-MVP;
// this route is reserved and intentionally shows only the empty state.
export default function ProfilePage() {
  return (
    <div className="mx-auto w-full max-w-xl px-5 pb-28 pt-2">
      <HeaderBrand back={false} />

      {/* MVP banner */}
      <div
        className="flex items-start gap-2.5 rounded-[12px] px-3.5 py-3 mt-2"
        style={{ background: 'var(--terra-soft)' }}
      >
        <span className="mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: 'var(--terra)' }} />
        <p className="text-[13px] leading-[19px]" style={{ color: 'var(--terra-ink)' }}>
          MVP state. Populated personality profile deferred post-MVP — route reserved, empty-state only.
        </p>
      </div>

      {/* Hero */}
      <div className="mt-9">
        <div className="rg-eyebrow">About you</div>
        <h1 className="rg-display mt-2" style={{ fontSize: 38, lineHeight: '42px', color: 'var(--ink)' }}>
          Still getting to know you.
        </h1>
        <p className="rg-serif mt-4" style={{ fontSize: 17, lineHeight: '26px', color: 'var(--ink-2)' }}>
          This is where your taste takes shape — the budgets you keep landing on, the brands you trust,
          the tradeoffs you accept and the ones you never will. It fills in quietly as you ask, so the
          next answer already knows the kind of person it&apos;s for.
        </p>
      </div>

      {/* Editorial CTA card */}
      <Link
        href="/chat?new=1"
        className="group flex items-center gap-4 rounded-[14px] border px-4 py-4 mt-7 transition-colors hover:bg-[var(--paper-alt)]"
        style={{ borderColor: 'var(--line)' }}
      >
        <span
          className="flex items-center justify-center rounded-full flex-shrink-0"
          style={{ width: 38, height: 38, background: 'var(--ink)' }}
        >
          <ArrowRight size={18} strokeWidth={2} color="var(--paper)" />
        </span>
        <span className="flex flex-col">
          <span className="text-[15px] font-semibold" style={{ color: 'var(--ink)' }}>Ask your first thing</span>
          <span className="text-[13px]" style={{ color: 'var(--ink-2)' }}>One real question is enough to start.</span>
        </span>
      </Link>

      {/* What lives here, eventually */}
      <div className="mt-10">
        <div className="rg-eyebrow">What lives here, eventually</div>
        <div className="mt-4 space-y-3" style={{ opacity: 0.42 }}>
          {['Your taste profile', 'Budgets & non-negotiables', 'Things you keep coming back to'].map((label) => (
            <div
              key={label}
              className="rounded-[12px] px-4 py-5"
              style={{ border: '1px dashed var(--line-2)' }}
            >
              <span className="text-[14px] font-medium" style={{ color: 'var(--ink-3)' }}>{label}</span>
            </div>
          ))}
        </div>
        <p className="text-[11px] mt-4" style={{ color: 'var(--ink-3)' }}>
          Filled in by your conversations · never by a form.
        </p>
      </div>
    </div>
  )
}
