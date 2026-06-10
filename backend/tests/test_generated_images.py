"""AI-generated card images via OpenRouter (Habib, 2026-06-10).

Strain cards (and any future imageless results) get AI-generated images:
- the TOP PICK gets its own subject-specific image
- every OTHER imageless card in the query shares ONE default image per query
- at most 2 generations per query, and they're LAZY: cards carry a
  /v1/images/generate URL; the image is generated on first browser request
  and Redis-cached, so chat latency and SSE payloads are untouched.

Generation uses the existing OPENROUTER_API_KEY (no new provider); the
absolute URL base comes from PUBLIC_API_URL or Railway's auto-injected
RAILWAY_PUBLIC_DOMAIN.
"""
import base64
import json
import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

from unittest.mock import AsyncMock, patch  # noqa: E402

import pytest  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.services import image_gen  # noqa: E402
from mcp_server.tools.strain_compose import strain_compose  # noqa: E402

_PNG = b"\x89PNG\r\n\x1a\nfakebytes"


# ---------------------------------------------------------------------------
# URL building
# ---------------------------------------------------------------------------

def test_image_urls_use_public_api_url(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_API_URL", "https://api.reviewguide.ai", raising=False)
    url = image_gen.build_image_url("strain-pick", "Blue Dream")
    assert url.startswith("https://api.reviewguide.ai/v1/images/generate?")
    assert "kind=strain-pick" in url
    assert "Blue+Dream" in url or "Blue%20Dream" in url


def test_image_urls_fall_back_to_railway_domain(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_API_URL", "", raising=False)
    monkeypatch.setattr(settings, "RAILWAY_PUBLIC_DOMAIN", "backend-production.up.railway.app", raising=False)
    url = image_gen.build_image_url("strain-default", "strains for sleep")
    assert url.startswith("https://backend-production.up.railway.app/v1/images/generate?")


def test_image_urls_empty_without_public_base(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_API_URL", "", raising=False)
    monkeypatch.setattr(settings, "RAILWAY_PUBLIC_DOMAIN", "", raising=False)
    assert image_gen.build_image_url("strain-pick", "Blue Dream") == ""


# ---------------------------------------------------------------------------
# OpenRouter generation
# ---------------------------------------------------------------------------

def _openrouter_response(with_image=True):
    images = []
    if with_image:
        b64 = base64.b64encode(_PNG).decode()
        images = [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]
    return {"choices": [{"message": {"content": "here you go", "images": images}}]}


@pytest.mark.asyncio
async def test_generate_image_bytes_parses_openrouter_data_uri(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-or-key")
    with patch.object(image_gen, "_post_openrouter", new=AsyncMock(return_value=_openrouter_response())):
        data = await image_gen.generate_image_bytes("a cannabis bud")
    assert data == _PNG


@pytest.mark.asyncio
async def test_generate_image_bytes_none_when_model_refuses(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-or-key")
    with patch.object(image_gen, "_post_openrouter", new=AsyncMock(return_value=_openrouter_response(with_image=False))):
        assert await image_gen.generate_image_bytes("x") is None


@pytest.mark.asyncio
async def test_generate_image_bytes_none_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    post = AsyncMock()
    with patch.object(image_gen, "_post_openrouter", new=post):
        assert await image_gen.generate_image_bytes("x") is None
    post.assert_not_awaited()


# ---------------------------------------------------------------------------
# Endpoint: lazy generation + Redis cache
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_endpoint_generates_caches_and_serves_png():
    from app.api.v1.images import generate_image

    cache = {}

    async def fake_get(key, **kw):
        return cache.get(key)

    async def fake_set(key, value, ex=None, **kw):
        cache[key] = value
        return True

    gen = AsyncMock(return_value=_PNG)
    with patch("app.api.v1.images.redis_get_with_retry", new=fake_get), \
         patch("app.api.v1.images.redis_set_with_retry", new=fake_set), \
         patch("app.api.v1.images.generate_image_bytes", new=gen):
        resp1 = await generate_image(kind="strain-pick", subject="Blue Dream")
        resp2 = await generate_image(kind="strain-pick", subject="Blue Dream")

    assert resp1.media_type == "image/png"
    assert resp1.body == _PNG
    assert resp2.body == _PNG
    assert gen.await_count == 1, "second request must come from cache"


@pytest.mark.asyncio
async def test_concurrent_identical_requests_coalesce_into_one_generation():
    """Cold-cache race seen in prod 2026-06-10: a carousel fires N identical
    image requests at once and each triggered its own OpenRouter generation
    (4x cost). Concurrent requests for the same kind+subject must share ONE
    generation."""
    import asyncio
    from app.api.v1.images import generate_image

    cache = {}

    async def fake_get(key, **kw):
        return cache.get(key)

    async def fake_set(key, value, ex=None, **kw):
        cache[key] = value
        return True

    async def slow_generate(prompt):
        await asyncio.sleep(0.05)
        return _PNG

    gen = AsyncMock(side_effect=slow_generate)
    with patch("app.api.v1.images.redis_get_with_retry", new=fake_get), \
         patch("app.api.v1.images.redis_set_with_retry", new=fake_set), \
         patch("app.api.v1.images.generate_image_bytes", new=gen):
        responses = await asyncio.gather(*(
            generate_image(kind="strain-default", subject="best strains for sleep")
            for _ in range(4)
        ))

    assert all(r.body == _PNG for r in responses)
    assert gen.await_count == 1, f"expected 1 coalesced generation, got {gen.await_count}"


@pytest.mark.asyncio
async def test_endpoint_rejects_unknown_kind_and_long_subjects():
    from fastapi import HTTPException
    from app.api.v1.images import generate_image

    with pytest.raises(HTTPException):
        await generate_image(kind="anything-goes", subject="x")
    with pytest.raises(HTTPException):
        await generate_image(kind="strain-pick", subject="y" * 200)


@pytest.mark.asyncio
async def test_endpoint_404_when_generation_fails():
    from fastapi import HTTPException
    from app.api.v1.images import generate_image

    with patch("app.api.v1.images.redis_get_with_retry", new=AsyncMock(return_value=None)), \
         patch("app.api.v1.images.redis_set_with_retry", new=AsyncMock(return_value=True)), \
         patch("app.api.v1.images.generate_image_bytes", new=AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as exc:
            await generate_image(kind="strain-pick", subject="Blue Dream")
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# strain_compose wiring: pick image + one shared default per query
# ---------------------------------------------------------------------------

_STRAIN_RESULTS = [
    {"name": "Blue Dream", "strain_type": "Hybrid", "dominant_terpene": "Myrcene",
     "feelings": ["Happy"], "helps_with": ["Stress"], "score": 0.9,
     "match_reasons": [], "leafly_url": "https://www.leafly.com/search?q=Blue%20Dream"},
    {"name": "Sour Diesel", "strain_type": "Sativa", "dominant_terpene": "Caryophyllene",
     "feelings": ["Energetic"], "helps_with": ["Fatigue"], "score": 0.8,
     "match_reasons": [], "leafly_url": "https://www.leafly.com/search?q=Sour%20Diesel"},
    {"name": "Candyland", "strain_type": "Sativa", "dominant_terpene": "Caryophyllene",
     "feelings": ["Uplifted"], "helps_with": ["Stress"], "score": 0.7,
     "match_reasons": [], "leafly_url": "https://www.leafly.com/search?q=Candyland"},
]

_BLOG = json.dumps({"body": "Blue Dream is the pick.", "follow_up_question": "Evenings?", "top_pick": "Blue Dream"})


@pytest.mark.asyncio
async def test_strain_cards_get_pick_image_and_shared_default(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_GENERATED_IMAGES", True, raising=False)
    monkeypatch.setattr(settings, "PUBLIC_API_URL", "https://api.example.com", raising=False)

    state = {
        "user_message": "best strains for stress",
        "strain_results": [dict(s) for s in _STRAIN_RESULTS],
        "strain_mode": "recommend",
        "slots": {},
        "conversation_history": [],
    }
    with patch(
        "app.services.model_service.model_service.generate_compose",
        new=AsyncMock(return_value=_BLOG),
    ):
        result = await strain_compose(state)

    cards = [b["data"] for b in result["ui_blocks"] if b["type"] == "product_review"]
    assert cards[0]["product_name"] == "Blue Dream"
    # Top pick: subject-specific generated image
    assert "kind=strain-pick" in cards[0]["image_url"]
    assert "Blue" in cards[0]["image_url"]
    # All other cards share ONE default image per query (max 2 generations)
    other_urls = {c["image_url"] for c in cards[1:]}
    assert len(other_urls) == 1
    assert "kind=strain-default" in other_urls.pop()


@pytest.mark.asyncio
async def test_strain_cards_imageless_when_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_GENERATED_IMAGES", False, raising=False)

    state = {
        "user_message": "best strains for stress",
        "strain_results": [dict(s) for s in _STRAIN_RESULTS],
        "strain_mode": "recommend",
        "slots": {},
        "conversation_history": [],
    }
    with patch(
        "app.services.model_service.model_service.generate_compose",
        new=AsyncMock(return_value=_BLOG),
    ):
        result = await strain_compose(state)

    for b in result["ui_blocks"]:
        assert b["data"]["image_url"] == ""
