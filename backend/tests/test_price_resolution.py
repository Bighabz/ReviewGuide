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


# ---------------------------------------------------------------------------
# Task 3 — the headline honours condition: no laundered renewed prices.
# ---------------------------------------------------------------------------

from mcp_server.tools.product_compose import _select_backfill_source, _apply_backfill


def test_backfill_source_prefers_unlabelled_new():
    offers = [
        make_offer("Sony WH-1000XM5 Renewed", 147.26, condition="Renewed"),
        make_offer("Sony WH-1000XM5", 398.00, merchant="Best Buy"),
    ]
    src = _select_backfill_source(offers)
    assert _offer_condition_label(src) is None
    assert _extract_price(src) == 398.00


def test_renewed_source_backfills_with_its_condition_attached():
    """When ONLY a renewed source exists, its price may backfill — but the
    condition must travel with it so the card labels it (never launder)."""
    offers = [
        make_offer("Sony WH-1000XM5 Renewed", 147.26, condition="Renewed"),
        make_offer("Sony WH-1000XM5", 0, merchant="Amazon"),  # unpriced new
    ]
    _apply_backfill(offers)
    amazon = next(o for o in offers if o["merchant"] == "Amazon")
    assert amazon["price"] == 147.26
    assert _offer_condition_label(amazon) is not None  # condition travelled


def test_title_only_renewed_source_cannot_launder():
    """Final-validation blocker: the source's condition FIELD is empty but its
    TITLE says Renewed — _offer_condition_label derives from either. The
    backfilled target must still end up labelled."""
    offers = [
        make_offer("Sony WH-1000XM5 (Renewed)", 147.26, condition=""),  # title-only
        make_offer("Sony WH-1000XM5", 0, merchant="Amazon"),
    ]
    # Precondition: the source labels via title alone, or this test is vacuous.
    assert _offer_condition_label(offers[0]) is not None
    _apply_backfill(offers)
    amazon = next(o for o in offers if o["merchant"] == "Amazon")
    assert amazon["price"] == 147.26
    assert _offer_condition_label(amazon) is not None


# ---------------------------------------------------------------------------
# Task 4 — deterministic election across ALL offers (not offers[0] per group).
# Same query -> different provider ordering used to mean $668 vs $209.99.
# ---------------------------------------------------------------------------

import random

from mcp_server.tools.product_compose import _assemble_offers_for_product


def _groups():
    """Two provider groups, multiple offers each, deliberately shuffled."""
    return [
        {"provider": "ebay", "product_name": "Breville Barista Express", "offers": [
            make_offer("Breville Barista Express", 668.00, merchant="Marketplace", source="ebay"),
            make_offer("Breville Barista Express", 209.99, merchant="Unknown", source="ebay"),
        ]},
        {"provider": "serper_shopping", "product_name": "Breville Barista Express", "offers": [
            make_offer("Breville Barista Express", 699.95, merchant="Best Buy", source="serper_shopping"),
        ]},
    ]


def test_assembly_is_order_independent():
    baseline = _assemble_offers_for_product("Breville Barista Express", _groups())
    base_prices = sorted(_extract_price(o) for o in baseline)
    base_first = baseline[0]["merchant"]
    rng = random.Random(42)
    for _ in range(25):
        groups = _groups()
        rng.shuffle(groups)
        for g in groups:
            rng.shuffle(g["offers"])
        shuffled = _assemble_offers_for_product("Breville Barista Express", groups)
        assert sorted(_extract_price(o) for o in shuffled) == base_prices
        assert shuffled[0]["merchant"] == base_first  # first-element reads stay stable


def test_assembly_keeps_every_offer_not_just_first():
    out = _assemble_offers_for_product("Breville Barista Express", _groups())
    assert len(out) == 3  # not 2 (one-per-group)


def test_assembly_survives_unpriced_offers():
    groups = _groups()
    groups[0]["offers"].append(make_offer("Breville Barista Express", 0,
                                          merchant="MockAffiliate"))
    out = _assemble_offers_for_product("Breville Barista Express", groups)
    assert len(out) == 4  # no TypeError, unpriced offer retained (carries links)
