# Clarifier & Follow-up Router Implementation Plan

> **⚠ Task 5 SHIPPED 2026-07-31** as part of `_SAFETY_ATTRIBUTE_SECTION` in
> `product_compose.py` (not `SAFETY_ATTRIBUTE_RULE` — see INDEX.md "Corrections").
> Tasks 1-4, 6, 7 remain. Tests: `tests/test_guardrails.py`.
>
> **⚠ REVISED 2026-07-31 after the round-2 debug sweep (verified findings):**
>
> - **Task 6 is RETARGETED — the "$300-$400 (like last time)" chip is a designed
>   feature, not a leak.** Outcome 7 (`clarifier_agent.py:1471-1504`) deliberately
>   injects cross-session `user_preferences` (saved by product_compose after every
>   search) into the next chat's clarifier options, and "New Chat" deliberately
>   keeps `user_id` (`ChatContainer.tsx:809`: "DO NOT remove 'chat_user_id'").
>   The only guard is option-membership, which free-text budgets always pass.
>   Clearing conversation context (Task 6 as written) would NOT remove this.
>   **The fix is a product decision for Habib** — keep personalization with
>   visible disclosure + a reset affordance, or scope it out. DOCTRINE.md D4.
>   The second half of the audit's leakage finding (gibberish answered with the
>   prior chat's topic) is separate and still Task 6's to fix: the empty-state /
>   suggestion personalization path carries prior-chat interest keywords.
> - **Task 1 — a band-aid already exists; extend it, don't duplicate it.** The
>   "budget guard" (`clarifier_agent.py:1643-1653`) overrides the LLM extractor's
>   budget with the literal answer phrase when the extractor "lost the shape" —
>   proof the typed-answer-loss was observed in prod. Generalize this pattern
>   (deterministic assignment when exactly ONE question is pending) instead of
>   adding a parallel capture function; `capture_freetext_answer`'s tests stand.
> - **Task 1 context — the OTHER way "Manchester, UK" dies:** stale halt-state
>   snapshots. `HaltStateManager._cache` is a process-level dict with no TTL and
>   no revision check; on multi-worker deploys a stale worker resumes the
>   pre-answer question. In-scope fix: `force_reload` on resume reads. The full
>   compare-and-set redesign is DOCTRINE.md D3, not this plan.
> - **Task 4's extractor-null path is confirmed as the re-ask mechanism:** one
>   LLM null (or exception → all-null at `:1659-1661`) sends the slot to
>   `still_missing_required` and regenerates the same question. Deterministic
>   single-slot assignment (Task 1) is the fix; Task 4's merge tests stand.
>
> **Validation corrections (Kimi, 2026-07-31) — binding on executors:**
> - **T1 call site:** `execute()` short-circuits to `_handle_user_answer` when
>   followups exist (`:373-379`), so `capture_freetext_answer` goes in
>   `_handle_user_answer` (`:904`), AFTER the `_is_skip_all` check at `:940` —
>   not "at the top of execute" as v1 said.
> - **T1×T3 composition rule:** the two rules compose badly on question-shaped
>   answers ("What about Manchester?"). Order is mandatory: when a halt is
>   pending and exactly ONE slot is open, deterministic capture runs FIRST and
>   a message that plausibly fills the open slot is NEVER rerouted by T3 —
>   otherwise T1 declines (ends in "?"), T3 reroutes to intent and deletes the
>   halt, and the answer is lost with the halt gone. T3 fires only when capture
>   declined AND the message back-references the previous ANSWER, not the
>   pending question.
> - **T3 precondition:** `is_followup_question` returns False when
>   `last_search_context` is empty — and halt saves don't reliably include it.
>   Require halt-state writes to carry `last_search_context`, or fall back to
>   `slots`/`conversation_history` as context, or the fix no-ops on exactly the
>   clarification-halt path it targets.
> - **T4 budget capture gating:** `_BUDGET_RE` would match prices inside
>   follow-up QUESTIONS ("does the $300-$400 model…?") and silently overwrite
>   `slots.budget`. Only REPLACE an existing budget when the message carries a
>   budget verb ("dropped to", "budget is", "under") — bare price mentions
>   never overwrite.
> - Anchors: budget guard opens at `:1641` (not :1643); followups slot-key
>   evidence is `workflow.py:244` (not :236); `initial_state` is `chat.py:335`
>   (not ~243); session minting lives in `app/chat/page.tsx:97-103,147-160`,
>   not ChatContainer/chatApi.

> **For agentic workers:** Use superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop discarding typed answers, stop turning follow-up questions into fresh
clarifier widgets, stop re-asking for information the user already gave, and stop leaking
one conversation's context into the next.

**Architecture:** Slots are filled by `ClarifierAgent` and persisted to Redis by
`HaltStateManager`. On the next turn `safety_node` (`workflow.py:84-105`) restores
`intent`, `slots`, and `plan` from the halt state and routes straight back to the
clarifier. The failures cluster in two places: free-text messages are not parsed into the
slot the clarifier is waiting on, and any message arriving while a halt state exists is
treated as a slot answer or a new search rather than as a question about the last answer.

**Tech Stack:** Python 3.11, pytest, Redis; React/TypeScript for the chip card.

## Global Constraints

- **"Just show me the best overall" and "Ask me a few more questions" are backend
  contracts.** `frontend/components/Message.tsx:297-299` documents that `_is_skip_all` and
  `_is_ask_more` in `clarifier_agent.py` match these exact strings. Never reword either
  side independently.
- Results-first: never ask a question you can answer from what the user already said. A
  lost user is a lost sale.
- Adding a `GraphState` field requires a default in the `initial_state` dict in
  `backend/app/api/v1/chat.py` (~line 243), or LangGraph channels crash.
- `frontend/components/Message.tsx` is also touched by PLAN-7. Sequence them.
- Tests: `cd backend && python -m pytest tests/<file> -v`;
  `cd frontend && npx vitest run <file>`

## File Structure

- Modify: `backend/app/agents/clarifier_agent.py` — slot capture, re-ask suppression
- Modify: `backend/app/services/langgraph/workflow.py` — follow-up routing
- Modify: `frontend/components/Message.tsx` — free-text input on the chip card
- Create: `backend/tests/test_clarifier_freetext.py`
- Create: `backend/tests/test_followup_routing.py`
- Create: `frontend/tests/clarifierFreeText.test.tsx`

Existing clarifier tests — read before starting, and keep all of them green:
`test_clarifier_answer_aware.py`, `test_clarifier_ask_more.py`,
`test_clarifier_expert_questions.py`, `test_clarifier_preference_chips.py`.

---

### Task 1: Typed answers must fill the slot being asked

**Root cause:** the audit was asked for a departure city three times after answering
"Manchester, UK" twice. When the clarifier halts on slot `departure_city` and the next
user message is free text, nothing maps that text onto the open slot — the message is
re-classified from scratch and the same question is regenerated.

**Files:**
- Modify: `backend/app/agents/clarifier_agent.py`
- Create: `backend/tests/test_clarifier_freetext.py`

**Interfaces:**
- Produces: `capture_freetext_answer(message: str, open_slot: str, followups: list) -> Optional[str]`
  — the value to write into `slots[open_slot]`, or `None` when the message is not an
  answer.

- [ ] **Step 1: Locate the real halt/slot plumbing**

```bash
cd backend && grep -n "def \|_is_skip_all\|_is_ask_more\|followups\|next_question" app/agents/clarifier_agent.py | head -40
```

Record the function that decides the next question and the shape of a `followups` entry
(`workflow.py:236` shows each has a `"slot"` key). Use the real names below.

- [ ] **Step 2: Write the failing test**

```python
"""Free-text answers must fill the slot the clarifier is waiting on.

Audit: asked for a departure city three times after being told "Manchester, UK"
twice. The typed answer was never mapped onto the open slot.
"""
import pytest

from app.agents.clarifier_agent import capture_freetext_answer

FOLLOWUPS = [{"slot": "departure_city", "question": "Which city are you flying from?"}]


@pytest.mark.parametrize("message,expected", [
    ("Manchester, UK", "Manchester, UK"),
    ("manchester uk", "manchester uk"),
    ("I'm flying from Manchester", "Manchester"),
    ("From Manchester, UK", "Manchester, UK"),
    ("Manchester", "Manchester"),
])
def test_captures_a_typed_city_answer(message, expected):
    assert capture_freetext_answer(message, "departure_city", FOLLOWUPS) == expected


@pytest.mark.parametrize("message", [
    "Just show me the best overall",
    "Ask me a few more questions",
])
def test_control_phrases_are_not_slot_answers(message):
    # These are backend contracts handled by _is_skip_all / _is_ask_more.
    assert capture_freetext_answer(message, "departure_city", FOLLOWUPS) is None


def test_a_question_is_not_a_slot_answer():
    assert capture_freetext_answer(
        "which reviews support your pick?", "departure_city", FOLLOWUPS) is None


def test_empty_message_is_not_an_answer():
    assert capture_freetext_answer("   ", "departure_city", FOLLOWUPS) is None
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_clarifier_freetext.py -v`
Expected: FAIL — `ImportError: cannot import name 'capture_freetext_answer'`.

- [ ] **Step 4: Implement**

```python
import re
from typing import Optional

# Lead-ins users type before the answer itself. Stripped so "I'm flying from
# Manchester" fills the slot with "Manchester", not the whole sentence.
_ANSWER_LEADIN_RE = re.compile(
    r"^\s*(?:i'?m\s+)?(?:flying\s+|departing\s+|travelling\s+|traveling\s+|leaving\s+)?"
    r"(?:from|out of|in|it'?s|its|that'?s)\s+",
    re.IGNORECASE,
)


def capture_freetext_answer(
    message: str, open_slot: str, followups: list
) -> Optional[str]:
    """Map a free-text message onto the slot the clarifier is waiting on.

    Returns the value to store, or None when the message is not an answer —
    a control phrase, a question, or empty. Without this the clarifier
    re-classifies every typed reply from scratch and re-asks the same question,
    which is what the audit hit three times in a row.
    """
    if not message or not message.strip() or not open_slot:
        return None

    text = message.strip()

    # Control phrases are contracts handled elsewhere (_is_skip_all / _is_ask_more).
    if _is_skip_all(text) or _is_ask_more(text):
        return None

    # A question is a follow-up, not a slot answer. Routed by Task 3.
    if text.endswith("?"):
        return None

    # Only capture when this slot is genuinely open.
    open_slots = {f.get("slot") for f in followups if isinstance(f, dict)}
    if open_slot not in open_slots:
        return None

    stripped = _ANSWER_LEADIN_RE.sub("", text).strip()
    return stripped or text
```

Then call it at the top of the clarifier's execute path, before question generation:

```python
        open_slot = next(
            (f.get("slot") for f in state.get("followups", []) if isinstance(f, dict)),
            None,
        )
        if open_slot:
            captured = capture_freetext_answer(state.get("user_message", ""), open_slot,
                                               state.get("followups", []))
            if captured:
                slots[open_slot] = captured
                logger.info(f"[Clarifier] Captured free-text answer for '{open_slot}': {captured!r}")
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_clarifier_freetext.py -v`
Expected: all PASS.

- [ ] **Step 6: Keep the existing clarifier suite green**

Run: `cd backend && python -m pytest tests/ -k clarifier -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/agents/clarifier_agent.py backend/tests/test_clarifier_freetext.py
git commit -m "fix(clarifier): map typed answers onto the open slot instead of re-asking"
```

---

### Task 2: Give "type your own answer" a real input (v2 — real submission path)

> **Reworked after adversarial validation (Kimi).** v1's test assumed an
> `onSubmit` prop on `Message` and a `ui_blocks: [{type: 'clarifier'}]` fixture.
> Neither exists: `MessageProps` is `{ message, isLast? }` (`Message.tsx:341-344`),
> the clarifier card renders from **`message.followups`** (`{intro, questions,
> closing}`, `:593-597`) via the `ClarifierCard` component (`:166-330`), and
> submission goes through `window.dispatchEvent(new CustomEvent('sendSuggestion',
> {detail: {question: text}}))` (`:598-600`).

**Root cause:** the card's "or type your own answer" hint (`resolvedHint`,
`Message.tsx:188`) has no input control. The only escape is the skip link.

**Files:**
- Modify: `frontend/components/Message.tsx` — inside `ClarifierCard`
- Create: `frontend/tests/clarifierFreeText.test.tsx`

**Interfaces:**
- Consumes: `ClarifierCard`'s existing `onSubmit(text: string)` internal prop
  (the one the chips call), which `Message` wires to the `sendSuggestion`
  CustomEvent at `:598-600`.

- [ ] **Step 1: Copy the existing test harness**

The Message clarifier tests need ~10 module mocks (framer-motion,
react-markdown, BlockRegistry, MessageRecoveryUI, trackAffiliate, lucide-react —
see `tests/clarifierChips.test.tsx:19-55`). Start `clarifierFreeText.test.tsx`
by copying that file's mock block and its `makeClarifierMessage` fixture
(followups shape, NOT ui_blocks).

- [ ] **Step 2: Write the failing test — assert the CustomEvent**

```tsx
// After the clarifierChips.test.tsx mock block + fixture:
describe('clarifier free-text answer', () => {
  it('submits a typed answer through the sendSuggestion event', () => {
    const heard: string[] = []
    const listener = (e: Event) =>
      heard.push((e as CustomEvent).detail.question)
    window.addEventListener('sendSuggestion', listener)

    render(<Message message={makeClarifierMessage()} {...({} as any)} />)
    fireEvent.change(screen.getByTestId('clarifier-freetext-input'),
                     { target: { value: 'Manchester, UK' } })
    fireEvent.submit(screen.getByTestId('clarifier-freetext-form'))

    expect(heard).toEqual(['Manchester, UK'])
    window.removeEventListener('sendSuggestion', listener)
  })

  it('does not submit an empty or whitespace answer', () => {
    const heard: string[] = []
    const listener = (e: Event) => heard.push((e as CustomEvent).detail.question)
    window.addEventListener('sendSuggestion', listener)

    render(<Message message={makeClarifierMessage()} {...({} as any)} />)
    fireEvent.change(screen.getByTestId('clarifier-freetext-input'),
                     { target: { value: '   ' } })
    fireEvent.submit(screen.getByTestId('clarifier-freetext-form'))

    expect(heard).toEqual([])
    window.removeEventListener('sendSuggestion', listener)
  })
})
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/clarifierFreeText.test.tsx`
Expected: FAIL — `clarifier-freetext-input` not found.

- [ ] **Step 4: Add the input inside ClarifierCard**

Inside `ClarifierCard`, above the footer affordances block (`Message.tsx:300`),
gated on `!submitted` exactly like the footer, calling the card's existing
`onSubmit` prop (the same one the chips use — Message routes it to the
`sendSuggestion` event):

```tsx
{!submitted && (
  <form
    data-testid="clarifier-freetext-form"
    className="mt-3 flex items-center gap-2"
    onSubmit={(e) => {
      e.preventDefault()
      const value = freeText.trim()
      if (!value) return
      setSubmitted(true)
      onSubmit(value)
    }}
  >
    <input
      data-testid="clarifier-freetext-input"
      value={freeText}
      onChange={(e) => setFreeText(e.target.value)}
      placeholder="Or type your own answer"
      className="flex-1 min-h-[40px] rounded-[12px] border border-[var(--line)] bg-transparent px-3 text-[14px] text-[var(--ink)] placeholder:text-[var(--ink-3)] focus:border-[var(--terra)] focus:outline-none"
    />
    <button
      type="submit"
      className="inline-flex min-h-[40px] items-center rounded-[12px] border border-[var(--terra)] px-3 text-[13px] font-medium text-[var(--terra)] hover:bg-[var(--terra)] hover:text-white transition-colors"
    >
      Send
    </button>
  </form>
)}
```

Declare the state beside the card's other `useState` calls:

```tsx
const [freeText, setFreeText] = useState('')
```

Remove any now-duplicated "or type your own answer" static hint text.

- [ ] **Step 5: Run to verify it passes**

Run: `cd frontend && npx vitest run tests/clarifierFreeText.test.tsx`
Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/Message.tsx frontend/tests/clarifierFreeText.test.tsx
git commit -m "fix(ui): clarifier card accepts a typed answer"
```

---

### Task 3: Route follow-up questions to an answer, not a new widget

**Root cause:** "what CADR and filter type should I look for, and does the GermGuardian
meet it?" produced another budget/brand questionnaire. Same for "which reviews support
your pick?" A message arriving while a halt state exists is treated as a slot answer or a
fresh search; it is never recognised as a question *about the previous answer*.

**Files:**
- Modify: `backend/app/services/langgraph/workflow.py`
- Create: `backend/tests/test_followup_routing.py`

**Interfaces:**
- Produces: `is_followup_question(message: str, last_search_context: dict) -> bool` in
  `backend/app/agents/clarifier_agent.py`; consumed by `safety_node`'s resume branch at
  `workflow.py:84-105`.

- [ ] **Step 1: Write the failing test**

```python
"""Questions about the previous answer must be answered, not re-clarified."""
import pytest

from app.agents.clarifier_agent import is_followup_question

CONTEXT = {"category": "air purifier",
           "product_names": ["GermGuardian AC4825", "Levoit Core 300"]}


@pytest.mark.parametrize("message", [
    "what CADR and filter type should I look for, and does the GermGuardian meet it?",
    "which reviews support your pick?",
    "where did you get the Emma claim?",
    "why did you pick that one over the Levoit?",
    "is the GermGuardian quiet enough for a bedroom?",
])
def test_recognises_follow_up_questions(message):
    assert is_followup_question(message, CONTEXT) is True


@pytest.mark.parametrize("message", [
    "best espresso machine under $500",
    "cordless vacuum for pet hair",
    "Manchester, UK",
    "under $300",
])
def test_new_searches_and_slot_answers_are_not_follow_ups(message):
    assert is_followup_question(message, CONTEXT) is False


def test_no_prior_context_means_no_follow_up():
    assert is_followup_question("which reviews support your pick?", {}) is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_followup_routing.py -v`
Expected: FAIL — `ImportError: cannot import name 'is_followup_question'`.

- [ ] **Step 3: Implement**

```python
# Interrogatives that refer back to an answer already given rather than starting a
# new search. Requires prior context — with no previous answer there is nothing to
# follow up on.
_FOLLOWUP_LEAD_RE = re.compile(
    r"^\s*(?:what|which|why|how|where|when|who|is|are|does|do|did|can|could|would|should)\b",
    re.IGNORECASE,
)
# References that only make sense against a previous answer.
_BACKREF_RE = re.compile(
    r"\b(?:your|you)\b|\bthat one\b|\bthe pick\b|\byour pick\b|\bover the\b|"
    r"\binstead of\b|\bthese\b|\bthose\b|\bit\b",
    re.IGNORECASE,
)


def is_followup_question(message: str, last_search_context: dict) -> bool:
    """True when the message asks about the previous answer.

    Such a message must be answered directly. Re-running clarification on it is
    the most visible frustration in the audit: asking "which reviews support your
    pick?" and getting a budget questionnaire back.
    """
    if not message or not last_search_context:
        return False
    text = message.strip()
    if not text.endswith("?") and not _FOLLOWUP_LEAD_RE.match(text):
        return False

    lowered = text.lower()
    # A named product or category from the previous turn is a strong back-reference.
    known = [str(last_search_context.get("category") or "")]
    known += [str(n) for n in (last_search_context.get("product_names") or [])]
    mentions_known = any(k and k.lower() in lowered for k in known)

    return bool(_FOLLOWUP_LEAD_RE.match(text)) and (
        mentions_known or bool(_BACKREF_RE.search(text))
    )
```

Then, in `safety_node`'s resume branch (`workflow.py:84-105`), skip the clarifier when
the message is a follow-up. Replace the `resume_update` construction so it routes to the
executor with the restored slots instead of back to the clarifier:

```python
                            from app.agents.clarifier_agent import is_followup_question

                            if is_followup_question(
                                state.get("user_message", ""),
                                state.get("last_search_context", {}),
                            ):
                                logger.info("  ✓ Follow-up question — answering, not re-clarifying")
                                resume_update["next_agent"] = "intent"
                                resume_update["followups"] = []
                                await HaltStateManager.delete_halt_state(session_id)
```

Clearing `followups` and the halt state is what stops the clarifier re-triggering on the
next turn.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_followup_routing.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/clarifier_agent.py backend/app/services/langgraph/workflow.py \
        backend/tests/test_followup_routing.py
git commit -m "fix(router): answer follow-up questions instead of re-clarifying"
```

---

### Task 4: Never re-ask a slot the user already filled; honour changes

**Root cause:** the budget was given in the opening message ($400) and asked for again
two turns later. Separately, "budget dropped to $700 and Apple is now allowed" produced
the same ASUS pick, no Apple products, and no acknowledgement.

**Files:**
- Modify: `backend/app/agents/clarifier_agent.py`
- Create: `backend/tests/test_slot_persistence.py`

**Interfaces:**
- Produces: `merge_constraint_updates(message: str, slots: dict) -> dict` — returns slots
  with any restated or changed constraints applied.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from app.agents.clarifier_agent import merge_constraint_updates


def test_budget_from_the_opening_message_is_captured():
    slots = merge_constraint_updates("cordless vacuum for pet hair under $400", {})
    assert slots.get("budget") == "under $400"


def test_a_lowered_budget_replaces_the_old_one():
    slots = merge_constraint_updates("budget dropped to $700", {"budget": "under $1200"})
    assert "700" in slots["budget"]
    assert "1200" not in slots["budget"]


def test_removing_a_brand_exclusion_clears_it():
    slots = merge_constraint_updates("Apple is now allowed",
                                     {"excluded_brands": ["Apple"]})
    assert "Apple" not in slots.get("excluded_brands", [])


def test_unrelated_message_leaves_slots_untouched():
    before = {"budget": "under $400", "category": "vacuum"}
    assert merge_constraint_updates("which one is quietest?", dict(before)) == before
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_slot_persistence.py -v`
Expected: FAIL — `ImportError: cannot import name 'merge_constraint_updates'`.

- [ ] **Step 3: Implement**

Reuse the existing budget parser rather than writing a second one:

```bash
cd backend && grep -rn "def _parse_budget" mcp_server/tools/product_compose.py
```

```python
_BUDGET_RE = re.compile(
    r"(?:under|below|less than|up to|max(?:imum)?|budget (?:is|of|dropped to)?)\s*"
    r"\$?\s*(\d[\d,]*)|(\$\s?\d[\d,]*\s*(?:-|to)\s*\$?\s?\d[\d,]*)",
    re.IGNORECASE,
)
_BRAND_ALLOW_RE = re.compile(
    r"\b([A-Z][\w'&-]+)\b[^.?!]{0,20}\bis (?:now )?(?:allowed|fine|ok|okay|back on)\b",
    re.IGNORECASE,
)


def merge_constraint_updates(message: str, slots: dict) -> dict:
    """Apply constraints restated or changed in this message to the slot dict.

    Two audit failures share this root: a budget given in the opening message was
    asked for again two turns later, and "budget dropped to $700 and Apple is now
    allowed" changed nothing. A constraint the user has stated must never be
    re-asked, and a changed one must win over the stored value.
    """
    if not message:
        return slots
    updated = dict(slots)

    m = _BUDGET_RE.search(message)
    if m:
        updated["budget"] = (m.group(0) or "").strip()

    allow = _BRAND_ALLOW_RE.search(message)
    if allow:
        brand = allow.group(1)
        excluded = [b for b in updated.get("excluded_brands", [])
                    if b.lower() != brand.lower()]
        updated["excluded_brands"] = excluded

    return updated
```

Call it before the clarifier decides what is missing, so a slot filled here is never
asked about. Then confirm the clarifier treats a filled slot as satisfied:

```bash
cd backend && grep -n "missing\|required_slots\|followups" app/agents/clarifier_agent.py | head -20
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_slot_persistence.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/clarifier_agent.py backend/tests/test_slot_persistence.py
git commit -m "fix(clarifier): capture stated constraints and honour changes to them"
```

---

### Task 5: Do not silently substitute a different product

**Root cause:** asked to finish a Shark Rocket (cordless stick) recommendation, the
assistant recommended the Shark Navigator Lift-Away — a corded upright — with no
acknowledgement, against an explicit cordless requirement.

**Files:**
- Modify: `backend/mcp_server/tools/product_compose.py` — extend the PLAN-4
  `SAFETY_ATTRIBUTE_RULE` mechanism with a substitution clause
- Create: `backend/tests/test_no_silent_substitution.py`

**Interfaces:**
- Consumes: `SAFETY_ATTRIBUTE_RULE`, `_with_safety_rule` (PLAN-4 Task 2)

- [ ] **Step 1: Write the failing test**

```python
from mcp_server.tools.product_compose import SAFETY_ATTRIBUTE_RULE


@pytest.mark.parametrize("phrase", ["substitut", "acknowledge", "different product"])
def test_rule_forbids_silent_substitution(phrase):
    assert phrase in SAFETY_ATTRIBUTE_RULE.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_no_silent_substitution.py -v`
Expected: FAIL.

- [ ] **Step 3: Extend the rule**

Append inside `SAFETY_ATTRIBUTE_RULE` before the closing `"""`:

```
SUBSTITUTION:
- If you recommend a different product from the one under discussion, say so explicitly
  and give the reason in the same sentence.
- Never substitute a product that violates a stated requirement. A corded upright is not
  an answer to a cordless request, and swapping one in without acknowledgement makes the
  whole recommendation untrustworthy.
- If nothing in the shortlist meets a hard requirement, say that plainly rather than
  presenting the closest miss as if it qualified.
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_no_silent_substitution.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/mcp_server/tools/product_compose.py backend/tests/test_no_silent_substitution.py
git commit -m "fix(compose): forbid silent product substitution across turns"
```

---

### Task 6: New Chat topic-bleed — the carriers are client-side (v2)

> **Reworked after adversarial validation (Kimi), which traced the real path.**
> v1 targeted a backend helper (`build_initial_state` / `is_new_chat`) that
> does not exist, to clear state that is already clean: New Chat mints a fresh
> UUID (`app/chat/page.tsx:97-103`, `:147-160`; `ChatContainer.tsx:432-437`),
> and a fresh session loads no halt state and no history (`chat.py:261`).
> Server-side isolation already holds.

**Verified root cause of "gibberish answered with headphones":** the empty-state
starter is biased by `readUserSignal()` (`frontend/lib/chatStarters.ts:85-101`),
which reads THREE localStorage keys that New Chat never clears:
- `reviewguide_recent_searches` (`recentSearches.ts:3`)
- `saved_items` (`savedItems.ts:19`)
- `rg_pref_summary` (`userPreferences.ts:11-23`) — rewritten on **every done
  event** (`chatApi.ts:379` `cachePreferenceSummary(chunk.preference_summary)`)

The signal feeds `pickStarter` keyword matching (`chatStarters.ts:69-82` —
`'headphone'` is literally a match keyword at `:38`). New Chat clears only
`chat_session_id` + messages (`ChatContainer.tsx:806-809`).

**Scope note:** saved items and recent searches are user-visible features —
clearing them on New Chat would be wrong. The bleed to fix is the *invisible*
aggregate (`rg_pref_summary`) driving suggestions in a chat the user believes
is fresh. Whether that personalization should survive New Chat is the same
product decision as DOCTRINE D4 — this task implements the minimal honest
version: starter bias off in a brand-new chat until the user acts.

**Files:**
- Modify: `frontend/lib/chatStarters.ts` — accept a `freshChat` signal
- Modify: `frontend/components/ChatContainer.tsx` — pass it on the New Chat path
- Create: `frontend/tests/chatStarters.test.ts`

- [ ] **Step 1: Write the failing test — against the HOOK, not pickStarter**

**Final-validation correction (Kimi):** `pickStarter(sets, signalText, rng?)`
takes the signal AS AN ARGUMENT and never touches localStorage — the
signal-reading lives in the `useChatStarter()` hook
(`setSet(pickStarter(STARTER_SETS, readUserSignal()))`). The `freshChat` flag
therefore belongs on the hook. Testing `pickStarter({freshChat})` would assert
a signature that cannot exist.

```tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useChatStarter } from '@/lib/chatStarters'  // confirm real export name

describe('starter personalization in a fresh chat', () => {
  beforeEach(() => {
    localStorage.setItem('rg_pref_summary', JSON.stringify(['headphones', 'sony']))
    localStorage.setItem('reviewguide_recent_searches', JSON.stringify([
      { query: 'best headphones', category: 'audio', productNames: ['Sony XM5'] },
    ]))
  })

  it('ignores stored signal when the chat is brand-new', () => {
    const { result } = renderHook(() => useChatStarter({ freshChat: true }))
    expect(JSON.stringify(result.current).toLowerCase()).not.toContain('headphone')
  })

  it('uses stored signal in an ongoing session', () => {
    const { result } = renderHook(() => useChatStarter({ freshChat: false }))
    expect(JSON.stringify(result.current).toLowerCase()).toContain('headphone')
  })
})
```

`pickStarter` itself stays pure and untouched. Confirm the hook's real name,
options shape, and return shape in `chatStarters.ts` before running; keep the
assertions' intent.

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/chatStarters.test.ts`
Expected: FAIL — the hook takes no such option and reads the signal
unconditionally.

- [ ] **Step 3: Implement**

Add the `freshChat` option to `useChatStarter`; when set, pass `''` to
`pickStarter` instead of `readUserSignal()`. Thread the flag from the New Chat
path (`clearHistoryTrigger` effect, `ChatContainer.tsx:803-811`, and the
`?new=1` mount) to the hook's call site (`ChatContainer.tsx:121`). One flag, no
key deletion — saved items and recents remain intact for their own features.

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run tests/chatStarters.test.ts`

- [ ] **Step 5: Verify live**

Ask about headphones, New Chat, send "asdfgh": the clarification prompt must
not mention headphones. (The "(like last time)" budget chip is DOCTRINE D4 —
out of scope here, by design.)

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/chatStarters.ts frontend/components/ChatContainer.tsx \
        frontend/tests/chatStarters.test.ts
git commit -m "fix(ui): fresh chats start unbiased — starter ignores stored signal until the user acts"
```

---

### Task 7: Travel output must respect stated constraints

**Root cause:** "4 days in Lisbon with two kids under 8" returned Bairro Alto nightlife, a
Fado dinner, and a tapas crawl; never answered the explicit "what should we skip?";
invented dates (Sep 30 – Oct 4, 2026); then asked for travel dates and traveller counts it
had already used.

**Files:**
- Modify: `backend/mcp_server/tools/travel_itinerary.py`
- Create: `backend/tests/test_travel_constraints.py`

**Interfaces:**
- Produces: `_travel_constraint_block(slots: dict) -> str` — a prompt fragment asserting
  the party composition and forbidding invented dates.

- [ ] **Step 1: Write the failing test**

```python
from mcp_server.tools.travel_itinerary import _travel_constraint_block


def test_children_in_the_party_are_asserted():
    block = _travel_constraint_block({"travelers": "2 adults, 2 children under 8"})
    lowered = block.lower()
    assert "child" in lowered or "kid" in lowered
    assert "nightlife" in lowered or "late-night" in lowered


def test_absent_dates_are_not_invented():
    block = _travel_constraint_block({"destination": "Lisbon", "duration": "4 days"})
    assert "do not invent" in block.lower() or "never invent" in block.lower()


def test_no_constraints_yields_an_empty_block():
    assert _travel_constraint_block({}) == ""
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_travel_constraints.py -v`
Expected: FAIL — `ImportError: cannot import name '_travel_constraint_block'`.

- [ ] **Step 3: Implement**

```python
_CHILD_RE = re.compile(r"\b(?:kid|child|children|toddler|infant|baby)\w*\b", re.IGNORECASE)


def _travel_constraint_block(slots: dict) -> str:
    """Prompt fragment asserting hard party constraints for the itinerary.

    An itinerary for a family with two under-8s that opens with Bairro Alto
    nightlife and a late Fado dinner is not a near-miss — it is unusable.
    """
    slots = slots or {}
    parts = []

    travelers = str(slots.get("travelers") or "")
    if _CHILD_RE.search(travelers):
        parts.append(
            "PARTY INCLUDES YOUNG CHILDREN — this is a hard constraint:\n"
            "- No nightlife, bar crawls, late-night dining, or adults-only venues.\n"
            "- Keep evenings early; assume an early bedtime.\n"
            "- Prefer parks, beaches, trams, aquariums, and short walks between stops."
        )

    if not slots.get("dates") and not slots.get("start_date"):
        parts.append(
            "DATES ARE UNKNOWN — do not invent them. Write the itinerary as "
            "Day 1 / Day 2 / Day 3. Never print a specific calendar date the user "
            "did not give you."
        )

    if not parts:
        return ""
    return "\n\n".join(parts)
```

Insert the returned block into the itinerary prompt, and make sure the composer answers
any explicit question in the user's message (such as "what should we skip?") before
listing the itinerary.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_travel_constraints.py -v`
Expected: all 3 PASS.

- [ ] **Step 5: Verify live**

Send: *"4 days in Lisbon with two kids under 8 — what should we skip?"* The answer must
contain no nightlife, must answer the skip question, and must use Day 1–4 rather than
invented dates.

- [ ] **Step 6: Commit**

```bash
git add backend/mcp_server/tools/travel_itinerary.py backend/tests/test_travel_constraints.py
git commit -m "fix(travel): honour party composition and stop inventing travel dates"
```

---

### Task 8: Verification pass

- [ ] **Step 1: Run both suites**

```bash
cd backend && python -m pytest tests/ -q
cd ../frontend && npx vitest run
```

- [ ] **Step 2: Replay the audit's Lisbon conversation**

Ask for a Lisbon trip, answer the departure-city question by typing "Manchester, UK", and
confirm it is asked **once**. Then ask "which reviews support your pick?" and confirm you
get an answer, not a questionnaire.

- [ ] **Step 3: Commit**

```bash
git commit --allow-empty -m "test: PLAN-5 verified — slots stick, follow-ups answered"
```
