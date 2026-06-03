"""Tests for USE_REVIEW_GROUNDING (Tier 5 / A1).

The standard product plan (recommendation/comparison) skips review_search by
default, so the composer writes with no real review evidence (concierge path).
When USE_REVIEW_GROUNDING is on, the planner must insert a review_search step
between product_search and product_normalize so review_data reaches the composer
(editorial path). These tests assert that wiring with zero network calls — the
plan-builder methods are pure.
"""

import pytest

from app.agents.planner_agent import PlannerAgent


@pytest.fixture
def agent():
    return PlannerAgent()


def _ordered_tools(plan):
    """Flatten a plan into its step-by-step list of tool-lists (in order)."""
    return [step["tools"] for step in plan["steps"]]


def _has_tool(plan, tool):
    return any(tool in step["tools"] for step in plan["steps"])


@pytest.mark.parametrize("complexity", ["recommendation", "comparison"])
def test_review_search_absent_when_flag_off(agent, monkeypatch, complexity):
    monkeypatch.setattr(agent.settings, "USE_REVIEW_GROUNDING", False)
    plan = agent._get_product_plan_for_complexity(complexity)
    assert not _has_tool(plan, "review_search")


@pytest.mark.parametrize("complexity", ["recommendation", "comparison"])
def test_review_search_present_when_flag_on(agent, monkeypatch, complexity):
    monkeypatch.setattr(agent.settings, "USE_REVIEW_GROUNDING", True)
    plan = agent._get_product_plan_for_complexity(complexity)
    assert _has_tool(plan, "review_search")


@pytest.mark.parametrize("complexity", ["recommendation", "comparison"])
def test_review_search_runs_after_search_before_normalize(agent, monkeypatch, complexity):
    """review_search's TOOL_CONTRACT requires product_search before it and
    product_normalize after it (it enriches the products normalize merges)."""
    monkeypatch.setattr(agent.settings, "USE_REVIEW_GROUNDING", True)
    plan = agent._get_product_plan_for_complexity(complexity)

    def step_index(tool):
        for i, step in enumerate(plan["steps"]):
            if tool in step["tools"]:
                return i
        raise AssertionError(f"{tool} not in plan")

    search_i = step_index("product_search")
    review_i = step_index("review_search")
    normalize_i = step_index("product_normalize")
    assert search_i < review_i < normalize_i
    # review_search is its own sequential step immediately before normalize.
    assert plan["steps"][review_i]["tools"] == ["review_search"]
    assert review_i + 1 == normalize_i


def test_flag_off_plan_is_unchanged(agent, monkeypatch):
    """Default-off must be a strict no-op: the recommendation plan keeps its
    exact tool order (search∥evidence → normalize → affiliate → ranking → compose),
    with next_step_suggestion appended. product_ranking joined the standard plan
    in Outcome 9 (budget-aware value ranking) — it runs after affiliate so it can
    see real offer prices, before compose so the composer mirrors its order."""
    monkeypatch.setattr(agent.settings, "USE_REVIEW_GROUNDING", False)
    plan = agent._get_product_plan_for_complexity("recommendation")
    assert _ordered_tools(plan) == [
        ["product_search", "product_evidence"],
        ["product_normalize"],
        ["product_affiliate"],
        ["product_ranking"],
        ["product_compose"],
        ["next_step_suggestion"],
    ]


def test_flag_on_only_inserts_review_search(agent, monkeypatch):
    """Flag-on must add exactly the review_search step and nothing else — the
    rest of the recommendation pipeline is identical to flag-off."""
    monkeypatch.setattr(agent.settings, "USE_REVIEW_GROUNDING", True)
    plan = agent._get_product_plan_for_complexity("recommendation")
    assert _ordered_tools(plan) == [
        ["product_search", "product_evidence"],
        ["review_search"],
        ["product_normalize"],
        ["product_affiliate"],
        ["product_ranking"],
        ["product_compose"],
        ["next_step_suggestion"],
    ]


def test_ranking_runs_after_affiliate_before_compose(agent, monkeypatch):
    """Outcome 9: product_ranking needs affiliate prices (after affiliate) and
    must finish before compose (which mirrors its value order)."""
    for flag in (False, True):
        monkeypatch.setattr(agent.settings, "USE_REVIEW_GROUNDING", flag)
        for complexity in ("recommendation", "comparison"):
            plan = agent._get_product_plan_for_complexity(complexity)

            def step_index(tool):
                for i, step in enumerate(plan["steps"]):
                    if tool in step["tools"]:
                        return i
                raise AssertionError(f"{tool} not in plan")

            assert step_index("product_affiliate") < step_index("product_ranking") < step_index("product_compose")


def test_step_ids_are_unique_and_sequential(agent, monkeypatch):
    """Inserting a step must not duplicate or skip step ids."""
    monkeypatch.setattr(agent.settings, "USE_REVIEW_GROUNDING", True)
    plan = agent._get_product_plan_for_complexity("comparison")
    ids = [step["id"] for step in plan["steps"] if step["id"].startswith("step_")]
    assert len(ids) == len(set(ids)), f"duplicate step ids: {ids}"
