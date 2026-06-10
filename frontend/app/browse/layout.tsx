/**
 * Browse pages render with the standard app chrome (NavLayout topbar + footer).
 * The old CategorySidebar wrapper was removed with the Section Opener redesign —
 * category navigation now lives on the homepage Index and each page's colophon.
 */
export default function Layout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen bg-[var(--background)] text-[var(--text)]">{children}</div>
}
