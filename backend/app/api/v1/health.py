"""
Health Check Endpoint
"""
import dataclasses
import os
import sqlalchemy
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from app.core.centralized_logger import get_logger

from app.core.redis_client import get_redis
from app.core.database import engine
from app.services.startup_manifest import get_manifest

logger = get_logger(__name__)

router = APIRouter()


def _running_version() -> str:
    """Return the git SHA of the currently-running build.

    Railway injects ``RAILWAY_GIT_COMMIT_SHA`` as a *runtime* environment
    variable on GitHub-connected deploys (the primary deploy path) — NOT as
    a Docker build arg, which is why the build-time ``GIT_SHA`` (Dockerfile
    ``ARG``) stayed ``"unknown"`` in production. So we read the runtime var
    first, then fall back to the build-time ``GIT_SHA`` (set when a build
    passes ``--build-arg``), then ``"unknown"`` (local dev).

    A single curl against ``/health`` then tells you the exact running
    commit — the SHA-vs-HEAD check that was missing during the
    2026-05-20→25 silent deploy gap.
    """
    for var in ("RAILWAY_GIT_COMMIT_SHA", "GIT_SHA"):
        val = os.environ.get(var, "").strip()
        if val and val.lower() != "unknown":
            return val
    return "unknown"


class LivenessResponse(BaseModel):
    """Simple liveness check response"""
    status: str
    timestamp: datetime


@router.get("/", response_model=LivenessResponse)
async def liveness():
    """
    Simple liveness probe for ALB health checks
    Always returns 200 OK if the server is running
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow()
    }


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    timestamp: datetime
    database: str
    redis: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    Returns the status of the application and its dependencies
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "database": "unknown",
        "redis": "unknown",
        "version": _running_version(),
    }

    # Check database
    try:
        if engine:
            async with engine.connect() as conn:
                await conn.execute(sqlalchemy.text("SELECT 1"))
            health_status["database"] = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["database"] = "unhealthy"
        health_status["status"] = "degraded"

    # Check Redis
    try:
        redis = await get_redis()
        await redis.ping()
        health_status["redis"] = "healthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        health_status["redis"] = "unhealthy"
        health_status["status"] = "degraded"

    # Return 503 if any service is down
    if health_status["status"] == "degraded":
        raise HTTPException(status_code=503, detail=health_status)

    return health_status


@router.get("/health/ready")
async def readiness_check():
    """
    RFC §3.3 — Provider capability readiness probe.

    Returns 200 for 'ok' or 'degraded' (service is up, even if some optional
    providers are missing env vars).
    Returns 503 only when critical providers (LLM) are unavailable or when the
    startup manifest has not been generated yet.
    """
    manifest = get_manifest()

    if manifest is None:
        raise HTTPException(status_code=503, detail="Startup not complete")

    if manifest.all_critical_providers_ok:
        all_ok = all(
            p.status == "ok" for p in manifest.providers if p.enabled
        )
        status = "ok" if all_ok else "degraded"
    else:
        status = "unavailable"

    response = {
        "status": status,
        "manifest": dataclasses.asdict(manifest),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    if status == "unavailable":
        raise HTTPException(status_code=503, detail=response)

    return response
