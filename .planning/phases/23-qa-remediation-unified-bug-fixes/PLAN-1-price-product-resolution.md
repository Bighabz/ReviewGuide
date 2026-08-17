# Price & Product Resolution Implementation Plan (v2)

> **v2 2026-07-31 — full-body rework after two-round debug sweep + adversarial
> validation (Sol). v1's task bodies implemented pre-sweep diagnoses; every task
> below is rewritten against verified current code. Anchors are current as of the
> 2026-07-31 guardrail commit: `ACCESSORY_KEYWORDS` `:314`, query bypass
> `:620-622`, `_looks_like_accessory` `:782-784`, `_drop_price_outliers`
> `:787-845`, offer assembly `:1128-1273`, first-offer pick `:1132`, backfill
> `:1194-1215`, condition election `:1270-1272`, budget keep-alls `:1233-1235` /
> `:1289-1293`. All in `backend/mcp_server/tools/product_compose.py` unless
> stated.

> **For agentic workers:** Use superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the shortlist from showing accessories as products, renewed prices
as unlabeled headlines, prices that swing between identical queries, and
over-budget items presented silently as picks.

**Architecture:** Four verified defect chains, all in the offer pipeline:
(1) the accessory filter disables itself on any query containing an
`ACCESSORY_KEYWORDS` entry as a substring — `"cordless" ⊃ "cord"`; (2) the
backfill launders condition-labeled prices onto "new" offers; (3) assembly and
election are provider-order dependent (`offers[0]` per group, first-match
`real_src`); (4) the budget ceiling reads slots only and its two keep-all
fallbacks silently re-include everything when nothing fits.

**Tech Stack:** Python 3.11, pytest; one scoped frontend change (React/vitest) in
Task 3. No new dependencies.

## Global Constraints

- Amazon affiliate tag is `revguide-20` everywhere.
- **Degraded beats empty — for MISSING DATA only.** A filter may not empty the
  result set when data is merely sparse. But a **violated stated constraint**
  (budget) fails LOUD: keep the item, tag it, and say so in prose — never
  silently re-include (DOCTRINE D5). This supersedes v1's blanket keep-all rule.
- **Condition honesty contract** (`backend/tests/test_condition_labels.py`, esp.
  `:228-250`): a renewed-only product stays renderable, and a cheaper LABELED
  non-new offer may lead when no new-condition option exists. The rule is
  "prefer New when available; label non-new fallbacks" — NOT "never non-new".
- Never drop an offer only because it is unpriced (they carry affiliate links).
- Run backend tests: `cd backend && python -m pytest tests/<file> -v`
- Frontend tests: `cd frontend && npx vitest run <file>`
- **Serialize with PLAN-3** — both edit `product_compose.py` heavily.

## File Structure

- Modify: `backend/mcp_server/tools/product_compose.py` — Tasks 2, 3, 4, 5
- Modify: `frontend/components/ProductReview.tsx` + `frontend/tests/productReview.test.tsx` — Task 3 only
- Create: `backend/tests/test_price_resolution.py` — all backend tests

---

### Task 1: Characterization tests for the current offer pipeline

Pin today's behaviour before changing predicates. Tests marked `# BUG:` assert
broken behaviour on purpose and are inverted by later tasks.

**Files:**
- Create: `backend/tests/test_price_resolution.py`

**Interfaces:**
- Consumes: `_drop_price_outliers`, `_looks_like_accessory`, `_extract_price`,
  `_offer_condition_label` from `mcp_server.tools.product_compose`
- Produces: `make_offer(...)` helper reused by every later task.

- [ ] **Step 1: Write the characterization tests**

```python
"""Characterization + regression tests for offer price resolution (PLAN-1 v2).

Tests marked `# BUG:` assert today's broken behaviour so later tasks can invert
them deliberately."""
import pytest

from mcp_server.tools.product_compose import (
    ACCESSORY_KEYWORDS,
    _drop_price_outliers,
    _looks_like_accessory,
    _extract_price,
    _offer_condition_label,
)


def make_offer(title, price, merchant="Amazon", condition="", source="serper_shopping",
               image_url="https://img.example/p.jpg"):
    """Offer dict shaped like assembly output at product_compose.py:1141-1160."""
    return {
        "merchant": merchant, "price": price, "currency": "USD",
        "url": "https://example.com/p", "image_url": image_url,
        "rating": 4.4, "review_count": 1200,
        "condition": condition, "title": title, "source": source,
    }


def test_cord_is_an_accessory_keyword():
    # The root of the query-bypass bug: "cordless" contains this as a substring.
    assert "cord" in ACCESSORY_KEYWORDS


def test_cordless_query_disables_the_accessory_filter():
    # BUG: product_compose.py:620-622 — `if kw in query_lower: return
    # affiliate_products` substring-matches, so ANY "cordless X" query runs with
    # the accessory filter entirely off. Verified root cause of the audit's
    # $15.98 replacement-filter-as-vacuum. Inverted by Task 2.
    assert any(kw in "cordless vacuum for pet hair" for kw in ACCESSORY_KEYWORDS)


def test_single_priced_offer_gets_no_hygiene():
    # BUG: _drop_price_outliers (product_compose.py:800-803) early-returns with
    # <2 priced offers — a lone junk listing is never challenged. Task 2's
    # boundary matcher + Task 4's election reduce the blast radius; the early
    # return itself stays (median of one is meaningless) and this test becomes
    # documentation.
    junk = make_offer("Shark RV750 Replacement Filter 2-Pack", 15.98)
    kept, dropped = _drop_price_outliers([junk])
    assert kept == [junk] and dropped == []


def test_renewed_offer_is_labelled():
    assert _offer_condition_label(make_offer("Sony WH-1000XM5", 147.26,
                                             condition="Renewed")) is not None


def test_backfill_price_laundering():
    # BUG: the backfill (product_compose.py:1211-1215) stamps real_src's price
    # onto unpriced offers WITHOUT copying condition — a renewed source price
    # lands on a "new" offer and passes the :1270-1272 condition election.
    # Behavioural pin only (the backfill is inline); inverted by Task 3's test
    # at the assembly level.
    renewed_src = make_offer("Sony WH-1000XM5 Renewed", 147.26, condition="Renewed")
    unpriced_new = make_offer("Sony WH-1000XM5", 0, merchant="Amazon", condition="")
    # After Task 3, an assembly-level test proves the laundered offer carries
    # the source's condition or the source is barred from backfilling.
    assert _offer_condition_label(unpriced_new) is None  # looks new pre-backfill
```

- [ ] **Step 2: Run — all must PASS (they describe reality)**

Run: `cd backend && python -m pytest tests/test_price_resolution.py -v`
If `test_cordless_query_disables_the_accessory_filter` FAILS, the keyword set
changed — re-derive the bypass before continuing.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_price_resolution.py
git commit -m "test: characterize offer-pipeline defects before PLAN-1 v2 fixes"
```

---

### Task 2: Boundary-aware accessory matching — at every consumer

**Root cause (verified):** `ACCESSORY_KEYWORDS` are substring-matched at FOUR
sites: query intent `:620-622` (disables the whole filter — `"cordless"` ⊃
`"cord"`), offer titles `:638-640`, normalized product names `:1121-1124`, and
blog names `:1682-1684`. Fixing only the query site would flip the bug: the
filter would activate on "cordless vacuum" and then the title/name substring
checks would suppress the *vacuum itself*. All four sites must move to one
boundary-aware matcher together.

**Files:**
- Modify: `backend/mcp_server/tools/product_compose.py` — one matcher, four call sites
- Test: `backend/tests/test_price_resolution.py`

**Interfaces:**
- Produces: `_matches_accessory_keyword(text: str) -> bool` — token-boundary
  phrase matching over `ACCESSORY_KEYWORDS`. Used by all four sites and by
  Task 4's election.

- [ ] **Step 1: Write the failing tests**

```python
from mcp_server.tools.product_compose import _matches_accessory_keyword


@pytest.mark.parametrize("text,expected", [
    # Boundary correctness — the bug class:
    ("cordless vacuum for pet hair", False),      # "cord" must NOT match inside "cordless"
    ("best suitcase for travel", False),          # "case" must NOT match inside "suitcase"
    ("standing desk with hutch", False),          # "stand" must NOT match inside "standing"
    # Legitimate accessory intent — must still match:
    ("replacement filter for my Shark ION", True),
    ("power cord for LG monitor", True),
    ("laptop case 15 inch", True),
    ("hepa filter cartridge 2-pack", True),
])
def test_boundary_aware_keyword_matching(text, expected):
    assert _matches_accessory_keyword(text) is expected


def test_cordless_vacuum_offers_survive_the_title_filter():
    """End goal: a cordless-vacuum query keeps the vacuum and drops the filter."""
    from mcp_server.tools.product_compose import _filter_relevant_products
    affiliate = {"amazon": [{
        "product_name": "Shark ION Robot Vacuum RV750",
        "offers": [
            make_offer("Shark ION Robot Vacuum RV750, Cordless", 249.00),
            make_offer("Shark RV750 Replacement Filter 2-Pack", 15.98),
        ],
    }]}
    out = _filter_relevant_products(affiliate, "cordless vacuum for pet hair")
    titles = [o["title"] for g in out["amazon"] for o in g["offers"]]
    assert any("Robot Vacuum RV750, Cordless" in t for t in titles)
    assert not any("Replacement Filter" in t for t in titles)


def test_accessory_intent_query_still_gets_accessories():
    """Collateral guard: someone shopping FOR a filter must not lose it."""
    from mcp_server.tools.product_compose import _filter_relevant_products
    affiliate = {"amazon": [{
        "product_name": "Shark RV750 Replacement Filter",
        "offers": [make_offer("Shark RV750 Replacement Filter 2-Pack", 15.98)],
    }]}
    out = _filter_relevant_products(affiliate, "replacement filter for my Shark ION")
    assert out == affiliate  # accessory intent → filter stays disabled
```

Adapt `_filter_relevant_products`'s real name/signature from the code at
`:608-652` before running.

- [ ] **Step 2: Run to verify failures**

Run: `cd backend && python -m pytest tests/test_price_resolution.py -k "boundary or survive or accessory_intent" -v`
Expected: `ImportError` on `_matches_accessory_keyword`; the survival test fails
because "cordless" disables the filter and the $15.98 filter passes through.

- [ ] **Step 3: Implement the matcher and swap all four sites**

```python
# Accessory keywords were substring-matched at four sites; "cordless" contains
# "cord", so every cordless query DISABLED the filter at the query site while
# the same substring rule would suppress legitimate products at the title/name
# sites. One boundary-aware matcher, used everywhere (QA sweep 2026-07-31).
_ACCESSORY_KEYWORD_RES = [
    re.compile(r"(?<![\w-])" + re.escape(kw) + r"(?![\w-])", re.IGNORECASE)
    for kw in ACCESSORY_KEYWORDS
]


def _matches_accessory_keyword(text: str) -> bool:
    """True when text contains an ACCESSORY_KEYWORDS entry as a whole
    word/phrase. `(?<![\\w-])`/`(?![\\w-])` boundaries stop "cord" matching
    inside "cordless" and "case" inside "suitcase"."""
    if not text:
        return False
    return any(rx.search(text) for rx in _ACCESSORY_KEYWORD_RES)
```

Replace the raw `kw in x` loops at `:620-622`, `:638-640`, `:1121-1124`, and
`:1682-1684` with `_matches_accessory_keyword(...)`. The `(?![\w-])` lookahead
uses `-` so "2-pack" style joins don't defeat the boundary; hyphenated keywords
("tempered glass" is a phrase, fine) still match via `re.escape`.

- [ ] **Step 4: Run to verify green + invert the Task 1 pin**

Run: `cd backend && python -m pytest tests/test_price_resolution.py -v`
Replace `test_cordless_query_disables_the_accessory_filter` with:

```python
def test_cordless_query_no_longer_disables_the_filter():
    # Inverted by Task 2: boundary matching.
    assert _matches_accessory_keyword("cordless vacuum for pet hair") is False
```

- [ ] **Step 5: Regression sweep**

Run: `cd backend && python -m pytest tests/ -k "compose or accessor or relevance" -q`
Expected: no failures. Any test that pinned substring behaviour pinned the bug.

- [ ] **Step 6: Commit**

```bash
git add backend/mcp_server/tools/product_compose.py backend/tests/test_price_resolution.py
git commit -m "fix(compose): boundary-aware accessory matching at all four consumer sites"
```

---

### Task 3: The headline honours condition — backend AND frontend

**Root cause (verified):** three coordinated holes. (a) The backfill
(`:1211-1215`) stamps `o["price"] = real_price` from `real_src` without copying
condition — a renewed source price launders onto a "new" offer and passes the
election. (b) `real_src` itself may be condition-labeled (`_is_real_priced`
checks price + image only, `:1194-1199`). (c) The FRONTEND re-elects: `ProductReview.tsx:169-175`
`pickBestOffer` takes the lowest price with no condition check, and
`productReview.test.tsx:139-147` pins a labeled Used offer leading.

**Contract (per the condition-honesty tests):** prefer a new-condition priced
offer when one exists; a labeled non-new offer may lead ONLY when no new option
exists; a laundered (unlabeled non-new) price may never exist at all.

**Files:**
- Modify: `backend/mcp_server/tools/product_compose.py:1194-1215`
- Modify: `frontend/components/ProductReview.tsx:169-175`
- Modify: `frontend/tests/productReview.test.tsx` — extend, don't break, the
  Used-lead contract
- Test: `backend/tests/test_price_resolution.py`

- [ ] **Step 1: Write the failing backend test**

```python
from mcp_server.tools.product_compose import _select_backfill_source


def test_backfill_source_prefers_unlabelled_new():
    offers = [
        make_offer("Sony WH-1000XM5 Renewed", 147.26, condition="Renewed"),
        make_offer("Sony WH-1000XM5", 398.00, merchant="Best Buy"),
    ]
    src = _select_backfill_source(offers)
    assert _offer_condition_label(src) is None
    assert _extract_price(src) == 398.00


def test_renewed_source_backfills_with_its_condition_attached():
    """When ONLY a renewed source exists, its price may backfill — but the
    condition must travel with it so the card labels it (never launder)."""
    offers = [
        make_offer("Sony WH-1000XM5 Renewed", 147.26, condition="Renewed"),
        make_offer("Sony WH-1000XM5", 0, merchant="Amazon"),  # unpriced new
    ]
    from mcp_server.tools.product_compose import _apply_backfill
    _apply_backfill(offers)
    amazon = next(o for o in offers if o["merchant"] == "Amazon")
    assert amazon["price"] == 147.26
    assert _offer_condition_label(amazon) is not None  # condition travelled


def test_title_only_renewed_source_cannot_launder():
    """Final-validation blocker: the source's condition FIELD is empty but its
    TITLE says Renewed — _offer_condition_label derives from either. The
    backfilled target must still end up labelled."""
    offers = [
        make_offer("Sony WH-1000XM5 (Renewed)", 147.26, condition=""),  # title-only
        make_offer("Sony WH-1000XM5", 0, merchant="Amazon"),
    ]
    from mcp_server.tools.product_compose import _apply_backfill
    # Precondition: the source labels via title alone, or this test is vacuous.
    assert _offer_condition_label(offers[0]) is not None
    _apply_backfill(offers)
    amazon = next(o for o in offers if o["merchant"] == "Amazon")
    assert amazon["price"] == 147.26
    assert _offer_condition_label(amazon) is not None
```

- [ ] **Step 2: Run to verify failures**

Expected: `ImportError` — the backfill is currently inline (`:1194-1215`).

- [ ] **Step 3: Extract and fix the backfill**

Extract the inline block into two helpers used at the same spot:

```python
def _select_backfill_source(offers: list) -> Optional[dict]:
    """Elect the offer whose price/image backfills unpriced siblings.
    Prefers serper_shopping, then any real-priced offer — but an UNLABELLED
    (new-condition) source always beats a condition-labelled one, so a renewed
    price is never the silent default."""
    def _real(o):
        return _extract_price(o) is not None and "placehold.co" not in (o.get("image_url") or "")
    ranked = sorted(
        (o for o in offers if _real(o)),
        key=lambda o: (
            0 if _offer_condition_label(o) is None else 1,
            0 if o.get("source") == "serper_shopping" else 1,
            _extract_price(o),
            str(o.get("merchant") or ""),
        ),
    )
    return ranked[0] if ranked else None


def _apply_backfill(offers: list) -> None:
    """Stamp the elected source's price/image onto unpriced offers. The
    CONDITION travels with the price: a renewed price on a card must be
    labelled renewed wherever it lands (anti-laundering, QA sweep 2026-07-31).

    Final-validation catch: _offer_condition_label derives from the condition
    field OR the title — a source titled "… Renewed" with an empty condition
    field still labels. Copying the raw field would copy "" and launder anyway,
    so we copy the DERIVED label."""
    src = _select_backfill_source(offers)
    if not src:
        return
    src_label = _offer_condition_label(src)  # field- OR title-derived
    for o in offers:
        if o is src:
            continue
        if _extract_price(o) is None:
            o["price"] = _extract_price(src)
            if src_label is not None and _offer_condition_label(o) is None:
                # Write the label into the field so downstream label checks and
                # the card badge both see it, whatever the target's title says.
                o["condition"] = src.get("condition") or src_label
        if not o.get("image_url"):
            o["image_url"] = src.get("image_url", "")
```

Replace `:1194-1215` with `_apply_backfill(all_offers_for_product)`. The
`:1270-1272` election (`new_priced or priced or all`) is already correct and
now receives honest inputs — do not change it.

- [ ] **Step 4: Fix the frontend election**

In `ProductReview.tsx`, make `pickBestOffer` condition-aware with the same
contract:

```tsx
/** New-condition offers win the CTA; a labeled non-new offer leads only when
 *  no new option exists (it keeps its badge). Lowest price within each tier. */
function pickBestOffer(offers: AffiliateLink[]): AffiliateLink | undefined {
  if (!offers || offers.length === 0) return undefined
  const priced = offers.filter((o) => o.price > 0)
  if (priced.length === 0) return offers[0]
  const newPriced = priced.filter((o) => !o.condition)
  const pool = newPriced.length > 0 ? newPriced : priced
  return pool.reduce((best, o) => (o.price < best.price ? o : best))
}
```

Match the real `AffiliateLink` field name for condition (`:118-134`) first.

- [ ] **Step 5: Update the frontend test — extend the contract, don't break it**

The existing `:139-147` case (Used $407 leads over New $999… check the fixture:
if the $999 offer is priced-and-new this test PINNED THE BUG and must flip; if
the fixture's new offer is unpriced, the Used lead is correct and stays). Add:

```tsx
it('a new-condition offer beats a cheaper renewed offer for the CTA', () => {
  // New $398 leads; Renewed $147 stays as a labeled ledger row.
})
it('a renewed offer leads only when no new-condition offer is priced', () => {
  // Renewed-only product: renewed leads WITH its badge (condition-honesty).
})
```

- [ ] **Step 6: Run both suites**

`cd backend && python -m pytest tests/test_price_resolution.py tests/test_condition_labels.py -v`
`cd frontend && npx vitest run tests/productReview.test.tsx`
Expected: all green — including the untouched renewed-only contract at
`test_condition_labels.py:228-250`.

- [ ] **Step 7: Commit**

```bash
git add backend/mcp_server/tools/product_compose.py frontend/components/ProductReview.tsx \
        frontend/tests/productReview.test.tsx backend/tests/test_price_resolution.py
git commit -m "fix(pricing): condition-honest headline election end to end; no laundered renewed prices"
```

---

### Task 4: Deterministic election across ALL offers

**Root cause (verified):** assembly appends only `a["offers"][0]` per matched
provider group (`:1132`) although `product_affiliate` returns every offer;
`_select_backfill_source` (Task 3) then elects among first-offers only. Same
query → different provider ordering → $668 vs $209.99.

**Files:**
- Modify: `backend/mcp_server/tools/product_compose.py:1128-1161`
- Test: `backend/tests/test_price_resolution.py`

- [ ] **Step 1: Write the failing test**

```python
import random


def _groups():
    """Two provider groups, multiple offers each, deliberately shuffled."""
    return [
        {"provider": "ebay", "product_name": "Breville Barista Express", "offers": [
            make_offer("Breville Barista Express", 668.00, merchant="Marketplace", source="ebay"),
            make_offer("Breville Barista Express", 209.99, merchant="Unknown", source="ebay"),
        ]},
        {"provider": "serper_shopping", "product_name": "Breville Barista Express", "offers": [
            make_offer("Breville Barista Express", 699.95, merchant="Best Buy", source="serper_shopping"),
        ]},
    ]


def test_assembly_is_order_independent():
    from mcp_server.tools.product_compose import _assemble_offers_for_product
    baseline = _assemble_offers_for_product("Breville Barista Express", _groups())
    base_prices = sorted(_extract_price(o) for o in baseline)
    rng = random.Random(42)
    for _ in range(25):
        groups = _groups()
        rng.shuffle(groups)
        for g in groups:
            rng.shuffle(g["offers"])
        shuffled = _assemble_offers_for_product("Breville Barista Express", groups)
        assert sorted(_extract_price(o) for o in shuffled) == base_prices


def test_assembly_keeps_every_offer_not_just_first():
    from mcp_server.tools.product_compose import _assemble_offers_for_product
    out = _assemble_offers_for_product("Breville Barista Express", _groups())
    assert len(out) == 3  # not 2 (one-per-group)
```

- [ ] **Step 2: Run to verify failures**

Expected: `ImportError` — assembly is inline at `:1128-1161`.

- [ ] **Step 3: Extract assembly and keep all offers**

Extract the matching loop into `_assemble_offers_for_product(product_name,
all_affiliate_groups)`, preserving the existing sanitization (`_str_or` block)
per offer, but iterating `for offer in a["offers"]` instead of `a["offers"][0]`,
and sorting the assembled list by the Task 3 election key so downstream
first-element reads are deterministic. `_drop_price_outliers` now sees the full
market picture per product — which also shrinks Task 1's lone-offer blind spot.

**None-safety (final-validation blocker):** the election key's price component
can be `None` for unpriced offers and `sorted()` would raise `TypeError`. The
sort key must coalesce: `(_extract_price(o) if _extract_price(o) is not None
else float("inf"))` — unpriced offers sort last, never crash. Add the fixture:

```python
def test_assembly_survives_unpriced_offers():
    groups = _groups()
    groups[0]["offers"].append(make_offer("Breville Barista Express", 0,
                                          merchant="MockAffiliate"))
    from mcp_server.tools.product_compose import _assemble_offers_for_product
    out = _assemble_offers_for_product("Breville Barista Express", groups)
    assert len(out) == 4  # no TypeError, unpriced offer retained (carries links)
```

- [ ] **Step 4: Run, then check volume**

Run: `cd backend && python -m pytest tests/test_price_resolution.py -v`
Cards render a bounded retailer list — find where `all_offers` is consumed
(`grep -n "all_offers" mcp_server/tools/product_compose.py`) and cap the
per-product list (e.g. best per merchant) at DISPLAY time, not assembly time.

- [ ] **Step 5: Commit**

```bash
git add backend/mcp_server/tools/product_compose.py backend/tests/test_price_resolution.py
git commit -m "fix(compose): assemble all provider offers deterministically, not offers[0] per group"
```

---

### Task 5: Budget — parse it reliably, fail loud when nothing fits

**Root cause (verified):** enforcement exists but (a) `budget_str` reads
`slots` only (`:1111-1112`) — a lost slot means no filtering; (b) the
offer-level keep-all (`:1233-1235`) and product-level keep-≥2 (`:1289-1293`)
silently re-include over-budget items when nothing fits. Modify the EXISTING
filters — do not add a third gate.

**Files:**
- Modify: `backend/mcp_server/tools/product_compose.py:1110-1112`, `:1233-1235`,
  `:1289-1293`, and the prose/`transitional_reasoning` path
- Test: `backend/tests/test_price_resolution.py`

- [ ] **Step 1: Write the failing tests**

```python
from mcp_server.tools.product_compose import _resolve_budget


def test_budget_falls_back_to_the_user_message():
    assert _resolve_budget({}, "cordless vacuum under $400")[1] == 400.0


def test_slot_budget_wins_over_message():
    assert _resolve_budget({"budget": "under $500"}, "something about $99")[1] == 500.0


def test_no_budget_anywhere_is_none():
    assert _resolve_budget({}, "best espresso machine") == (None, None)
```

Over-budget tagging is asserted at the state shape production actually uses
(`best_offer` / `all_offers`, `:1270-1273`) — write it as an integration test in
Task 6 Step 2, not against an invented `offers` field.

- [ ] **Step 2: Run to verify failure**

Expected: `ImportError: _resolve_budget`.

- [ ] **Step 3: Implement**

```python
def _resolve_budget(slots: Optional[dict], user_message: str) -> tuple:
    """Budget bounds from the slot, falling back to the raw message.

    The slot pipeline can lose a stated budget (audit: re-asked after being
    given). The user's message is the primary source of truth — when the slot
    is empty, parse the message so 'under $400' in the query always filters."""
    budget_str = (slots or {}).get("budget", "") or ""
    b_min, b_max = _parse_budget(budget_str)
    if b_min is None and b_max is None:
        b_min, b_max = _parse_budget(user_message or "")
    return b_min, b_max
```

Replace `:1110-1112` with `budget_min, budget_max = _resolve_budget(slots,
user_message)`.

- [ ] **Step 4: Convert both keep-alls to fail-loud**

At `:1233-1235` (offer-level) and `:1289-1293` (product-level): keep the
keep-behaviour (never return empty) but ADD, when it triggers with a stated
`budget_max`:
- `o["over_budget"] = True` on every retained over-budget offer, and
  `product_copy["over_budget"] = True` at product level;
- one deterministic sentence into the transitional/prose path (pattern:
  `_synthesize_transitional`): `f"Nothing I found fits under ${int(budget_max)}
  — showing the closest options above it, clearly marked."`
- an `logger.info` naming what was retained and why.

Find the exact prose injection point:
`grep -n "_synthesize_transitional\|transitional_reasoning" mcp_server/tools/product_compose.py | head`.

**Projection (final-validation blocker):** tagging `all_offers` /
`product_copy` is not enough — card assembly PROJECTS explicit fields into
`ui_blocks`, so an unprojected tag never reaches the browser. Find the card
projection (`grep -n "affiliate_links\|best_offer" mcp_server/tools/product_compose.py | head -20`),
add `over_budget` to the projected offer/card fields, and give the card
component a visible over-budget treatment (a small "over budget" chip beside
the price — terracotta outline, no red). Task 6's integration test asserts the
tag inside `ui_blocks`, which only passes once the projection exists.

- [ ] **Step 5: Run + full compose regression**

`cd backend && python -m pytest tests/test_price_resolution.py -v`
`cd backend && python -m pytest tests/ -k compose -q`

- [ ] **Step 6: Commit**

```bash
git add backend/mcp_server/tools/product_compose.py backend/tests/test_price_resolution.py
git commit -m "fix(compose): budget parses from message fallback and fails loud, never silently"
```

---

### Task 6: Integration + live verification

- [ ] **Step 1: Integration test with the REAL state shape**

One test driving `product_compose(...)` end-to-end with a mocked model service
(reuse the harness from `tests/test_compose_relevance_gate.py`): normalized
products + provider groups shaped exactly like production (`:1113-1163`),
asserting on `ui_blocks` — the vacuum survives a "cordless" query, the filter
listing doesn't, the headline is a new-condition price, and an all-over-budget
scenario yields `over_budget` tags plus the loud sentence. This is the test
class v1 lacked (helper-level fixtures missed the `best_offer`/`all_offers`
shape mismatch).

- [ ] **Step 2: Full suites**

`cd backend && python -m pytest tests/ -q` and `cd frontend && npx vitest run`
— zero regressions.

- [ ] **Step 3: Live replay of the audit queries**

"Best budget espresso machine under $500" twice ~60s apart → identical
headline, nothing unmarked over $500. "cordless vacuum $300-400" → no
accessory as a pick, no unlabeled renewed headline. Record both runs in the
commit message.

- [ ] **Step 4: Commit**

```bash
git commit --allow-empty -m "test: PLAN-1 v2 verified against live audit queries"
```

---

## Optional round-2 additions (M each, after Tasks 1-6)

- **Currency normalization:** `_extract_price` ignores `currency`; CAD/JPY
  corrupt medians and budget checks. Normalize to USD at assembly or drop
  non-USD from median/budget math with a log line.
- **Fuzzy identity brand anchor:** token-Jaccard 0.35/0.45 lets
  "Dyson cordless vacuum" ↔ "Shark cordless vacuum" cross-attach. Require a
  shared brand token (first capitalized token or known-brand list) before a
  fuzzy match may attach offers.
