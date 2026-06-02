"""Tests for cross-provider SerpAPI failover (Serper.dev -> SerpApi.com).

When Serper.dev errors or runs out of credits, SerpAPIClient fails over to
SerpApi.com (a different provider) and maps its response back into Serper's
shape so all downstream parsers work unchanged. These tests cover the mapping,
the failover trigger, the config gating, and graceful dual-failure (no cache
poisoning) — all with zero real network calls.
"""

import contextlib

import httpx
import pytest
from unittest.mock import AsyncMock, patch


# Base settings the client __init__ reads. Fallback ON + key present by default;
# individual tests override (e.g. to disable fallback) as needed.
BASE_SETTINGS = dict(
    SERPAPI_API_KEY="primary-key",
    SERPAPI_MAX_SOURCES=8,
    SERPAPI_CACHE_TTL=86400,
    SERPAPI_TIMEOUT=15.0,
    REDIS_RETRY_MAX_ATTEMPTS=1,
    REDIS_RETRY_BACKOFF_BASE=0.01,
    SERPAPI_FALLBACK_ENABLED=True,
    SERPAPI_COM_API_KEY="fallback-key",
    SERPAPI_COM_API_KEY_2="",
)


@contextlib.contextmanager
def make_client(**overrides):
    """Yield a SerpAPIClient built against patched settings."""
    cfg = {**BASE_SETTINGS, **overrides}
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.configure_mock(**cfg)
        from app.services.serpapi.client import SerpAPIClient
        yield SerpAPIClient()


def _credit_error() -> httpx.HTTPStatusError:
    """Build the exact Serper.dev 400 'Not enough credits' error."""
    req = httpx.Request("POST", "https://google.serper.dev/search")
    resp = httpx.Response(
        400, json={"message": "Not enough credits", "statusCode": 400}, request=req
    )
    return httpx.HTTPStatusError("400 Bad Request", request=req, response=resp)


# ---------------------------------------------------------------------------
# Response mapping: SerpApi.com schema -> Serper.dev shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_serpapi_com_search_maps_to_serper_organic_shape():
    with make_client() as client:
        serpapi_response = {
            "organic_results": [
                {
                    "title": "Sony WH-1000XM5 Review - RTINGS",
                    "link": "https://www.rtings.com/headphones/reviews/sony/wh-1000xm5",
                    "snippet": "Excellent noise-canceling headphones.",
                    "date": "Dec 2024",
                },
            ]
        }
        with patch.object(client, "_serpapi_com_request", new_callable=AsyncMock,
                          return_value=serpapi_response):
            mapped = await client._serpapi_com_search("Sony WH-1000XM5", num=10)

        assert "organic" in mapped
        assert mapped["organic"][0]["link"].endswith("wh-1000xm5")
        assert mapped["organic"][0]["title"].startswith("Sony")
        assert mapped["organic"][0]["snippet"]


@pytest.mark.asyncio
async def test_serpapi_com_shopping_maps_to_serper_shopping_shape():
    with make_client() as client:
        serpapi_response = {
            "shopping_results": [
                {
                    "title": "Sony WH-1000XM5 Wireless Headphones",
                    "price": "$278.00",
                    "extracted_price": 278.0,
                    "rating": 4.7,
                    "reviews": 8234,
                    "source": "Amazon",
                    "product_link": "https://www.amazon.com/dp/B09XS7JWHH",
                    "thumbnail": "https://example.com/xm5.jpg",
                },
            ]
        }
        with patch.object(client, "_serpapi_com_request", new_callable=AsyncMock,
                          return_value=serpapi_response):
            mapped = await client._serpapi_com_shopping("Sony WH-1000XM5")

        item = mapped["shopping"][0]
        assert item["price"] == "$278.00"          # _parse_price handles the string
        assert item["rating"] == 4.7
        assert item["ratingCount"] == 8234          # serpapi 'reviews' -> serper 'ratingCount'
        assert item["source"] == "Amazon"
        assert item["link"].endswith("B09XS7JWHH")  # product_link -> link
        assert item["imageUrl"].startswith("http")  # thumbnail -> imageUrl


# ---------------------------------------------------------------------------
# Failover trigger on credit exhaustion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_reviews_fails_over_on_credit_exhaustion():
    """Serper.dev 400 'Not enough credits' -> SerpApi.com supplies the reviews."""
    async def fake_serpapi(params):
        if params.get("engine") == "google":
            return {"organic_results": [
                {"title": "XM5 Review - RTINGS",
                 "link": "https://www.rtings.com/headphones/reviews/sony/wh-1000xm5",
                 "snippet": "Great ANC."},
            ]}
        return {"shopping_results": [
            {"title": "Sony WH-1000XM5", "price": "$278.00", "rating": 4.7,
             "reviews": 8234, "source": "Amazon", "product_link": "https://x/y"},
        ]}

    with make_client() as client:
        with patch.object(client, "_serper_request", new_callable=AsyncMock,
                          side_effect=_credit_error()), \
             patch.object(client, "_serpapi_com_request", new_callable=AsyncMock,
                          side_effect=fake_serpapi), \
             patch.object(client, "_get_cached", new_callable=AsyncMock, return_value=None), \
             patch.object(client, "_set_cached", new_callable=AsyncMock):
            bundle = await client.search_reviews("Sony WH-1000XM5", "headphones")

        assert len(bundle.sources) > 0          # reviews came from the fallback provider
        assert bundle.avg_rating > 0


@pytest.mark.asyncio
async def test_search_shopping_offer_fails_over_on_credit_exhaustion():
    async def fake_serpapi(params):
        return {"shopping_results": [
            {"title": "Sony WH-1000XM5", "price": "$278.00", "rating": 4.7,
             "reviews": 8234, "source": "Amazon", "product_link": "https://x/y",
             "thumbnail": "https://img/x.jpg"},
        ]}

    with make_client() as client:
        with patch.object(client, "_serper_request", new_callable=AsyncMock,
                          side_effect=_credit_error()), \
             patch.object(client, "_serpapi_com_request", new_callable=AsyncMock,
                          side_effect=fake_serpapi), \
             patch.object(client, "_get_cached_shopping", new_callable=AsyncMock, return_value=None), \
             patch.object(client, "_set_cached_shopping", new_callable=AsyncMock):
            offer = await client.search_shopping_offer("Sony WH-1000XM5")

        assert offer is not None
        assert offer["price"] == 278.0          # parsed to float through the mapped shape
        assert isinstance(offer["price"], float)
        assert offer["merchant"] == "Amazon"


# ---------------------------------------------------------------------------
# Config gating: no failover unless enabled AND key present
# ---------------------------------------------------------------------------

def test_should_failover_false_when_disabled():
    with make_client(SERPAPI_FALLBACK_ENABLED=False) as client:
        assert client._should_failover(_credit_error()) is False


def test_should_failover_false_when_no_fallback_key():
    with make_client(SERPAPI_COM_API_KEY="") as client:
        assert client._should_failover(_credit_error()) is False


def test_should_failover_true_when_configured():
    with make_client() as client:
        assert client._should_failover(_credit_error()) is True
        # Network/timeout errors also fail over.
        assert client._should_failover(httpx.ConnectTimeout("timeout")) is True


def test_is_credit_exhaustion_detects_serper_400():
    with make_client() as client:
        assert client._is_credit_exhaustion(_credit_error()) is True
        assert client._is_credit_exhaustion(ValueError("nope")) is False


@pytest.mark.asyncio
async def test_no_failover_when_disabled_propagates_error():
    """Flag off -> the Serper error propagates (caught upstream as graceful empty),
    and SerpApi.com is never called."""
    with make_client(SERPAPI_FALLBACK_ENABLED=False) as client:
        serpapi_mock = AsyncMock()
        with patch.object(client, "_serper_request", new_callable=AsyncMock,
                          side_effect=_credit_error()), \
             patch.object(client, "_serpapi_com_request", serpapi_mock):
            with pytest.raises(httpx.HTTPStatusError):
                await client._serper_search("anything")
        serpapi_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Dual failure stays graceful and does NOT poison the cache
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dual_provider_failure_returns_empty_without_caching():
    """Both providers down -> empty bundle, and the empty bundle is NOT cached
    (else the 24h TTL masks the fix for a day)."""
    with make_client() as client:
        set_cached = AsyncMock()
        with patch.object(client, "_serper_request", new_callable=AsyncMock,
                          side_effect=_credit_error()), \
             patch.object(client, "_serpapi_com_request", new_callable=AsyncMock,
                          side_effect=RuntimeError("SerpApi.com error: exhausted")), \
             patch.object(client, "_get_cached", new_callable=AsyncMock, return_value=None), \
             patch.object(client, "_set_cached", set_cached):
            bundle = await client.search_reviews("Sony WH-1000XM5", "headphones")

        assert bundle.sources == []
        assert bundle.avg_rating == 0.0
        set_cached.assert_not_called()         # no cache poisoning on provider error


@pytest.mark.asyncio
async def test_genuine_empty_result_is_still_cached():
    """Searches succeed but return no reviews -> empty bundle IS cached (avoid
    re-querying obscure products); this is the non-error path."""
    with make_client(SERPAPI_FALLBACK_ENABLED=False) as client:
        set_cached = AsyncMock()
        with patch.object(client, "_serper_request", new_callable=AsyncMock,
                          return_value={"organic": [], "shopping": []}), \
             patch.object(client, "_get_cached", new_callable=AsyncMock, return_value=None), \
             patch.object(client, "_set_cached", set_cached):
            bundle = await client.search_reviews("Obscure Gadget", "")

        assert bundle.sources == []
        set_cached.assert_called_once()        # genuine empty -> cached, no error occurred


# ---------------------------------------------------------------------------
# Chained SerpApi.com keys: first exhausted -> second succeeds
# ---------------------------------------------------------------------------

# Stub fallback identifiers for the chain tests. Deliberately named without
# "key"/"token"/"secret" and given non-credential-looking values so the secret
# scanner does not flag them as real credentials.
_FALLBACK_A = "first-fallback-stub"
_FALLBACK_B = "second-fallback-stub"


class _FakeResp:
    def __init__(self, status, json_data):
        self.status_code = status
        self._json = json_data
        self.text = __import__("json").dumps(json_data)

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("GET", "https://serpapi.com/search.json")
            resp = httpx.Response(self.status_code, json=self._json, request=req)
            raise httpx.HTTPStatusError("err", request=req, response=resp)

    def json(self):
        return self._json


class _FakeClient:
    """Async-context-manager httpx.AsyncClient stand-in driven by a behavior fn."""
    def __init__(self, behavior):
        self._behavior = behavior

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None):
        return self._behavior(params or {})


@pytest.mark.asyncio
async def test_serpapi_com_request_falls_through_to_second_key():
    """key #1 out of searches (200 + error body) -> key #2 serves the result."""
    def behavior(params):
        if params.get("api_key") == _FALLBACK_A:
            return _FakeResp(200, {"error": "Your account has run out of searches"})
        return _FakeResp(200, {"organic_results": [
            {"title": "X", "link": "https://x/y", "snippet": "s"}]})

    with make_client(SERPAPI_COM_API_KEY=_FALLBACK_A, SERPAPI_COM_API_KEY_2=_FALLBACK_B) as client:
        assert client.serpapi_com_keys == [_FALLBACK_A, _FALLBACK_B]
        with patch("httpx.AsyncClient", lambda *a, **k: _FakeClient(behavior)):
            mapped = await client._serpapi_com_search("anything")
        assert mapped["organic"][0]["link"] == "https://x/y"


@pytest.mark.asyncio
async def test_serpapi_com_request_raises_when_all_keys_exhausted():
    """Both keys dry -> raise (so the upstream graceful-empty path engages)."""
    def behavior(params):
        return _FakeResp(200, {"error": "out of searches"})

    with make_client(SERPAPI_COM_API_KEY=_FALLBACK_A, SERPAPI_COM_API_KEY_2=_FALLBACK_B) as client:
        with patch("httpx.AsyncClient", lambda *a, **k: _FakeClient(behavior)):
            with pytest.raises(Exception):
                await client._serpapi_com_search("anything")


def test_single_key_still_works_as_a_one_element_chain():
    with make_client() as client:  # only SERPAPI_COM_API_KEY set, _2 is ""
        assert client.serpapi_com_keys == ["fallback-key"]
        assert client._should_failover(_credit_error()) is True
