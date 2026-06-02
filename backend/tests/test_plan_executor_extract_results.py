"""
Unit tests for PlanExecutor._extract_results (plan_executor.py).

Locks in the contract that affiliate_products stored in self.state by
_write_tool_outputs_to_state (from product_affiliate) is lifted into
the returned results dict so plan_executor_node can propagate it into
GraphState.

Regression coverage for the 2026-05-26 bug: product_affiliate wrote
affiliate_products to self.state via in-place mutation, but _extract_results
only scanned self.context for compose-tool output. affiliate_products was
never included in results, inner_update, or GraphState. chat.py then read {}
and reported amazon/ebay as "unavailable" even when the tool produced results.
"""
from __future__ import annotations

import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("ADMIN_PASSWORD", "testpassword123")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

import pytest
from unittest.mock import patch, MagicMock

from app.services.plan_executor import PlanExecutor


def _executor_with_compose_result(extra_state: dict = None) -> PlanExecutor:
    """Return a PlanExecutor whose context has a product_compose result."""
    executor = PlanExecutor()
    executor.context = {
        "step_1.product_compose": {
            "assistant_text": "Here are the best earbuds.",
            "ui_blocks": [],
            "citations": [],
            "success": True,
        }
    }
    executor.state = extra_state or {}
    return executor


class TestExtractResultsAffiliateProducts:
    def test_affiliate_products_lifted_from_state(self):
        """_extract_results must include affiliate_products when self.state has it."""
        affiliate_data = {
            "amazon": [{"product_name": "Sony WH-1000XM5", "offers": []}],
            "ebay": [{"product_name": "Sony WH-1000XM5 Used", "offers": []}],
        }
        executor = _executor_with_compose_result(
            extra_state={"affiliate_products": affiliate_data}
        )

        results = executor._extract_results()

        assert "affiliate_products" in results, (
            "_extract_results must lift affiliate_products from self.state. "
            "Without this, plan_executor_node's inner_update cannot include it "
            "and chat.py always reads {} — marking amazon/ebay as unavailable."
        )
        assert results["affiliate_products"] == affiliate_data

    def test_affiliate_products_absent_when_state_empty(self):
        """When product_affiliate never ran, self.state has no affiliate_products;
        _extract_results should not include the key (falsy guard prevents it)."""
        executor = _executor_with_compose_result(extra_state={})

        results = executor._extract_results()

        # Key absent OR value is falsy — either is acceptable; chat.py handles both.
        assert not results.get("affiliate_products"), (
            "affiliate_products should not be populated when self.state has none."
        )

    def test_affiliate_products_not_overwritten_by_empty_dict(self):
        """An explicitly empty affiliate_products dict in state should not be
        surfaced — the `if self.state.get(...)` guard keeps results clean."""
        executor = _executor_with_compose_result(
            extra_state={"affiliate_products": {}}
        )

        results = executor._extract_results()

        assert not results.get("affiliate_products")

    def test_affiliate_products_independent_of_follow_up_question(self):
        """Both affiliate_products and follow_up_question can be present
        simultaneously without either being dropped."""
        affiliate_data = {"amazon": [{"product_name": "AirPods", "offers": []}]}
        executor = _executor_with_compose_result(
            extra_state={"affiliate_products": affiliate_data}
        )
        executor.context["step_1.product_compose"]["follow_up_question"] = (
            "Are you leaning toward noise cancellation or sound quality?"
        )

        results = executor._extract_results()

        assert results.get("affiliate_products") == affiliate_data
        assert results.get("follow_up_question") == (
            "Are you leaning toward noise cancellation or sound quality?"
        )


class TestExtractResultsSearchContext:
    """Outcome 2 (refinement chips): last_search_context + search_history built by
    product_compose must be lifted into results so they can persist across turns."""

    def test_last_search_context_lifted_from_compose_result(self):
        ctx = {
            "category": "headphones",
            "product_names": ["Sony WH-1000XM5", "Bose QC45"],
            "top_prices": {"Sony WH-1000XM5": 149.99, "Bose QC45": 169.0},
            "budget": "under $200",
        }
        executor = _executor_with_compose_result()
        executor.context["step_1.product_compose"]["last_search_context"] = ctx

        results = executor._extract_results()

        assert results.get("last_search_context") == ctx, (
            "_extract_results must lift last_search_context from the compose result. "
            "Without it, the search context never persists and refinement chips "
            "('Show cheaper options') have nothing to adjust."
        )

    def test_search_history_lifted_from_compose_result(self):
        history = [{"category": "laptops", "product_names": ["Dell XPS 13"]}]
        executor = _executor_with_compose_result()
        executor.context["step_1.product_compose"]["search_history"] = history

        results = executor._extract_results()

        assert results.get("search_history") == history

    def test_context_absent_when_compose_has_none(self):
        executor = _executor_with_compose_result()

        results = executor._extract_results()

        assert not results.get("last_search_context")
        assert not results.get("search_history")
