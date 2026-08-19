"""
PostgresKV — a Postgres-backed drop-in for the subset of the async redis-py
client this app uses (2026-08-18 Redis retirement).

The whole codebase talks to Redis through the module-global client created in
app.core.redis_client.init_redis(). This class mirrors that client's method
surface (get/set/setex/delete/exists/expire/rpush/lrange/zadd/zcard/
zremrangebyscore/ping/close) on three tables, so every consumer — halt state,
rate limiter, config cache, search/travel/affiliate/image caches — keeps its
code and its tests unchanged while the storage moves into the same Supabase
Postgres that already holds the relational data.

Tables (alembic revision 20260818_0001):
  kv_cache (key PK, value, expires_at, updated_at)         — strings w/ TTL
  kv_zset  (key, member PK pair, score)                    — rate-limit windows
  kv_list  (key, seq PK pair, value, expires_at)           — legacy list ops

TTL is enforced on READ (expires_at filter) and swept periodically by
sweep_expired(), scheduled from app.services.scheduler. Unlike Redis, an
expired row still occupies disk until the sweeper passes — reads never see it.
"""
import time
from typing import Any, Optional

from sqlalchemy import text

from app.core.centralized_logger import get_logger

logger = get_logger(__name__)


def _engine():
    # Late import: the engine global is created by init_db(), which runs before
    # init_redis() in the app lifespan.
    from app.core import database
    if database.engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return database.engine


class PostgresKV:
    """Async redis-py–shaped facade over Postgres tables."""

    # ── core string ops (kv_cache) ──────────────────────────────────────────

    async def get(self, key: str) -> Optional[str]:
        async with _engine().connect() as conn:
            row = (await conn.execute(
                text("SELECT value FROM kv_cache WHERE key = :k "
                     "AND (expires_at IS NULL OR expires_at > now())"),
                {"k": key},
            )).first()
            return row[0] if row else None

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        async with _engine().begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO kv_cache (key, value, expires_at, updated_at) "
                    "VALUES (:k, :v, "
                    "  CASE WHEN CAST(:ex AS integer) IS NULL THEN NULL "
                    "       ELSE now() + make_interval(secs => :ex) END, now()) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, "
                    "  expires_at = EXCLUDED.expires_at, updated_at = now()"
                ),
                {"k": key, "v": str(value), "ex": ex},
            )
        return True

    async def setex(self, key: str, ttl: int, value: Any) -> bool:
        return await self.set(key, value, ex=int(ttl))

    async def delete(self, *keys: str) -> int:
        n = 0
        async with _engine().begin() as conn:
            for key in keys:
                r1 = await conn.execute(
                    text("DELETE FROM kv_cache WHERE key = :k"), {"k": key})
                r2 = await conn.execute(
                    text("DELETE FROM kv_zset WHERE key = :k"), {"k": key})
                r3 = await conn.execute(
                    text("DELETE FROM kv_list WHERE key = :k"), {"k": key})
                n += 1 if (r1.rowcount or r2.rowcount or r3.rowcount) else 0
        return n

    async def exists(self, *keys: str) -> int:
        n = 0
        async with _engine().connect() as conn:
            for key in keys:
                row = (await conn.execute(
                    text("SELECT 1 FROM kv_cache WHERE key = :k "
                         "AND (expires_at IS NULL OR expires_at > now()) "
                         "UNION ALL SELECT 1 FROM kv_zset WHERE key = :k "
                         "UNION ALL SELECT 1 FROM kv_list WHERE key = :k "
                         "LIMIT 1"),
                    {"k": key},
                )).first()
                n += 1 if row else 0
        return n

    async def expire(self, key: str, seconds: int) -> bool:
        async with _engine().begin() as conn:
            r1 = await conn.execute(
                text("UPDATE kv_cache SET expires_at = now() + make_interval(secs => :s) "
                     "WHERE key = :k"), {"k": key, "s": int(seconds)})
            r2 = await conn.execute(
                text("UPDATE kv_list SET expires_at = now() + make_interval(secs => :s) "
                     "WHERE key = :k"), {"k": key, "s": int(seconds)})
        # zset windows self-expire via zremrangebyscore + the sweeper.
        return bool(r1.rowcount or r2.rowcount) or True

    # ── sorted-set ops (kv_zset) — rate limiter sliding window ─────────────

    async def zadd(self, key: str, mapping: dict) -> int:
        async with _engine().begin() as conn:
            for member, score in mapping.items():
                await conn.execute(
                    text("INSERT INTO kv_zset (key, member, score) VALUES (:k, :m, :s) "
                         "ON CONFLICT (key, member) DO UPDATE SET score = EXCLUDED.score"),
                    {"k": key, "m": str(member), "s": float(score)},
                )
        return len(mapping)

    async def zcard(self, key: str) -> int:
        async with _engine().connect() as conn:
            return (await conn.execute(
                text("SELECT count(*) FROM kv_zset WHERE key = :k"), {"k": key},
            )).scalar_one()

    async def zremrangebyscore(self, key: str, min_score, max_score) -> int:
        lo = float("-inf") if str(min_score) in ("-inf", "(-inf",) else float(min_score)
        hi = float("inf") if str(max_score) in ("+inf", "inf") else float(max_score)
        async with _engine().begin() as conn:
            r = await conn.execute(
                text("DELETE FROM kv_zset WHERE key = :k "
                     "AND (:lo = '-Infinity'::float8 OR score >= :lo) "
                     "AND (:hi = 'Infinity'::float8 OR score <= :hi)"),
                {"k": key, "lo": lo, "hi": hi},
            )
            return r.rowcount or 0

    # ── list ops (kv_list) — legacy conversation-history cache ─────────────

    async def rpush(self, key: str, *values: Any) -> int:
        async with _engine().begin() as conn:
            for v in values:
                await conn.execute(
                    text("INSERT INTO kv_list (key, value) VALUES (:k, :v)"),
                    {"k": key, "v": str(v)},
                )
            return (await conn.execute(
                text("SELECT count(*) FROM kv_list WHERE key = :k"), {"k": key},
            )).scalar_one()

    async def lrange(self, key: str, start: int, stop: int) -> list:
        # Only the tail form lrange(key, -limit, -1) is used in this codebase.
        async with _engine().connect() as conn:
            if start < 0 and stop == -1:
                rows = (await conn.execute(
                    text("SELECT value FROM kv_list WHERE key = :k "
                         "AND (expires_at IS NULL OR expires_at > now()) "
                         "ORDER BY seq DESC LIMIT :n"),
                    {"k": key, "n": -start},
                )).all()
                return [r[0] for r in reversed(rows)]
            rows = (await conn.execute(
                text("SELECT value FROM kv_list WHERE key = :k "
                     "AND (expires_at IS NULL OR expires_at > now()) "
                     "ORDER BY seq"),
                {"k": key},
            )).all()
            vals = [r[0] for r in rows]
            end = len(vals) if stop == -1 else stop + 1
            return vals[start:end]

    # ── lifecycle ───────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        async with _engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True

    async def close(self) -> None:
        return None  # storage lifecycle belongs to close_db()


async def sweep_expired(zset_max_age_seconds: int = 172800) -> dict:
    """Delete expired kv rows and stale rate-limit members. Redis evicted these
    for free; here the scheduler calls this periodically (and reads filter on
    expires_at, so correctness never depends on the sweeper's timing)."""
    cutoff = time.time() - zset_max_age_seconds
    async with _engine().begin() as conn:
        c1 = (await conn.execute(
            text("DELETE FROM kv_cache WHERE expires_at IS NOT NULL AND expires_at <= now()")
        )).rowcount
        c2 = (await conn.execute(
            text("DELETE FROM kv_list WHERE expires_at IS NOT NULL AND expires_at <= now()")
        )).rowcount
        c3 = (await conn.execute(
            text("DELETE FROM kv_zset WHERE score <= :cutoff"), {"cutoff": cutoff}
        )).rowcount
    swept = {"kv_cache": c1 or 0, "kv_list": c2 or 0, "kv_zset": c3 or 0}
    if any(swept.values()):
        logger.info(f"[pg_kv] swept expired rows: {swept}")
    return swept
