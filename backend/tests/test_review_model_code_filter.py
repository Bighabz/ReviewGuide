"""Fix 6 (Defect C bug 3, 2026-07-05): model-code identity filter on review sources.

Search engines return a WH-1000XM4 (over-ear) review for a WF-1000XM4 (earbud)
query — same family, wrong product. search_reviews now drops a source whose own
model code shares NONE with the queried product, keeps code-less sources, and
never filters the bundle to empty.
"""
import os

import pytest
from unittest.mock import AsyncMock

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

from app.services.serpapi.client import (  # noqa: E402
    SerpAPIClient,
    ReviewSource,
    _model_codes,
)


def _src(title, snippet="", url=None):
    return ReviewSource(
        site_name="Site", url=url or f"https://x/{title}", title=title,
        snippet=snippet, authority_score=0.5,
    )


def _client(editorial_sources):
    client = SerpAPIClient()
    client._get_cached = AsyncMock(return_value=None)
    client._set_cached = AsyncMock(return_value=None)
    client._search_editorial = AsyncMock(return_value=editorial_sources)
    client._search_reddit = AsyncMock(return_value=[])
    client._search_shopping = AsyncMock(return_value={})
    return client


# ── unit ────────────────────────────────────────────────────────────────────

def test_model_codes_extraction_and_normalization():
    assert _model_codes("Sony WF-1000XM4 earbuds") == {"WF1000XM4"}
    assert _model_codes("WH1000XM4 headphones") == {"WH1000XM4"}
    assert _model_codes("great wireless earbuds") == set()  # code-less


# ── integration ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_off_model_source_dropped():
    sources = [
        _src("Sony WF-1000XM4 earbud review", "the best true wireless earbuds"),
        _src("Sony WH-1000XM4 over-ear review", "flagship noise-cancelling headphones"),
        _src("Best earbuds this year", "roundup with no model code"),
    ]
    bundle = await _client(sources).search_reviews("Sony WF-1000XM4", "earbuds")
    titles = [s.title for s in bundle.sources]
    assert any("WF-1000XM4" in t for t in titles)
    assert not any("WH-1000XM4" in t for t in titles), "off-model WH source must be dropped"
    assert any("no model code" in s.snippet for s in bundle.sources), "code-less kept"


@pytest.mark.asyncio
async def test_all_off_model_never_filters_to_empty():
    """If every coded source mismatches, keep them rather than return no evidence."""
    sources = [
        _src("Sony WH-1000XM4 review", "over-ear"),
        _src("Sony WH-1000XM5 review", "over-ear"),
    ]
    bundle = await _client(sources).search_reviews("Sony WF-1000XM4", "earbuds")
    assert len(bundle.sources) == 2, "must not filter to empty"


@pytest.mark.asyncio
async def test_codeless_query_leaves_sources_untouched():
    sources = [
        _src("Anker Soundcore review", "budget earbuds"),
        _src("Sony WH-1000XM4 review", "over-ear"),
    ]
    bundle = await _client(sources).search_reviews("best budget earbuds", "earbuds")
    assert len(bundle.sources) == 2, "no query codes → no filtering"
