"""tone.md compliance — loading/status copy never names competitor sites.

tone.md ("Loading state vocabulary"): loading copy is curious and AMBIGUOUS —
"Searching the web…", "Seeing what others are saying…" — and NEVER names a
source ("According to RTINGS…", "Wirecutter says…" are on the never-list).

review_search's streamed status said "Searching reviews across Wirecutter,
Reddit, RTINGS..." — a literal source attribution rendered to the user. The
frontend has an equivalent test (loadingCopy.test.ts); this is the backend
side, covering every status message a tool emits into tool_citations.
"""
import os
import re

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

import pytest  # noqa: E402

from app.core.config import settings  # noqa: E402
from mcp_server.tools.review_search import review_search  # noqa: E402

# Same blocklist the frontend's loadingCopy.test.ts enforces.
_COMPETITOR_RE = re.compile(
    r"\b(?:RTINGS|Wirecutter|Reddit|Tom['’]?s Guide|CNET|TechRadar|The Verge|Engadget|PCMag|SoundGuys)\b",
    re.IGNORECASE,
)


@pytest.mark.asyncio
async def test_review_search_status_messages_never_name_sources(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_SERPAPI", True)
    monkeypatch.setattr(settings, "SERPAPI_API_KEY", "test-key")

    fake_client_cls = MagicMock()
    fake_client_cls.return_value.search_reviews = AsyncMock(
        side_effect=Exception("no network in tests")
    )

    state = {"product_names": ["Sony WH-1000XM5"], "slots": {"category": "headphones"}}
    with patch("app.services.serpapi.client.SerpAPIClient", fake_client_cls):
        result = await review_search(state)

    assert result["success"] is True
    statuses = [c.get("message", "") for c in result["tool_citations"]]
    assert statuses, "review_search must still emit status updates"
    for message in statuses:
        assert not _COMPETITOR_RE.search(message), (
            f"status message names a source (tone.md violation): {message!r}"
        )
