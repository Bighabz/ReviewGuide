"""
Product Normalize Tool

Merges product data from multiple sources (search, evidence, affiliate, ranking).
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


def _fuzzy_product_match(query_name: str, candidate_name: str, threshold: float = 0.45) -> bool:
    """Token-overlap Jaccard similarity for fuzzy product matching."""
    q_tokens = set(query_name.lower().split())
    c_tokens = set(candidate_name.lower().split())
    if not q_tokens or not c_tokens:
        return False
    intersection = q_tokens & c_tokens
    union = q_tokens | c_tokens
    return len(intersection) / len(union) >= threshold


# Tool contract for planner
TOOL_CONTRACT = {
    "name": "product_normalize",
    "intent": "product",
    "purpose": "Create normalized product list from product names with review data merged in. Merges data from search/extractor, evidence, and ranking into a unified product list.",
    "tools": {
        "pre": [],  # Needs product_names from either search or extractor
        "post": ["product_affiliate"]  # Compose is auto-added at end of intent
    },
    "produces": ["normalized_products"],
    "citation_message": "Sorting the contenders…",
    "is_default": True
}


@tool_error_handler(tool_name="product_normalize", error_message="Failed to normalize products")
async def product_normalize(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize product names into structured product objects.

    Reads from state:
        - product_names: List of product names from product_search
        - review_aspects: Review analysis (optional)

    Writes to state:
        - normalized_products: Normalized product data

    Returns:
        {
            "normalized_products": [...],
            "success": bool
        }
    """
    try:
        # Read from state
        product_names = state.get("product_names", [])
        review_aspects = state.get("review_aspects")
        ranked_items = state.get("ranked_products")

        logger.info(f"[product_normalize] Normalizing {len(product_names)} products")

        normalized_products = []

        for idx, product_name in enumerate(product_names):
            # Start with basic product data from name
            normalized = {
                "id": f"product_{idx}",
                "name": product_name,
                "url": f"ai://product/{idx+1}/{product_name.lower().replace(' ', '-')}",
                "snippet": f"Product suggestion from OpenAI: {product_name}",
                "score": 0.0,
                "pros": [],
                "cons": [],
                "best_offer": None,
                "badges": []
            }

            # Merge ranking data
            if ranked_items:
                matching_rank = next(
                    (r for r in ranked_items if _fuzzy_product_match(product_name, r.get("product_name", ""))),
                    None
                )
                if matching_rank:
                    normalized["score"] = matching_rank.get("score", 0.0)
                    if matching_rank.get("reasons"):
                        normalized["badges"] = matching_rank["reasons"][:2]  # Top 2 reasons

            # Merge review aspects
            if review_aspects:
                matching_review = next(
                    (r for r in review_aspects if _fuzzy_product_match(product_name, r.get("product", ""))),
                    None
                )
                if matching_review:
                    normalized["pros"] = matching_review.get("pros", [])[:3]  # Top 3 pros
                    normalized["cons"] = matching_review.get("cons", [])[:2]  # Top 2 cons
                    normalized["rating"] = matching_review.get("rating", 0.0)

            normalized_products.append(normalized)

        # Sort by score
        normalized_products.sort(key=lambda x: x.get("score", 0), reverse=True)

        logger.info(f"[product_normalize] Normalized {len(normalized_products)} products")

        return {
            "normalized_products": normalized_products,
            "success": True
        }

    except Exception as e:
        logger.error(f"[product_normalize] Error: {e}", exc_info=True)
        return {
            "normalized_products": [],
            "error": str(e),
            "success": False
        }
