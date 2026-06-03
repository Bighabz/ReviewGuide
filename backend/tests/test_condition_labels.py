"""$407-class listing honesty — condition labels (Renewed / Used / Open box).

Marketplace offers priced at 30-40% of market are usually renewed/used/open-box
listings; the median price filter can't catch them (they look plausible). Label
them instead of hiding them: the eBay Browse API carries the condition field,
and Google Shopping listings put "Renewed"/"Refurbished" in the title (their
condition field arrives hardcoded "new").
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

from mcp_server.tools.product_compose import (  # noqa: E402
    _offer_condition_label,
    product_compose,
)


# ---------------------------------------------------------------------------
# The label helper
# ---------------------------------------------------------------------------

def test_ebay_condition_field_drives_the_label():
    """eBay Browse API condition strings map to honest labels."""
    assert _offer_condition_label({"condition": "Used"}) == "Used"
    assert _offer_condition_label({"condition": "Certified - Refurbished"}) == "Renewed"
    assert _offer_condition_label({"condition": "Seller refurbished"}) == "Renewed"
    assert _offer_condition_label({"condition": "Open box"}) == "Open box"
    assert _offer_condition_label({"condition": "Pre-owned"}) == "Used"


def test_new_conditions_get_no_label():
    assert _offer_condition_label({"condition": "New"}) is None
    assert _offer_condition_label({"condition": "new"}) is None
    assert _offer_condition_label({"condition": "Brand New"}) is None
    assert _offer_condition_label({"condition": "New other (see details)"}) is None
    assert _offer_condition_label({"condition": ""}) is None
    assert _offer_condition_label({}) is None


def test_title_keywords_catch_google_shopping_refurbs():
    """Serper/Google Shopping offers arrive with condition='new' — the listing
    title is the only signal there."""
    assert _offer_condition_label({
        "condition": "new",
        "title": "Apple iPhone 15 Pro 128GB (Renewed) - Unlocked",
    }) == "Renewed"
    assert _offer_condition_label({
        "condition": "new",
        "title": "Sony WH-1000XM5 Refurbished by Sony",
    }) == "Renewed"
    assert _offer_condition_label({
        "condition": "new",
        "title": "Dell XPS 15 - Used, Like New",
    }) == "Used"
    assert _offer_condition_label({
        "condition": "new",
        "title": "Bose QC45 Open Box Special",
    }) == "Open box"


def test_clean_titles_get_no_label():
    assert _offer_condition_label({
        "condition": "new",
        "title": "Apple iPhone 15 Pro 128GB Natural Titanium",
    }) is None
    # "used" inside another word must not trigger (e.g. "Focused")
    assert _offer_condition_label({
        "condition": "new",
        "title": "Focused Audio Headphones FA-3000",
    }) is None


def test_non_string_fields_are_safe():
    assert _offer_condition_label({"condition": None, "title": None}) is None
    assert _offer_condition_label({"condition": {"weird": "dict"}, "title": ["list"]}) is None


# ---------------------------------------------------------------------------
# End-to-end: the card carries the label, headline price prefers new offers
# ---------------------------------------------------------------------------

def _compose_state(offers_by_provider):
    blog_json = json.dumps({
        "body": "The iPhone 15 Pro is the pick.",
        "follow_up_question": "Do you want the Pro Max size instead?",
        "transitional_reasoning": "",
    })
    affiliate_products = {}
    for provider, offers in offers_by_provider.items():
        affiliate_products[provider] = [{
            "product_name": "Apple iPhone 15 Pro",
            "offers": offers,
        }]
    return blog_json, {
        "user_message": "best phone",
        "intent": "product",
        "slots": {"category": "phones"},
        "normalized_products": [{"name": "Apple iPhone 15 Pro"}],
        "affiliate_products": affiliate_products,
        "review_data": {},
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }


@pytest.mark.asyncio
async def test_renewed_ebay_offer_gets_condition_label_on_card():
    """A used/renewed eBay listing shows up on the card WITH its honest label."""
    blog_json, state = _compose_state({
        "amazon": [{
            "title": "Apple iPhone 15 Pro", "price": 999.0, "currency": "USD",
            "url": "https://amzn.to/iphone15pro", "merchant": "Amazon",
            "image_url": "https://img.example.com/iphone.jpg", "condition": "new",
            "source": "amazon",
        }],
        "ebay": [{
            "title": "Apple iPhone 15 Pro 128GB - Excellent Condition", "price": 407.0,
            "currency": "USD", "url": "https://ebay.com/iphone-used",
            "merchant": "eBay (reseller99)", "image_url": "https://img.example.com/iphone-used.jpg",
            "condition": "Used", "source": "ebay",
        }],
    })

    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value=blog_json)
    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    assert cards, "expected a product card"
    links = cards[0]["data"]["affiliate_links"]

    ebay_link = next((l for l in links if "ebay" in l["affiliate_link"]), None)
    assert ebay_link is not None, f"eBay offer missing from card links: {links}"
    assert ebay_link["condition_label"] == "Used"

    amazon_link = next((l for l in links if "amzn.to" in l["affiliate_link"]), None)
    assert amazon_link is not None
    assert amazon_link.get("condition_label") is None


@pytest.mark.asyncio
async def test_new_offer_leads_card_over_cheaper_renewed_offer():
    """The card's first link (headline) is the NEW offer even when the renewed
    one is cheaper — honesty beats the lowest number.

    Setup mirrors production: each provider group contributes ONE offer (compose
    takes offers[0] per group), so the renewed and new Amazon listings arrive as
    two separate groups that both fuzzy-match the product.
    """
    blog_json = json.dumps({
        "body": "The iPhone 15 Pro is the pick.",
        "follow_up_question": "Do you want the Pro Max size instead?",
        "transitional_reasoning": "",
    })
    state = {
        "user_message": "best phone",
        "intent": "product",
        "slots": {"category": "phones"},
        "normalized_products": [{"name": "Apple iPhone 15 Pro"}],
        "affiliate_products": {
            "amazon": [
                {
                    "product_name": "Apple iPhone 15 Pro Renewed",
                    "offers": [{
                        # Renewed Amazon listing — cheaper
                        "title": "Apple iPhone 15 Pro (Renewed)", "price": 407.0, "currency": "USD",
                        "url": "https://amzn.to/iphone15pro-renewed", "merchant": "Amazon",
                        "image_url": "https://img.example.com/iphone-r.jpg", "condition": "new",
                        "source": "amazon",
                    }],
                },
                {
                    "product_name": "Apple iPhone 15 Pro",
                    "offers": [{
                        # New Amazon listing — pricier
                        "title": "Apple iPhone 15 Pro", "price": 999.0, "currency": "USD",
                        "url": "https://amzn.to/iphone15pro", "merchant": "Amazon",
                        "image_url": "https://img.example.com/iphone.jpg", "condition": "new",
                        "source": "amazon",
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

    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value=blog_json)
    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    assert cards
    links = cards[0]["data"]["affiliate_links"]
    # Only ONE Amazon link survives merchant dedup — it must be the NEW one
    amazon_links = [l for l in links if "amzn.to" in l["affiliate_link"]]
    assert len(amazon_links) == 1
    assert amazon_links[0]["affiliate_link"] == "https://amzn.to/iphone15pro", (
        "the NEW offer must lead, not the cheaper renewed one"
    )
    assert amazon_links[0].get("condition_label") is None


@pytest.mark.asyncio
async def test_renewed_only_product_still_renders_with_label():
    """When every offer is renewed (no new option), the card still renders —
    labeled, not hidden. Honest, not censored."""
    blog_json, state = _compose_state({
        "ebay": [{
            "title": "Apple iPhone 15 Pro - Certified Refurbished", "price": 450.0,
            "currency": "USD", "url": "https://ebay.com/iphone-refurb",
            "merchant": "eBay (refurbpro)", "image_url": "https://img.example.com/iphone-rf.jpg",
            "condition": "Certified - Refurbished", "source": "ebay",
        }],
    })

    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value=blog_json)
    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    assert cards, "renewed-only product must still get a card"
    links = cards[0]["data"]["affiliate_links"]
    labeled = [l for l in links if l.get("condition_label")]
    assert labeled, f"expected a Renewed label on the card links: {links}"
    assert labeled[0]["condition_label"] == "Renewed"
