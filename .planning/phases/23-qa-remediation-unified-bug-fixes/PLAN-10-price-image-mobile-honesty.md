# Price Attribution, Image Coverage & Mobile Layout Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this
> plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Source:** Habib's manual QA 2026-08-18 ("best tvs under 4k", "best robot
vacuums for pet hair") — mismatched prices, imageless cards, cramped mobile
layout. Reproduced locally 2026-08-18 against the post-PLAN-1 stack; the card
JSON below is real output.

**Reproduced evidence:**

```
Roomba j7+:  Amazon $156.55 (Open box, img) | eBay $156.55 (Open box, img)
LG OLED C3:  Amazon $1799.99 (img)          | eBay $1799.99 (img)
Neato D10:   Amazon $0, NO image            (blog-fallback card)
```

Every card shows the SAME price on both merchants because `_apply_backfill`
stamps one source's real price onto the other merchants' unpriced mock rows.
The label reads "Amazon – $156.55 Open box" on a link that opens an Amazon
SEARCH page where the real price is neither $156.55 nor open-box. PLAN-1 made
the backfill condition-HONEST (the label travels); it is still
merchant-DISHONEST (the price claims a merchant that never quoted it). That
is the "mismatched prices" Habib saw: card price ≠ price on the landing page.

**Goal:** A price shown next to a merchant is a price that merchant actually
quoted. Borrowed market prices are labeled as market context, never as a
merchant quote. No card renders an empty image box or a bare "$0". Responses
are readable and tappable at 390px.

**Architecture:** Three independent tasks. T1 is backend + frontend
(projection + money-row rendering), T2 is mostly frontend (graceful
imageless/priceless cards) with one backend suppression rule, T3 is a
frontend-only responsive pass. DOCTRINE D1 (retrieval-first) remains the
root-cause fix for name/offer quality; this plan makes the bridge honest.

## Global Constraints

- Never remove an offer solely because it is unpriced (affiliate links earn).
- Condition-honesty contract stands (`test_condition_labels.py`): labeled
  non-new offers may lead only when no new-condition offer is priced.
- `ComposeResult` is the envelope (D2): any new projected field goes through
  the card projection in `product_compose.py` (`affiliate_links.append`,
  ~`:2560`) — ui_blocks pass whole, no schema change needed.
- No orphan lines in any copy added. Terracotta tokens, no blue, no red.
- Tests: `cd backend && python -m pytest tests/<file> -v`;
  `cd frontend && npx vitest run <file>`.

---

### Task 1: Merchant-honest pricing — a borrowed price is market context

**Root cause (verified live):** `_apply_backfill` (`product_compose.py`,
helper near `_select_backfill_source`) stamps the elected source's price onto
every unpriced offer. The card projection then renders those rows as
per-merchant quotes, so Amazon mock rows display eBay/Serper prices. The
duplicate-price columns in the evidence above are all one real price + N
copies.

**Fix shape:** keep the backfill (the card still needs a real headline
number) but make provenance explicit and rendering honest:

- [ ] **Step 1 (backend, test-first):** in `_apply_backfill`, stamp
  `o["price_source"] = "market"` on every backfilled offer and
  `"native"` on offers that arrived priced. Project `price_source` into
  `affiliate_links` next to `over_budget`. Tests in
  `test_price_resolution.py`: backfilled row carries `price_source: market`;
  native row carries `native`; golden path keeps both keys through
  validator/extract/node (extend the PLAN-1 integration test, not the
  ComposeResult field list — ui_blocks pass whole).
- [ ] **Step 2 (frontend, test-first):** in `ProductReview`:
  - The **money row** (headline) may show a market price, labeled: when the
    lead offer's `price_source === "market"`, render "≈ $156.55 market" (or
    "from $156.55") instead of a bare price, keeping the condition badge.
  - **Ledger rows** with `price_source === "market"` render "Check price →"
    instead of the borrowed number — exactly what unpriced rows rendered
    before the backfill existed. A merchant row shows a number ONLY when
    that merchant quoted it.
  - Extend `productReview.test.tsx`: two rows sharing one backfilled price →
    only the money row shows the number (labeled), the ledger row shows
    Check price; a native-priced row still shows its own number.
- [ ] **Step 3 (backend):** `pickBestOffer`/`best_offer` election preference
  gains a final tie-break: native-priced beats market-priced at equal
  condition tier (deterministic, extends the PLAN-1 T4 election key).
- [ ] **Step 4:** run both suites + replay the two evidence queries; assert
  no card shows the same borrowed number as two merchant quotes.
- [ ] Commit: `fix(pricing): merchant-honest prices — borrowed market prices are labeled, never quoted`

**Product note for Habib (decide during review, not blocking):** when only
second-hand offers are priced (Roomba $156.55 Open box), the headline is
honest but reads like the product's price. Option: frame non-new headlines as
"Used from $X" and keep the new-condition search link as the primary CTA.

---

### Task 2: No empty image boxes, no "$0" cards

**Root cause (verified live):** the Neato D10 card is a blog-mention fallback
card (`fallback_card` builder, `product_compose.py` ~`:2620`): Amazon search
link, `price: 0`, empty `image_url` — the frontend renders an empty image
panel and a $0-ish money row.

- [ ] **Step 1 (backend):** fallback cards with NEITHER a real image NOR any
  priced offer are demoted: cap them to at most ONE per response (they exist
  for buy-link coverage of the prose's mentions, not to pad the shortlist).
  Test: three imageless priceless fallback candidates → one card emitted,
  log line names the suppressed two.
- [ ] **Step 2 (frontend):** `ProductReview` renders a compact TEXT-ONLY
  layout when `image_url` is empty (no empty image panel: title, summary,
  CTA row full-width) and shows "Check price →" whenever price is 0/absent —
  never "$0". Characterization tests for both.
- [ ] **Step 3 (backend, cheap win):** before emitting a fallback card, reuse
  any image already harvested for the SAME product name from
  `products_with_offers` fuzzy match (the existing `fallback_image` loop) —
  verify it runs AFTER dedup so merged duplicates donate their images.
- [ ] Commit: `fix(cards): imageless and priceless cards degrade gracefully, never $0 boxes`

---

### Task 3: Mobile response layout pass (390px)

Scoped to the response surface (cards, consensus, composer area) — not a
site-wide redesign. Verify each with Playwright at 390×844 (the PLAN-7 T7
harness pattern in `tests/e2e/smoke.spec.ts`) and screenshots.

- [ ] **Step 1 — audit:** seed a full product answer (localStorage harness
  from `smoke.spec.ts`) and screenshot 390px: list every overflow, cramped
  tap target, and truncation in `ProductReview`, `ReviewConsensus`,
  `ComparisonTable`, follow-up line, suggestion chips.
- [ ] **Step 2 — known fixes (verify each against the audit):**
  - `ProductReview` money row: price + badges + CTA wrap as a column at
    <400px; ledger rows get min-h 44px tap targets.
  - Card image panel: full-bleed width, fixed aspect, `object-contain` —
    no letterboxed slivers.
  - `ReviewConsensus` and `ComparisonTable`: horizontal scroll INSIDE the
    card (`overflow-x-auto` on the container, never body scroll) — pin with
    a vitest/e2e assertion like PLAN-7 T4's.
  - Suggestion chips + clarifier chips: wrap with 8px gaps, min-h 40px
    (clarifier already does; mirror on next_suggestions).
  - Prose: cap line length, 15px/1.6 at mobile, no orphan lines in
    templated copy.
- [ ] **Step 3 — verify:** re-screenshot 390px + 1440px; e2e guard asserting
  no horizontal body scroll on a seeded long answer
  (`document.body.scrollWidth <= innerWidth`).
- [ ] Commit: `fix(ui): mobile response layout — wrap, scroll-in-card, tap targets`

---

### Task 4: Verification

- [ ] Both suites green; replay both evidence queries; screenshot desktop +
  390px before/after into the PR/commit message.
- [ ] `git commit --allow-empty -m "test: PLAN-10 verified — merchant-honest prices, graceful cards, mobile pass"`
