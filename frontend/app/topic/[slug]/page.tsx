'use client'

import { useRouter, notFound } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import { DISCOVER_TOPICS, getTopicBySlug } from '@/lib/discoverTopics'

/**
 * Topic landing page (Group C). The Discover carousel links here instead of
 * preloading chat. This is the editorial intro + the single CTA that actually
 * enters research, seeding an *editable* draft (draft=, not auto-send).
 */
export default function TopicPage({ params }: { params: { slug: string } }) {
  const router = useRouter()
  const topic = getTopicBySlug(params.slug)

  if (!topic) return notFound()

  const startResearch = () => {
    router.push(`/chat?draft=${encodeURIComponent(topic.query)}&new=1`)
  }

  // A few other topics to keep browsing (deterministic — no Math.random here).
  const more = DISCOVER_TOPICS.filter((t) => t.slug !== topic.slug).slice(0, 8)

  return (
    <div className="flex flex-col pb-16">
      {/* Back link */}
      <div className="px-4 sm:px-6 md:px-8 pt-4">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors"
        >
          <ArrowLeft size={14} />
          Discover
        </Link>
      </div>

      {/* Hero */}
      <div className="relative h-60 sm:h-80 mx-4 sm:mx-6 md:mx-8 mt-4 rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-float)' }}>
        <img
          src={topic.image}
          alt={topic.title}
          className="w-full h-full object-cover"
          style={{ background: 'var(--paper-alt)' }}
          onError={(e) => {
            e.currentTarget.style.display = 'none'
          }}
        />
        <div
          className="absolute inset-0"
          aria-hidden="true"
          style={{ background: 'linear-gradient(180deg, rgba(26,24,22,0) 28%, rgba(26,24,22,0.55) 62%, rgba(26,24,22,0.88) 100%)' }}
        />
        <div className="absolute bottom-0 left-0 right-0 p-6 sm:p-8">
          <div className="uppercase mb-2" style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--terra-soft)' }}>
            {topic.category}
          </div>
          <h1 className="rg-display tracking-tight text-white" style={{ fontSize: 34, lineHeight: '38px' }}>
            {topic.title}
          </h1>
          <p className="text-sm sm:text-base text-white/80 mt-2 max-w-md">{topic.hook}</p>
        </div>
      </div>

      {/* Editorial intro + CTA */}
      <div className="px-4 sm:px-6 md:px-8 mt-7 max-w-2xl">
        <p className="rg-serif" style={{ fontSize: 18, lineHeight: '28px', color: 'var(--ink)' }}>
          {topic.blurb}
        </p>

        <button
          onClick={startResearch}
          className="inline-flex items-center gap-2 mt-6 px-5 rounded-full text-white font-medium transition-transform hover:scale-[1.02]"
          style={{ background: 'var(--terra)', minHeight: 48, fontSize: 15, boxShadow: 'var(--shadow-md)' }}
        >
          Start researching
          <ArrowRight size={17} />
        </button>
        <p className="text-[12px] mt-2" style={{ color: 'var(--text-secondary)' }}>
          You’ll start with “{topic.query}” — tweak it before you send.
        </p>
      </div>

      {/* More to explore */}
      <section className="px-4 sm:px-6 md:px-8 mt-10">
        <div className="rg-eyebrow mb-3">More to explore</div>
        <div className="flex gap-3 overflow-x-auto pb-2 -mx-4 px-4 sm:-mx-6 sm:px-6 md:-mx-8 md:px-8 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {more.map((t) => (
            <Link
              key={t.slug}
              href={`/topic/${t.slug}`}
              className="group relative flex-shrink-0 w-[150px] sm:w-[172px] overflow-hidden rounded-[14px]"
              style={{ boxShadow: 'var(--shadow-float)', border: '1px solid var(--line)' }}
            >
              <div className="relative aspect-[3/4]">
                <img
                  src={t.image}
                  alt={t.title}
                  loading="lazy"
                  className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                  style={{ background: 'var(--paper-alt)' }}
                />
                <div
                  className="absolute inset-0"
                  aria-hidden="true"
                  style={{ background: 'linear-gradient(180deg, rgba(26,24,22,0) 32%, rgba(26,24,22,0.55) 64%, rgba(26,24,22,0.85) 100%)' }}
                />
                <div className="absolute inset-x-0 bottom-0 p-3">
                  <p className="rg-serif" style={{ fontSize: 14, lineHeight: '17px', fontWeight: 600, color: '#fff' }}>
                    {t.title}
                  </p>
                  <p style={{ fontSize: 11, lineHeight: '14px', color: 'rgba(255,255,255,0.82)', marginTop: 2 }}>
                    {t.hook}
                  </p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
