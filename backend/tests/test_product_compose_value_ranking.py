"""Outcome 9 — budget-aware value ranking reaches the user (compose integration).

product_ranking writes ranked_products (with value_per_dollar metadata when a
budget was stated); product_compose must mirror that order in the cards, the
"How They Compare" consensus block, and the writer's blog data — while #93's
prose-top-pick pinning still overrides #1.
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

from mcp_server.tools.product_compose import product_compose  # noqa: E402


VALUE_PICK = "Acer Aspire Value 15"      # $550 / 4.5★ — best rating per dollar
MID_PICK = "Lenovo ThinkPad Mid 14"      # $849 / 4.5★
PREMIUM_PICK = "Dell XPS Premium 15"     # $999 / 4.6★ — best by review score


def _value_ranking_state(with_ranking=True, prose_top_pick=None):
    """Three laptops on a "$500–$1,000" ask. Search order AND review quality_score
    both favor the premium pick — so any value-first ordering observed in the
    output is the ranking's doing, nothing else's.

    with_ranking:   include ranked_products as product_ranking would have written it
    prose_top_pick: name for the blog JSON's top_pick field (None = omitted)
    """
    blog = {
        "body": (
            "At your $500-$1,000 budget, the Acer Aspire Value 15 is the pick - "
            "it covers everything a student needs and saves you $450 over the Dell. "
            "The Dell XPS Premium 15 is the upgrade only if build quality is worth "
            "that premium to you."
        ),
        "follow_up_question": "Will you mostly use it at a desk or carry it around?",
        "transitional_reasoning": "",
    }
    if prose_top_pick:
        blog["top_pick"] = prose_top_pick
    blog_json = json.dumps(blog)

    def _sources(n):
        return [
            {"snippet": f"Review snippet {i}.", "site_name": f"site{i}", "url": f"https://example.com/{i}"}
            for i in range(n)
        ]

    def _offer(name, price, slug):
        return {
            "product_name": name,
            "offers": [{
                "title": name, "price": price, "currency": "USD",
                "url": f"https://www.google.com/shopping/product/{slug}",
                "merchant": "BestBuy",
                "image_url": f"https://img.example.com/{slug}.jpg",
                "source": "serper_shopping",
            }],
        }

    state = {
        "user_message": "best laptops",
        "intent": "product",
        "slots": {"category": "laptops", "budget": "$500–$1,000", "use_case": "Student / everyday"},
        # Search order: premium first, value pick last
        "normalized_products": [
            {"name": PREMIUM_PICK},
            {"name": MID_PICK},
            {"name": VALUE_PICK},
        ],
        "affiliate_products": {
            "serper_shopping": [
                _offer(PREMIUM_PICK, 999.0, "dell-xps"),
                _offer(MID_PICK, 849.0, "thinkpad"),
                _offer(VALUE_PICK, 550.0, "acer-aspire"),
            ],
        },
        # Review quality_score favors the premium pick.
        "review_data": {
            PREMIUM_PICK: {
                "quality_score": 95, "avg_rating": 4.6, "total_reviews": 3200, "sources": _sources(3),
            },
            MID_PICK: {
                "quality_score": 88, "avg_rating": 4.5, "total_reviews": 1500, "sources": _sources(3),
            },
            VALUE_PICK: {
                "quality_score": 80, "avg_rating": 4.5, "total_reviews": 2100, "sources": _sources(3),
            },
        },
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }

    if with_ranking:
        # What product_ranking writes to state for this shortlist (value order:
        # Acer 4.5/550=.00818 > Lenovo 4.5/849=.0053 > Dell 4.6/999=.0046)
        state["ranked_products"] = [
            {"product_name": VALUE_PICK, "score": 3.0, "value_per_dollar": 0.00818,
             "price": 550.0, "rating": 4.5, "in_budget": True,
             "reasons": ["Best value in your budget ($550 at 4.5★)"]},
            {"product_name": MID_PICK, "score": 2.65, "value_per_dollar": 0.0053,
             "price": 849.0, "rating": 4.5, "in_budget": True, "reasons": []},
            {"product_name": PREMIUM_PICK, "score": 2.56, "value_per_dollar": 0.0046,
             "price": 999.0, "rating": 4.6, "in_budget": True, "reasons": []},
        ]

    return blog_json, state


def _card_names(result):
    review_cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    return [c["data"]["product_name"] for c in review_cards]


def _consensus_names(result):
    blocks = [b for b in result.get("ui_blocks", []) if b.get("type") == "review_consensus"]
    assert blocks, "expected a review_consensus block"
    return [p["name"] for p in blocks[0]["data"]["products"]], blocks[0]["data"]["products"]


# ---------------------------------------------------------------------------
# Value order drives what the user sees
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_value_order_drives_cards_when_ranking_present():
    """With value ranking in state and NO prose top_pick, card order is the value
    order — the $550/4.5★ pick leads despite search AND review-score order both
    favoring the $999/4.6★ pick."""
    blog_json, state = _value_ranking_state(with_ranking=True, prose_top_pick=None)
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value=blog_json)

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    card_names = _card_names(result)
    assert card_names[0] == VALUE_PICK, f"value pick must be card #1, got: {card_names}"
    assert card_names[-1] == PREMIUM_PICK, f"premium pick ranks last on value, got: {card_names}"


@pytest.mark.asyncio
async def test_value_order_drives_consensus_when_ranking_present():
    """The "How They Compare" block mirrors the value order too (no prose pick)."""
    blog_json, state = _value_ranking_state(with_ranking=True, prose_top_pick=None)
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value=blog_json)

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    names, _ = _consensus_names(result)
    assert names[0] == VALUE_PICK, f"value pick must rank #1 in consensus, got: {names}"


@pytest.mark.asyncio
async def test_prose_pick_still_overrides_value_order():
    """Respect #93: if the prose names the premium pick as its top pick, prose
    pinning still moves it to card #1 / consensus #1 — value order decides the rest."""
    blog_json, state = _value_ranking_state(with_ranking=True, prose_top_pick=PREMIUM_PICK)
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value=blog_json)

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    card_names = _card_names(result)
    assert card_names[0] == PREMIUM_PICK, (
        f"prose top pick must still override value order for card #1, got: {card_names}"
    )
    # Value order governs the remainder
    assert card_names[1] == VALUE_PICK

    names, products = _consensus_names(result)
    assert names[0] == PREMIUM_PICK
    assert products[0].get("editors_pick") is True


@pytest.mark.asyncio
async def test_value_directive_reaches_blog_prompt():
    """The writer is told the value ranking — in blog_data (USER content), never
    in blog_role (which stays pinned byte-identical to the eval)."""
    captured_calls = []

    async def capture_compose(**kwargs):
        captured_calls.append(kwargs)
        return "mock response text"

    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(side_effect=capture_compose)

    blog_json, state = _value_ranking_state(with_ranking=True)
    with patch("app.services.model_service.model_service", fake_service):
        await product_compose(state)

    blog_calls = [c for c in captured_calls if c.get("agent_name") == "blog_article_composer"]
    assert blog_calls, "blog_article composer was not called"
    blog_messages = blog_calls[0]["messages"]
    user_content = blog_messages[-1]["content"]
    system_content = blog_messages[0]["content"]

    assert "VALUE RANKING" in user_content, "value directive missing from blog data"
    assert VALUE_PICK in user_content
    # The directive is data, not a role-prompt edit (blog_role stays eval-pinned)
    assert "VALUE RANKING" not in system_content
    assert "RANK AND COMMIT" in system_content
    # The writer sees products in value order: the value pick's line comes first
    value_pos = user_content.find(f"Product: {VALUE_PICK}")
    premium_pos = user_content.find(f"Product: {PREMIUM_PICK}")
    assert value_pos != -1 and premium_pos != -1
    assert value_pos < premium_pos, "writer must see the value pick first"


# ---------------------------------------------------------------------------
# Inactive paths stay untouched
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_value_order_without_ranking_in_state():
    """Without ranked_products (e.g. ranking step failed), ordering falls back to
    existing behavior — review quality_score for consensus, search order for cards."""
    blog_json, state = _value_ranking_state(with_ranking=False, prose_top_pick=None)
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value=blog_json)

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    card_names = _card_names(result)
    assert card_names[0] == PREMIUM_PICK, "search order preserved without ranking"

    names, _ = _consensus_names(result)
    assert names[0] == PREMIUM_PICK, "quality_score order preserved without ranking"


@pytest.mark.asyncio
async def test_legacy_ranking_without_value_scores_changes_nothing():
    """ranked_products WITHOUT value_per_dollar (no budget stated → legacy scores)
    must not reorder anything — value order only activates on value scoring."""
    blog_json, state = _value_ranking_state(with_ranking=False, prose_top_pick=None)
    # Legacy-style ranking output (0–1 scores, no value metadata)
    state["ranked_products"] = [
        {"product_name": VALUE_PICK, "score": 0.9, "reasons": []},
        {"product_name": PREMIUM_PICK, "score": 0.5, "reasons": []},
    ]
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value=blog_json)

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    card_names = _card_names(result)
    assert card_names[0] == PREMIUM_PICK, "legacy ranking must not reorder cards"
