'use client'

import { usePathname, useRouter } from 'next/navigation'
import { ArrowLeft, User, Maximize2 } from 'lucide-react'
import { useState, useEffect } from 'react'
import { useChatStatus } from '@/lib/chatStatusContext'
import { CHAT_CONFIG } from '@/lib/constants'
import LoadingStatusText from './LoadingStatusText'
import { Wordmark } from './Brand'

export default function MobileHeader() {
  const pathname = usePathname()
  const router = useRouter()
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const { isStreaming, statusText, sessionTitle } = useChatStatus()

  const isChatRoute = pathname?.startsWith('/chat')
  const isResultsRoute = pathname?.startsWith('/results')
  const showChatHeader = isChatRoute || isResultsRoute

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | null
    setTheme(savedTheme || 'light')
  }, [])

  const handleExpandClick = () => {
    const sessionId = localStorage.getItem(CHAT_CONFIG.SESSION_STORAGE_KEY)
    if (sessionId) {
      router.push(`/results/${sessionId}`)
    }
  }

  return (
    <header
      className="fixed top-0 left-0 right-0 z-[100] flex items-center h-12 px-4"
      style={{
        background: 'var(--background)',
        borderBottom: '1px solid var(--border)',
      }}
    >
      {showChatHeader ? (
        <>
          {/* Back arrow — goes to /chat from results, or / from chat */}
          <button
            onClick={() => router.push(isResultsRoute ? '/chat' : '/')}
            className="flex items-center justify-center w-8 h-8 rounded-lg -ml-1"
            style={{ color: 'var(--text)' }}
            aria-label={isResultsRoute ? 'Back to Chat' : 'Back to Discover'}
          >
            <ArrowLeft size={20} strokeWidth={1.5} />
          </button>

          {/* Dynamic title + status */}
          <div className="flex-1 text-center px-2 min-w-0">
            <div
              className="text-sm font-medium truncate"
              style={{ color: 'var(--text)' }}
            >
              {sessionTitle}
            </div>
            {isStreaming && (
              <div
                className="text-[12px] truncate"
                style={{ color: 'var(--text-secondary)' }}
              >
                <LoadingStatusText statusText={statusText} />
              </div>
            )}
          </div>

          {/* Expand icon — hidden on /results (already on results page) */}
          {!isResultsRoute && (
            <button
              className="flex items-center justify-center w-8 h-8 rounded-lg"
              style={{ color: 'var(--text-muted)' }}
              aria-label="Expand results"
              onClick={handleExpandClick}
            >
              <Maximize2 size={16} strokeWidth={1.5} />
            </button>
          )}

          {/* Spacer to keep title centered when expand icon hidden */}
          {isResultsRoute && (
            <div className="w-8 h-8" />
          )}
        </>
      ) : (
        <>
          {/* Logo — blueprint 3-piece wordmark */}
          <a href="/" className="flex items-center shrink-0 min-h-[40px]" aria-label="ReviewGuide.Ai home">
            <Wordmark size={19} />
          </a>

          {/* Spacer */}
          <div className="flex-1" />

          {/* User avatar */}
          <button
            className="flex w-10 h-10 rounded-full items-center justify-center border transition-all"
            style={{
              background: 'var(--surface)',
              borderColor: 'var(--border)',
              color: 'var(--text-secondary)',
            }}
            aria-label="User menu"
          >
            <User size={14} strokeWidth={1.5} />
          </button>
        </>
      )}
    </header>
  )
}
