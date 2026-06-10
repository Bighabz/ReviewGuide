'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import extractResultsData from '@/lib/extractResultsData'
import type { ResultsData } from '@/lib/extractResultsData'
import ResultsProductCard from '@/components/ResultsProductCard'
import ResultsQuickActions from '@/components/ResultsQuickActions'
import { HeaderBrand } from '@/components/Brand'

interface ResultsPageProps {
  params: { id: string }
}

function loadResultsData(): ResultsData | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem('chat_messages')
    if (!raw) return null
    const messages = JSON.parse(raw)
    return extractResultsData(messages)
  } catch {
    return null
  }
}

export default function ResultsPage({ params }: ResultsPageProps) {
  const router = useRouter()
  const sessionId = params.id

  // Load synchronously so tests (which don't wrap in act/waitFor) can access data
  const [resultsData] = useState<ResultsData | null>(() => loadResultsData())
  const [toast, setToast] = useState<string | null>(null)

  // Gate rendering until after mount. resultsData is derived from localStorage —
  // null during SSR (no localStorage on the server), populated on the client. Without
  // this guard the server renders null while the client renders the full page → React
  // hydration mismatch (#418/#423). Returning null until mounted makes the server and
  // first client paint agree; content renders post-mount. (CLAUDE.md: SSR non-determinism.)
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    setMounted(true)
  }, [])

  // Redirect to home if no data found
  useEffect(() => {
    if (resultsData === null) {
      router.replace('/')
    }
  }, [resultsData, router])

  function showToast(message: string) {
    setToast(message)
    setTimeout(() => setToast(null), 2500)
  }

  // Construct results URL with /results/ in it for clipboard sharing
  const resultsUrl =
    typeof window !== 'undefined'
      ? `${window.location.origin}/results/${sessionId}`
      : `/results/${sessionId}`

  if (!mounted || !resultsData) {
    return null
  }

  const { sessionTitle, summaryText, products } = resultsData
  const contextLine = sessionTitle

  return (
    <div className="min-h-screen" style={{ background: 'var(--paper)' }}>
      <div className="max-w-[760px] mx-auto px-4 pt-2 pb-16">
        {/* Header band */}
        <HeaderBrand back onBack={() => router.push('/chat')} context={contextLine} />

        {/* Editorial blog card — THE PICK */}
        <div
          className="rounded-[18px] px-5 py-6 mt-2 rg-blog-in"
          style={{ background: 'var(--paper-hi)', border: '1px solid var(--line)' }}
        >
          <div className="rg-eyebrow rg-eyebrow--terra">The pick</div>
          <h1
            className="rg-display mt-2"
            style={{ fontSize: 30, lineHeight: '36px', color: 'var(--ink)' }}
          >
            {sessionTitle}
          </h1>
          <div className="rg-hairline my-4" />
          {summaryText && (
            <p className="rg-serif" style={{ fontSize: 16, lineHeight: '26px', color: 'var(--ink)' }}>
              {summaryText}
            </p>
          )}
          <div className="mt-5">
            <ResultsQuickActions onToast={showToast} shareUrl={resultsUrl} />
          </div>
        </div>

        {/* THE SHORTLIST — horizontal peek carousel */}
        {products.length > 0 && (
          <div className="mt-8">
            <div className="rg-eyebrow mb-3">
              The shortlist · {products.length} pick{products.length === 1 ? '' : 's'}
            </div>
            <div className="flex gap-4 overflow-x-auto snap-x snap-mandatory scrollbar-hide pb-2 -mx-4 px-4">
              {products.map((product, index) => (
                <div key={product.name + index} className="snap-start shrink-0 w-[240px]">
                  <ResultsProductCard product={product} index={index} />
                </div>
              ))}
              {/* peek buffer */}
              <div className="shrink-0 w-2" aria-hidden />
            </div>
          </div>
        )}

        {/* NOTE: the "Sources analyzed" section was removed — tone.md mandates
            "No source citations. Synthesize." (no client-facing citation
            surface; competitor review-site names never render). */}
      </div>

      {/* Toast */}
      {toast && (
        <div
          className="fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2 rounded-[10px] text-sm font-medium shadow-lg z-50"
          style={{ background: 'var(--ink)', color: 'var(--paper)' }}
        >
          {toast}
        </div>
      )}
    </div>
  )
}
