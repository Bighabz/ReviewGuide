"""F4 — near-duplicate card dedup via model-code identity.

Search providers return the same physical product under different names
("Sony WH-1000XM5 Wireless" vs "Sony WH1000XM5/B Noise Canceling") and each
became its own card. Model codes are the identity signal: dedupe ONLY when
codes match. The URL/offer-set approach was reverted (fuzzy offer attachment
gives DISTINCT products identical offer sets → false positives on real
products); these tests pin that distinct products never get merged.
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
    _dedupe_by_model_code,
    _extract_model_codes,
    product_compose,
)


# ---------------------------------------------------------------------------
# Model-code extraction
# ---------------------------------------------------------------------------

def test_extracts_common_model_code_shapes():
    assert _extract_model_codes("Sony WH-1000XM5 Wireless Headphones") == {"WH1000XM5"}
    # The code stops at the first dash-separated segment ("A515") — both Acer
    # variants below extract the same code, which is what dedup needs.
    assert _extract_model_codes("Acer Aspire 5 A515-56-36UT Slim") == {"A515"}
    assert _extract_model_codes("Acer Aspire 5 Slim A515-56") == {"A515"}
    assert _extract_model_codes("Bose QC45 Headphones") == set()  # only 2 digits — no code
    assert _extract_model_codes("Apple AirPods Pro 2") == set()   # no model code at all


def test_normalization_collapses_dash_variants():
    """'WH-1000XM5' and 'WH1000XM5' are the same product."""
    a = _extract_model_codes("Sony WH-1000XM5")
    b = _extract_model_codes("Sony WH1000XM5/B")
    assert a and b
    assert a & b, f"dash variants must share a normalized code: {a} vs {b}"


def test_non_string_and_empty_names_are_safe():
    assert _extract_model_codes("") == set()
    assert _extract_model_codes(None) == set()
    assert _extract_model_codes({"name": "dict"}) == set()


# ---------------------------------------------------------------------------
# Dedup behavior
# ---------------------------------------------------------------------------

def _product(name, offers=None):
    p = {"name": name}
    if offers is not None:
        p["all_offers"] = offers
        priced = [o for o in offers if (o.get("price") or 0) > 0]
        p["best_offer"] = priced[0] if priced else (offers[0] if offers else None)
    return p


def test_same_model_code_collapses_to_one_product():
    products = [
        _product("Sony WH-1000XM5 Wireless Headphones",
                 [{"url": "https://amazon.com/a", "price": 348.0, "source": "amazon"}]),
        _product("Sony WH1000XM5/B Noise Canceling",
                 [{"url": "https://ebay.com/b", "price": 299.0, "source": "ebay"}]),
    ]
    deduped = _dedupe_by_model_code(products)
    assert len(deduped) == 1
    # First occurrence kept...
    assert deduped[0]["name"] == "Sony WH-1000XM5 Wireless Headphones"
    # ...with the duplicate's offers merged in
    urls = {o["url"] for o in deduped[0]["all_offers"]}
    assert urls == {"https://amazon.com/a", "https://ebay.com/b"}


def test_distinct_products_with_shared_offers_are_never_merged():
    """The false positive that killed the URL-based approach: two genuinely
    different products that fuzzy offer attachment gave the SAME offer set."""
    shared_offers = [{"url": "https://amazon.com/shared", "price": 999.0, "source": "amazon"}]
    products = [
        _product("Apple iPhone 15 Pro", list(shared_offers)),
        _product("Apple iPhone 15 Pro Max", list(shared_offers)),
    ]
    deduped = _dedupe_by_model_code(products)
    assert len(deduped) == 2, "distinct products must never be merged on shared offers"


def test_products_without_model_codes_are_never_merged():
    """'Cheap Laptop A' / 'Cheap Laptop B' have no identity signal → no dedup."""
    products = [
        _product("Cheap Gaming Laptop", [{"url": "https://x.com/1", "price": 400.0}]),
        _product("Cheap Gaming Laptop Pro", [{"url": "https://x.com/2", "price": 450.0}]),
    ]
    deduped = _dedupe_by_model_code(products)
    assert len(deduped) == 2


def test_different_model_codes_are_kept_separate():
    products = [
        _product("Acer Aspire 5 A515-56", [{"url": "https://x.com/1", "price": 500.0}]),
        _product("Acer Aspire 5 A517-53", [{"url": "https://x.com/2", "price": 600.0}]),
    ]
    deduped = _dedupe_by_model_code(products)
    assert len(deduped) == 2


def test_duplicate_offer_urls_not_double_merged():
    """Merging skips offers the kept product already has (same URL)."""
    products = [
        _product("Sony WH-1000XM5", [{"url": "https://amazon.com/a", "price": 348.0}]),
        _product("Sony WH1000XM5 Black", [
            {"url": "https://amazon.com/a", "price": 348.0},   # same
            {"url": "https://ebay.com/b", "price": 299.0},     # new
        ]),
    ]
    deduped = _dedupe_by_model_code(products)
    assert len(deduped) == 1
    assert len(deduped[0]["all_offers"]) == 2


def test_merge_fills_missing_best_offer():
    """A kept product with no priced offer inherits the duplicate's best offer."""
    products = [
        _product("Sony WH-1000XM5", []),  # no offers at all
        _product("Sony WH1000XM5/B", [{"url": "https://ebay.com/b", "price": 299.0}]),
    ]
    deduped = _dedupe_by_model_code(products)
    assert len(deduped) == 1
    assert deduped[0]["best_offer"]["price"] == 299.0


def test_empty_list_is_safe():
    assert _dedupe_by_model_code([]) == []


# ---------------------------------------------------------------------------
# End-to-end through product_compose: one card per physical product
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_near_duplicate_products_produce_one_card():
    """Two name-variants of the same headphones (shared model code) come out of
    compose as ONE product_review card carrying both retailers' offers."""
    def _offer(name, url, price, source, merchant):
        return {
            "product_name": name,
            "offers": [{
                "title": name, "price": price, "currency": "USD",
                "url": url, "merchant": merchant,
                "image_url": f"https://img.example.com/{source}.jpg",
                "source": source,
            }],
        }

    blog_json = json.dumps({
        "body": "The Sony WH-1000XM5 is the pick.",
        "follow_up_question": "Mostly for commuting or the office?",
        "transitional_reasoning": "",
    })

    state = {
        "user_message": "best noise cancelling headphones",
        "intent": "product",
        "slots": {"category": "headphones"},
        "normalized_products": [
            {"name": "Sony WH-1000XM5 Wireless Headphones"},
            {"name": "Sony WH1000XM5/B Noise Canceling"},   # same product, different name
            {"name": "Bose QuietComfort Ultra"},            # genuinely different product
        ],
        "affiliate_products": {
            "amazon": [
                _offer("Sony WH-1000XM5 Wireless Headphones", "https://amzn.to/sony-xm5", 348.0, "amazon", "Amazon"),
            ],
            "ebay": [
                _offer("Sony WH1000XM5/B Noise Canceling", "https://ebay.com/sony-xm5-b", 299.0, "ebay", "eBay"),
                _offer("Bose QuietComfort Ultra", "https://ebay.com/bose-qc", 379.0, "ebay", "eBay"),
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

    review_cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    card_names = [c["data"]["product_name"] for c in review_cards]

    # The two Sony variants collapse to one card; the Bose keeps its own
    sony_cards = [n for n in card_names if "WH" in n.replace("-", "")]
    assert len(sony_cards) == 1, f"expected ONE Sony card, got: {card_names}"
    assert any("Bose" in n for n in card_names), f"Bose card must survive: {card_names}"

    # The surviving Sony card carries offers from BOTH retailers
    sony_card = next(c for c in review_cards if "WH" in c["data"]["product_name"].replace("-", ""))
    merchants = {link["merchant"] for link in sony_card["data"]["affiliate_links"]}
    assert "Amazon" in merchants
    assert any("eBay" in m for m in merchants), f"merged eBay offer missing: {merchants}"
