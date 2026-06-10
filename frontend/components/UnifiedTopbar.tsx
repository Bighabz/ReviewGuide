'use client'

import { Sun, Moon, Menu, Search, Plus, User, History } from 'lucide-react'
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { Wordmark } from './Brand'

interface UnifiedTopbarProps {
  onMenuClick?: () => void
  onNewChat?: () => void
  onHistoryClick?: () => void
  onSearch?: (query: string) => void
  searchPlaceholder?: string
}

export default function UnifiedTopbar({
  onMenuClick,
  onNewChat,
  onHistoryClick,
  onSearch,
  searchPlaceholder = 'Search products, reviews, travel...'
}: UnifiedTopbarProps) {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const [searchQuery, setSearchQuery] = useState('')
  const [scrolled, setScrolled] = useState(false)
  const [searchFocused, setSearchFocused] = useState(false)
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false)
  const pathname = usePathname()
  const router = useRouter()

  const getActiveTab = (): 'discover' | 'browse' | 'ask' | 'saved' | 'compare' | 'profile' => {
    if (pathname?.startsWith('/chat')) return 'ask'
    if (pathname === '/') return 'discover'
    if (pathname?.startsWith('/browse')) return 'browse'
    if (pathname?.startsWith('/saved')) return 'saved'
    if (pathname?.startsWith('/compare')) return 'compare'
    if (pathname?.startsWith('/profile')) return 'profile'
    return 'discover'
  }
  const activeTab = getActiveTab()

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | null
    const initialTheme = savedTheme || 'light'
    setTheme(initialTheme)
    document.documentElement.setAttribute('data-theme', initialTheme)
    // Single-accent brand: scrub any stale accent override from the old picker
    // so returning visitors get terracotta, not amber/teal/etc.
    document.documentElement.removeAttribute('data-accent')
    try {
      localStorage.removeItem('accent')
    } catch {}
  }, [])

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 10)
    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(newTheme)
    document.documentElement.setAttribute('data-theme', newTheme)
    localStorage.setItem('theme', newTheme)
  }

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (onSearch && searchQuery.trim()) {
      onSearch(searchQuery.trim())
      setSearchQuery('')
    }
  }

  return (
    <header
      className={`sticky top-0 z-[100] transition-all duration-300 ${scrolled
        ? 'bg-[var(--background)]/95 backdrop-blur-xl shadow-editorial'
        : 'bg-[var(--background)]'
        }`}
    >
      <div className="w-full px-4 sm:px-6 lg:px-8">
        <div className="h-14 sm:h-16 flex items-center gap-3 sm:gap-5">

          {/* Mobile Menu */}
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 -ml-2 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-[var(--surface-hover)]"
            aria-label="Open menu"
          >
            <Menu size={22} strokeWidth={1.5} />
          </button>

          {/* Logo — blueprint 3-piece wordmark (Review 700 terra / Guide 500 ink / .Ai 700 terra) */}
          <Link href="/" className="flex items-center shrink-0 group" aria-label="ReviewGuide.Ai home">
            <Wordmark size={24} className="group-hover:opacity-80 transition-opacity" />
          </Link>

          {/* Navigation — Refined text links */}
          <nav className="hidden sm:flex items-center gap-1 ml-2">
            <Link
              href="/"
              className={`px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all ${activeTab === 'discover'
                ? 'text-[var(--text)] bg-[var(--surface)]'
                : 'text-[var(--text-secondary)] hover:text-[var(--text)]'
                }`}
            >
              Discover
            </Link>
            <Link
              href="/#the-index"
              className={`px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all ${activeTab === 'browse'
                ? 'text-[var(--text)] bg-[var(--surface)]'
                : 'text-[var(--text-muted)] hover:text-[var(--text)]'
                }`}
            >
              Browse
            </Link>
            <Link
              href="/saved"
              className={`px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all ${activeTab === 'saved'
                ? 'text-[var(--text)] bg-[var(--surface)]'
                : 'text-[var(--text-secondary)] hover:text-[var(--text)]'
                }`}
            >
              Saved
            </Link>
            <Link
              href="/chat?new=1"
              className={`px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all ${activeTab === 'ask'
                ? 'text-[var(--text)] bg-[var(--surface)]'
                : 'text-[var(--text-secondary)] hover:text-[var(--text)]'
                }`}
            >
              Ask
            </Link>
            <Link
              href="/compare"
              className={`px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all ${activeTab === 'compare'
                ? 'text-[var(--text)] bg-[var(--surface)]'
                : 'text-[var(--text-secondary)] hover:text-[var(--text)]'
                }`}
            >
              Compare
            </Link>
            {/* Profile link hidden 2026-04-21 — href was /browse (→ redirects to /), misleading.
                Re-enable once a real /profile page ships. */}
          </nav>

          {/* Search Bar */}
          <form onSubmit={handleSearchSubmit} className="flex-1 max-w-xl hidden md:flex mx-auto">
            <div className="relative w-full">
              <Search
                size={16}
                className={`absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors ${searchFocused ? 'text-[var(--primary)]' : 'text-[var(--text-muted)]'
                  }`}
              />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => setSearchFocused(true)}
                onBlur={() => setSearchFocused(false)}
                placeholder={searchPlaceholder}
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-[var(--surface)] border border-[var(--border)] text-[var(--text)] text-sm placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary)]/40 focus:ring-2 focus:ring-[var(--primary)]/8 transition-all"
              />
            </div>
          </form>

          {/* Right Actions */}
          <div className="flex items-center gap-1.5 sm:gap-2 ml-auto">

            {/* Mobile Search */}
            <button
              onClick={() => setMobileSearchOpen(!mobileSearchOpen)}
              className="md:hidden p-2 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-[var(--surface-hover)]"
              aria-label="Search"
            >
              <Search size={20} strokeWidth={1.5} />
            </button>

            {/* History */}
            <button
              onClick={() => onHistoryClick ? onHistoryClick() : router.push('/chat')}
              className="p-2 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-[var(--surface-hover)]"
              aria-label="Chat history"
              title="Chat history"
            >
              <History size={20} strokeWidth={1.5} />
            </button>

            {/* New Chat — Primary CTA */}
            <button
              onClick={() => onNewChat ? onNewChat() : router.push('/chat?new=1')}
              className="hidden sm:flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--primary)] text-white text-sm font-medium hover:bg-[var(--primary-hover)] transition-all active:scale-[0.97]"
            >
              <Plus size={16} strokeWidth={2.5} />
              <span>New Chat</span>
            </button>

            {/* Mobile New Chat */}
            <button
              onClick={() => onNewChat ? onNewChat() : router.push('/chat?new=1')}
              className="sm:hidden p-2 rounded-lg bg-[var(--primary)] text-white active:scale-95"
              aria-label="New chat"
            >
              <Plus size={20} />
            </button>

            <div className="hidden sm:block w-px h-5 bg-[var(--border)] mx-0.5" />

            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-[var(--surface-hover)]"
              title={theme === 'light' ? 'Dark mode' : 'Light mode'}
              aria-label="Toggle theme"
            >
              <motion.div
                initial={false}
                animate={{ rotate: theme === 'dark' ? 180 : 0 }}
                transition={{ duration: 0.3 }}
              >
                {theme === 'light' ? <Moon size={18} strokeWidth={1.5} /> : <Sun size={18} strokeWidth={1.5} />}
              </motion.div>
            </button>

            {/* User Avatar */}
            <button
              className="hidden sm:flex w-8 h-8 rounded-full bg-[var(--surface)] border border-[var(--border)] items-center justify-center text-[var(--text-muted)] hover:border-[var(--primary)] hover:text-[var(--primary)] transition-all"
              aria-label="User menu"
            >
              <User size={14} strokeWidth={1.5} />
            </button>
          </div>
        </div>
      </div>

      {/* Mobile search form */}
      <AnimatePresence>
        {mobileSearchOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="md:hidden overflow-hidden"
          >
            <form onSubmit={(e) => { handleSearchSubmit(e); setMobileSearchOpen(false) }} className="px-4 pb-3">
              <div className="relative w-full">
                <Search
                  size={16}
                  className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
                />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder={searchPlaceholder}
                  autoFocus
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-[var(--surface)] border border-[var(--border)] text-[var(--text)] text-sm placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary)]/40 focus:ring-2 focus:ring-[var(--primary)]/8 transition-all"
                />
              </div>
            </form>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bottom rule — editorial separator */}
      <div className="editorial-rule" />
    </header>
  )
}
