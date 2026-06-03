'use client'

import {
  Plane,
  Laptop,
  Home,
  Heart,
  Mountain,
  Shirt,
  X,
  Sparkles,
  TrendingUp,
  Star,
  Rocket,
  DollarSign,
  Gift,
  Briefcase,
  Tag,
} from 'lucide-react'
import { useRouter } from 'next/navigation'
import { categories } from '@/lib/categoryConfig'

const ICON_MAP: Record<string, any> = {
  Plane,
  Laptop,
  Home,
  Heart,
  Mountain,
  Shirt,
}

const QUICK_SEARCHES = [
  { label: 'Budget Picks', query: 'best budget products under $100', icon: DollarSign },
  { label: 'Premium Finds', query: 'premium high-end products worth the price', icon: Sparkles },
  { label: 'Trending Now', query: 'trending products in 2026', icon: TrendingUp },
  { label: 'Top Rated', query: 'highest rated products with best reviews', icon: Star },
  { label: 'New Releases', query: 'newest product releases this month', icon: Rocket },
  { label: 'Under $100', query: 'best products under $100', icon: Tag },
  { label: 'Under $500', query: 'best products under $500', icon: Tag },
  { label: 'Gift Ideas', query: 'best gift ideas for any occasion', icon: Gift },
  { label: 'Everyday Carry', query: 'best everyday carry essentials', icon: Briefcase },
]

interface CategorySidebarProps {
  isOpen?: boolean
  onClose?: () => void
}

export default function CategorySidebar({ isOpen = true, onClose }: CategorySidebarProps) {
  const router = useRouter()

  const handleTagClick = (query: string) => {
    router.push(`/chat?q=${encodeURIComponent(query)}&new=1`)
    if (onClose) onClose()
  }

  const handleCategoryClick = (slug: string) => {
    router.push(`/browse/${slug}`)
    if (onClose) onClose()
  }

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <div
        className={`
          fixed lg:relative inset-y-0 left-0 z-[60]
          w-56 lg:w-52 flex flex-col h-screen lg:h-full
          transform transition-transform duration-300 ease-out
          lg:transform-none border-r border-[var(--border)]
          ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
        style={{ background: 'var(--surface)' }}
      >
        {/* Close button (mobile) */}
        <button
          onClick={onClose}
          aria-label="Close categories"
          className="lg:hidden absolute top-1 right-1 min-w-[40px] min-h-[40px] flex items-center justify-center rounded-lg text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-hover)] z-[70]"
        >
          <X size={16} strokeWidth={1.5} />
        </button>

        <div className="flex-1 overflow-y-auto px-3 py-5 space-y-6">
          {/* Quick Searches */}
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-muted)] px-1 mb-2.5">
              Quick Searches
            </div>
            <div className="flex flex-wrap gap-1.5">
              {QUICK_SEARCHES.map((tag) => {
                const TagIcon = tag.icon
                return (
                  <button
                    key={tag.label}
                    onClick={() => handleTagClick(tag.query)}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs font-medium
                      bg-[var(--surface-hover)] text-[var(--text-secondary)]
                      hover:bg-[var(--primary-light)] hover:text-[var(--primary)]
                      transition-colors cursor-pointer"
                  >
                    <TagIcon size={12} strokeWidth={1.5} />
                    {tag.label}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Categories */}
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-muted)] px-1 mb-2">
              Categories
            </div>
            <nav className="space-y-0.5">
              {categories.map((category) => {
                const Icon = ICON_MAP[category.icon] || Laptop
                return (
                  <button
                    key={category.slug}
                    onClick={() => handleCategoryClick(category.slug)}
                    className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-colors group
                      text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-[var(--surface-hover)]"
                  >
                    <Icon
                      size={14}
                      strokeWidth={1.5}
                      className="text-[var(--text-muted)] group-hover:text-[var(--primary)] transition-colors"
                    />
                    <span className="text-xs font-medium">{category.name}</span>
                  </button>
                )
              })}
            </nav>
          </div>
        </div>

        {/* Footer — affiliate disclosure */}
        <div className="border-t border-[var(--border)] p-3">
          <p className="text-[10px] text-[var(--text-muted)] leading-relaxed px-2">
            ReviewGuide.ai earns commissions via affiliate links.
          </p>
        </div>
      </div>
    </>
  )
}
