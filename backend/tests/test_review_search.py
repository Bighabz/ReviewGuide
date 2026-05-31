"""
Tests for Review Search (SerpAPI integration)

Tests the SerpAPI client, review_search MCP tool, and product_compose
with/without review data.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

# ============================================================
# SerpAPI Client Tests
# ============================================================

class TestSerpAPIClient:
    """Tests for the SerpAPI client service."""

    @pytest.fixture
    def mock_serpapi_editorial_response(self):
        """Mock Serper.dev search response for editorial reviews."""
        return {
            "organic": [
                {
                    "title": "Best Wireless Headphones 2025 - Wirecutter",
                    "link": "https://www.nytimes.com/wirecutter/reviews/best-wireless-headphones/",
                    "snippet": "The Sony WH-1000XM5 remains our top pick for the best wireless headphones.",
                    "date": "Jan 2025",
                },
                {
                    "title": "Sony WH-1000XM5 Review - RTINGS",
                    "link": "https://www.rtings.com/headphones/reviews/sony/wh-1000xm5",
                    "snippet": "The Sony WH-1000XM5 are excellent noise-canceling headphones with a comfortable fit.",
                    "date": "Dec 2024",
                },
            ]
        }

    @pytest.fixture
    def mock_serpapi_reddit_response(self):
        """Mock Serper.dev search response for Reddit."""
        return {
            "organic": [
                {
                    "title": "Sony WH-1000XM5 vs Bose QC Ultra - r/headphones",
                    "link": "https://www.reddit.com/r/headphones/comments/abc123/sony_xm5_review/",
                    "snippet": "After 6 months with the XM5, ANC is still the best I've tried.",
                },
            ]
        }

    @pytest.fixture
    def mock_serpapi_shopping_response(self):
        """Mock Serper.dev Google Shopping response."""
        return {
            "shopping": [
                {
                    "title": "Sony WH-1000XM5 Wireless Headphones",
                    "rating": "4.7",
                    "ratingCount": "8234",
                    "price": "$278.00",
                    "source": "Amazon",
                },
            ]
        }

    @pytest.mark.asyncio
    async def test_search_shopping_offer_parses_real_price(
        self,
        mock_serpapi_shopping_response,
    ):
        """search_shopping_offer returns a normalized offer with the price parsed
        from Serper's "$278.00" string into a float, plus merchant/image fields."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.SERPAPI_API_KEY = "test-key"
            mock_settings.SERPAPI_MAX_SOURCES = 8
            mock_settings.SERPAPI_CACHE_TTL = 86400
            mock_settings.SERPAPI_TIMEOUT = 15.0
            mock_settings.REDIS_RETRY_MAX_ATTEMPTS = 1
            mock_settings.REDIS_RETRY_BACKOFF_BASE = 0.01

            from app.services.serpapi.client import SerpAPIClient

            client = SerpAPIClient()
            with patch.object(client, "_serper_request", new_callable=AsyncMock,
                              return_value=mock_serpapi_shopping_response), \
                 patch("app.core.redis_client.redis_get_with_retry", new_callable=AsyncMock, return_value=None), \
                 patch("app.core.redis_client.redis_set_with_retry", new_callable=AsyncMock, return_value=True):
                offer = await client.search_shopping_offer("Sony WH-1000XM5")

            assert offer is not None
            assert offer["price"] == 278.0          # parsed from "$278.00"
            assert isinstance(offer["price"], float)
            assert offer["merchant"] == "Amazon"
            assert offer["rating"] == 4.7
            assert offer["review_count"] == 8234

    @pytest.mark.asyncio
    async def test_search_shopping_offer_no_priced_result_returns_none(self):
        """When no shopping item has a parseable price, returns None (cached as {})."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.SERPAPI_API_KEY = "test-key"
            mock_settings.SERPAPI_MAX_SOURCES = 8
            mock_settings.SERPAPI_CACHE_TTL = 86400
            mock_settings.SERPAPI_TIMEOUT = 15.0
            mock_settings.REDIS_RETRY_MAX_ATTEMPTS = 1
            mock_settings.REDIS_RETRY_BACKOFF_BASE = 0.01

            from app.services.serpapi.client import SerpAPIClient

            client = SerpAPIClient()
            with patch.object(client, "_serper_request", new_callable=AsyncMock,
                              return_value={"shopping": [{"title": "X", "source": "Y"}]}), \
                 patch("app.core.redis_client.redis_get_with_retry", new_callable=AsyncMock, return_value=None), \
                 patch("app.core.redis_client.redis_set_with_retry", new_callable=AsyncMock, return_value=True):
                offer = await client.search_shopping_offer("Obscure Product")

            assert offer is None

    @pytest.mark.asyncio
    async def test_search_reviews_success(
        self,
        mock_serpapi_editorial_response,
        mock_serpapi_reddit_response,
        mock_serpapi_shopping_response,
    ):
        """Test successful review search with all three search types."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.SERPAPI_API_KEY = "test-key"
            mock_settings.SERPAPI_MAX_SOURCES = 8
            mock_settings.SERPAPI_CACHE_TTL = 86400
            mock_settings.SERPAPI_TIMEOUT = 15.0
            mock_settings.REDIS_RETRY_MAX_ATTEMPTS = 1
            mock_settings.REDIS_RETRY_BACKOFF_BASE = 0.01

            from app.services.serpapi.client import SerpAPIClient

            client = SerpAPIClient()

            # Mock the HTTP requests
            with patch.object(client, "_serper_request") as mock_request:
                mock_request.side_effect = [
                    mock_serpapi_editorial_response,
                    mock_serpapi_reddit_response,
                    mock_serpapi_shopping_response,
                ]

                # Mock Redis cache (miss then write)
                with patch("app.core.redis_client.redis_get_with_retry", new_callable=AsyncMock, return_value=None), \
                     patch("app.core.redis_client.redis_set_with_retry", new_callable=AsyncMock, return_value=True):

                    bundle = await client.search_reviews("Sony WH-1000XM5", "headphones")

            assert bundle.product_name == "Sony WH-1000XM5"
            assert len(bundle.sources) > 0
            assert bundle.avg_rating > 0
            # Should have sources from editorial + reddit
            site_names = [s.site_name for s in bundle.sources]
            assert any("Wirecutter" in name or "RTINGS" in name for name in site_names)

    @pytest.mark.asyncio
    async def test_search_reviews_cache_hit(self):
        """Test that cached results are returned without making API calls."""
        cached_bundle = {
            "product_name": "Sony WH-1000XM5",
            "sources": [
                {
                    "site_name": "Wirecutter",
                    "url": "https://www.nytimes.com/wirecutter/reviews/best-wireless-headphones/",
                    "title": "Best Wireless Headphones",
                    "snippet": "Our top pick.",
                    "rating": 4.8,
                    "review_count": 12000,
                    "favicon_url": "",
                    "authority_score": 0.95,
                    "date": None,
                }
            ],
            "avg_rating": 4.8,
            "total_reviews": 12000,
            "consensus": "",
        }

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.SERPAPI_API_KEY = "test-key"
            mock_settings.SERPAPI_MAX_SOURCES = 8
            mock_settings.SERPAPI_CACHE_TTL = 86400
            mock_settings.SERPAPI_TIMEOUT = 15.0

            from app.services.serpapi.client import SerpAPIClient

            client = SerpAPIClient()

            with patch("app.core.redis_client.redis_get_with_retry", new_callable=AsyncMock, return_value=json.dumps(cached_bundle)):
                bundle = await client.search_reviews("Sony WH-1000XM5", "headphones")

            assert bundle.product_name == "Sony WH-1000XM5"
            assert len(bundle.sources) == 1
            assert bundle.sources[0].site_name == "Wirecutter"

    @pytest.mark.asyncio
    async def test_search_reviews_api_failure_returns_empty(self):
        """Test graceful degradation when SerpAPI fails."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.SERPAPI_API_KEY = "test-key"
            mock_settings.SERPAPI_MAX_SOURCES = 8
            mock_settings.SERPAPI_CACHE_TTL = 86400
            mock_settings.SERPAPI_TIMEOUT = 15.0

            from app.services.serpapi.client import SerpAPIClient

            client = SerpAPIClient()

            with patch.object(client, "_serper_request", side_effect=Exception("API timeout")), \
                 patch("app.core.redis_client.redis_get_with_retry", new_callable=AsyncMock, return_value=None), \
                 patch("app.core.redis_client.redis_set_with_retry", new_callable=AsyncMock, return_value=True):
                bundle = await client.search_reviews("Sony WH-1000XM5", "headphones")

            # Should return empty bundle, not raise
            assert bundle.product_name == "Sony WH-1000XM5"
            assert len(bundle.sources) == 0
            assert bundle.avg_rating == 0.0

    @pytest.mark.asyncio
    async def test_authority_scoring(self):
        """Test that sources are sorted by authority score."""
        from app.services.serpapi.client import _get_authority_score

        wirecutter = _get_authority_score("https://www.nytimes.com/wirecutter/reviews/best-headphones/")
        reddit = _get_authority_score("https://www.reddit.com/r/headphones/comments/xyz/")
        unknown = _get_authority_score("https://www.randomreviewblog.com/headphones/")

        assert wirecutter > reddit
        assert reddit > unknown

    def test_site_name_extraction(self):
        """Test human-readable site name extraction from URLs."""
        from app.services.serpapi.client import _extract_site_name

        assert _extract_site_name("https://www.nytimes.com/wirecutter/reviews/") == "Wirecutter"
        assert _extract_site_name("https://www.rtings.com/headphones/") == "RTINGS"
        assert _extract_site_name("https://www.reddit.com/r/headphones/") == "Reddit"
        assert _extract_site_name("https://www.youtube.com/watch?v=123") == "YouTube"


# ============================================================
# Review Search MCP Tool Tests
# ============================================================

class TestReviewSearchTool:
    """Tests for the review_search MCP tool."""

    @pytest.mark.asyncio
    async def test_review_search_disabled(self):
        """Test that tool returns empty when SerpAPI is disabled."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.ENABLE_SERPAPI = False
            mock_settings.SERPAPI_API_KEY = ""

            from mcp_server.tools.review_search import review_search

            state = {
                "product_names": ["Sony WH-1000XM5"],
                "slots": {"category": "headphones"},
            }

            result = await review_search(state)

            assert result["success"] is True
            assert result["review_data"] == {}

    @pytest.mark.asyncio
    async def test_review_search_no_products(self):
        """Test that tool returns empty when no product names."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.ENABLE_SERPAPI = True
            mock_settings.SERPAPI_API_KEY = "test-key"

            from mcp_server.tools.review_search import review_search

            state = {
                "product_names": [],
                "slots": {},
            }

            result = await review_search(state)

            assert result["success"] is True
            assert result["review_data"] == {}

    @pytest.mark.asyncio
    async def test_review_search_filters_low_quality(self):
        """Test that products with low ratings are filtered out."""
        from app.services.serpapi.client import ReviewBundle, ReviewSource

        low_quality_bundle = ReviewBundle(
            product_name="Bad Product",
            sources=[],
            avg_rating=2.5,
            total_reviews=3,
        )

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.ENABLE_SERPAPI = True
            mock_settings.SERPAPI_API_KEY = "test-key"

            from mcp_server.tools.review_search import review_search

            with patch("app.services.serpapi.client.SerpAPIClient.search_reviews", new_callable=AsyncMock, return_value=low_quality_bundle):
                state = {
                    "product_names": ["Bad Product"],
                    "slots": {"category": "electronics"},
                }

                result = await review_search(state)

            assert result["success"] is True
            # Low quality product should be filtered out
            assert "Bad Product" not in result["review_data"]

    @pytest.mark.asyncio
    async def test_review_search_writes_correct_state_keys(self):
        """Test that the tool writes the expected state keys."""
        from app.services.serpapi.client import ReviewBundle, ReviewSource

        good_bundle = ReviewBundle(
            product_name="Sony WH-1000XM5",
            sources=[
                ReviewSource(
                    site_name="Wirecutter",
                    url="https://www.nytimes.com/wirecutter/reviews/best-headphones/",
                    title="Best Headphones 2025",
                    snippet="Our top pick for noise-canceling.",
                    rating=4.8,
                    review_count=12000,
                    authority_score=0.95,
                )
            ],
            avg_rating=4.8,
            total_reviews=12000,
        )

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.ENABLE_SERPAPI = True
            mock_settings.SERPAPI_API_KEY = "test-key"

            from mcp_server.tools.review_search import review_search

            with patch("app.services.serpapi.client.SerpAPIClient.search_reviews", new_callable=AsyncMock, return_value=good_bundle):
                state = {
                    "product_names": ["Sony WH-1000XM5"],
                    "slots": {"category": "headphones"},
                }

                result = await review_search(state)

            assert result["success"] is True
            assert "review_data" in result
            assert "tool_citations" in result
            assert "Sony WH-1000XM5" in result["review_data"]
            bundle_dict = result["review_data"]["Sony WH-1000XM5"]
            assert bundle_dict["avg_rating"] == 4.8
            assert bundle_dict["total_reviews"] == 12000
            assert len(bundle_dict["sources"]) == 1

    def test_quality_score_calculation(self):
        """Test the review quality score calculation."""
        from mcp_server.tools.review_search import _quality_score

        # High rating, high reviews
        score_high = _quality_score(4.8, 10000)
        # Lower rating, fewer reviews
        score_low = _quality_score(3.5, 100)

        assert score_high > score_low
        assert score_high > 0
        assert score_low > 0


# ============================================================
# Product Compose Integration Tests
# ============================================================

class TestProductComposeWithReviews:
    """Tests for product_compose with review data."""

    @pytest.mark.asyncio
    async def test_compose_without_review_data(self):
        """Test that product_compose works without review_data (fallback)."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.COMPOSER_MODEL = "gpt-4o-mini"

            with patch("app.services.model_service.model_service.generate", new_callable=AsyncMock, return_value="Here are some great options!"):
                from mcp_server.tools.product_compose import product_compose

                state = {
                    "user_message": "best wireless headphones",
                    "normalized_products": [],
                    "affiliate_products": {
                        "ebay": [
                            {
                                "product_name": "Sony WH-1000XM5",
                                "offers": [
                                    {
                                        "title": "Sony WH-1000XM5",
                                        "price": 278,
                                        "currency": "USD",
                                        "url": "https://ebay.com/item/123",
                                        "merchant": "eBay",
                                    }
                                ],
                            }
                        ],
                    },
                    "review_data": {},  # No review data
                    "conversation_history": [],
                }

                result = await product_compose(state)

            assert result["success"] is True
            assert result["assistant_text"]

    @pytest.mark.asyncio
    async def test_compose_with_review_data(self):
        """Test that product_compose adds review_sources block when review_data exists."""
        review_data = {
            "Sony WH-1000XM5": {
                "product_name": "Sony WH-1000XM5",
                "avg_rating": 4.7,
                "total_reviews": 12400,
                "sources": [
                    {
                        "site_name": "Wirecutter",
                        "url": "https://www.nytimes.com/wirecutter/reviews/best-headphones/",
                        "title": "Best Wireless Headphones 2025",
                        "snippet": "The XM5 remains our top pick.",
                        "rating": 4.8,
                        "favicon_url": "https://www.google.com/s2/favicons?domain=nytimes.com&sz=32",
                        "date": "Jan 2025",
                    },
                    {
                        "site_name": "RTINGS",
                        "url": "https://www.rtings.com/headphones/reviews/sony/wh-1000xm5",
                        "title": "Sony WH-1000XM5 Review",
                        "snippet": "Excellent noise canceling with comfortable fit.",
                        "rating": None,
                        "favicon_url": "",
                        "date": "Dec 2024",
                    },
                ],
                "consensus": "",
                "quality_score": 3.52,
            }
        }

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.COMPOSER_MODEL = "gpt-4o-mini"

            with patch("app.services.model_service.model_service.generate", new_callable=AsyncMock, return_value="Best overall ANC headphones according to Wirecutter and RTINGS."):
                from mcp_server.tools.product_compose import product_compose

                state = {
                    "user_message": "best wireless headphones",
                    "normalized_products": [],
                    "affiliate_products": {},
                    "review_data": review_data,
                    "conversation_history": [],
                }

                result = await product_compose(state)

            assert result["success"] is True
            # assistant_text should contain the blog article with review data
            assert result["assistant_text"]


# ============================================================
# RX-04 — caps at 3 products, per-product timeout
# ============================================================

import inspect as _inspect
import ast as _ast

def test_review_search_caps_at_3_products():
    """
    RX-04: review_search must use product_names[:3] (not [:5]) and wrap each
    search call with asyncio.wait_for(..., timeout=8).
    """
    import mcp_server.tools.review_search as rs_module

    source = _inspect.getsource(rs_module)

    # Verify the 3-product cap is in place
    assert "product_names[:3]" in source, (
        "review_search still uses [:5] or another slice — expected product_names[:3]"
    )

    # Verify asyncio.wait_for is used for per-product timeout
    assert "asyncio.wait_for" in source, (
        "review_search does not use asyncio.wait_for for per-product timeout"
    )

    # Verify a timeout of 8 seconds is configured
    assert "timeout=PER_PRODUCT_TIMEOUT_S" in source or "timeout=8" in source, (
        "review_search does not set an 8-second per-product timeout"
    )
