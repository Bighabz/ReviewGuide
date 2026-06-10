"""Cannabis strain vertical — SmartVape engine + AI-driven routing.

QA 2026-06-10: "sour d vs blue dream" got plain strain education with no
product flow. The vendored SmartVape engine (1054 strains) powers a
strain_search → strain_compose plan whose cards link OUT to Leafly.

Routing and query understanding are AI-driven (per Habib, 2026-06-10 — no
deterministic keyword detector):
- the intent classifier owns strain detection via a "strain" category
- strain_search asks an LLM to extract named strains / feelings / conditions
  / strain type from the message, then the SmartVape engine ranks
- live Leafly page URLs + snippets come from Serper (no Leafly API key
  needed); the search-URL fallback covers Serper-off environments
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

from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

import pytest  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.services.smartvape import get_engine, leafly_url  # noqa: E402
from mcp_server.tools.strain_search import strain_search  # noqa: E402
from mcp_server.tools.strain_compose import strain_compose  # noqa: E402


# ---------------------------------------------------------------------------
# Engine + helpers
# ---------------------------------------------------------------------------

def test_engine_loads_strain_database():
    engine = get_engine()
    assert engine.get_stats()["total_strains"] > 1000
    assert get_engine() is engine  # singleton


def test_leafly_url_is_always_a_working_search_link():
    url = leafly_url("Blue Dream")
    assert url.startswith("https://www.leafly.com/search?q=")
    assert "Blue%20Dream" in url or "Blue+Dream" in url


# ---------------------------------------------------------------------------
# AI routing: the intent classifier owns strain detection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_intent_prompt_offers_strain_category():
    from app.agents.intent_agent import IntentAgent

    agent = IntentAgent()
    captured = {}

    async def fake_generate(messages, **kwargs):
        captured["messages"] = messages
        return json.dumps({"intent": "strain"})

    agent.generate = fake_generate
    result = await agent._quick_intent_classification("sour d vs blue dream")

    system_prompt = captured["messages"][0]["content"]
    assert "strain" in system_prompt, "classifier must be offered the strain category"
    assert result["intent"] == "strain"


@pytest.mark.asyncio
async def test_intent_node_routes_strain_to_planner():
    from app.agents.intent_agent import intent_agent_node

    agent = MagicMock()
    agent.execute = AsyncMock(return_value={"intent": "strain"})
    state = MagicMock()

    result = await intent_agent_node(state, agent)
    assert result.next_agent == "planner"


@pytest.mark.asyncio
async def test_workflow_intent_node_routes_strain_to_planner():
    """The LIVE graph uses workflow.py's intent_node, which carries its OWN
    intent whitelist (duplicate of intent_agent_node's). Caught in prod
    2026-06-10: 'strain' passed the agent-side whitelist but the workflow
    node's copy rejected it — 'I'm not sure how to help with that.'"""
    from app.services.langgraph import workflow as wf

    with patch.object(wf.intent_agent_instance, "execute", new=AsyncMock(return_value={"intent": "strain"})), \
         patch("app.services.halt_state_manager.HaltStateManager.get_halt_state", new=AsyncMock(return_value=None)):
        update = await wf.intent_node({
            "sanitized_text": "sour d vs blue dream",
            "user_message": "sour d vs blue dream",
            "session_id": "test-session",
        })

    assert update.get("next_agent") == "planner", (
        f"workflow intent_node rejected strain intent: {update.get('assistant_text')}"
    )
    assert update.get("status") != "error"


@pytest.mark.asyncio
async def test_planner_routes_strain_intent_to_strain_plan():
    from app.agents.planner_agent import PlannerAgent

    agent = PlannerAgent()
    state = {
        "user_message": "sour d vs blue dream",
        "intent": "strain",
        "slots": {},
        "conversation_history": [],
    }
    result = await agent.execute(state)

    tools = [t for step in result["plan"]["steps"] for t in step.get("tools", [])]
    assert "strain_search" in tools
    assert "strain_compose" in tools


# ---------------------------------------------------------------------------
# strain_search: LLM extraction → engine ranking
# ---------------------------------------------------------------------------

def _extraction(named=None, feelings=None, conditions=None, strain_type=None):
    return json.dumps({
        "named_strains": named or [],
        "feelings": feelings or [],
        "conditions": conditions or [],
        "strain_type": strain_type,
    })


def _no_serper(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_SERPAPI", False)


@pytest.mark.asyncio
async def test_strain_search_asks_llm_to_parse_the_query(monkeypatch):
    """The query is parsed by the LLM, not keyword matching — the raw message
    goes to the model and its JSON answer drives the engine."""
    _no_serper(monkeypatch)
    captured = {}

    async def fake_generate(messages, **kwargs):
        captured["messages"] = messages
        return _extraction(named=["Sour Diesel", "Blue Dream"])

    with patch("app.services.model_service.model_service.generate", new=fake_generate):
        result = await strain_search({"user_message": "sour d vs blue dream", "slots": {}})

    assert "sour d vs blue dream" in json.dumps(captured["messages"])
    assert result["strain_mode"] == "comparison"
    names = [s["name"].lower() for s in result["strain_results"]]
    assert any("sour diesel" in n for n in names)
    assert any("blue dream" in n for n in names)


@pytest.mark.asyncio
async def test_strain_search_mood_mode_from_llm_extraction(monkeypatch):
    _no_serper(monkeypatch)
    with patch(
        "app.services.model_service.model_service.generate",
        new=AsyncMock(return_value=_extraction(feelings=["Sleepy"], conditions=["Insomnia"])),
    ):
        result = await strain_search({"user_message": "best strains to help me sleep", "slots": {}})

    assert result["strain_mode"] == "recommend"
    assert len(result["strain_results"]) >= 3
    top = result["strain_results"][0]
    effects = " ".join(top.get("feelings", []) + top.get("helps_with", [])).lower()
    assert "sleep" in effects or "insomnia" in effects


@pytest.mark.asyncio
async def test_strain_search_survives_llm_failure(monkeypatch):
    """Extraction LLM down → still returns a sensible recommendation set."""
    _no_serper(monkeypatch)
    with patch(
        "app.services.model_service.model_service.generate",
        new=AsyncMock(side_effect=Exception("LLM down")),
    ):
        result = await strain_search({"user_message": "indica vs sativa", "slots": {}})

    assert result["success"] is True
    assert len(result["strain_results"]) >= 3


@pytest.mark.asyncio
async def test_strain_search_results_carry_leafly_links(monkeypatch):
    _no_serper(monkeypatch)
    with patch(
        "app.services.model_service.model_service.generate",
        new=AsyncMock(return_value=_extraction(feelings=["Relaxed"])),
    ):
        result = await strain_search({"user_message": "something relaxing", "slots": {}})

    for s in result["strain_results"]:
        assert s.get("leafly_url", "").startswith("https://www.leafly.com/")


# ---------------------------------------------------------------------------
# Serper enrichment: real Leafly page URLs + live snippets, no API key needed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_serper_enrichment_upgrades_links_and_snippets(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_SERPAPI", True)
    monkeypatch.setattr(settings, "SERPAPI_API_KEY", "test-key")

    fake_client_cls = MagicMock()
    fake_client_cls.return_value.search_strain_info = AsyncMock(return_value={
        "url": "https://www.leafly.com/strains/blue-dream",
        "snippet": "Blue Dream is a sativa-dominant hybrid with 4.4 stars from 13k reviews.",
        "title": "Blue Dream",
    })

    with patch(
        "app.services.model_service.model_service.generate",
        new=AsyncMock(return_value=_extraction(named=["Blue Dream"])),
    ), patch("app.services.serpapi.client.SerpAPIClient", fake_client_cls):
        result = await strain_search({"user_message": "tell me about blue dream", "slots": {}})

    top = result["strain_results"][0]
    assert top["leafly_url"] == "https://www.leafly.com/strains/blue-dream"
    assert "4.4 stars" in top.get("leafly_snippet", "")


@pytest.mark.asyncio
async def test_serper_failure_keeps_search_url_fallback(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_SERPAPI", True)
    monkeypatch.setattr(settings, "SERPAPI_API_KEY", "test-key")

    fake_client_cls = MagicMock()
    fake_client_cls.return_value.search_strain_info = AsyncMock(side_effect=Exception("serper down"))

    with patch(
        "app.services.model_service.model_service.generate",
        new=AsyncMock(return_value=_extraction(named=["Blue Dream"])),
    ), patch("app.services.serpapi.client.SerpAPIClient", fake_client_cls):
        result = await strain_search({"user_message": "tell me about blue dream", "slots": {}})

    assert result["strain_results"][0]["leafly_url"].startswith("https://www.leafly.com/search?q=")


# ---------------------------------------------------------------------------
# strain_compose (unchanged contract)
# ---------------------------------------------------------------------------

_STRAIN_RESULTS = [
    {
        "name": "Blue Dream", "strain_type": "Hybrid",
        "dominant_terpene": "Myrcene",
        "feelings": ["Happy", "Relaxed", "Euphoric"],
        "helps_with": ["Stress", "Depression"],
        "score": 0.92, "match_reasons": ["Produces: Relaxed"],
        "leafly_url": "https://www.leafly.com/strains/blue-dream",
        "leafly_snippet": "Sativa-dominant hybrid, 4.4 stars.",
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
    assert "leafly.com" in json.dumps(result["ui_blocks"])
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
    assert result["assistant_text"].strip()
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
