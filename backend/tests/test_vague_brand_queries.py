"""QA remediation — vague brand queries fabricate wrong-category products.

Observed in QA (2026-06-10): "shoul i go ford or chevy" returned Ford v Ferrari
Blu-rays, Tom Ford perfumes, and Hot Wheels toys. Root cause is two-layered:

1. The clarifier's brand-without-category rule only fired for ~15 hardcoded
   brands (Dyson, Shark, ...) — Ford/Chevy sailed straight to execution with
   zero category signal.
2. product_search's name-generator LLM was instructed to "NEVER refuse", so
   with no category constraint it fabricated 5-8 names containing "Ford"
   literally, and those went verbatim into retailer searches.

These tests pin both layers: ANY brand-only query asks the category question,
and the generator may return an empty list when no buyable product type is
identifiable instead of inventing one.
"""
import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

import json  # noqa: E402
from unittest.mock import AsyncMock, patch  # noqa: E402

import pytest  # noqa: E402

from app.agents.clarifier_agent import ClarifierAgent  # noqa: E402
from mcp_server.tools.product_search import product_search  # noqa: E402


@pytest.fixture
def agent():
    return ClarifierAgent()


CATEGORY_QUESTION_RESPONSE = {
    "intro": "Happy to help you choose.",
    "questions": [
        {"slot": "category", "question": "Are you comparing Ford vs Chevy trucks, SUVs, or something else?",
         "options": ["Trucks", "SUVs", "Sedans"]},
    ],
    "closing": "",
}


def _new_plan_state(message, slots=None):
    return {
        "user_message": message,
        "sanitized_text": message,
        "intent": "product",
        "slots": dict(slots or {}),
        "session_id": "test-session",
        "conversation_history": [{"role": "user", "content": message}],
        "last_search_context": {},
        "plan": {"steps": [{"id": "step_1", "tools": ["product_search"], "parallel": False}]},
        "metadata": {},
    }


# ---------------------------------------------------------------------------
# Layer 1: clarifier requires a category for ANY brand-only query
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_brand_only_query_requires_category(agent):
    """Ford/Chevy are not in any curated ambiguous-brand list — the category
    question must fire for any brand without a category/product_name anyway."""
    agent._extract_all_slots_from_conversation = AsyncMock(
        return_value={"brand": "Ford, Chevy"}
    )
    agent._generate_followup_questions = AsyncMock(return_value=CATEGORY_QUESTION_RESPONSE)

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        result = await agent._handle_new_plan(
            _new_plan_state("shoul i go ford or chevy"), "test-session"
        )

    assert result["proceed_to_execution"] is False, (
        "brand-only query must halt for category clarification, not run the search"
    )
    assert "category" in result["missing_required_slots"]


@pytest.mark.asyncio
async def test_brand_with_category_does_not_ask_category(agent):
    """'nike vs adidas sneakers' has a category — no category question."""
    agent._extract_all_slots_from_conversation = AsyncMock(
        return_value={"brand": "Nike, Adidas", "category": "sneakers"}
    )
    agent._generate_followup_questions = AsyncMock(return_value={
        "intro": "x", "questions": [{"slot": "use_case", "question": "u?"}], "closing": "",
    })

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        result = await agent._handle_new_plan(
            _new_plan_state("nike vs adidas sneakers"), "test-session"
        )

    assert "category" not in result["missing_required_slots"]


# ---------------------------------------------------------------------------
# Layer 2: product_search generator must not fabricate when category unknown
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_product_search_prompt_drops_never_refuse():
    """The generator prompt must not mandate fabrication; it must instead carry
    an escape hatch for queries with no identifiable buyable product type."""
    captured = {}

    async def fake_generate(messages, **kwargs):
        captured["messages"] = messages
        return json.dumps({"products": []})

    with patch("app.services.model_service.model_service.generate", new=fake_generate):
        await product_search({"user_message": "shoul i go ford or chevy", "slots": {}})

    full_prompt = "\n".join(m["content"] for m in captured["messages"])
    assert "NEVER refuse" not in full_prompt
    assert '"products": []' in full_prompt, "prompt must show the empty-list escape hatch"


@pytest.mark.asyncio
async def test_product_search_handles_empty_product_list():
    """LLM exercising the escape hatch yields an empty, successful result —
    downstream tools skip gracefully instead of searching garbage names."""
    with patch(
        "app.services.model_service.model_service.generate",
        new=AsyncMock(return_value=json.dumps({"products": []})),
    ):
        result = await product_search({"user_message": "shoul i go ford or chevy", "slots": {}})

    assert result["success"] is True
    assert result["product_names"] == []
