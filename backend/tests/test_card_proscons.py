"""PLAN-3 v2 — grounded pros/cons from the consolidated composer call.

The old evidence path was dead (parallel with its producer) and fabricated
quotes when alive. Pros/cons now ride the consolidated schema, grounded on the
review_data the call already receives."""
import os

import pytest

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from mcp_server.tools.product_compose import (
    _BLOG_SCHEMA_TAIL,
    _CONSOLIDATED_SCHEMA_TAIL,
    _CONSOLIDATED_EXTRA_RULES,
    _consolidated_blog_role,
)


def test_consolidated_schema_declares_pros_cons():
    assert '"pros_cons"' in _CONSOLIDATED_SCHEMA_TAIL


def test_rules_ground_pros_cons_and_forbid_invention():
    lowered = _CONSOLIDATED_EXTRA_RULES.lower()
    assert "pros_cons" in lowered
    assert "review" in lowered           # grounded on review signal
    assert "empty" in lowered            # no grounding -> empty lists
    assert "never" in lowered            # never invent / never quote


def test_transform_still_replaces_the_tail():
    # The extension edits the tail the transform swaps in — the swap must
    # still fire (guards against breaking the .replace anchor).
    fake_role = "ROLE HEAD\n" + _BLOG_SCHEMA_TAIL
    out = _consolidated_blog_role(fake_role)
    assert '"pros_cons"' in out
    assert out.endswith(_CONSOLIDATED_EXTRA_RULES)


# ---------------------------------------------------------------------------
# Task 2 — cards consume the grounded pros/cons; snippets never render.
# Old builder filed snippet[:150] under pros (mid-word garbage, raw forum
# text) and never wrote cons; fallback cards hardcoded both empty.
# ---------------------------------------------------------------------------

from mcp_server.tools.product_compose import _card_pros_cons

PARSED = {"Breville Barista Express": {
    "pros": ["Built-in burr grinder", "Fast heat-up"],
    "cons": ["Struggles at very fine espresso grind"],
}}
REVIEW = {"Breville Barista Express": {"avg_rating": 4.3, "total_reviews": 1180}}


def test_grounded_entry_flows_to_the_card():
    pros, cons = _card_pros_cons("Breville Barista Express", PARSED, REVIEW)
    assert [p["description"] for p in pros] == ["Built-in burr grinder", "Fast heat-up"]
    assert [c["description"] for c in cons] == ["Struggles at very fine espresso grind"]


def test_no_grounding_yields_empty_not_snippets():
    # Product with a blog entry but NO review signal: sourcing honesty says
    # the model was told to return empty; if it didn't, we drop it here.
    pros, cons = _card_pros_cons("Mystery Machine", PARSED, {})
    assert pros == [] and cons == []


def test_missing_product_yields_empty():
    assert _card_pros_cons("Unknown", PARSED, REVIEW) == ([], [])


def test_items_are_never_raw_truncations():
    long_entry = {"P": {"pros": ["x" * 400], "cons": []}}
    pros, _ = _card_pros_cons("P", long_entry, {"P": {"avg_rating": 4, "total_reviews": 10}})
    # Over-long items are dropped, not truncated mid-word.
    assert pros == []


# ---------------------------------------------------------------------------
# Task 3 — a product query never ends as prose with no card.
#
# Branch under test (early return, pre-LLM): fires ONLY when
# normalized_products AND affiliate_products AND review_data are ALL empty
# (final-validation correction — a fixture with products present can never
# exercise it). When general_product_info is present it used to ship that
# prose verbatim with ui_blocks: [] — the audit's laptop answer: named
# products with prices, nothing actionable.
# ---------------------------------------------------------------------------

from mcp_server.tools.product_compose import product_compose


def _empty_sources_state(info: str) -> dict:
    return {
        "user_message": "best gaming laptop under $1500",
        "intent": "product",
        "slots": {"category": "laptops"},
        "normalized_products": [],
        "affiliate_products": {},
        "review_data": {},
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": info,
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }


@pytest.mark.asyncio
async def test_recommendation_shaped_prose_with_no_listings_is_suppressed():
    """Prose recommending named purchasable products with prices, backed by
    zero sourced listings, must become an explicit no-listings answer."""
    info = (
        "For gaming, the ASUS ROG Strix G16 at $1,299 is excellent. "
        "The Lenovo Legion 5 at $999 is the value pick, and the "
        "Acer Nitro V at $749 covers the budget end."
    )
    result = await product_compose(_empty_sources_state(info))

    assert result["ui_blocks"] == []
    text = result["assistant_text"]
    assert "$1,299" not in text and "$999" not in text and "$749" not in text
    assert "listings" in text.lower()


@pytest.mark.asyncio
async def test_plain_factoid_prose_still_passes_through():
    """A genuine factoid (no price-quoting recommendations) keeps flowing —
    zero cards is CORRECT when nothing purchasable was asked about."""
    info = (
        "Espresso machines force hot water through finely ground coffee at "
        "around nine bars of pressure; the grind size controls extraction."
    )
    result = await product_compose(_empty_sources_state(info))
    assert "nine bars" in result["assistant_text"]


@pytest.mark.asyncio
async def test_no_info_still_returns_honest_no_listings():
    result = await product_compose(_empty_sources_state(""))
    assert result["ui_blocks"] == []
    assert "listings" in result["assistant_text"].lower()


# ---------------------------------------------------------------------------
# Task 4 — characterization: the "How They Compare" block already pins the
# prose top pick to rank 1 (QA Round 6). Pin the behaviour so PLAN-1/PLAN-8
# compose edits can't regress it.
# ---------------------------------------------------------------------------

import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import settings


def _offer(name, price, slug):
    return {
        "title": name, "price": price, "currency": "USD",
        "url": f"https://www.amazon.com/dp/{slug}?tag=revguide-20",
        "merchant": "Amazon",
        "image_url": f"https://img.example.com/{slug}.jpg",
        "source": "amazon",
    }


@pytest.mark.asyncio
async def test_consensus_block_leads_with_the_prose_pick(monkeypatch):
    """Input order and review score both favor Alpha; the prose top_pick is
    Bravo — the comparison block must rank Bravo first as Editor's pick."""
    monkeypatch.setattr(settings, "USE_CONSOLIDATED_COMPOSE", True)
    monkeypatch.setattr(settings, "USE_DECOUPLED_COMPOSE", False, raising=False)
    monkeypatch.setattr(settings, "USE_COMPOSE_STREAMING", False, raising=False)
    monkeypatch.setattr(settings, "USE_GROUNDED_COMPOSE", False, raising=False)
    monkeypatch.setattr(settings, "USE_VOICE_PASS", False, raising=False)

    blog = json.dumps({
        "body": "The Bravo Espresso Two is the pick for most people.",
        "follow_up_question": "Milk drinks or straight espresso?",
        "transitional_reasoning": "",
        "top_pick": "Bravo Espresso Two",
        "consensus": {
            "Alpha Espresso One": "Reviewers praise the Alpha's consistency and value. "
                                  "Some note a slow warm-up. Best for patient owners.",
            "Bravo Espresso Two": "Reviewers call the Bravo the better all-rounder. "
                                  "A few dislike the tank size. Best for daily drinkers.",
        },
        "descriptions": {},
        "pros_cons": {},
    })

    fake = MagicMock()

    async def _generate_compose(*args, **kwargs):
        if kwargs.get("agent_name") == "blog_article_composer":
            return blog
        return "x"

    fake.generate_compose = AsyncMock(side_effect=_generate_compose)

    state = {
        "user_message": "best espresso machine",
        "intent": "product",
        "slots": {"category": "espresso machines"},
        "normalized_products": [
            {"name": "Alpha Espresso One", "price": 300, "url": "https://example.com/a"},
            {"name": "Bravo Espresso Two", "price": 350, "url": "https://example.com/b"},
        ],
        "affiliate_products": {
            "amazon": [
                {"product_name": "Alpha Espresso One", "offers": [_offer("Alpha Espresso One", 300, "alpha1")]},
                {"product_name": "Bravo Espresso Two", "offers": [_offer("Bravo Espresso Two", 350, "bravo2")]},
            ],
        },
        "review_data": {
            # Non-empty sources required: bundles without sources never enter
            # review_bundles (product_compose.py, products_with_sources filter).
            "Alpha Espresso One": {
                "avg_rating": 4.8, "total_reviews": 2000, "quality_score": 9.0,
                "sources": [{"snippet": "Consistent shots.", "site_name": "x", "url": "https://x.example/a"}],
            },
            "Bravo Espresso Two": {
                "avg_rating": 4.0, "total_reviews": 100, "quality_score": 4.0,
                "sources": [{"snippet": "Great all-rounder.", "site_name": "y", "url": "https://y.example/b"}],
            },
        },
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }

    with patch("app.services.model_service.model_service", fake):
        result = await product_compose(state)

    consensus_blocks = [b for b in result["ui_blocks"] if b.get("type") == "review_consensus"]
    assert consensus_blocks, "review_consensus block missing"
    products = consensus_blocks[0]["data"]["products"]
    assert products[0]["name"] == "Bravo Espresso Two"
    assert products[0].get("editors_pick") is True
    assert products[0]["rank"] == 1
