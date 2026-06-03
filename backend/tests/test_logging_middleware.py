"""
Logging middleware — proxy-aware client IP (QA Round 6 P2 sweep).

Behind Railway's proxy, request.client.host is the proxy's IP for every
request, which made the request logs useless for debugging per-user issues.
The middleware must resolve the real client IP the same way the rate limiter
does: get_real_client_ip (X-Forwarded-For, trusted only when the connecting
IP is inside TRUSTED_PROXY_CIDRS).
"""
import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

from unittest.mock import MagicMock, patch  # noqa: E402

import pytest  # noqa: E402

from app.middleware.logging_middleware import LoggingMiddleware  # noqa: E402


def _fake_request(path="/v1/products", method="GET"):
    request = MagicMock()
    request.headers = {"user-agent": "pytest"}
    request.method = method
    url = MagicMock()
    url.path = path
    request.url = url
    request.query_params = {}
    request.client.host = "100.64.0.2"  # Railway proxy IP
    return request


async def _ok_response(_request):
    response = MagicMock()
    response.status_code = 200
    response.headers = {}
    return response


@pytest.mark.asyncio
async def test_request_log_uses_proxy_aware_client_ip():
    """The logged client_ip is resolved via get_real_client_ip, not the raw
    connecting (proxy) IP."""
    with patch(
        "app.middleware.logging_middleware.get_real_client_ip",
        return_value="203.0.113.7",
    ) as mock_resolve, patch(
        "app.middleware.logging_middleware.colored_logger"
    ) as mock_logger:
        middleware = LoggingMiddleware(app=MagicMock())
        request = _fake_request()

        await middleware.dispatch(request, _ok_response)

    mock_resolve.assert_called_once()
    logged = mock_logger.api_input.call_args.args[0]
    assert logged["client_ip"] == "203.0.113.7", (
        "request log must carry the X-Forwarded-For-resolved IP, not the proxy's"
    )


@pytest.mark.asyncio
async def test_real_ip_resolution_uses_trusted_proxy_cidrs():
    """End-to-end through the real get_real_client_ip: a request arriving from a
    trusted proxy CIDR takes the X-Forwarded-For client; an untrusted source
    keeps the connecting IP (header spoofing from the open internet is ignored)."""
    from app.core.ip_utils import get_real_client_ip

    trusted = ["100.64.0.0/10"]

    proxied = MagicMock()
    proxied.client.host = "100.64.0.2"  # inside the trusted CIDR
    proxied.headers = {"X-Forwarded-For": "203.0.113.7, 100.64.0.2"}
    assert get_real_client_ip(proxied, trusted) == "203.0.113.7"

    spoofer = MagicMock()
    spoofer.client.host = "198.51.100.5"  # NOT a trusted proxy
    spoofer.headers = {"X-Forwarded-For": "203.0.113.7"}
    assert get_real_client_ip(spoofer, trusted) == "198.51.100.5"
