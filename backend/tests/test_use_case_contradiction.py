"""Fix 1d (2026-07-05): use-case contradiction guardrail in product_compose.

Card #1 must never be a product whose own review text explicitly negates the
stated use ("aren't the best choice for sports use"). After the value sort, if
the top product contradicts the use_case, compose swaps in the first
non-contradicting product from index 1-2. Inert when use_case is empty.
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

from mcp_server.tools.product_compose import product_compose  # noqa: E402

CONTRA = "Sony WF-1000XM5"     # value pick (ranked #1) but reviews negate sports use
SPORTY = "Jabra Elite Active"  # ranked #2, purpose-built for sport


def _state(use_case=None):
    blog = {
        "body": "Here's the shortlist.",
        "follow_up_question": "Indoor or outdoor workouts?",
        "transitional_reasoning": "",
    }
    blog_json = json.dumps(blog)

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
        "user_message": "best earbuds for sports",
        "intent": "product",
        "slots": {"category": "earbuds", "budget": "$100–$300"},
        "normalized_products": [{"name": CONTRA}, {"name": SPORTY}],
        "affiliate_products": {
            "serper_shopping": [
                _offer(CONTRA, 180.0, "sony-wf"),
                _offer(SPORTY, 200.0, "jabra-elite"),
            ],
        },
        "review_data": {
            CONTRA: {
                "quality_score": 92, "avg_rating": 4.6, "total_reviews": 3000,
                "sources": [{"title": "Sony WF review",
                             "snippet": "Superb sound, but they aren't the best choice for sports use — no ear-hooks."}],
            },
            SPORTY: {
                "quality_score": 85, "avg_rating": 4.4, "total_reviews": 1200,
                "sources": [{"title": "Jabra review",
                             "snippet": "Secure ear-hooks make these the pick for sports and running."}],
            },
        },
        # Value order puts the (contradicting) Sony pick first.
        "ranked_products": [
            {"product_name": CONTRA, "score": 3.0, "value_per_dollar": 0.02556,
             "price": 180.0, "rating": 4.6, "in_budget": True, "reasons": []},
            {"product_name": SPORTY, "score": 2.7, "value_per_dollar": 0.022,
             "price": 200.0, "rating": 4.4, "in_budget": True, "reasons": []},
        ],
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }
    if use_case is not None:
        state["slots"]["use_case"] = use_case
    return blog_json, state


def _card_names(result):
    cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    return [c["data"]["product_name"] for c in cards]


@pytest.mark.asyncio
async def test_contradicting_top_pick_swapped_out_with_use_case():
    blog_json, state = _state(use_case="sports")
    fake = MagicMock()
    fake.generate_compose = AsyncMock(return_value=blog_json)
    with patch("app.services.model_service.model_service", fake):
        result = await product_compose(state)
    names = _card_names(result)
    assert names[0] == SPORTY, f"contradicting Sony pick must not lead: {names}"


@pytest.mark.asyncio
async def test_no_swap_without_use_case():
    """Inert when use_case unset — value order (Sony first) preserved."""
    blog_json, state = _state(use_case=None)
    fake = MagicMock()
    fake.generate_compose = AsyncMock(return_value=blog_json)
    with patch("app.services.model_service.model_service", fake):
        result = await product_compose(state)
    names = _card_names(result)
    assert names[0] == CONTRA, f"no use_case → value order unchanged: {names}"
