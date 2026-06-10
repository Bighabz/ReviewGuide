"""QA remediation — composer text contradicting the product cards.

Observed in QA (2026-06-10): when search retrieved garbage ("Ford v Ferrari"
Blu-ray on a vehicle query), the blog prose acknowledged the results were wrong
("This product list is a mess...") but the cards still rendered — even crowning
an irrelevant item Pick #1. The composer is the only stage that reads the full
product list against the user's ask, so it now emits the verdict that gates the
cards: an ``irrelevant_products`` list in its structured output, which
product_compose applies BEFORE any ui_block is assembled (cards, consensus,
and the blog-mention fallback cards alike).

The instruction is appended to the role at the CALL SITE only — blog_role
itself stays byte-pinned by the eval prod-sync test.
"""
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

from app.core.config import settings
from mcp_server.tools.product_compose import product_compose


def _offer(name, price, slug, source="amazon"):
    return {
        "title": name, "price": price, "currency": "USD",
        "url": f"https://www.amazon.com/dp/{slug}?tag=revguide-20",
        "merchant": "Amazon",
        "image_url": f"https://img.example.com/{slug}.jpg",
        "source": source,
    }


def _base_state(**overrides):
    state = {
        "user_message": "ford vs chevy truck",
        "intent": "product",
        "slots": {"category": "trucks"},
        "normalized_products": [
            {"name": "Ford F-150 Lightning", "price": 54999, "url": "https://example.com/f150"},
            {"name": "Ford v Ferrari Blu-ray", "price": 12, "url": "https://example.com/blu"},
        ],
        "affiliate_products": {
            "amazon": [
                {"product_name": "Ford F-150 Lightning", "offers": [_offer("Ford F-150 Lightning", 54999, "f150")]},
                {"product_name": "Ford v Ferrari Blu-ray", "offers": [_offer("Ford v Ferrari Blu-ray", 12, "bluray")]},
            ],
        },
        "review_data": {},
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }
    state.update(overrides)
    return state


def _blog(irrelevant=None, top_pick="Ford F-150 Lightning"):
    payload = {
        "body": "For an actual truck, the Ford F-150 Lightning is the pick.",
        "follow_up_question": "Will you tow with it?",
        "transitional_reasoning": "",
        "top_pick": top_pick,
    }
    if irrelevant is not None:
        payload["irrelevant_products"] = irrelevant
    return json.dumps(payload)


def _fake_service(blog_response):
    fake = MagicMock()

    async def _generate_compose(*args, **kwargs):
        if kwargs.get("agent_name") == "blog_article_composer":
            return blog_response
        return "x"

    fake.generate_compose = AsyncMock(side_effect=_generate_compose)
    return fake


def _pin_simple_path(monkeypatch):
    monkeypatch.setattr(settings, "USE_CONSOLIDATED_COMPOSE", False)
    monkeypatch.setattr(settings, "USE_DECOUPLED_COMPOSE", False, raising=False)
    monkeypatch.setattr(settings, "USE_COMPOSE_STREAMING", False, raising=False)
    monkeypatch.setattr(settings, "USE_GROUNDED_COMPOSE", False, raising=False)
    monkeypatch.setattr(settings, "USE_VOICE_PASS", False, raising=False)


@pytest.mark.asyncio
async def test_irrelevant_products_dropped_from_cards(monkeypatch):
    """A product the composer flags as irrelevant must not appear in ANY
    ui_block — no card, no carousel entry, no fallback card."""
    _pin_simple_path(monkeypatch)
    fake = _fake_service(_blog(irrelevant=["Ford v Ferrari Blu-ray"]))

    with patch("app.services.model_service.model_service", fake):
        result = await product_compose(_base_state())

    blocks_json = json.dumps(result["ui_blocks"])
    assert "Ford v Ferrari" not in blocks_json, "irrelevant product leaked into ui_blocks"
    assert "F-150" in blocks_json, "relevant product must keep its card"


@pytest.mark.asyncio
async def test_all_irrelevant_suppresses_every_card(monkeypatch):
    """When the composer rejects the whole list, NO product blocks render —
    the honest prose stands alone instead of contradicting a Pick #1 card."""
    _pin_simple_path(monkeypatch)
    fake = _fake_service(_blog(
        irrelevant=["Ford F-150 Lightning", "Ford v Ferrari Blu-ray"],
        top_pick="",
    ))

    with patch("app.services.model_service.model_service", fake):
        result = await product_compose(_base_state())

    blocks_json = json.dumps(result["ui_blocks"])
    assert "Ford v Ferrari" not in blocks_json
    assert "F-150" not in blocks_json
    assert result["assistant_text"].strip(), "prose must still answer the user"


@pytest.mark.asyncio
async def test_no_exclusions_keeps_all_cards(monkeypatch):
    """Absent/empty irrelevant_products → behavior unchanged."""
    _pin_simple_path(monkeypatch)
    fake = _fake_service(_blog(irrelevant=None))

    with patch("app.services.model_service.model_service", fake):
        result = await product_compose(_base_state())

    blocks_json = json.dumps(result["ui_blocks"])
    assert "F-150" in blocks_json
    assert "Ford v Ferrari" in blocks_json


@pytest.mark.asyncio
async def test_blog_prompt_carries_relevance_gate_instruction(monkeypatch):
    """The call-site role must instruct the composer to emit
    irrelevant_products (blog_role itself stays pinned)."""
    _pin_simple_path(monkeypatch)
    fake = _fake_service(_blog(irrelevant=[]))

    with patch("app.services.model_service.model_service", fake):
        await product_compose(_base_state())

    blog_calls = [
        c for c in fake.generate_compose.call_args_list
        if c.kwargs.get("agent_name") == "blog_article_composer"
    ]
    assert blog_calls, "blog call must fire"
    system_content = blog_calls[0].kwargs["messages"][0]["content"]
    assert "irrelevant_products" in system_content
