# QA Remediation — Plan Index

**Source:** 10-conversation QA audit of Ask/Chat, 2026-07-31
**Status:** Guardrails SHIPPED (see below). Remaining plans written, not executed.

---

## Shipped 2026-07-31 — safety & honesty guardrails

All tests written first and watched fail. Backend **872 passed**, frontend
**349 passed**, zero regressions. Frontend typecheck: 41 pre-existing errors before
and after, none in touched files.

| Guardrail | Where | Tests |
|---|---|---|
| No invented review attributions; no claimed retrieval; English-only answers | `product_compose.py` `_SOURCING_HONESTY_SECTION` | `tests/test_guardrails.py` |
| No unverifiable safety attributes (nickel-free, left-handed, hypoallergenic); no silent substitution | `product_compose.py` `_SAFETY_ATTRIBUTE_SECTION` | `tests/test_guardrails.py` |
| Both applied at the call site, after the byte-pinned transforms | `product_compose.py` `_with_guardrails`, wired at `:1842` | `tests/test_guardrails.py` (incl. 2 integration tests proving the text reaches the model) |
| Medical query classified before slot-filling | `safety_agent.py` `detect_health_advisory` | `tests/test_health_advisory.py` |
| `health_advisory` threaded through all 4 graph layers | `safety_agent` → `workflow.safety_node` → `GraphState` → `chat.py` initial_state | `tests/test_health_advisory.py::TestGraphWiring` |
| Clarifier leads a medical query with a caveat | `clarifier_agent.py` `HEALTH_CAVEAT` / `apply_health_caveat`, applied in `workflow.clarifier_node` | `tests/test_health_advisory.py::TestHealthCaveat` |
| Homepage no longer promises receipts | `FrontPage.tsx` | `tests/honestCopy.test.ts` (mutation-verified) |
| Loading labels describe real stages | `lib/loadingCopy.ts` | `tests/honestCopy.test.ts` |
| Generative tools' status labels can't claim retrieval | `product_evidence.py` `citation_message` | `tests/test_guardrails.py` |

### Corrections the implementation forced

Three things in the plans below were wrong. They are wrong as written — read this
before executing PLAN-2 T3, PLAN-4 T2/T4, or PLAN-5 T5.

1. **`BLOG_ROLE` is not importable.** The plans treat it as a module constant in
   `product_compose.py`. It is a **function-local string literal** at
   `product_compose.py:1723` named `blog_role`. Guardrails therefore ship as
   module-level `_*_SECTION` constants appended via `_with_guardrails()` at the
   call site — the exact pattern `_RELEVANCE_GATE_SECTION` already uses. The
   byte-pin is preserved and `test_consolidated_role_in_sync_with_production`
   still passes.
2. **`next_question` is structured data, not a string.** PLAN-4 T4 says to prepend
   `HEALTH_CAVEAT` to it. It is `followups_data` — a dict of `{"intro", "questions"}`
   rendered as chips. Prepending a string would corrupt the frontend payload. The
   caveat prepends to the **`intro`** field via `apply_health_caveat()`.
3. **`ClarifierAgent.execute` has no single return.** PLAN-4 T4 says to apply the
   caveat at "the single outermost return". There are five (`clarifier_agent.py`
   :381, :859, :1018, :1096, :1137). It is applied instead in
   `workflow.clarifier_node`, the one place every clarifier result passes through.

`general_search`'s "Searching the web…" was checked and **left alone** — it does
real retrieval via `search_manager.search()`, so the label is honest.

---

**Original status:** Plans written, none executed
**Decision (Habib, 2026-07-31):** On the "receipts" gap — change the copy to match
reality and add an anti-fabrication guardrail. Do NOT build real retrieval yet.

---

## Debug sweep 2026-07-31 (route loop, 2 rounds, read-only — all verified)

Two workers (GPT-5.6 Sol, Kimi K3) swept the codebase; Fable cross-checked every
cited claim against source. Full reports archived in the session scratchpad.
Consequences folded into the plans below — **each revised plan carries a ⚠ banner
at the top; executors must read the banner before the task bodies.**

**Validation loop closed 2026-07-31:** three adversarial rounds (Sol: PLAN-1/3/8
+ doctrine backend; Kimi: PLAN-5/6/7/8-T4 + doctrine frontend). Final state:
**PLAN-6 and PLAN-8-T4 carry explicit worker APPROVE**; PLAN-1/3/5/7 and the
rest of PLAN-8 had every identified blocker folded in the last pass but were
not re-validated afterward — their ⚠ banners and "final-validation" callouts
are BINDING on executors. DOCTRINE approved by both validators in full.

New artifacts:
- **[PLAN-8 — workflow & state integrity](PLAN-8-workflow-state-integrity.md)** —
  four confirmed bugs no earlier plan covered: `conversation_history` doubles
  every turn (`operator.add` reducer + full-list return), resumed messages
  bypass moderation entirely, `product_evidence` runs in parallel with the step
  that produces its input (dead since inception), `completeness` hardcoded
  `"full"`.
- **[DOCTRINE.md](DOCTRINE.md)** — five milestone-scale decisions for Habib:
  retrieval-first shortlist, typed composer envelope, clarification-state
  redesign, cross-session personalization (own it or scope it out), fallback
  taxonomy.

Key reframe: the audit's "cross-conversation leakage" is a **designed feature**
(preference chips, Outcome 7) missing disclosure — PLAN-5 T6 retargeted; the
product call is DOCTRINE D4.

## Why seven plans and not one

The audit's findings land in seven subsystems that can be built, tested, and shipped
independently. Each plan below produces working software on its own, so they can be
executed in any order — or in parallel by different people — without merge conflicts
beyond the two shared files noted under "Collision points".

## Execution order (recommended)

Ordered by user-visible harm per hour of work, not by audit severity.

| # | Plan | Fixes | Est. |
|---|------|-------|------|
| 4 | [Safety guardrails](PLAN-4-safety-guardrails.md) | Fabricated safety attributes, medical guardrail fires too late | S |
| 2 | [Honest sourcing copy](PLAN-2-honest-sourcing-copy.md) | "Receipts" claim, invented user-review citations | S |
| 7 | [Frontend defects](PLAN-7-frontend-defects.md) | History drawer, Regenerate, disclosure, comparison table | M |
| 3 | [Pros/cons quality](PLAN-3-proscons-content-quality.md) | Raw forum snippets as pros, cons always empty | M |
| 6 | [Stream reliability](PLAN-6-stream-reliability.md) | 5-min hang, error attributed to wrong message, truncation | M |
| 5 | [Clarifier & router](PLAN-5-clarifier-and-router.md) | Slot answers discarded, follow-ups become new searches | L |
| 1 | [Price/product resolution](PLAN-1-price-product-resolution.md) | Accessories as products, 3× price swings, renewed as headline | L |
| **8** | [Workflow & state integrity](PLAN-8-workflow-state-integrity.md) | History doubling, unmoderated resume, dead evidence step, dishonest completeness | M |
| **9** | [Strain misroute](PLAN-9-strain-misroute.md) | Prod incident 2026-07-21: fitness-tracker question answered with cannabis strains (GG4). Traced end-to-end via Langfuse; three stacked failures, incl. a fallback overriding an LLM refusal (D5 exhibit) | S |

Plan 1 is the audit's #1 priority and stays last among the originals only because
it is the largest and the least self-contained. **Plan 8 slots in right after
Plan 4** — its Task 1 (history doubling) and Task 2 (moderation bypass) are
cheap, verified, and touch every conversation. If only one plan ships this week,
ship Plan 4; if two, add Plan 8.

## Collision points & required sequencing (validated 2026-07-31)

- `backend/mcp_server/tools/product_compose.py` — Plans 1, 2✓(shipped), 3.
  **Serialize Plan 1 and Plan 3** — both rework its card/offer paths.
- `frontend/components/Message.tsx` — Plans 5, 7. Sequence them.
- **Plan 3 v2 MUST land before Plan 8 Task 3** — Plan 8 removes
  `product_evidence` from every template and retires its consumers
  (`product_normalize`, `product_ranking`); Plan 3 provides the replacement
  pros/cons source first.
- Plan 8 Tasks 1, 2, 4 are independent of everything else and can ship first.
- Plan 3 v2 no longer touches `tool_validator`/`plan_executor`/`workflow`/`chat`
  (v1's citation-wiring task was deleted on validation) — the v1 collision with
  Plan 8 is gone.

---

## Coverage map — every audit finding has a home

### Critical

| Finding | Plan | Task |
|---|---|---|
| Fabricated nickel-free / left-handed claims | 4 | T2, T3 |
| "Receipts" marketing vs. no citations | 2 | T1, T2 |
| Invented "two users specifically mentioned" | 2 | T3 |
| Same query → $668 then $209.99 | 1 | T4 |
| Accessory returned as the product ($15.98 vacuum) | 1 | T2 |
| Renewed listing as headline price | 1 | T3 |
| Budget filter not held ($668 for $500) | 1 | T5 |
| Raw forum text in THE GOOD / THE CATCH | 3 | T1, T2 |
| Wrong-polarity snippet under THE GOOD | 3 | T2 |

### High

| Finding | Plan | Task |
|---|---|---|
| Free-text slot answers discarded (Manchester ×3) | 5 | T1, T2 |
| "Or type your own answer" has no input | 5 | T2 |
| Follow-ups misrouted to new clarifier widget | 5 | T3 |
| Budget re-asked after being given | 5 | T4 |
| Answer truncated mid-sentence | 6 | T4 |
| Product substituted across turns (cordless → corded) | 5 | T5 |
| 5-minute hang, no timeout surfaced | 6 | T1 |
| Error attributed to the wrong message | 6 | T2 |
| Regenerate button does nothing | 7 | T2 |
| History drawer never opens | 7 | T1 |

### Medium

| Finding | Plan | Task |
|---|---|---|
| Cross-conversation context leakage | 5 + D4 | T6 (topic bleed) / DOCTRINE D4 (preference chip — designed, needs product call) |
| Constraint changes ignored (budget↓, Apple allowed) | 5 | T4 |
| Narrative disagrees with comparison table | 3 | T4 |
| Comparison table: No Image, N/A, overflow | 7 | T4 |
| Localisation absent + self-contradicting refusal | 2 | T4 |
| Unsupported health claims (Spanish) | 4 | T2 |
| Travel ignores "two kids under 8" / auto-invents dates | 5 | T7 |
| Stale widgets stay interactive | 7 | T5 |
| Output format inconsistent (prose-only, no cards) | 3 | T5 |

### Low

| Finding | Plan | Task |
|---|---|---|
| Typing before focus drops text | 7 | T6 |
| Text clipped behind composer | 7 | T7 |
| "01" reads as "0l" | 7 | T8 |
| No affiliate disclosure | 7 | T3 |

### Sweep-discovered (not in the original audit)

| Finding | Plan | Task |
|---|---|---|
| conversation_history doubles every turn | 8 | T1 |
| Resumed messages bypass moderation | 8 | T2 |
| product_evidence dead-parallel with its producer | 8 | T3 |
| completeness hardcoded "full" | 8 | T4 |
| Accessory filter self-disables on "cordless" queries | 1 | T2 (revised) |
| Renewed-price laundering via backfill | 1 | T3 (revised) |
| Zombie fetch: read loop unbounded after headers | 6 | T1 (revised) |
| done-without-session_id swallowed | 6 | T4 (revised) |

### Confirmed working — protect with regression tests

Whitespace rejection, gibberish/emoji handling, multi-select chips, within-conversation
memory, prompt-injection resistance, and the final-answer medical pushback all behaved
correctly. Plan 4 T4 pins the medical pushback and the injection resistance so the
upstream guardrail work cannot regress them.

---

## Corrections to the audit

Two of the audit's stated causes are wrong. The plans fix the real ones.

**"Add a request timeout with a real error state."** The backend already enforces a
60-second hard cap — `backend/app/api/v1/chat.py:459` computes a deadline from
`MAX_TOTAL_REQUEST_S`, checks it every loop iteration, and emits a `request_timeout`
error at `chat.py:573`. The 5-minute spinner is the frontend never clearing pending
state and attributing the resulting error to the newest message. Fixing the backend
timeout would have changed nothing. See Plan 6 T1/T2.

**"Fix the history drawer's display toggle."** `display: none` is a symptom. The cause
is `frontend/components/NavLayout.tsx:42` — `handleHistory` calls `router.push('/chat')`
and never toggles `ConversationSidebar`. There is no shared open-state between the
topbar button and the drawer. See Plan 7 T1.
