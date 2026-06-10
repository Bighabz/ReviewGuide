'use client'

/**
 * SectionOpener — the proposed category browse page: a magazine section opener.
 *   Split hero (text panel + framed photo — never text-on-photo),
 *   "Start here" featured question + numbered question index,
 *   colophon strip for other categories.
 */

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowRight, Search } from 'lucide-react'
import { categories, type BrowseCategory } from '@/lib/categoryConfig'

export default function SectionOpener({ slug = 'electronics' }: { slug?: string }) {
  const router = useRouter()
  const category = categories.find((c) => c.slug === slug) ?? categories[0]
  const number = categories.indexOf(category) + 1
  const [query, setQuery] = useState('')
  const [lead, ...restQueries] = category.queries

  const ask = (q: string) => router.push(`/chat?q=${encodeURIComponent(q)}&new=1`)

  return (
    <div className="space-y-12 sm:space-y-16 pb-8">
      {/* ── Split hero: ivory panel + framed photo ── */}
      <header className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-10 items-stretch px-4 pt-2">
        <div className="flex flex-col justify-center py-6 md:py-10 order-2 md:order-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em]" style={{ color: 'var(--accent)' }}>
            The Guide · Nº {String(number).padStart(2, '0')}
          </p>
          <h1
            className="font-serif tracking-tight mt-3"
            style={{ color: 'var(--text)', fontSize: 'clamp(2.25rem, 5vw, 3.5rem)', lineHeight: 1.05 }}
          >
            {category.name}
          </h1>
          <p className="text-base mt-4 max-w-md leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            {category.tagline}.
          </p>

          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (query.trim()) ask(query.trim())
            }}
            className="mt-7 flex items-center gap-2 rounded-md p-1.5 pl-4 max-w-md"
            style={{ background: 'var(--surface-elevated)', border: '1px solid var(--border)' }}
          >
            <Search size={16} style={{ color: 'var(--text-muted)' }} className="shrink-0" aria-hidden="true" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={`Ask about ${category.name.toLowerCase()}…`}
              aria-label={`Ask about ${category.name}`}
              className="flex-1 min-w-0 bg-transparent text-sm outline-none h-10"
              style={{ color: 'var(--text)' }}
            />
            <button
              type="submit"
              className="h-10 px-4 rounded-md text-sm font-semibold shrink-0"
              style={{ background: 'var(--accent)', color: '#FFF8F4' }}
            >
              Ask
            </button>
          </form>
        </div>

        {/* Photo in a frame with a terracotta offset rule — degrades cleanly if the image fails */}
        <div className="relative order-1 md:order-2 py-2 pr-2">
          <div
            aria-hidden="true"
            className="absolute right-0 top-0 bottom-0 w-2/3 rounded-md"
            style={{ background: 'var(--accent-light)', transform: 'translate(8px, 8px)' }}
          />
          <div
            className="relative aspect-[4/3] md:aspect-auto md:h-full min-h-[220px] rounded-md overflow-hidden"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
          >
            <img src={category.image} alt={category.name} className="w-full h-full object-cover" loading="lazy" />
          </div>
        </div>
      </header>

      {/* ── Start here + question index ── */}
      <section className="px-4">
        <div className="flex items-baseline gap-4 mb-6">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em]" style={{ color: 'var(--accent)' }}>
            Start here
          </p>
          <div className="editorial-rule flex-1 self-center" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-10 items-start">
          {/* Featured question as a pull quote */}
          <button
            onClick={() => ask(lead)}
            className="group text-left rounded-md p-6 sm:p-8 w-full shadow-editorial"
            style={{
              background: 'var(--surface-elevated)',
              border: '1px solid var(--border)',
              borderLeft: '3px solid var(--accent)',
            }}
          >
            <span className="block font-serif italic tracking-tight text-balance" style={{ color: 'var(--text)', fontSize: 'clamp(1.4rem, 3vw, 1.9rem)', lineHeight: 1.25 }}>
              “{lead}”
            </span>
            <span className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold group-hover:gap-2.5 transition-all" style={{ color: 'var(--accent)' }}>
              Ask this <ArrowRight size={15} aria-hidden="true" />
            </span>
          </button>

          {/* Numbered index of the rest */}
          <div style={{ borderTop: '1px solid var(--border)' }}>
            {restQueries.map((q, i) => (
              <button
                key={q}
                onClick={() => ask(q)}
                className="group flex items-center gap-4 py-4 w-full text-left min-h-[56px]"
                style={{ borderBottom: '1px solid var(--border)' }}
              >
                <span className="font-serif italic text-xl w-7 shrink-0 text-right leading-none" style={{ color: 'var(--border-strong)' }}>
                  {i + 2}
                </span>
                <span className="flex-1 font-serif text-[16px] leading-snug group-hover:underline underline-offset-4 decoration-1" style={{ color: 'var(--text)' }}>
                  {q}
                </span>
                <ArrowRight size={14} className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" style={{ color: 'var(--accent)' }} aria-hidden="true" />
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* ── Colophon strip: other sections ── */}
      <section className="px-4">
        <div className="flex items-baseline gap-4 mb-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em]" style={{ color: 'var(--text-muted)' }}>
            Elsewhere in the guide
          </p>
          <div className="editorial-rule flex-1 self-center" />
        </div>
        <div className="flex flex-wrap gap-x-7 gap-y-3">
          {categories
            .filter((c) => c.slug !== category.slug)
            .map((c: BrowseCategory) => (
              <button
                key={c.slug}
                onClick={() => router.push(`/browse/${c.slug}`)}
                className="group inline-flex items-center gap-2 min-h-[44px] text-sm"
              >
                <span className="w-7 h-7 rounded-sm overflow-hidden shrink-0" style={{ background: 'var(--surface)' }}>
                  <img src={c.image} alt="" loading="lazy" className="w-full h-full object-cover" />
                </span>
                <span className="font-serif group-hover:underline underline-offset-4 decoration-1" style={{ color: 'var(--text-secondary)' }}>
                  {c.name}
                </span>
              </button>
            ))}
        </div>
      </section>
    </div>
  )
}
