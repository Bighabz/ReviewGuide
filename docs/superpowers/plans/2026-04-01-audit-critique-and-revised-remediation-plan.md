# ReviewGuide.ai QA Audit Critique and Revised Remediation Plan

Date: 2026-04-01  
Scope: Critique of the QA audit + resulting implementation plan, with a revised execution plan grounded in current source code.

## What the audit gets right

- It identifies user-facing failures that directly impact trust and monetization: missing Amazon links, hanging travel flow, and mismatched product details.
- It includes concrete repro prompts, not just vague complaints.
- It correctly prioritizes impact-heavy issues (affiliate links, travel hang, product correctness) over visual polish.
- It catches inconsistency patterns (different responses for similar queries), which usually indicate orchestration or guardrail gaps.

## Where the audit is weak

- It lacks reproducibility metadata (commit hash, environment vars, backend URL, model/provider config, exact timestamp, request IDs).
- It mixes hard failures with preference-level UX findings in one severity stream.
- It assumes one affiliate tag/URL format without validating configured runtime tag.
- It does not separate "pipeline data issue" from "rendering issue"; both can present as "missing links."
- It does not capture backend logs/tool coverage for failed runs, so root cause remains speculative.

## Critique of the current implementation plan

The current plan has good intent, but it is overly UI-checklist-driven and under-instrumented for backend pipeline issues.

- Strengths:
  - Includes mobile + desktop QA checks.
  - Emphasizes high-value paths (`/`, `/chat`, affiliate link correctness).
  - Has specific acceptance checks for product cards and citations.
- Gaps:
  - No "freeze + baseline" step to correlate behavior with commit SHA and env.
  - No explicit observability step (request IDs, tool-level timing, per-tool success map).
  - Suggests risky behavior changes before proving root cause.
  - Lacks automated regression tests for the exact failures reported.
  - No rollout strategy (canary/feature flag) for high-risk compose/router changes.

## Code-grounded findings that should reshape the plan

1. `product_compose.py` fallback loop has a control-flow bug:
   - In the blog fallback card loop, `if pname in seen_card_names ...: break` exits the loop entirely instead of skipping one item.
   - This can suppress expected fallback Amazon cards after the first already-seen item.

2. `product_compose.py` enforces multi-provider gating for review cards:
   - Current logic requires >=2 providers in offers for a card to be emitted.
   - If Amazon signals are sparse, users can end up with mostly eBay exposure.

3. `product_search.py` has no hard accessory/part exclusion:
   - Product generation prompt favors "always return products" but lacks strict anti-accessory constraints.
   - This aligns with observed "logic board"/replacement part leakage.

4. Budget constraints are weakly enforced end-to-end:
   - Budget is captured as text but not reliably enforced at affiliate ranking/filter stage.

5. Travel hang likely needs reliability + UX mitigation, not only routing:
   - Router appears default-to-product and travel-aware in `fast_router.py`.
   - Runtime "hung" behavior needs end-to-end tracing (tool timeout, retries, frontend timeout messaging) rather than router-only edits.

## Revised remediation plan (priority-ordered)

### Phase 0 - Reproducible baseline (must do first)

- Record: commit SHA, backend env snapshot (redacted), model/provider toggles, affiliate tag, and API base URL.
- Add a QA run template that logs:
  - prompt
  - session_id/request_id
  - intent
  - tools invoked
  - elapsed time to first token and done
- Freeze baseline evidence for 8 canonical prompts (same set as QA audit).

Exit criteria:
- Every test case has a linked request trace and deterministic environment metadata.

### Phase 1 - P0 correctness fixes (affiliate + data integrity)

1) Fix fallback loop termination bug in `backend/mcp_server/tools/product_compose.py`:
- Change fallback-loop duplicate guard from `break` to `continue`.
- Add unit test: duplicate-first-item scenario still emits fallback cards for later items.

2) Relax or tier multi-provider gating:
- If only one provider exists for a product, still render card with explicit availability state.
- Preserve ranking preference for products with Amazon links but do not suppress cards entirely.

3) Enforce merchant-label/link consistency:
- UI assertion: Amazon-labeled CTA must resolve to Amazon domain; eBay label must resolve to eBay domain.
- Add integration test for label-domain parity.

Exit criteria:
- Product query always returns at least one Amazon path when available (direct or search fallback).
- No label/domain mismatches in automated checks.

### Phase 2 - P0/P1 query quality guards (accessory + budget)

1) Add accessory/part suppression in search/normalize pipeline:
- Introduce denylist + contextual checks (e.g., replacement, filter, logic board, case, charger) unless user explicitly asks for accessories.
- Apply before ranking and before final compose emission.

2) Add budget enforcement:
- Parse user budget constraints into numeric bounds.
- Filter or penalize offers/products outside bounds before compose.
- If no in-budget results: render explicit "closest options" fallback message.

Exit criteria:
- "best laptops for students" excludes parts/accessories by default.
- "under $500" results do not include out-of-budget products without explicit fallback labeling.

### Phase 3 - Travel reliability and timeout UX

1) Instrument travel path:
- Capture per-tool start/end, timeout/failure flags, and emit to response metadata.
- Include request_id in user-visible error/recovery state.

2) Improve timeout handling:
- If upstream tools exceed thresholds, return partial travel response + recovery prompt instead of indefinite "Thinking."
- Frontend should surface retry/recoverable status before hard timeout.

Exit criteria:
- No travel query remains in undifferentiated loading state beyond threshold.
- Users get a partial response or actionable error with retry path.

### Phase 4 - Citations and status transparency

1) Ensure citation block always uses actual URL set from search results and validates URL format.
2) Ensure at least one non-generic status update appears during long operations (not only "Thinking...").
3) Add tests for:
- clickable source links
- minimum status update cadence
- done event completeness fields

Exit criteria:
- Product responses include clickable source links when sources exist.
- Streaming shows meaningful intermediate status updates.

### Phase 5 - Regression harness + release gate

- Convert QA audit prompts into automated smoke tests (API-level + minimal UI E2E).
- Gate deploy on:
  - affiliate label-domain parity
  - accessory suppression test
  - budget-bound test
  - travel non-hang test
  - source link presence test
- Run full checklist on mobile + desktop after passing automated gate.

Exit criteria:
- All P0/P1 tests green in CI before release candidate.

## Suggested execution order (short, practical)

1. Phase 0 baseline (half-day)  
2. Phase 1 affiliate/data-integrity fixes (half-day)  
3. Phase 2 accessory+budget guards (1 day)  
4. Phase 3 travel reliability (half to one day)  
5. Phase 4/5 transparency + regression gate (half-day)

## Definition of done

- No critical failures from the original audit remain reproducible under baseline test conditions.
- QA artifacts include traceability per test case (request_id + logs + screenshots where applicable).
- Automated tests cover every previously critical issue.
- Manual QA checklist passes on mobile and desktop.
