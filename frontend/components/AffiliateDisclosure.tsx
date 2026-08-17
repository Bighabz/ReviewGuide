/**
 * PLAN-7 T3: the FTC-required disclosure has to live on the screens that carry
 * the affiliate links. The Footer (its only pre-existing home) is hidden on
 * /chat entirely and hidden on mobile everywhere, so every link surface —
 * chat, /results/[id], /saved, /compare — renders this line directly.
 */
export default function AffiliateDisclosure() {
  return (
    <p
      data-testid="affiliate-disclosure"
      className="px-4 pt-2 pb-1 text-center text-[11px] leading-relaxed text-[var(--ink-3)]"
    >
      We may earn a commission when you buy through our links, at no extra cost to you.{' '}
      <a href="/affiliate-disclosure" className="underline underline-offset-2 hover:text-[var(--terra)]">
        How this works
      </a>
    </p>
  )
}
