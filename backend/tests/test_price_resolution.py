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


# ---------------------------------------------------------------------------
# Task 5 — budget parses from the message fallback; fails loud, never silent.
# ---------------------------------------------------------------------------

from mcp_server.tools.product_compose import _resolve_budget


def test_budget_falls_back_to_the_user_message():
    assert _resolve_budget({}, "cordless vacuum under $400")[1] == 400.0


def test_slot_budget_wins_over_message():
    assert _resolve_budget({"budget": "under $500"}, "something about $99")[1] == 500.0


def test_no_budget_anywhere_is_none():
    assert _resolve_budget({}, "best espresso machine") == (None, None)


# ---------------------------------------------------------------------------
# Task 6 — integration with the REAL state shape, end to end through
# product_compose (mocked model service), asserting on ui_blocks.
# ---------------------------------------------------------------------------

import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import settings
from mcp_server.tools.product_compose import product_compose


def _pin_simple_path(monkeypatch):
    monkeypatch.setattr(settings, "USE_CONSOLIDATED_COMPOSE", False)
    monkeypatch.setattr(settings, "USE_DECOUPLED_COMPOSE", False, raising=False)
    monkeypatch.setattr(settings, "USE_COMPOSE_STREAMING", False, raising=False)
    monkeypatch.setattr(settings, "USE_GROUNDED_COMPOSE", False, raising=False)
    monkeypatch.setattr(settings, "USE_VOICE_PASS", False, raising=False)


def _fake_service(top_pick, body):
    blog = json.dumps({
        "body": body,
        "follow_up_question": "Anything else that matters?",
        "transitional_reasoning": "",
        "top_pick": top_pick,
    })
    fake = MagicMock()

    async def _generate_compose(*args, **kwargs):
        if kwargs.get("agent_name") == "blog_article_composer":
            return blog
        return "x"

    fake.generate_compose = AsyncMock(side_effect=_generate_compose)
    return fake


def _real_offer(title, price, merchant="Amazon", condition="", source="amazon"):
    o = make_offer(title, price, merchant=merchant, condition=condition, source=source)
    o["url"] = f"https://www.amazon.com/dp/{abs(hash(title)) % 99999}?tag=revguide-20"
    return o


@pytest.mark.asyncio
async def test_cordless_query_end_to_end_keeps_vacuum_drops_filter(monkeypatch):
    _pin_simple_path(monkeypatch)
    fake = _fake_service("Shark ION Robot Vacuum RV750",
                         "The Shark ION Robot Vacuum RV750 is the cordless pick.")
    state = {
        "user_message": "cordless vacuum for pet hair",
        "intent": "product",
        "slots": {"category": "vacuums"},
        "normalized_products": [
            {"name": "Shark ION Robot Vacuum RV750", "price": 249, "url": "https://e.com/rv750"},
        ],
        "affiliate_products": {
            "amazon": [{
                "product_name": "Shark ION Robot Vacuum RV750",
                "offers": [
                    _real_offer("Shark ION Robot Vacuum RV750, Cordless", 249.00),
                    _real_offer("Shark RV750 Replacement Filter 2-Pack", 15.98),
                ],
            }],
        },
        "review_data": {},
        "comparison_html": None, "comparison_data": None,
        "general_product_info": "", "conversation_history": [],
        "last_search_context": {}, "search_history": [],
    }
    with patch("app.services.model_service.model_service", fake):
        result = await product_compose(state)

    blocks_json = json.dumps(result["ui_blocks"])
    assert "Replacement Filter" not in blocks_json
    assert "RV750" in blocks_json


@pytest.mark.asyncio
async def test_all_over_budget_fails_loud_end_to_end(monkeypatch):
    _pin_simple_path(monkeypatch)
    fake = _fake_service("Breville Barista Express",
                         "The Breville Barista Express is the pick.")
    state = {
        "user_message": "best espresso machine under $500",
        "intent": "product",
        "slots": {"category": "espresso machines", "budget": "under $500"},
        "normalized_products": [
            {"name": "Breville Barista Express", "price": 668, "url": "https://e.com/bbe"},
        ],
        "affiliate_products": {
            "amazon": [{
                "product_name": "Breville Barista Express",
                "offers": [_real_offer("Breville Barista Express BES870XL", 668.00)],
            }],
        },
        "review_data": {},
        "comparison_html": None, "comparison_data": None,
        "general_product_info": "", "conversation_history": [],
        "last_search_context": {}, "search_history": [],
    }
    with patch("app.services.model_service.model_service", fake):
        result = await product_compose(state)

    # The over-budget offer is retained (degraded beats empty)…
    blocks_json = json.dumps(result["ui_blocks"])
    assert "668" in blocks_json
    # …but tagged in the projected card links…
    links = [
        link
        for b in result["ui_blocks"] if b.get("type") == "product_review"
        for link in b["data"]["affiliate_links"]
    ]
    assert any(link.get("over_budget") for link in links)
    # …and the prose says so, loudly and deterministically.
    assert "Nothing I found fits under $500" in (result.get("transitional_reasoning") or "")


# ---------------------------------------------------------------------------
# PLAN-7 T4 — the comparison follow-up renders rows from the elected offers
# saved in last_search_context (merchant/image/price match the cards), not
# empty fields that display "No Image" / "N/A".
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_comparison_followup_rows_carry_offer_data():
    context = {
        "category": "espresso machines",
        "product_names": ["Breville Barista Express", "De'Longhi Dedica"],
        "top_prices": {"Breville Barista Express": 699.95, "De'Longhi Dedica": 249.0},
        "avg_rating": {"Breville Barista Express": 4.6},
        "top_offers": {
            "Breville Barista Express": {
                "merchant": "Best Buy", "url": "https://bestbuy.example/bbe",
                "image_url": "https://img.example/bbe.jpg", "currency": "USD",
            },
            "De'Longhi Dedica": {
                "merchant": "Amazon", "url": "https://amazon.example/dedica",
                "image_url": "https://img.example/dedica.jpg", "currency": "USD",
            },
        },
    }
    result = await product_compose({
        "user_message": "compare them",
        "intent": "product",
        "slots": {},
        "normalized_products": [], "affiliate_products": {}, "review_data": {},
        "comparison_html": None, "comparison_data": None,
        "general_product_info": "", "conversation_history": [],
        "last_search_context": context, "search_history": [],
    })
    blocks = [b for b in result["ui_blocks"] if b.get("type") == "product_comparison"]
    assert blocks, "comparison block missing"
    rows = blocks[0]["data"]["products"]
    by_title = {r["title"]: r for r in rows}
    assert by_title["Breville Barista Express"]["merchant"] == "Best Buy"
    assert by_title["Breville Barista Express"]["image_url"] == "https://img.example/bbe.jpg"
    assert by_title["De'Longhi Dedica"]["price"] == 249.0
