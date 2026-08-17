# Architecture Doctrine — decisions for Habib

Five milestone-scale calls surfaced by the 2026-07-31 two-round debug sweep.
None of these are bug fixes; each changes what the product IS or how it is built.
The plans (1-8) fix what can be fixed inside the current architecture — these are
the decisions that decide whether those fixes are the end state or a bridge.
Every evidence pointer below was verified against source.

---

## D1. Retrieval-first shortlist (the original sin)

**Today:** `product_search.py` asks an LLM to invent 5-8 product names from
parametric memory (temperature 0.7, no catalog, no existence check). Everything
downstream — fuzzy offer matching, the relevance gate, model-code dedup,
keep-≥2 verification, accessory filters — is compensation for names that may
not exist. The codebase admits it: "gpt-4o-mini's guessed product names reach
the composer and it writes confident prose about products that don't exist"
(`product_compose.py` comments), and the two grounding flags
(`USE_REVIEW_GROUNDING`, `USE_PRODUCT_VERIFICATION`) are **default-off**.

**The call:** invert the pipeline — query real shopping data first (the Google
Shopping array is already fetched and mostly discarded —
`app/services/serpapi/client.py:561-563`, `shopping_results` loop), cluster
offers into canonical products, and let the LLM rank/explain only retrieved
candidates. Products get evidence before they get prose.

**Cost/when:** the largest item here — a v4.0-milestone rebuild of the product
pipeline's front half. Everything in PLAN-1 remains worth shipping now; it
hardens the bridge, not the destination.

## D2. One typed envelope for composer output

**Today:** a composer field must be hand-copied through five layers (composer →
validator → `_extract_results` → node merge → SSE), any of which drops it
silently. Three shipped incidents, each patched at the layer it was caught.
`affiliate_products` is currently half-threaded (no schema, out-of-band lift) —
the next incident waiting.

**The call:** one `ComposeResult` Pydantic model as the single definition of
composer output, consumed at every layer. Estimated ~5 files, ~150 net lines
DELETED, plus one golden test asserting every emitted key reaches the SSE done
payload.

**Cost/when:** M — the rare refactor that removes code. Good candidate to ship
immediately after PLAN-8 (it touches the same files while they're warm).

## D3. Clarification state: versioned record + single reducer

**Today:** eleven implicit clarifier states encoded in branch order, five
`next_question` exits, a process-level halt cache with no TTL and no
compare-and-set, chip answers stripped of their slot IDs, and an LLM extractor
that can silently null a typed answer (the prod "budget guard" band-aid at
`clarifier_agent.py:1643-1653` proves it happened). PLAN-5 patches the loop;
it cannot make this reliable.

**The call:** a single durable `ClarificationState` record (revision,
question_ids, typed slots, status) with one reducer and compare-and-set writes;
chips submit `{question_id, slot, value}` instead of display prose;
deterministic assignment when one question is pending, LLM only for genuinely
ambiguous multi-slot parses. Sol's full sketch is in the archived round-2
report (`report_sol_r2.txt`, T3).

**Cost/when:** L — after PLAN-5 ships and its tests exist, so the redesign
lands against a pinned behavioural contract.

## D4. Cross-session personalization: own it or scope it out

**Today:** the "(like last time)" chip is a DESIGNED feature (Outcome 7,
`clarifier_agent.py:1471-1504`): preferences saved per-user after every search,
re-injected into future chats; "New Chat" deliberately keeps `user_id`
(`ChatContainer.tsx:809`). The QA audit read it as leakage. Both readings are
right: it is intentional AND undisclosed, unscoped, unresettable.

**The call:** either (a) keep it and make it legible — a one-line disclosure on
the chip, a "reset what I remember" affordance, category-scoped budgets — or
(b) scope preferences to the session and drop Outcome 7. This is a product
decision, not an engineering one. Until made, PLAN-5 T6 fixes only the
gibberish-topic-bleed half of the audit finding.

## D5. Fallback taxonomy: three axes, not one reflex

**Today:** "degraded beats empty" is applied uniformly. Verified consequences:
the $668-item-under-a-$500-budget is two compounding keep-all fallbacks working
as designed; a clarifier timeout silently skips clarification (the identical
fallback already caused QA Round 4's F6 regression — `stage_telemetry.py:51-55`
admits it — and it is still there); a hung safety stage routes content through
as "unchecked"; `completeness` is hardcoded "full" (PLAN-8 T4 fixes that one).

**The call:** adopt the three-axis rule —
- **Missing data** → degrade openly, label it (this part works today:
  `missing_sources` / provider coverage).
- **Violated stated constraint** → fail LOUD to the user ("everything I found
  is over $500"), never silently re-include (PLAN-1 T5 implements this for
  budget).
- **Failed protective gate** (safety hang, clarifier error) → fail closed:
  re-ask or block-and-retry, never proceed-as-is.

**Cost/when:** the budget and completeness pieces ship in PLAN-1/PLAN-8. The
clarifier-timeout and safety-timeout flips are S each — decide, then they're an
afternoon.
