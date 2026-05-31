'use client'

import { useState, useEffect, useRef, useCallback, RefCallback } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Home, Bookmark, Plus, LayoutGrid, User, Sun, Moon } from 'lucide-react'

const ACCENT_COLORS = [
  { id: 'indigo', label: 'Terracotta', color: '#B8543A' }, // default theme (no data-accent)
  { id: 'teal', label: 'Teal', color: '#0D9488' },
  { id: 'rose', label: 'Rose', color: '#E11D48' },
  { id: 'amber', label: 'Amber', color: '#D97706' },
  { id: 'violet', label: 'Violet', color: '#7C3AED' },
] as const

const TABS = [
  { id: 'discover', label: 'Discover', icon: Home, href: '/' },
  { id: 'saved', label: 'Saved', icon: Bookmark, href: '/saved' },
  { id: 'ask', label: 'Ask', icon: Plus, href: null },
  { id: 'compare', label: 'Compare', icon: LayoutGrid, href: '/compare' },
  { id: 'profile', label: 'You', icon: User, href: null },
] as const

export default function MobileTabBar() {
  const pathname = usePathname()
  const router = useRouter()
  const [keyboardOpen, setKeyboardOpen] = useState(false)
  const [showProfilePopover, setShowProfilePopover] = useState(false)
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const [accent, setAccent] = useState<string>('indigo')
  const profileRef = useRef<HTMLDivElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Apply env(safe-area-inset-bottom) via DOM ref to bypass React style normalization.
  // Use calc(0px + env(...)) so jsdom's CSS parser preserves the value during tests,
  // while real browsers still respect the env() function.
  const navRefCallback: RefCallback<HTMLElement> = useCallback((node) => {
    if (node) {
      node.style.paddingBottom = 'calc(0px + env(safe-area-inset-bottom))'
    }
  }, [])

  // Read theme/accent from localStorage on mount
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | null
    const savedAccent = localStorage.getItem('accent') || 'indigo'
    setTheme(savedTheme || 'light')
    setAccent(savedAccent)
  }, [])

  // Keyboard detection via visualViewport API
  useEffect(() => {
    if (typeof window === 'undefined' || !window.visualViewport) return
    const vv = window.visualViewport

    const handleResize = () => {
      const keyboardThreshold = window.innerHeight * 0.75
      setKeyboardOpen(vv.height < keyboardThreshold)
    }

    vv.addEventListener('resize', handleResize)
    return () => vv.removeEventListener('resize', handleResize)
  }, [])

  // Close popover on click outside
  useEffect(() => {
    if (!showProfilePopover) return

    const handleClickOutside = (e: MouseEvent) => {
      if (
        profileRef.current &&
        !profileRef.current.contains(e.target as Node)
      ) {
        setShowProfilePopover(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showProfilePopover])

  // Long-press handlers for Profile tab
  const startLongPress = useCallback(() => {
    longPressTimerRef.current = setTimeout(() => {
      setShowProfilePopover(true)
    }, 500)
  }, [])

  const cancelLongPress = useCallback(() => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current)
      longPressTimerRef.current = null
    }
  }, [])

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(newTheme)
    document.documentElement.setAttribute('data-theme', newTheme)
    localStorage.setItem('theme', newTheme)
  }

  const changeAccent = (newAccent: string) => {
    setAccent(newAccent)
    if (newAccent === 'indigo') {
      document.documentElement.removeAttribute('data-accent')
    } else {
      document.documentElement.setAttribute('data-accent', newAccent)
    }
    localStorage.setItem('accent', newAccent)
    setShowProfilePopover(false)
  }

  // Active tab detection
  const getIsActive = (tabId: string, href: string | null) => {
    if (tabId === 'discover') {
      return pathname?.startsWith('/browse') || pathname === '/'
    }
    if (tabId === 'ask') {
      return pathname?.startsWith('/chat') || pathname?.startsWith('/results')
    }
    if (tabId === 'profile') {
      return pathname?.startsWith('/profile')
    }
    if (href) {
      return pathname?.startsWith(href)
    }
    return false
  }

  return (
    <motion.nav
      ref={navRefCallback}
      animate={{ y: keyboardOpen ? '100%' : 0 }}
      transition={{ duration: 0.15, ease: 'easeInOut' }}
      className="fixed bottom-0 left-0 right-0 z-[200]"
      data-keyboard-open={keyboardOpen ? 'true' : 'false'}
      style={{
        background: 'var(--surface-elevated)',
        borderTop: '1px solid #E8E6E1',
      }}
    >
      <div className="flex items-center justify-around h-16 px-2">
        {TABS.map((tab) => {
          const isActive = getIsActive(tab.id, tab.href)

          // Central FAB — Ask tab
          if (tab.id === 'ask') {
            return (
              <button
                key="ask"
                onClick={() => router.push('/chat?new=1')}
                className="relative flex flex-col items-center justify-center active:scale-95 transition-transform"
                aria-label="Start new research"
                data-active={isActive ? 'true' : undefined}
              >
                <div
                  className="flex items-center justify-center w-12 h-12 rounded-full"
                  style={{
                    background: 'var(--primary, #B8543A)',
                    transform: 'translateY(-8px)',
                    boxShadow: '0 4px 16px rgba(184,84,58,0.35)',
                  }}
                >
                  <Plus size={22} strokeWidth={2.5} color="white" />
                </div>
                <span
                  style={{
                    fontSize: '10px',
                    color: isActive ? '#B8543A' : '#6B6560',
                    fontFamily: 'var(--font-dm-sans, system-ui)',
                    fontWeight: 500,
                    marginTop: '-6px',
                  }}
                >
                  Ask
                </span>
              </button>
            )
          }

          // Profile tab — long-press for popover
          if (tab.id === 'profile') {
            const Icon = tab.icon
            return (
              <div key="profile" ref={profileRef} className="relative">
                <button
                  className="flex flex-col items-center gap-0.5 min-w-[56px] py-1"
                  aria-label="Profile"
                  data-active={isActive ? 'true' : undefined}
                  onClick={() => router.push('/profile')}
                  onMouseDown={startLongPress}
                  onMouseUp={cancelLongPress}
                  onMouseLeave={cancelLongPress}
                  onTouchStart={startLongPress}
                  onTouchEnd={cancelLongPress}
                >
                  <Icon
                    size={22}
                    strokeWidth={isActive ? 2 : 1.5}
                    color={isActive ? '#B8543A' : '#6B6560'}
                  />
                  <span
                    style={{
                      fontSize: '10px',
                      color: isActive ? '#B8543A' : '#6B6560',
                      fontFamily: 'var(--font-dm-sans, system-ui)',
                      fontWeight: 500,
                    }}
                  >
                    You
                  </span>
                </button>

                <AnimatePresence>
                  {showProfilePopover && (
                    <motion.div
                      ref={popoverRef}
                      initial={{ opacity: 0, y: 6, scale: 0.96 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 6, scale: 0.96 }}
                      transition={{ duration: 0.15 }}
                      className="absolute bottom-full right-0 mb-2 p-3 rounded-xl border z-[300]"
                      style={{
                        background: 'var(--surface-elevated)',
                        borderColor: 'var(--border, #E8E6E1)',
                        boxShadow: '0 4px 24px rgba(0,0,0,0.12)',
                        minWidth: '140px',
                      }}
                    >
                      {/* Theme toggle */}
                      <button
                        onClick={toggleTheme}
                        className="flex items-center gap-2 w-full px-2 py-1.5 rounded-lg hover:bg-[var(--surface-hover)] transition-colors mb-2"
                        style={{ color: 'var(--text)' }}
                      >
                        {theme === 'light' ? (
                          <Moon size={16} strokeWidth={1.5} />
                        ) : (
                          <Sun size={16} strokeWidth={1.5} />
                        )}
                        <span style={{ fontSize: '13px', fontWeight: 500 }}>
                          {theme === 'light' ? 'Dark mode' : 'Light mode'}
                        </span>
                      </button>

                      {/* Accent color picker */}
                      <div
                        className="text-[10px] font-semibold mb-2 uppercase tracking-widest"
                        style={{ color: 'var(--text-muted)' }}
                      >
                        Accent
                      </div>
                      <div className="flex gap-2">
                        {ACCENT_COLORS.map((c) => (
                          <button
                            key={c.id}
                            onClick={() => changeAccent(c.id)}
                            className={`w-6 h-6 rounded-full transition-transform hover:scale-110 ${
                              accent === c.id ? 'ring-2 ring-offset-1 scale-110' : ''
                            }`}
                            style={{ backgroundColor: c.color }}
                            title={c.label}
                            aria-label={`Set ${c.label} accent`}
                          />
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )
          }

          // Standard tabs
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => tab.href && router.push(tab.href)}
              className="flex flex-col items-center gap-0.5 min-w-[56px] py-1"
              aria-label={tab.label}
              aria-current={isActive ? 'page' : undefined}
              data-active={isActive ? 'true' : undefined}
            >
              <Icon
                size={22}
                strokeWidth={isActive ? 2 : 1.5}
                color={isActive ? '#B8543A' : '#6B6560'}
              />
              <span
                style={{
                  fontSize: '10px',
                  color: isActive ? '#B8543A' : '#6B6560',
                  fontFamily: 'var(--font-dm-sans, system-ui)',
                  fontWeight: 500,
                }}
              >
                {tab.label}
              </span>
            </button>
          )
        })}
      </div>
    </motion.nav>
  )
}
