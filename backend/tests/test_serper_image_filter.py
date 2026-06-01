"""
D2 (perf): SerpAPIClient.search_shopping_offer must drop base64 `data:` image
URIs (they bloat the SSE payload ~7-9KB each) and keep only real http(s) images.
"""
import os
import pytest
from unittest.mock import AsyncMock

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

from app.services.serpapi.client import SerpAPIClient  # noqa: E402


def _client_with_shopping(shopping_items):
    client = SerpAPIClient()
    client._get_cached_shopping = AsyncMock(return_value=None)
    client._set_cached_shopping = AsyncMock(return_value=None)
    client._serper_shopping = AsyncMock(return_value={"shopping": shopping_items})
    return client


@pytest.mark.asyncio
async def test_data_uri_image_is_dropped():
    client = _client_with_shopping([
        {"price": "$129.00", "source": "Google", "link": "https://x.com/p",
         "imageUrl": "data:image/webp;base64,UklGRiAAAAA=", "title": "Sony XM5"},
    ])
    offer = await client.search_shopping_offer("Sony XM5")
    assert offer is not None
    assert offer["price"] == 129.0
    assert offer["image_url"] == ""  # data: URI stripped


@pytest.mark.asyncio
async def test_http_image_is_kept():
    url = "https://img.example.com/sony.jpg"
    client = _client_with_shopping([
        {"price": "$129.00", "source": "Google", "link": "https://x.com/p",
         "imageUrl": url, "title": "Sony XM5"},
    ])
    offer = await client.search_shopping_offer("Sony XM5")
    assert offer is not None
    assert offer["image_url"] == url  # real http(s) image preserved


@pytest.mark.asyncio
async def test_missing_image_stays_empty():
    client = _client_with_shopping([
        {"price": "$129.00", "source": "Google", "link": "https://x.com/p", "title": "Sony XM5"},
    ])
    offer = await client.search_shopping_offer("Sony XM5")
    assert offer is not None
    assert offer["image_url"] == ""
