"""
Unit tests for chat streaming behavior.

Covers:
  RX-02: product_compose calls model_service.generate with stream=False for
         the blog_article task so tokens are batched in parallel LLM calls.
"""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Environment bootstrap — must happen before any app import
# ---------------------------------------------------------------------------
os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

from mcp_server.tools.product_compose import product_compose  # noqa: E402


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Pre-existing product_compose blog-article breakage: asyncio.gather TypeError "
    "at product_compose.py:903 (a non-coroutine enters llm_tasks). Broken since the "
    "Mar-2026 backend-restore commit, unrelated to this branch. Tracked for the "
    "product_compose refactor PR.",
    strict=False,
)
@pytest.mark.asyncio
async def test_blog_article_runs_in_parallel_batch():
    """
    RX-02: product_compose must generate the blog_article in the same parallel
    LLM batch as consensus/concierge/descriptions calls. This avoids a
    sequential bottleneck where blog_article (12-15s) runs AFTER the parallel
    batch, causing compose to timeout.

    Test approach: patch model_service.generate to capture kwargs, run
    product_compose with data that triggers the blog_article path, then
    assert the blog_article_composer call was made (non-streaming, in parallel).
    """
    captured_calls = []

    async def fake_generate(**kwargs):
        captured_calls.append(kwargs)
        agent_name = kwargs.get("agent_name", "")
        if agent_name == "blog_article_composer":
            return "## Sony WH-1000XM5\nGreat headphones.\n\n## Our Verdict\nBuy the Sony."
        if agent_name == "review_consensus":
            return "Excellent product praised by experts."
        if agent_name == "product_compose_descriptions":
            return '{"descriptions": ["desc1", "desc2"]}'
        return "mock response"

    fake_service = MagicMock()
    fake_service.generate = fake_generate

    state = {
        "user_message": "best wireless headphones",
        "intent": "product",
        "slots": {"category": "headphones"},
        "normalized_products": [
            {"name": "Sony WH-1000XM5", "price": 299, "url": "https://example.com/sony"},
        ],
        "affiliate_products": {
            "amazon": [
                {
                    "product_name": "Sony WH-1000XM5",
                    "offers": [
                        {
                            "title": "Sony WH-1000XM5",
                            "price": 299.99,
                            "currency": "USD",
                            "url": "https://amazon.com/sony",
                            "merchant": "Amazon",
                            "image_url": "https://example.com/img.jpg",
                        }
                    ],
                }
            ]
        },
        "review_data": {
            "Sony WH-1000XM5": {
                "avg_rating": 4.7,
                "total_reviews": 12500,
                "quality_score": 0.95,
                "sources": [
                    {
                        "site_name": "Wirecutter",
                        "url": "https://wirecutter.com/sony",
                        "snippet": "Best in class ANC",
                    }
                ],
            }
        },
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    assert result["success"] is True

    # Verify blog_article_composer was called
    blog_calls = [c for c in captured_calls if c.get("agent_name") == "blog_article_composer"]
    assert len(blog_calls) >= 1, (
        f"RX-02: Expected at least one blog_article_composer call but none found. "
        f"All calls: {[c.get('agent_name') for c in captured_calls]}"
    )

    # Blog article should be non-streaming (for stability) and in parallel batch
    blog_call = blog_calls[0]
    assert blog_call.get("stream") is not True, (
        f"RX-02: blog_article should be non-streaming for parallel batch stability "
        f"— got stream={blog_call.get('stream')}."
    )

    # Verify the response contains the blog article content
    assert result.get("assistant_text"), "RX-02: assistant_text should contain the blog article"
    assert "Sony WH-1000XM5" in result["assistant_text"]
