"""
Tests for the review_consensus ui_block (the "How They Compare" cards).

product_compose must:
1. Emit a `review_consensus` block (one entry per reviewed product, ranked by
   quality_score) whenever review_data is present — replacing comparison_html.
2. Fall back to the old `comparison_html` block when review_data is empty.
3. Never surface review-site names in consensus text (tone.md: "No source
   citations. Synthesize.").

Also covers the rating-scale normalization in the search client: editorial /10
ratings must be normalized to /5 before averaging so star displays never exceed 5.
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

from mcp_server.tools.product_compose import product_compose


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _base_state(**overrides):
    state = {
        "user_message": "best noise cancelling headphones under $300",
        "intent": "product",
        "slots": {"category": "headphones"},
        "normalized_products": [
            {"name": "Sony WH-1000XM5", "price": 299, "url": "https://example.com/sony"},
            {"name": "Bose QuietComfort 45", "price": 279, "url": "https://example.com/bose"},
        ],
        "affiliate_products": {
            "serper_shopping": [
                {
                    "product_name": "Sony WH-1000XM5",
                    "offers": [{
                        "title": "Sony WH-1000XM5", "price": 299.99, "currency": "USD",
                        "url": "https://www.google.com/shopping/product/sony", "merchant": "BestBuy",
                        "image_url": "https://img.example.com/sony.jpg",
                        "source": "serper_shopping",
                    }],
                },
                {
                    "product_name": "Bose QuietComfort 45",
                    "offers": [{
                        "title": "Bose QuietComfort 45", "price": 279.00, "currency": "USD",
                        "url": "https://www.google.com/shopping/product/bose", "merchant": "BestBuy",
                        "image_url": "https://img.example.com/bose.jpg",
                        "source": "serper_shopping",
                    }],
                },
            ],
        },
        "review_data": {},
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }
    state.update(overrides)
    return state


_REVIEW_DATA = {
    "Sony WH-1000XM5": {
        "avg_rating": 4.7,
        "total_reviews": 12500,
        "quality_score": 0.95,
        "sources": [
            {"site_name": "Wirecutter", "url": "https://wirecutter.com/sony", "snippet": "Best in class ANC"},
            {"site_name": "The Verge", "url": "https://theverge.com/sony", "snippet": "Excellent comfort"},
        ],
    },
    "Bose QuietComfort 45": {
        "avg_rating": 4.5,
        "total_reviews": 8400,
        "quality_score": 0.88,
        "sources": [
            {"site_name": "RTINGS", "url": "https://rtings.com/bose", "snippet": "Great sound quality"},
        ],
    },
}


def _fake_service():
    fake = MagicMock()
    fake.generate_compose = AsyncMock(return_value="mock response text")
    return fake


# ---------------------------------------------------------------------------
# review_consensus block emission
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_review_consensus_block_emitted_when_review_data_present():
    """With review_data, product_compose must emit a review_consensus block
    (and NOT the comparison_html fallback)."""
    fake_service = _fake_service()
    state = _base_state(
        review_data=_REVIEW_DATA,
        comparison_html="<table><tr><td>legacy</td></tr></table>",
        comparison_data={"products": ["Sony WH-1000XM5", "Bose QuietComfort 45"]},
    )

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    blocks = result.get("ui_blocks", [])
    consensus_blocks = [b for b in blocks if b.get("type") == "review_consensus"]
    html_blocks = [b for b in blocks if b.get("type") == "comparison_html"]

    assert consensus_blocks, f"expected review_consensus block, got types: {[b.get('type') for b in blocks]}"
    assert not html_blocks, "comparison_html must not be emitted when review_consensus is"

    block = consensus_blocks[0]
    products = block["data"]["products"]
    assert len(products) == 2

    # Ranked by quality_score: Sony (0.95) first, Bose (0.88) second
    assert products[0]["name"] == "Sony WH-1000XM5"
    assert products[0]["rank"] == 1
    assert products[1]["name"] == "Bose QuietComfort 45"
    assert products[1]["rank"] == 2

    # Each entry carries the display fields the frontend needs
    for p in products:
        assert isinstance(p["avg_rating"], float)
        assert isinstance(p["total_reviews"], int)
        assert p["consensus"]  # non-empty synthesized text


@pytest.mark.asyncio
async def test_comparison_html_fallback_when_no_review_data():
    """Without review_data, the legacy comparison_html block must still be emitted."""
    fake_service = _fake_service()
    state = _base_state(
        review_data={},
        comparison_html="<table><tr><td>legacy</td></tr></table>",
        comparison_data={"products": ["Sony WH-1000XM5"]},
    )

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    blocks = result.get("ui_blocks", [])
    consensus_blocks = [b for b in blocks if b.get("type") == "review_consensus"]
    html_blocks = [b for b in blocks if b.get("type") == "comparison_html"]

    assert not consensus_blocks, "review_consensus must not be emitted without review_data"
    assert html_blocks, "comparison_html fallback missing"
    assert html_blocks[0]["data"]["html"].startswith("<table>")


@pytest.mark.asyncio
async def test_template_consensus_never_names_sources():
    """Products beyond the top-3 LLM cap get deterministic template consensus.
    That template must not name review sites (tone.md: no source citations)."""
    fake_service = _fake_service()

    # 5 reviewed products → top 3 get (mocked) LLM consensus, last 2 get templates.
    # Each product also needs a purchasable offer: QA5 bug 6 made the consensus
    # block only show products that appear in the cards (offer required).
    review_data = {}
    shopping_offers = []
    site_names = ["Wirecutter", "RTINGS", "TechRadar", "SoundGuys", "PCMag"]
    for i in range(5):
        name = f"Headphone Model {i + 1}"
        review_data[name] = {
            "avg_rating": 4.0 + i * 0.1,
            "total_reviews": 1000 + i,
            "quality_score": 0.9 - i * 0.1,  # descending: Model 1 best
            "sources": [
                {"site_name": site_names[i], "url": f"https://example.com/{i}", "snippet": f"Snippet {i}"},
            ],
        }
        shopping_offers.append({
            "product_name": name,
            "offers": [{
                "title": name, "price": 199.0 + i, "currency": "USD",
                "url": f"https://www.google.com/shopping/product/{i}", "merchant": "BestBuy",
                "image_url": f"https://img.example.com/{i}.jpg",
                "source": "serper_shopping",
            }],
        })

    state = _base_state(
        review_data=review_data,
        # The 5 reviewed products must also exist in the search results + have offers:
        # QA5 bug 6 made the consensus block only show products that get cards.
        normalized_products=[
            {"name": f"Headphone Model {i + 1}", "price": 199.0 + i, "url": f"https://example.com/{i}"}
            for i in range(5)
        ],
        affiliate_products={"serper_shopping": shopping_offers},
    )

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    blocks = result.get("ui_blocks", [])
    consensus_blocks = [b for b in blocks if b.get("type") == "review_consensus"]
    assert consensus_blocks

    products = consensus_blocks[0]["data"]["products"]
    # The two template-consensus products (ranks 4 and 5) must not cite their source
    template_entries = [p for p in products if p["rank"] > 3]
    assert template_entries, "expected template-consensus entries beyond the LLM cap"
    for entry in template_entries:
        for site in site_names:
            assert site not in entry["consensus"], (
                f"template consensus cites source '{site}': {entry['consensus']}"
            )


# ---------------------------------------------------------------------------
# Rating-scale normalization (client)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mixed_scale_ratings_normalize_to_five_scale():
    """Editorial /10 ratings (e.g. RTINGS 8.5) must be normalized to /5 before
    averaging — bundle.avg_rating must never exceed 5 or star displays break."""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.SERPAPI_API_KEY = "test-key"
        mock_settings.SERPAPI_MAX_SOURCES = 8
        mock_settings.SERPAPI_CACHE_TTL = 86400
        mock_settings.SERPAPI_TIMEOUT = 15.0
        mock_settings.SERPAPI_FALLBACK_ENABLED = False
        mock_settings.SERPAPI_COM_API_KEY = ""
        mock_settings.SERPAPI_COM_API_KEY_2 = ""
        mock_settings.REDIS_RETRY_MAX_ATTEMPTS = 1
        mock_settings.REDIS_RETRY_BACKOFF_BASE = 0.01

        from app.services.serpapi.client import SerpAPIClient, ReviewSource

        client = SerpAPIClient()

        # RTINGS-style /10 rating in an editorial source + /5 shopping rating
        editorial_sources = [
            ReviewSource(
                site_name="RTINGS", url="https://rtings.com/x", title="Review",
                snippet="Great headphones", rating=8.5, authority_score=0.93,
            ),
        ]
        shopping_data = {"rating": 4.5, "review_count": 100}

        with patch.object(client, "_search_editorial", new_callable=AsyncMock, return_value=editorial_sources), \
             patch.object(client, "_search_reddit", new_callable=AsyncMock, return_value=[]), \
             patch.object(client, "_search_shopping", new_callable=AsyncMock, return_value=shopping_data), \
             patch("app.core.redis_client.redis_get_with_retry", new_callable=AsyncMock, return_value=None), \
             patch("app.core.redis_client.redis_set_with_retry", new_callable=AsyncMock, return_value=True):

            bundle = await client.search_reviews("Test Headphones", "headphones")

    assert bundle.avg_rating <= 5.0, f"avg_rating {bundle.avg_rating} exceeds the 5-star scale"
    # 8.5/10 → 4.25; shopping 4.5 stays → avg = round((4.25 + 4.5) / 2, 1) = 4.4
    assert bundle.avg_rating == 4.4


# ---------------------------------------------------------------------------
# QA Round 5 (external bug 6) — consensus block matches the cards
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_offerless_reviewed_product_excluded_from_consensus():
    """A product with review data but NO purchasable offer must not appear in the
    consensus block (it has no card — ranking it #1 contradicts the page)."""
    fake_service = _fake_service()

    review_data = dict(_REVIEW_DATA)
    # Reviewed heavily, ranked first by quality score — but nobody sells it here
    review_data["Sennheiser Momentum 4"] = {
        "avg_rating": 4.8,
        "total_reviews": 9000,
        "quality_score": 0.99,  # would rank #1 without the filter
        "sources": [
            {"site_name": "RTINGS", "url": "https://rtings.com/senn", "snippet": "Class-leading battery"},
        ],
    }

    state = _base_state(review_data=review_data)

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    blocks = result.get("ui_blocks", [])
    consensus_blocks = [b for b in blocks if b.get("type") == "review_consensus"]
    assert consensus_blocks

    products = consensus_blocks[0]["data"]["products"]
    names = [p["name"] for p in products]
    assert "Sennheiser Momentum 4" not in names, (
        "offerless product must be suppressed from the consensus block"
    )
    # The remaining products keep a gap-free 1..N rank sequence
    assert [p["rank"] for p in products] == list(range(1, len(products) + 1))
    # And the products that DO have offers still appear
    assert "Sony WH-1000XM5" in names


@pytest.mark.asyncio
async def test_consensus_rank_renumbered_after_filtering():
    """When the would-be #1 product is filtered out, the survivors are ranked 1..N
    (no gaps, no rank-2-first lists)."""
    fake_service = _fake_service()

    review_data = dict(_REVIEW_DATA)
    review_data["Phantom Product X"] = {
        "avg_rating": 5.0,
        "total_reviews": 50000,
        "quality_score": 1.0,  # top quality score, but no offer anywhere
        "sources": [
            {"site_name": "PCMag", "url": "https://pcmag.com/x", "snippet": "Incredible"},
        ],
    }

    state = _base_state(review_data=review_data)

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    consensus_blocks = [
        b for b in result.get("ui_blocks", []) if b.get("type") == "review_consensus"
    ]
    assert consensus_blocks
    products = consensus_blocks[0]["data"]["products"]
    assert products[0]["rank"] == 1, "first listed product must be rank 1 after filtering"
    assert all(p["name"] != "Phantom Product X" for p in products)


@pytest.mark.asyncio
async def test_consensus_collapses_trim_variants_to_one_per_family():
    """A head-to-head ask must not fill the comparison block with trim variants of
    one side. iPhone 15 / 15 Pro / 15 Pro Max (more reviews → higher quality_score)
    collapse to ONE iPhone representative; the Pixel still appears — one per model
    family. This is the QA finding fix: the block showed 3 iPhone variants and no
    Pixel, plus duplicate consensus text across near-identical variants."""
    fake_service = _fake_service()
    names = ["iPhone 15", "iPhone 15 Pro", "iPhone 15 Pro Max", "Google Pixel 8"]
    qscores = [0.95, 0.93, 0.90, 0.70]  # iPhones outrank the Pixel by review quality
    review_data = {}
    shopping_offers = []
    for i, name in enumerate(names):
        review_data[name] = {
            "avg_rating": 4.6,
            "total_reviews": 5000 - i,
            "quality_score": qscores[i],
            "sources": [{"site_name": "", "url": f"https://x/{i}", "snippet": f"Great phone {i}"}],
        }
        shopping_offers.append({
            "product_name": name,
            "offers": [{
                "title": name, "price": 699.0 + i, "currency": "USD",
                "url": f"https://www.google.com/shopping/product/{i}", "merchant": "BestBuy",
                "image_url": f"https://img.example.com/{i}.jpg", "source": "serper_shopping",
            }],
        })

    state = _base_state(
        user_message="iPhone 15 vs Pixel 8",
        review_data=review_data,
        normalized_products=[
            {"name": n, "price": 699.0 + i, "url": f"https://example.com/{i}"} for i, n in enumerate(names)
        ],
        affiliate_products={"serper_shopping": shopping_offers},
    )

    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    consensus_blocks = [b for b in result.get("ui_blocks", []) if b.get("type") == "review_consensus"]
    assert consensus_blocks
    block_names = [p["name"] for p in consensus_blocks[0]["data"]["products"]]

    iphone_count = sum(1 for n in block_names if n.lower().startswith("iphone"))
    assert iphone_count == 1, f"expected ONE iPhone representative (trims collapsed), got {block_names}"
    assert any("pixel" in n.lower() for n in block_names), f"Pixel must appear (not crowded out): {block_names}"
    # Ranks stay contiguous after the collapse.
    assert [p["rank"] for p in consensus_blocks[0]["data"]["products"]] == list(
        range(1, len(block_names) + 1)
    )


@pytest.mark.asyncio
async def test_consensus_keeps_distinct_models_and_falls_back_below_two():
    """Distinct models (different last token) are NOT collapsed; and if collapsing
    would drop the block below two entries, the full list is kept rather than
    showing a lone card."""
    fake_service = _fake_service()
    # Two genuinely distinct models — must both survive (no false collapse).
    distinct = ["Sony WH-1000XM5", "Bose QuietComfort 45"]
    review_data = {}
    shopping_offers = []
    for i, name in enumerate(distinct):
        review_data[name] = {
            "avg_rating": 4.6, "total_reviews": 5000 - i, "quality_score": 0.9 - i * 0.1,
            "sources": [{"site_name": "", "url": f"https://x/{i}", "snippet": f"Snippet {i}"}],
        }
        shopping_offers.append({
            "product_name": name,
            "offers": [{
                "title": name, "price": 299.0 + i, "currency": "USD",
                "url": f"https://www.google.com/shopping/product/{i}", "merchant": "BestBuy",
                "image_url": f"https://img.example.com/{i}.jpg", "source": "serper_shopping",
            }],
        })

    state = _base_state(
        review_data=review_data,
        normalized_products=[{"name": n, "price": 299.0 + i, "url": f"https://e/{i}"} for i, n in enumerate(distinct)],
        affiliate_products={"serper_shopping": shopping_offers},
    )
    with patch("app.services.model_service.model_service", fake_service):
        result = await product_compose(state)

    consensus_blocks = [b for b in result.get("ui_blocks", []) if b.get("type") == "review_consensus"]
    assert consensus_blocks
    block_names = [p["name"] for p in consensus_blocks[0]["data"]["products"]]
    assert "Sony WH-1000XM5" in block_names and "Bose QuietComfort 45" in block_names
