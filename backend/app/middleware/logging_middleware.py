"""
Logging Middleware for Request/Response Tracking
"""
import time
from app.core.centralized_logger import get_logger
import json
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from app.core.colored_logging import get_colored_logger
from app.core.config import settings
from app.core.ip_utils import get_real_client_ip

logger = get_logger(__name__)
colored_logger = get_colored_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured logging of all requests"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details"""
        # Start timer
        start_time = time.time()

        # Generate request ID
        request_id = request.headers.get("X-Request-ID", f"req_{int(start_time * 1000)}")

        # Skip logging for chat stream endpoints and OPTIONS requests
        skip_paths = ["/v1/chat/stream"]
        should_skip_log = (
            request.url.path in skip_paths or
            request.method == "OPTIONS"
        )

        # Log request (skip for certain paths)
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params),
            # Proxy-aware: behind Railway's proxy, request.client.host is the
            # proxy's IP for every request — useless for debugging. Resolve the
            # real client IP the same way the rate limiter does (X-Forwarded-For,
            # trusted only when the connecting IP is a known proxy CIDR).
            "client_ip": get_real_client_ip(request, settings.TRUSTED_PROXY_CIDRS),
            "user_agent": request.headers.get("user-agent"),
        }

        if not should_skip_log:
            colored_logger.api_input(log_data, endpoint=f"{request.method} {request.url.path}")

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log error
            duration = time.time() - start_time
            error_log = {
                **log_data,
                "event": "request_failed",
                "duration_seconds": round(duration, 3),
                "error": str(e),
                "error_type": type(e).__name__,
            }
            colored_logger.error(f"Request failed: {str(e)}", exc_info=True, **error_log)
            raise

        # Calculate duration
        duration = time.time() - start_time

        # Log response (skip for certain paths)
        if not should_skip_log:
            response_log = {
                **log_data,
                "event": "request_completed",
                "status_code": response.status_code,
                "duration_seconds": round(duration, 3),
            }

            colored_logger.api_output(response_log, endpoint=f"{request.method} {request.url.path}")

        # Add custom headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration:.3f}s"

        return response
