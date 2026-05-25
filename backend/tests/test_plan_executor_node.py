"""
Tests for plan_executor_node in app/services/langgraph/workflow.py.

Locks in the contract that fields plan_executor.execute() returns in its
results dict — specifically follow_up_question — propagate into the
LangGraph state update returned by plan_executor_node. The node builds
inner_update field-by-field; any new GraphState field that needs to flow
back from plan_executor must be wired here.

Regression coverage for the 2026-05-25 bug where PR #13 fixed
_extract_results but the node wrapper dropped the field before it reached
GraphState, so chat.py's SSE emission never fired.
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("ADMIN_PASSWORD", "testpassword123")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

import pytest

from app.services.langgraph.workflow import plan_executor_node


def _minimal_state(**overrides):
    """Smallest state shape the node will accept without errors."""
    base = {
        "plan": {"steps": [{"id": "compose", "tools": ["product_compose"]}]},
        "slots": {},
        "user_message": "best wireless earbuds under $100",
        "intent": "product",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_node_propagates_follow_up_question_from_results():
    """When plan_executor.execute returns follow_up_question, the node's
    update dict must include it so LangGraph merges it into GraphState."""
    follow_up_text = "Want me to dig into noise cancellation specifically?"
    fake_results = {
        "assistant_text": "Body of the response.",
        "ui_blocks": [],
        "citations": [],
        "next_suggestions": [],
        "tool_citations": [],
        "follow_up_question": follow_up_text,
    }

    with patch(
        "app.services.langgraph.workflow.PlanExecutor"
    ) as mock_executor_cls:
        mock_executor = mock_executor_cls.return_value
        mock_executor.execute = AsyncMock(return_value=fake_results)

        update = await plan_executor_node(_minimal_state())

    assert "follow_up_question" in update, (
        "plan_executor_node must include follow_up_question in its returned "
        "update dict. Missing it silently drops the value before LangGraph "
        "merges it into GraphState, breaking chat.py's SSE event emission."
    )
    assert update["follow_up_question"] == follow_up_text


@pytest.mark.asyncio
async def test_node_passes_through_none_when_no_follow_up():
    """Composer didn't emit a follow-up — node should surface None (not omit
    the key entirely) so downstream `.get('follow_up_question')` sees the
    same default whether the field is absent or explicitly cleared."""
    fake_results = {
        "assistant_text": "Body.",
        "ui_blocks": [],
        "citations": [],
        "next_suggestions": [],
        "tool_citations": [],
    }

    with patch(
        "app.services.langgraph.workflow.PlanExecutor"
    ) as mock_executor_cls:
        mock_executor = mock_executor_cls.return_value
        mock_executor.execute = AsyncMock(return_value=fake_results)

        update = await plan_executor_node(_minimal_state())

    assert update.get("follow_up_question") is None


@pytest.mark.asyncio
async def test_fallback_on_timeout_clears_follow_up_question():
    """On hard timeout, the fallback dict replaces results — verify it
    explicitly clears follow_up_question rather than leaking stale state."""
    from app.services.langgraph import workflow as workflow_module

    async def _timeout(*_args, **_kwargs):
        raise TimeoutError("simulated stage timeout")

    with patch(
        "app.services.langgraph.workflow.PlanExecutor"
    ) as mock_executor_cls:
        mock_executor = mock_executor_cls.return_value
        mock_executor.execute = AsyncMock(side_effect=_timeout)

        update = await plan_executor_node(_minimal_state())

    # The fallback path returns a degraded message; key must be present
    # so chat.py's `result_state.get("follow_up_question")` returns None
    # cleanly on the timeout path too.
    assert "follow_up_question" in update
    assert update["follow_up_question"] is None
