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
