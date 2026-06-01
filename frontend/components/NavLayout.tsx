'use client'

import { usePathname, useRouter } from 'next/navigation'
import UnifiedTopbar from './UnifiedTopbar'
import MobileHeader from './MobileHeader'
import MobileTabBar from './MobileTabBar'
import Footer from './Footer'
import { ChatStatusProvider } from '@/lib/chatStatusContext'

const EXCLUDED_PREFIXES = ['/admin', '/privacy', '/terms', '/affiliate-disclosure', '/login']

interface NavLayoutProps {
  children: React.ReactNode
}

export default function NavLayout({ children }: NavLayoutProps) {
  const pathname = usePathname()
  const router = useRouter()

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

  const handleHistory = () => {
    router.push('/chat')
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
          <MobileHeader />
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
        <main className="flex-1 min-h-0 overflow-y-auto pb-[calc(64px+env(safe-area-inset-bottom))] md:pb-0">
          {children}

          {/* Desktop: Footer (hidden on mobile, and hidden on /chat so the chat
              welcome screen + input can fill the viewport). */}
          {!isChat && (
            <div className="hidden md:block">
              <Footer />
            </div>
          )}
        </main>

        {/* Mobile: MobileTabBar (hidden on desktop) */}
        <div className="block md:hidden">
          <MobileTabBar />
        </div>
      </div>
    </ChatStatusProvider>
  )
}
