"""Fix 3 (Defect B-b, 2026-07-05): real stage status over SSE.

plan_executor._emit_tool_citation dispatches a request-scoped LangChain custom
event ("tool_status") so chat.py can forward the ACTUAL stage as an SSE status
event instead of the frontend rotating canned loadingCopy strings. The dispatch
must fire per tool and never raise (best-effort).
"""
import os

import pytest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("ADMIN_PASSWORD", "testpassword123")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

from app.services.plan_executor import PlanExecutor  # noqa: E402


@pytest.mark.asyncio
async def test_emit_tool_citation_dispatches_custom_event():
    ex = PlanExecutor()
    ex.state = {}
    dispatched = []

    async def fake_dispatch(name, data):
        dispatched.append((name, data))

    with patch("langchain_core.callbacks.manager.adispatch_custom_event",
               new=AsyncMock(side_effect=fake_dispatch)):
        await ex._emit_tool_citation("product_evidence", "Reading reviews…")

    assert dispatched, "expected a tool_status custom event to be dispatched"
    name, data = dispatched[0]
    assert name == "tool_status"
    assert data["message"] == "Reading reviews…"
    assert data["tool"] == "product_evidence"
    # citation is still recorded for the results payload
    assert ex.tool_citations and ex.tool_citations[0]["message"] == "Reading reviews…"


@pytest.mark.asyncio
async def test_emit_tool_citation_never_raises_when_dispatch_fails():
    """A dispatch failure (e.g. no callback manager in context) must not break
    the tool flow — the citation is still recorded."""
    ex = PlanExecutor()
    ex.state = {}

    with patch("langchain_core.callbacks.manager.adispatch_custom_event",
               new=AsyncMock(side_effect=RuntimeError("no callback manager"))):
        # Must not raise
        await ex._emit_tool_citation("product_search", "Searching…")

    assert ex.tool_citations[-1]["message"] == "Searching…"
    # state stream_chunk_data still written (unchanged legacy path)
    assert ex.state.get("stream_chunk_data", {}).get("type") == "tool_citation"
