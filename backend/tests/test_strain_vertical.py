"""Cannabis strain vertical — SmartVape engine integration.

QA 2026-06-10: "sour d vs blue dream" got plain strain education with no
product flow — no pick, no shortlist, no cards. ReviewGuide can't SELL
cannabis through its affiliate stack, but it can own the verdict: the vendored
SmartVape engine (1054 strains, terpene + effect profiles, multi-factor
recommendation) powers a strain_search → strain_compose plan whose cards link
OUT to Leafly (their age gate, our recommendation).

Pins:
1. is_strain_query detection — keywords, strain-name pairs, vs-comparisons;
   no false positive on ordinary product queries ("wedding cake stand").
2. strain_search — comparison / similar / mood modes, Leafly link on every
   result.
3. strain_compose — verdict prose + product_review cards (LLM mocked),
   deterministic fallback when the LLM fails, tone: no competitor citation
   needed since SmartVape data is ours.
4. Planner routes detected strain queries to the strain plan regardless of
   classified intent.
"""
import json
import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

from unittest.mock import AsyncMock, patch  # noqa: E402

import pytest  # noqa: E402

from app.services.smartvape import get_engine, is_strain_query, leafly_url  # noqa: E402
from mcp_server.tools.strain_search import strain_search  # noqa: E402
from mcp_server.tools.strain_compose import strain_compose  # noqa: E402


# ---------------------------------------------------------------------------
# Engine + helpers
# ---------------------------------------------------------------------------

def test_engine_loads_strain_database():
    engine = get_engine()
    assert engine.get_stats()["total_strains"] > 1000
    # Singleton: second call returns the same instance (no re-parse)
    assert get_engine() is engine


def test_leafly_url_is_always_a_working_search_link():
    url = leafly_url("Blue Dream")
    assert url.startswith("https://www.leafly.com/search?q=")
    assert "Blue%20Dream" in url or "Blue+Dream" in url


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("query", [
    "sour d vs blue dream",
    "indica vs sativa",
    "best strains for sleep",
    "what weed should i smoke for focus",
    "blue dream vs sour diesel for anxiety",
    "something with myrcene terpenes to relax",
])
def test_strain_queries_detected(query):
    assert is_strain_query(query) is True


@pytest.mark.parametrize("query", [
    "best laptop under $1000",
    "nike vs adidas sneakers",
    "wedding cake stand for a 3-tier cake",   # strain name in a baking query
    "gelato maker for home use",              # strain name in an appliance query
    "what is the capital of France",
    "ford vs chevy truck",
])
def test_non_strain_queries_not_detected(query):
    assert is_strain_query(query) is False


# ---------------------------------------------------------------------------
# strain_search tool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_strain_search_comparison_mode():
    """'sour d vs blue dream' resolves both sides (partial names included)
    and returns them as the head of the results."""
    result = await strain_search({"user_message": "sour d vs blue dream", "slots": {}})

    assert result["success"] is True
    names = [s["name"].lower() for s in result["strain_results"]]
    assert any("sour diesel" in n for n in names), f"Sour Diesel missing from {names[:5]}"
    assert any("blue dream" in n for n in names), f"Blue Dream missing from {names[:5]}"
    assert result["strain_mode"] == "comparison"


@pytest.mark.asyncio
async def test_strain_search_mood_mode():
    result = await strain_search({"user_message": "best strains to help me sleep", "slots": {}})

    assert result["success"] is True
    assert len(result["strain_results"]) >= 3
    assert result["strain_mode"] == "recommend"
    # Sleep intent must actually shape the results
    top = result["strain_results"][0]
    effects = " ".join(top.get("feelings", []) + top.get("helps_with", [])).lower()
    assert "sleep" in effects or "insomnia" in effects


@pytest.mark.asyncio
async def test_strain_search_results_carry_leafly_links():
    result = await strain_search({"user_message": "indica vs sativa", "slots": {}})
    for s in result["strain_results"]:
        assert s.get("leafly_url", "").startswith("https://www.leafly.com/"), (
            f"every strain result needs a Leafly link-out: {s.get('name')}"
        )


# ---------------------------------------------------------------------------
# strain_compose tool
# ---------------------------------------------------------------------------

_STRAIN_RESULTS = [
    {
        "name": "Blue Dream", "strain_type": "Hybrid",
        "dominant_terpene": "Myrcene",
        "feelings": ["Happy", "Relaxed", "Euphoric"],
        "helps_with": ["Stress", "Depression"],
        "score": 0.92, "match_reasons": ["Produces: Relaxed"],
        "leafly_url": "https://www.leafly.com/search?q=Blue%20Dream",
    },
    {
        "name": "Sour Diesel", "strain_type": "Sativa",
        "dominant_terpene": "Caryophyllene",
        "feelings": ["Energetic", "Uplifted"],
        "helps_with": ["Fatigue", "Stress"],
        "score": 0.88, "match_reasons": ["Produces: Energetic"],
        "leafly_url": "https://www.leafly.com/search?q=Sour%20Diesel",
    },
]

_BLOG_JSON = json.dumps({
    "body": "For winding down, Blue Dream is the pick — the myrcene lean does the heavy lifting.",
    "follow_up_question": "Is this for evenings, or do you need to stay functional?",
    "top_pick": "Blue Dream",
})


@pytest.mark.asyncio
async def test_strain_compose_builds_cards_with_leafly_links():
    state = {
        "user_message": "sour d vs blue dream",
        "strain_results": _STRAIN_RESULTS,
        "strain_mode": "comparison",
        "slots": {},
        "conversation_history": [],
    }
    with patch(
        "app.services.model_service.model_service.generate_compose",
        new=AsyncMock(return_value=_BLOG_JSON),
    ):
        result = await strain_compose(state)

    assert result["success"] is True
    assert "Blue Dream" in result["assistant_text"]
    assert result.get("follow_up_question")

    cards = [b for b in result["ui_blocks"] if b["type"] == "product_review"]
    assert len(cards) == 2
    blocks_json = json.dumps(result["ui_blocks"])
    assert "leafly.com" in blocks_json
    # Top pick leads the cards
    assert cards[0]["data"]["product_name"] == "Blue Dream"


@pytest.mark.asyncio
async def test_strain_compose_degrades_without_llm():
    state = {
        "user_message": "strains for sleep",
        "strain_results": _STRAIN_RESULTS,
        "strain_mode": "recommend",
        "slots": {},
        "conversation_history": [],
    }
    with patch(
        "app.services.model_service.model_service.generate_compose",
        new=AsyncMock(side_effect=Exception("LLM down")),
    ):
        result = await strain_compose(state)

    assert result["success"] is True
    assert result["assistant_text"].strip(), "fallback prose required"
    assert [b for b in result["ui_blocks"] if b["type"] == "product_review"]


@pytest.mark.asyncio
async def test_strain_compose_no_results_is_honest():
    result = await strain_compose({
        "user_message": "strains", "strain_results": [], "slots": {},
        "conversation_history": [],
    })
    assert result["success"] is True
    assert result["assistant_text"].strip()
    assert result["ui_blocks"] == []


# ---------------------------------------------------------------------------
# Planner routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_planner_routes_strain_queries_to_strain_plan():
    """Strain queries get the strain plan even when intent classified them
    as 'general' (the QA failure mode)."""
    from app.agents.planner_agent import PlannerAgent

    agent = PlannerAgent()
    state = {
        "user_message": "sour d vs blue dream",
        "intent": "general",
        "slots": {},
        "conversation_history": [],
    }
    result = await agent.execute(state)

    tools = [t for step in result["plan"]["steps"] for t in step.get("tools", [])]
    assert "strain_search" in tools
    assert "strain_compose" in tools
