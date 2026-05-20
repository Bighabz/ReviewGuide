# Intent Router Overhaul — Default-to-Product

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reverse the router philosophy from "prove it's a product query" to "prove it's NOT a product query." This is a product review site — the default should be product search, not general/unclear.

**Architecture:** Replace the fragile keyword→Haiku→general fallback chain with a simple exclusion-based router. Tier 1 checks if the query is clearly NOT a product query (travel, intro, general knowledge). If it's not clearly something else, it's product. Tier 2 Haiku becomes a tiebreaker for edge cases, not a gatekeeper. The keyword lists shrink to only what we need to route AWAY from product.

**Tech Stack:** Python, existing fast_router.py, no new dependencies

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/services/fast_router.py` | Modify | Invert classification logic, simplify fallbacks |

Single file change. The router logic is self-contained.

---

### Task 1: Invert _classify_tier1 to default-to-product

**Files:**
- Modify: `backend/app/services/fast_router.py:454-535` (the `_classify_tier1` function)

The current logic: check product keywords → if none match → return None → Haiku → if fails → "general".

New logic: check if it's clearly travel, intro, comparison, or general knowledge. If NONE of those match → it's product. The `_PRODUCT_KEYWORDS` list becomes unnecessary.

- [ ] **Step 1: Rewrite `_classify_tier1` with inverted logic**

Replace the function body (keep the signature). New logic:

```python
def _classify_tier1(
    query: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    last_search_context: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Deterministic intent classification — DEFAULT IS PRODUCT.

    Only routes AWAY from product when clearly something else.
    This is a product review site. When in doubt, search for products.

    Explicitly routed away:
        1. intro (short greetings, <= 4 words)
        2. comparison (explicit vs / compare)
        3. travel (trip, hotel, flight keywords)
        4. general (pure knowledge questions with NO product signal)

    Everything else → product.
    """
    q = query.strip().lower()

    # 1. Intro — only pure short greetings
    is_greeting = any(pat.search(q) for pat in _INTRO_PATTERNS)
    if is_greeting and len(q.split()) <= 4:
        return "intro"

    # 2. Comparison — explicit compare signals
    if _has_keyword(q, _COMPARISON_KEYWORDS):
        return "comparison"

    # 3. Travel — clear travel intent
    if _has_keyword(q, _TRAVEL_KEYWORDS):
        return "travel"

    # 4. General — ONLY if it's clearly a knowledge question AND has
    #    no product/brand/category signal at all
    has_general = _has_keyword(q, _GENERAL_KEYWORDS)
    if has_general:
        # Check if there's ANY product signal — if so, it's product, not general
        has_brand = any(re.search(r"\b" + re.escape(b) + r"\b", q) for b in KNOWN_BRANDS)
        has_category = any(re.search(r"\b" + re.escape(c) + r"\b", q) for c in KNOWN_CATEGORIES)
        has_product_kw = _has_keyword(q, _PRODUCT_KEYWORDS)
        if not has_brand and not has_category and not has_product_kw:
            return "general"
        # Has product signal + general signal → product wins
        # e.g. "what is the best laptop" → product, not general

    # 5. Service — only when clearly a service query
    if _has_keyword(q, _SERVICE_KEYWORDS) and not _has_keyword(q, _PRODUCT_KEYWORDS):
        return "service"

    # 6. Follow-up context from previous search
    if last_search_context and last_search_context.get("intent") in (
        "product", "comparison", "service",
    ):
        return last_search_context["intent"]

    # DEFAULT: product. This is a product review site.
    return "product"
```

- [ ] **Step 2: Verify the logic handles key cases**

Mental walkthrough:
- "best electric skateboards" → no travel/intro/general match → **product** ✓
- "top picks for headphones" → no travel/intro/general match → **product** ✓
- "hi" → greeting, 1 word → **intro** ✓
- "hi I need a lawn mower" → greeting but 7 words → falls through → **product** ✓
- "what is quantum computing" → general keyword, no brand/category → **general** ✓
- "what is the best laptop" → general keyword BUT "laptop" is a category → **product** ✓
- "flights to tokyo" → travel keyword → **travel** ✓
- "sony vs bose" → comparison keyword → **comparison** ✓
- "recommend a good vacuum" → no travel/intro/general → **product** ✓
- "I want something for my kitchen" → no travel/intro/general → **product** ✓

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/fast_router.py
git commit -m "feat: invert intent router to default-to-product

Product review site should default to product search. Only route
away when query is clearly travel, intro, comparison, or pure
general knowledge. Removes dependency on _PRODUCT_KEYWORDS for
the core classification path."
```

---

### Task 2: Simplify fast_router_sync to match

**Files:**
- Modify: `backend/app/services/fast_router.py:541-570` (`fast_router_sync` function)

Since `_classify_tier1` now always returns a value (never None), the "unclear" fallback is dead code. Simplify.

- [ ] **Step 1: Remove the None/unclear branch**

```python
def fast_router_sync(
    query: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    last_search_context: Optional[Dict[str, Any]] = None,
) -> FastRouterResult:
    """
    Synchronous entry point for Tier 1 fast routing.

    _classify_tier1 always returns an intent (defaults to product).
    No more unclear/None path.
    """
    intent = _classify_tier1(query, conversation_history, last_search_context)
    slots = extract_slots(query)

    # Confidence heuristics
    if intent == "intro":
        confidence = 0.99
    elif intent == "comparison":
        confidence = 0.95
    elif intent == "travel":
        confidence = 0.92 if "destination" in slots else 0.82
    elif intent == "general":
        confidence = 0.85
    elif intent in ("product", "service"):
        has_slot = "brand" in slots or "category" in slots
        confidence = 0.92 if has_slot else 0.80
    else:
        confidence = 0.75

    return FastRouterResult(
        intent=intent,
        slots=slots,
        tool_chain=TOOL_CHAINS[intent],
        plan={"steps": PLAN_TEMPLATES[intent]},
        confidence=confidence,
        tier=1,
        needs_clarification=False,
    )
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/fast_router.py
git commit -m "refactor: remove dead unclear/None path from fast_router_sync

_classify_tier1 now always returns an intent, never None."
```

---

### Task 3: Simplify async fast_router — Tier 2 becomes optional enhancement

**Files:**
- Modify: `backend/app/services/fast_router.py:700-790` (`fast_router` async function)

Tier 2 (Haiku) is no longer needed as a gatekeeper. Tier 1 always returns an intent. Haiku becomes an optional confidence booster — if Tier 1 returns "product" with low confidence and Haiku is available, Haiku can upgrade to a more specific intent. But if Haiku fails, Tier 1's answer stands. No more falling through to "general".

- [ ] **Step 1: Rewrite async fast_router**

```python
async def fast_router(
    query: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    last_search_context: Optional[Dict[str, Any]] = None,
) -> FastRouterResult:
    """
    Async entry point for the fast router.

    Tier 1 always produces an intent (default: product).
    Tier 2 (Haiku) is an optional refinement — if Tier 1 is uncertain
    and Haiku is available, Haiku can override. If Haiku fails,
    Tier 1's answer stands. No more "general" fallback trap.
    """
    # --- Tier 1: always produces an intent ---
    tier1_intent = _classify_tier1(query, conversation_history, last_search_context)
    tier1_slots = extract_slots(query)

    # Confidence heuristics (same as sync path)
    if tier1_intent == "intro":
        confidence = 0.99
    elif tier1_intent == "comparison":
        confidence = 0.95
    elif tier1_intent == "travel":
        confidence = 0.92 if "destination" in tier1_slots else 0.82
    elif tier1_intent == "general":
        confidence = 0.85
    elif tier1_intent in ("product", "service"):
        has_slot = "brand" in tier1_slots or "category" in tier1_slots
        confidence = 0.92 if has_slot else 0.80
    else:
        confidence = 0.75

    # If Tier 1 is confident, skip Haiku entirely
    if confidence >= 0.85:
        logger.debug("fast_router: Tier 1 confident (%s, %.2f) — skipping Tier 2", tier1_intent, confidence)
        return FastRouterResult(
            intent=tier1_intent,
            slots=tier1_slots,
            tool_chain=TOOL_CHAINS[tier1_intent],
            plan={"steps": PLAN_TEMPLATES[tier1_intent]},
            confidence=confidence,
            tier=1,
            needs_clarification=False,
        )

    # --- Tier 2: optional refinement for low-confidence Tier 1 ---
    logger.debug("fast_router: Tier 1 low-confidence (%s, %.2f) — trying Tier 2", tier1_intent, confidence)

    try:
        haiku_result = await _call_haiku(query, conversation_history)
    except Exception as exc:
        logger.error("fast_router: Tier 2 error: %s — using Tier 1 result", exc)
        haiku_result = None

    if haiku_result is not None:
        intent = haiku_result.get("intent", tier1_intent)
        haiku_slots = haiku_result.get("slots", {}) or {}
        merged_slots = {**haiku_slots, **tier1_slots}

        logger.info("fast_router: Tier 2 refined %s → %s", tier1_intent, intent)
        return FastRouterResult(
            intent=intent,
            slots=merged_slots,
            tool_chain=TOOL_CHAINS.get(intent, TOOL_CHAINS["product"]),
            plan={"steps": PLAN_TEMPLATES.get(intent, PLAN_TEMPLATES["product"])},
            confidence=0.80,
            tier=2,
            needs_clarification=False,
        )

    # Tier 2 failed — Tier 1 result stands (product, not general!)
    logger.info("fast_router: Tier 2 failed — using Tier 1 result (%s)", tier1_intent)
    return FastRouterResult(
        intent=tier1_intent,
        slots=tier1_slots,
        tool_chain=TOOL_CHAINS[tier1_intent],
        plan={"steps": PLAN_TEMPLATES[tier1_intent]},
        confidence=confidence,
        tier=1,
        needs_clarification=False,
    )
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/fast_router.py
git commit -m "refactor: Tier 2 Haiku becomes optional refinement, not gatekeeper

Tier 1 always produces an intent (default: product). Tier 2 only
fires when Tier 1 confidence is low. If Tier 2 fails, Tier 1 stands.
No more falling through to 'general' on Haiku failures."
```

---

### Task 4: Clean up dead code

**Files:**
- Modify: `backend/app/services/fast_router.py`

Remove `_PRODUCT_KEYWORDS` list (no longer used in classification — only `_has_keyword(q, _PRODUCT_KEYWORDS)` call remains in the general-intent guard, which is fine to keep). Remove the brand/category fallback we added to `_classify_tier1` earlier today (now redundant since we default to product). Remove the "unclear" tool chain and plan template.

- [ ] **Step 1: Remove "unclear" from TOOL_CHAINS and PLAN_TEMPLATES**

Delete the "unclear" entries:
```python
# Remove these lines:
    "unclear": [
        {"id": "step_1", "tools": ["unclear_compose"], "parallel": False},
    ],
```

Actually — keep "unclear" in the maps as an alias for "product" to avoid KeyError if any other code references it:
```python
    "unclear": [  # Legacy alias — routes to product
        {"id": "step_1", "tools": ["product_search"], "parallel": False},
        {"id": "step_2", "tools": ["product_normalize", "review_search"], "parallel": True},
        {"id": "step_3", "tools": ["product_affiliate"], "parallel": False},
        {"id": "step_4", "tools": ["product_compose"], "parallel": False},
        {"id": "step_5", "tools": ["next_step_suggestion"], "parallel": False},
    ],
```

Do the same for `PLAN_TEMPLATES["unclear"]` — make it a copy of the product template.

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/fast_router.py
git commit -m "refactor: 'unclear' routes to product search instead of unclear_compose

On a product review site, unclear queries should trigger product
search, not a clarification question. Users came here to buy."
```

---

### Task 5: Push and verify with live test

- [ ] **Step 1: Push to deploy**

```bash
git push origin main
```

- [ ] **Step 2: Wait for Railway deploy (~60s)**

- [ ] **Step 3: Test these queries on reviewguide.ai/chat**

| Query | Expected Intent | Why |
|-------|----------------|-----|
| "electric skateboards" | product | Default |
| "top picks for headphones" | product | Default (no travel/intro/general) |
| "I want something for my dog" | product | Default |
| "flights to bali" | travel | Travel keyword |
| "hi" | intro | Short greeting |
| "what is machine learning" | general | Knowledge question, no product signal |
| "what is the best air fryer" | product | "best" + "air fryer" category overrides general |
| "recommend me something nice" | product | Default |

- [ ] **Step 4: Check Railway logs for intent classification**

```bash
railway logs --filter "fast_router" --lines 20
```

Verify no queries are hitting "general" or "unclear" that should be "product".

---

## Summary

**Before:** Keywords → Haiku → general (3 failure points, any one kills the product search)
**After:** Is it travel? Is it intro? Is it general knowledge? No? → Product. (1 path, default is correct)

The keyword list becomes a bonus speed optimization, not a gatekeeper. The AI (Haiku) becomes a refinement tool, not a required checkpoint. And "unclear" routes to product search because on this site, the best guess is always "they want to buy something."
