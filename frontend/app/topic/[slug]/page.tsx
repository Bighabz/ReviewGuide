'use client'

import { useRouter, notFound } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import { DISCOVER_TOPICS, getTopicBySlug } from '@/lib/discoverTopics'
import TopicHero from '@/components/TopicHero'

/**
 * Topic blog page. The Discover grid links here instead of preloading chat:
 * a short editorial read about the topic, then a single "Research this in chat"
 * CTA that opens a NEW session seeded with this topic's context (an editable
 * draft — draft=, not auto-send).
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

      {/* Hero — prefers an AI-generated, palette-matched illustration when present */}
      <TopicHero
        slug={topic.slug}
        title={topic.title}
        category={topic.category}
        hook={topic.hook}
        fallbackImage={topic.image}
      />

      {/* Editorial blog body + research CTA. The body is the standalone article;
          the blurb is the card/hero hook, so we don't repeat it here. */}
      <article className="px-4 sm:px-6 md:px-8 mt-7 max-w-2xl">
        <p className="rg-serif" style={{ fontSize: 19, lineHeight: '31px', color: 'var(--ink)' }}>
          {topic.body || topic.blurb}
        </p>

        <div className="rg-hairline my-7" />

        <div className="rg-eyebrow mb-1">Ready to dig in?</div>
        <p className="rg-serif" style={{ fontSize: 15, lineHeight: '23px', color: 'var(--ink-2)' }}>
          Open a fresh chat already framed around this topic — then ask anything to narrow it to your budget and needs.
        </p>
        <button
          onClick={startResearch}
          className="inline-flex items-center gap-2 mt-4 px-5 rounded-full text-white font-medium transition-transform hover:scale-[1.02]"
          style={{ background: 'var(--terra)', minHeight: 48, fontSize: 15, boxShadow: 'var(--shadow-md)' }}
        >
          Research this in chat
          <ArrowRight size={17} />
        </button>
        <p className="text-[12px] mt-2" style={{ color: 'var(--text-secondary)' }}>
          Starts a new session with “{topic.query}” — tweak it before you send.
        </p>
      </article>

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
