/**
 * QA remediation (audit 2026-07-31) — the product promised receipts it cannot produce.
 *
 * The homepage claimed "We read thousands of expert and owner reviews, so you get
 * a straight answer with receipts." Loading states said "Searching the web…",
 * "Pulling the receipts…", "Looking through partner reviews…". Asked for sources,
 * the assistant stated plainly that it has no access to links or review sites and
 * cannot cite anything.
 *
 * Decision (2026-07-31): change the copy to match reality rather than build
 * retrieval. These tests are the ratchet — they fail the build if a retrieval or
 * citation claim reappears anywhere in user-facing copy.
 *
 * What the system ACTUALLY does: aggregates ratings and review volume
 * (review_search.py `_quality_score`) into one ranked pick. It never reads an
 * individual review and never holds a source URL for a claim.
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { join } from 'path'

import { LOADING_COPY } from '@/lib/loadingCopy'

const ROOT = join(__dirname, '..')

/** Phrases that assert retrieval, sourcing, or citation the backend cannot perform. */
const RETRIEVAL_CLAIMS = [
  'receipts',
  'searching the web',
  'search the web',
  'looking through partner reviews',
  'we read thousands',
  'read thousands of',
  'researched live',
]

/**
 * Read a source file with comments stripped.
 *
 * The scan targets user-facing COPY. Comments explaining why a claim was removed
 * legitimately name the banned phrase, and tripping on those would make the
 * guardrail unmaintainable — you could never document the fix.
 */
function sourceOf(relPath: string): string {
  return readFileSync(join(ROOT, relPath), 'utf8')
    .replace(/\{\s*\/\*[\s\S]*?\*\/\s*\}/g, '') // {/* JSX comment */}
    .replace(/\/\*[\s\S]*?\*\//g, '') // /* block comment */
    .replace(/^\s*\/\/.*$/gm, '') // // line comment
}

describe('loading copy', () => {
  it('never claims retrieval the backend does not perform', () => {
    const offenders: string[] = []
    for (const label of LOADING_COPY) {
      for (const claim of RETRIEVAL_CLAIMS) {
        if (label.toLowerCase().includes(claim)) {
          offenders.push(`"${label}" asserts "${claim}"`)
        }
      }
    }
    expect(offenders, offenders.join('; ')).toHaveLength(0)
  })

  it('still has enough phrases to rotate without repeating quickly', () => {
    expect(new Set(LOADING_COPY).size).toBeGreaterThanOrEqual(8)
  })

  it('keeps every phrase in the ambiguous, curious register', () => {
    // Each line ends in an ellipsis — the tone.md §10.1 vocabulary contract.
    for (const label of LOADING_COPY) {
      expect(label.endsWith('…'), `"${label}" should end in an ellipsis`).toBe(true)
    }
  })
})

describe('homepage sourcing claim', () => {
  it('does not promise receipts or claim to read reviews', () => {
    const src = sourceOf('components/home/FrontPage.tsx').toLowerCase()
    const found = RETRIEVAL_CLAIMS.filter((claim) => src.includes(claim))
    expect(found, `FrontPage.tsx still claims: ${found.join(', ')}`).toHaveLength(0)
  })

  it('still makes a value claim rather than going silent', () => {
    // Removing the false claim must not leave an empty hero.
    const src = sourceOf('components/home/FrontPage.tsx')
    expect(src).toMatch(/expert and owner|one clear pick|straight answer/i)
  })
})
