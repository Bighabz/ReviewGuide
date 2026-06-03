"""
Product Affiliate Tool

Finds affiliate/monetized links for products.
Supports multiple affiliate networks dynamically based on configuration.
Returns a dictionary of provider -> products for flexible frontend rendering.
"""

import sys
import os
import asyncio
from typing import Dict, Any, List
from app.core.error_manager import tool_error_handler

# Add backend to path (portable path)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


# ---------------------------------------------------------------------------
# Curated-link matching
#
# find_curated_links() returns a whole *category bucket* (e.g. the 5-6 entries
# under "noise cancelling headphone"), NOT a per-product match. The previous
# code zipped that bucket against the LLM's product list by index, so slot N
# always got curated entry N regardless of what the LLM picked for slot N —
# guaranteeing a mismatch (Sony card -> Bose link). Advertising product X with
# an affiliate link to product Y is an Amazon Associates / FTC compliance risk,
# so we match by product name and only attach a curated link when it genuinely
# corresponds to the card's product.
#
# We deliberately do NOT reuse _fuzzy_product_match (token-overlap Jaccard,
# threshold 0.35): in this category-heavy domain it both over-matches across
# brands (Sony vs Beats both share "wireless/noise/cancelling/headphones") and
# under-matches short-vs-long titles ("Bose QuietComfort Ultra" vs the long
# curated Bose title scores ~0.29). For a compliance fix, precision matters far
# more than recall — a wrong link is exactly the bug we're fixing — so we
# require a brand anchor plus a shared distinctive (non-generic) token.
# ---------------------------------------------------------------------------

# Category / marketing words that are too generic to anchor a product identity.
_GENERIC_TOKENS = frozenset({
    "the", "a", "an", "with", "for", "and", "of", "by", "new", "best",
    "wireless", "bluetooth", "wifi", "wi-fi", "portable", "cordless",
    "noise", "cancelling", "canceling", "cancellation", "anc", "active", "hybrid",
    "headphones", "headphone", "earbuds", "earbud", "headset", "speaker", "speakers",
    "smart", "series", "gen", "generation", "edition", "model", "set",
    "2023", "2024", "2025", "2026",
})


def _normalize_tokens(name: str) -> list:
    """Lowercase, strip parens, split on whitespace into tokens."""
    cleaned = (name or "").lower().replace("(", " ").replace(")", " ").replace(",", " ")
    return [t for t in cleaned.split() if t]


def _match_curated_entry(product_name: str, curated_links: list, used: set):
    """Return the index of the curated entry that genuinely matches product_name,
    or None if no curated entry corresponds to this product.

    Matching rule (precision over recall):
      1. Brand anchor — the leading token (brand) of either name must appear in
         the other name's tokens. This blocks same-category cross-brand collisions
         (e.g. "LG Front Load Washer" vs "Samsung Front Load Washer").
      2. At least two shared distinctive (non-generic) tokens, so a bare brand
         match isn't enough (blocks "Sony WH-1000XM5" matching "Sony WH-1000XM4").

    Already-used indices are skipped so two different cards never get the same link.
    Among candidates, the one with the most shared distinctive tokens wins.
    """
    p_tokens = _normalize_tokens(product_name)
    if not p_tokens:
        return None
    p_set = set(p_tokens)

    best_idx = None
    best_overlap = 0
    for idx, entry in enumerate(curated_links):
        if idx in used:
            continue
        title = entry.get("title", "") if isinstance(entry, dict) else str(entry)
        c_tokens = _normalize_tokens(title)
        if not c_tokens:
            continue
        c_set = set(c_tokens)

        brand_anchor = (c_tokens[0] in p_set) or (p_tokens[0] in c_set)
        if not brand_anchor:
            continue

        shared_distinctive = {
            t for t in (p_set & c_set)
            if t not in _GENERIC_TOKENS and len(t) >= 2
        }
        if len(shared_distinctive) < 2:
            continue

        if len(shared_distinctive) > best_overlap:
            best_overlap = len(shared_distinctive)
            best_idx = idx

    return best_idx


# Tool contract for planner
TOOL_CONTRACT = {
    "name": "product_affiliate",
    "intent": "product",
    "purpose": "Find affiliate/monetization links for products from configured providers (eBay, Amazon, etc). Fetches real purchase links and prices.",
    "tools": {
        "pre": [],  # Needs normalized_products
        "post": ["product_ranking"]  # Compose is auto-added at end of intent
    },
    "produces": ["affiliate_products"],
    "citation_message": "Cross-checking the specs…",
    "is_default": True
}


@tool_error_handler(tool_name="product_affiliate", error_message="Failed to get affiliate links")
async def product_affiliate(
    state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Find affiliate links for products from all configured providers.

    Reads from state:
        - normalized_products: List of normalized products (with name field)
        - slots.country_code: Optional country code for regional links

    Writes to state:
        - affiliate_products: Dict mapping provider_name -> list of product results
          Example: {"ebay": [...], "amazon": [...]}

    Returns:
        {
            "affiliate_products": {
                "ebay": [{"product_name": "...", "offers": [...]}],
                "amazon": [{"product_name": "...", "offers": [...]}],
                ...
            },
            "success": bool
        }
    """
    # Import here to avoid settings validation at module load
    from app.core.centralized_logger import get_logger
    from app.services.affiliate.manager import affiliate_manager
    from app.core.config import settings

    logger = get_logger(__name__)

    try:
        # Read from state - support both normalized_products and product_names as fallback
        products = state.get("normalized_products", [])
        product_names = state.get("product_names", [])
        max_offers = settings.MAX_AFFILIATE_OFFERS_PER_PRODUCT

        # Get country code and category from slots, with context fallback
        slots = state.get("slots", {})
        last_search_context = state.get("last_search_context", {})
        country_code = slots.get("country_code", settings.AMAZON_DEFAULT_COUNTRY)
        category = slots.get("category") or last_search_context.get("category")

        # Prepare product names to search
        products_to_search = []

        # First try to get names from normalized_products
        if products:
            for product in products[:8]:  # Limit to top 8 products
                product_name = product.get("title") or product.get("name") or ""
                if product_name:
                    products_to_search.append(product_name)

        # Fallback to product_names if normalized_products is empty
        if not products_to_search and product_names:
            logger.info("[product_affiliate] Using product_names as fallback (normalized_products was empty)")
            products_to_search = product_names[:8]

        logger.info(f"[product_affiliate] Finding links for {len(products_to_search)} products (country={country_code})")

        if not products_to_search:
            return {
                "affiliate_products": {},
                "success": True
            }

        # Check for curated Amazon links matching the user's query
        user_message = state.get("user_message", "")
        curated_amazon_links = None
        try:
            from app.services.affiliate.providers.curated_amazon_links import find_curated_links
            curated_amazon_links = find_curated_links(user_message)
            if not curated_amazon_links and category:
                curated_amazon_links = find_curated_links(category)
            if curated_amazon_links:
                logger.info(f"[product_affiliate] Found {len(curated_amazon_links)} curated Amazon links for query")
        except Exception as e:
            logger.warning(f"[product_affiliate] Curated link lookup failed: {e}")

        # Get all available providers from the manager
        available_providers = affiliate_manager.get_available_providers()
        # Filter out "mock" provider - we want real affiliate providers
        providers_to_use = [p for p in available_providers if p != "mock"]

        logger.info(f"[product_affiliate] Using providers: {providers_to_use}")

        # Helper function to search a single product on a single provider
        async def search_single_product(provider, provider_name: str, product_name: str) -> Dict[str, Any]:
            """Search one product on one provider."""
            try:
                search_kwargs = {
                    "query": product_name,
                    "limit": max_offers,
                    "category": category,
                }

                # Add country_code for providers that support it
                if hasattr(provider, 'search_products'):
                    import inspect
                    sig = inspect.signature(provider.search_products)
                    if 'country_code' in sig.parameters:
                        search_kwargs['country_code'] = country_code

                search_results = await provider.search_products(**search_kwargs)

                if search_results:
                    offers = []
                    for result in search_results:
                        offer = {
                            "merchant": getattr(result, 'merchant', provider_name.title()),
                            "price": getattr(result, 'price', 0),
                            "currency": getattr(result, 'currency', "USD"),
                            "url": getattr(result, 'affiliate_link', ""),
                            "condition": getattr(result, 'condition', "new"),
                            "title": getattr(result, 'title', ""),
                            "image_url": getattr(result, 'image_url', ""),
                            "rating": getattr(result, 'rating', None),
                            "review_count": getattr(result, 'review_count', None),
                            "source": provider_name
                        }
                        if hasattr(result, 'product_id') and result.product_id:
                            offer["product_id"] = result.product_id
                        offers.append(offer)

                    return {"product_name": product_name, "offers": offers}

            except Exception as e:
                logger.warning(f"[product_affiliate] {provider_name} search failed for {product_name}: {e}")

            return None

        # Helper function to search a provider for all products (in parallel)
        async def search_provider(provider_name: str) -> Dict[str, Any]:
            """Search all products on a single provider using asyncio.gather."""
            # For Amazon: match curated links to each product BY NAME (not by index).
            # A curated entry is only attached when it genuinely corresponds to the
            # card's product (see _match_curated_entry). Products with no curated
            # match fall through to a tagged Amazon search URL for the correct
            # product name — never a mismatched curated link.
            #
            # Harmony Step 1 (shadow fix): this curated path only applies while
            # PA-API is disabled. Once AMAZON_API_ENABLED=true, the Amazon
            # provider's real product search must run — without this gate the
            # curated special-case would shadow PA-API results forever.
            if provider_name == "amazon" and curated_amazon_links and not settings.AMAZON_API_ENABLED:
                results = []
                used_curated = set()
                matched_count = 0
                search_url_count = 0
                for product_name in products_to_search:
                    match_idx = _match_curated_entry(product_name, curated_amazon_links, used_curated)

                    if match_idx is not None:
                        used_curated.add(match_idx)
                        curated = curated_amazon_links[match_idx]
                        # Support both old format (string URL) and new format (dict with metadata)
                        if isinstance(curated, dict):
                            link = curated.get("url", "")
                            title = curated.get("title", product_name)
                            price = curated.get("price", 0)
                            image = curated.get("image_url", "")
                        else:
                            link = curated
                            title = product_name
                            price = 0
                            image = ""
                        matched_count += 1
                        results.append({
                            "product_name": product_name,
                            "offers": [{
                                "merchant": "Amazon",
                                "price": price,
                                "currency": "USD",
                                "url": link,
                                "condition": "new",
                                "title": title,
                                "image_url": image,
                                "rating": None,
                                "review_count": None,
                                "source": "amazon",
                            }]
                        })
                        continue

                    # A2 — no curated match: give this product a tagged Amazon search
                    # URL for its own name so the Amazon link still corresponds to the
                    # card (and earns commission), instead of a wrong curated product.
                    search_url = affiliate_manager.get_amazon_search_url(product_name, country_code)
                    if search_url:
                        search_url_count += 1
                        results.append({
                            "product_name": product_name,
                            "offers": [{
                                "merchant": "Amazon",
                                "price": 0,
                                "currency": "USD",
                                "url": search_url,
                                "condition": "new",
                                "title": product_name,
                                "image_url": "",
                                "rating": None,
                                "review_count": None,
                                "source": "amazon",
                            }]
                        })
                    # else: no curated match and no search URL available -> skip (A1);
                    # other providers (e.g. eBay) still populate the card.

                logger.info(
                    f"[product_affiliate] Amazon: {matched_count} curated name-matches, "
                    f"{search_url_count} search-URL fallbacks "
                    f"({len(products_to_search) - matched_count - search_url_count} skipped)"
                )
                return {"provider": provider_name, "results": results}

            provider = affiliate_manager.get_provider(provider_name)
            if not provider:
                return {"provider": provider_name, "results": []}

            tasks = [
                search_single_product(provider, provider_name, name)
                for name in products_to_search
            ]
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)

            results = []
            for r in raw_results:
                if isinstance(r, Exception):
                    logger.warning(f"[product_affiliate] {provider_name} product search exception: {r}")
                elif r is not None:
                    results.append(r)

            return {"provider": provider_name, "results": results}

        # Execute searches for all providers in parallel
        logger.info(f"[product_affiliate] Starting parallel search for {len(products_to_search)} products on {len(providers_to_use)} providers")

        tasks = [search_provider(provider_name) for provider_name in providers_to_use]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build the affiliate_products dictionary
        affiliate_products = {}
        for result in all_results:
            if isinstance(result, Exception):
                logger.warning(f"[product_affiliate] Provider search failed: {result}")
                continue
            if result and result.get("results"):
                provider_name = result["provider"]
                affiliate_products[provider_name] = result["results"]
                logger.info(f"[product_affiliate] Found {len(result['results'])} product groups from {provider_name}")

        logger.info(f"[product_affiliate] Total providers with results: {list(affiliate_products.keys())}")

        # NOTE (affiliate provider harmony, Step 1): the Serper Google Shopping
        # enrichment that used to be bolted on here is now a real registered
        # provider — app/services/affiliate/providers/serper_shopping_provider.py.
        # It runs in the provider fan-out above and emits the same
        # `serper_shopping` group (real prices/images/merchants), plus optional
        # Skimlinks monetization of non-Amazon/non-eBay merchant URLs.

        return {
            "affiliate_products": affiliate_products,
            "success": True
        }

    except Exception as e:
        logger.error(f"[product_affiliate] Error: {e}", exc_info=True)
        return {
            "affiliate_products": {},
            "error": str(e),
            "success": False
        }
