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
# fal.ai FLUX Schnell (primary provider when FAL_API_KEY is set)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fal_provider_used_when_key_set(monkeypatch):
    """FAL_API_KEY present → fal.ai generates; OpenRouter is never called."""
    monkeypatch.setattr(settings, "FAL_API_KEY", "test-fal-key", raising=False)
    fal_response = {"images": [{"url": "https://fal.media/files/x/out.jpeg", "content_type": "image/jpeg"}]}

    post_fal = AsyncMock(return_value=fal_response)
    post_or = AsyncMock()
    download = AsyncMock(return_value=_PNG)
    with patch.object(image_gen, "_post_fal", new=post_fal), \
         patch.object(image_gen, "_post_openrouter", new=post_or), \
         patch.object(image_gen, "_download", new=download):
        data = await image_gen.generate_image_bytes("a cannabis bud")

    assert data == _PNG
    post_fal.assert_awaited_once()
    post_or.assert_not_awaited()
    download.assert_awaited_once_with("https://fal.media/files/x/out.jpeg")


@pytest.mark.asyncio
async def test_fal_data_uri_response_decoded_without_download(monkeypatch):
    monkeypatch.setattr(settings, "FAL_API_KEY", "test-fal-key", raising=False)
    b64 = base64.b64encode(_PNG).decode()
    fal_response = {"images": [{"url": f"data:image/png;base64,{b64}"}]}

    download = AsyncMock()
    with patch.object(image_gen, "_post_fal", new=AsyncMock(return_value=fal_response)), \
         patch.object(image_gen, "_download", new=download):
        data = await image_gen.generate_image_bytes("a cannabis bud")

    assert data == _PNG
    download.assert_not_awaited()


@pytest.mark.asyncio
async def test_fal_empty_images_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "FAL_API_KEY", "test-fal-key", raising=False)
    with patch.object(image_gen, "_post_fal", new=AsyncMock(return_value={"images": []})):
        assert await image_gen.generate_image_bytes("x") is None


@pytest.mark.asyncio
async def test_openrouter_fallback_when_no_fal_key(monkeypatch):
    monkeypatch.setattr(settings, "FAL_API_KEY", "", raising=False)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-or-key")
    with patch.object(image_gen, "_post_openrouter", new=AsyncMock(return_value=_openrouter_response())):
        data = await image_gen.generate_image_bytes("a cannabis bud")
    assert data == _PNG


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
# Layer 2: AI-written prompts via server-side token handoff
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_store_image_prompt_returns_token_and_persists():
    stored = {}

    async def fake_set(key, value, ex=None, **kw):
        stored[key] = value
        return True

    with patch("app.core.redis_client.redis_set_with_retry", new=fake_set):
        token = await image_gen.store_image_prompt("A dense violet-green nug with amber pistils")

    assert token and len(token) == 16
    assert stored[f"gen_prompt:{token}"] == "A dense violet-green nug with amber pistils"


def test_build_token_image_url(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_API_URL", "https://api.example.com", raising=False)
    url = image_gen.build_token_image_url("abc123def456abcd")
    assert url == "https://api.example.com/v1/images/generate?token=abc123def456abcd"


@pytest.mark.asyncio
async def test_endpoint_token_path_uses_stored_prompt_plus_style_suffix():
    """The endpoint generates ONLY server-stored prompts, and the brand style
    suffix is appended server-side no matter what the LLM wrote."""
    from app.api.v1.images import generate_image

    token = "abc123def456abcd"
    store = {f"gen_prompt:{token}": "A dense violet-green nug with amber pistils"}

    async def fake_get(key, **kw):
        return store.get(key)

    gen = AsyncMock(return_value=_PNG)
    with patch("app.api.v1.images.redis_get_with_retry", new=fake_get), \
         patch("app.api.v1.images.redis_set_with_retry", new=AsyncMock(return_value=True)), \
         patch("app.api.v1.images.generate_image_bytes", new=gen):
        resp = await generate_image(token=token)

    assert resp.media_type == "image/png"
    prompt_used = gen.call_args.args[0]
    assert "violet-green nug" in prompt_used
    assert "warm cream background" in prompt_used, "style suffix must be appended server-side"


@pytest.mark.asyncio
async def test_endpoint_unknown_token_is_404_never_generates():
    from fastapi import HTTPException
    from app.api.v1.images import generate_image

    gen = AsyncMock()
    with patch("app.api.v1.images.redis_get_with_retry", new=AsyncMock(return_value=None)), \
         patch("app.api.v1.images.generate_image_bytes", new=gen):
        with pytest.raises(HTTPException) as exc:
            await generate_image(token="abc123def456abcd")
    assert exc.value.status_code == 404
    gen.assert_not_awaited()


@pytest.mark.asyncio
async def test_endpoint_token_cache_survives_prompt_expiry():
    """A generated image keeps serving from its own cache even after the
    stored prompt's TTL lapses (old conversations keep their images)."""
    from app.api.v1.images import generate_image

    token = "abc123def456abcd"
    store = {f"gen_image:tok:{token}": base64.b64encode(_PNG).decode()}  # image cached, prompt gone

    async def fake_get(key, **kw):
        return store.get(key)

    gen = AsyncMock()
    with patch("app.api.v1.images.redis_get_with_retry", new=fake_get), \
         patch("app.api.v1.images.generate_image_bytes", new=gen):
        resp = await generate_image(token=token)

    assert resp.body == _PNG
    gen.assert_not_awaited()


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
async def test_pick_uses_llm_image_prompt_token_when_present(monkeypatch):
    """Verdict LLM emitted image_prompt → the pick card's URL is a token URL
    (full-context AI prompt, stored server-side), not a subject template."""
    monkeypatch.setattr(settings, "ENABLE_GENERATED_IMAGES", True, raising=False)
    monkeypatch.setattr(settings, "PUBLIC_API_URL", "https://api.example.com", raising=False)

    blog = json.dumps({
        "body": "Blue Dream is the pick.", "follow_up_question": "Evenings?",
        "top_pick": "Blue Dream",
        "image_prompt": "A dense sage-green nug with icy trichomes and amber pistils",
    })
    store_mock = AsyncMock(return_value="abc123def456abcd")
    state = {
        "user_message": "best strains for stress",
        "strain_results": [dict(s) for s in _STRAIN_RESULTS],
        "strain_mode": "recommend", "slots": {}, "conversation_history": [],
    }
    with patch("app.services.model_service.model_service.generate_compose", new=AsyncMock(return_value=blog)), \
         patch("app.services.image_gen.store_image_prompt", new=store_mock):
        result = await strain_compose(state)

    cards = [b["data"] for b in result["ui_blocks"] if b["type"] == "product_review"]
    assert "token=abc123def456abcd" in cards[0]["image_url"]
    stored_prompt = store_mock.call_args.args[0]
    assert "sage-green nug" in stored_prompt
    assert "Blue Dream" in stored_prompt, "strain name must anchor the stored prompt"
    # other cards still share the per-query default
    assert "kind=strain-default" in cards[1]["image_url"]


@pytest.mark.asyncio
async def test_pick_falls_back_to_enriched_subject_without_llm_prompt(monkeypatch):
    """No image_prompt from the LLM → Layer 1: the subject template URL,
    enriched with the structured data compose holds (type + terpene)."""
    monkeypatch.setattr(settings, "ENABLE_GENERATED_IMAGES", True, raising=False)
    monkeypatch.setattr(settings, "PUBLIC_API_URL", "https://api.example.com", raising=False)

    state = {
        "user_message": "best strains for stress",
        "strain_results": [dict(s) for s in _STRAIN_RESULTS],
        "strain_mode": "recommend", "slots": {}, "conversation_history": [],
    }
    with patch(
        "app.services.model_service.model_service.generate_compose",
        new=AsyncMock(return_value=_BLOG),  # no image_prompt field
    ):
        result = await strain_compose(state)

    pick_url = [b["data"] for b in result["ui_blocks"]][0]["image_url"]
    assert "kind=strain-pick" in pick_url
    assert "Hybrid" in pick_url and "Myrcene" in pick_url, (
        f"fallback subject must carry type+terpene context: {pick_url}"
    )


def test_strain_blog_role_requests_image_prompt():
    from mcp_server.tools.strain_compose import _STRAIN_BLOG_ROLE
    assert "image_prompt" in _STRAIN_BLOG_ROLE


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
