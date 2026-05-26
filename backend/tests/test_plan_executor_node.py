"""
Tests for plan_executor_node in app/services/langgraph/workflow.py.

Locks in the contract that fields plan_executor.execute() returns in its
results dict propagate into the LangGraph state update returned by
plan_executor_node. The node builds inner_update field-by-field; any new
GraphState field that needs to flow back from plan_executor must be wired
here.

Regression coverage for two passthrough bugs:
- 2026-05-25: PR #13 fixed _extract_results for follow_up_question but the
  node wrapper dropped the field before it reached GraphState, so chat.py's
  SSE emission never fired.
- 2026-05-26: affiliate_products written by product_affiliate to executor.state
  was never lifted into _extract_results' return dict, so chat.py always read
  {} and reported amazon/ebay as "unavailable" even when the tool found results.
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
async def test_node_propagates_affiliate_products_from_results():
    """When _extract_results surfaces affiliate_products from executor.state,
    the node's inner_update must include it so LangGraph merges it into
    GraphState and chat.py can build an accurate provider_coverage entry.

    Regression: product_affiliate writes affiliate_products to executor.state
    in-place; it never appears in the compose tool's output dict. Before the
    fix, _extract_results never included it in results{}, so inner_update's
    `results.get("affiliate_products", {})` always returned {} — causing
    chat.py to report amazon/ebay as result_count:0 / "unavailable" even when
    the tool found 7+ results per provider."""
    fake_affiliate = {
        "amazon": [{"product_name": "Sony WH-1000XM5", "offers": [{"price": 279.99}]}],
        "ebay": [{"product_name": "Sony WH-1000XM5", "offers": [{"price": 249.99}]}],
    }
    fake_results = {
        "assistant_text": "Here are the best options.",
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
        "update dict. Missing it means chat.py reads {} from GraphState and "
        "marks every provider as unavailable in provider_coverage."
    )
    assert update["affiliate_products"] == fake_affiliate


@pytest.mark.asyncio
async def test_node_returns_empty_dict_when_no_affiliate_products():
    """When no affiliate_products in results (non-product intent or tool
    skipped), the node should return {} — not omit the key — so downstream
    GraphState always has a consistent type for the field."""
    fake_results = {
        "assistant_text": "Here is some general info.",
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
