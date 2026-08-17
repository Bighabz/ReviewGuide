# Workflow & State Integrity Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix four confirmed workflow-layer bugs found by the 2026-07-31 two-round
debug sweep: conversation history that duplicates itself every turn, resumed
messages that bypass moderation, an evidence step that runs before its input
exists, and a completeness flag that always says "full".

**Architecture:** All four live at the LangGraph orchestration layer — the graph's
reducer semantics, the safety node's resume branch, the planner's step ordering,
and the SSE done-payload. None touch product logic. Each was verified against
source; citations are current as of 2026-07-31 (post-guardrail-commit offsets).

**Tech Stack:** Python 3.11, pytest, LangGraph.

## Global Constraints

- Adding or changing a `GraphState` field requires a matching default in
  `initial_state` in `backend/app/api/v1/chat.py` (`:335`) or LangGraph
  channels crash. This has bitten twice.
- Real stage names in telemetry are `"safety"`, `"intent"`, `"clarifier"`,
  `"plan_exec"`, and `"tool.<name>"` (`stage_telemetry.py:31,49-58`) — use
  those literals in fixtures, and Task 4's live-verify tweaks a real
  `STAGE_BUDGETS` key.
- **Task 4 scope note (validation catch):** deriving "degraded" from ANY
  `timeout_hit` includes the clarifier stage's designed silent-skip fallback —
  which quietly decides part of DOCTRINE D5 by side effect (users would see a
  degraded badge on every clarifier timeout). Until D5 is decided, EXCLUDE the
  `"clarifier"` stage from `_derive_completeness` and say so in a comment.
- The resume path is load-bearing for multi-turn clarification. Task 2 must not
  break halt/resume — the existing clarifier tests must stay green.
- Fail open stays fail open for API errors (`safety_agent.py` moderation catch).
  Task 2 adds moderation to a path that skips it; it must not convert API
  failure into blocking.
- Tests: `cd backend && python -m pytest tests/<file> -v`

## File Structure

- Modify: `backend/app/services/langgraph/workflow.py` — Tasks 1, 2
- Modify: `backend/app/agents/planner_agent.py` — Task 3
- Modify: `backend/app/api/v1/chat.py` — Task 4
- Create: `backend/tests/test_workflow_state_integrity.py` — all tasks

---

### Task 1: conversation_history must not duplicate itself every turn

**Root cause (verified):** `graph_state.py:22` declares
`conversation_history: Annotated[List[Dict[str, str]], operator.add]` — an
additive reducer. `safety_node` (`workflow.py:113-121`) copies the FULL existing
history, appends the new user message, and returns the whole list. LangGraph
concatenates the returned list onto the channel: after the safety node runs, the
channel holds `initial_history + (initial_history + [new_msg])`. Every
downstream node and every prompt that reads history sees the prior conversation
doubled, every turn.

**Fix shape:** with an additive reducer, a node must return only the DELTA.
Safety returns `[{new user message}]`; the reducer does the append.

**Files:**
- Modify: `backend/app/services/langgraph/workflow.py` (the `_run_safety` inner
  function's history handling)
- Test: `backend/tests/test_workflow_state_integrity.py`

- [ ] **Step 1: Write the failing test**

```python
"""Round-2 sweep (2026-07-31): four confirmed workflow-layer bugs.

Task 1 — conversation_history doubles every turn: the channel reducer is
operator.add (graph_state.py:22) but safety_node returns the FULL copied
history + new message, so LangGraph concatenates a second copy of the prior
history onto the channel on every turn.
"""
import os

import pytest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from app.services.langgraph import workflow as wf

PRIOR = [
    {"role": "user", "content": "best espresso machine under $500"},
    {"role": "assistant", "content": "The Breville Barista Express is the pick."},
]


@pytest.mark.asyncio
async def test_safety_node_returns_only_the_history_delta():
    """With an operator.add reducer, returning the full list duplicates it.
    The node must return ONLY the new message."""
    fake = AsyncMock(return_value={
        "policy_status": "allow", "sanitized_text": "how loud is it?",
        "redaction_map": {}, "health_advisory": False,
    })
    with patch.object(wf.safety_agent_instance, "execute", fake):
        update = await wf.safety_node({
            "session_id": "s1",
            "user_message": "how loud is it?",
            "conversation_history": list(PRIOR),
        })

    returned = update["conversation_history"]
    # The delta: exactly one entry, the new user message. If this returns
    # len(PRIOR) + 1 entries, the reducer will double the prior history.
    assert len(returned) == 1
    assert returned[0] == {"role": "user", "content": "how loud is it?"}


@pytest.mark.asyncio
async def test_simulated_reducer_yields_no_duplicates():
    """What the channel actually holds after the merge: prior + delta,
    each prior message exactly once."""
    import operator

    fake = AsyncMock(return_value={
        "policy_status": "allow", "sanitized_text": "how loud is it?",
        "redaction_map": {}, "health_advisory": False,
    })
    with patch.object(wf.safety_agent_instance, "execute", fake):
        update = await wf.safety_node({
            "session_id": "s1",
            "user_message": "how loud is it?",
            "conversation_history": list(PRIOR),
        })

    merged = operator.add(list(PRIOR), update["conversation_history"])
    assert len(merged) == len(PRIOR) + 1
    contents = [m["content"] for m in merged]
    assert contents.count("best espresso machine under $500") == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_workflow_state_integrity.py -k history -v`
Expected: FAIL — `len(returned)` is `len(PRIOR) + 1`, and the simulated merge
contains the first message twice.

- [ ] **Step 3: Return the delta**

In `_run_safety` (`workflow.py:113-121`), replace the copy-append-return-all with:

```python
        # conversation_history uses an operator.add reducer (graph_state.py:22):
        # LangGraph CONCATENATES whatever this node returns onto the channel.
        # Returning the full copied history therefore doubled the prior
        # conversation on every turn (round-2 sweep, 2026-07-31). Return ONLY
        # the delta — the reducer does the append.
        history_delta = []
        if user_message:
            history_delta.append({"role": "user", "content": user_message})
            logger.info("[SafetyAgent] Appending user message to conversation_history (delta)")
```

and in the `update` dict: `"conversation_history": history_delta,`.

- [ ] **Step 4: Audit every other writer of the channel**

```bash
cd backend && grep -rn "conversation_history" app/services/langgraph/ app/api/v1/chat.py | grep -v "\.get("
```

Any other node returning a full list has the same bug — convert each to a delta.
`initial_state` in `chat.py` seeding the channel once at graph entry is correct
and must NOT change.

- [ ] **Step 5: Run to verify it passes, then the full suite**

Run: `cd backend && python -m pytest tests/test_workflow_state_integrity.py -v`
Then: `cd backend && python -m pytest tests/ -q`
Expected: new tests PASS; no regressions. Watch specifically for tests that
asserted the old (doubled) behaviour — fix the production expectation, never
re-introduce the duplication.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/langgraph/workflow.py backend/tests/test_workflow_state_integrity.py
git commit -m "fix(workflow): safety node returns history delta — operator.add was doubling history every turn"
```

---

### Task 2: Resumed messages must be moderated

**Root cause (verified):** the resume branch in `safety_node`
(`workflow.py:84-105`) manufactures `policy_status: "allow"` and returns before
`safety_agent_instance.execute` is called (`:111`). Any message sent while a
clarification halt is pending — including blockable content — skips moderation
entirely and goes straight to the clarifier. It also skips
`detect_health_advisory`.

**Fix shape:** moderate first, route second. The resume branch keeps its routing
job but runs AFTER the safety checks, using their real `policy_status`.

**Files:**
- Modify: `backend/app/services/langgraph/workflow.py` — restructure `_run_safety`
- Test: `backend/tests/test_workflow_state_integrity.py`

- [ ] **Step 1: Write the failing test**

```python
BLOCKED_RESULT = {
    "policy_status": "block",
    "sanitized_text": "…",
    "redaction_map": {},
    "health_advisory": False,
    "errors": ["Content flagged for: hate/threatening"],
}


@pytest.mark.asyncio
async def test_resumed_message_is_still_moderated():
    """A blockable message sent while a clarification halt is pending must be
    blocked, not routed to the clarifier as a slot answer."""
    halt = {"intent": "product", "slots": {"category": "laptops"},
            "followups": [{"slot": "budget", "question": "Budget?"}], "plan": None}

    fake_exec = AsyncMock(return_value=dict(BLOCKED_RESULT))
    with patch.object(wf.safety_agent_instance, "execute", fake_exec), \
         patch("app.services.halt_state_manager.HaltStateManager.check_halt_exists",
               AsyncMock(return_value=True)), \
         patch("app.services.halt_state_manager.HaltStateManager.load_halt_state",
               AsyncMock(return_value=halt)):
        update = await wf.safety_node({
            "session_id": "s1",
            "user_message": "<blockable content>",
            "conversation_history": [],
        })

    fake_exec.assert_awaited()          # moderation actually ran
    assert update["policy_status"] == "block"
    assert update.get("next_agent") != "clarifier"


@pytest.mark.asyncio
async def test_clean_resumed_message_still_routes_to_clarifier():
    """The halt/resume contract survives: a clean answer resumes clarification
    with restored intent and slots."""
    halt = {"intent": "product", "slots": {"category": "laptops"},
            "followups": [{"slot": "budget", "question": "Budget?"}], "plan": None}

    fake_exec = AsyncMock(return_value={
        "policy_status": "allow", "sanitized_text": "under $800",
        "redaction_map": {}, "health_advisory": False,
    })
    with patch.object(wf.safety_agent_instance, "execute", fake_exec), \
         patch("app.services.halt_state_manager.HaltStateManager.check_halt_exists",
               AsyncMock(return_value=True)), \
         patch("app.services.halt_state_manager.HaltStateManager.load_halt_state",
               AsyncMock(return_value=halt)):
        update = await wf.safety_node({
            "session_id": "s1",
            "user_message": "under $800",
            "conversation_history": [],
        })

    fake_exec.assert_awaited()
    assert update["next_agent"] == "clarifier"
    assert update["intent"] == "product"
    assert update["slots"] == {"category": "laptops"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_workflow_state_integrity.py -k resumed -v`
Expected: `test_resumed_message_is_still_moderated` FAILS —
`fake_exec.assert_awaited()` fails because the resume branch returns before
moderation, and `next_agent` is `"clarifier"`.

- [ ] **Step 3: Restructure — moderate first, route second**

In `_run_safety`, move the halt-state lookup AFTER
`result = await safety_agent_instance.execute(state)`. Then:

```python
        # Moderation runs on EVERY message, resumed or not. The old code
        # manufactured policy_status="allow" and returned before execute() on
        # the resume path, so blockable content sent mid-clarification skipped
        # safety entirely (round-2 sweep, 2026-07-31). Route to the clarifier
        # only with a real allow.
        if result["policy_status"] != "block" and halt_state_data_with_followups:
            resume_update = {
                "policy_status": result["policy_status"],
                "sanitized_text": result["sanitized_text"],
                "redaction_map": result["redaction_map"],
                "health_advisory": result.get("health_advisory", False),
                "current_agent": "safety",
                "next_agent": "clarifier",
                "conversation_history": history_delta,
            }
            # …restore intent/slots/plan from halt_state_data exactly as before…
            return resume_update
```

Keep the block path identical to the non-resume block path. Preserve the
existing stale-halt cleanup (empty followups → delete + fall through). The
history delta from Task 1 must be returned on the resume path too — the old
early return skipped the history append entirely, which was its own
inconsistency.

- [ ] **Step 4: Run to verify it passes, then the clarifier suite**

Run: `cd backend && python -m pytest tests/test_workflow_state_integrity.py -v`
Then: `cd backend && python -m pytest tests/ -k "clarifier or halt or chat_streaming" -q`
Expected: all PASS — the halt/resume contract is unchanged for clean messages.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/langgraph/workflow.py backend/tests/test_workflow_state_integrity.py
git commit -m "fix(safety): moderate resumed messages before routing to the clarifier"
```

---

### Task 3: Remove product_evidence from every plan template — with consumer migration

> **Revised after adversarial validation (Sol).** The original claim was too
> broad and the removal was incomplete. Corrected picture:

**Root cause (verified, narrowed):** on **recommendation/deep-research**
templates, `product_evidence` is a guaranteed no-op — scheduled in parallel
with `product_search` (`planner_agent.py:622`), whose output it reads. On
**comparison/factoid** templates, `include_extractor=True`
(`planner_agent.py:576-585`) runs `product_extractor` BEFORE the parallel step,
so evidence receives names and RUNS — fabricating "direct quotes" from
parametric memory. So the tool is dead where it's harmless and alive where it's
harmful.

**Also verified:** it is scheduled in the fast-path template too
(`planner_agent.py:638-669`), and it has **live consumers** —
`product_normalize.py:101-110` merges `review_aspects` into pros/cons/rating,
and `product_ranking.py:223-247` uses it as a ranking fallback. Removal without
migration silently changes comparison ranking.

**Ordering prerequisite: PLAN-3 v2 must land first** — it replaces the
pros/cons source (consolidated composer, grounded). Then this task removes the
tool from BOTH templates and retires the consumers.

**Files:**
- Modify: `backend/app/agents/planner_agent.py` — standard template (`:622`) AND
  fast-path template (`:638-669`)
- Modify: `backend/mcp_server/tools/product_normalize.py:101-110` — drop the
  `review_aspects` merge (pros/cons now arrive via PLAN-3's path; rating stays
  sourced from `review_data`)
- Modify: `backend/mcp_server/tools/product_ranking.py:223-247` — remove the
  `review_aspects` fallback; rank on the remaining signals
- Test: `backend/tests/test_workflow_state_integrity.py`

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.parametrize("complexity", ["factoid", "comparison", "recommendation",
                                        "deep_research"])
def test_no_plan_template_schedules_product_evidence(complexity):
    """Dead in parallel on recommendation paths, fabricating on comparison
    paths (extractor pre-populates names) — removed from EVERY template.
    Pros/cons come from PLAN-3's grounded consolidated call."""
    from app.agents.planner_agent import PlannerAgent

    plan = PlannerAgent()._get_product_plan_for_complexity(complexity)
    for step in plan["steps"]:
        assert "product_evidence" not in step["tools"], (
            f"product_evidence still in {complexity} template step {step['id']}"
        )


def test_normalize_no_longer_reads_review_aspects():
    """Consumer migration: normalize's pros/cons merge came from the removed
    tool. Rating still flows from review_data."""
    import inspect
    from mcp_server.tools import product_normalize

    src = inspect.getsource(product_normalize)
    assert "review_aspects" not in src
```

`_get_product_plan_for_complexity` is real (`planner_agent.py:576`); verify the
exact constructor args before running. Add the mirror `inspect` check for
`product_ranking` once its fallback is removed.

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_workflow_state_integrity.py -k evidence -v`
Expected: FAIL — `product_evidence` is present in the parallel step.

- [ ] **Step 3: Remove it**

At `planner_agent.py:622`:

```python
        # product_evidence removed 2026-07-31: it was scheduled in parallel with
        # product_search but READS product_search's output — a guaranteed no-op
        # (round-2 sweep). Serializing it was rejected: when it runs it invents
        # "direct quotes" from parametric memory into evidence_citations, which
        # the sourcing-honesty guardrail forbids. Card pros/cons come from the
        # consolidated composer call instead (PLAN-3).
        steps.append({"id": f"step_{step_num}", "tools": ["product_search"], "parallel": False})
```

Then sweep for other plans referencing the tool:

```bash
cd backend && grep -rn "product_evidence" app/agents/planner_agent.py mcp_server/main.py
```

Leave the tool registered in `mcp_server/main.py` (removal from the MCP registry
is out of scope — the planner just stops scheduling it). If the LLM-planner
prompt lists it as available, remove it from that listing too, or the dynamic
planner will keep scheduling what the template plan dropped.

**Consumer migration (final-validation blocker — an implementation step, not
just tests):** in the SAME commit,
- `product_normalize.py:101-110` — delete the `review_aspects` merge block
  (pros/cons arrive via PLAN-3's path; keep the `review_data`-sourced rating).
- `product_ranking.py:223-247` — delete the `review_aspects` fallback branch;
  rank on the remaining signals.
Run `cd backend && python -m pytest tests/ -k "normalize or ranking" -q` after
each deletion — a test that consumed `review_aspects` was testing the dead/
fabricating path and moves to the PLAN-3 source.

- [ ] **Step 4: Run to verify it passes, then the compose suite**

Run: `cd backend && python -m pytest tests/test_workflow_state_integrity.py -v`
Then: `cd backend && python -m pytest tests/ -k "compose or plan" -q`
Expected: all PASS. If a compose test consumed `review_aspects` from
product_evidence, it was testing a dead path — update it to the PLAN-3 source.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/planner_agent.py backend/mcp_server/tools/product_normalize.py \
        backend/mcp_server/tools/product_ranking.py backend/tests/test_workflow_state_integrity.py
git commit -m "fix(planner): drop product_evidence from all templates and retire its consumers"
```

---

### Task 4: The completeness flag must tell the truth — backend AND frontend

> **Revised after adversarial validation.** Two additions: (a) stage failures
> can produce fallbacks with `timeout_hit=False` but a fatal `error_class`
> (`stage_telemetry.py:92-98,128-134`) — deriving from `timeout_hit` alone
> misses them; (b) the FRONTEND discards `data.completeness` and hardcodes
> `'full'` on every done event (`ChatContainer.tsx:590`) — a backend-only fix
> changes nothing on screen.

**Root cause (verified):** `chat.py:909` hardcodes `"completeness": "full"`
("degraded logic deferred to a later phase") in the done payload, and
`ChatContainer.tsx:581-598` overwrites whatever arrives with `'full'`. The
executor-timeout fallback says "partial results" in prose while both layers say
the answer is complete.

**Files:**
- Modify: `backend/app/api/v1/chat.py` (~:909)
- Modify: `frontend/components/ChatContainer.tsx:581-598` — thread
  `data.completeness` into the message instead of the literal
- Test: `backend/tests/test_workflow_state_integrity.py` +
  `frontend/tests/completeness.test.tsx`

- [ ] **Step 1: Find the degradation signals already in state**

```bash
cd backend && grep -n "timeout_hit\|stage_telemetry\|partial results\|degraded" app/api/v1/chat.py app/services/langgraph/workflow.py | head -20
```

`stage_telemetry` entries carry `timeout_hit` per stage — that is the existing
truth source. Record what you find; the test below assumes a helper reading it.

- [ ] **Step 2: Write the failing test**

```python
def test_completeness_reflects_stage_timeouts_and_fatal_fallbacks():
    from app.api.v1.chat import _derive_completeness

    full = [{"stage": "safety", "timeout_hit": False, "error_class": None},
            {"stage": "plan_exec", "timeout_hit": False, "error_class": None}]
    timed_out = [{"stage": "plan_exec", "timeout_hit": True, "error_class": "transient"}]
    # Validation catch: a stage can fail fatally WITHOUT a timeout — its
    # fallback ran, so the answer is degraded (stage_telemetry.py:92-98).
    fatal = [{"stage": "plan_exec", "timeout_hit": False, "error_class": "fatal"}]

    assert _derive_completeness(full) == "full"
    assert _derive_completeness(timed_out) == "degraded"
    assert _derive_completeness(fatal) == "degraded"
    assert _derive_completeness([]) == "full"
    assert _derive_completeness(None) == "full"
    # D5 guard: a clarifier timeout alone must NOT degrade the response —
    # that flip is an undecided product call (DOCTRINE D5).
    clarifier_only = [{"stage": "clarifier", "timeout_hit": True, "error_class": "transient"}]
    assert _derive_completeness(clarifier_only) == "full"
```

Before finalising the `fatal` fixture, read `stage_telemetry.py:92-134` for the
exact `error_class` values a fallback stamps and use those literals.

- [ ] **Step 3: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_workflow_state_integrity.py -k completeness -v`
Expected: FAIL — `ImportError: cannot import name '_derive_completeness'`.

- [ ] **Step 4: Implement and wire**

```python
def _derive_completeness(stage_telemetry) -> str:
    """The done payload's completeness, derived from what actually happened.

    Was hardcoded "full" — so the executor-timeout path told the user "partial
    results" in prose while telling the UI the answer was complete. A stage
    degrades the answer when it hit its hard timeout OR failed fatally into its
    fallback (validation catch: fatal fallbacks carry timeout_hit=False).
    """
    for entry in stage_telemetry or []:
        # D5 guard: the clarifier's timeout-fallback (silent skip) is an
        # undecided product call — flagging it here would decide DOCTRINE D5
        # by side effect. Excluded until D5 is settled.
        if entry.get("stage") == "clarifier":
            continue
        if entry.get("timeout_hit") or entry.get("error_class") == "fatal":
            return "degraded"
    return "full"
```

Replace `"completeness": "full",` at `chat.py:909` with
`"completeness": _derive_completeness(result_state.get("stage_telemetry")),`.

**Then the frontend half** — `ChatContainer.tsx:590` currently overwrites with
the literal `'full'`. Thread the payload value:

```tsx
                    completeness: (data.completeness as Message['completeness']) ?? 'full',
```

and add `frontend/tests/completeness.test.tsx`: drive `onComplete` with
`completeness: 'degraded'` and assert the message carries `'degraded'` (the
recovery/badge UI for that state already exists — `messageRecovery.test.tsx`).

- [ ] **Step 5: Run to verify it passes, then the chat API suite**

Run: `cd backend && python -m pytest tests/test_workflow_state_integrity.py -v`
Then: `cd backend && python -m pytest tests/test_chat_api.py tests/test_chat_streaming.py -q`
Expected: all PASS. If a streaming test pinned `completeness == "full"`
unconditionally, it pinned the bug — update it to the derived value.

- [ ] **Step 6: Verify live**

Start the stack, force an executor timeout (set the plan_exec stage budget low
in a dev override), and confirm the done payload carries
`completeness: "degraded"` and the UI shows its degraded treatment.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/chat.py backend/tests/test_workflow_state_integrity.py
git commit -m "fix(chat): derive completeness from stage telemetry instead of hardcoding full"
```

---

### Task 5: Full-suite regression check

- [ ] **Step 1:** `cd backend && python -m pytest tests/ -q` — no regressions
  versus baseline.
- [ ] **Step 2:** Replay one full clarification conversation live (ask → answer
  the chip → get results) to confirm halt/resume still works end-to-end after
  Task 2's restructure.
- [ ] **Step 3:** `git commit --allow-empty -m "test: PLAN-8 verified — history delta, moderated resume, no dead evidence step, honest completeness"`
