"""Fix A (2026-07-05): use-case relevance in product_ranking.

The use case ("running") never reached ranking, so a pure rating-per-dollar value
band promoted famous commuter buds over sport-fit picks. These tests prove the
bounded relevance term lifts a purpose-built pick over a higher-raw-value generic
one WHEN a use_case is set — and is inert (identical order) when it isn't.
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

from mcp_server.tools.product_ranking import product_ranking, _use_case_relevance  # noqa: E402

# Commuter has the BETTER raw rating-per-dollar; sport is purpose-built for running.
COMMUTER = "Sony WF Commuter Buds"   # $120, 4.6★ → 0.03833 raw
SPORT = "Jabra Sport Active Buds"    # $140, 4.4★ → 0.03143 raw


def _affiliate(prices: dict) -> dict:
    return {
        "serper_shopping": [
            {"product_name": n, "offers": [{"price": p, "merchant": "Best Buy", "url": f"https://x.com/{i}"}]}
            for i, (n, p) in enumerate(prices.items())
        ]
    }


def _earbud_state(use_case=None):
    state = {
        "normalized_products": [{"name": COMMUTER, "score": 0.6}, {"name": SPORT, "score": 0.5}],
        "affiliate_products": _affiliate({COMMUTER: 120.0, SPORT: 140.0}),
        "review_data": {
            COMMUTER: {"avg_rating": 4.6, "total_reviews": 1500, "quality_score": 4.0,
                       "sources": [{"title": "Sony WF review", "snippet": "great all-round commuter buds for the daily office trip"}]},
            SPORT: {"avg_rating": 4.4, "total_reviews": 900, "quality_score": 4.0,
                    "sources": [{"title": "Jabra Sport review", "snippet": "the best earbuds for running — secure ear-hooks stay put for runners"}]},
        },
        "slots": {"budget": "$100–$200"},
    }
    if use_case is not None:
        state["slots"]["use_case"] = use_case
    return state


def _order(result):
    return [it["product_name"] for it in result["ranked_products"]]


@pytest.mark.asyncio
async def test_without_use_case_higher_raw_value_leads():
    """Regression sentinel: no use_case → pure rating-per-dollar order (commuter wins)."""
    result = await product_ranking(_earbud_state())
    assert _order(result)[0] == COMMUTER


@pytest.mark.asyncio
async def test_use_case_lifts_purpose_built_pick_over_higher_raw_value():
    """With use_case='running', the sport bud whose reviews mention running outranks
    the commuter bud that has the better raw rating-per-dollar."""
    result = await product_ranking(_earbud_state(use_case="running"))
    order = _order(result)
    assert order[0] == SPORT, f"sport pick should lead with use_case=running: {order}"
    by_name = {it["product_name"]: it for it in result["ranked_products"]}
    # value_per_dollar stays the RAW figure (compose mirrors it) — commuter still higher there
    assert by_name[COMMUTER]["value_per_dollar"] > by_name[SPORT]["value_per_dollar"]
    assert by_name[SPORT].get("use_case_relevance", 0) >= 0.5
    assert any("Strong fit" in r for r in by_name[SPORT]["reasons"])


@pytest.mark.asyncio
async def test_use_case_never_lifts_out_of_budget_above_in_budget():
    """An out-of-budget product must stay below in-budget ones even if it matches the use case."""
    state = _earbud_state(use_case="running")
    pricey = "Bose Sport Ultra"
    state["normalized_products"].append({"name": pricey, "score": 0.9})
    state["affiliate_products"]["serper_shopping"].append(
        {"product_name": pricey, "offers": [{"price": 320.0, "merchant": "Bose", "url": "https://x.com/bose"}]}
    )
    state["review_data"][pricey] = {"avg_rating": 4.9, "total_reviews": 2000, "quality_score": 4.5,
                                    "sources": [{"title": "Bose Sport", "snippet": "excellent for running and gym runners"}]}
    result = await product_ranking(state)
    order = _order(result)
    assert order.index(pricey) > order.index(SPORT)
    assert order.index(pricey) > order.index(COMMUTER)


def test_use_case_relevance_unit():
    rd = {"Jabra Sport": {"sources": [{"title": "", "snippet": "great for runners on long runs"}]}}
    assert _use_case_relevance("Jabra Sport Active", "running", rd) == 1.0  # "runners"/"runs" prefix-hit
    rd2 = {"Sony WF": {"sources": [{"title": "", "snippet": "solid commuter buds for phone calls"}]}}
    assert _use_case_relevance("Sony WF Commuter", "running", rd2) == 0.0
    assert _use_case_relevance("Anything", "", rd) == 0.0  # no use_case → inert
