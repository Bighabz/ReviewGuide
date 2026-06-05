'use client'

import { useChatStatus } from '@/lib/chatStatusContext'
import { slugifyProduct } from '@/lib/savedItems'

// "Not quite right?" refinement affordance. Each chip sends the EXACT phrase the
// clarifier's refinement detector recognizes (`_detect_refinement_action` in
// backend/app/agents/clarifier_agent.py — verified against the canonical chips
// in mcp_server/tools/next_step_suggestion.py). The backend re-ranks the prior
// shortlist with adjusted slots WITHOUT re-asking — no backend or API change.
//
// IMPORTANT: these strings are a contract. The detector is an exact-match
// allowlist ("Show cheaper options", "More premium picks", "Different use
// case", "Only <Brand>"), so any reword here silently drops back to a fresh
// query (the "Cheaper" chip would stop making results cheaper). The backend
// operates on the whole shortlist, so the chips carry no product name —
// `productName` only seeds a unique test id (optional: omit it below a carousel).
export default function RefineRow({ productName }: { productName?: string }) {
  // Read live streaming state so chips don't become silent dead-clicks while a
  // previous request is in flight (ChatContainer.handleSuggestionClick no-ops
  // when isStreaming — without this the user gets zero feedback).
  const { isStreaming } = useChatStatus()
  const send = (question: string) => {
    if (isStreaming) return
    window.dispatchEvent(new CustomEvent('sendSuggestion', { detail: { question } }))
  }
  const slug = (productName ? slugifyProduct(productName) : '') || 'shortlist'
  const chips = [
    { label: 'Cheaper', q: 'Show cheaper options' },
    { label: 'More premium', q: 'More premium picks' },
    { label: 'Different use case', q: 'Different use case' },
  ]
  return (
    <div className="mt-4 pt-4 border-t border-[var(--border)]" data-testid={`refine-row-${slug}`}>
      <h4 className="rg-eyebrow mb-2">Not quite right?</h4>
      <div className="flex flex-row flex-wrap gap-2">
        {chips.map((c) => (
          <button
            key={c.label}
            data-testid={`refine-chip-${slug}-${c.label.toLowerCase().replace(/\s+/g, '-')}`}
            onClick={() => send(c.q)}
            disabled={isStreaming}
            className="inline-flex items-center gap-2 rounded-[12px] border border-[var(--line-2)] bg-[var(--paper-hi)] text-[var(--ink)] px-3.5 py-2.5 text-[14px] leading-[20px] font-medium text-left transition-all hover:border-[var(--terra)] hover:bg-[var(--terra-soft)] disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:border-[var(--line-2)] disabled:hover:bg-[var(--paper-hi)]"
          >
            {/* quiz-path 4px terracotta leading dot — matches next_suggestions */}
            <span className="w-1 h-1 rounded-full flex-shrink-0" style={{ background: 'var(--terra)' }} />
            {c.label}
          </button>
        ))}
      </div>
    </div>
  )
}
