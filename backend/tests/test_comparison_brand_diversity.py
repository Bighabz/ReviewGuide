"""QA remediation — "X vs Y" shortlists must represent BOTH sides.

Observed in QA (2026-06-10): "nike vs adidas sneakers" produced an all-Nike
shortlist; "iPhone 15 vs Pixel 8" produced all-iPhone cards with the Pixel
absent from recommendations entirely. Two causes:

1. product_search's name-generator got the raw query with no requirement to
   cover both compared sides, so token-order bias filled all 5-8 slots with
   one brand.
2. product_ranking sorts purely by score — even when both sides exist in the
   results, one brand's higher authority/ratings packs the top of the list.

The clarifier already detects comparisons and stores ``comparison_products``
in slots (Outcome 5); these tests pin that both downstream stages use it.
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

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402

from mcp_server.tools.product_search import product_search  # noqa: E402
from mcp_server.tools.product_ranking import product_ranking  # noqa: E402


# ---------------------------------------------------------------------------
# Stage 1: the name-generator prompt demands both sides
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_product_search_prompt_demands_both_comparison_sides():
    captured = {}

    async def fake_generate(messages, **kwargs):
        captured["messages"] = messages
        return json.dumps({"products": ["Nike Air Max 270", "Adidas Ultraboost 22"]})

    state = {
        "user_message": "nike vs adidas sneakers",
        "slots": {
            "category": "sneakers",
            "comparison_products": ["nike", "adidas sneakers"],
        },
    }
    with patch("app.services.model_service.model_service.generate", new=fake_generate):
        await product_search(state)

    full_prompt = "\n".join(m["content"] for m in captured["messages"])
    assert "EACH" in full_prompt, "prompt must demand products for EACH compared side"
    assert "nike" in full_prompt.lower()
    assert "adidas" in full_prompt.lower()


@pytest.mark.asyncio
async def test_product_search_prompt_unchanged_without_comparison():
    """No comparison pair → no comparison directive (regression guard)."""
    captured = {}

    async def fake_generate(messages, **kwargs):
        captured["messages"] = messages
        return json.dumps({"products": ["Sony WH-1000XM5"]})

    state = {"user_message": "best headphones", "slots": {"category": "headphones"}}
    with patch("app.services.model_service.model_service.generate", new=fake_generate):
        await product_search(state)

    full_prompt = "\n".join(m["content"] for m in captured["messages"])
    assert "COMPARISON REQUEST" not in full_prompt


# ---------------------------------------------------------------------------
# Stage 2: ranking interleaves the two sides instead of score-packing one
# ---------------------------------------------------------------------------

IPHONES = [
    ("Apple iPhone 15 Pro Max", 0.9),
    ("Apple iPhone 15 Pro", 0.85),
    ("Apple iPhone 15", 0.8),
]
PIXELS = [
    ("Google Pixel 8 Pro", 0.5),
    ("Google Pixel 8", 0.45),
]


def _ranking_state(comparison=None):
    state = {
        "normalized_products": [
            {"name": n, "score": s} for n, s in IPHONES + PIXELS
        ],
        "review_data": {},
        "affiliate_products": {},
        "slots": {},
    }
    if comparison:
        state["slots"]["comparison_products"] = comparison
    return state


def _side(name):
    return "iphone" if "iphone" in name.lower() else "pixel"


@pytest.mark.asyncio
async def test_ranking_interleaves_comparison_sides():
    """With a comparison pair, the shortlist alternates sides — the top 2 must
    contain one of each, and the top 4 two of each, even when one side's raw
    scores would otherwise sweep the head of the list."""
    result = await product_ranking(_ranking_state(comparison=["iPhone 15", "Pixel 8"]))

    names = [it["product_name"] for it in result["ranked_products"]]
    assert {_side(names[0]), _side(names[1])} == {"iphone", "pixel"}, (
        f"top 2 must represent both sides, got {names[:2]}"
    )
    top4_sides = [_side(n) for n in names[:4]]
    assert top4_sides.count("iphone") == 2 and top4_sides.count("pixel") == 2, (
        f"top 4 must hold two of each side, got {names[:4]}"
    )


@pytest.mark.asyncio
async def test_ranking_keeps_score_order_without_comparison():
    """No comparison pair → pure score order (legacy behavior pinned)."""
    result = await product_ranking(_ranking_state())

    names = [it["product_name"] for it in result["ranked_products"]]
    assert names == [n for n, _ in IPHONES + PIXELS]


@pytest.mark.asyncio
async def test_ranking_interleave_noop_when_one_side_absent():
    """If search returned only one side anyway, interleaving must not scramble
    the list (nothing to balance)."""
    state = {
        "normalized_products": [{"name": n, "score": s} for n, s in IPHONES],
        "review_data": {},
        "affiliate_products": {},
        "slots": {"comparison_products": ["iPhone 15", "Pixel 8"]},
    }
    result = await product_ranking(state)

    names = [it["product_name"] for it in result["ranked_products"]]
    assert names == [n for n, _ in IPHONES]
