"""
FastAPI Main Application
ReviewGuide.ai - Multi-Agent AI Affiliate + Travel Assistant
"""
from app.core.centralized_logger import get_logger
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings, load_config_overrides_from_db
from app.core.database import init_db, close_db
from app.core.redis_client import init_redis, close_redis
from app.core.logging_config import setup_logging
from app.middleware.logging_middleware import LoggingMiddleware
from app.api.v1 import chat, health, admin, admin_auth, admin_users, affiliate, telemetry, qos, images
from app.services.search.config import setup_search_provider
from app.services.travel.config import setup_travel_providers
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.startup_manifest import (
    build_startup_manifest,
    log_startup_manifest,
    set_manifest,
)

# Configure structured logging with centralized control
setup_logging(
    log_level=settings.LOG_LEVEL,
    use_json=settings.LOG_FORMAT == "json",
    use_colors=settings.LOG_FORMAT == "colored",
    enabled=settings.LOG_ENABLED
)
logger = get_logger(__name__)

# Sentry error monitoring (added 2026-04-21).
# Requires: pip install "sentry-sdk[fastapi]" and SENTRY_DSN env var.
# No-op if SDK not installed or DSN empty — safe for local dev.
_sentry_dsn = getattr(settings, "SENTRY_DSN", "") or ""
if _sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=_sentry_dsn,
            environment=getattr(settings, "ENV", "development"),
            integrations=[FastApiIntegration(), StarletteIntegration()],
            traces_sample_rate=0.1,
            # Redact known sensitive keys from breadcrumbs/payloads.
            send_default_pii=False,
        )
        logger.info("[sentry] initialized (env=%s)", getattr(settings, "ENV", "?"))
    except ImportError:
        logger.warning("[sentry] SENTRY_DSN set but sentry-sdk not installed — skipping")
    except Exception as _e:  # noqa: BLE001
        logger.warning("[sentry] init failed: %s", _e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager"""
    # Startup
    logger.info("Starting ReviewGuide.ai API server")
    try:
        await init_db()
        await init_redis()
        logger.info("Database and Redis connections initialized")

        # Load config overrides from database (without pre-caching to Redis)
        await load_config_overrides_from_db()
        logger.info("Config overrides loaded from database")

        # Initialize search provider
        setup_search_provider()
        logger.info("Search provider initialized")

        # Initialize travel providers
        setup_travel_providers()
        logger.info("Travel providers initialized")

        # Build and log the provider capability manifest (RFC §3.3)
        _manifest = build_startup_manifest()
        log_startup_manifest(_manifest)
        set_manifest(_manifest)

        # Start background scheduler for link health checks
        start_scheduler()
        logger.info("Background scheduler started")

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        # Exit immediately if services fail to initialize
        import sys
        sys.exit(1)
    yield
    # Shutdown
    logger.info("Shutting down ReviewGuide.ai API server")
    try:
        # Stop background scheduler
        stop_scheduler()
        logger.info("Background scheduler stopped")

        await close_db()
        await close_redis()
        logger.info("Database and Redis connections closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI app
app = FastAPI(
    title="ReviewGuide.ai API",
    description="Multi-Agent AI Affiliate + Travel Assistant",
    version="1.0.0",
    lifespan=lifespan
)

# DISABLED: FastAPI auto-instrumentation creates too many noisy HTTP spans
# We now use CallbackHandler for LLM tracing only
# instrument_fastapi(app)

# Add custom logging middleware FIRST (middlewares are executed in reverse order)
app.add_middleware(LoggingMiddleware)

# Add CORS middleware SECOND (will execute first due to reverse order)
# SECURITY: Use explicit origins from settings, never wildcard in production
cors_kwargs = {
    "allow_origins": settings.cors_origins_list,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.CORS_ORIGIN_REGEX:
    cors_kwargs["allow_origin_regex"] = settings.CORS_ORIGIN_REGEX
app.add_middleware(CORSMiddleware, **cors_kwargs)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(admin_auth.router, prefix="/v1/auth", tags=["Authentication"])
app.include_router(chat.router, prefix="/v1/chat", tags=["Chat"])
app.include_router(admin.router, prefix="/v1/admin", tags=["Admin"])
app.include_router(admin_auth.router, prefix="/v1/admin/auth", tags=["Admin Auth"])
app.include_router(admin_users.router, prefix="/v1/admin/users", tags=["Admin Users"])
app.include_router(affiliate.router, prefix="/v1/affiliate", tags=["Affiliate"])
app.include_router(telemetry.router, prefix="/v1", tags=["Telemetry"])
app.include_router(qos.router, prefix="/v1", tags=["QoS"])
app.include_router(images.router, prefix="/v1/images", tags=["Images"])


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
        log_level="info"
    )
