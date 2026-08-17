'use client'

import { useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import UnifiedTopbar from './UnifiedTopbar'
import MobileHeader from './MobileHeader'
import MobileTabBar from './MobileTabBar'
import ConversationSidebar from './ConversationSidebar'
import Footer from './Footer'
import { ChatStatusProvider } from '@/lib/chatStatusContext'
import { CHAT_CONFIG } from '@/lib/constants'

const EXCLUDED_PREFIXES = ['/admin', '/privacy', '/terms', '/affiliate-disclosure', '/login']

interface NavLayoutProps {
  children: React.ReactNode
}

export default function NavLayout({ children }: NavLayoutProps) {
  const pathname = usePathname()
  const router = useRouter()
  const [historyOpen, setHistoryOpen] = useState(false)
  const [currentSessionId, setCurrentSessionId] = useState('')

  const isExcluded = EXCLUDED_PREFIXES.some((prefix) => pathname?.startsWith(prefix))

  if (isExcluded) {
    // Excluded routes render children with no layout chrome.
    // Each excluded route manages its own topbar (or none).
    return <>{children}</>
  }

  // Chat routes render without the desktop footer: the footer eats 395px of
  // viewport, cramming the chat welcome screen into <350px of visible space
  // even after main's overflow-y:auto kicks in. Chat should be chrome-free
  // (same pattern as ChatGPT / Perplexity). Added 2026-04-21.
  const isChat = !!pathname?.startsWith('/chat')

  const handleSearch = (query: string) => {
    router.push(`/chat?q=${encodeURIComponent(query)}&new=1`)
  }

  const handleNewChat = () => {
    router.push('/chat?new=1')
  }

  // The History button opens the conversation drawer. It used to
  // router.push('/chat'), which navigated without ever opening the drawer —
  // ten conversations were created during QA and none were reachable.
  const handleHistory = () => {
    setCurrentSessionId(localStorage.getItem(CHAT_CONFIG.SESSION_STORAGE_KEY) ?? '')
    setHistoryOpen((open) => !open)
  }

  const handleSelectConversation = (sessionId: string) => {
    setHistoryOpen(false)
    // The chat page's ?session= handler does the actual switch, so selecting
    // works from any route, not only when a chat page instance is mounted.
    router.push(`/chat?session=${encodeURIComponent(sessionId)}`)
  }

  const handleNewConversationFromDrawer = () => {
    setHistoryOpen(false)
    handleNewChat()
  }

  return (
    <ChatStatusProvider>
      <div className="flex flex-col h-dvh">
        {/* Desktop: UnifiedTopbar (hidden on mobile) */}
        <div className="hidden md:block">
          <UnifiedTopbar
            onSearch={handleSearch}
            onNewChat={handleNewChat}
            onHistoryClick={handleHistory}
          />
        </div>

        {/* Mobile: MobileHeader (hidden on desktop) */}
        <div className="block md:hidden">
          <MobileHeader onHistoryClick={handleHistory} />
        </div>

        {/* Content area — padded bottom on mobile for 64px tab bar + safe area.
            overflow-y-auto added 2026-04-21 to fix desktop overflow at ≤1200px-tall viewports:
            without it, content taller than (viewport - topbar - footer) overflowed main and
            rendered behind the footer. Chat page's inner h-full overflow-hidden prevents
            double-scroll; homepage/browse use main's scroll.

            The footer lives INSIDE main (last child) so it scrolls with the page content
            instead of staying pinned to the viewport. This pairs with app/template.tsx
            using min-h-full on non-chat routes: the page wrapper fills the screen on short
            pages but grows on long ones, keeping the footer at the true bottom. */}
        {/* Row wrapper (PLAN-7 T1): hosts the conversation drawer to main's
            right. The drawer renders null when closed, so this row changes
            nothing until History is opened; on lg the open drawer is static
            and docks here instead of overlaying. */}
        <div className="flex-1 min-h-0 flex overflow-hidden">
          <main className="flex-1 min-w-0 overflow-y-auto pb-[calc(64px+env(safe-area-inset-bottom))] md:pb-0">
            {children}

            {/* Desktop: Footer (hidden on mobile, and hidden on /chat so the chat
                welcome screen + input can fill the viewport). */}
            {!isChat && (
              <div className="hidden md:block">
                <Footer />
              </div>
            )}
          </main>

          <ConversationSidebar
            isOpen={historyOpen}
            onClose={() => setHistoryOpen(false)}
            currentSessionId={currentSessionId}
            onSelectConversation={handleSelectConversation}
            onNewConversation={handleNewConversationFromDrawer}
          />
        </div>

        {/* Mobile: MobileTabBar (hidden on desktop) */}
        <div className="block md:hidden">
          <MobileTabBar />
        </div>
      </div>
    </ChatStatusProvider>
  )
}
