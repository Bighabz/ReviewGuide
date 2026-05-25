"""
Product Ranking Tool

Ranks products by quality, relevance, and user preferences.
"""

from app.core.centralized_logger import get_logger
from app.core.error_manager import tool_error_handler
import sys
import os
from typing import Dict, Any, List
from app.core.error_manager import tool_error_handler

# Add backend to path (portable path)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

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


# Tool contract for planner
TOOL_CONTRACT = {
    "name": "product_ranking",
    "intent": "product",
    "purpose": "Scores and ranks products based on multiple quality factors including review sentiment, ratings, value for money, and relevance to user criteria. This tool combines evidence from reviews with search relevance to produce an ordered list from best to worst. Use this when user wants to know which product is best overall or needs help prioritizing between multiple options.",
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
    Rank products by quality and relevance.

    Reads from state:
        - product_names: List of product name strings from product_search
        - normalized_products: Normalized product objects (optional, preferred over product_names)
        - review_aspects: Review analysis results (optional)
        - affiliate_products: Affiliate link data by provider (optional)
        - review_data: Review data from review_search (optional)

    Writes to state:
        - ranked_products: Ranked list of products with scores

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
        review_data = state.get("review_data", {})
        affiliate_products = state.get("affiliate_products", {})

        logger.info(f"[product_ranking] Ranking {len(products)} products")

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

            # Normalize final score
            score = min(1.0, score)

            ranked_items.append({
                "product_name": product_name,
                "score": round(score, 2),
                "reasons": reasons
            })

        # Sort by score descending
        ranked_items.sort(key=lambda x: x["score"], reverse=True)

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
