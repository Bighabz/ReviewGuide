# ReviewGuide.ai — Gap-Closure Implementation Plan

**Created:** 2026-05-30 · **Source:** the 2026-05-30 gap analysis (supersedes `GAP_ANALYSIS.md`)
**Goal:** close the remaining gaps to a launch-ready MVP — real data end-to-end, blueprint-complete visuals, production-hardened.
**Method:** ship each phase as its own PR → CI → merge → verify live. Ordered by (value × low-risk).

Legend: ☐ todo · ▣ in progress · ☑ done

---

## Phase 1 — Composer & carousel layout — ☑ ALREADY CORRECT (verified 2026-05-30)
Audit over-flagged this. On inspection:
- ☑ Cream gradient mask is already implemented (`ChatContainer.tsx:881`).
- ☑ 36px ink send circle + radius-28 pill already correct (`ChatInput.tsx:79-92`).
- ☑ Composer is a flex sibling **below** the bounded scroll area (`MessageList` owns `flex-1 overflow-y-auto`), so it does not overlap content; spec explicitly allows `fixed`/`sticky`. No change needed.

## Phase 2 — Re-enable ChatContainer tests — ☑ DONE (2026-05-30)
The old `.skip` suite asserted the removed pre-blueprint welcome screen, so it was a rewrite, not an un-skip.
- ☑ Deleted stale `tests/ChatContainer.test.tsx.skip`.
- ☑ New `tests/ChatContainer.test.tsx` against current behavior: empty-state greeting, composer renders (no auto-send), loading-history state, send→`streamChat`. 4 tests passing.

## Phase 3 — Real Compare verdict *(backend + frontend; "demo → product")*
Compare verdict + spec rows are hardcoded price logic (`compare/page.tsx`).
- ☐ Verify first: is `transitional_reasoning` actually LLM-backed or placeholder? (informs the composer pattern)
- ☐ Backend: a compare composer/endpoint that takes the two products (+ stated priorities) and returns an AI verdict + curated spec rows. Reuse existing MCP composer patterns.
- ☐ Frontend: wire `/compare` to it with loading + fallback to the current heuristic.

## Phase 4 — Real Discover content *(needs a data-source decision)*
"Popular this week" / trending are fixtures (`lib/trendingTopics.ts`).
- ☐ DECISION: curated-rotating set (cheap, MVP-fine) vs search-derived trending (bigger). Default: curated, refreshed from a small backend list — unless product wants live.
- ☐ Implement chosen source; keep the editorial card shape.

## Phase 5 — Performance & a11y *(frontend; launch hardening)*
- ☐ Asset weight: trim the 2.3 MB hero WebP; migrate eager `<img>` category images to `next/image` + lazy-load.
- ☑ Rate-limit UX: ALREADY implemented — `chatApi.ts:233-241` surfaces 429s with a friendly "wait N minutes" message (parses `Retry-After`).
- ☐ Accessibility: add `@axe-core/playwright` to smoke tests; fix obvious findings (focus, contrast, target size).

## Phase 6 — Minor hardening *(optional / post-launch)*
- ☐ Admin JWT → httpOnly cookie; CSRF on POST.
- ☐ Strip stray `console.log`s; tighten `any` usage.
- ☐ Confirm Langfuse/Sentry env keys set in prod.

---

## Corrections folded in from the audit (do NOT action)
- Secrets are **not** in the repo (`.env*` gitignored; only `.example` tracked).
- Anonymous `/chat` (no route auth) is **by design**; `/login` is an admin gate. Not a security hole.
- Discover hero as a baked WebP is the intended mobile-autoplay fix, not a regression.
