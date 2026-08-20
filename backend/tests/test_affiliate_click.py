"""
T3 (PLAN 2026-08-19): POST /v1/affiliate/click must persist the posted
session_id on the AffiliateClick row.
"""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

from app.api.v1.affiliate import ClickRequest, track_click  # noqa: E402


@pytest.mark.asyncio
async def test_click_persists_session_id():
    """A posted session_id must land on the AffiliateClick row, not be dropped."""
    captured = {}

    def fake_add(obj):
        captured["row"] = obj

    db = MagicMock()
    db.add = fake_add
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    request = ClickRequest(
        provider="cj",
        product_name="Sony WH-1000XM5",
        category="headphones",
        url="https://example.com/aff/sony",
        session_id="sess-abc-123",
    )

    response = await track_click(request, db)

    assert response.tracked is True
    row = captured.get("row")
    assert row is not None, "track_click must db.add() an AffiliateClick row"
    assert row.session_id == "sess-abc-123"
    assert row.provider == "cj"
    db.commit.assert_awaited_once()