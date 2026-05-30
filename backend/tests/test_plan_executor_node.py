"""
Tests for plan_executor_node in app/services/langgraph/workflow.py.

Locks in the contract that fields plan_executor.execute() returns in its
results dict — specifically follow_up_question and affiliate_products —
propagate into the LangGraph state update returned by plan_executor_node.
The node builds inner_update field-by-field; any new GraphState field that
needs to flow back from plan_executor must be wired here.

Regression coverage:
  - 2026-05-25: PR #13 fixed _extract_results for follow_up_question but the
    node wrapper dropped the field before it reached GraphState.
  - 2026-05-26: affiliate_products written to self.state by product_affiliate
    was never lifted into results nor included in inner_update, so chat.py
    always read {} and reported amazon/ebay as "unavailable".
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
async def test_node_propagates_transitional_reasoning_from_results():
    """Same node-boundary trap as follow_up_question: the quiz-path transitional
    reasoning must appear in the node's update dict or LangGraph drops it before
    chat.py can emit the SSE event / render the TransitionalBubble."""
    transitional_text = "$200 puts the mid-tier on the table — that changes the pick."
    fake_results = {
        "assistant_text": "Body of the response.",
        "ui_blocks": [],
        "citations": [],
        "next_suggestions": [],
        "tool_citations": [],
        "transitional_reasoning": transitional_text,
    }

    with patch(
        "app.services.langgraph.workflow.PlanExecutor"
    ) as mock_executor_cls:
        mock_executor = mock_executor_cls.return_value
        mock_executor.execute = AsyncMock(return_value=fake_results)

        update = await plan_executor_node(_minimal_state())

    assert "transitional_reasoning" in update, (
        "plan_executor_node must include transitional_reasoning in its update dict."
    )
    assert update["transitional_reasoning"] == transitional_text


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
async def test_node_propagates_affiliate_products_from_results():
    """When plan_executor.execute returns affiliate_products, the node's
    update dict must include it so LangGraph merges it into GraphState.
    Without this, chat.py reads {} and reports amazon/ebay as unavailable."""
    fake_affiliate = {
        "amazon": [{"product_name": "Sony WH-1000XM5", "offers": []}],
        "ebay": [{"product_name": "Sony WH-1000XM5 Used", "offers": []}],
    }
    fake_results = {
        "assistant_text": "Here are the best earbuds.",
        "ui_blocks": [],
        "citations": [],
        "next_suggestions": [],
        "tool_citations": [],
        "affiliate_products": fake_affiliate,
    }

    with patch(
        "app.services.langgraph.workflow.PlanExecutor"
    ) as mock_executor_cls:
        mock_executor = mock_executor_cls.return_value
        mock_executor.execute = AsyncMock(return_value=fake_results)

        update = await plan_executor_node(_minimal_state())

    assert "affiliate_products" in update, (
        "plan_executor_node must include affiliate_products in its returned "
        "update dict. Missing it means chat.py always reads {} and reports "
        "amazon/ebay as unavailable even when the tool produced real results."
    )
    assert update["affiliate_products"] == fake_affiliate


@pytest.mark.asyncio
async def test_node_passes_empty_dict_when_no_affiliate_products():
    """When product_affiliate didn't run or returned nothing, node should
    surface {} (not omit the key) so chat.py's .get() always has a key."""
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

    assert update.get("affiliate_products") == {}


@pytest.mark.asyncio
async def test_fallback_on_timeout_clears_follow_up_question():
    """On hard timeout, the fallback dict replaces results — verify it
    explicitly clears follow_up_question rather than leaking stale state.

    Raises ``asyncio.TimeoutError`` rather than the builtin so this test
    exercises the ``except asyncio.TimeoutError`` branch of
    ``run_stage_with_budget`` (classified ``transient``), which is the
    path the production budget timeout actually takes. The two are
    aliased on Python 3.11+ but distinguishing matters for the error
    classification asserted upstream.
    """
    import asyncio as _asyncio

    async def _timeout(*_args, **_kwargs):
        raise _asyncio.TimeoutError("simulated stage timeout")

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


@pytest.mark.asyncio
async def test_fallback_on_timeout_passes_empty_affiliate_products():
    """On hard timeout the fallback dict must include affiliate_products: {}
    so chat.py's result_state.get('affiliate_products', {}) stays stable."""
    import asyncio as _asyncio

    async def _timeout(*_args, **_kwargs):
        raise _asyncio.TimeoutError("simulated stage timeout")

    with patch(
        "app.services.langgraph.workflow.PlanExecutor"
    ) as mock_executor_cls:
        mock_executor = mock_executor_cls.return_value
        mock_executor.execute = AsyncMock(side_effect=_timeout)

        update = await plan_executor_node(_minimal_state())

    assert "affiliate_products" in update
    assert update["affiliate_products"] == {}
