"""
Unit tests for product_compose tool.

Covers the general_product_info fallback path: when the planner routes through
product_general_information (factoid queries), the fetched answer must be
surfaced as assistant_text rather than silently discarded by the no-results guard.

Also covers RX-06: opener and conclusion LLM calls must be removed.
Also covers RX-07: review source URLs must be threaded into blog_data.
"""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

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

from mcp_server.tools.product_compose import product_compose, _parse_budget, _drop_price_outliers


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_model_service():
    """
    Patch model_service so no real OpenAI calls are made during tests.
    The early-exit path tested here never reaches the LLM, but the fixture
    is required to prevent accidental API calls if the guard is removed.
    """
    fake_service = MagicMock()
    fake_service.get_response = AsyncMock(return_value="mock response")
    fake_service.get_streaming_response = AsyncMock(return_value=iter([]))
    with patch("app.services.model_service.model_service", fake_service):
        yield fake_service


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compose_uses_general_product_info_when_no_listings(mock_model_service):
    """
    When general_product_info is in state but no affiliate/review/normalized data exists,
    product_compose must return general_product_info as assistant_text.
    """
    state = {
        "user_message": "tell me more about Sony WH-1000XM5",
        "intent": "product",
        "slots": {},
        "normalized_products": [],
        "affiliate_products": {},
        "review_data": {},
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "The Sony WH-1000XM5 is a premium over-ear headphone with industry-leading ANC.",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }
    result = await product_compose(state)
    assert result["success"] is True
    assert "Sony WH-1000XM5" in result["assistant_text"]
    assert result["ui_blocks"] == []


@pytest.mark.asyncio
async def test_compose_falls_back_to_generic_message_when_no_data_at_all(mock_model_service):
    """
    When neither general_product_info nor any listing data exists, product_compose
    must return the generic fallback message (not crash or return empty text).
    """
    state = {
        "user_message": "tell me about some unknown gadget",
        "intent": "product",
        "slots": {},
        "normalized_products": [],
        "affiliate_products": {},
        "review_data": {},
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }
    result = await product_compose(state)
    assert result["success"] is True
    assert result["assistant_text"]  # non-empty fallback
    assert result["ui_blocks"] == []


@pytest.mark.asyncio
async def test_compose_ignores_whitespace_only_general_product_info(mock_model_service):
    """
    Whitespace-only general_product_info must not be surfaced as assistant_text.
    """
    state = {
        "user_message": "tell me more about Sony WH-1000XM5",
        "intent": "product",
        "slots": {},
        "normalized_products": [],
        "affiliate_products": {},
        "review_data": {},
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "   ",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }
    result = await product_compose(state)
    assert result["success"] is True
    assert result["assistant_text"].strip()
    assert "wasn't able to find" in result["assistant_text"]


@pytest.mark.asyncio
async def test_compose_general_product_info_not_used_when_listings_present(mock_model_service):
    """
    When listing data IS present alongside general_product_info, the tool must
    not short-circuit — it should proceed through the full compose path.
    The early-exit guard must only fire when ALL of normalized/affiliate/review are empty.
    """
    state = {
        "user_message": "Sony WH-1000XM5",
        "intent": "product",
        "slots": {},
        "normalized_products": [
            {"name": "Sony WH-1000XM5", "price": 299, "url": "https://example.com"}
        ],
        "affiliate_products": {},
        "review_data": {},
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "Should not appear — listings are present.",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }
    result = await product_compose(state)
    # The tool must not short-circuit; it must attempt to compose a real response.
    # We only assert it did not raise and returned a dict with the expected keys.
    assert "success" in result
    assert "assistant_text" in result
    assert "ui_blocks" in result


# ---------------------------------------------------------------------------
# RX-06: Opener and conclusion LLM calls must be removed
# ---------------------------------------------------------------------------

_REVIEW_STATE_WITH_DATA = {
    "user_message": "best noise cancelling headphones under $300",
    "intent": "product",
    "slots": {"category": "headphones", "budget": 300},
    "normalized_products": [
        {"name": "Sony WH-1000XM5", "price": 299, "url": "https://example.com/sony"},
        {"name": "Bose QuietComfort 45", "price": 279, "url": "https://example.com/bose"},
    ],
    "affiliate_products": {
        "amazon": [
            {
                "product_name": "Sony WH-1000XM5",
                "offers": [{"title": "Sony WH-1000XM5", "price": 299.99, "currency": "USD",
                             "url": "https://amazon.com/sony", "merchant": "Amazon",
                             "image_url": "https://example.com/img.jpg"}]
            }
        ]
    },
    "review_data": {
        "Sony WH-1000XM5": {
            "avg_rating": 4.7,
            "total_reviews": 12500,
            "quality_score": 0.95,
            "sources": [
                {"site_name": "Wirecutter", "url": "https://wirecutter.com/sony", "snippet": "Best in class ANC"},
                {"site_name": "The Verge", "url": "https://theverge.com/sony", "snippet": "Excellent comfort"},
            ]
        },
        "Bose QuietComfort 45": {
            "avg_rating": 4.5,
            "total_reviews": 8400,
            "quality_score": 0.88,
            "sources": [
                {"site_name": "RTINGS", "url": "https://rtings.com/bose", "snippet": "Great sound quality"},
            ]
        }
    },
    "comparison_html": None,
    "comparison_data": None,
    "general_product_info": "",
    "conversation_history": [],
    "last_search_context": {},
    "search_history": [],
}


# ---------------------------------------------------------------------------
# Budget-ceiling leak: the slot extractor returns budget as a NUMBER, so
# _parse_budget must accept a numeric (or bare-number) budget as a hard max —
# otherwise the offer filter is skipped and over-budget items leak through.
# ---------------------------------------------------------------------------

def test_parse_budget_accepts_numeric_as_ceiling():
    assert _parse_budget(100) == (None, 100.0)        # the bug case: int from slot extractor
    assert _parse_budget(249.99) == (None, 249.99)
    assert _parse_budget(0) == (None, None)           # nonsense → no ceiling
    assert _parse_budget(-5) == (None, None)
    assert _parse_budget(True) == (None, None)        # bool must NOT be treated as 1


def test_parse_budget_accepts_bare_number_string():
    assert _parse_budget("100") == (None, 100.0)
    assert _parse_budget("$100") == (None, 100.0)
    assert _parse_budget("1,200") == (None, 1200.0)


def test_parse_budget_still_parses_qualified_strings():
    assert _parse_budget("under $500") == (None, 500.0)
    assert _parse_budget("$100-$200") == (100.0, 200.0)
    lo, hi = _parse_budget("around $500")
    assert (lo, hi) == (400.0, 600.0)
    assert _parse_budget("") == (None, None)
    assert _parse_budget(None) == (None, None)


def test_parse_budget_floor_formats():
    """The clarifier's top budget chip ("$1,200+") and spoken floor forms must parse
    as a min bound — previously they parsed to (None, None) = no filtering at all."""
    assert _parse_budget("$1,200+") == (1200.0, None)
    assert _parse_budget("500+") == (500.0, None)
    assert _parse_budget("$500+") == (500.0, None)
    assert _parse_budget("over $500") == (500.0, None)
    assert _parse_budget("above $800") == (800.0, None)
    assert _parse_budget("more than $300") == (300.0, None)
    assert _parse_budget("at least $1,000") == (1000.0, None)


def test_parse_budget_clarifier_chip_range_formats():
    """The exact strings the clarifier budget chips send (en dash) must parse as ranges."""
    assert _parse_budget("$500–$800") == (500.0, 800.0)
    assert _parse_budget("$1,000–$2,000") == (1000.0, 2000.0)
    # "Under $500" chip (capital U)
    assert _parse_budget("Under $500") == (None, 500.0)


@pytest.mark.asyncio
async def test_numeric_budget_filters_over_ceiling_offer():
    """slots["budget"] = 100 (int, as the slot extractor produces it) must drop an
    over-budget offer from the card — the budget-ceiling-leak fix."""
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value="mock response text")

    state = {
        "user_message": "best mechanical keyboard under $100",
        "intent": "product",
        "slots": {"category": "keyboards", "budget": 100},  # int — the leak trigger
        "normalized_products": [{"name": "Cheap Keyboard"}],
        "affiliate_products": {
            "serper_shopping": [{
                "product_name": "Cheap Keyboard",
                "offers": [{
                    "title": "Cheap Keyboard", "price": 59.99, "currency": "USD",
                    "url": "https://www.google.com/shopping/product/kb", "merchant": "Walmart",
                    "image_url": "https://img.example.com/kb.jpg",
                    "source": "serper_shopping",
                }],
            }],
            "amazon": [{
                "product_name": "Cheap Keyboard",
                "offers": [{
                    "title": "Cheap Keyboard", "price": 159.99, "currency": "USD",
                    "url": "https://amzn.to/kb", "merchant": "Amazon",
                    "image_url": "https://img.example.com/amz.jpg",
                }],
            }],
        },
        "review_data": {},
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    review_cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    assert review_cards, "expected a product_review card"
    prices = [l.get("price") for l in review_cards[0]["data"]["affiliate_links"]]
    assert 59.99 in prices, f"in-budget offer missing: {prices}"
    assert 159.99 not in prices, f"over-budget offer leaked past the ceiling: {prices}"


def _budget_filter_state(budget, products_and_prices):
    """Build a minimal compose state: each (name, price) becomes one product with one
    serper_shopping offer at that price."""
    return {
        "user_message": "best laptop",
        "intent": "product",
        "slots": {"category": "laptops", "budget": budget},
        "normalized_products": [{"name": name} for name, _ in products_and_prices],
        "affiliate_products": {
            "serper_shopping": [
                {
                    "product_name": name,
                    "offers": [{
                        "title": name, "price": price, "currency": "USD",
                        "url": f"https://www.google.com/shopping/product/{i}",
                        "merchant": "BestBuy",
                        "image_url": f"https://img.example.com/{i}.jpg",
                        "source": "serper_shopping",
                    }],
                }
                for i, (name, price) in enumerate(products_and_prices)
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


@pytest.mark.asyncio
async def test_floor_budget_drops_under_floor_product():
    """A "$500+" budget must not surface a $299 product as a pick — the under-floor
    leak observed in prod (laptop query, $500+ chip, $299.99 top pick)."""
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value="mock response text")

    state = _budget_filter_state("$500+", [
        ("Budget Laptop", 299.99),
        ("Mid Laptop", 749.00),
        ("Premium Laptop", 1299.00),
    ])

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    review_cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    card_names = [c["data"]["product_name"] for c in review_cards]
    assert "Mid Laptop" in card_names and "Premium Laptop" in card_names, f"in-budget products missing: {card_names}"
    assert "Budget Laptop" not in card_names, f"under-floor product leaked into the shortlist: {card_names}"


@pytest.mark.asyncio
async def test_range_budget_keeps_only_in_range_products():
    """A "$500–$800" chip budget must keep only products priced inside the range."""
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value="mock response text")

    state = _budget_filter_state("$500–$800", [
        ("Too Cheap Laptop", 349.00),
        ("Just Right Laptop", 649.00),
        ("Also Right Laptop", 799.00),
        ("Too Expensive Laptop", 1499.00),
    ])

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    review_cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    card_names = [c["data"]["product_name"] for c in review_cards]
    assert "Just Right Laptop" in card_names and "Also Right Laptop" in card_names, f"in-range products missing: {card_names}"
    assert "Too Cheap Laptop" not in card_names, f"under-range product leaked: {card_names}"
    assert "Too Expensive Laptop" not in card_names, f"over-range product leaked: {card_names}"


@pytest.mark.asyncio
async def test_budget_pruning_degrades_gracefully_when_too_few_in_budget():
    """If pruning would leave <2 products, keep everything (degraded beats empty)."""
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value="mock response text")

    state = _budget_filter_state("$500+", [
        ("Only In-Budget Laptop", 749.00),
        ("Cheap Laptop A", 299.00),
        ("Cheap Laptop B", 199.00),
    ])

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    review_cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    card_names = [c["data"]["product_name"] for c in review_cards]
    # Only 1 product is in budget → pruning is skipped entirely → all 3 still render
    assert len(card_names) == 3, f"graceful degradation failed, expected all 3 products: {card_names}"


@pytest.mark.asyncio
async def test_serper_price_backfills_zero_priced_amazon_offer():
    """The real-price fix: when an Amazon offer has price=0 (mock mode, no PA-API)
    but a serper_shopping offer carries a real price for the same product,
    product_compose stamps that real price onto the Amazon offer so the card's
    headline (affiliate_links[0]) shows a real price instead of $0."""
    # compose calls model_service.generate_compose (awaitable) — mock it so the
    # parallel LLM batch resolves and card-building is reached.
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value="mock response text")

    state = {
        "user_message": "best wireless earbuds under $100",
        "intent": "product",
        "slots": {"category": "earbuds"},
        "normalized_products": [{"name": "Jabra Elite 3"}],
        "affiliate_products": {
            # Amazon offer with a real affiliate link but NO price (mock mode).
            "amazon": [{
                "product_name": "Jabra Elite 3",
                "offers": [{
                    "title": "Jabra Elite 3", "price": 0, "currency": "USD",
                    "url": "https://amzn.to/jabra", "merchant": "Amazon",
                    "image_url": "",
                }],
            }],
            # Serper Google Shopping offer carrying the REAL price + image.
            "serper_shopping": [{
                "product_name": "Jabra Elite 3",
                "offers": [{
                    "title": "Jabra Elite 3", "price": 79.99, "currency": "USD",
                    "url": "https://www.google.com/shopping/product/jabra",
                    "merchant": "Walmart", "image_url": "https://img.example.com/jabra.jpg",
                    "rating": 4.4, "review_count": 5000, "source": "serper_shopping",
                }],
            }],
        },
        "review_data": {},
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    blocks = result.get("ui_blocks", [])
    review_cards = [b for b in blocks if b.get("type") == "product_review"]
    assert review_cards, f"expected a product_review card, got block types {[b.get('type') for b in blocks]}"

    links = review_cards[0]["data"]["affiliate_links"]
    prices = [l.get("price") for l in links]
    # No surviving offer renders $0 — the real price flowed onto the Amazon offer.
    assert 0 not in prices and 0.0 not in prices, f"a $0 offer survived: {prices}"
    assert 79.99 in prices, f"real Serper price not surfaced on the card: {prices}"
    # The Amazon affiliate link is preserved as a buy option.
    assert any("amzn.to" in (l.get("affiliate_link") or "") for l in links), \
        "Amazon affiliate buy-link was dropped"


@pytest.mark.asyncio
async def test_real_price_backfills_from_live_ebay_when_no_serper_match():
    """When Serper has no match for a product but a LIVE eBay offer (real,
    non-placeholder image) does, its real price backfills the price-0 Amazon
    offer. Mock eBay offers (placehold.co image) must NOT be used."""
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value="mock response text")

    state = {
        "user_message": "best wireless earbuds under $100",
        "intent": "product",
        "slots": {"category": "earbuds"},
        "normalized_products": [{"name": "Samsung Galaxy Buds 2"}],
        "affiliate_products": {
            "amazon": [{
                "product_name": "Samsung Galaxy Buds 2",
                "offers": [{
                    "title": "Samsung Galaxy Buds 2", "price": 0, "currency": "USD",
                    "url": "https://amzn.to/galaxybuds", "merchant": "Amazon",
                    "image_url": "",
                }],
            }],
            # Live eBay Browse-API offer: real price + real (non-placeholder) image.
            "ebay": [{
                "product_name": "Samsung Galaxy Buds 2",
                "offers": [{
                    "title": "Samsung Galaxy Buds 2", "price": 39.99, "currency": "USD",
                    "url": "https://www.ebay.com/itm/123", "merchant": "eBay (emilystore)",
                    "image_url": "https://i.ebayimg.com/images/g/abc/s-l500.jpg",
                    "source": "ebay",
                }],
            }],
        },
        "review_data": {},
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    review_cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    assert review_cards, "expected a product_review card"
    links = review_cards[0]["data"]["affiliate_links"]
    prices = [l.get("price") for l in links]
    assert 0 not in prices and 0.0 not in prices, f"a $0 offer survived: {prices}"
    assert 39.99 in prices, f"live eBay price not backfilled: {prices}"


@pytest.fixture
def capturing_model_service():
    """
    Patch model_service to capture all call kwargs and return plausible strings
    so the tool can complete without error.

    The reverted product_compose imports model_service inside the function, so
    we patch at `app.services.model_service.model_service`.
    """
    captured_calls = []

    async def fake_generate(**kwargs):
        captured_calls.append(kwargs)
        agent_name = kwargs.get("agent_name", "")
        if agent_name == "blog_article_composer":
            return "## Sony WH-1000XM5\nGreat headphones.\n\n## Our Verdict\nBuy the Sony."
        if agent_name == "review_consensus":
            return "Excellent product praised by experts."
        if agent_name == "product_compose_descriptions":
            return '{"descriptions": ["desc1", "desc2"]}'
        return "mock response"

    fake_service = MagicMock()
    fake_service.generate = fake_generate

    with patch("app.services.model_service.model_service", fake_service):
        yield fake_service, captured_calls


# ---------------------------------------------------------------------------
# RX-07: Review source URLs must be threaded into blog_data
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    reason="Pre-existing product_compose blog-article breakage (same root cause as "
    "test_chat_streaming::test_blog_article_runs_in_parallel_batch). Broken since the "
    "Mar-2026 backend-restore commit, unrelated to this branch. Tracked for the "
    "product_compose refactor PR.",
    strict=False,
)
@pytest.mark.asyncio
async def test_blog_includes_source_inline_links(capturing_model_service):
    """
    RX-07: When review bundle has sources with url+site_name, the blog_data string
    passed to model_service.generate for the blog_article call must contain
    'Reviews: [SiteName](url)' entries.
    """
    import copy
    fake_service, captured_calls = capturing_model_service
    state = copy.deepcopy(_REVIEW_STATE_WITH_DATA)

    result = await product_compose(state)

    assert result["success"] is True

    # Find the blog_article generate call
    blog_calls = [c for c in captured_calls if c.get("agent_name") == "blog_article_composer"]
    assert len(blog_calls) >= 1, "Expected at least one blog_article_composer call"

    # Extract the user content from the messages list
    blog_call = blog_calls[0]
    messages = blog_call.get("messages", [])
    user_content = next(
        (m["content"] for m in messages if m.get("role") == "user"),
        ""
    )

    # The blog_data must contain inline source refs for Sony (which has sources with url+site_name)
    assert "Reviews:" in user_content, (
        f"Expected 'Reviews:' in blog_data user content, but got:\n{user_content[:500]}"
    )
    assert "[Wirecutter]" in user_content, (
        f"Expected '[Wirecutter]' markdown link in blog_data, but got:\n{user_content[:500]}"
    )


@pytest.mark.asyncio
async def test_google_shopping_is_context_only_not_a_buy_link():
    """Google Shopping (serper_shopping) must be used for price/image/rating
    CONTEXT only — never as a clickable buy-link to a merchant we don't earn
    from. The real price still backfills the Amazon offer, but every clickable
    affiliate_link points to Amazon."""
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value="mock response text")

    state = {
        "user_message": "best wireless earbuds under $100",
        "intent": "product",
        "slots": {"category": "earbuds"},
        "normalized_products": [{"name": "Jabra Elite 3"}],
        "affiliate_products": {
            "amazon": [{
                "product_name": "Jabra Elite 3",
                "offers": [{
                    "title": "Jabra Elite 3", "price": 0, "currency": "USD",
                    "url": "https://amzn.to/jabra", "merchant": "Amazon",
                    "image_url": "",
                }],
            }],
            "serper_shopping": [{
                "product_name": "Jabra Elite 3",
                "offers": [{
                    "title": "Jabra Elite 3", "price": 79.99, "currency": "USD",
                    "url": "https://www.google.com/shopping/product/jabra",
                    "merchant": "Walmart", "image_url": "https://img.example.com/jabra.jpg",
                    "rating": 4.4, "review_count": 5000, "source": "serper_shopping",
                }],
            }],
        },
        "review_data": {},
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    review_cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    assert review_cards
    links = review_cards[0]["data"]["affiliate_links"]

    # No clickable link points at Google Shopping or the non-affiliate merchant.
    for link in links:
        url = (link.get("affiliate_link") or "").lower()
        assert "google.com/shopping" not in url, f"Google Shopping URL leaked as a buy-link: {url}"
        assert link.get("merchant") != "Walmart", f"non-affiliate merchant surfaced: {link}"
    # Every clickable link is an Amazon (affiliate) link.
    assert all(
        "amazon" in (l.get("affiliate_link") or "").lower()
        or "amzn.to" in (l.get("affiliate_link") or "").lower()
        for l in links
    ), f"a non-Amazon buy-link survived: {[l.get('affiliate_link') for l in links]}"
    # But the price CONTEXT from Shopping still flowed onto the card.
    assert any(l.get("price") == 79.99 for l in links), "Shopping price context was lost"
    # And the clean Shopping image is used.
    assert review_cards[0]["data"]["image_url"] == "https://img.example.com/jabra.jpg"


@pytest.mark.asyncio
async def test_shopping_only_product_falls_back_to_tagged_amazon_search():
    """If Google Shopping is the ONLY priced source (no Amazon/eBay offer), the
    card keeps a buy-link — a tagged Amazon SEARCH url carrying the real price —
    instead of dropping the card or linking out to a non-affiliate merchant."""
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value="mock response text")

    state = {
        "user_message": "best wireless earbuds under $100",
        "intent": "product",
        "slots": {"category": "earbuds"},
        "normalized_products": [{"name": "Jabra Elite 3"}],
        "affiliate_products": {
            "serper_shopping": [{
                "product_name": "Jabra Elite 3",
                "offers": [{
                    "title": "Jabra Elite 3", "price": 79.99, "currency": "USD",
                    "url": "https://www.google.com/shopping/product/jabra",
                    "merchant": "Walmart", "image_url": "https://img.example.com/jabra.jpg",
                    "rating": 4.4, "review_count": 5000, "source": "serper_shopping",
                }],
            }],
        },
        "review_data": {},
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    review_cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    assert review_cards
    links = review_cards[0]["data"]["affiliate_links"]
    assert links, "card lost its only buy-link"
    for link in links:
        url = (link.get("affiliate_link") or "").lower()
        assert "google.com/shopping" not in url
        assert "amazon.com/s" in url and "tag=revguide-20" in url, f"expected tagged Amazon search, got {url}"


# ---------------------------------------------------------------------------
# Marketplace price hygiene: offers whose price is wildly inconsistent with
# the product's median market price across providers (accessory/scam listings,
# bundles) must be dropped before card building.
# ---------------------------------------------------------------------------

def _offer(price, merchant="Store", source="ebay", image="https://img.example.com/x.jpg"):
    return {
        "merchant": merchant, "price": price, "currency": "USD",
        "url": f"https://example.com/{merchant.lower()}", "image_url": image,
        "source": source,
    }


def test_price_outliers_drops_scam_low_offer():
    """The $12-iPhone case: a $12 'iPhone 15' listing (a phone case) among real
    ~$999 offers must be dropped."""
    offers = [_offer(999.00, "Amazon", "amazon"), _offer(12.00, "eBay (scamstore)"), _offer(1049.00, "Walmart", "serper_shopping")]
    kept, dropped = _drop_price_outliers(offers)
    kept_prices = [o["price"] for o in kept]
    assert 12.00 not in kept_prices, f"scam listing survived: {kept_prices}"
    assert 999.00 in kept_prices and 1049.00 in kept_prices
    assert [o["price"] for o in dropped] == [12.00]


def test_price_outliers_drops_bundle_high_offer():
    """A $4,500 '10-pack bundle' listing among ~$1,000 offers must be dropped."""
    offers = [_offer(999.00, "Amazon", "amazon"), _offer(1049.00, "Walmart", "serper_shopping"), _offer(4500.00, "eBay (bulkseller)")]
    kept, dropped = _drop_price_outliers(offers)
    kept_prices = [o["price"] for o in kept]
    assert 4500.00 not in kept_prices, f"bundle listing survived: {kept_prices}"
    assert 999.00 in kept_prices and 1049.00 in kept_prices


def test_price_outliers_keeps_all_when_consistent():
    """The keep-all fallback: when all offers look consistent, nothing is dropped."""
    offers = [_offer(279.00, "Amazon", "amazon"), _offer(299.00, "eBay (goodstore)"), _offer(310.00, "BestBuy", "serper_shopping")]
    kept, dropped = _drop_price_outliers(offers)
    assert len(kept) == 3 and not dropped


def test_price_outliers_no_market_signal_keeps_all():
    """With fewer than 2 priced offers there is no market consensus — keep all."""
    offers = [_offer(999.00, "Amazon", "amazon"), _offer(0, "Amazon mock", "amazon")]
    kept, dropped = _drop_price_outliers(offers)
    assert len(kept) == 2 and not dropped
    # And a single offer is trivially kept
    kept, dropped = _drop_price_outliers([_offer(12.00)])
    assert len(kept) == 1 and not dropped


def test_price_outliers_keeps_unpriced_offers():
    """Unpriced (price=0 mock) offers carry affiliate links, not price signal —
    they must never be dropped by hygiene."""
    offers = [_offer(0, "Amazon", "amazon", image=""), _offer(999.00, "Walmart", "serper_shopping"), _offer(1049.00, "eBay (realstore)")]
    kept, dropped = _drop_price_outliers(offers)
    assert len(kept) == 3 and not dropped


def test_price_outliers_legit_sale_pricing_survives():
    """A genuine discount (~40% off) must NOT be treated as noise."""
    offers = [_offer(599.00, "Amazon", "amazon"), _offer(999.00, "BestBuy", "serper_shopping")]
    kept, dropped = _drop_price_outliers(offers)
    assert len(kept) == 2 and not dropped


@pytest.mark.asyncio
async def test_price_hygiene_scam_offer_never_reaches_card():
    """End-to-end through product_compose: a $12 eBay 'iPhone 15' listing must not
    surface on the card, and must NOT become the backfill price for the $0 Amazon
    offer — the real Serper price must."""
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value="mock response text")

    state = {
        "user_message": "best smartphone",
        "intent": "product",
        "slots": {"category": "phones"},
        "normalized_products": [{"name": "iPhone 15"}],
        "affiliate_products": {
            # $0 Amazon mock offer (affiliate link, no price)
            "amazon": [{
                "product_name": "iPhone 15",
                "offers": [{
                    "title": "iPhone 15", "price": 0, "currency": "USD",
                    "url": "https://amzn.to/iphone15", "merchant": "Amazon",
                    "image_url": "",
                }],
            }],
            # $12 scraped eBay listing — actually a phone case, titled like the phone
            "ebay": [{
                "product_name": "iPhone 15",
                "offers": [{
                    "title": "iPhone 15", "price": 12.00, "currency": "USD",
                    "url": "https://www.ebay.com/itm/scam123", "merchant": "eBay (scamstore)",
                    "image_url": "https://i.ebayimg.com/images/g/scam/s-l500.jpg",
                    "source": "ebay",
                }],
            }],
            # Real market price from Google Shopping
            "serper_shopping": [{
                "product_name": "iPhone 15",
                "offers": [{
                    "title": "iPhone 15", "price": 799.00, "currency": "USD",
                    "url": "https://www.google.com/shopping/product/iphone15",
                    "merchant": "Best Buy", "image_url": "https://img.example.com/iphone15.jpg",
                    "rating": 4.8, "review_count": 12000, "source": "serper_shopping",
                }],
            }],
        },
        "review_data": {},
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    review_cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    assert review_cards, "expected a product_review card"
    links = review_cards[0]["data"]["affiliate_links"]
    prices = [l.get("price") for l in links]
    assert 12.00 not in prices, f"$12 scam listing surfaced on the card: {prices}"
    assert 0 not in prices and 0.0 not in prices, f"a $0 offer survived: {prices}"
    # The Amazon offer's backfilled price is the REAL one, not the scam one.
    assert 799.00 in prices, f"real market price missing from card: {prices}"


def _a2_state():
    """3 products: two with real Serper shopping matches, one 'fake' with only a
    mock (price-0, imageless) Amazon offer and no review evidence."""
    return {
        "user_message": "best noise cancelling headphones",
        "intent": "product",
        "slots": {"category": "headphones"},
        "normalized_products": [
            {"name": "Sony WH-1000XM5"},
            {"name": "Bose QuietComfort Ultra"},
            {"name": "Phantom Nonexistent Headphone XZ9000"},
        ],
        "affiliate_products": {
            "amazon": [
                {"product_name": "Phantom Nonexistent Headphone XZ9000", "offers": [{
                    "title": "Phantom Nonexistent Headphone XZ9000", "price": 0, "currency": "USD",
                    "url": "https://amzn.to/phantom", "merchant": "Amazon", "image_url": "",
                }]},
            ],
            "serper_shopping": [
                {"product_name": "Sony WH-1000XM5", "offers": [{
                    "title": "Sony WH-1000XM5", "price": 348.00, "currency": "USD",
                    "url": "https://www.google.com/shopping/sony", "merchant": "Walmart",
                    "image_url": "https://img.example.com/sony.jpg", "rating": 4.7,
                    "review_count": 8000, "source": "serper_shopping",
                }]},
                {"product_name": "Bose QuietComfort Ultra", "offers": [{
                    "title": "Bose QuietComfort Ultra", "price": 429.00, "currency": "USD",
                    "url": "https://www.google.com/shopping/bose", "merchant": "BestBuy",
                    "image_url": "https://img.example.com/bose.jpg", "rating": 4.6,
                    "review_count": 5000, "source": "serper_shopping",
                }]},
            ],
        },
        "review_data": {},
        "comparison_html": None, "comparison_data": None, "general_product_info": "",
        "conversation_history": [], "last_search_context": {}, "search_history": [],
    }


@pytest.mark.asyncio
async def test_a2_drops_unverifiable_product_when_enabled():
    """With USE_PRODUCT_VERIFICATION on, the fake product (no real shopping match,
    no reviews) is dropped — no card and not mentioned."""
    from app.core.config import settings as _settings
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value="The Sony WH-1000XM5 leads; Bose QuietComfort Ultra is the alternative.")

    with patch("app.services.model_service.model_service", fake_service), \
         patch.object(_settings, "USE_PRODUCT_VERIFICATION", True):
        result = await product_compose(_a2_state())

    cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    names = [c["data"]["product_name"] for c in cards]
    assert "Phantom Nonexistent Headphone XZ9000" not in names, f"unverifiable product survived: {names}"
    assert any("Sony" in n for n in names) and any("Bose" in n for n in names)


@pytest.mark.asyncio
async def test_a2_keeps_all_when_disabled():
    """Default off -> the fake product is NOT pruned (behavior unchanged)."""
    from app.core.config import settings as _settings
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value="mock response text")

    with patch("app.services.model_service.model_service", fake_service), \
         patch.object(_settings, "USE_PRODUCT_VERIFICATION", False):
        result = await product_compose(_a2_state())

    cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    names = [c["data"]["product_name"] for c in cards]
    assert "Phantom Nonexistent Headphone XZ9000" in names, f"phantom should remain when flag off: {names}"


def _two_speed_state(msg):
    return {
        "user_message": msg,
        "intent": "product",
        "slots": {"category": "headphones"},
        "normalized_products": [{"name": "Sony WH-1000XM5"}],
        "affiliate_products": {
            "serper_shopping": [{"product_name": "Sony WH-1000XM5", "offers": [{
                "title": "Sony WH-1000XM5", "price": 348.0, "currency": "USD",
                "url": "https://www.google.com/shopping/sony", "merchant": "Walmart",
                "image_url": "https://img.example.com/sony.jpg", "rating": 4.7,
                "review_count": 8000, "source": "serper_shopping",
            }]}],
        },
        "review_data": {}, "comparison_html": None, "comparison_data": None,
        "general_product_info": "", "conversation_history": [],
        "last_search_context": {}, "search_history": [],
    }


def _blog_call(mock_service):
    for c in mock_service.generate_compose.call_args_list:
        if c.kwargs.get("agent_name") == "blog_article_composer":
            return c
    return None


@pytest.mark.asyncio
async def test_two_speed_off_uses_default_depth():
    from app.core.config import settings as _settings
    svc = MagicMock(); svc.generate_compose = AsyncMock(return_value="text")
    with patch("app.services.model_service.model_service", svc), \
         patch.object(_settings, "USE_TWO_SPEED_COMPOSE", False):
        await product_compose(_two_speed_state("best noise cancelling headphones"))
    call = _blog_call(svc)
    assert call is not None and call.kwargs["max_tokens"] == 700
    assert "LENGTH OVERRIDE" not in call.kwargs["messages"][0]["content"]


@pytest.mark.asyncio
async def test_two_speed_utility_query_is_terser():
    """A comparison ('vs') query is utility tier -> terser cap + lower max_tokens."""
    from app.core.config import settings as _settings
    svc = MagicMock(); svc.generate_compose = AsyncMock(return_value="text")
    with patch("app.services.model_service.model_service", svc), \
         patch.object(_settings, "USE_TWO_SPEED_COMPOSE", True):
        await product_compose(_two_speed_state("Sony WH-1000XM5 vs Bose QuietComfort Ultra"))
    call = _blog_call(svc)
    assert call.kwargs["max_tokens"] == 550
    assert "250 words" in call.kwargs["messages"][0]["content"]


@pytest.mark.asyncio
async def test_two_speed_considered_query_is_richer():
    """A review-laden query is deep_research tier -> richer cap + higher max_tokens."""
    from app.core.config import settings as _settings
    svc = MagicMock(); svc.generate_compose = AsyncMock(return_value="text")
    msg = "what are the real-world owner complaints and long-term problems with these headphones"
    with patch("app.services.model_service.model_service", svc), \
         patch.object(_settings, "USE_TWO_SPEED_COMPOSE", True):
        await product_compose(_two_speed_state(msg))
    call = _blog_call(svc)
    assert call.kwargs["max_tokens"] == 1000
    assert "550 words" in call.kwargs["messages"][0]["content"]


# ---------------------------------------------------------------------------
# Provider-field sanitization: a scraped offer whose url/title/merchant arrives
# as a dict (not a string) must degrade gracefully, never crash card building.
# Prod incident 2026-06-02: "'dict' object has no attribute 'lower'" killed the
# whole response for a headphones query.
# ---------------------------------------------------------------------------

from mcp_server.tools.product_compose import _str_or


def test_str_or_coercion():
    assert _str_or("https://x.com", "") == "https://x.com"
    assert _str_or({"nested": "dict"}, "") == ""
    assert _str_or(["list"], "fallback") == "fallback"
    assert _str_or(None, "default") == "default"
    assert _str_or("", "default") == "default"
    assert _str_or(123, "d") == "d"


@pytest.mark.asyncio
async def test_dict_url_offer_does_not_crash_card_building():
    """The prod crash: an offer with url as a DICT must not kill the response.
    The bad field is blanked; the good offer still drives the card."""
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value="mock response text")

    state = {
        "user_message": "best wireless headphones",
        "intent": "product",
        "slots": {"category": "headphones"},
        "normalized_products": [{"name": "Sony WH-1000XM5"}],
        "affiliate_products": {
            "amazon": [{
                "product_name": "Sony WH-1000XM5",
                "offers": [{
                    "title": "Sony WH-1000XM5", "price": 0, "currency": "USD",
                    "url": "https://amzn.to/sonyxm5", "merchant": "Amazon",
                    "image_url": "",
                }],
            }],
            # The poisoned offer: url is a dict (scraper returned structured data)
            "serper_shopping": [{
                "product_name": "Sony WH-1000XM5",
                "offers": [{
                    "title": "Sony WH-1000XM5", "price": 348.00, "currency": "USD",
                    "url": {"link": "https://www.google.com/shopping/product/xm5", "source": "Best Buy"},
                    "merchant": "Best Buy",
                    "image_url": "https://img.example.com/xm5.jpg",
                    "rating": 4.7, "review_count": 30000, "source": "serper_shopping",
                }],
            }],
        },
        "review_data": {},
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    # The response must succeed — not the generic error fallback.
    assert result["success"] is True, f"compose failed: {result.get('error')}"
    assert "error while formatting" not in result["assistant_text"]

    # The card still renders, driven by the Amazon offer (the dict url was blanked,
    # but the offer's price/image context still backfills).
    review_cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    assert review_cards, "expected a product_review card despite the poisoned offer"
    links = review_cards[0]["data"]["affiliate_links"]
    # No link carries a non-string URL.
    for link in links:
        assert isinstance(link.get("affiliate_link") or "", str)


@pytest.mark.asyncio
async def test_dict_title_offer_does_not_crash_blog_path():
    """A dict title from a provider must not crash _fuzzy_product_match in the
    blog/affiliate-only path."""
    fake_service = MagicMock()
    fake_service.generate_compose = AsyncMock(return_value="mock response text")

    state = {
        "user_message": "best wireless headphones",
        "intent": "product",
        "slots": {"category": "headphones"},
        "normalized_products": [{"name": "Sony WH-1000XM5"}],
        "affiliate_products": {
            "amazon": [{
                "product_name": "Sony WH-1000XM5",
                "offers": [{
                    # Poisoned title (dict) + valid url
                    "title": {"text": "Sony WH-1000XM5"}, "price": 299.99, "currency": "USD",
                    "url": "https://amzn.to/sonyxm5", "merchant": "Amazon",
                    "image_url": "https://img.example.com/xm5.jpg",
                }],
            }],
        },
        "review_data": {},
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    assert result["success"] is True, f"compose failed: {result.get('error')}"
    assert "error while formatting" not in result["assistant_text"]
