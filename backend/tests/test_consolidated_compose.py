"""
Tests for Tier 3a consolidated compose (USE_CONSOLIDATED_COMPOSE).

When the flag is on, the single blog_article call also returns per-product
review consensus (top 3) + card descriptions in its JSON, so product_compose
must:

1. NOT fire the separate consensus:* / descriptions LLM calls (fewer round-trips).
2. Populate the review_consensus block from the blog JSON's `consensus` field.
3. Apply the blog JSON's `descriptions` to the product cards.
4. Still degrade gracefully when those fields are missing (template/empty).
5. Be a no-op when the flag is off (the separate calls still fire).
"""
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Environment bootstrap — must happen before any app import
# ---------------------------------------------------------------------------
os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

from app.core.config import settings
from mcp_server.tools.product_compose import product_compose


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _base_state(**overrides):
    state = {
        "user_message": "best noise cancelling headphones under $300",
        "intent": "product",
        "slots": {"category": "headphones"},
        "normalized_products": [
            {"name": "Sony WH-1000XM5", "price": 299, "url": "https://example.com/sony"},
            {"name": "Bose QuietComfort 45", "price": 279, "url": "https://example.com/bose"},
        ],
        "affiliate_products": {
            "serper_shopping": [
                {
                    "product_name": "Sony WH-1000XM5",
                    "offers": [{
                        "title": "Sony WH-1000XM5", "price": 299.99, "currency": "USD",
                        "url": "https://www.google.com/shopping/product/sony", "merchant": "BestBuy",
                        "image_url": "https://img.example.com/sony.jpg",
                        "source": "serper_shopping",
                    }],
                },
                {
                    "product_name": "Bose QuietComfort 45",
                    "offers": [{
                        "title": "Bose QuietComfort 45", "price": 279.00, "currency": "USD",
                        "url": "https://www.google.com/shopping/product/bose", "merchant": "BestBuy",
                        "image_url": "https://img.example.com/bose.jpg",
                        "source": "serper_shopping",
                    }],
                },
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


_REVIEW_DATA = {
    "Sony WH-1000XM5": {
        "avg_rating": 4.7,
        "total_reviews": 12500,
        "quality_score": 0.95,
        "sources": [
            {"site_name": "Wirecutter", "url": "https://wirecutter.com/sony", "snippet": "Best in class ANC"},
            {"site_name": "The Verge", "url": "https://theverge.com/sony", "snippet": "Excellent comfort"},
        ],
    },
    "Bose QuietComfort 45": {
        "avg_rating": 4.5,
        "total_reviews": 8400,
        "quality_score": 0.88,
        "sources": [
            {"site_name": "RTINGS", "url": "https://rtings.com/bose", "snippet": "Great sound quality"},
        ],
    },
}


# A consolidated blog response: body + the two new fields the flag relies on.
_CONSOLIDATED_BLOG = json.dumps({
    "body": (
        "Under $300, the Sony WH-1000XM5 is the pick for most people — the ANC "
        "leads the class and the comfort holds up over long flights. The Bose "
        "QuietComfort 45 is the call if you want a lighter clamp and don't mind "
        "slightly weaker noise cancellation."
    ),
    "follow_up_question": "Is the Sony's bulkier case a problem for how you travel?",
    "transitional_reasoning": "Under $300, ANC quality decides it, and that points to the Sony.",
    "top_pick": "Sony WH-1000XM5",
    "consensus": {
        "Sony WH-1000XM5": "Reviewers consistently praise the class-leading ANC and all-day comfort. A few note the case is bulky. Best for frequent flyers who want the quietest cabin.",
        "Bose QuietComfort 45": "Praised for a light, comfortable fit and natural sound. ANC trails the Sony slightly. Best for all-day office wear where comfort beats absolute silence.",
    },
    "descriptions": {
        "Sony WH-1000XM5": "Class-leading ANC and 30-hour battery make this the default premium pick for travelers under $300.",
        "Bose QuietComfort 45": "Light, comfortable over-ears with natural tuning, ideal for all-day office listening.",
    },
})


def _fake_service(blog_response=_CONSOLIDATED_BLOG):
    """A model_service whose blog_article call returns a consolidated JSON and
    every other call returns a short string (so a stray separate call is
    visible as non-JSON consensus text)."""
    fake = MagicMock()

    async def _generate_compose(*args, **kwargs):
        if kwargs.get("agent_name") == "blog_article_composer":
            return blog_response
        return "STRAY-SEPARATE-CALL"

    fake.generate_compose = AsyncMock(side_effect=_generate_compose)
    return fake


def _agent_names(fake_service):
    return [c.kwargs.get("agent_name") for c in fake_service.generate_compose.call_args_list]


# ---------------------------------------------------------------------------
# Consolidated ON
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_consolidated_skips_separate_consensus_and_description_calls(monkeypatch):
    monkeypatch.setattr(settings, "USE_CONSOLIDATED_COMPOSE", True)
    fake_service = _fake_service()
    state = _base_state(review_data=_REVIEW_DATA)

    with patch("app.services.model_service.model_service", fake_service):
        await product_compose(state)

    names = _agent_names(fake_service)
    # The blog call fires; the per-product consensus + descriptions calls do not.
    assert "blog_article_composer" in names
    assert "review_consensus" not in names
    assert "product_compose_descriptions" not in names


@pytest.mark.asyncio
async def test_consolidated_consensus_block_uses_blog_json(monkeypatch):
    monkeypatch.setattr(settings, "USE_CONSOLIDATED_COMPOSE", True)
    fake_service = _fake_service()
    state = _base_state(review_data=_REVIEW_DATA)

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    blocks = result.get("ui_blocks", [])
    consensus_blocks = [b for b in blocks if b.get("type") == "review_consensus"]
    assert consensus_blocks, f"expected review_consensus block, got: {[b.get('type') for b in blocks]}"

    products = consensus_blocks[0]["data"]["products"]
    by_name = {p["name"]: p for p in products}
    assert "Sony WH-1000XM5" in by_name
    # The consensus text came from the blog JSON, not a stray separate call.
    assert "class-leading ANC" in by_name["Sony WH-1000XM5"]["consensus"]
    assert "STRAY-SEPARATE-CALL" not in by_name["Sony WH-1000XM5"]["consensus"]


@pytest.mark.asyncio
async def test_consolidated_blog_prompt_asks_for_consensus_and_descriptions(monkeypatch):
    """The single blog call's role prompt must carry the consensus + descriptions
    schema/rules — i.e. the one call is responsible for everything the deleted
    calls used to produce."""
    monkeypatch.setattr(settings, "USE_CONSOLIDATED_COMPOSE", True)
    fake_service = _fake_service()
    state = _base_state(review_data=_REVIEW_DATA)

    with patch("app.services.model_service.model_service", fake_service):
        await product_compose(state)

    blog_call = next(
        c for c in fake_service.generate_compose.call_args_list
        if c.kwargs.get("agent_name") == "blog_article_composer"
    )
    system_prompt = blog_call.kwargs["messages"][0]["content"]
    assert "CONSENSUS RULES" in system_prompt
    assert "DESCRIPTIONS RULES" in system_prompt
    assert '"consensus"' in system_prompt
    assert '"descriptions"' in system_prompt
    # Token budget widened to fit the bigger single-call output.
    assert blog_call.kwargs["max_tokens"] >= 1400


@pytest.mark.asyncio
async def test_consolidated_graceful_when_fields_missing(monkeypatch):
    """A blog JSON without consensus/descriptions must not crash — the consensus
    block falls through to empty (no entries) and cards keep their defaults."""
    monkeypatch.setattr(settings, "USE_CONSOLIDATED_COMPOSE", True)
    blog_no_extras = json.dumps({
        "body": "Sony is the pick.",
        "follow_up_question": "How often do you fly?",
        "transitional_reasoning": "",
        "top_pick": "Sony WH-1000XM5",
    })
    fake_service = _fake_service(blog_response=blog_no_extras)
    state = _base_state(review_data=_REVIEW_DATA)

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    # No crash, assistant_text still produced from the body.
    assert "Sony is the pick." in result.get("assistant_text", "")


# ---------------------------------------------------------------------------
# Tier 3b — voice pass folded into the single call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_consolidated_voice_pass_folded_no_second_call(monkeypatch):
    """With consolidated + USE_VOICE_PASS on, the self-edit directive rides the
    single blog call and the separate voice_pass_reviser round-trip is skipped."""
    monkeypatch.setattr(settings, "USE_CONSOLIDATED_COMPOSE", True)
    monkeypatch.setattr(settings, "USE_VOICE_PASS", True)
    fake_service = _fake_service()
    state = _base_state(review_data=_REVIEW_DATA)

    with patch("app.services.model_service.model_service", fake_service):
        await product_compose(state)

    names = _agent_names(fake_service)
    assert "voice_pass_reviser" not in names, "voice pass must not be a separate call in consolidated mode"

    blog_call = next(
        c for c in fake_service.generate_compose.call_args_list
        if c.kwargs.get("agent_name") == "blog_article_composer"
    )
    system_prompt = blog_call.kwargs["messages"][0]["content"]
    assert "SELF-EDIT BEFORE EMITTING" in system_prompt


@pytest.mark.asyncio
async def test_consolidated_no_voice_pass_section_when_flag_off(monkeypatch):
    """Consolidated but USE_VOICE_PASS off → no self-edit section, no revise call."""
    monkeypatch.setattr(settings, "USE_CONSOLIDATED_COMPOSE", True)
    monkeypatch.setattr(settings, "USE_VOICE_PASS", False)
    fake_service = _fake_service()
    state = _base_state(review_data=_REVIEW_DATA)

    with patch("app.services.model_service.model_service", fake_service):
        await product_compose(state)

    blog_call = next(
        c for c in fake_service.generate_compose.call_args_list
        if c.kwargs.get("agent_name") == "blog_article_composer"
    )
    assert "SELF-EDIT BEFORE EMITTING" not in blog_call.kwargs["messages"][0]["content"]
    assert "voice_pass_reviser" not in _agent_names(fake_service)


@pytest.mark.asyncio
async def test_legacy_voice_pass_still_a_separate_call_when_not_consolidated(monkeypatch):
    """Non-consolidated path keeps the separate voice pass round-trip (unchanged)."""
    monkeypatch.setattr(settings, "USE_CONSOLIDATED_COMPOSE", False)
    monkeypatch.setattr(settings, "USE_VOICE_PASS", True)
    # The legacy voice pass calls generate_compose with agent_name=voice_pass_reviser
    # and expects a JSON body back; return a valid revise payload for that call.
    revised = json.dumps({
        "body": "Revised body.", "follow_up_question": "Revised q?", "transitional_reasoning": "",
    })

    async def _generate_compose(*args, **kwargs):
        name = kwargs.get("agent_name")
        if name == "blog_article_composer":
            return _CONSOLIDATED_BLOG
        if name == "voice_pass_reviser":
            return revised
        return "STRAY-SEPARATE-CALL"

    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(side_effect=_generate_compose)
    state = _base_state(review_data=_REVIEW_DATA)

    with patch("app.services.model_service.model_service", fake_service):
        await product_compose(state)

    assert "voice_pass_reviser" in _agent_names(fake_service)


# ---------------------------------------------------------------------------
# Consolidated OFF (baseline parity)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_flag_off_still_fires_separate_calls(monkeypatch):
    monkeypatch.setattr(settings, "USE_CONSOLIDATED_COMPOSE", False)
    fake_service = _fake_service()
    state = _base_state(review_data=_REVIEW_DATA)

    with patch("app.services.model_service.model_service", fake_service):
        await product_compose(state)

    names = _agent_names(fake_service)
    # Baseline: the per-product consensus calls fire (one per top product).
    assert "review_consensus" in names
