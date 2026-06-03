"""Tests for product_ranking — Outcome 9 (budget-aware value ranking).

Within a stated budget, ranking favors rating-per-dollar value: a $550/4.5★
pick must outrank a $999/4.6★ pick on a "$500–$1,000" ask. Without a budget,
the legacy quality scoring is unchanged. Budget semantics are shared with
product_compose (_parse_budget): ceiling always hard, floor hard only on
floor-only budgets.
"""
import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

import pytest  # noqa: E402

from mcp_server.tools.product_ranking import (  # noqa: E402
    _best_rating,
    _median_offer_price,
    product_ranking,
)


# ---------------------------------------------------------------------------
# Fixtures: a laptop shortlist with prices and ratings
# ---------------------------------------------------------------------------

def _affiliate(products_prices: dict) -> dict:
    """Build affiliate_products: {provider: [{product_name, offers:[{price,...}]}]}."""
    return {
        "serper_shopping": [
            {
                "product_name": name,
                "offers": [{"price": price, "merchant": "Best Buy", "url": f"https://x.com/{i}"}],
            }
            for i, (name, price) in enumerate(products_prices.items())
        ]
    }


def _reviews(products_ratings: dict) -> dict:
    """Build review_data: {product_name: {avg_rating, total_reviews, quality_score, sources}}."""
    return {
        name: {
            "avg_rating": rating,
            "total_reviews": 1200,
            "quality_score": 4.0,
            "sources": [{"snippet": "solid"}],
        }
        for name, rating in products_ratings.items()
    }


VALUE_PICK = "Acer Aspire Value 15"       # $550, 4.5★ → 0.00818 rating/dollar
PREMIUM_PICK = "Dell XPS Premium 15"      # $999, 4.6★ → 0.0046 rating/dollar
OVER_BUDGET = "Razer Blade Ultra"         # $1,899, 4.8★ → over ceiling
NO_PRICE = "Mystery Laptop X"             # rated but unpriced


def _state(budget=None):
    state = {
        "normalized_products": [
            {"name": PREMIUM_PICK, "score": 0.9},
            {"name": OVER_BUDGET, "score": 0.8},
            {"name": VALUE_PICK, "score": 0.5},
            {"name": NO_PRICE, "score": 0.4},
        ],
        "affiliate_products": _affiliate({
            PREMIUM_PICK: 999.0,
            OVER_BUDGET: 1899.0,
            VALUE_PICK: 550.0,
        }),
        "review_data": _reviews({
            PREMIUM_PICK: 4.6,
            OVER_BUDGET: 4.8,
            VALUE_PICK: 4.5,
            NO_PRICE: 4.9,
        }),
    }
    if budget is not None:
        state["slots"] = {"budget": budget}
    return state


def _names_in_order(result):
    return [item["product_name"] for item in result["ranked_products"]]


# ---------------------------------------------------------------------------
# Outcome 9: the headline behavior
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_value_pick_beats_premium_pick_in_budget_range():
    """The handoff's canonical case: $550/4.5★ beats $999/4.6★ on '$500–$1,000'."""
    result = await product_ranking(_state(budget="$500–$1,000"))

    assert result["success"]
    order = _names_in_order(result)
    assert order.index(VALUE_PICK) < order.index(PREMIUM_PICK), (
        f"value pick must lead: {order}"
    )
    # Both carry value metadata
    by_name = {it["product_name"]: it for it in result["ranked_products"]}
    assert by_name[VALUE_PICK]["value_per_dollar"] > by_name[PREMIUM_PICK]["value_per_dollar"]
    assert by_name[VALUE_PICK]["in_budget"] is True
    assert by_name[PREMIUM_PICK]["in_budget"] is True
    # The top value pick says so in its reasons
    assert any("Best value" in r for r in by_name[VALUE_PICK]["reasons"])


@pytest.mark.asyncio
async def test_over_budget_product_sinks_below_in_budget_ones():
    """The $1,899 laptop is over the $1,000 ceiling — it must rank below every
    in-budget product, no matter how good its rating is."""
    result = await product_ranking(_state(budget="$500–$1,000"))

    order = _names_in_order(result)
    assert order.index(OVER_BUDGET) > order.index(VALUE_PICK)
    assert order.index(OVER_BUDGET) > order.index(PREMIUM_PICK)

    by_name = {it["product_name"]: it for it in result["ranked_products"]}
    assert by_name[OVER_BUDGET]["in_budget"] is False
    assert any("Outside stated budget" in r for r in by_name[OVER_BUDGET]["reasons"])


@pytest.mark.asyncio
async def test_legacy_numeric_budget_still_works():
    """The budget slot used to be a number (e.g. 1000) — _parse_budget treats it
    as a ceiling and value ranking must still kick in."""
    result = await product_ranking(_state(budget=1000))

    order = _names_in_order(result)
    assert order.index(VALUE_PICK) < order.index(PREMIUM_PICK)
    assert order.index(OVER_BUDGET) > order.index(PREMIUM_PICK)


@pytest.mark.asyncio
async def test_below_floor_on_range_budget_is_a_deal_not_a_violation():
    """F2 semantics: on a range budget, a product below the floor is a deal —
    it stays in_budget (and its great rating-per-dollar may rank it first)."""
    state = _state(budget="$500–$1,000")
    # Add a $399 laptop with a good rating (below the $500 floor)
    deal = "HP Pavilion Deal 14"
    state["normalized_products"].append({"name": deal, "score": 0.3})
    state["affiliate_products"]["serper_shopping"].append(
        {"product_name": deal, "offers": [{"price": 399.0, "merchant": "HP", "url": "https://x.com/hp"}]}
    )
    state["review_data"][deal] = {
        "avg_rating": 4.4, "total_reviews": 800, "quality_score": 3.5, "sources": [{"snippet": "ok"}],
    }

    result = await product_ranking(state)
    by_name = {it["product_name"]: it for it in result["ranked_products"]}
    assert by_name[deal]["in_budget"] is True, "below-floor on a RANGE budget is a deal, not a violation"
    # 4.4/399 = 0.011 — the best rating-per-dollar of the set → it leads
    assert _names_in_order(result)[0] == deal


@pytest.mark.asyncio
async def test_floor_only_budget_excludes_below_floor():
    """'$1,500+' is a quality intent — below-floor products are out of budget."""
    result = await product_ranking(_state(budget="$1,500+"))

    by_name = {it["product_name"]: it for it in result["ranked_products"]}
    # Only the $1,899 laptop satisfies the $1,500 floor
    assert by_name[OVER_BUDGET]["in_budget"] is True
    assert by_name[VALUE_PICK]["in_budget"] is False
    assert by_name[PREMIUM_PICK]["in_budget"] is False
    # And it leads the ranking
    assert _names_in_order(result)[0] == OVER_BUDGET


@pytest.mark.asyncio
async def test_no_budget_keeps_legacy_scoring():
    """Without a budget, scores stay in the legacy 0–1 band and no value
    metadata is attached — existing behavior is untouched."""
    result = await product_ranking(_state(budget=None))

    assert result["success"]
    for item in result["ranked_products"]:
        assert item["score"] <= 1.0
        assert "value_per_dollar" not in item
        assert "in_budget" not in item
        assert "price" not in item


@pytest.mark.asyncio
async def test_unpriced_product_keeps_legacy_score_under_budget():
    """A rated-but-unpriced product can't be value-scored — it keeps its legacy
    score (it neither leads nor gets the out-of-budget penalty)."""
    result = await product_ranking(_state(budget="$500–$1,000"))

    by_name = {it["product_name"]: it for it in result["ranked_products"]}
    assert by_name[NO_PRICE]["in_budget"] is None
    assert "value_per_dollar" not in by_name[NO_PRICE]
    assert by_name[NO_PRICE]["score"] <= 1.0
    # In-budget value picks (score 2.0+) outrank it
    order = _names_in_order(result)
    assert order.index(VALUE_PICK) < order.index(NO_PRICE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_median_offer_price_is_outlier_robust():
    """A $12 accessory listing must not drag the product's price signal down."""
    affiliate = {
        "ebay": [{
            "product_name": "Apple iPhone 15 Pro",
            "offers": [{"price": 999.0}, {"price": 949.0}, {"price": 12.0}],
        }],
        "serper_shopping": [{
            "product_name": "iPhone 15 Pro 128GB",
            "offers": [{"price": 989.0}],
        }],
    }
    price = _median_offer_price("iPhone 15 Pro", affiliate)
    # median of [999, 949, 12, 989] = (949+989)/2 = 969 — not 12
    assert price == pytest.approx(969.0)


def test_median_offer_price_none_when_no_match():
    assert _median_offer_price("Unknown Product", {"ebay": []}) is None
    assert _median_offer_price("Unknown Product", {}) is None


def test_best_rating_prefers_review_data():
    review_data = {"Sony WH-1000XM5": {"avg_rating": 4.7}}
    aspects = [{"product": "Sony WH-1000XM5", "rating": 4.0}]
    product = {"name": "Sony WH-1000XM5", "rating": 3.5}
    assert _best_rating("Sony WH-1000XM5", review_data, aspects, product) == 4.7
    # Falls back: aspects, then product's own rating
    assert _best_rating("Sony WH-1000XM5", {}, aspects, product) == 4.0
    assert _best_rating("Sony WH-1000XM5", {}, None, product) == 3.5
    assert _best_rating("Sony WH-1000XM5", {}, None, {}) is None


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_state_returns_empty_ranking():
    result = await product_ranking({})
    assert result["success"]
    assert result["ranked_products"] == []


@pytest.mark.asyncio
async def test_product_names_fallback_without_normalized():
    """Ranking still works from bare product_names when normalize didn't run."""
    result = await product_ranking({
        "product_names": ["Laptop A", "Laptop B"],
        "slots": {"budget": "under $800"},
    })
    assert result["success"]
    assert len(result["ranked_products"]) == 2


@pytest.mark.asyncio
async def test_garbage_budget_string_degrades_to_legacy():
    """An unparseable budget must not crash or distort scoring."""
    result = await product_ranking(_state(budget="whatever feels right"))
    assert result["success"]
    for item in result["ranked_products"]:
        assert item["score"] <= 1.0
