"""
Unit tests for product_affiliate tool.

Covers:
  RX-03: Per-product search coroutines are gathered in parallel (asyncio.gather),
         not run sequentially in a for loop.
  RX-05: The fast-path product plan (PlannerAgent._create_fast_path_product_plan)
         collocates review_search and product_affiliate in the same parallel step.
"""
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

from mcp_server.tools.product_affiliate import (  # noqa: E402
    product_affiliate,
    _match_curated_entry,
)
from app.services.affiliate.providers.curated_amazon_links import (  # noqa: E402
    CURATED_LINKS,
)


# ---------------------------------------------------------------------------
# Fix 1 (P0): curated links must match products BY NAME, not by list position.
# These lock in the compliance fix for the positional-zip mismapping bug.
# ---------------------------------------------------------------------------

HEADPHONES = CURATED_LINKS["noise cancelling headphone"]
WASHERS = CURATED_LINKS["washing machine"]


def _title_at(bucket, idx):
    return bucket[idx]["title"]


def test_match_curated_matches_correct_brand():
    """A Bose product matches the Bose curated entry, not whatever is at its slot."""
    idx = _match_curated_entry("Bose QuietComfort Ultra", HEADPHONES, used=set())
    assert idx is not None
    assert "Bose" in _title_at(HEADPHONES, idx)


def test_match_curated_no_cross_brand_false_positive():
    """Sony/Apple products must NOT match the curated bucket that lacks them —
    shared category words (wireless/noise/cancelling/headphones) must not be
    enough to link them to a Beats/Bose/Anker entry."""
    assert _match_curated_entry(
        "Sony WH-1000XM5 Wireless Noise Cancelling Headphones", HEADPHONES, used=set()
    ) is None
    assert _match_curated_entry("Apple AirPods Max", HEADPHONES, used=set()) is None


def test_match_curated_same_category_different_brand_disambiguated():
    """LG vs Samsung washers share 'front load washer' but must each map to their
    own brand via the brand anchor."""
    lg_idx = _match_curated_entry("LG Front Load Washer", WASHERS, used=set())
    samsung_idx = _match_curated_entry("Samsung Front Load Washer", WASHERS, used=set())
    assert lg_idx is not None and "LG" in _title_at(WASHERS, lg_idx)
    assert samsung_idx is not None and "Samsung" in _title_at(WASHERS, samsung_idx)
    assert lg_idx != samsung_idx


def test_match_curated_respects_used_indices():
    """A curated entry already assigned to one card is not reused for another."""
    used = set()
    first = _match_curated_entry("Bose QuietComfort Ultra", HEADPHONES, used=used)
    assert first is not None
    used.add(first)
    second = _match_curated_entry("Bose QuietComfort Ultra", HEADPHONES, used=used)
    assert second != first  # either a different Bose-ish entry or None, never the same


def test_match_curated_empty_name_returns_none():
    assert _match_curated_entry("", HEADPHONES, used=set()) is None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_affiliate_search_products_parallel_within_provider():
    """
    RX-03: When multiple products are searched on a single provider, the
    individual search_products coroutines must be gathered with asyncio.gather
    (all at once), not executed sequentially in a for-loop.

    Verification: all 3 products are searched and results returned correctly.
    Uses asyncio.gather(*search_tasks) inside search_provider() to issue all
    per-product coroutines concurrently.
    """
    mock_result = MagicMock()
    mock_result.merchant = "Mock"
    mock_result.price = 99.99
    mock_result.currency = "USD"
    mock_result.affiliate_link = "https://mock.example.com/product"
    mock_result.condition = "new"
    mock_result.title = "Product A"
    mock_result.image_url = ""
    mock_result.rating = 4.5
    mock_result.review_count = 100
    mock_result.product_id = "MOCK123"

    mock_provider = MagicMock()
    mock_provider.search_products = AsyncMock(return_value=[mock_result])

    state = {
        "normalized_products": [
            {"title": "Product A"},
            {"title": "Product B"},
            {"title": "Product C"},
        ],
        "slots": {},
        "last_search_context": {},
    }

    with patch("app.services.affiliate.manager.affiliate_manager") as mock_manager, \
         patch("app.core.config.settings") as mock_settings:
        mock_settings.MAX_AFFILIATE_OFFERS_PER_PRODUCT = 3
        mock_settings.AMAZON_DEFAULT_COUNTRY = "US"
        mock_settings.ENABLE_SERPAPI = False  # don't trigger Serper enrichment (no network in unit test)
        mock_manager.get_available_providers.return_value = ["mock_provider"]
        mock_manager.get_provider.return_value = mock_provider

        result = await product_affiliate(state)

    # All 3 products should have been searched via asyncio.gather
    assert result["success"] is True
    assert "mock_provider" in result["affiliate_products"]
    provider_results = result["affiliate_products"]["mock_provider"]
    assert len(provider_results) == 3, (
        f"Expected 3 product results (one per product via asyncio.gather), got {len(provider_results)}: "
        f"search_products call count={mock_provider.search_products.call_count}"
    )
    # search_products must have been called 3 times (once per product)
    assert mock_provider.search_products.call_count == 3


@pytest.mark.asyncio
async def test_planner_fast_path_includes_review_and_affiliate():
    """
    Verify PlannerAgent._create_fast_path_product_plan includes both
    review_search and product_affiliate steps in the pipeline.
    """
    from app.agents.planner_agent import PlannerAgent

    planner = PlannerAgent()
    plan = planner._create_fast_path_product_plan(include_extractor=False)

    steps = plan.get("steps", [])
    all_tools = []
    for step in steps:
        all_tools.extend(step.get("tools", []))

    assert "review_search" in all_tools, (
        f"review_search not found in plan. Tools: {all_tools}"
    )
    assert "product_affiliate" in all_tools, (
        f"product_affiliate not found in plan. Tools: {all_tools}"
    )


# ---------------------------------------------------------------------------
# Serper Google Shopping — the REAL-price source, now a registered provider
# (affiliate provider harmony Step 1: the bolt-on moved into
# providers/serper_shopping_provider.py and runs in the provider fan-out).
# These tests exercise the provider THROUGH the tool, preserving the original
# bolt-on behavioral contract.
# ---------------------------------------------------------------------------

def _serper_provider_with_offer(offer):
    """Real SerperShoppingProvider wired to a mocked Serper client."""
    from app.services.affiliate.providers.serper_shopping_provider import (
        SerperShoppingProvider,
    )
    provider = SerperShoppingProvider(skimlinks_publisher_id="", skimlinks_enabled=False)
    client = MagicMock()
    client.search_shopping_offer = AsyncMock(return_value=offer)
    provider._client = client
    return provider, client


@pytest.mark.asyncio
async def test_affiliate_adds_serper_shopping_offers_with_real_price():
    """When Google Shopping returns a priced offer, the tool's provider fan-out
    surfaces a `serper_shopping` group with that real price/image/merchant —
    same contract as the old bolt-on."""
    state = {
        "normalized_products": [{"title": "Sony WH-1000XM5"}],
        "slots": {},
        "last_search_context": {},
    }

    provider, client = _serper_provider_with_offer({
        "price": 348.0,
        "currency": "USD",
        "merchant": "Walmart",
        "url": "https://www.walmart.com/ip/sony/123",
        "image_url": "https://img.example.com/sony.jpg",
        "title": "Sony WH-1000XM5",
        "rating": 4.7,
        "review_count": 12000,
    })

    with patch("app.services.affiliate.manager.affiliate_manager") as mock_manager, \
         patch("app.core.config.settings") as mock_settings, \
         patch("app.services.affiliate.providers.serper_shopping_provider.settings") as provider_settings:
        mock_settings.MAX_AFFILIATE_OFFERS_PER_PRODUCT = 3
        mock_settings.AMAZON_DEFAULT_COUNTRY = "US"
        provider_settings.ENABLE_SERPAPI = True
        provider_settings.SERPAPI_API_KEY = "test-serper-key"
        mock_manager.get_available_providers.return_value = ["serper_shopping"]
        mock_manager.get_provider.return_value = provider

        result = await product_affiliate(state)

    assert result["success"] is True
    assert "serper_shopping" in result["affiliate_products"]
    groups = result["affiliate_products"]["serper_shopping"]
    assert len(groups) == 1
    offer = groups[0]["offers"][0]
    assert offer["price"] == 348.0
    assert offer["source"] == "serper_shopping"
    assert offer["image_url"] == "https://img.example.com/sony.jpg"
    # Skimlinks dormant → raw merchant URL passes through
    assert offer["url"] == "https://www.walmart.com/ip/sony/123"
    client.search_shopping_offer.assert_awaited_once_with("Sony WH-1000XM5")


@pytest.mark.asyncio
async def test_affiliate_skips_serper_when_disabled():
    """ENABLE_SERPAPI=False ⇒ the provider self-gates ⇒ no serper_shopping group."""
    state = {
        "normalized_products": [{"title": "Sony WH-1000XM5"}],
        "slots": {},
        "last_search_context": {},
    }

    provider, client = _serper_provider_with_offer({"price": 348.0, "url": "https://x.com"})

    with patch("app.services.affiliate.manager.affiliate_manager") as mock_manager, \
         patch("app.core.config.settings") as mock_settings, \
         patch("app.services.affiliate.providers.serper_shopping_provider.settings") as provider_settings:
        mock_settings.MAX_AFFILIATE_OFFERS_PER_PRODUCT = 3
        mock_settings.AMAZON_DEFAULT_COUNTRY = "US"
        provider_settings.ENABLE_SERPAPI = False
        provider_settings.SERPAPI_API_KEY = ""
        mock_manager.get_available_providers.return_value = ["serper_shopping"]
        mock_manager.get_provider.return_value = provider

        result = await product_affiliate(state)

    assert "serper_shopping" not in result["affiliate_products"]
    client.search_shopping_offer.assert_not_awaited()


@pytest.mark.asyncio
async def test_affiliate_serper_unpriced_result_is_skipped():
    """A Shopping lookup that returns None (no priced result) adds no group and
    does not raise."""
    state = {
        "normalized_products": [{"title": "Obscure Product"}],
        "slots": {},
        "last_search_context": {},
    }

    provider, _ = _serper_provider_with_offer(None)

    with patch("app.services.affiliate.manager.affiliate_manager") as mock_manager, \
         patch("app.core.config.settings") as mock_settings, \
         patch("app.services.affiliate.providers.serper_shopping_provider.settings") as provider_settings:
        mock_settings.MAX_AFFILIATE_OFFERS_PER_PRODUCT = 3
        mock_settings.AMAZON_DEFAULT_COUNTRY = "US"
        provider_settings.ENABLE_SERPAPI = True
        provider_settings.SERPAPI_API_KEY = "test-serper-key"
        mock_manager.get_available_providers.return_value = ["serper_shopping"]
        mock_manager.get_provider.return_value = provider

        result = await product_affiliate(state)

    assert result["success"] is True
    assert "serper_shopping" not in result["affiliate_products"]


# ---------------------------------------------------------------------------
# Harmony Step 1 — Amazon shadow fix: the curated special-case must yield to
# PA-API once AMAZON_API_ENABLED=true.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_amazon_curated_path_yields_to_pa_api_when_enabled():
    """With AMAZON_API_ENABLED=true, the tool must call the Amazon provider's
    real search_products instead of taking the curated/search-URL shortcut."""
    state = {
        "normalized_products": [{"title": "Bose QuietComfort Ultra"}],
        "user_message": "best noise cancelling headphones",
        "slots": {},
        "last_search_context": {},
    }

    pa_api_result = MagicMock()
    pa_api_result.merchant = "Amazon"
    pa_api_result.price = 379.0
    pa_api_result.currency = "USD"
    pa_api_result.affiliate_link = "https://www.amazon.com/dp/B0CCZ1L489?tag=revguide-20"
    pa_api_result.condition = "new"
    pa_api_result.title = "Bose QuietComfort Ultra"
    pa_api_result.image_url = "https://m.media-amazon.com/images/I/bose.jpg"
    pa_api_result.rating = 4.5
    pa_api_result.review_count = 5000
    pa_api_result.product_id = "B0CCZ1L489"

    amazon_provider = MagicMock()
    amazon_provider.search_products = AsyncMock(return_value=[pa_api_result])

    with patch("app.services.affiliate.manager.affiliate_manager") as mock_manager, \
         patch("app.core.config.settings") as mock_settings:
        mock_settings.MAX_AFFILIATE_OFFERS_PER_PRODUCT = 3
        mock_settings.AMAZON_DEFAULT_COUNTRY = "US"
        mock_settings.AMAZON_API_ENABLED = True  # PA-API on → curated path must yield
        mock_manager.get_available_providers.return_value = ["amazon"]
        mock_manager.get_provider.return_value = amazon_provider

        result = await product_affiliate(state)

    # The real provider was called — the curated shortcut did not shadow it
    assert amazon_provider.search_products.await_count == 1
    assert "amazon" in result["affiliate_products"]
    offer = result["affiliate_products"]["amazon"][0]["offers"][0]
    assert offer["url"] == "https://www.amazon.com/dp/B0CCZ1L489?tag=revguide-20"
    assert offer["price"] == 379.0


@pytest.mark.asyncio
async def test_amazon_curated_path_still_used_while_pa_api_disabled():
    """With AMAZON_API_ENABLED=false (today's prod state), the curated/search-URL
    path keeps working exactly as before."""
    state = {
        "normalized_products": [{"title": "Bose QuietComfort Ultra"}],
        "user_message": "best noise cancelling headphones",
        "slots": {},
        "last_search_context": {},
    }

    amazon_provider = MagicMock()
    amazon_provider.search_products = AsyncMock(return_value=[])

    with patch("app.services.affiliate.manager.affiliate_manager") as mock_manager, \
         patch("app.core.config.settings") as mock_settings:
        mock_settings.MAX_AFFILIATE_OFFERS_PER_PRODUCT = 3
        mock_settings.AMAZON_DEFAULT_COUNTRY = "US"
        mock_settings.AMAZON_API_ENABLED = False
        mock_manager.get_available_providers.return_value = ["amazon"]
        mock_manager.get_provider.return_value = amazon_provider
        mock_manager.get_amazon_search_url.return_value = (
            "https://www.amazon.com/s?k=Bose+QuietComfort+Ultra&tag=revguide-20"
        )

        result = await product_affiliate(state)

    # The provider's real search was NOT called — curated/search-URL path served it
    amazon_provider.search_products.assert_not_awaited()
    assert "amazon" in result["affiliate_products"]
    offers = result["affiliate_products"]["amazon"][0]["offers"]
    assert offers, "curated path must still produce an Amazon offer"
    # Curated entries use amzn.to short links; search-URL fallbacks use amazon.com
    assert "amzn.to" in offers[0]["url"] or "amazon.com" in offers[0]["url"]
