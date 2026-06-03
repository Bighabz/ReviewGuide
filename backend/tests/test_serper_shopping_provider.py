"""
SerperShoppingProvider — Google Shopping as a registered affiliate provider,
with dormant Skimlinks monetization (affiliate provider harmony, Steps 1+2).

Covers:
- registry registration (name + env-var gating contract)
- search_products: real-priced offer → AffiliateProduct; unpriced/None → []
- ENABLE_SERPAPI=False → [] without constructing a client
- Skimlinks wrapping: dormant by default, active only with BOTH flag + ID,
  never wraps Amazon/eBay (direct programs), never double-wraps
"""

import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402
from urllib.parse import quote  # noqa: E402

import pytest  # noqa: E402

from app.services.affiliate.base import AffiliateProduct  # noqa: E402
from app.services.affiliate.registry import AffiliateProviderRegistry  # noqa: E402
from app.services.affiliate.providers.serper_shopping_provider import (  # noqa: E402
    SerperShoppingProvider,
    _is_excluded_domain,
)


SHOPPING_OFFER = {
    "price": 348.0,
    "currency": "USD",
    "merchant": "Walmart",
    "url": "https://www.walmart.com/ip/sony-wh-1000xm5/123",
    "image_url": "https://img.example.com/sony.jpg",
    "title": "Sony WH-1000XM5",
    "rating": 4.7,
    "review_count": 12000,
}


def _provider(publisher_id="", enabled=False, offer=SHOPPING_OFFER):
    """Provider with a mocked Serper client returning `offer`."""
    p = SerperShoppingProvider(
        skimlinks_publisher_id=publisher_id,
        skimlinks_enabled=enabled,
    )
    client = MagicMock()
    client.search_shopping_offer = AsyncMock(return_value=offer)
    p._client = client
    return p, client


# ---------------------------------------------------------------------------
# Registration contract
# ---------------------------------------------------------------------------


def test_provider_is_registered_with_env_gating():
    info = AffiliateProviderRegistry.list_provider_info()
    assert "serper_shopping" in info
    # No required env vars — the provider self-gates on settings (ENABLE_SERPAPI
    # + SERPAPI_API_KEY) inside search_products, matching the old bolt-on's gate.
    assert info["serper_shopping"]["required_env_vars"] == []
    assert "SKIMLINKS_PUBLISHER_ID" in info["serper_shopping"]["optional_env_vars"]


# ---------------------------------------------------------------------------
# search_products
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_returns_real_priced_offer():
    provider, client = _provider()

    with patch(
        "app.services.affiliate.providers.serper_shopping_provider.settings"
    ) as s:
        s.ENABLE_SERPAPI = True
        s.SERPAPI_API_KEY = "test-key"
        results = await provider.search_products("Sony WH-1000XM5")

    assert len(results) == 1
    product = results[0]
    assert isinstance(product, AffiliateProduct)
    assert product.price == 348.0
    assert product.merchant == "Walmart"
    assert product.image_url == "https://img.example.com/sony.jpg"
    # Skimlinks dormant → raw merchant URL passes through unchanged
    assert product.affiliate_link == SHOPPING_OFFER["url"]
    client.search_shopping_offer.assert_awaited_once_with("Sony WH-1000XM5")


@pytest.mark.asyncio
async def test_search_skips_unpriced_and_missing_offers():
    provider_none, _ = _provider(offer=None)
    provider_unpriced, _ = _provider(offer={"price": None, "url": "https://x.com"})

    with patch(
        "app.services.affiliate.providers.serper_shopping_provider.settings"
    ) as s:
        s.ENABLE_SERPAPI = True
        s.SERPAPI_API_KEY = "test-key"
        assert await provider_none.search_products("Obscure Product") == []
        assert await provider_unpriced.search_products("Obscure Product") == []


@pytest.mark.asyncio
async def test_search_returns_empty_when_serpapi_disabled():
    """The gate is settings-based and needs BOTH the flag and the key —
    identical to the old product_affiliate bolt-on."""
    provider, client = _provider()

    with patch(
        "app.services.affiliate.providers.serper_shopping_provider.settings"
    ) as s:
        s.ENABLE_SERPAPI = False
        s.SERPAPI_API_KEY = "test-key"
        assert await provider.search_products("Sony WH-1000XM5") == []

        s.ENABLE_SERPAPI = True
        s.SERPAPI_API_KEY = ""
        assert await provider.search_products("Sony WH-1000XM5") == []

    client.search_shopping_offer.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_swallows_client_errors():
    provider, client = _provider()
    client.search_shopping_offer = AsyncMock(side_effect=RuntimeError("Serper 500"))

    with patch(
        "app.services.affiliate.providers.serper_shopping_provider.settings"
    ) as s:
        s.ENABLE_SERPAPI = True
        s.SERPAPI_API_KEY = "test-key"
        results = await provider.search_products("Sony WH-1000XM5")

    assert results == []


# ---------------------------------------------------------------------------
# Skimlinks wrapping
# ---------------------------------------------------------------------------


def test_wrapping_dormant_without_id_or_flag():
    """DORMANT contract: wrapping requires BOTH the flag and the publisher ID."""
    url = "https://www.walmart.com/ip/123"

    no_id = SerperShoppingProvider(skimlinks_publisher_id="", skimlinks_enabled=True)
    no_flag = SerperShoppingProvider(
        skimlinks_publisher_id="12345X6789", skimlinks_enabled=False
    )
    neither = SerperShoppingProvider(skimlinks_publisher_id="", skimlinks_enabled=False)

    assert no_id.wrap_with_skimlinks(url) == url
    assert no_flag.wrap_with_skimlinks(url) == url
    assert neither.wrap_with_skimlinks(url) == url


def test_wrapping_active_with_id_and_flag():
    provider = SerperShoppingProvider(
        skimlinks_publisher_id="12345X6789", skimlinks_enabled=True
    )
    url = "https://www.walmart.com/ip/123?selected=true"
    wrapped = provider.wrap_with_skimlinks(url)

    assert wrapped.startswith("https://go.skimresources.com/?id=12345X6789")
    assert quote(url, safe="") in wrapped
    assert "&xs=1" in wrapped


def test_wrapping_never_touches_direct_program_merchants():
    """Amazon/eBay have direct affiliate programs — never give Skimlinks the cut."""
    provider = SerperShoppingProvider(
        skimlinks_publisher_id="12345X6789", skimlinks_enabled=True
    )
    for url in (
        "https://www.amazon.com/dp/B0BXYCS74H?tag=revguide-20",
        "https://amzn.to/3abc",
        "https://www.ebay.com/itm/123456",
        "https://www.ebay.co.uk/itm/999",
    ):
        assert provider.wrap_with_skimlinks(url) == url, f"must not wrap {url}"


def test_wrapping_does_not_double_wrap():
    provider = SerperShoppingProvider(
        skimlinks_publisher_id="12345X6789", skimlinks_enabled=True
    )
    already = "https://go.skimresources.com/?id=12345X6789&xs=1&url=https%3A%2F%2Fx.com"
    assert provider.wrap_with_skimlinks(already) == already


@pytest.mark.asyncio
async def test_search_wraps_offer_url_when_skimlinks_active():
    provider, _ = _provider(publisher_id="12345X6789", enabled=True)

    with patch(
        "app.services.affiliate.providers.serper_shopping_provider.settings"
    ) as s:
        s.ENABLE_SERPAPI = True
        s.SERPAPI_API_KEY = "test-key"
        results = await provider.search_products("Sony WH-1000XM5")

    assert len(results) == 1
    assert results[0].affiliate_link.startswith("https://go.skimresources.com/")
    # The original merchant URL is preserved for transparency/debugging
    assert results[0].source_url == SHOPPING_OFFER["url"]


# ---------------------------------------------------------------------------
# Excluded-domain helper
# ---------------------------------------------------------------------------


def test_excluded_domain_helper():
    assert _is_excluded_domain("https://www.amazon.com/dp/X")
    assert _is_excluded_domain("https://smile.amazon.com/dp/X")  # subdomain
    assert _is_excluded_domain("https://www.ebay.com/itm/1")
    assert not _is_excluded_domain("https://www.walmart.com/ip/1")
    assert not _is_excluded_domain("https://www.bestbuy.com/site/1")
    assert not _is_excluded_domain("")
    # Lookalike domains must NOT match (endswith-dot check, not substring)
    assert not _is_excluded_domain("https://www.notamazon.com/x")
    assert not _is_excluded_domain("https://fakeebay.com.evil.io/x")
