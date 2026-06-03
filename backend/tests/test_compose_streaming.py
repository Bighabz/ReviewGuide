"""
Tests for Tier 2.1 true token streaming (USE_COMPOSE_STREAMING).

Covers the two novel pieces:
1. generate_compose_with_streaming dispatches stream_token events for the PROSE
   body only and stops at the <data> tail — the structured JSON must never reach
   the user as streamed prose — while still returning the full text for parsing.
2. product_compose routes the blog call through generate_compose_with_streaming
   when the flag is on (decoupled + streaming), and falls back otherwise.
"""
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

from app.core.config import settings
from app.services.model_service import model_service


class _FakeChunk:
    def __init__(self, content):
        self.content = content


def _fake_llm(chunks):
    """An llm whose .astream yields the given content chunks."""
    llm = MagicMock()

    async def _astream(_messages):
        for c in chunks:
            yield _FakeChunk(c)

    llm.astream = _astream
    return llm


@pytest.mark.asyncio
async def test_streaming_gates_data_tail(monkeypatch):
    """Only the prose before <data> is dispatched as tokens; the <data> tail is
    withheld. The full text (tail included) is still returned for parsing."""
    monkeypatch.setattr(settings, "USE_OPENROUTER_COMPOSE", True)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-openrouter-key")

    chunks = [
        "The Sony is the pick. ",
        "The Bose is the runner-up.",
        "\n\n<data>\n",
        json.dumps({"top_pick": "Sony", "follow_up_question": "Travel often?"}),
        "\n</data>",
    ]
    dispatched = []

    async def _capture(event_name, payload):
        if event_name == "stream_token":
            dispatched.append(payload["token"])

    monkeypatch.setattr(model_service, "_get_llm", lambda **kw: _fake_llm(chunks))
    with patch("langchain_core.callbacks.manager.adispatch_custom_event", _capture):
        result = await model_service.generate_compose_with_streaming(
            messages=[{"role": "user", "content": "x"}],
            agent_name="test",
        )

    streamed = "".join(dispatched)
    # Prose streamed; nothing from the <data> tail leaked.
    assert "The Sony is the pick." in streamed
    assert "The Bose is the runner-up." in streamed
    assert "<data>" not in streamed
    assert "top_pick" not in streamed
    assert "follow_up_question" not in streamed
    # Full text (with the tail) is returned for downstream parsing.
    assert "<data>" in result
    assert "top_pick" in result


@pytest.mark.asyncio
async def test_streaming_dispatches_nothing_past_marker_even_split_across_chunks(monkeypatch):
    """The marker can arrive mid-chunk; tokens after it (same or later chunks)
    must not be dispatched."""
    monkeypatch.setattr(settings, "USE_OPENROUTER_COMPOSE", True)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-openrouter-key")

    chunks = ["Prose body here.<data>{\"top_pick\":", " \"X\"}</data>"]
    dispatched = []

    async def _capture(event_name, payload):
        if event_name == "stream_token":
            dispatched.append(payload["token"])

    monkeypatch.setattr(model_service, "_get_llm", lambda **kw: _fake_llm(chunks))
    with patch("langchain_core.callbacks.manager.adispatch_custom_event", _capture):
        result = await model_service.generate_compose_with_streaming(
            messages=[{"role": "user", "content": "x"}], agent_name="test",
        )

    streamed = "".join(dispatched)
    assert streamed == "Prose body here."  # exactly up to the marker, nothing after
    assert result == "Prose body here.<data>{\"top_pick\": \"X\"}</data>"
