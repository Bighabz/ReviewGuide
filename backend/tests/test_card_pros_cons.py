"""Fix 2 (Defect C, 2026-07-05) × PLAN-3 merge (2026-08-18): card pros/cons.

The product_review card loop prefers the classified pros/cons from
product_evidence's `review_aspects` (word-boundary truncated). When a product
has no aspects it falls back to PLAN-3's grounded synthesis from the blog
payload's `pros_cons` (honesty-gated via _card_pros_cons). Raw review snippets
are model INPUT only and never render on cards — Fix 2's sentiment-routed
snippet fallback was retired by PLAN-3.
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
async def test_no_aspects_falls_back_to_grounded_synthesis():
    # No review_aspects -> PLAN-3 fallback: pros/cons come from the blog
    # payload's pros_cons (grounded), never from raw snippets.
    blog = {"body": "Shortlist.", "follow_up_question": "Indoor or outdoor?",
            "transitional_reasoning": "",
            "pros_cons": {PROD: {"pros": ["Built-in burr grinder"],
                                 "cons": ["Struggles at fine grind"]}}}
    _, state = _state(review_aspects=[], sources=[
        {"snippet": "However, this raw snippet must never render on a card.",
         "site_name": "S1", "url": "https://x/1"},
    ])
    data = _card(await _run(json.dumps(blog), state))
    pros = [p["description"] for p in data["pros"]]
    cons = [c["description"] for c in data["cons"]]
    assert pros == ["Built-in burr grinder"]
    assert cons == ["Struggles at fine grind"]
    assert not any("raw snippet" in t for t in pros + cons)


@pytest.mark.asyncio
async def test_long_aspect_item_truncated_on_word_boundary():
    long = "The battery life is outstanding and easily lasts a full working day of continuous listening " \
           "without any noticeable drop in the noise cancellation performance whatsoever here"
    aspects = [{"product": PROD, "pros": [long], "cons": [], "rating": 4.2}]
    blog_json, state = _state(review_aspects=aspects)
    data = _card(await _run(blog_json, state))
    desc = data["pros"][0]["description"]
    assert desc.endswith("…")
    assert len(desc) <= 151
    assert not desc[:-1].endswith(" ")


@pytest.mark.asyncio
async def test_no_aspects_no_grounding_yields_empty_never_snippets():
    # No aspects AND no grounded pros_cons in the payload -> honest empties;
    # the snippets in review sources must not leak onto the card.
    sources = [
        {"snippet": "Disappointing bass and a poor, uncomfortable fit.", "site_name": "S1", "url": "https://x/1"},
        {"snippet": "The mic is bad and the app keeps missing devices.", "site_name": "S2", "url": "https://x/2"},
    ]
    blog_json, state = _state(review_aspects=[], sources=sources)
    data = _card(await _run(blog_json, state))
    assert data["pros"] == []
    assert data["cons"] == []
