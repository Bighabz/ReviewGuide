"""AI card-image generation via OpenRouter (Habib, 2026-06-10).

Results without a real product image (strain cards today; any imageless card
tomorrow) get an AI-generated one. Two rules keep cost bounded:

1. Only the TOP PICK gets a subject-specific image; every other imageless
   card in the same query shares ONE default image → max 2 generations per
   query.
2. Generation is LAZY: compose tools only attach a /v1/images/generate URL.
   The image is generated on the first browser request and Redis-cached
   (GEN_IMAGE_CACHE_TTL), so chat latency and SSE payloads are untouched.

Uses the existing OPENROUTER_API_KEY with an image-capable model
(OPENROUTER_IMAGE_MODEL, default Gemini 2.5 Flash Image). The absolute URL
base comes from PUBLIC_API_URL, falling back to Railway's auto-injected
RAILWAY_PUBLIC_DOMAIN; with neither set (bare local dev), URLs are empty and
cards simply stay imageless.
"""
from __future__ import annotations

import base64
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from app.core.centralized_logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)

# kind → prompt builder. Kinds double as the endpoint whitelist: anything not
# listed here is rejected, so the public endpoint can't be used as a free
# arbitrary-image generator.
IMAGE_KINDS = {
    # Subject anchoring matters for FLUX Schnell: with the strain name as the
    # literal subject, "Blue Dream" came back as a blue dried flower. The nug
    # description leads; the name only flavors it.
    "strain-pick": (
        "Professional studio product photograph of a single dense, frosty "
        "trichome-covered cannabis flower nug (dried marijuana bud, variety "
        "\"{subject}\"), resting on a warm cream background, macro detail, soft "
        "natural light, editorial magazine style. No text, no labels, no people."
    ),
    "strain-default": (
        "Editorial still-life photograph of assorted cannabis flower buds in small "
        "glass apothecary jars on a warm cream background, soft window light, "
        "shallow depth of field, magazine quality. Styled to suit: {subject}. "
        "No text, no labels, no people."
    ),
}

MAX_SUBJECT_LEN = 120


def _public_base() -> str:
    if settings.PUBLIC_API_URL:
        return settings.PUBLIC_API_URL.rstrip("/")
    if getattr(settings, "RAILWAY_PUBLIC_DOMAIN", ""):
        return f"https://{settings.RAILWAY_PUBLIC_DOMAIN}".rstrip("/")
    return ""


def build_image_url(kind: str, subject: str) -> str:
    """Absolute lazy-generation URL for a card's image_url field.

    Empty string when no public base is configured or the kind is unknown —
    callers leave the card imageless, which is the pre-feature behavior.
    """
    base = _public_base()
    if not base or kind not in IMAGE_KINDS or not subject:
        return ""
    subject = subject.strip()[:MAX_SUBJECT_LEN]
    return f"{base}/v1/images/generate?{urlencode({'kind': kind, 'subject': subject})}"


async def _post_fal(prompt: str) -> Dict[str, Any]:
    """POST to fal.ai's synchronous run endpoint (FLUX Schnell: 4 inference
    steps, typically sub-second server-side)."""
    import httpx

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"https://fal.run/{settings.FAL_IMAGE_MODEL.strip('/')}",
            json={
                "prompt": prompt,
                "image_size": "square_hd",
                "num_inference_steps": 4,
                "num_images": 1,
            },
            headers={
                "Authorization": f"Key {settings.FAL_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        return response.json()


async def _download(url: str) -> Optional[bytes]:
    """Fetch generated-image bytes from fal's CDN."""
    import httpx

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


async def _post_openrouter(payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST to OpenRouter chat completions (separate function so tests can mock
    the HTTP layer without touching parsing logic)."""
    import httpx

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        return response.json()


async def generate_image_bytes(prompt: str) -> Optional[bytes]:
    """Generate one image — fal.ai FLUX Schnell when FAL_API_KEY is set
    (sub-second, ~$0.003/image), OpenRouter otherwise. None when the model
    returns no image (refusal) or the response shape is unexpected."""
    if getattr(settings, "FAL_API_KEY", ""):
        return await _generate_via_fal(prompt)
    if not settings.OPENROUTER_API_KEY:
        logger.warning("[image_gen] no FAL_API_KEY or OPENROUTER_API_KEY — skipping generation")
        return None

    data = await _post_openrouter({
        "model": settings.OPENROUTER_IMAGE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image", "text"],
    })

    try:
        images = (data["choices"][0]["message"].get("images") or [])
        if not images:
            logger.info("[image_gen] model returned no image (refusal or text-only)")
            return None
        url = images[0].get("image_url", {}).get("url", "")
        if not url.startswith("data:image/"):
            logger.warning(f"[image_gen] unexpected image url scheme: {url[:40]}")
            return None
        b64 = url.split(",", 1)[1]
        return base64.b64decode(b64)
    except (KeyError, IndexError, ValueError, TypeError) as e:
        logger.warning(f"[image_gen] could not parse OpenRouter response: {e}")
        return None


async def _generate_via_fal(prompt: str) -> Optional[bytes]:
    """fal.ai path: sync run returns hosted CDN URLs (or data URIs in
    sync_mode); fetch the bytes either way."""
    try:
        data = await _post_fal(prompt)
        images = data.get("images") or []
        if not images:
            logger.info("[image_gen] fal returned no image (safety filter or error)")
            return None
        url = images[0].get("url", "") or ""
        if url.startswith("data:image/"):
            return base64.b64decode(url.split(",", 1)[1])
        if url.startswith("http"):
            return await _download(url)
        logger.warning(f"[image_gen] fal returned unexpected url: {url[:40]}")
        return None
    except (KeyError, IndexError, ValueError, TypeError) as e:
        logger.warning(f"[image_gen] could not parse fal response: {e}")
        return None
