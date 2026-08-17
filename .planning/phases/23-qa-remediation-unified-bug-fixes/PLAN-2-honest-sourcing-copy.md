# Honest Sourcing Copy Implementation Plan

> **⚠ SHIPPED 2026-07-31 — Tasks 1, 2, 3, 4 are DONE.** Read INDEX.md "Corrections"
> first: `BLOG_ROLE` is NOT importable (it is a function-local literal at
> `product_compose.py:1723`). Shipped as `_SOURCING_HONESTY_SECTION` +
> `_with_guardrails()` appended at the call site. Tests: `tests/test_guardrails.py`,
> `frontend/tests/honestCopy.test.ts`.

> **For agentic workers:** Use superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop promising receipts the system cannot produce. Rewrite the marketing claim
and loading labels to describe what actually happens, and stop the model attributing
claims to specific reviewers or users it never read.

**Architecture:** Three surfaces make the sourcing promise — the homepage hero
(`FrontPage.tsx`), the rotating loading copy (`loadingCopy.ts`), and each tool's
`citation_message`. All three are strings; none require pipeline changes. The fourth
change is a behavioural rule appended to the composer role at the call site, forbidding
invented attributions.

**Tech Stack:** Next.js 14 / React 18 / TypeScript; Python 3.11 backend. No new deps.

## Global Constraints

- **`BLOG_ROLE` is byte-pinned.** `backend/mcp_server/tools/product_compose.py:30-32`
  documents that the role constants are mirrored byte-for-byte in
  `backend/eval/voice_eval.py`, and `test_consolidated_role_in_sync_with_production`
  asserts they match. **Never edit `BLOG_ROLE` in place.** Extend it at the call site,
  the way `USE_VOICE_PASS` does at `product_compose.py:73-74`.
- Design tokens are terracotta-on-cream. `--terra #B8543A`, `--ink #1A1816`,
  `--paper #FAFAF7`. No blue.
- **No orphan lines.** Any copy that wraps must not leave a final line under ~60% of the
  column width. Fix it in the writing, not with a CSS hack.
- Decision on record (Habib, 2026-07-31): change the copy, do **not** build retrieval.
  Real citations are a later milestone; nothing in this plan should pretend otherwise.
- Frontend tests: `cd frontend && npx vitest run <file>`
- Backend tests: `cd backend && python -m pytest tests/<file> -v`

## File Structure

- Modify: `frontend/components/home/FrontPage.tsx:81` — the hero claim
- Modify: `frontend/lib/loadingCopy.ts:22-29` — rotating loading labels
- Modify: `backend/mcp_server/tools/product_evidence.py:29`,
  `backend/mcp_server/tools/general_search.py:34`,
  `backend/mcp_server/tools/review_search.py:31` — tool `citation_message` strings
- Modify: `backend/mcp_server/tools/product_compose.py` — call-site role extension only
- Create: `backend/tests/test_no_fabricated_attribution.py`
- Create: `frontend/tests/loadingCopy.test.ts`

---

### Task 1: Rewrite the homepage sourcing claim

**Current text** (`frontend/components/home/FrontPage.tsx:81`):
> We read thousands of expert and owner reviews, so you get a straight answer with receipts.

Two false claims: "we read thousands of reviews" and "receipts". What the system actually
does is weigh aggregate review signal — ratings and volume from
`review_search.py:43-50`'s `_quality_score` — into a single ranked pick.

**Files:**
- Modify: `frontend/components/home/FrontPage.tsx:81`

- [ ] **Step 1: Replace the claim**

```tsx
        We weigh expert and owner sentiment across the market, so you get one clear
        pick instead of forty tabs and a maybe.
```

Both lines run past 60% of the column — no orphan. The claim is now about weighing
sentiment (true: ratings and review volume are aggregated) rather than reading reviews
(false) or producing receipts (false).

- [ ] **Step 2: Check the rendered wrap**

Run: `cd frontend && npm run dev`, open `http://localhost:3000`, and confirm at 1440px
and at 390px that neither line ends in a one- or two-word stub. If it does, reword —
never ship an orphan.

- [ ] **Step 3: Sweep for the same claim elsewhere**

Run: `cd frontend && grep -rn "receipts\|thousands of" app components lib --include=*.tsx --include=*.ts`
Expected: no remaining hits outside `loadingCopy.ts` (handled in Task 2). Fix any found.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/home/FrontPage.tsx
git commit -m "fix(copy): homepage no longer claims to read reviews or produce receipts"
```

---

### Task 2: Rewrite the loading labels

**Root cause:** `frontend/lib/loadingCopy.ts` rotates labels asserting retrieval that
does not happen — `'Searching the web…'` (:22), `'Looking through partner reviews…'`
(:23), `'Pulling the receipts…'` (:29). The user then asks for sources and is told none
exist. The labels must describe real stages.

**Files:**
- Modify: `frontend/lib/loadingCopy.ts:22-29`
- Create: `frontend/tests/loadingCopy.test.ts`

**Interfaces:**
- Consumes: the exported array in `frontend/lib/loadingCopy.ts`. Read the file first to
  get the exact export name and shape before writing the test import.

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest'
// Replace `loadingCopy` with the real export name from frontend/lib/loadingCopy.ts.
import { loadingCopy } from '@/lib/loadingCopy'

// Words that assert retrieval, sourcing, or citation the system cannot perform.
const FORBIDDEN = [
  'receipt',
  'searching the web',
  'partner review',
  'reading review',
  'sources',
  'citation',
]

describe('loadingCopy', () => {
  it('never claims retrieval the backend does not perform', () => {
    for (const label of loadingCopy) {
      for (const banned of FORBIDDEN) {
        expect(
          label.toLowerCase().includes(banned),
          `"${label}" claims "${banned}"`,
        ).toBe(false)
      }
    }
  })

  it('still has enough variety to rotate', () => {
    expect(new Set(loadingCopy).size).toBeGreaterThanOrEqual(4)
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/loadingCopy.test.ts`
Expected: FAIL, naming `Pulling the receipts…`, `Searching the web…`, and
`Looking through partner reviews…`.

- [ ] **Step 3: Replace the labels**

In `frontend/lib/loadingCopy.ts`, replace the offending entries. Keep the array's
existing shape and any entries that are already honest:

```ts
  'Lining up the contenders…',
  'Weighing the tradeoffs…',
  'Comparing the contenders…',
  'Checking prices…',
  'Putting it together…',
```

Each describes a stage that genuinely runs: shortlist generation
(`product_search.py`), ranking (`product_ranking.py`), offer assembly and price
election (`product_compose.py`), composition (`product_compose.py`).

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run tests/loadingCopy.test.ts`
Expected: both tests PASS.

- [ ] **Step 5: Fix the backend tool citation messages**

The same claims appear in tool contracts and can surface in the status line:

- `backend/mcp_server/tools/product_evidence.py:29` — `"Pulling the receipts…"` →
  `"Weighing the tradeoffs…"`
- `backend/mcp_server/tools/general_search.py:34` — `"Searching the web…"` →
  `"Digging for answers…"`
- `backend/mcp_server/tools/review_search.py:31` — `"Seeing what others are saying…"`
  is accurate (it does query SerpAPI for review aggregates). **Leave it.**

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/loadingCopy.ts frontend/tests/loadingCopy.test.ts \
        backend/mcp_server/tools/product_evidence.py backend/mcp_server/tools/general_search.py
git commit -m "fix(copy): loading labels describe real stages, not imagined retrieval"
```

---

### Task 3: Forbid invented attributions

**Root cause:** nothing in the composer role bars attributing a claim to a named source.
The audit caught "came from real user reviews on the platform where the product is
listed. Two users specifically mentioned…" — a fabricated citation about a named brand,
which is a defamation exposure as well as a trust one.

`review_search` returns aggregate signal (`avg_rating`, `total_reviews`, `sources` with
site names) — enough to say "owners rate this 4.4 across ~1,200 ratings", never enough to
say "two users mentioned sagging".

**Files:**
- Modify: `backend/mcp_server/tools/product_compose.py` — call site only, never `BLOG_ROLE`
- Create: `backend/tests/test_no_fabricated_attribution.py`

**Interfaces:**
- Consumes: `BLOG_ROLE`, and the existing call-site extension pattern at
  `product_compose.py:73-74` (`USE_VOICE_PASS`)
- Produces: `ATTRIBUTION_RULE: str` and
  `_with_attribution_rule(role: str) -> str` — appended at the call site.

- [ ] **Step 1: Write the failing test**

```python
"""The composer must never attribute a claim to a specific reviewer or user.

review_search returns aggregate signal only (avg_rating, total_reviews, site
names). Any sentence of the form "two users said X" is invented, and inventing
one about a named brand is a legal exposure, not just a trust cost.
"""
import pytest

from mcp_server.tools.product_compose import (
    BLOG_ROLE,
    ATTRIBUTION_RULE,
    _with_attribution_rule,
)


def test_attribution_rule_is_not_baked_into_blog_role():
    # BLOG_ROLE is byte-pinned and mirrored in backend/eval/voice_eval.py.
    # The rule must be appended at the call site, never edited in.
    assert ATTRIBUTION_RULE not in BLOG_ROLE


def test_with_attribution_rule_appends_once():
    extended = _with_attribution_rule(BLOG_ROLE)
    assert extended.startswith(BLOG_ROLE)
    assert extended.count(ATTRIBUTION_RULE) == 1


def test_with_attribution_rule_is_idempotent():
    once = _with_attribution_rule(BLOG_ROLE)
    assert _with_attribution_rule(once) == once


@pytest.mark.parametrize("phrase", [
    "never attribute",
    "aggregate",
    "number of users",
])
def test_rule_names_the_forbidden_behaviour(phrase):
    assert phrase in ATTRIBUTION_RULE.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_no_fabricated_attribution.py -v`
Expected: FAIL — `ImportError: cannot import name 'ATTRIBUTION_RULE'`.

- [ ] **Step 3: Add the rule and the call-site extension**

Add near the other call-site extensions (`product_compose.py:73-74`):

```python
# Anti-fabrication rule (QA 2026-07-31). Appended at the CALL SITE only — BLOG_ROLE
# is byte-pinned and mirrored in backend/eval/voice_eval.py, so editing it in place
# breaks test_consolidated_role_in_sync_with_production.
ATTRIBUTION_RULE = """

SOURCING HONESTY — non-negotiable:
- You have aggregate review signal only: an average rating, a total rating count, and
  the names of sites that carry reviews. You have NOT read any individual review.
- NEVER attribute a claim to a specific person, a named reviewer, or a number of users.
  "Two users mentioned sagging", "one owner said it arrived damaged", and "reviewers on
  the retailer site report" are all forbidden — you cannot know any of them.
- Say what the aggregate supports: "owners rate it 4.4 across about 1,200 ratings", or
  "the rating spread is wide for a product at this price".
- If you cannot support a criticism from the aggregate, do not make the criticism. This
  matters most for named brands, where an invented complaint is a legal exposure.
- Never claim you searched the web, read reviews, or can provide sources or links.
"""


def _with_attribution_rule(role: str) -> str:
    """Append the sourcing-honesty rule to a role, idempotently."""
    if ATTRIBUTION_RULE in role:
        return role
    return role + ATTRIBUTION_RULE
```

Then wrap the role at every place the composer role is handed to the model. Find them
with:

```bash
cd backend && grep -n "BLOG_ROLE\|_consolidated_blog_role\|_decoupled_blog_role" mcp_server/tools/product_compose.py
```

Apply `_with_attribution_rule(...)` as the **outermost** call, after
`_consolidated_blog_role` / `_decoupled_blog_role`, so the pinned constants are still
transformed byte-identically before the rule is appended.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_no_fabricated_attribution.py -v`
Expected: all PASS.

- [ ] **Step 5: Confirm the byte-pin is intact**

Run: `cd backend && python -m pytest tests/ -k "role_in_sync or voice_eval or consolidated" -v`
Expected: PASS. If `test_consolidated_role_in_sync_with_production` fails, you edited
`BLOG_ROLE` in place — revert and append at the call site instead.

- [ ] **Step 6: Commit**

```bash
git add backend/mcp_server/tools/product_compose.py backend/tests/test_no_fabricated_attribution.py
git commit -m "fix(compose): forbid invented review attributions and source claims"
```

---

### Task 4: Make the language refusal consistent with itself

**Root cause:** a Spanish query produced *"No puedo responder en español — ReviewGuide
funciona solo en inglés,"* followed by four fluent Spanish paragraphs and a promise to
answer in English, also in Spanish. Whatever the language policy is, the response
contradicts it in the same breath.

**Scope decision:** full localisation is out of scope — prices are USD and merchants are
US-only, so a Spanish answer would be misleading even if fluent. This task makes the
behaviour coherent: answer in English, say so once, in English, and do not editorialise.

**Files:**
- Modify: `backend/mcp_server/tools/product_compose.py` — extend `ATTRIBUTION_RULE`
  from Task 3
- Test: `backend/tests/test_no_fabricated_attribution.py`

**Interfaces:**
- Consumes: `ATTRIBUTION_RULE`, `_with_attribution_rule` (Task 3)

- [ ] **Step 1: Write the failing test**

```python
def test_rule_covers_language_consistency():
    lowered = ATTRIBUTION_RULE.lower()
    assert "english" in lowered
    assert "same language" in lowered or "in english" in lowered
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_no_fabricated_attribution.py -k language -v`
Expected: FAIL — `assert False`.

- [ ] **Step 3: Extend the rule**

Append inside the `ATTRIBUTION_RULE` string, before the closing `"""`:

```
LANGUAGE:
- Always answer in English. Prices are USD and merchants are US-only, so an answer in
  another language would imply local availability that does not exist.
- If the user writes in another language, answer their question in English. Do not open
  with a refusal, do not apologise, and never explain the English-only policy in the
  language you are declining to use.
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_no_fabricated_attribution.py -v`
Expected: all PASS.

- [ ] **Step 5: Verify live**

Start the stack and send: *"Busco un colchón para el dolor de espalda, presupuesto 800
euros."* The reply must be entirely in English, must answer the question, and must not
open with a refusal. Note that the EUR/USD mismatch is a separate known gap — record it,
do not fix it here.

- [ ] **Step 6: Commit**

```bash
git add backend/mcp_server/tools/product_compose.py backend/tests/test_no_fabricated_attribution.py
git commit -m "fix(compose): answer non-English queries in English without a self-contradicting refusal"
```

---

### Task 5: Verification pass

- [ ] **Step 1: Run both suites**

```bash
cd backend && python -m pytest tests/ -q
cd ../frontend && npx vitest run
```
Expected: no new failures versus baseline.

- [ ] **Step 2: Re-run the audit's failing conversation**

Ask for a product recommendation, then ask *"which reviews support your pick?"*. The
answer must decline to produce citations **without** contradicting a marketing claim —
because the marketing claim is now gone. Confirm the homepage and the loading labels no
longer promise receipts.

- [ ] **Step 3: Commit**

```bash
git commit --allow-empty -m "test: PLAN-2 verified — no receipts claim, no invented attributions"
```
