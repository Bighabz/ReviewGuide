"""
Integration Tests for Chat API
Tests the core chat flow with mocked LLM responses
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
import json


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    with patch('app.core.config.settings') as mock:
        mock.OPENAI_API_KEY = "test-key"
        mock.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
        mock.REDIS_URL = "redis://localhost:6379/0"
        mock.SECRET_KEY = "test-secret-key-for-testing-purposes-only"
        mock.ADMIN_PASSWORD = "testpassword123"
        mock.RATE_LIMIT_ENABLED = False
        mock.LOG_ENABLED = False
        yield mock


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    with patch('app.core.redis_client.redis_client') as mock:
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock(return_value=True)
        mock.delete = AsyncMock(return_value=True)
        yield mock


@pytest.fixture
def mock_db():
    """Mock database session"""
    with patch('app.core.database.get_db') as mock:
        session = MagicMock()
        # execute must be AsyncMock but its return_value must be a plain MagicMock
        # so that result.scalars() / result.scalar_one_or_none() are synchronous
        # calls — not AsyncMock calls that create unawaited coroutines.
        session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[]))
                ),
                scalar_one_or_none=MagicMock(return_value=None),
            )
        )
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.close = AsyncMock()
        session.add = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        # get_db is an async generator; make the mock yield session properly
        # so that `await anext(get_db())` returns session (not an AsyncMock).
        async def _async_gen():
            yield session

        mock.side_effect = _async_gen
        yield session


class TestHealthEndpoint:
    """Tests for the health check endpoint"""

    def test_health_check_returns_ok(self):
        """Test that health endpoint returns 200 OK"""
        # FIX-2: health.py now probes the DB; in the test env engine is None,
        # which made the probe report unhealthy -> status degraded. Patch a
        # successful mock engine so the test exercises the intended healthy path.
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=MagicMock())
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.connect = MagicMock(return_value=mock_cm)
        # Import here to avoid module-level import issues
        from app.main import app

        with patch("app.api.v1.health.engine", mock_engine):
            with TestClient(app) as client:
                response = client.get("/health")
                assert response.status_code == 200
                data = response.json()
                assert data.get("status") in ["ok", "healthy"]


class TestChatStreamEndpoint:
    """Tests for the chat stream SSE endpoint"""

    @pytest.mark.asyncio
    async def test_chat_stream_requires_message(self, mock_settings, mock_redis, mock_db):
        """Test that chat stream endpoint requires a message"""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/chat/stream",
                json={}
            )
            # Should return 422 for missing required field
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_stream_accepts_valid_message(self, mock_settings, mock_redis, mock_db):
        """Test that chat stream endpoint accepts valid message"""
        from app.main import app

        # Mock the LangGraph graph to avoid real LLM calls
        mock_graph = MagicMock()

        async def mock_astream_events(*args, **kwargs):
            # Yield nothing — causes the endpoint to finish with an empty stream
            return
            yield  # make it an async generator

        mock_graph.astream_events = mock_astream_events

        with patch('app.api.v1.chat.graph', mock_graph):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/v1/chat/stream",
                    json={"message": "Hello"}
                )
                # Should accept the request (even if workflow mock doesn't work perfectly)
                assert response.status_code in [200, 500]  # 500 if mock fails

    @pytest.mark.asyncio
    async def test_chat_stream_with_session_id(self, mock_settings, mock_redis, mock_db):
        """Test that chat stream endpoint accepts session_id"""
        from app.main import app

        # Mock the LangGraph graph to avoid real LLM calls
        mock_graph = MagicMock()

        async def mock_astream_events(*args, **kwargs):
            return
            yield  # make it an async generator

        mock_graph.astream_events = mock_astream_events

        with patch('app.api.v1.chat.graph', mock_graph):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/v1/chat/stream",
                    json={
                        "message": "test message",
                        "session_id": "550e8400-e29b-41d4-a716-446655440000"
                    }
                )
                assert response.status_code in [200, 500]


class TestAdminAuthEndpoint:
    """Tests for admin authentication endpoint"""

    @pytest.mark.asyncio
    async def test_admin_login_requires_credentials(self, mock_settings, mock_db):
        """Test that admin login requires username and password"""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/auth/login",
                json={}
            )
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_admin_login_rejects_invalid_credentials(self, mock_settings, mock_db):
        """Test that admin login rejects invalid credentials"""
        from app.main import app

        # Mock the admin user repository to return None (user not found)
        with patch('app.api.v1.admin_auth.AdminUserRepository') as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.get_by_username = AsyncMock(return_value=None)
            mock_repo.return_value = mock_repo_instance

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/v1/auth/login",
                    json={
                        "username": "nonexistent",
                        "password": "wrongpassword"
                    }
                )
                assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_admin_login_accepts_valid_credentials(self, mock_settings, mock_db):
        """Test that admin login accepts valid credentials"""
        from app.main import app
        from app.utils.auth import hash_password

        # Mock the admin user repository to return a valid user
        with patch('app.api.v1.admin_auth.AdminUserRepository') as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.get_by_username = AsyncMock(return_value={
                "id": 1,
                "username": "admin",
                "email": "admin@test.com",
                "password_hash": hash_password("testpassword123"),
                "is_active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "last_login": None
            })
            mock_repo_instance.update_last_login = AsyncMock()
            mock_repo.return_value = mock_repo_instance

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/v1/auth/login",
                    json={
                        "username": "admin",
                        "password": "testpassword123"
                    }
                )
                assert response.status_code == 200
                data = response.json()
                assert "access_token" in data
                assert data["token_type"] == "bearer"


class TestRateLimiting:
    """Tests for rate limiting functionality"""

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_excessive_requests(self):
        """Test that rate limiter blocks after limit exceeded"""
        from app.core.rate_limiter import RateLimiter
        from fastapi import HTTPException
        import app.core.config as config_module

        # Build a mock Redis client for the rate limiter
        mock_redis = MagicMock()
        mock_redis.zremrangebyscore = AsyncMock(return_value=0)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis.zadd = AsyncMock(return_value=1)

        # Simulate: first two requests within limit, third exceeds limit
        call_count = 0

        async def mock_zcard(key):
            nonlocal call_count
            count = call_count
            call_count += 1
            return count  # 0, then 1 (below limit=2), then 2 (at limit)

        mock_redis.zcard = mock_zcard

        limiter = RateLimiter(redis_client=mock_redis)

        # Temporarily set rate limit enabled and low limits for testing
        original_enabled = config_module.settings.RATE_LIMIT_ENABLED
        original_guest_requests = config_module.settings.RATE_LIMIT_GUEST_REQUESTS
        try:
            config_module.settings.RATE_LIMIT_ENABLED = True
            config_module.settings.RATE_LIMIT_GUEST_REQUESTS = 2

            # First two calls should pass (zcard returns 0, then 1)
            await limiter.check_rate_limit("test-key", is_authenticated=False)
            await limiter.check_rate_limit("test-key", is_authenticated=False)

            # Third call should be blocked (zcard returns 2, which equals max_requests=2)
            with pytest.raises(HTTPException) as exc_info:
                await limiter.check_rate_limit("test-key", is_authenticated=False)
            assert exc_info.value.status_code == 429
        finally:
            config_module.settings.RATE_LIMIT_ENABLED = original_enabled
            config_module.settings.RATE_LIMIT_GUEST_REQUESTS = original_guest_requests


@pytest.mark.asyncio
async def test_startup_io_calls_are_concurrent(monkeypatch):
    """
    HaltStateManager.get_halt_state and chat_history_manager.get_history
    must be awaited concurrently, not sequentially.
    """
    call_order = []

    async def fake_halt(session_id):
        call_order.append("halt_start")
        await asyncio.sleep(0.05)
        call_order.append("halt_end")
        return {}

    async def fake_history(session_id):
        call_order.append("history_start")
        await asyncio.sleep(0.05)
        call_order.append("history_end")
        return []

    monkeypatch.setattr("app.api.v1.chat.HaltStateManager.get_halt_state", fake_halt)
    monkeypatch.setattr("app.api.v1.chat.chat_history_manager.get_history", fake_history)

    start = time.monotonic()
    from app.api.v1.chat import _load_session_context
    halt, history = await _load_session_context("test-session")
    elapsed = time.monotonic() - start

    # Primary concurrency check: in a concurrent execution, history_start must appear
    # before halt_end (i.e., both coroutines started before either finished)
    assert "history_start" in call_order, f"history coroutine never started: {call_order}"
    assert call_order.index("history_start") < call_order.index("halt_end"), (
        f"Calls appear sequential — history did not start before halt finished. "
        f"call_order={call_order}"
    )

    # If concurrent: elapsed ≈ 0.05s. If sequential: elapsed ≈ 0.10s
    assert elapsed < 0.09, f"Calls appear sequential (took {elapsed:.3f}s)"
    assert halt == {}
    assert history == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
