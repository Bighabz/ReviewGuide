import Link from 'next/link'

export default function Footer() {
  return (
    <footer className="w-full border-t border-[var(--border)] bg-[var(--surface)]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        {/* Three-column grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-8 sm:gap-12">
          {/* Brand */}
          <div>
            <h3 className="font-serif text-lg font-semibold text-[var(--text)] mb-3">
              ReviewGuide.ai
            </h3>
            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
              AI-powered product research, reviews, and price comparison — all in one conversation.
            </p>
          </div>

          {/* Legal Links */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-3">
              Legal
            </h4>
            <ul className="space-y-2">
              <li>
                <Link href="/privacy" className="text-sm text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors">
                  Privacy Policy
                </Link>
              </li>
              <li>
                <Link href="/terms" className="text-sm text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors">
                  Terms of Service
                </Link>
              </li>
              <li>
                <Link href="/affiliate-disclosure" className="text-sm text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors">
                  Affiliate Disclosure
                </Link>
              </li>
            </ul>
          </div>

          {/* Connect */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-3">
              Connect
            </h4>
            <ul className="space-y-2">
              <li>
                <a href="mailto:mike@reviewguide.ai" className="text-sm text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors">
                  mike@reviewguide.ai
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Prominent Affiliate Disclosure */}
        <div className="mt-3 pt-3 border-t border-[var(--border)]">
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed max-w-3xl">
            ReviewGuide.ai participates in affiliate marketing programs, including the Amazon Associates program. We may earn commissions when you purchase products through links on our site, at no additional cost to you. Our recommendations are generated independently and are not influenced by affiliate partnerships.
          </p>
        </div>

        {/* Copyright */}
        <div className="mt-3 pt-3 border-t border-[var(--border)]">
          <p className="text-xs text-[var(--text-muted)]">
            &copy; {new Date().getFullYear()} ReviewGuide.ai. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  )
}
