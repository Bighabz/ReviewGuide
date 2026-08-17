# Strain Misroute Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A non-cannabis question can never receive a cannabis-strain answer.

**Evidence (prod, verified via Langfuse traces 2026-07-21, session `96e11c6f`):**
user asked *"Health only, but is the whoop worth it, does it do more than the
apple watch for health"* in a fitness-tracker conversation and received
*"**GG4** is the pick here — a hybrid known for Relaxed, Happy, Euphoric…"*.
Trace `c2296050045148043981a53cc55c1d4b` shows the full chain:

1. Intent LLM emitted `{"intent": "strain"}` on a fitness question (`agent_intent`
   observation).
2. `strain_search`'s extraction LLM correctly found **zero** cannabis signal —
   `{"named_strains": [], "feelings": [], "conditions": [], "strain_type": null}`
   — but zero-extraction falls through to "broad recommend" mode instead of
   aborting.
3. The `strain_compose` verdict LLM **refused** ("I need to stop here and be
   direct: you asked about health tracking devices… but the strain data you've
   given me is cannabis recommendations") — and the deterministic fallback
   DISCARDED the refusal and shipped the GG4 pick (`agent_plan_executor`
   observation).

Three independent failures; fixing any one prevents the incident. This plan
fixes the two deterministic ones (2 and 3) and adds a narrow veto for 1 —
deliberately NOT a keyword router, preserving Habib's 2026-06-10 "AI-driven,
not deterministic" intent decision: the AI still detects; the veto only fires
when there is zero cannabis evidence anywhere.

**Tech Stack:** Python 3.11, pytest.

## Global Constraints

- The SmartVape vertical itself is working and shipped ("sour d vs blue dream"
  prod-verified) — nothing here may break genuine strain queries. The existing
  suite is `backend/tests/test_strain_vertical.py`; it stays green.
- workflow.py's intent_node has its OWN intent whitelist separate from
  intent_agent's (both must list "strain") — do not touch either list.
- DOCTRINE D5 applies: an LLM refusal is a protective gate; a fallback may
  never override it (fail closed, not degraded).
- Tests: `cd backend && python -m pytest tests/<file> -v`

## File Structure

- Modify: `backend/mcp_server/tools/strain_search.py` — zero-signal abort
- Modify: `backend/mcp_server/tools/strain_compose.py` — refusal honored
- Modify: `backend/app/agents/intent_agent.py` — evidence veto
- Create: `backend/tests/test_strain_misroute.py`

---

### Task 1: Zero cannabis signal aborts the strain plan

**Root cause:** `strain_search`'s documented contract is "Extraction-LLM
failure → broad recommend default". An all-empty extraction — the extractor
succeeding and finding NOTHING — takes the same path, so a misrouted fitness
question gets a broad strain recommendation.

**Files:**
- Modify: `backend/mcp_server/tools/strain_search.py`
- Create: `backend/tests/test_strain_misroute.py`

**Interfaces:**
- Produces: on all-empty extraction AND no cannabis lexicon in the raw message,
  `strain_search` returns `{"strain_results": [], "strain_misroute": True,
  "success": True}` instead of engine recommendations. Task 2 consumes the flag.

- [ ] **Step 1: Read the current extraction handling**

`grep -n "named_strains\|recommend\|def strain_search" mcp_server/tools/strain_search.py | head -15`
Record the exact branch where empty extraction falls into recommend mode.

- [ ] **Step 2: Write the failing test**

```python
"""Prod incident 2026-07-21 (session 96e11c6f): a Whoop-vs-Apple-Watch
question was intent-classified 'strain', the extractor correctly found zero
cannabis signal, and the pipeline recommended GG4 anyway."""
import os
import pytest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from mcp_server.tools.strain_search import strain_search

UNCLE_QUERY = ("Health only, but is the whoop worth it, does it do more than "
               "the apple watch for health")

EMPTY_EXTRACTION = '{"named_strains": [], "feelings": [], "conditions": [], "strain_type": null}'


@pytest.mark.asyncio
async def test_zero_signal_aborts_instead_of_recommending():
    with patch("app.services.model_service.model_service") as ms:
        ms.generate = AsyncMock(return_value=EMPTY_EXTRACTION)
        result = await strain_search({"user_message": UNCLE_QUERY, "slots": {}})
    assert result.get("strain_misroute") is True
    assert result.get("strain_results") in ([], None)


@pytest.mark.asyncio
async def test_empty_extraction_with_cannabis_words_still_recommends():
    """'what should I smoke to relax' can extract empty (vocab clamp) but the
    message IS a cannabis ask — broad recommend stays correct there."""
    with patch("app.services.model_service.model_service") as ms:
        ms.generate = AsyncMock(return_value=EMPTY_EXTRACTION)
        result = await strain_search({
            "user_message": "what weed should I smoke to relax", "slots": {}})
    assert result.get("strain_misroute") is not True
```

Adapt the mock target to how `strain_search` actually calls the model (read
the file first — same pattern as the other tool tests).

- [ ] **Step 3: Run to verify failure, then implement**

```python
# Words that make a message a plausible cannabis ask even when extraction is
# empty. Deliberately broad on cannabis slang, zero overlap with product terms.
_CANNABIS_LEXICON_RE = re.compile(
    r"\b(?:weed|cannabis|marijuana|strains?|indica|sativa|hybrid|terpenes?|"
    r"thc|cbd|smoke|smoking|toke|kush|edibles?|dispensary|joint|blunt|bud)\b",
    re.IGNORECASE,
)
```

In the empty-extraction branch: if `_CANNABIS_LEXICON_RE` finds nothing in the
user message, log the misroute loudly and return the abort shape from the
interface block — the intent classifier was wrong, and recommending strains to
a question with zero cannabis evidence is how GG4 answered a Whoop question.

- [ ] **Step 4: Run this file + the strain suite**

`python -m pytest tests/test_strain_misroute.py tests/test_strain_vertical.py -v`
Both green — genuine strain queries untouched.

- [ ] **Step 5: Commit**

```bash
git add backend/mcp_server/tools/strain_search.py backend/tests/test_strain_misroute.py
git commit -m "fix(strain): zero cannabis signal aborts the strain plan instead of broad-recommending"
```

---

### Task 2: A verdict refusal is final — the fallback may not override it

**Root cause:** `strain_compose` = one LLM verdict call + deterministic
fallback. The verdict LLM refused the mismatched request; the fallback treated
the refusal as an unusable output and shipped GG4 anyway.

**Files:**
- Modify: `backend/mcp_server/tools/strain_compose.py`
- Test: `backend/tests/test_strain_misroute.py`

- [ ] **Step 1: Read the fallback branch**

`grep -n "fallback\|def strain_compose\|verdict" mcp_server/tools/strain_compose.py | head -15`

- [ ] **Step 2: Write the failing tests**

```python
from mcp_server.tools.strain_compose import strain_compose


@pytest.mark.asyncio
async def test_misroute_flag_yields_honest_redirect_not_cards():
    result = await strain_compose({
        "user_message": UNCLE_QUERY,
        "strain_results": [],
        "strain_misroute": True,
    })
    text = (result.get("assistant_text") or "").lower()
    assert "gg4" not in text and "strain" not in text.split(".")[0]
    assert result.get("ui_blocks") in ([], None)
    # It answers or redirects to the actual question, not cannabis.
    assert "?" in text or "let" in text or "back" in text


@pytest.mark.asyncio
async def test_verdict_refusal_is_not_replaced_by_fallback():
    """The prod incident's third failure: the verdict LLM refused the
    mismatch and the deterministic fallback overrode it with GG4."""
    refusal = ("I need to stop here and be direct: you asked about health "
               "tracking devices, but the strain data is cannabis.")
    with patch("app.services.model_service.model_service") as ms:
        ms.generate = AsyncMock(return_value=refusal)
        result = await strain_compose({
            "user_message": UNCLE_QUERY,
            "strain_results": [{"name": "GG4", "type": "hybrid",
                                "effects": ["Relaxed", "Happy", "Euphoric"]}],
        })
    text = (result.get("assistant_text") or "")
    assert "GG4" not in text  # fallback must not resurrect the pick
```

Adapt shapes to the tool's real state contract (read it first).

- [ ] **Step 3: Implement**

Two changes: (a) when `strain_misroute` is set, emit a short honest redirect
("That looked like a cannabis question to my router — it isn't. Back to your
actual question: …" or simply answer via the general path) with no cards;
(b) detect a verdict output that declines/flags a mismatch (no strain names
from the results appear in it, or it opens by refusing) and treat it as FINAL
— the deterministic fallback runs only on transport/parse failures, never on a
refusal. This is DOCTRINE D5 axis three: a protective gate fails closed.

- [ ] **Step 4: Run + commit**

```bash
python -m pytest tests/test_strain_misroute.py tests/test_strain_vertical.py -v
git add backend/mcp_server/tools/strain_compose.py backend/tests/test_strain_misroute.py
git commit -m "fix(strain): honest redirect on misroute; verdict refusals are final"
```

---

### Task 3: Evidence veto on the strain intent (narrow, AI-first preserved)

**Files:**
- Modify: `backend/app/agents/intent_agent.py`
- Test: `backend/tests/test_strain_misroute.py`

- [ ] **Step 1: Write the failing test**

```python
from app.agents.intent_agent import veto_strain_intent


def test_vetoes_strain_on_zero_evidence():
    history = [
        {"role": "user", "content": "What's the difference between an apple watch and whoop"},
        {"role": "assistant", "content": "The Apple Watch and Whoop serve different purposes…"},
    ]
    assert veto_strain_intent(UNCLE_QUERY, history) is True


def test_no_veto_when_message_has_cannabis_terms():
    assert veto_strain_intent("sour d vs blue dream", []) is False


def test_no_veto_when_history_is_a_strain_conversation():
    history = [{"role": "user", "content": "best sativa strains for focus"},
               {"role": "assistant", "content": "Durban Poison is the pick…"}]
    assert veto_strain_intent("what about something more relaxing", history) is False
```

- [ ] **Step 2: Implement**

```python
def veto_strain_intent(user_message: str, conversation_history: list) -> bool:
    """True when the LLM classified 'strain' but NO cannabis evidence exists in
    the message or recent history. Not a keyword router (the AI still owns
    detection, per Habib 2026-06-10) — a veto that fires only on zero evidence,
    which is exactly the prod misroute: a Whoop question classified 'strain'."""
    recent = " ".join(m.get("content", "") for m in (conversation_history or [])[-6:])
    blob = f"{user_message} {recent}"
    return not _CANNABIS_LEXICON_RE.search(blob)
```

Share `_CANNABIS_LEXICON_RE` (import from one home — put it in
`intent_agent.py`, import in `strain_search.py`). Apply in the intent result
handling: when the LLM says `strain` and the veto fires, downgrade to
`product` with a log line naming the veto.

- [ ] **Step 3: Run everything + verify live**

`python -m pytest tests/test_strain_misroute.py tests/test_strain_vertical.py tests/ -q`
Live: replay the uncle's two turns (fitness context → "Health only, but is the
whoop worth it…") and confirm a fitness answer; then "sour d vs blue dream"
still returns strain cards.

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/intent_agent.py backend/mcp_server/tools/strain_search.py \
        backend/tests/test_strain_misroute.py
git commit -m "fix(intent): zero-evidence veto on strain classification"
```
