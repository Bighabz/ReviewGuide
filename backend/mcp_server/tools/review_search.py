"""
Review Search Tool

Searches for real product reviews from trusted sources via SerpAPI.
Runs after product_search to enrich product recommendations with real review data.
"""

import sys
import os
import math
import asyncio
from typing import Dict, Any, List

from app.core.error_manager import tool_error_handler

# Add backend to path (portable path)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Tool contract for planner
TOOL_CONTRACT = {
    "name": "review_search",
    "intent": "product",
    "purpose": "Search for real product reviews from trusted sources (Wirecutter, Reddit, RTINGS, etc.)",
    "tools": {
        "pre": ["product_search"],
        "post": ["product_normalize"]
    },
    "produces": ["review_data"],
    "citation_message": "Seeing what others are saying…",
    "tool_order": 200,
    "is_default": True,
}

# Minimum thresholds for including a product
MIN_AVG_RATING = 3.5
MIN_TOTAL_REVIEWS = 5
MIN_SOURCE_TYPES = 2  # Require at least 2 different source types
PER_PRODUCT_TIMEOUT_S = 8  # Timeout per product review search


def _quality_score(avg_rating: float, total_reviews: int) -> float:
    """
    Calculate review quality score.
    Weights: 60% rating, 40% review volume (log-scaled).
    """
    rating_component = avg_rating * 0.6
    volume_component = math.log10(max(total_reviews, 1)) * 0.4
    return round(rating_component + volume_component, 3)


def _count_source_types(sources: list) -> int:
    """Count distinct source types (editorial, community, shopping)."""
    editorial_domains = {"Wirecutter", "RTINGS", "Tom's Guide", "TechRadar", "CNET", "The Verge", "PCMag", "SoundGuys"}
    community_domains = {"Reddit", "YouTube"}
    shopping_domains = {"Amazon", "Best Buy", "Walmart", "Target"}

    types = set()
    for source in sources:
        name = source.get("site_name", "") if isinstance(source, dict) else getattr(source, "site_name", "")
        if name in editorial_domains:
            types.add("editorial")
        elif name in community_domains:
            types.add("community")
        elif name in shopping_domains:
            types.add("shopping")
        else:
            types.add("other")
    return len(types)


@tool_error_handler(tool_name="review_search", error_message="Failed to search reviews")
async def review_search(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for real product reviews from trusted sources.

    Reads from state:
        - product_names: List of product names from product_search
        - slots: Category and other context

    Writes to state:
        - review_data: Dict mapping product_name -> ReviewBundle dict
        - tool_citations: Status updates for streaming

    Returns:
        {
            "review_data": {product_name: ReviewBundle dict, ...},
            "tool_citations": [...],
            "success": bool
        }
    """
    from app.core.centralized_logger import get_logger
    from app.core.config import settings

    logger = get_logger(__name__)

    # Check if SerpAPI is enabled
    if not settings.ENABLE_SERPAPI or not settings.SERPAPI_API_KEY:
        logger.info("[review_search] SerpAPI disabled or no API key — skipping")
        return {
            "review_data": {},
            "tool_citations": [],
            "success": True,
        }

    try:
        product_names = state.get("product_names", [])
        slots = state.get("slots", {})
        category = slots.get("category", "")

        if not product_names:
            logger.warning("[review_search] No product names in state — skipping")
            return {
                "review_data": {},
                "tool_citations": [],
                "success": True,
            }

        # Take top 3 products max (cap to reduce latency)
        products_to_search = product_names[:3]

        logger.info(f"[review_search] Searching reviews for {len(products_to_search)} products")

        # Emit status update
        tool_citations = [
            {
                "type": "status",
                "message": "Searching reviews across Wirecutter, Reddit, RTINGS...",
            }
        ]

        # Initialize SerpAPI client
        from app.services.serpapi.client import SerpAPIClient
        client = SerpAPIClient()

        # Run parallel searches for all products with per-product timeout
        async def _search_with_timeout(name: str, cat: str):
            return await asyncio.wait_for(
                client.search_reviews(name, cat),
                timeout=PER_PRODUCT_TIMEOUT_S,
            )

        tasks = [
            _search_with_timeout(name, category)
            for name in products_to_search
        ]
        bundles = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        review_data: Dict[str, Any] = {}
        total_sources = 0

        for name, bundle in zip(products_to_search, bundles):
            if isinstance(bundle, Exception):
                logger.warning(f"[review_search] Search failed for '{name}': {bundle}")
                continue

            # Filter: must meet quality thresholds
            has_rating = bundle.avg_rating >= MIN_AVG_RATING
            has_reviews = bundle.total_reviews >= MIN_TOTAL_REVIEWS
            has_sources = len(bundle.sources) > 0
            source_type_count = _count_source_types([{"site_name": s.site_name} for s in bundle.sources])
            has_diverse_sources = source_type_count >= MIN_SOURCE_TYPES

            # Accept if has sources AND (rating OR review count OR diverse source types)
            if has_sources and (has_rating or has_reviews or has_diverse_sources):
                bundle_dict = bundle.to_dict()
                bundle_dict["quality_score"] = _quality_score(bundle.avg_rating, bundle.total_reviews)
                bundle_dict["source_type_count"] = _count_source_types(bundle_dict.get("sources", []))
                review_data[name] = bundle_dict
                total_sources += len(bundle.sources)
                logger.info(
                    f"[review_search] '{name}': {len(bundle.sources)} sources, "
                    f"avg_rating={bundle.avg_rating}, total_reviews={bundle.total_reviews}, "
                    f"quality_score={bundle_dict['quality_score']}"
                )
            else:
                logger.info(
                    f"[review_search] '{name}' filtered out: "
                    f"rating={bundle.avg_rating}, reviews={bundle.total_reviews}, sources={len(bundle.sources)}"
                )

        # Sort by quality score (stored in review_data values)
        if review_data:
            sorted_items = sorted(
                review_data.items(),
                key=lambda x: x[1].get("quality_score", 0),
                reverse=True,
            )
            review_data = dict(sorted_items)

        # Final status update
        tool_citations.append({
            "type": "status",
            "message": f"Found {total_sources} reviews for {len(review_data)} products",
        })

        logger.info(f"[review_search] Complete: {len(review_data)} products with {total_sources} total sources")

        return {
            "review_data": review_data,
            "tool_citations": tool_citations,
            "success": True,
        }

    except Exception as e:
        logger.error(f"[review_search] Error: {e}", exc_info=True)
        return {
            "review_data": {},
            "tool_citations": [],
            "error": str(e),
            "success": False,
        }
