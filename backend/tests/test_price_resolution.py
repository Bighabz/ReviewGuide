"""Characterization + regression tests for offer price resolution (PLAN-1 v2).

Tests marked `# BUG:` assert today's broken behaviour so later tasks can invert
them deliberately."""
import os

import pytest

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from mcp_server.tools.product_compose import (
    ACCESSORY_KEYWORDS,
    _drop_price_outliers,
    _looks_like_accessory,
    _extract_price,
    _offer_condition_label,
)


def make_offer(title, price, merchant="Amazon", condition="", source="serper_shopping",
               image_url="https://img.example/p.jpg"):
    """Offer dict shaped like assembly output in product_compose."""
    return {
        "merchant": merchant, "price": price, "currency": "USD",
        "url": "https://example.com/p", "image_url": image_url,
        "rating": 4.4, "review_count": 1200,
        "condition": condition, "title": title, "source": source,
    }


def test_cord_is_an_accessory_keyword():
    # The root of the query-bypass bug: "cordless" contains this as a substring.
    assert "cord" in ACCESSORY_KEYWORDS


def test_cordless_query_no_longer_disables_the_filter():
    # Inverted by Task 2: boundary matching. (The raw substring overlap that
    # caused the bypass — "cordless" ⊃ "cord" — still exists in the keyword
    # set; the matcher's word boundaries are what neutralize it.)
    from mcp_server.tools.product_compose import _matches_accessory_keyword
    assert _matches_accessory_keyword("cordless vacuum for pet hair") is False


def test_single_priced_offer_gets_no_hygiene():
    # BUG (documented): _drop_price_outliers early-returns with <2 priced
    # offers — a lone junk listing is never challenged. Task 2's boundary
    # matcher + Task 4's election reduce the blast radius; the early return
    # itself stays (median of one is meaningless).
    junk = make_offer("Shark RV750 Replacement Filter 2-Pack", 15.98)
    kept, dropped = _drop_price_outliers([junk])
    assert kept == [junk] and dropped == []


def test_renewed_offer_is_labelled():
    assert _offer_condition_label(make_offer("Sony WH-1000XM5", 147.26,
                                             condition="Renewed")) is not None


def test_backfill_price_laundering():
    # BUG: the backfill stamps real_src's price onto unpriced offers WITHOUT
    # copying condition — a renewed source price lands on a "new" offer and
    # passes the condition election. Behavioural pin only (the backfill is
    # inline); inverted by Task 3's assembly-level tests.
    unpriced_new = make_offer("Sony WH-1000XM5", 0, merchant="Amazon", condition="")
    assert _offer_condition_label(unpriced_new) is None  # looks new pre-backfill


# ---------------------------------------------------------------------------
# Task 2 — boundary-aware accessory matching at every consumer site.
# ---------------------------------------------------------------------------

from mcp_server.tools.product_compose import (
    _matches_accessory_keyword,
    _filter_relevant_products,
)


@pytest.mark.parametrize("text,expected", [
    # Boundary correctness — the bug class:
    ("cordless vacuum for pet hair", False),      # "cord" must NOT match inside "cordless"
    ("best suitcase for travel", False),          # "case" must NOT match inside "suitcase"
    ("standing desk with hutch", False),          # "stand" must NOT match inside "standing"
    # Legitimate accessory intent — must still match:
    ("replacement filter for my Shark ION", True),
    ("power cord for LG monitor", True),
    ("laptop case 15 inch", True),
    ("hepa filter cartridge 2-pack", True),
])
def test_boundary_aware_keyword_matching(text, expected):
    assert _matches_accessory_keyword(text) is expected


def test_cordless_vacuum_offers_survive_the_title_filter():
    """End goal: a cordless-vacuum query keeps the vacuum and drops the filter."""
    affiliate = {"amazon": [{
        "product_name": "Shark ION Robot Vacuum RV750",
        "offers": [
            make_offer("Shark ION Robot Vacuum RV750, Cordless", 249.00),
            make_offer("Shark RV750 Replacement Filter 2-Pack", 15.98),
        ],
    }]}
    out = _filter_relevant_products(affiliate, "cordless vacuum for pet hair")
    titles = [o["title"] for g in out["amazon"] for o in g["offers"]]
    assert any("Robot Vacuum RV750, Cordless" in t for t in titles)
    assert not any("Replacement Filter" in t for t in titles)


def test_accessory_intent_query_still_gets_accessories():
    """Collateral guard: someone shopping FOR a filter must not lose it."""
    affiliate = {"amazon": [{
        "product_name": "Shark RV750 Replacement Filter",
        "offers": [make_offer("Shark RV750 Replacement Filter 2-Pack", 15.98)],
    }]}
    out = _filter_relevant_products(affiliate, "replacement filter for my Shark ION")
    assert out == affiliate  # accessory intent → filter stays disabled
