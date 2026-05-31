'use client'

import { Sun, Moon, Menu, Search, Plus, User, History, Palette } from 'lucide-react'
import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { Wordmark } from './Brand'

const ACCENT_COLORS = [
  { id: 'indigo', label: 'Terracotta', color: '#B8543A' }, // default theme (no data-accent)
  { id: 'teal', label: 'Teal', color: '#0D9488' },
  { id: 'rose', label: 'Rose', color: '#E11D48' },
  { id: 'amber', label: 'Amber', color: '#D97706' },
  { id: 'violet', label: 'Violet', color: '#7C3AED' },
] as const

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
  const [accent, setAccent] = useState<string>('indigo')
  const [showColorPicker, setShowColorPicker] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [scrolled, setScrolled] = useState(false)
  const [searchFocused, setSearchFocused] = useState(false)
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false)
  const colorPickerRef = useRef<HTMLDivElement>(null)
  const pathname = usePathname()
  const router = useRouter()

  const getActiveTab = (): 'discover' | 'ask' | 'saved' | 'compare' | 'profile' => {
    if (pathname?.startsWith('/chat')) return 'ask'
    if (pathname === '/') return 'discover'
    if (pathname?.startsWith('/browse')) return 'discover'
    if (pathname?.startsWith('/saved')) return 'saved'
    if (pathname?.startsWith('/compare')) return 'compare'
    if (pathname?.startsWith('/profile')) return 'profile'
    return 'discover'
  }
  const activeTab = getActiveTab()

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | null
    const savedAccent = localStorage.getItem('accent') || 'indigo'
    const initialTheme = savedTheme || 'light'
    setTheme(initialTheme)
    setAccent(savedAccent)
    document.documentElement.setAttribute('data-theme', initialTheme)
    if (savedAccent !== 'indigo') {
      document.documentElement.setAttribute('data-accent', savedAccent)
    }
  }, [])

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (colorPickerRef.current && !colorPickerRef.current.contains(e.target as Node)) {
        setShowColorPicker(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
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

  const changeAccent = (newAccent: string) => {
    setAccent(newAccent)
    if (newAccent === 'indigo') {
      document.documentElement.removeAttribute('data-accent')
    } else {
      document.documentElement.setAttribute('data-accent', newAccent)
    }
    localStorage.setItem('accent', newAccent)
    setShowColorPicker(false)
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

            {/* Accent Color Picker */}
            <div ref={colorPickerRef} className="relative">
              <button
                onClick={() => setShowColorPicker(!showColorPicker)}
                className="p-2 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-[var(--surface-hover)]"
                title="Accent color"
                aria-label="Change accent color"
              >
                <Palette size={18} strokeWidth={1.5} />
              </button>

              <AnimatePresence>
                {showColorPicker && (
                  <motion.div
                    initial={{ opacity: 0, y: 6, scale: 0.96 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 6, scale: 0.96 }}
                    transition={{ duration: 0.15 }}
                    className="absolute right-0 top-full mt-2 p-3 bg-[var(--surface-elevated)] border border-[var(--border)] rounded-xl shadow-lg z-50"
                  >
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] mb-2 uppercase tracking-widest">
                      Theme
                    </div>
                    <div className="flex gap-2">
                      {ACCENT_COLORS.map((c) => (
                        <button
                          key={c.id}
                          onClick={() => changeAccent(c.id)}
                          className={`w-7 h-7 rounded-full transition-transform hover:scale-110 ${accent === c.id ? 'ring-2 ring-[var(--text)] ring-offset-2 ring-offset-[var(--surface-elevated)] scale-110' : ''
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
