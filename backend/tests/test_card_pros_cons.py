"""Fix 2 (Defect C, 2026-07-05): classified pros/cons + word-boundary truncation.

The product_review card loop used to push EVERY review snippet into `pros`, leave
`cons` empty, and hard-slice at [:150] mid-word. Now it prefers the classified
pros/cons from product_evidence's `review_aspects`; falls back to sentiment-routed
snippets; and truncates on a word boundary.
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

from mcp_server.tools.product_compose import (  # noqa: E402
    product_compose,
    _truncate_at_word,
    _reads_negative,
)

PROD = "Anker Soundcore Liberty 4"


# ── unit: helpers ───────────────────────────────────────────────────────────

def test_truncate_at_word_short_text_untouched():
    assert _truncate_at_word("all good", 150) == "all good"


def test_truncate_at_word_breaks_on_word_boundary():
    text = "the noise cancellation is genuinely excellent " * 6  # >150 chars
    out = _truncate_at_word(text, 150)
    assert len(out) <= 151            # <=150 body + ellipsis
    assert out.endswith("…")
    # last real char before ellipsis is not mid-word (no dangling partial token)
    body = out[:-1]
    assert not body.endswith(" ")
    assert " " in body and text.startswith(body.split("…")[0].rstrip())


def test_reads_negative():
    assert _reads_negative("However, the battery is disappointing")
    assert _reads_negative("uncomfortable after an hour")
    assert not _reads_negative("crisp sound and great battery life")


# ── integration: card pros/cons ─────────────────────────────────────────────

def _state(review_aspects=None, sources=None):
    blog = {"body": "Shortlist.", "follow_up_question": "Indoor or outdoor?",
            "transitional_reasoning": ""}

    def _offer():
        return {
            "product_name": PROD,
            "offers": [{
                "title": PROD, "price": 99.0, "currency": "USD",
                "url": "https://www.amazon.com/dp/x?tag=revguide-20",
                "merchant": "Amazon",
                "image_url": "https://img.example.com/anker.jpg",
                "source": "amazon",
            }],
        }

    state = {
        "user_message": "best budget earbuds",
        "intent": "product",
        "slots": {"category": "earbuds"},
        "normalized_products": [{"name": PROD}],
        "affiliate_products": {"amazon": [_offer()]},
        "review_data": {
            PROD: {
                "avg_rating": 4.4, "total_reviews": 1800,
                "quality_score": 85,
                "sources": sources if sources is not None else [
                    {"snippet": "Fantastic sound for the money.", "site_name": "TechSite",
                     "url": "https://tech.example.com/a"},
                ],
            },
        },
        "comparison_html": None,
        "comparison_data": None,
        "general_product_info": "",
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }
    if review_aspects is not None:
        state["review_aspects"] = review_aspects
    return json.dumps(blog), state


def _card(result):
    cards = [b for b in result.get("ui_blocks", []) if b.get("type") == "product_review"]
    assert cards, "expected a product_review card"
    return cards[0]["data"]


async def _run(blog_json, state):
    fake = MagicMock()
    fake.generate_compose = AsyncMock(return_value=blog_json)
    with patch("app.services.model_service.model_service", fake):
        return await product_compose(state)


@pytest.mark.asyncio
async def test_aspects_populate_pros_and_cons():
    aspects = [{
        "product": PROD,
        "pros": ["Excellent sound quality", "Great battery life", "Comfortable fit", "Cheap"],
        "cons": ["App is clunky", "No wireless charging", "Mediocre mic"],
        "rating": 4.4,
    }]
    blog_json, state = _state(review_aspects=aspects)
    data = _card(await _run(blog_json, state))
    pros = [p["description"] for p in data["pros"]]
    cons = [c["description"] for c in data["cons"]]
    assert pros == ["Excellent sound quality", "Great battery life", "Comfortable fit"]  # capped 3
    assert cons == ["App is clunky", "No wireless charging"]                              # capped 2
    # a con text must never appear in pros
    assert not (set(pros) & set(cons))


@pytest.mark.asyncio
async def test_fallback_routes_negative_snippet_to_cons():
    sources = [
        {"snippet": "Crisp, punchy sound that beats the price.", "site_name": "S1", "url": "https://x/1"},
        {"snippet": "However, the touch controls are unreliable and frustrating.", "site_name": "S2", "url": "https://x/2"},
    ]
    blog_json, state = _state(review_aspects=[], sources=sources)
    data = _card(await _run(blog_json, state))
    pros = [p["description"] for p in data["pros"]]
    cons = [c["description"] for c in data["cons"]]
    assert any("Crisp" in p for p in pros)
    assert any("touch controls" in c for c in cons), f"negative snippet should be a con: {cons}"


@pytest.mark.asyncio
async def test_fallback_long_snippet_truncated_on_word_boundary():
    long = "The battery life is outstanding and easily lasts a full working day of continuous listening " \
           "without any noticeable drop in the noise cancellation performance whatsoever here"
    blog_json, state = _state(review_aspects=[], sources=[
        {"snippet": long, "site_name": "S", "url": "https://x/1"},
    ])
    data = _card(await _run(blog_json, state))
    desc = data["pros"][0]["description"]
    assert desc.endswith("…")
    assert len(desc) <= 151
    assert not desc[:-1].endswith(" ")


@pytest.mark.asyncio
async def test_all_negative_no_aspects_yields_valid_card():
    sources = [
        {"snippet": "Disappointing bass and a poor, uncomfortable fit.", "site_name": "S1", "url": "https://x/1"},
        {"snippet": "The mic is bad and the app keeps missing devices.", "site_name": "S2", "url": "https://x/2"},
    ]
    blog_json, state = _state(review_aspects=[], sources=sources)
    data = _card(await _run(blog_json, state))
    # honest: pros may be empty, but the card is still valid and cons carry the criticism
    assert isinstance(data["pros"], list)
    assert len(data["cons"]) >= 1
