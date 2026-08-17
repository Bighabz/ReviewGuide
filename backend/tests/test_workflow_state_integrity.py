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


# ---------------------------------------------------------------------------
# Task 2 — resumed messages bypass moderation: the resume branch manufactured
# policy_status="allow" and returned before safety_agent_instance.execute was
# called, so blockable content sent mid-clarification skipped safety entirely.
# ---------------------------------------------------------------------------

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


@pytest.mark.asyncio
async def test_resumed_message_returns_history_delta_too():
    """The old early return skipped the history append entirely — the resume
    path must return the same one-message delta as the normal path."""
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
            "conversation_history": list(PRIOR),
        })

    assert update["conversation_history"] == [
        {"role": "user", "content": "under $800"}
    ]


# ---------------------------------------------------------------------------
# Task 4 — the completeness flag must tell the truth. chat.py:909 hardcoded
# "full" ("degraded logic deferred to a later phase") while the executor-
# timeout fallback said "partial results" in prose. Derived from the stage
# telemetry that already records what actually happened.
# ---------------------------------------------------------------------------

def test_completeness_reflects_stage_timeouts_and_fatal_fallbacks():
    from app.api.v1.chat import _derive_completeness

    full = [{"stage": "safety", "timeout_hit": False, "error_class": None},
            {"stage": "plan_exec", "timeout_hit": False, "error_class": None}]
    timed_out = [{"stage": "plan_exec", "timeout_hit": True, "error_class": "transient"}]
    # Validation catch: a stage can fail fatally WITHOUT a timeout — its
    # fallback ran, so the answer is degraded (stage_telemetry.py: any
    # non-timeout exception stamps error_class="fatal", timeout_hit=False).
    fatal = [{"stage": "plan_exec", "timeout_hit": False, "error_class": "fatal"}]

    assert _derive_completeness(full) == "full"
    assert _derive_completeness(timed_out) == "degraded"
    assert _derive_completeness(fatal) == "degraded"
    assert _derive_completeness([]) == "full"
    assert _derive_completeness(None) == "full"
    # D5 guard: a clarifier timeout alone must NOT degrade the response.
    # D5 is DECIDED (2026-08-17: flip to fail-closed) but the clarifier flip
    # has not landed yet — the exclusion stays until it does, then becomes
    # moot (a fail-closed clarifier timeout re-asks instead of degrading).
    clarifier_only = [{"stage": "clarifier", "timeout_hit": True, "error_class": "transient"}]
    assert _derive_completeness(clarifier_only) == "full"


# ---------------------------------------------------------------------------
# DOCTRINE D5 flips (decided 2026-08-17): failed PROTECTIVE gates fail CLOSED.
# A hung safety stage must never route content through "unchecked"; a timed-out
# clarifier must re-ask, never silently skip clarification (the F6 regression).
# ---------------------------------------------------------------------------

import asyncio


@pytest.mark.asyncio
async def test_safety_timeout_fails_closed(monkeypatch):
    from app.services import stage_telemetry as st

    monkeypatch.setitem(st.STAGE_BUDGETS, "safety", (0.02, 0.05))

    async def _hang(state):
        await asyncio.sleep(2)

    with patch.object(wf.safety_agent_instance, "execute", _hang):
        update = await wf.safety_node({
            "session_id": "s1",
            "user_message": "best espresso machine",
            "conversation_history": [],
        })

    assert update.get("next_agent") is None       # never proceeds unmoderated
    assert update.get("status") == "error"
    assert update.get("assistant_text")           # the user is told to retry


@pytest.mark.asyncio
async def test_clarifier_timeout_reasks_instead_of_skipping(monkeypatch):
    from app.services import stage_telemetry as st

    monkeypatch.setitem(st.STAGE_BUDGETS, "clarifier", (0.02, 0.05))

    async def _hang(state):
        await asyncio.sleep(2)

    with patch.object(wf.clarifier_agent_instance, "execute", _hang):
        update = await wf.clarifier_node({
            "session_id": "s1",
            "user_message": "best espresso machine",
            "slots": {"category": "espresso machines"},
            "plan": {"steps": []},
            "conversation_history": [],
        })

    assert update.get("next_agent") is None       # never proceeds as-is
    assert update.get("status") == "halted"
    assert update.get("assistant_text")           # the user is re-asked
