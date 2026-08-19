"""
KV client with retry logic (2026-08-18: Redis retired, Postgres-backed).

Historically this module owned the app's Redis connection. The Redis server is
gone — init_redis() now builds a PostgresKV adapter (app.core.pg_kv) that
mirrors the redis-py method surface on Postgres tables in the same database
the app already uses. The module/function names are unchanged on purpose:
every consumer imports `get_redis`/`redis_*_with_retry` from here, and the
test suite patches these exact names.
"""
from app.core.centralized_logger import get_logger
from typing import Any, Optional
import asyncio
from redis.exceptions import ConnectionError, TimeoutError

from app.core.config import settings
from app.core.pg_kv import PostgresKV

logger = get_logger(__name__)

# Global KV client (PostgresKV; the name stays for import/patch compatibility)
redis_client: Optional[PostgresKV] = None
connection_pool = None  # retained for import compatibility; always None now


async def init_redis() -> None:
    """Initialize the Postgres-backed KV adapter (requires init_db() first)."""
    global redis_client

    try:
        client = PostgresKV()
        await client.ping()
        redis_client = client
        logger.info("PostgresKV adapter initialized (Redis retired)")
    except Exception as e:
        logger.error(f"Failed to initialize PostgresKV adapter: {e}")
        raise


async def close_redis() -> None:
    """Close the KV adapter (no-op: storage lifecycle belongs to close_db())."""
    global redis_client
    if redis_client:
        await redis_client.close()
    logger.info("PostgresKV adapter closed")


async def get_redis() -> PostgresKV:
    """Get the KV client instance"""
    if not redis_client:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return redis_client


async def redis_get_with_retry(key: str, max_retries: int = None) -> Optional[str]:
    """Get value from Redis with automatic retry"""
    max_retries = max_retries or settings.REDIS_RETRY_MAX_ATTEMPTS
    client = await get_redis()

    for attempt in range(max_retries):
        try:
            return await client.get(key)
        except (ConnectionError, TimeoutError) as e:
            if attempt == max_retries - 1:
                logger.error(f"Redis GET failed after {max_retries} attempts: {e}")
                raise
            logger.warning(f"Redis GET attempt {attempt + 1} failed, retrying...")
            await asyncio.sleep(settings.REDIS_RETRY_BACKOFF_BASE * (2 ** attempt))  # Exponential backoff


async def redis_set_with_retry(
    key: str,
    value: str,
    ex: Optional[int] = None,
    max_retries: int = None
) -> bool:
    """Set value in Redis with automatic retry"""
    max_retries = max_retries or settings.REDIS_RETRY_MAX_ATTEMPTS
    client = await get_redis()

    for attempt in range(max_retries):
        try:
            return await client.set(key, value, ex=ex)
        except (ConnectionError, TimeoutError) as e:
            if attempt == max_retries - 1:
                logger.error(f"Redis SET failed after {max_retries} attempts: {e}")
                raise
            logger.warning(f"Redis SET attempt {attempt + 1} failed, retrying...")
            await asyncio.sleep(settings.REDIS_RETRY_BACKOFF_BASE * (2 ** attempt))


async def redis_delete_with_retry(key: str, max_retries: int = None) -> int:
    """Delete key from Redis with automatic retry"""
    max_retries = max_retries or settings.REDIS_RETRY_MAX_ATTEMPTS
    client = await get_redis()

    for attempt in range(max_retries):
        try:
            return await client.delete(key)
        except (ConnectionError, TimeoutError) as e:
            if attempt == max_retries - 1:
                logger.error(f"Redis DELETE failed after {max_retries} attempts: {e}")
                raise
            logger.warning(f"Redis DELETE attempt {attempt + 1} failed, retrying...")
            await asyncio.sleep(settings.REDIS_RETRY_BACKOFF_BASE * (2 ** attempt))
