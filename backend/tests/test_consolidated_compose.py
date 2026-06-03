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
from mcp_server.tools.product_compose import (
    product_compose,
    _parse_blog_output,
    _decoupled_blog_role,
    _consolidated_blog_role,
)


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
# Tier 2 — prose / JSON decouple
# ---------------------------------------------------------------------------

# A decoupled response: prose body, then a <data> tail with the structured fields.
_DECOUPLED_BLOG = (
    "Under $300, the Sony WH-1000XM5 is the pick for most people — the ANC leads "
    "the class. The Bose QuietComfort 45 is the call if comfort matters more.\n\n"
    "Skip the AirPods Max at this budget.\n\n"
    "<data>\n"
    + json.dumps({
        "follow_up_question": "Is the Sony's bulkier case a problem for how you travel?",
        "transitional_reasoning": "Under $300, ANC quality decides it.",
        "top_pick": "Sony WH-1000XM5",
        "consensus": {
            "Sony WH-1000XM5": "Reviewers praise the class-leading ANC and comfort. Case is bulky. Best for flyers.",
            "Bose QuietComfort 45": "Praised for light fit and natural sound. ANC trails slightly. Best for all-day wear.",
        },
        "descriptions": {
            "Sony WH-1000XM5": "Class-leading ANC and 30-hour battery for travelers under $300.",
            "Bose QuietComfort 45": "Light, comfortable over-ears ideal for all-day office listening.",
        },
    })
    + "\n</data>"
)


def test_parse_blog_output_json_mode():
    parsed = _parse_blog_output(_CONSOLIDATED_BLOG, decoupled=False)
    assert parsed["top_pick"] == "Sony WH-1000XM5"
    assert "Sony WH-1000XM5" in parsed["consensus"]
    assert parsed["body"].startswith("Under $300")


def test_parse_blog_output_decoupled_splits_prose_and_data():
    parsed = _parse_blog_output(_DECOUPLED_BLOG, decoupled=True)
    # Body is the prose before <data>, with no data block leaking in.
    assert parsed["body"].startswith("Under $300")
    assert "<data>" not in parsed["body"]
    assert "follow_up_question" not in parsed["body"]
    # Structured fields came from the <data> tail.
    assert parsed["top_pick"] == "Sony WH-1000XM5"
    assert parsed["follow_up_question"].startswith("Is the Sony")
    assert "Sony WH-1000XM5" in parsed["consensus"]
    assert "Bose QuietComfort 45" in parsed["descriptions"]


def test_parse_blog_output_decoupled_missing_data_block_degrades_to_body():
    parsed = _parse_blog_output("Just prose, no data block.", decoupled=True)
    assert parsed["body"] == "Just prose, no data block."
    assert "top_pick" not in parsed


def test_parse_blog_output_decoupled_garbled_data_keeps_body():
    raw = "Prose here.\n\n<data>\n{not valid json,,,}\n</data>"
    parsed = _parse_blog_output(raw, decoupled=True)
    assert parsed["body"] == "Prose here."
    assert "top_pick" not in parsed  # garbled JSON → fields dropped, body survives


def test_parse_blog_output_empty_returns_none():
    assert _parse_blog_output("", decoupled=True) is None
    assert _parse_blog_output("   ", decoupled=False) is None


def test_decoupled_role_rewrites_output_format():
    consolidated = _consolidated_blog_role(
        # minimal fake base role carrying the json OUTPUT FORMAT block
        'Write a guide.\n\nOUTPUT FORMAT — return a JSON object with these string fields:\n'
        '{\n  "body": "<x>",\n  "top_pick": "<the EXACT product name of your #1 pick, copied verbatim from the product list — the same product your body names first>"\n}\n\nRANK AND COMMIT: ...'
    )
    decoupled = _decoupled_blog_role(consolidated)
    # JSON-object framing gone; prose + <data> framing in.
    assert "return a JSON object with these string fields" not in decoupled
    assert "<data>" in decoupled
    assert "THE BODY" in decoupled
    # Downstream sections survive the rewrite.
    assert "RANK AND COMMIT" in decoupled
    assert "CONSENSUS RULES" in decoupled


@pytest.mark.asyncio
async def test_decoupled_blog_call_drops_json_object_response_format(monkeypatch):
    monkeypatch.setattr(settings, "USE_CONSOLIDATED_COMPOSE", True)
    monkeypatch.setattr(settings, "USE_DECOUPLED_COMPOSE", True)
    monkeypatch.setattr(settings, "USE_VOICE_PASS", False)
    fake_service = _fake_service(blog_response=_DECOUPLED_BLOG)
    state = _base_state(review_data=_REVIEW_DATA)

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    blog_call = next(
        c for c in fake_service.generate_compose.call_args_list
        if c.kwargs.get("agent_name") == "blog_article_composer"
    )
    # Decoupled → no json_object constraint; role carries the <data> framing.
    assert blog_call.kwargs.get("response_format") is None
    assert "<data>" in blog_call.kwargs["messages"][0]["content"]

    # Prose body reached assistant_text (without the data block leaking in).
    assert "Under $300" in result.get("assistant_text", "")
    assert "<data>" not in result.get("assistant_text", "")

    # Consensus block built from the <data> tail.
    consensus_blocks = [b for b in result.get("ui_blocks", []) if b.get("type") == "review_consensus"]
    assert consensus_blocks
    names = {p["name"] for p in consensus_blocks[0]["data"]["products"]}
    assert "Sony WH-1000XM5" in names


@pytest.mark.asyncio
async def test_decoupled_requires_consolidated(monkeypatch):
    """USE_DECOUPLED_COMPOSE without USE_CONSOLIDATED_COMPOSE is inert — the
    call stays on the json_object path."""
    monkeypatch.setattr(settings, "USE_CONSOLIDATED_COMPOSE", False)
    monkeypatch.setattr(settings, "USE_DECOUPLED_COMPOSE", True)
    fake_service = _fake_service()
    state = _base_state(review_data=_REVIEW_DATA)

    with patch("app.services.model_service.model_service", fake_service):
        await product_compose(state)

    blog_call = next(
        c for c in fake_service.generate_compose.call_args_list
        if c.kwargs.get("agent_name") == "blog_article_composer"
    )
    assert blog_call.kwargs.get("response_format") == {"type": "json_object"}


# ---------------------------------------------------------------------------
# Tier 2.1 — true token streaming routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_streaming_routes_blog_through_streaming_method(monkeypatch):
    """With consolidated + decoupled + streaming all on, the blog call uses
    generate_compose_with_streaming (token streaming); the response still parses
    identically (it returns the same prose + <data> text)."""
    monkeypatch.setattr(settings, "USE_CONSOLIDATED_COMPOSE", True)
    monkeypatch.setattr(settings, "USE_DECOUPLED_COMPOSE", True)
    monkeypatch.setattr(settings, "USE_COMPOSE_STREAMING", True)
    monkeypatch.setattr(settings, "USE_VOICE_PASS", False)

    fake = MagicMock()
    fake.generate_compose = AsyncMock(side_effect=AssertionError("must not use non-streaming compose for the blog"))
    fake.generate_compose_with_streaming = AsyncMock(return_value=_DECOUPLED_BLOG)
    state = _base_state(review_data=_REVIEW_DATA)

    with patch("app.services.model_service.model_service", fake):
        result = await product_compose(state)

    assert fake.generate_compose_with_streaming.await_count == 1
    stream_call = fake.generate_compose_with_streaming.call_args
    assert stream_call.kwargs.get("agent_name") == "blog_article_composer"
    # Output still assembled correctly from the streamed text.
    assert "Under $300" in result.get("assistant_text", "")
    assert "<data>" not in result.get("assistant_text", "")
    consensus_blocks = [b for b in result.get("ui_blocks", []) if b.get("type") == "review_consensus"]
    assert consensus_blocks


@pytest.mark.asyncio
async def test_streaming_inert_without_decoupled(monkeypatch):
    """USE_COMPOSE_STREAMING without USE_DECOUPLED_COMPOSE stays on the
    non-streaming json_object path (streaming needs plain-text prose)."""
    monkeypatch.setattr(settings, "USE_CONSOLIDATED_COMPOSE", True)
    monkeypatch.setattr(settings, "USE_DECOUPLED_COMPOSE", False)
    monkeypatch.setattr(settings, "USE_COMPOSE_STREAMING", True)

    fake = MagicMock()
    fake.generate_compose = AsyncMock(side_effect=lambda *a, **k: _CONSOLIDATED_BLOG if k.get("agent_name") == "blog_article_composer" else "x")
    fake.generate_compose_with_streaming = AsyncMock(side_effect=AssertionError("streaming must be inert without decouple"))
    state = _base_state(review_data=_REVIEW_DATA)

    with patch("app.services.model_service.model_service", fake):
        await product_compose(state)

    assert fake.generate_compose_with_streaming.await_count == 0
    blog_call = next(c for c in fake.generate_compose.call_args_list if c.kwargs.get("agent_name") == "blog_article_composer")
    assert blog_call.kwargs.get("response_format") == {"type": "json_object"}


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
