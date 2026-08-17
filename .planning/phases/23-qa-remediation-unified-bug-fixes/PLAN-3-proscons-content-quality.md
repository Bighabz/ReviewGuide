# Pros/Cons & Content Quality Implementation Plan (v2)

> **v2 2026-07-31 — full-body rework after the debug sweep + adversarial
> validation (Sol). What changed from v1:**
> - The structured evidence v1 consumed (`product_evidence` output) is dead on
>   the recommendation path (scheduled in parallel with its producer,
>   `planner_agent.py:622`) and fabricates "direct quotes" when it does run
>   (comparison path). Pros/cons now come from the **consolidated composer
>   call**, grounded on real `review_data`, and only when grounding exists.
> - v1's card-citations task is DELETED — `ui_blocks` is `List[Any]` in the
>   validator and forwarded whole through all layers (no five-layer wiring
>   needed), and the composer deliberately strips client-facing review sources
>   (`product_compose.py:2571-2579`). Card pros/cons are uncited synthesis;
>   snippets stay internal grounding. This also removes v1's file collisions
>   with PLAN-8.
> - v1's frontend T3 and table-agreement T4 are DELETED — they targeted a
>   `data` prop that doesn't exist (`ProductReview({ product })`,
>   `ProductReview.tsx:205`), empty-cons hiding that already works
>   (`VerdictCard.tsx:321-344`), and table-pinned-to-prose-pick that already
>   works (`product_compose.py:2179-2203`). Replaced by characterization tests.
> - **Flag prerequisites:** `USE_CONSOLIDATED_COMPOSE` defaults False
>   (`config.py:294`) and `USE_REVIEW_GROUNDING` defaults False (`:257-263`).
>   Task 1 works at the call site regardless, but the GROUNDED pros/cons path
>   only produces output when both are enabled — enabling them in the target
>   environment is part of Task 5's verification, not an accident.

> **For agentic workers:** Use superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cards show polarity-correct pros AND cons synthesized from real review
signal — no raw forum snippets, no mid-word truncation, no fabricated quotes —
and a product query never returns prose with no actionable card.

**Architecture:** Extend the consolidated compose schema (the same single LLM
call that already returns per-product `consensus` and `descriptions`) with
per-product `pros`/`cons`, generated from the grounded `review_data` the call
already receives, gated so absence of grounding yields empty lists rather than
parametric invention. Wire into both normal and fallback card paths. The dead
`product_evidence` tool is removed by PLAN-8 Task 3 — **this plan must land
first** so its consumers have their replacement before the tool disappears.

**Tech Stack:** Python 3.11, pytest. Frontend: characterization tests only.

## Global Constraints

- **The role constants are byte-pinned AND mirrored.** `_CONSOLIDATED_SCHEMA_TAIL`
  / `_CONSOLIDATED_EXTRA_RULES` are mirrored byte-for-byte in
  `backend/eval/voice_eval.py` (`CONSOLIDATED_ROLE`), asserted by the sync test
  (`backend/eval/test_eval_smoke.py:229-250`). **Changing the schema tail means
  changing BOTH files in the same commit** — this is the sanctioned way to
  extend the schema (the comment at `product_compose.py:30-34` says so).
- Sourcing honesty (shipped guardrail): pros/cons must be supportable from the
  grounded review signal. No grounding → empty lists. Never raw snippet text in
  a displayed field.
- Every product named in prose must have a card with a buy link.
- Serialize with PLAN-1 (both edit `product_compose.py`); land before PLAN-8 T3.
- Tests: `cd backend && python -m pytest tests/<file> -v`

## File Structure

- Modify: `backend/mcp_server/tools/product_compose.py` — schema tail, rules,
  parse, card wiring (normal + fallback)
- Modify: `backend/eval/voice_eval.py` — mirrored role update (same commit)
- Create: `backend/tests/test_card_proscons.py`
- Create: `frontend/tests/prosConsCharacterization.test.tsx`

---

### Task 1: Extend the consolidated schema with grounded pros/cons

**Files:**
- Modify: `backend/mcp_server/tools/product_compose.py:35-58`
  (`_CONSOLIDATED_SCHEMA_TAIL`, `_CONSOLIDATED_EXTRA_RULES`)
- Modify: `backend/eval/voice_eval.py` — apply the byte-identical change
- Test: `backend/tests/test_card_proscons.py`

**Interfaces:**
- Produces: the consolidated JSON gains
  `"pros_cons": {"<product name>": {"pros": [..], "cons": [..]}}`, and
  `_parse_blog_payload` (or the real parse fn — find it:
  `grep -n "_blog_parsed_early\|def _parse" mcp_server/tools/product_compose.py`)
  exposes it.

- [ ] **Step 1: Write the failing tests**

```python
"""PLAN-3 v2 — grounded pros/cons from the consolidated composer call.

The old evidence path was dead (parallel with its producer) and fabricated
quotes when alive. Pros/cons now ride the consolidated schema, grounded on the
review_data the call already receives."""
import os

import pytest

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from mcp_server.tools.product_compose import (
    _CONSOLIDATED_SCHEMA_TAIL,
    _CONSOLIDATED_EXTRA_RULES,
    _consolidated_blog_role,
    BLOG_SCHEMA_TAIL_SENTINEL := None,  # remove; illustrative only
)


def test_consolidated_schema_declares_pros_cons():
    assert '"pros_cons"' in _CONSOLIDATED_SCHEMA_TAIL


def test_rules_ground_pros_cons_and_forbid_invention():
    lowered = _CONSOLIDATED_EXTRA_RULES.lower()
    assert "pros_cons" in lowered
    assert "review" in lowered           # grounded on review signal
    assert "empty" in lowered            # no grounding -> empty lists
    assert "never" in lowered            # never invent / never quote


def test_transform_still_replaces_the_tail():
    # The extension edits the tail the transform swaps in — the swap must
    # still fire (guards against breaking the .replace anchor).
    fake_role = "ROLE HEAD\n" + __import__(
        "mcp_server.tools.product_compose", fromlist=["_BLOG_SCHEMA_TAIL"]
    )._BLOG_SCHEMA_TAIL
    out = _consolidated_blog_role(fake_role)
    assert '"pros_cons"' in out
    assert out.endswith(_CONSOLIDATED_EXTRA_RULES)
```

Clean up the illustrative import lines to match real names before running.

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/test_card_proscons.py -v`
Expected: FAIL — no `"pros_cons"` in the tail.

- [ ] **Step 3: Extend the tail and rules — in BOTH files**

In `_CONSOLIDATED_SCHEMA_TAIL`, add after `descriptions`:

```
  "pros_cons": {"<product name>": {"pros": ["<short factual strength>", "..."], "cons": ["<short factual caveat>", "..."]}, "...": "..."}
```

In `_CONSOLIDATED_EXTRA_RULES`, append:

```
PROS_CONS RULES (pros_cons field):
- One entry for EACH of the top 3 products (all products if fewer than 3)
- 2-3 pros and 1-2 cons per product, each a short factual phrase (max ~12 words)
- Ground every item in the REVIEW SIGNAL you were given (ratings, volume,
  consensus themes). If you have no review signal for a product, return empty
  lists for it — NEVER invent from general knowledge
- These are synthesis, not quotes: never quote, never attribute, never truncate
  source text into an item
```

Apply the byte-identical edit to `CONSOLIDATED_ROLE` in
`backend/eval/voice_eval.py`.

- [ ] **Step 4: Run + the sync test**

`cd backend && python -m pytest tests/test_card_proscons.py -v`
`cd backend && python -m pytest eval/test_eval_smoke.py -k sync -v`
Both green or the mirror is out of sync — fix before committing.

- [ ] **Step 5: Commit**

```bash
git add backend/mcp_server/tools/product_compose.py backend/eval/voice_eval.py \
        backend/tests/test_card_proscons.py
git commit -m "feat(compose): consolidated schema emits grounded per-product pros/cons"
```

---

### Task 2: Wire pros/cons into cards — normal AND fallback paths

**Root cause being replaced:** the card builder (`product_compose.py:2461-2485`)
files `snippet[:150]` under `pros` and never writes `cons`; fallback cards
hardcode both empty (`:2548-2556`).

**Files:**
- Modify: `backend/mcp_server/tools/product_compose.py:2461-2485` and `:2548-2556`
- Test: `backend/tests/test_card_proscons.py`

**Interfaces:**
- Produces: `_card_pros_cons(pname, blog_pros_cons, review_data) -> tuple[list, list]`
  where `blog_pros_cons` is the parsed `pros_cons` dict from the consolidated
  payload. Returns `([], [])` when the product has no grounded entry.

- [ ] **Step 1: Write the failing tests**

```python
from mcp_server.tools.product_compose import _card_pros_cons

PARSED = {"Breville Barista Express": {
    "pros": ["Built-in burr grinder", "Fast heat-up"],
    "cons": ["Struggles at very fine espresso grind"],
}}
REVIEW = {"Breville Barista Express": {"avg_rating": 4.3, "total_reviews": 1180}}


def test_grounded_entry_flows_to_the_card():
    pros, cons = _card_pros_cons("Breville Barista Express", PARSED, REVIEW)
    assert [p["description"] for p in pros] == ["Built-in burr grinder", "Fast heat-up"]
    assert [c["description"] for c in cons] == ["Struggles at very fine espresso grind"]


def test_no_grounding_yields_empty_not_snippets():
    # Product with a blog entry but NO review signal: sourcing honesty says
    # the model was told to return empty; if it didn't, we drop it here.
    pros, cons = _card_pros_cons("Mystery Machine", PARSED, {})
    assert pros == [] and cons == []


def test_missing_product_yields_empty():
    assert _card_pros_cons("Unknown", PARSED, REVIEW) == ([], [])


def test_items_are_never_raw_truncations():
    long_entry = {"P": {"pros": ["x" * 400], "cons": []}}
    pros, _ = _card_pros_cons("P", long_entry, {"P": {"avg_rating": 4, "total_reviews": 10}})
    # Over-long items are dropped, not truncated mid-word.
    assert pros == []
```

- [ ] **Step 2: Run to verify failure** — `ImportError: _card_pros_cons`.

- [ ] **Step 3: Implement and wire both paths**

```python
def _card_pros_cons(pname: str, blog_pros_cons: dict, review_data: dict) -> tuple:
    """Card pros/cons from the consolidated payload, honesty-gated.

    Double gate: the product must have a parsed pros_cons entry AND real review
    signal (review_data) backing it. Either missing -> ([], []) — an empty
    section beats an invented one. Items are validated, never truncated: the
    old builder's snippet[:150] is exactly what produced mid-word garbage."""
    entry = (blog_pros_cons or {}).get(pname) or {}
    bundle = (review_data or {}).get(pname) or {}
    if not entry or not (bundle.get("avg_rating") or bundle.get("total_reviews")):
        return [], []

    def _items(values):
        out = []
        for v in (values or [])[:3]:
            text = str(v).strip()
            if text and len(text) <= 140:
                out.append({"description": text, "citations": []})
        return out

    return _items(entry.get("pros")), _items(entry.get("cons"))
```

Wire it where the parsed consolidated payload is in scope (find the parse
site: `grep -n "consensus\b.*=\|_blog_parsed" mcp_server/tools/product_compose.py`),
replacing the snippet loop at `:2461-2485`:

```python
            pros, cons = _card_pros_cons(pname, blog_pros_cons, review_data)
```

and the hardcoded empties in the fallback-card builder at `:2548-2556` with the
same call. Snippets remain model INPUT (the grounding block at `:1723-1743`) —
they no longer appear in any displayed field.

- [ ] **Step 4: Run + non-consolidated path check**

`cd backend && python -m pytest tests/test_card_proscons.py -v`
Then confirm the legacy (non-consolidated) path degrades to empty pros/cons
rather than crashing on the absent field:
`cd backend && python -m pytest tests/ -k "compose" -q`

- [ ] **Step 5: Commit**

```bash
git add backend/mcp_server/tools/product_compose.py backend/tests/test_card_proscons.py
git commit -m "fix(compose): cards consume grounded pros/cons; snippets never render"
```

---

### Task 3: A product query never ends as prose with no card

**Root cause (verified):** the early-return branch at `product_compose.py:1068-1075`
deliberately emits `general_product_info` prose with `ui_blocks: []`. The
audit's laptop query hit this: recommendations with prices in prose, nothing
actionable. Detection-and-log (v1's approach) does not satisfy the product rule.

**Files:**
- Modify: `backend/mcp_server/tools/product_compose.py:1068-1075`
- Test: `backend/tests/test_card_proscons.py`

- [ ] **Step 1: Read the branch and record when it fires**

`sed -n '1055,1080p' backend/mcp_server/tools/product_compose.py` — record the
guard conditions in the test docstring. The fix must distinguish "no products
found" (honest no-listings answer, zero cards is correct) from "products exist
but this branch bypassed card assembly".

- [ ] **Step 2: Write the failing test**

**Final-validation correction:** the branch's guard is
`not normalized_products and not affiliate_products and not review_data` — it
fires only when ALL THREE sources are empty, so a fixture with products present
can never exercise it. Test the branch on its own terms: drive
`product_compose` (the `test_compose_relevance_gate.py` harness) with all three
sources EMPTY and `general_product_info` containing prose that names specific
purchasable products with prices (the audit's laptop answer shape). Assert the
emitted answer either (a) strips/suppresses the named-product recommendations,
or (b) is an explicit no-listings response — prose recommending named products
with zero cards must be impossible. Add a second case with sources present
asserting the branch does NOT fire (cards render normally).

- [ ] **Step 3: Fix**

When normalized products with offers exist, the branch may not return
prose-only: route to card assembly (preferred) or suppress unsupported product
names from the prose (the relevance-gate pruning at `:2018-2044` is the
pattern). When genuinely nothing was found, keep the honest no-listings prose.

- [ ] **Step 4: Run + commit**

```bash
cd backend && python -m pytest tests/test_card_proscons.py -v && python -m pytest tests/ -k compose -q
git add backend/mcp_server/tools/product_compose.py backend/tests/test_card_proscons.py
git commit -m "fix(compose): product queries yield cards or an explicit no-listings answer"
```

---

### Task 4: Characterize the two behaviours v1 wrongly planned to build

Both already work; pin them so PLAN-1/PLAN-8's compose edits can't regress them.

**Files:**
- Create: `frontend/tests/prosConsCharacterization.test.tsx`
- Extend: `backend/tests/test_card_proscons.py`

- [ ] **Step 1: Frontend — empty cons render no empty section**

`ForAgainst` already hides empty columns (`VerdictCard.tsx:321-344`). Write a
characterization test rendering `ProductReview` (prop is `product`, NOT `data` —
`ProductReview.tsx:205`) with cons `[]` and assert no empty "against" heading
renders; with cons present, assert the text renders.

- [ ] **Step 2: Backend — table leads with the prose pick**

Compose already pins "How They Compare" to the prose pick
(`product_compose.py:2179-2203`). Extend the compose harness test: mock payload
whose `top_pick` is product B while input order lists A first → assert the
comparison block ranks B first.

- [ ] **Step 3: Run + commit**

```bash
cd frontend && npx vitest run tests/prosConsCharacterization.test.tsx
cd backend && python -m pytest tests/test_card_proscons.py -v
git add frontend/tests/prosConsCharacterization.test.tsx backend/tests/test_card_proscons.py
git commit -m "test: pin empty-cons hiding and table/prose pick agreement"
```

---

### Task 5: Verification

- [ ] **Step 1:** Both suites: `cd backend && python -m pytest tests/ -q`;
  `cd frontend && npx vitest run`. Zero regressions.
- [ ] **Step 2:** Enable `USE_CONSOLIDATED_COMPOSE` + `USE_REVIEW_GROUNDING` in
  the dev env and ask "best espresso machine under $500": THE GOOD/THE CATCH
  read as written synthesis, nothing mid-word, no forum text; a product with no
  review signal shows no invented section. Ask the laptop query: cards appear
  or the answer is an explicit no-listings response.
- [ ] **Step 3:** Confirm the flags' production values are a deliberate rollout
  decision recorded in the commit message (they default OFF — enabling them is
  Habib's call, per DOCTRINE D1's bridge strategy).
- [ ] **Step 4:** `git commit --allow-empty -m "test: PLAN-3 v2 verified — grounded pros/cons live"`
