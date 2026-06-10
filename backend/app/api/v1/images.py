"""Lazy AI image generation endpoint.

GET /v1/images/generate?kind=<whitelisted>&subject=<text>

Cards carry these URLs in image_url; the browser's <img> request triggers
generation on first hit, after which the PNG comes from Redis. kind is
whitelisted via image_gen.IMAGE_KINDS so this can't be driven as a free
arbitrary-image generator; subject length is capped for the same reason.
"""
import asyncio
import base64
import hashlib
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.core.centralized_logger import get_logger
from app.core.config import settings
from app.core.dependencies import check_rate_limit
from app.core.redis_client import redis_get_with_retry, redis_set_with_retry
from app.services.image_gen import IMAGE_KINDS, MAX_SUBJECT_LEN, generate_image_bytes

logger = get_logger(__name__)
router = APIRouter()


def _cache_key(kind: str, subject: str) -> str:
    digest = hashlib.sha256(f"{kind}:{subject.strip().lower()}".encode()).hexdigest()[:24]
    return f"gen_image:{digest}"


# Request coalescing: a carousel fires N identical image requests at once; on
# a cold cache each used to trigger its own OpenRouter generation (4x cost,
# seen in prod 2026-06-10). Concurrent requests for the same cache key now
# share ONE in-flight generation task.
_inflight: Dict[str, "asyncio.Task[Optional[bytes]]"] = {}


async def _generate_coalesced(cache_key: str, prompt: str) -> Optional[bytes]:
    task = _inflight.get(cache_key)
    if task is None:
        task = asyncio.create_task(generate_image_bytes(prompt))
        _inflight[cache_key] = task
        task.add_done_callback(lambda _t: _inflight.pop(cache_key, None))
    try:
        return await asyncio.shield(task)
    except Exception as e:
        logger.warning(f"[images] coalesced generation failed for {cache_key}: {e}")
        return None


async def generate_image(kind: str, subject: str) -> Response:
    """Core handler (route wrapper below adds the rate-limit dependency)."""
    if kind not in IMAGE_KINDS:
        raise HTTPException(status_code=400, detail="Unknown image kind")
    subject = (subject or "").strip()
    if not subject or len(subject) > MAX_SUBJECT_LEN:
        raise HTTPException(status_code=400, detail="Invalid subject")

    cache_key = _cache_key(kind, subject)
    cached = await redis_get_with_retry(cache_key)
    if cached:
        return Response(
            content=base64.b64decode(cached),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    if not getattr(settings, "ENABLE_GENERATED_IMAGES", False):
        raise HTTPException(status_code=404, detail="Image generation disabled")

    prompt = IMAGE_KINDS[kind].format(subject=subject)
    image = await _generate_coalesced(cache_key, prompt)
    if not image:
        raise HTTPException(status_code=404, detail="No image available")

    await redis_set_with_retry(
        cache_key,
        base64.b64encode(image).decode(),
        ex=settings.GEN_IMAGE_CACHE_TTL,
    )
    logger.info(f"[images] generated + cached {kind} image for {subject!r} ({len(image)} bytes)")
    return Response(
        content=image,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/generate")
async def generate_image_route(
    kind: str = Query(...),
    subject: str = Query(...),
    _rate_limit: None = Depends(check_rate_limit),
) -> Response:
    return await generate_image(kind=kind, subject=subject)
