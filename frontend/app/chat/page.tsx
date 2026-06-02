'use client'

import { useEffect, useState, useCallback, Suspense, useRef } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
// CategorySidebar removed from /chat in B.4 — spec §11.6 forbids filter chip
// bars / refinement sidebars on the chat surface; the conversation IS the
// filter. Component still lives at frontend/components/CategorySidebar.tsx
// because it's used by frontend/components/browse/BrowseLayout.tsx.
import ChatContainer from '@/components/ChatContainer'
import ConversationSidebar from '@/components/ConversationSidebar'
import ErrorBoundary from '@/components/ErrorBoundary'
import { CHAT_CONFIG } from '@/lib/constants'

// Sentinel stored in processedQueryRef for the "new session, no query" case so the
// effect's router.replace fires once per /chat?new=1 navigation instead of re-running
// every time the replace mutates searchParams and re-triggers the effect.
const NEW_EMPTY_SESSION = '__new_empty_session__'

function ChatPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  // sidebarOpen state removed in B.4 alongside CategorySidebar.
  const [conversationSidebarOpen, setConversationSidebarOpen] = useState(false)
  const [clearHistoryTrigger, setClearHistoryTrigger] = useState(0)
  const [showClearDialog, setShowClearDialog] = useState(false)
  const [currentSessionId, setCurrentSessionId] = useState<string>('')
  const [switchToSessionId, setSwitchToSessionId] = useState<string | undefined>(undefined)
  const [initialQuery, setInitialQuery] = useState<string | undefined>(undefined)
  // initialDraft: pre-fills the composer WITHOUT sending (editable starting point).
  // Used by Discover category chips / "popular" rows so the user can refine before asking.
  const [initialDraft, setInitialDraft] = useState<string | undefined>(undefined)

  // Track which query we've processed to avoid re-processing after router.replace
  const processedQueryRef = useRef<string | null>(null)

  useEffect(() => {
    // Check for query parameters (from sticky chat bar on browse page)
    const query = searchParams.get('q')
    const draft = searchParams.get('draft')
    const isNewSession = searchParams.get('new') === '1'

    console.log('[ChatPage] URL params:', { query, draft, isNewSession, alreadyProcessed: processedQueryRef.current })

    // Draft: start a fresh session and seed the composer with editable text (no auto-send).
    if (isNewSession && draft && processedQueryRef.current !== `draft:${draft}`) {
      processedQueryRef.current = `draft:${draft}`
      const newSessionId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = Math.random() * 16 | 0
        const v = c === 'x' ? r : (r & 0x3 | 0x8)
        return v.toString(16)
      })
      localStorage.removeItem(CHAT_CONFIG.MESSAGES_STORAGE_KEY)
      localStorage.setItem(CHAT_CONFIG.SESSION_STORAGE_KEY, newSessionId)
      setSwitchToSessionId(newSessionId)
      setCurrentSessionId(newSessionId)
      setInitialDraft(draft)
      setInitialQuery(undefined)
      setTimeout(() => router.replace('/chat', { scroll: false }), 100)
    }
    // Only process if this is a new session request AND we haven't processed this exact query
    else if (isNewSession && query && processedQueryRef.current !== query) {
      console.log('[ChatPage] Processing new session with query:', query)
      processedQueryRef.current = query

      // Start a fresh session with the query
      const newSessionId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = Math.random() * 16 | 0
        const v = c === 'x' ? r : (r & 0x3 | 0x8)
        return v.toString(16)
      })

      // Clear old session data
      localStorage.removeItem(CHAT_CONFIG.MESSAGES_STORAGE_KEY)
      localStorage.setItem(CHAT_CONFIG.SESSION_STORAGE_KEY, newSessionId)

      setSwitchToSessionId(newSessionId)
      setCurrentSessionId(newSessionId)
      setInitialQuery(query)

      // Clean up URL params after processing (with slight delay to ensure state is set)
      setTimeout(() => {
        router.replace('/chat', { scroll: false })
      }, 100)
    } else if (isNewSession && !query && processedQueryRef.current !== NEW_EMPTY_SESSION) {
      // New session without query - just start fresh.
      // Gate on the sentinel so this branch (and its router.replace) runs once per
      // /chat?new=1 navigation rather than re-firing on every effect re-entry.
      processedQueryRef.current = NEW_EMPTY_SESSION

      const newSessionId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = Math.random() * 16 | 0
        const v = c === 'x' ? r : (r & 0x3 | 0x8)
        return v.toString(16)
      })

      localStorage.removeItem(CHAT_CONFIG.MESSAGES_STORAGE_KEY)
      localStorage.setItem(CHAT_CONFIG.SESSION_STORAGE_KEY, newSessionId)

      setSwitchToSessionId(newSessionId)
      setCurrentSessionId(newSessionId)
      setInitialQuery(undefined)

      setTimeout(() => {
        router.replace('/chat', { scroll: false })
      }, 100)
    } else if (!isNewSession && !query) {
      // Normal page load - load current session ID
      const storedSessionId = localStorage.getItem(CHAT_CONFIG.SESSION_STORAGE_KEY)
      if (storedSessionId) {
        setCurrentSessionId(storedSessionId)
      }
      // QA Round 4 F0c — re-arm the ?new=1 handler once the URL is back to a clean
      // /chat (the post-processing router.replace has landed). Without this, the
      // one-shot NEW_EMPTY_SESSION sentinel made the "New Chat" button a no-op after
      // the first ?new=1 navigation on this page instance: the session never rotated,
      // so old backend context (Redis halt state / last_search_context) leaked into
      // what the user thought was a fresh chat. The sentinel's double-fire protection
      // is preserved — it stays set for the whole window where ?new=1 is in the URL.
      if (processedQueryRef.current === NEW_EMPTY_SESSION) {
        processedQueryRef.current = null
      }
    }
  }, [searchParams, router])

  const handleSessionChange = useCallback((sessionId: string) => {
    setCurrentSessionId(sessionId)
  }, [])

  const handleSelectConversation = useCallback((sessionId: string) => {
    setSwitchToSessionId(sessionId)
    setCurrentSessionId(sessionId)
    setInitialQuery(undefined) // Clear initial query when switching conversations
  }, [])

  const handleNewConversation = useCallback(() => {
    // Generate new session ID
    const newSessionId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = Math.random() * 16 | 0
      const v = c === 'x' ? r : (r & 0x3 | 0x8)
      return v.toString(16)
    })
    setSwitchToSessionId(newSessionId)
    setCurrentSessionId(newSessionId)
    setInitialQuery(undefined)
    processedQueryRef.current = null // Reset for next potential URL param processing
    // Clear local messages
    localStorage.removeItem(CHAT_CONFIG.MESSAGES_STORAGE_KEY)
  }, [])

  const handleClearHistory = () => {
    setShowClearDialog(true)
  }

  const confirmClearHistory = () => {
    setShowClearDialog(false)
    setClearHistoryTrigger(prev => prev + 1)
  }

  const cancelClearHistory = () => {
    setShowClearDialog(false)
  }

  const handleSearch = (query: string) => {
    // Start a new conversation with the search query
    handleNewConversation()
    setInitialQuery(query)
  }

  return (
    <div className="h-full flex flex-col overflow-hidden bg-[var(--background)] text-[var(--text)]">

      {/* Content area below topbar. CategorySidebar removed in B.4 (spec
          §11.6 — no filter chip bars / refinement sidebars on /chat).
          Main content now spans the full viewport width. */}
      <div className="flex-1 flex overflow-hidden relative min-h-0">
        {/* Inner wrapper is a plain <div>: NavLayout already renders the page
            <main> landmark, so a nested <main> here is a duplicate (axe). */}
        <div className="flex-1 flex flex-col overflow-hidden min-h-0">
          <ErrorBoundary>
            <ChatContainer
              clearHistoryTrigger={clearHistoryTrigger}
              externalSessionId={switchToSessionId}
              onSessionChange={handleSessionChange}
              initialQuery={initialQuery}
              initialDraft={initialDraft}
            />
          </ErrorBoundary>
        </div>

        <ConversationSidebar
          isOpen={conversationSidebarOpen}
          onClose={() => setConversationSidebarOpen(false)}
          currentSessionId={currentSessionId}
          onSelectConversation={handleSelectConversation}
          onNewConversation={handleNewConversation}
        />
      </div>

      {/* Custom Clear History Dialog */}
      {showClearDialog && (
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center p-3 sm:p-4"
          style={{
            background: 'rgba(0, 0, 0, 0.5)',
            backdropFilter: 'blur(4px)'
          }}
          onClick={cancelClearHistory}
        >
          <div
            className="rounded-2xl shadow-2xl max-w-md w-full p-5 sm:p-6 bg-[var(--background)] border border-[var(--border)]"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base sm:text-lg font-semibold font-serif mb-2 text-[var(--text)]">
              Clear Chat History
            </h3>
            <p className="text-xs sm:text-sm mb-5 sm:mb-6 text-[var(--text-secondary)]">
              Are you sure you want to clear all chat history? This cannot be undone.
            </p>
            <div className="flex gap-2 sm:gap-3 justify-end">
              <button
                onClick={cancelClearHistory}
                className="px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all bg-[var(--surface)] border border-[var(--border)] text-[var(--text)] hover:bg-[var(--surface-hover)] cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={confirmClearHistory}
                className="px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all bg-[var(--primary)] text-white hover:bg-[var(--primary-hover)] cursor-pointer border-none"
              >
                OK
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function ChatPage() {
  return (
    <Suspense fallback={
      <div className="h-dvh flex items-center justify-center bg-[var(--background)]">
        <div className="text-center text-[var(--text-secondary)]">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-current mb-2"></div>
          <p>Loading chat...</p>
        </div>
      </div>
    }>
      <ChatPageContent />
    </Suspense>
  )
}
