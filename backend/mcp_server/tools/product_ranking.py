"""
Product Ranking Tool

Ranks products by quality, relevance, and user preferences.

Outcome 9 (budget-aware value ranking): when the user stated a budget, ranking
favors value — rating per dollar — within that budget. A $550 / 4.5★ pick
outranks a $999 / 4.6★ pick on a "$500–$1,000" ask. Products outside the budget
sink below everything inside it. With no stated budget, the legacy quality
scoring is unchanged.
"""

from app.core.centralized_logger import get_logger
from app.core.error_manager import tool_error_handler
import re
import statistics
import sys
import os
from itertools import zip_longest
from typing import Dict, Any, List, Optional

# Add backend to path (portable path)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Budget/price parsing is shared with product_compose so ranking's notion of
# "in budget" can never drift from the offer filter's (F2 / PR #92 semantics:
# ceiling always hard; floor hard only on floor-only budgets).
from .product_compose import _extract_price, _parse_budget  # noqa: E402

logger = get_logger(__name__)


def _fuzzy_name_match(name_a: str, name_b: str, threshold: float = 0.35) -> bool:
    """Token-overlap Jaccard similarity for fuzzy product name matching."""
    a_tokens = set(name_a.lower().split())
    b_tokens = set(name_b.lower().split())
    if not a_tokens or not b_tokens:
        return False
    intersection = a_tokens & b_tokens
    union = a_tokens | b_tokens
    return len(intersection) / len(union) >= threshold


def _comparison_side_matcher(side: str):
    """Build a matcher for one side of an 'X vs Y' pair.

    The side's first token is the brand/product family ("iPhone 15" → iphone,
    "adidas sneakers" → adidas); a word-boundary match against the product
    name decides membership.
    """
    tokens = str(side).strip().lower().split()
    if not tokens:
        return lambda name: False
    pattern = re.compile(rf"\b{re.escape(tokens[0])}\b")
    return lambda name: bool(pattern.search(name.lower()))


def _interleave_comparison_sides(ranked_items: List[Dict[str, Any]], pair: List) -> List[Dict[str, Any]]:
    """Alternate the two compared sides through the shortlist.

    QA 2026-06-10: 'iPhone 15 vs Pixel 8' shortlists came back all-iPhone —
    pure score sorting packs the higher-authority brand into every visible
    slot. Within each side the score order is preserved; the side owning the
    global top item leads; items matching neither side trail in score order.
    No-op when either side is absent from the results (nothing to balance).
    """
    match_a = _comparison_side_matcher(pair[0])
    match_b = _comparison_side_matcher(pair[1])
    side_a: List[Dict[str, Any]] = []
    side_b: List[Dict[str, Any]] = []
    rest: List[Dict[str, Any]] = []
    for item in ranked_items:
        name = item.get("product_name", "")
        if match_a(name):
            side_a.append(item)
        elif match_b(name):
            side_b.append(item)
        else:
            rest.append(item)
    if not side_a or not side_b:
        return ranked_items
    first, second = (side_a, side_b) if ranked_items[0] in side_a else (side_b, side_a)
    interleaved: List[Dict[str, Any]] = []
    for x, y in zip_longest(first, second):
        if x is not None:
            interleaved.append(x)
        if y is not None:
            interleaved.append(y)
    return interleaved + rest


def _median_offer_price(product_name: str, affiliate_products: Dict[str, List]) -> Optional[float]:
    """Median positive offer price across all providers for a product (fuzzy match).

    Median is robust to scraped-noise outliers (the "$12 iPhone 15" case listing)
    without duplicating compose's full outlier-dropping pass.
    """
    prices: List[float] = []
    for provider_name, provider_groups in (affiliate_products or {}).items():
        for group in provider_groups or []:
            if not _fuzzy_name_match(product_name, group.get("product_name", "")):
                continue
            for offer in group.get("offers", []) or []:
                p = _extract_price(offer)
                if p is not None and p > 0:
                    prices.append(p)
    return statistics.median(prices) if prices else None


def _best_rating(
    product_name: str,
    review_data: Dict[str, Any],
    review_aspects: Optional[List[Dict[str, Any]]],
    product: Dict[str, Any],
) -> Optional[float]:
    """Best available rating signal: review_search avg_rating, then legacy
    review_aspects, then the normalized product's own rating."""
    if review_data:
        for rname, rbundle in review_data.items():
            if _fuzzy_name_match(product_name, rname):
                rating = (rbundle or {}).get("avg_rating", 0)
                if rating:
                    return float(rating)
    if review_aspects:
        for r in review_aspects:
            if product_name in r.get("product", "") and r.get("rating"):
                return float(r["rating"])
    if product.get("rating"):
        return float(product["rating"])
    return None


# Tool contract for planner
TOOL_CONTRACT = {
    "name": "product_ranking",
    "intent": "product",
    "purpose": "Scores and ranks products based on multiple quality factors including review sentiment, ratings, value for money, and relevance to user criteria. When the user stated a budget, ranking favors rating-per-dollar value within that budget. This tool combines evidence from reviews with search relevance to produce an ordered list from best to worst. Use this when user wants to know which product is best overall or needs help prioritizing between multiple options.",
    "tools": {
        "pre": [],  # Needs review_aspects from evidence
        "post": []  # Compose is auto-added at end of intent
    },
    "produces": ["ranked_products"],
    "citation_message": "Weighing the tradeoffs…",
    "is_default": True
}


@tool_error_handler(tool_name="product_ranking", error_message="Failed to rank products")
async def product_ranking(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Rank products by quality, relevance, and budget-aware value.

    Reads from state:
        - product_names: List of product name strings from product_search
        - normalized_products: Normalized product objects (optional, preferred over product_names)
        - review_aspects: Review analysis results (optional)
        - affiliate_products: Affiliate link data by provider (optional, supplies prices)
        - review_data: Review data from review_search (optional, supplies ratings)
        - slots: Conversation slots; slots["budget"] is a STRING ("$500–$1,000",
                 "under $100", "$500+") since PR #94 — legacy numbers still accepted

    Writes to state:
        - ranked_products: Ranked list of products with scores. When a budget was
          stated, items carry price / rating / in_budget / value_per_dollar so
          compose can mirror the value order.

    Returns:
        {
            "ranked_products": [...],
            "success": bool
        }
    """
    try:
        # Read from state — prefer normalized_products, fall back to product_names
        normalized_products = state.get("normalized_products", [])
        product_names = state.get("product_names", [])

        # Build a list of product dicts to rank
        products = []
        if normalized_products:
            products = normalized_products
        elif product_names:
            # Convert name strings to minimal dicts
            products = [{"name": name, "title": name} for name in product_names]

        review_aspects = state.get("review_aspects")
        review_data = state.get("review_data", {}) or {}
        affiliate_products = state.get("affiliate_products", {}) or {}

        # Outcome 9: budget bounds from the conversation slots.
        slots = state.get("slots", {}) or {}
        budget_min, budget_max = _parse_budget(slots.get("budget"))
        has_budget = budget_min is not None or budget_max is not None
        # F2 semantics (shared with compose): ceiling is always hard; the floor is
        # hard only on floor-only budgets ("$500+" = quality intent). On a range
        # ("$80–$130") a cheaper product is a deal, not a violation.
        floor_is_hard = budget_min is not None and budget_max is None

        logger.info(
            f"[product_ranking] Ranking {len(products)} products"
            + (f" (budget: min={budget_min}, max={budget_max})" if has_budget else " (no budget stated)")
        )

        ranked_items = []

        for idx, product in enumerate(products):
            product_name = product.get("title") or product.get("name", f"Product {idx+1}")

            # Calculate score based on multiple factors
            score = 0.0
            reasons = []

            # Factor 1: Authority/quality score from normalized data
            authority = product.get("authority_score", 0) or product.get("score", 0)
            if authority > 0:
                score += min(authority, 1.0) if authority <= 1.0 else authority / 10
                if authority > 7 or (authority <= 1.0 and authority > 0.7):
                    reasons.append("High authority source")

            # Factor 2: Review data from review_search (product_name -> ReviewBundle)
            if review_data:
                # Fuzzy match product name against review_data keys
                matching_bundle = None
                for rname, rbundle in review_data.items():
                    if _fuzzy_name_match(product_name, rname):
                        matching_bundle = rbundle
                        break

                if matching_bundle:
                    rating = matching_bundle.get("avg_rating", 0)
                    total_reviews = matching_bundle.get("total_reviews", 0)
                    quality_score = matching_bundle.get("quality_score", 0)
                    if rating > 0:
                        score += rating / 5  # Normalize to 0-1
                        if rating >= 4.0:
                            reasons.append(f"Highly rated ({rating}/5)")
                    if total_reviews > 50:
                        reasons.append(f"{total_reviews} reviews")
                    if quality_score > 3.0:
                        score += 0.1

            # Factor 2b: Legacy review_aspects support
            elif review_aspects:
                matching_review = next(
                    (r for r in review_aspects if product_name in r.get("product", "")),
                    None
                )
                if matching_review:
                    rating = matching_review.get("rating", 0)
                    score += rating / 5
                    if rating >= 4.0:
                        reasons.append(f"Highly rated ({rating}/5)")
                    pros_count = len(matching_review.get("pros", []))
                    if pros_count > 2:
                        reasons.append(f"{pros_count} positive aspects")

            # Factor 3: Affiliate availability (check all providers)
            if affiliate_products:
                has_affiliate = False
                for provider_name, provider_groups in affiliate_products.items():
                    for group in provider_groups:
                        if _fuzzy_name_match(product_name, group.get("product_name", "")):
                            has_affiliate = True
                            break
                    if has_affiliate:
                        break
                if has_affiliate:
                    score += 0.2
                    reasons.append("Available for purchase")

            # Normalize legacy score
            score = min(1.0, score)

            item: Dict[str, Any] = {
                "product_name": product_name,
                "score": round(score, 2),
                "reasons": reasons,
            }

            # ── Outcome 9: attach value signals when a budget was stated ──
            if has_budget:
                price = _median_offer_price(product_name, affiliate_products)
                rating = _best_rating(product_name, review_data, review_aspects, product)
                item["price"] = price
                item["rating"] = rating
                if price is not None:
                    over_ceiling = budget_max is not None and price > budget_max
                    under_hard_floor = floor_is_hard and price < budget_min
                    item["in_budget"] = not (over_ceiling or under_hard_floor)
                else:
                    item["in_budget"] = None  # no price signal

            ranked_items.append(item)

        # ── Outcome 9: budget-aware value scoring ──
        # Within the budget, rating-per-dollar decides: value candidates are lifted
        # into a 2.0–3.0 score band (above every legacy 0–1 score), normalized so
        # the best value lands at 3.0. Out-of-budget products are penalized below
        # everything in budget. No budget → legacy scores stand untouched.
        if has_budget:
            value_candidates = [
                it for it in ranked_items
                if it.get("in_budget") and it.get("rating") and it.get("price")
            ]
            if value_candidates:
                max_value = max(it["rating"] / it["price"] for it in value_candidates)
                for it in value_candidates:
                    value = it["rating"] / it["price"]
                    it["value_per_dollar"] = round(value, 5)
                    it["score"] = round(2.0 + (value / max_value), 2)
                    if value == max_value:
                        it["reasons"].insert(
                            0, f"Best value in your budget (${it['price']:.0f} at {it['rating']}★)"
                        )
                    else:
                        it["reasons"].insert(0, f"${it['price']:.0f} at {it['rating']}★ — in budget")
                logger.info(
                    f"[product_ranking] Value ranking applied to {len(value_candidates)} in-budget products; "
                    f"best value: {max(value_candidates, key=lambda x: x['value_per_dollar'])['product_name']}"
                )

            for it in ranked_items:
                if it.get("in_budget") is False:
                    it["score"] = round(it["score"] * 0.3, 2)
                    it["reasons"].append("Outside stated budget")

        # Sort by score descending
        ranked_items.sort(key=lambda x: x["score"], reverse=True)

        # Comparison queries: alternate the two sides through the shortlist so
        # one brand can't sweep every visible card (QA 2026-06-10).
        comparison_pair = slots.get("comparison_products") or []
        if isinstance(comparison_pair, list) and len(comparison_pair) == 2:
            before = [it["product_name"] for it in ranked_items[:4]]
            ranked_items = _interleave_comparison_sides(ranked_items, comparison_pair)
            after = [it["product_name"] for it in ranked_items[:4]]
            if before != after:
                logger.info(
                    f"[product_ranking] Comparison interleave ({comparison_pair[0]!r} vs "
                    f"{comparison_pair[1]!r}): top 4 now {after}"
                )

        logger.info(f"[product_ranking] Top product: {ranked_items[0]['product_name'] if ranked_items else 'None'}")

        return {
            "ranked_products": ranked_items,
            "success": True
        }

    except Exception as e:
        logger.error(f"[product_ranking] Error: {e}", exc_info=True)
        return {
            "ranked_products": [],
            "error": str(e),
            "success": False
        }
