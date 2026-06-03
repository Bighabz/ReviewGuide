"""
Product Compose Tool

Formats final product response with UI blocks and citations.
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import quote_plus
from app.core.error_manager import tool_error_handler

# Add backend to path (portable path)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Tool contract for planner
TOOL_CONTRACT = {
    "name": "product_compose",
    "intent": "product",
    "purpose": "Generate final response with product carousel, recommendations, and comparison table. Formats all product data into UI-ready response. This is the final tool in the product flow.",
    "tools": {
        "pre": [],  # Auto-added at end of product intent
        "post": []
    },
    # last_search_context is produced so it lands in shared execution state —
    # next_step_suggestion (which runs after compose) builds the slot-aware
    # refinement chips ("Show cheaper options", "Only <brand>") from it.
    "produces": ["assistant_text", "ui_blocks", "citations", "last_search_context"],
    "citation_message": "Putting it together…",
    "tool_order": 800,
    "is_default": True,
    "is_required": True
}

# Provider display configuration - add new providers here
PROVIDER_CONFIG = {
    "ebay": {
        "title": "Shop on eBay",
        "type": "ebay_products",
        "order": 1
    },
    "amazon": {
        "title": "Shop on Amazon",
        "type": "amazon_products",
        "order": 2
    },
    "serper_shopping": {
        "title": "Shop Online",
        "type": "serper_products",
        "order": 3,
    },
    # Add more providers here as needed:
    # "walmart": {"title": "Shop on Walmart", "type": "walmart_products", "order": 4},
}

# Accessory keywords for relevance filtering
ACCESSORY_KEYWORDS = {
    "case", "charger", "protector", "cable", "adapter",
    "stand", "cover", "sleeve", "mount", "holder", "film",
    "tempered glass", "cleaning kit", "skin", "sticker",
    "screen protector", "screw", "screws", "hinge", "hinges",
    "bracket", "bezel", "replacement part", "repair", "tool kit",
    "rubber feet", "battery", "fan", "heatsink", "power cord",
    "cord", "dongle", "hub", "dock", "replacement filter",
    "logic board", "motherboard", "replacement", "refurbished part",
    "spare part", "hepa filter", "filter cartridge",
}


def _fuzzy_product_match(query_name: str, candidate_name: str, threshold: float = 0.35) -> bool:
    """Token-overlap Jaccard similarity for fuzzy product matching."""
    # Defensive: scraped provider data can put non-strings (dicts) where product
    # names/titles belong — treat as no match rather than crash on .lower().
    if not isinstance(query_name, str) or not isinstance(candidate_name, str):
        return False
    q_tokens = set(query_name.lower().split())
    c_tokens = set(candidate_name.lower().split())
    if not q_tokens or not c_tokens:
        return False
    intersection = q_tokens & c_tokens
    union = q_tokens | c_tokens
    return len(intersection) / len(union) >= threshold


# Domain -> merchant name mapping for label-domain parity correction
_DOMAIN_TO_MERCHANT = {
    "amazon.com": "Amazon",
    "amzn.to": "Amazon",
    "ebay.com": "eBay",
    "walmart.com": "Walmart",
    "bestbuy.com": "Best Buy",
    "target.com": "Target",
    "bhphotovideo.com": "B&H Photo",
    "newegg.com": "Newegg",
    "costco.com": "Costco",
    "homedepot.com": "Home Depot",
    "lowes.com": "Lowe's",
}


def _domain_to_merchant(url: str) -> str:
    """Derive merchant name from URL domain. Returns empty string if unknown."""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower().lstrip("www.")
        for domain, merchant in _DOMAIN_TO_MERCHANT.items():
            if domain in host:
                return merchant
        # Use capitalized domain root as fallback (e.g., "example" from "example.com")
        parts = host.split(".")
        return parts[0].title() if parts else ""
    except Exception:
        return ""


def _assign_editorial_labels(review_data: dict, products_with_offers: list) -> dict:
    """Assign editorial labels based on review quality + price data.
    Returns {product_name: label} mapping."""
    labels = {}
    if not review_data:
        return labels

    # Best Overall = highest quality_score
    sorted_by_quality = sorted(
        review_data.items(),
        key=lambda x: x[1].get("quality_score", 0),
        reverse=True
    )
    if sorted_by_quality and sorted_by_quality[0][1].get("quality_score", 0) > 0:
        labels[sorted_by_quality[0][0]] = "Best Overall"

    # Budget Pick = lowest priced product that has reviews
    priced_products = []
    for p in products_with_offers:
        offer = p.get("best_offer", {})
        price = offer.get("price", 0) if offer else 0
        name = p.get("name", "")
        if price > 0 and name in review_data:
            priced_products.append((name, price))

    if priced_products:
        cheapest = min(priced_products, key=lambda x: x[1])
        if cheapest[0] not in labels:  # Don't overwrite Best Overall
            labels[cheapest[0]] = "Budget Pick"

    return labels


def _find_price_comparisons(products_by_provider: dict) -> dict:
    """Find products available on multiple retailers and compare prices.
    Returns {product_title_normalized: {"best_retailer": str, "best_price": float, "savings": float, "other_prices": [...]}}"""
    from collections import defaultdict
    price_map = defaultdict(list)

    for provider_name, data in products_by_provider.items():
        for product in data["products"]:
            title = product.get("title", "")
            price = product.get("price", 0)
            if title and price > 0:
                # Use fuzzy matching to group same products
                matched = False
                for key in list(price_map.keys()):
                    if _fuzzy_product_match(title, key, threshold=0.5):
                        price_map[key].append({"retailer": provider_name, "price": price, "title": title})
                        matched = True
                        break
                if not matched:
                    price_map[title].append({"retailer": provider_name, "price": price, "title": title})

    # Only return products found on 2+ retailers
    comparisons = {}
    for key, entries in price_map.items():
        retailers = set(e["retailer"] for e in entries)
        if len(retailers) >= 2:
            sorted_entries = sorted(entries, key=lambda x: x["price"])
            comparisons[key] = {
                "best_retailer": sorted_entries[0]["retailer"],
                "best_price": sorted_entries[0]["price"],
                "savings": round(sorted_entries[-1]["price"] - sorted_entries[0]["price"], 2),
                "other_prices": [{"retailer": e["retailer"], "price": e["price"]} for e in sorted_entries[1:]]
            }

    return comparisons


def _is_follow_up_query(query: str, last_context: dict) -> bool:
    """Detect if query references previous search results."""
    if not last_context:
        return False

    q = query.lower().strip()

    reference_signals = [
        "that one", "the first", "the second", "the third",
        "cheapest", "most expensive", "best rated", "any of",
        "compare them", "which one", "between those",
        "more about", "tell me more", "go back to",
        "the one with", "how about the",
    ]
    if any(signal in q for signal in reference_signals):
        return True

    # Very short query with no product category noun
    if len(q.split()) <= 4:
        return True

    return False


COMPARISON_SIGNALS = [
    "compare", "comparison", "which one", "which should",
    "help me decide", "help me choose", "between these",
    "how do these compare", "side by side", "vs", "versus",
    "differences", "pros and cons of each", "better",
]


def _is_comparison_follow_up(query: str, last_context: dict) -> bool:
    """Detect if a follow-up message is asking for comparison of the active shortlist."""
    if not last_context or not last_context.get("product_names"):
        return False
    if len(last_context["product_names"]) < 2:
        return False
    q = query.lower().strip()
    return any(signal in q for signal in COMPARISON_SIGNALS)


def _find_in_history(query: str, history: list) -> dict | None:
    """Scan search_history for a matching previous context."""
    q = query.lower()
    for ctx in reversed(history):
        cat = ctx.get("category", "").lower()
        ptype = ctx.get("product_type", "").lower()
        if cat and cat in q:
            return ctx
        if ptype and ptype in q:
            return ctx
    return None


def _filter_relevant_products(
    affiliate_products: Dict[str, List],
    user_query: str,
    category: str = None,
) -> Dict[str, List]:
    """
    Filter out accessory products that don't match the user's intent.
    Skips filtering if the user is actually looking for accessories.
    """
    query_lower = user_query.lower()

    # If user is searching for accessories, don't filter
    for kw in ACCESSORY_KEYWORDS:
        if kw in query_lower:
            return affiliate_products

    filtered = {}
    total_before = 0
    total_after = 0

    for provider_name, provider_groups in affiliate_products.items():
        filtered_groups = []
        for group in provider_groups:
            offers = group.get("offers", [])
            total_before += len(offers)

            clean_offers = []
            for offer in offers:
                # _str_or: a scraped title can arrive as a dict — treat as no title
                # rather than crash (same bug class as the dict-url prod incident).
                title_lower = _str_or(offer.get("title"), "").lower()
                is_accessory = any(kw in title_lower for kw in ACCESSORY_KEYWORDS)
                if not is_accessory:
                    clean_offers.append(offer)

            total_after += len(clean_offers)

            if clean_offers:
                filtered_groups.append({
                    **group,
                    "offers": clean_offers,
                })

        if filtered_groups:
            filtered[provider_name] = filtered_groups

    removed = total_before - total_after
    if removed > 0:
        from app.core.centralized_logger import get_logger
        get_logger(__name__).info(
            f"[product_compose] Filter: {total_before} → {total_after} products ({removed} filtered)"
        )

    return filtered


def _parse_budget(budget_str: str) -> tuple:
    """
    Parse a budget string into (min_price, max_price) numeric bounds.

    Handles:
    - numeric input 500 / 500.0 → (None, 500.0)   [slot extractor returns budget as a number]
    - "under $500" / "below $500" / "less than $500" → (None, 500.0)
    - "$100-$200" / "$100 to $200" / "$500–$800" (en-dash chips) → (100.0, 200.0)
    - "$1,200+" / "500+" / "over $500" / "at least $500" → (1200.0, None)   [floor]
    - "around $500" / "about $500" / "roughly $500" → (400.0, 600.0)
    - bare "500" / "$500" / "1,200" → (None, 500.0)   [treated as a max ceiling]

    Returns (None, None) when no pattern matches.
    """
    import re
    # The clarifier/slot extractor returns budget NUMERICALLY (e.g. "under $100" → 100),
    # so a bare number must be accepted and treated as a hard max ceiling — otherwise
    # the downstream offer filter is silently skipped and over-budget items leak through.
    if isinstance(budget_str, bool):
        return None, None
    if isinstance(budget_str, (int, float)):
        return (None, float(budget_str)) if budget_str > 0 else (None, None)
    if not budget_str or not isinstance(budget_str, str):
        return None, None
    # "under $500", "below $500", "less than $500"
    m = re.search(r'(?:under|below|less\s+than)\s*\$?([\d,]+)', budget_str, re.I)
    if m:
        return None, float(m.group(1).replace(',', ''))
    # "$100-$200" or "$100 to $200" or "100–200"
    m = re.search(r'\$?([\d,]+)\s*[-\u2013to]+\s*\$?([\d,]+)', budget_str, re.I)
    if m:
        return float(m.group(1).replace(',', '')), float(m.group(2).replace(',', ''))
    # Floor-only budgets — the clarifier's top chip ("$1,200+") and spoken forms
    # ("over $500", "at least $500"). Without these, a "$500+" budget parses to
    # (None, None) → no filtering at all → a $299 item can headline a $500+ ask.
    m = re.search(r'\$?([\d,]+)\s*\+', budget_str)
    if m:
        return float(m.group(1).replace(',', '')), None
    m = re.search(r'(?:over|above|more\s+than|at\s+least|starting\s+at|upwards\s+of)\s*\$?([\d,]+)', budget_str, re.I)
    if m:
        return float(m.group(1).replace(',', '')), None
    # "around $500", "about $500", "roughly $500"
    m = re.search(r'(?:around|about|roughly)\s*\$?([\d,]+)', budget_str, re.I)
    if m:
        center = float(m.group(1).replace(',', ''))
        return center * 0.8, center * 1.2
    # Bare number with no qualifier ("100", "$100", "1,200") — treat as a max ceiling.
    m = re.fullmatch(r'\s*\$?\s*([\d,]+(?:\.\d+)?)\s*', budget_str)
    if m:
        val = float(m.group(1).replace(',', ''))
        return (None, val) if val > 0 else (None, None)
    return None, None


def _str_or(value, default: str = "") -> str:
    """Coerce a provider-supplied field to a usable string.

    Marketplace/scraper APIs (Serper, SerpApi.com, eBay) occasionally return a
    structured value (dict/list) or None where a plain string is expected. Card
    building does string ops (`.lower()`, `in`) on these fields, so a non-string
    must never pass through — return the default instead.
    """
    if isinstance(value, str) and value:
        return value
    return default


def _extract_price(offer: dict) -> float | None:
    """
    Extract a numeric price from an offer dict.

    The offer's price field may be a float, int, or a string like "$499.99" or "1,299".
    Returns None when the price cannot be determined.
    """
    price = offer.get("price")
    if price is None:
        return None
    if isinstance(price, (int, float)):
        return float(price) if price > 0 else None
    if isinstance(price, str):
        import re
        cleaned = re.sub(r'[^\d.]', '', price)
        try:
            val = float(cleaned)
            return val if val > 0 else None
        except ValueError:
            return None
    return None


# Marketplace price hygiene thresholds: an offer priced below LOW × median is
# treated as scraped noise (accessory/scam listing — the "$12 iPhone 15" case);
# above HIGH × median as a bundle/listing error. Deliberately loose so sales,
# refurb and open-box pricing survive.
PRICE_OUTLIER_LOW_RATIO = 0.25
PRICE_OUTLIER_HIGH_RATIO = 4.0


def _drop_price_outliers(offers: list) -> tuple:
    """
    Marketplace price hygiene: drop offers whose price is wildly inconsistent
    with the product's median market price across providers.

    Returns (kept_offers, dropped_offers). Unpriced offers are always kept —
    they carry affiliate links, not price signal. With fewer than 2 priced
    offers there is no market consensus to compare against, so everything is
    kept. If filtering would drop every priced offer, everything is kept
    (degraded beats empty).
    """
    import statistics

    priced = [(o, _extract_price(o)) for o in offers]
    prices = [p for _, p in priced if p is not None]
    if len(prices) < 2:
        return offers, []

    median_price = statistics.median(prices)
    if median_price <= 0:
        return offers, []

    kept, dropped = [], []
    for offer, price in priced:
        if price is None:
            kept.append(offer)
            continue
        ratio = price / median_price
        if ratio < PRICE_OUTLIER_LOW_RATIO or ratio > PRICE_OUTLIER_HIGH_RATIO:
            dropped.append(offer)
        else:
            kept.append(offer)

    # Never drop every priced offer — keep-all fallback.
    if not any(_extract_price(o) is not None for o in kept):
        return offers, []
    return kept, dropped


def _synthesize_transitional(user_message: str, slots: Optional[dict]) -> str:
    """E2: deterministically frame the shortlist when the query carries a real
    constraint but the LLM declined to emit transitional_reasoning.

    The LLM is reluctant to produce this aside even on clearly-constrained
    queries, so when it returns "" we fill it from the parsed budget / explicit
    use-case slot. Returns "" when there is no constraint to frame — preserving
    the conservative default for bare "best X" queries.

    Intentionally pick-agnostic: it frames *how the constraint shapes the
    ranking*, never naming a specific product — naming one risks contradicting
    the guide's actual #1 (the blog order is not the LLM's final pick).
    """
    slots = slots or {}

    # Budget — prefer the structured slot, fall back to parsing the raw message.
    _, max_b = _parse_budget(slots.get("budget"))
    if max_b is None:
        _, max_b = _parse_budget(user_message or "")

    if max_b and max_b > 0:
        budget = f"${int(max_b)}" if float(max_b).is_integer() else f"${max_b}"
        return f"Under {budget}, the shortlist is built to fit the budget — value leads over flagship extras."

    # Use-case — only from an explicit slot, to avoid free-text false positives.
    use_case = str(slots.get("use_case") or "").strip()
    if use_case:
        return f"For {use_case}, the priorities shift — and the shortlist reflects it."

    return ""


def _format_history(conversation_history: Optional[list], n: int = 6) -> Optional[str]:
    """Format the last ``n`` conversation turns for build_system_prompt's history
    slot. Session-scoped only (the caller passes session history; cross-chat
    content is forbidden). Returns None when there is nothing to show.
    """
    if not conversation_history:
        return None
    recent = conversation_history[-n:]
    lines = [
        f"{msg.get('role', 'user')}: {msg.get('content', '')[:150]}"
        for msg in recent
        if msg.get("content")
    ]
    return "\n".join(lines) or None


def _profile_inject(user_prefs: Optional[dict]) -> Optional[str]:
    """Build a one-line personality-profile fragment from accumulated user
    preferences (past categories / brands) for build_system_prompt's profile
    slot. Returns None for users with no history — never an empty string, per
    the build_system_prompt contract.
    """
    user_prefs = user_prefs or {}
    cats = list(user_prefs.get("categories", {}).keys())[:2]
    brands = list(user_prefs.get("brands", {}).keys())[:2]
    # Tier 5b: surface the richer signal preference_service already stores
    # (use-cases, budget tier, favored features) — not just categories + brands —
    # so the composer can calibrate the pick to who this returning buyer is.
    use_cases = list((user_prefs.get("use_cases") or {}).keys())[:2]
    budgets = list(user_prefs.get("budget_ranges") or [])[-1:]  # most recent budget
    features = list(user_prefs.get("features") or [])[:3]
    parts = []
    if cats:
        parts.append(f"often shops for {', '.join(cats)}")
    if brands:
        parts.append(f"favors {', '.join(brands)}")
    if use_cases:
        parts.append(f"typically buying for {', '.join(use_cases)}")
    if budgets:
        parts.append(f"usually budgets around {budgets[0]}")
    if features:
        parts.append(f"cares about {', '.join(features)}")
    if not parts:
        return None
    return f"Returning user who {'; '.join(parts)}."


async def _voice_revise_body(body: str, follow_up: str, transitional: str, user_message: str) -> Optional[dict]:
    """Tier 3 (Option B) draft→revise voice pass: one extra LLM call that polishes
    the assembled draft for maximum voice adherence (rank-and-commit, no glaze,
    position-by-fit) WITHOUT inventing new facts. Returns the revised
    ``{body, follow_up_question, transitional_reasoning}``, or None on any failure
    so the caller keeps the original draft."""
    import json as _json
    from app.core.centralized_logger import get_logger
    from app.services.model_service import model_service
    from app.services.prompts.voice import build_system_prompt
    logger = get_logger(__name__)

    revise_role = """You are the senior editor doing a FINAL VOICE PASS on a draft buying-guide response.
Rewrite the draft body to maximize voice adherence:
- Commit to a ranked #1 and #2 with a clear WHY the #1 wins for the default buyer.
- Cut every trace of glaze, empty affirmation, or hedging.
- Position alternatives by who they fit — never call anything "bad".
- Keep it tight and skimmable; preserve the draft's length and EVERY concrete fact.
- Do NOT add products, specs, prices, numbers, or URLs not already in the draft.
Return ONLY a JSON object: {"body": "...", "follow_up_question": "...", "transitional_reasoning": "..."}.
Keep follow_up_question to exactly one specific question; leave transitional_reasoning unchanged unless it breaks its one-sentence rule."""
    draft = _json.dumps({
        "body": body,
        "follow_up_question": follow_up,
        "transitional_reasoning": transitional,
    })
    try:
        messages = [
            {"role": "system", "content": build_system_prompt(role_prompt=revise_role, kind="response")},
            {"role": "user", "content": f'User asked: "{user_message}"\n\nDraft to revise:\n{draft}'},
        ]
        raw = await model_service.generate_compose(
            messages=messages,
            temperature=0.4,
            max_tokens=900,
            response_format={"type": "json_object"},
            agent_name="voice_pass_reviser",
        )
        parsed = _json.loads(raw)
        if isinstance(parsed, dict) and (parsed.get("body") or "").strip():
            return parsed
        logger.warning("[product_compose] Voice pass returned no usable body; keeping draft")
    except Exception as e:
        logger.warning(f"[product_compose] Voice pass failed ({e}); keeping draft")
    return None


@tool_error_handler(tool_name="product_compose", error_message="Failed to compose product response")
async def product_compose(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format final product response with assistant text and UI blocks.

    Reads from state:
        - user_message: Original user query
        - normalized_products: Normalized product data
        - affiliate_products: Dict of provider -> products (dynamic)
        - intent: User intent (optional)
        - slots: Extracted slots (optional)
        - review_data: Dict of product_name -> ReviewBundle (optional)
        - general_product_info: Factoid answer from product_general_information tool (optional)

    Writes to state:
        - assistant_text: Final response text
        - ui_blocks: UI components for display (dynamic provider carousels + recommendations)
        - citations: Source citations

    Returns:
        {
            "assistant_text": str,
            "ui_blocks": [...],
            "citations": [...],
            "success": bool
        }
    """
    # Import here to avoid settings validation at module load
    from app.core.centralized_logger import get_logger
    from app.services.model_service import model_service
    from app.services.prompts.voice import build_system_prompt
    from app.core.config import settings

    logger = get_logger(__name__)

    try:
        # Read from state
        user_message = state.get("user_message", "")
        user_message_lower = user_message.lower()
        normalized_products = state.get("normalized_products", [])
        affiliate_products_raw = state.get("affiliate_products", {})  # Dynamic: {"ebay": [...], "amazon": [...]}
        intent = state.get("intent", "product")
        slots = state.get("slots")
        last_search_context = state.get("last_search_context", {})
        category = (slots.get("category") if slots else None) or last_search_context.get("category")

        # Filter out accessory junk from any provider
        affiliate_products = _filter_relevant_products(affiliate_products_raw, user_message, category)
        comparison_table = state.get("comparison_table")
        review_data = state.get("review_data", {})  # product_name -> ReviewBundle dict from review_search
        general_product_info = state.get("general_product_info", "")

        # Log provider info
        providers_with_data = list(affiliate_products.keys())
        logger.info(f"[product_compose] Composing response for {len(normalized_products)} products with providers: {providers_with_data}")

        # Check for comparison HTML from product_comparison tool
        comparison_html = state.get("comparison_html")
        comparison_data = state.get("comparison_data")

        # ── Comparison follow-up detection (UX-05) ──
        if _is_comparison_follow_up(user_message, last_search_context):
            product_names = last_search_context.get("product_names", [])[:5]
            logger.info(f"[product_compose] Comparison follow-up detected for {product_names}")
            comparison_products = []
            for pname in product_names:
                price = last_search_context.get("top_prices", {}).get(pname, 0)
                rating = last_search_context.get("avg_rating", {}).get(pname, 0)
                comparison_products.append({
                    "title": pname,
                    "price": price,
                    "currency": "USD",
                    "rating": rating,
                    "merchant": "",
                    "url": "",
                })
            comparison_block = {
                "type": "product_comparison",
                "title": "Product Comparison",
                "data": {
                    "products": comparison_products,
                    "criteria": [],
                    "summary": f"Comparing {', '.join(product_names[:3])}{'...' if len(product_names) > 3 else ''}",
                }
            }
            return {
                "assistant_text": "Here's a side-by-side comparison of the products from your search.",
                "ui_blocks": [comparison_block],
                "citations": [],
                "last_search_context": last_search_context,
                "search_history": list(state.get("search_history", [])),
                "success": True
            }

        # Check if we have any data to display
        if not normalized_products and not affiliate_products and not review_data:
            if general_product_info and general_product_info.strip():
                return {
                    "assistant_text": general_product_info,
                    "ui_blocks": [],
                    "citations": [],
                    "success": True
                }
            assistant_text = (
                "I wasn't able to find current listings for that product. "
                "Try searching with a broader term — for example, the product category "
                "or brand name — and I'll pull up the best options available."
            )
            return {
                "assistant_text": assistant_text,
                "ui_blocks": [],
                "citations": [],
                "success": True
            }

        # Emit skeleton product cards immediately so the user sees product names
        # while affiliate data and blog article are still loading
        if normalized_products:
            skeleton_names = [p.get("name", "") for p in normalized_products[:5] if p.get("name")]
            if skeleton_names:
                state["stream_chunk_data"] = {
                    "type": "skeleton_cards",
                    "data": [{"name": n} for n in skeleton_names],
                }
                logger.info(f"[product_compose] Emitted {len(skeleton_names)} skeleton cards")

        # Merge affiliate links into products for UI display
        # Flatten all affiliate offers from all providers for matching
        all_affiliate_groups = []
        for provider_name, provider_groups in affiliate_products.items():
            for group in provider_groups:
                all_affiliate_groups.append({
                    **group,
                    "provider": provider_name
                })

        # Parse budget constraint once — used for offer-level filtering below
        budget_str = (slots.get("budget", "") or "") if slots else ""
        budget_min, budget_max = _parse_budget(budget_str)

        products_with_offers = []
        for product in normalized_products:
            product_copy = product.copy()
            product_name = product.get('name', '')

            # Skip products whose name matches an accessory keyword
            # (supplements _filter_relevant_products which only checks offer titles)
            if not any(kw in user_message_lower for kw in ACCESSORY_KEYWORDS):
                product_name_lower = product_name.lower()
                if any(kw in product_name_lower for kw in ACCESSORY_KEYWORDS):
                    logger.info(f"[product_compose] Suppressed accessory product: {product_name}")
                    continue

            # Find matching affiliate links from ALL providers
            all_offers_for_product = []
            for a in all_affiliate_groups:
                if _fuzzy_product_match(product_name, a.get("product_name", "")) and a.get("offers"):
                    provider = a.get("provider", "")
                    offer = a["offers"][0]
                    # Sanitize provider text fields at the single entry point into card
                    # building. Scraped/marketplace APIs occasionally return structured
                    # values (a dict/list) where a plain string is expected — a dict url
                    # crashed every downstream `.lower()` call and killed the whole
                    # response (prod incident 2026-06-02: "'dict' object has no
                    # attribute 'lower'"). Blank the bad value, log which provider sent
                    # it, and let the card degrade gracefully instead.
                    for _field, _default in (("merchant", provider.title()), ("currency", "USD"), ("url", ""), ("image_url", "")):
                        _raw = offer.get(_field, _default)
                        if not isinstance(_raw, str):
                            logger.warning(
                                f"[product_compose] Non-string '{_field}' from provider "
                                f"'{provider}' for {product_name}: {type(_raw).__name__}({str(_raw)[:120]}) — blanked"
                            )
                    all_offers_for_product.append({
                        "merchant": _str_or(offer.get("merchant"), provider.title()),
                        "price": offer.get("price", 0),
                        "currency": _str_or(offer.get("currency"), "USD"),
                        "url": _str_or(offer.get("url"), ""),
                        "image_url": _str_or(offer.get("image_url"), ""),
                        "rating": offer.get("rating"),
                        "review_count": offer.get("review_count"),
                        "source": provider
                    })

            if all_offers_for_product:
                # Marketplace price hygiene: drop scraped-noise offers (accessory/scam
                # listings, bundles) whose price is wildly inconsistent with the
                # product's median market price across providers — BEFORE the backfill
                # below, so a "$12 iPhone 15" case listing can never become the card's
                # headline price or the backfill source.
                clean_offers, outlier_offers = _drop_price_outliers(all_offers_for_product)
                if outlier_offers:
                    dropped_desc = [
                        f"${_extract_price(o):.2f} ({o.get('merchant', '?')})"
                        for o in outlier_offers
                    ]
                    logger.info(
                        f"[product_compose] Price hygiene: dropped {len(outlier_offers)} "
                        f"outlier offer(s) for {product_name}: {dropped_desc}"
                    )
                    all_offers_for_product = clean_offers

                # Backfill a REAL price/image from the Serper Google Shopping offer
                # onto offers that lack them. Affiliate providers run in mock mode
                # (Amazon price=0 without PA-API), and the Amazon offer sorts first —
                # so it drives the card's headline price. Without this, that headline
                # renders "$0". Stamping Serper's real market price + product image
                # onto unpriced offers makes the card look as it would with PA-API,
                # while preserving the Amazon affiliate buy-link. The serper_shopping
                # offer also remains as its own (true-merchant) retailer line.
                # A "real" price comes from an offer that has both a price and a
                # trustworthy (non-placeholder) image. Prefer Serper Google Shopping;
                # otherwise fall back to any such offer — this picks up a live eBay
                # Browse-API offer while still EXCLUDING eBay's mock placeholder-image
                # offers, whose synthetic prices must never surface.
                def _is_real_priced(o):
                    return (
                        _extract_price(o) is not None
                        and "placehold.co" not in (o.get("image_url") or "")
                    )

                real_src = next(
                    (o for o in all_offers_for_product
                     if o.get("source") == "serper_shopping" and _is_real_priced(o)),
                    None,
                ) or next(
                    (o for o in all_offers_for_product if _is_real_priced(o)),
                    None,
                )
                if real_src:
                    real_price = _extract_price(real_src)
                    real_image = real_src.get("image_url", "")
                    for o in all_offers_for_product:
                        if o is real_src:
                            continue
                        if _extract_price(o) is None:
                            o["price"] = real_price
                        # Only fill EMPTY images (Amazon mock). eBay mock offers keep
                        # their placehold.co image so the downstream real-offer filter
                        # still drops them — their synthetic prices must never surface.
                        if real_image and not o.get("image_url"):
                            o["image_url"] = real_image

                # Budget enforcement on offers (F2 final design, QA Round 6):
                #  - CEILING is always a hard filter — an over-budget offer must
                #    never appear ("Under $100" → no $159 link).
                #  - FLOOR depends on the budget's shape:
                #      * Floor-only ("$500+", "at least $500") expresses a quality
                #        intent → below-floor offers are dropped (the "$299 pick
                #        on a $500+ ask" bug).
                #      * Range ("$80–$130") expresses a price window → a cheaper
                #        offer is a deal, not a mistake. Keep it and tag it
                #        below_budget_floor so the card renders an honest
                #        "Under budget" badge (user product decision 2026-06-02).
                # If no offer survives the hard filters, keep them all so the user
                # still sees results (degraded beats empty).
                if budget_max is not None or budget_min is not None:
                    floor_is_hard = budget_min is not None and budget_max is None

                    def _within_budget(o):
                        p = _extract_price(o)
                        if p is None:
                            return False
                        if budget_max is not None and p > budget_max:
                            return False
                        if floor_is_hard and p < budget_min:
                            return False
                        return True

                    in_budget = [o for o in all_offers_for_product if _within_budget(o)]
                    if in_budget:
                        removed_count = len(all_offers_for_product) - len(in_budget)
                        if removed_count > 0:
                            bounds = []
                            if floor_is_hard:
                                bounds.append(f"≥${budget_min:.0f}")
                            if budget_max is not None:
                                bounds.append(f"≤${budget_max:.0f}")
                            logger.info(f"[product_compose] Budget filter ({' and '.join(bounds)}): removed {removed_count} out-of-budget offer(s) for {product_name}")
                        all_offers_for_product = in_budget

                    # Tag below-floor survivors (range budgets only) for the card badge.
                    if budget_min is not None and not floor_is_hard:
                        for o in all_offers_for_product:
                            _p = _extract_price(o)
                            if _p is not None and _p < budget_min:
                                o["below_budget_floor"] = True

                # Best offer = first with a real price, or just first
                priced = [o for o in all_offers_for_product if o.get("price", 0) > 0]
                product_copy["best_offer"] = priced[0] if priced else all_offers_for_product[0]
                product_copy["all_offers"] = all_offers_for_product

            products_with_offers.append(product_copy)

        # Product-level budget honesty: a product whose offers are ALL out of budget
        # survived the offer filter via its keep-all fallback — but it must not
        # headline the shortlist (the "$299 top pick on a $500+ ask" bug). Prune such
        # products, but only while ≥2 in-budget products remain, so sparse results
        # degrade to "show something" rather than nothing.
        _budget_pruned_names: set = set()
        if (budget_min is not None or budget_max is not None) and products_with_offers:
            def _product_in_budget(p):
                best = p.get("best_offer")
                if not best:
                    return True  # no offers → no price signal → keep
                price = _extract_price(best)
                if price is None:
                    return True
                if budget_max is not None and price > budget_max:
                    return False
                # The floor only prunes on floor-only budgets ("$500+" = quality
                # intent). On a range ("$80–$130") a cheaper product is a deal and
                # stays — its offers carry the below_budget_floor badge instead (F2).
                if budget_min is not None and budget_max is None and price < budget_min:
                    return False
                return True

            in_budget_products = [p for p in products_with_offers if _product_in_budget(p)]
            if len(in_budget_products) >= 2 and len(in_budget_products) < len(products_with_offers):
                dropped_names = [p.get("name") for p in products_with_offers if p not in in_budget_products]
                logger.info(f"[product_compose] Budget filter dropped {len(dropped_names)} out-of-budget product(s): {dropped_names}")
                products_with_offers = in_budget_products
                # Remember what was pruned so the blog-data loops below (review bundles +
                # affiliate-only products) don't reintroduce these as prose mentions or
                # fallback cards — that's how the "$299 pick on a $500+ ask" leaked.
                _budget_pruned_names.update(n for n in dropped_names if n)

        # Tier 5 / A2 anti-hallucination: drop products that the LLM search may have
        # invented — those with NEITHER a real shopping match (a priced offer with a
        # non-placeholder image) NOR real review evidence. Without this, gpt-4o-mini's
        # guessed product names reach the composer and it writes confident prose about
        # products that don't exist. Keep ≥2 verified products so sparse-but-real
        # results still render (degrade beats empty). Reuses the suppression set so
        # dropped names can't sneak back in via prose mentions or fallback cards.
        if settings.USE_PRODUCT_VERIFICATION and len(products_with_offers) > 2:
            def _has_real_shopping(p):
                for o in p.get("all_offers", []):
                    if _extract_price(o) is not None and "placehold.co" not in (o.get("image_url") or ""):
                        return True
                return False

            def _has_review_evidence(p):
                name = p.get("name", "")
                for rname, bundle in review_data.items():
                    if _fuzzy_product_match(name, rname) and (bundle or {}).get("sources"):
                        return True
                return False

            verified = [
                p for p in products_with_offers
                if _has_real_shopping(p) or _has_review_evidence(p)
            ]
            if len(verified) >= 2 and len(verified) < len(products_with_offers):
                dropped_names = [p.get("name") for p in products_with_offers if p not in verified]
                logger.info(
                    f"[product_compose] A2 verification dropped {len(dropped_names)} unverifiable "
                    f"product(s) (no shopping match, no reviews): {dropped_names}"
                )
                products_with_offers = verified
                _budget_pruned_names.update(n for n in dropped_names if n)

        # Assign editorial labels based on review quality + price
        editorial_labels = _assign_editorial_labels(review_data, products_with_offers)
        if editorial_labels:
            logger.info(f"[product_compose] Editorial labels: {editorial_labels}")

        # ── Phase 1: Build products_by_provider (pure data, needed by LLM prompts) ──

        sorted_providers = sorted(
            affiliate_products.keys(),
            key=lambda p: PROVIDER_CONFIG.get(p, {}).get("order", 999)
        )

        all_products_for_desc = []
        products_by_provider = {}

        for provider_name in sorted_providers:
            provider_data = affiliate_products.get(provider_name, [])
            if not provider_data:
                continue

            config = PROVIDER_CONFIG.get(provider_name, {
                "title": f"Shop on {provider_name.title()}",
                "type": f"{provider_name}_products",
                "order": 999
            })

            provider_products = []
            for affiliate_group in provider_data:
                if affiliate_group.get("offers"):
                    for offer in affiliate_group["offers"][:5]:
                        # Same provider-field sanitization as the card path above:
                        # these items feed the carousel ui_block, the blog data, and
                        # _fuzzy_product_match (string ops) — a dict title/url from a
                        # scraper must degrade to "" rather than crash or leak to the UI.
                        product_item = {
                            "title": _str_or(offer.get("title"), ""),
                            "price": offer.get("price", 0),
                            "currency": _str_or(offer.get("currency"), "USD"),
                            "url": _str_or(offer.get("url"), ""),
                            "image_url": _str_or(offer.get("image_url"), ""),
                            "merchant": _str_or(offer.get("merchant"), provider_name.title()),
                            "rating": offer.get("rating"),
                            "review_count": offer.get("review_count"),
                            "source": provider_name
                        }
                        if offer.get("product_id"):
                            product_item["product_id"] = offer["product_id"]
                        provider_products.append(product_item)
                        all_products_for_desc.append(product_item)

            if provider_products:
                products_by_provider[provider_name] = {
                    "config": config,
                    "products": provider_products[:5]
                }

        num_products = sum(len(d["products"]) for d in products_by_provider.values())
        num_providers = len(products_by_provider)

        # ── Phase 2: Prepare all LLM coroutines (fired in parallel) ──

        llm_tasks = {}  # key -> coroutine

        # --- Assistant text: concierge OR opener (mutually exclusive with review consensus) ---
        assistant_text = ""
        if comparison_html:
            comp_product_names = comparison_data.get("products", []) if comparison_data else []
            assistant_text = f"## Product Comparison: {', '.join(comp_product_names)}\n\nHere's a detailed specification comparison."
        elif not review_data:
            # Concierge-style summary
            provider_names = [p.title() for p in affiliate_products.keys()]
            conversation_history = state.get("conversation_history", [])
            context_summary = ""
            if conversation_history:
                recent = conversation_history[-4:]
                context_summary = "\n".join([
                    f"{msg.get('role', 'user')}: {msg.get('content', '')[:150]}"
                    for msg in recent if msg.get('content')
                ])
            product_name_list = [p.get("name", "") for p in normalized_products[:5] if p.get("name")]
            user_prefs = (state.get("metadata") or {}).get("user_preferences", {})
            pref_note = ""
            if user_prefs.get("brands") or user_prefs.get("categories"):
                past_cats = list(user_prefs.get("categories", {}).keys())[:2]
                past_brands = list(user_prefs.get("brands", {}).keys())[:2]
                parts = []
                if past_cats:
                    parts.append(f"often searches for {', '.join(past_cats)}")
                if past_brands:
                    parts.append(f"favors {', '.join(past_brands)}")
                pref_note = f"\nReturning user who {' and '.join(parts)}."

            concierge_role = (
                "Write 2-3 SHORT sentences (max 60 words) explaining WHY these "
                "products match the user's needs. Reference their criteria from "
                "the conversation (budget, features, use case). Do NOT list "
                "products — they are shown in cards below. Do NOT describe your "
                "process or mention how many sources you searched."
            )
            llm_tasks['concierge'] = model_service.generate_compose(
                messages=[
                    {"role": "system", "content": build_system_prompt(role_prompt=concierge_role, kind="snippet")},
                    {"role": "user", "content": f'User asked: "{user_message}"\nContext:\n{context_summary}{pref_note}\nProducts: {", ".join(product_name_list)}\nSources: {", ".join(provider_names)}'}
                ],
                temperature=0.7,
                max_tokens=120,
                agent_name="product_compose"
            )

        # --- Review consensus (one per product) + opener ---
        # Cap LLM consensus to top 3 products by quality_score to reduce fanout latency
        MAX_CONSENSUS_PRODUCTS = 3
        _template_consensus = {}  # Pre-computed consensus for lower-ranked products
        review_bundles = {}  # product_name -> bundle (for assembly later)
        if review_data:
            # Separate products with sources from those without
            products_with_sources = [
                (name, bundle) for name, bundle in review_data.items()
                if bundle.get("sources")
            ]
            # Sort by quality_score descending
            products_with_sources.sort(
                key=lambda kv: kv[1].get("quality_score", 0),
                reverse=True
            )
            top_products = products_with_sources[:MAX_CONSENSUS_PRODUCTS]
            remaining_products = products_with_sources[MAX_CONSENSUS_PRODUCTS:]

            # Full LLM consensus for top products
            for product_name, bundle in top_products:
                review_bundles[product_name] = bundle
                # Strip site_name from each snippet — the LLM must never see
                # named source attributions ("Wirecutter:", "RTINGS:") because
                # VOICE_PROMPT forbids citing competitors but the model treats
                # whatever names appear in its user message as canonical
                # citation material and weaves them into the output. The
                # review_sources UI block at line ~1268 still surfaces source
                # names to the USER for explainability. See voice-hotfix PR.
                source_snippets = "\n".join([
                    f"- {s.get('snippet', '')}"
                    for s in bundle.get("sources", [])[:5]
                    if s.get('snippet')
                ])
                consensus_role = (
                    "Write a 3-5 sentence summary that covers: (1) what reviewers "
                    "consistently praise, (2) any notable criticisms or caveats, "
                    "and (3) who this product is best suited for. End with a "
                    "sentence describing the ideal buyer. Do NOT describe your "
                    "process or mention how many sources you searched."
                )
                llm_tasks[f'consensus:{product_name}'] = model_service.generate_compose(
                    messages=[
                        {"role": "system", "content": build_system_prompt(role_prompt=consensus_role, kind="snippet")},
                        {"role": "user", "content": f"Product: {product_name}\nAvg Rating: {bundle.get('avg_rating', 0)}/5 from {bundle.get('total_reviews', 0)} reviews\n\nReview excerpts:\n{source_snippets}\n\nWrite a 3-5 sentence editorial summary covering: strengths, criticisms, and ideal buyer."}
                    ],
                    temperature=0.5,
                    max_tokens=220,
                    agent_name="review_consensus"
                )

            # Deterministic template for remaining products (no LLM call)
            # These get injected into result_map after the asyncio.gather below
            # NOTE: no source names here — tone.md "No source citations. Synthesize."
            _template_consensus = {}
            for product_name, bundle in remaining_products:
                review_bundles[product_name] = bundle
                rating = bundle.get("avg_rating", "N/A")
                total = bundle.get("total_reviews", 0)
                _template_consensus[f'consensus:{product_name}'] = (
                    f"Rated {rating}/5 across {total} reviews. "
                    f"Reviewers consider it a solid option in its category — "
                    f"a dependable pick if the top choices don't fit your needs."
                )

            # REMOVED (v3): opener LLM call — blog_article already provides intro
            # Saves ~1-2s per query. Fallback template will work without it.

        # --- Personalized product descriptions ---
        if all_products_for_desc:
            # Cap at 8: measured on Haiku via OpenRouter, the descriptions JSON
            # parses reliably at <=8 products (8/8 at 1200 tok); 10-15 return
            # malformed/truncated JSON regardless of token budget. Carousels
            # typically show <=7, so this fully covers the common case.
            products_to_describe = all_products_for_desc[:8]
            product_titles = [p["title"][:50] for p in products_to_describe]
            conversation_history = state.get("conversation_history", [])
            desc_context = ""
            if conversation_history:
                recent_messages = conversation_history[-6:]
                desc_context = "\n".join([
                    f"{msg.get('role', 'user')}: {msg.get('content', '')[:100]}"
                    for msg in recent_messages if msg.get('content')
                ])

            desc_system = """Generate factual 15-25 word descriptions for each product.

RULES:
1. Focus on what makes each product stand out — key features, best use case, who it's ideal for
2. ONLY reference personal details (names, pets, family) if they appear in the conversation context. NEVER invent or assume personal details.
3. If no personal context exists, write objectively about the product's strengths
4. Vary your descriptions — don't repeat the same pattern
5. Return descriptions in the EXACT same order as the products listed

Return JSON: {"descriptions": {"Product Title 1": "desc1", "Product Title 2": "desc2", ...}}"""

            desc_user = f'''Conversation context:
{desc_context if desc_context else "No prior context"}

User's current question: "{user_message}"

Products to describe:
{json.dumps(product_titles)}'''

            llm_tasks['descriptions'] = model_service.generate_compose(
                messages=[
                    {"role": "system", "content": build_system_prompt(role_prompt=desc_system, kind="snippet")},
                    {"role": "user", "content": desc_user}
                ],
                temperature=0.7,
                # Was 600: Haiku truncated the multi-product JSON mid-stream in prod
                # and the parse failed, dropping card descriptions. 1200 fits the
                # 8-product cap above with headroom (measured 8/8 on Haiku).
                max_tokens=1200,
                response_format={"type": "json_object"},
                agent_name="product_compose_descriptions"
            )

        # REMOVED (v3): conclusion LLM call — blog_article already provides conclusion
        # Saves ~1-2s per query. Fallback template will work without it.

        # --- Blog article composition ---
        # Gather all data the blog writer needs
        blog_data_parts = []
        blog_data_parts.append(f"User asked: \"{user_message}\"")
        blog_product_names = []  # Track which products are in the blog (for price comparison filtering)

        # Products with reviews (use fuzzy matching for offer lookup)
        if review_bundles:
            for pname, bundle in review_bundles.items():
                # Skip accessory products from the blog data (unless user is asking for accessories)
                if not any(kw in user_message_lower for kw in ACCESSORY_KEYWORDS):
                    if any(kw in pname.lower() for kw in ACCESSORY_KEYWORDS):
                        logger.info(f"[product_compose] Suppressed accessory from blog: {pname}")
                        continue
                # Skip products the budget filter pruned — they must not re-enter via reviews
                if _budget_pruned_names and any(
                    _fuzzy_product_match(pname, dropped) for dropped in _budget_pruned_names
                ):
                    logger.info(f"[product_compose] Suppressed budget-pruned product from blog: {pname}")
                    continue
                label_str = f" ({editorial_labels[pname]})" if pname in editorial_labels else ""
                rating = bundle.get("avg_rating", 0)
                total = bundle.get("total_reviews", 0)
                # Find price/merchant using fuzzy match (not exact) to handle name variations
                p_offer = next(
                    (p for p in products_with_offers
                     if _fuzzy_product_match(p.get("name", ""), pname) and p.get("best_offer")),
                    None
                )
                # Collect buy links from ALL providers for this product
                buy_links_str = ""
                image_str = ""
                if p_offer:
                    all_offers = p_offer.get("all_offers", [])
                    if not all_offers and p_offer.get("best_offer"):
                        all_offers = [p_offer["best_offer"]]
                    link_parts = []
                    for o in all_offers:
                        price = o.get("price", 0)
                        merchant = o.get("merchant", "")
                        url = o.get("url", "")
                        if url:
                            if price > 0:
                                link_parts.append(f"${price:.2f} on {merchant}: {url}")
                            else:
                                link_parts.append(f"{merchant}: {url}")
                        if not image_str and o.get("image_url"):
                            image_str = o["image_url"]
                    if link_parts:
                        buy_links_str = " | Buy: " + " ; ".join(link_parts)

                # Build review excerpts WITHOUT named source attribution.
                # The LLM must never see "[Wirecutter](url)" or "RTINGS:"
                # because VOICE_PROMPT forbids citing competitors but the
                # model uses whatever names appear in its user message as
                # citation material. Sources are still rendered in the
                # review_sources UI block (line ~1268) for user-facing
                # explainability — they just don't reach the LLM. See
                # voice-hotfix PR.
                review_excerpts = ""
                sources = bundle.get("sources", [])
                if sources:
                    top_sources = sources[:3]
                    excerpt_parts = [
                        f"  - {s.get('snippet', '')[:120]}"
                        for s in top_sources
                        if s.get("snippet")
                    ]
                    if excerpt_parts:
                        review_excerpts = "\n" + "\n".join(excerpt_parts)

                blog_data_parts.append(f"Product: {pname}{label_str} | Rating: {rating}/5 ({total} reviews){buy_links_str} | Image: {image_str}{review_excerpts}")
                blog_product_names.append(pname)

        # Also add affiliate-only products NOT already covered by review_bundles
        # Group by product title across providers so each product gets all buy links
        if products_by_provider:
            seen_titles = set()
            for prov, data in products_by_provider.items():
                for prod in data["products"][:5]:
                    t = prod.get("title", "")
                    # Skip if already covered by a review_bundle product (fuzzy match)
                    already_covered = any(
                        _fuzzy_product_match(t, bname, threshold=0.5)
                        for bname in blog_product_names
                    )
                    if already_covered or t in seen_titles:
                        continue
                    # Budget honesty: affiliate-only products bypass products_with_offers,
                    # so apply the same budget bounds here — otherwise an out-of-budget
                    # item re-enters the blog prose and comes back as a fallback card.
                    _prod_price = prod.get("price", 0) or 0
                    if _prod_price > 0:
                        if budget_max is not None and _prod_price > budget_max:
                            continue
                        # Floor is only a hard filter on floor-only budgets (F2):
                        # on a range, cheaper products are deals and stay.
                        if budget_min is not None and budget_max is None and _prod_price < budget_min:
                            continue
                    if _budget_pruned_names and any(
                        _fuzzy_product_match(t, dropped) for dropped in _budget_pruned_names
                    ):
                        continue
                    seen_titles.add(t)
                    # Gather links from ALL providers for this product
                    link_parts = []
                    img = ""
                    for p2, d2 in products_by_provider.items():
                        for pr2 in d2["products"]:
                            if _fuzzy_product_match(t, pr2.get("title", ""), threshold=0.5):
                                price = pr2.get("price", 0)
                                merchant = pr2.get("merchant", p2.title())
                                url = pr2.get("url", "")
                                if url:
                                    if price > 0:
                                        link_parts.append(f"${price:.2f} on {merchant}: {url}")
                                    else:
                                        link_parts.append(f"{merchant}: {url}")
                                if not img and pr2.get("image_url"):
                                    img = pr2["image_url"]
                                break
                    buy_str = " | Buy: " + " ; ".join(link_parts) if link_parts else ""
                    r = prod.get("rating", "")
                    blog_data_parts.append(f"Product: {t} | Rating: {r}/5{buy_str} | Image: {img}")
                    blog_product_names.append(t)

        blog_data = "\n".join(blog_data_parts)

        blog_role = """Write a buying guide for ReviewGuide.ai.

OUTPUT FORMAT — return a JSON object with these string fields:
{
  "body": "<3-5 paragraphs of markdown, no per-product headings>",
  "follow_up_question": "<exactly one contextual curious question that references something specific from the body — a product name, a tradeoff just mentioned, or the user's stated situation>",
  "transitional_reasoning": "<OPTIONAL — exactly one short sentence, OR an empty string. See TRANSITIONAL RULES.>"
}

RANK AND COMMIT (load-bearing — read first):

You are an editor with a take, not a balanced surveyor. Every buying guide
has a #1 pick and a #2 pick. Name them, in order, and explain WHY one beats
the other for the default buyer in this category. The runner-up isn't "also
great" — it is the right pick for a specific person whose situation differs
from the default.

DO NOT write parallel descriptions where every product gets one paragraph of
praise. That reads like SEO content, not editor judgment.

  BAD (parallel survey — do not write like this):
    "The Anker Soundcore Life P3 is praised for its active noise cancellation
    and customizable sound. The JBL TUNE 125TWS is noted for its deep bass
    and user-friendly controls. Both are solid options under $100."

  GOOD (ranked, with fit-based reasoning):
    "For most people under $100, the Anker Soundcore Life P3 is the pick —
    the ANC actually works on a subway, and the case is small enough to
    pocket. The JBL TUNE 125TWS edges it out only if you want louder bass
    and don't care about noise cancellation. Skip the rest at this price."

BODY RULES:
- Paragraph 1: what the user is looking for and what matters most in this category
- Paragraphs 2-3: name the #1 pick first with WHY, then the #2 pick with WHO IT FITS — speak in your own voice, do not name-check review outlets or "reviewers" as a group
- Paragraph 4: what to skip and why, or one real tradeoff worth knowing about the top pick
- Final paragraph: short verdict — who should buy the #1, who should buy the #2
- DO NOT write per-product ## headings — products render as interactive cards below your text
- DO NOT include product images, prices, or buy links — they render in the cards
- NEVER invent features, specs, or URLs
- NEVER mention personal details unless the user provided them
- Keep the body under 400 words total

FOLLOW-UP RULES:
- Exactly one question, returned in the follow_up_question field
- Must reference something specific from the body (a product, a tradeoff, the user's situation)
- Must NOT be a generic offer ("Anything else?", "Want to dig deeper?", "How can I help?")
- Must NOT be a bulleted list of multiple questions — just one single question

TRANSITIONAL RULES (transitional_reasoning field):
- This is a single, compressed-consensus sentence shown BEFORE the guide as a brief
  aside that frames HOW the user's key constraint shapes the pick. Emit it whenever the
  conversation carries a meaningful constraint — a budget, a use case, a must-have, or a
  deal-breaker — that drives which products lead the ranking. This INCLUDES the first
  turn when the query itself names such a constraint (e.g. "under $100", "for small
  ears", "best for travel", "quiet for an office").
- ALSO emit it when the user's latest message added or changed a constraint that flips
  the ranking from a prior shortlist.
- Voice (one sentence, no preamble, no generic filler):
    "$X puts the [tier] on the table — that changes the pick for [situation]."
    "Once comfort matters more than ANC, the order flips."
    "Under $100, value beats flagship features, so the pick leans practical."
- Return an EMPTY STRING "" ONLY when there is no real constraint to frame: bare
  greetings, intros, or vague "what's good?" queries with no budget / use case /
  must-have. When the query carries a genuine constraint, prefer to frame it rather
  than skip it.
- Never restate the question back; never list options; never exceed one sentence."""

        # Tier 5c two-speed routing: vary blog depth by query complexity. The
        # classifier is a <5ms pure heuristic, so we re-derive it here rather than
        # threading complexity through the GraphState passthrough. Utility queries
        # get terser/faster/cheaper prose; considered purchases get room for the
        # tradeoffs that matter; recommendations keep the 400-word default. The
        # length directive is appended to the role prompt at the CALL SITE only —
        # the blog_role string itself is unchanged (the eval prod-sync test pins it).
        blog_role_effective = blog_role
        blog_max_tokens = 700
        if getattr(settings, "USE_TWO_SPEED_COMPOSE", False):
            from app.agents.query_complexity import classify_query_complexity
            _complexity, _ = classify_query_complexity(user_message, state.get("slots") or {}, "product")
            if _complexity in ("factoid", "comparison"):
                blog_role_effective = blog_role + (
                    "\n\nLENGTH OVERRIDE: This is a quick query — keep the body to about "
                    "250 words, tighter than the 400-word default."
                )
                blog_max_tokens = 550
            elif _complexity == "deep_research":
                blog_role_effective = blog_role + (
                    "\n\nLENGTH OVERRIDE: This is a considered, high-involvement purchase — "
                    "you may run longer than the 400-word default, up to about 550 words, "
                    "to cover the tradeoffs that matter."
                )
                blog_max_tokens = 1000
            logger.info(f"[product_compose] Two-speed: complexity={_complexity}, blog_max_tokens={blog_max_tokens}")

        if getattr(settings, "USE_GROUNDED_COMPOSE", False):
            # Tier 2.2/2.3: product facts → RESEARCH slot, conversation → history
            # slot, accumulated prefs → profile slot; the user message is just the
            # query. The model reads labelled research + who-the-user-is instead of
            # parsing one undifferentiated string with no memory.
            blog_messages = [
                {"role": "system", "content": build_system_prompt(
                    role_prompt=blog_role_effective,
                    kind="response",
                    profile_inject=_profile_inject((state.get("metadata") or {}).get("user_preferences")),
                    history=_format_history(state.get("conversation_history")),
                    tool_outputs=blog_data,
                )},
                {"role": "user", "content": f'User asked: "{user_message}"'},
            ]
        else:
            blog_messages = [
                {"role": "system", "content": build_system_prompt(role_prompt=blog_role_effective, kind="response")},
                {"role": "user", "content": blog_data},
            ]
        llm_tasks['blog_article'] = model_service.generate_compose(
            messages=blog_messages,
            temperature=0.7,
            max_tokens=blog_max_tokens,
            response_format={"type": "json_object"},
            agent_name="blog_article_composer"
        )

        # --- Top Pick editorial prose (UX-03) ---
        # Uses deterministic "Best Overall" selection + LLM for prose
        if review_data and review_bundles:
            sorted_by_quality = sorted(
                review_data.items(),
                key=lambda x: x[1].get("quality_score", 0),
                reverse=True
            )
            if sorted_by_quality and sorted_by_quality[0][1].get("quality_score", 0) > 0:
                best_product_name = sorted_by_quality[0][0]
                best_bundle = sorted_by_quality[0][1]
                top_pick_role = (
                    "Given a top-rated product, write a JSON object with exactly "
                    "three keys: headline (one sentence why it's the best pick), "
                    "best_for (who should buy it, one sentence), not_for (who "
                    "should look elsewhere, one sentence). Be specific and "
                    "opinionated. Do not use generic phrases."
                )
                llm_tasks['top_pick'] = model_service.generate_compose(
                    messages=[
                        {"role": "system", "content": build_system_prompt(role_prompt=top_pick_role, kind="snippet")},
                        {"role": "user", "content": f'Product: {best_product_name}\nRating: {best_bundle.get("avg_rating", 0)}/5 from {best_bundle.get("total_reviews", 0)} reviews\nUser asked: "{user_message}"'}
                    ],
                    temperature=0.5,
                    max_tokens=150,
                    response_format={"type": "json_object"},
                    agent_name="top_pick_composer"
                )

        # ── Phase 3: Fire all LLM calls in parallel ──

        task_keys = list(llm_tasks.keys())
        if task_keys:
            results = await asyncio.gather(*llm_tasks.values(), return_exceptions=True)
            result_map = dict(zip(task_keys, results))
            logger.info(f"[product_compose] Parallel LLM batch: {len(task_keys)} calls ({', '.join(task_keys)})")
        else:
            result_map = {}

        # Inject pre-computed template consensus for lower-ranked products
        if _template_consensus:
            result_map.update(_template_consensus)

        # Helper to safely extract a string result
        def _get_result(key: str, fallback: str = "") -> str:
            val = result_map.get(key)
            if val is None or isinstance(val, Exception):
                if isinstance(val, Exception):
                    logger.warning(f"[product_compose] LLM call '{key}' failed: {val}")
                return fallback
            if not isinstance(val, str):
                logger.warning(f"[product_compose] LLM call '{key}' returned non-string: {type(val)}")
                return fallback
            return val.strip()

        # ── Phase 4: Assemble blog-style article ──

        ui_blocks = []

        # ── Top Pick block (UX-03) — must be FIRST in ui_blocks ──
        if 'top_pick' in result_map:
            top_pick_raw = _get_result('top_pick', '')
            if top_pick_raw:
                try:
                    top_pick_result = json.loads(top_pick_raw)
                    # Find the best product name (same selection as Phase 2)
                    sorted_by_quality = sorted(
                        review_data.items(),
                        key=lambda x: x[1].get("quality_score", 0),
                        reverse=True
                    )
                    best_product_name = sorted_by_quality[0][0] if sorted_by_quality else ""
                    # Find image and affiliate URL from products_with_offers
                    # Prefer Amazon offer for the buy button; fall back to best_offer
                    best_image = ""
                    best_url = ""
                    for p in products_with_offers:
                        if _fuzzy_product_match(p.get("name", ""), best_product_name):
                            all_p_offers = p.get("all_offers", [])
                            # Pick Amazon offer first (don't send users to eBay with "Buy on Amazon")
                            amazon_offer = next(
                                (o for o in all_p_offers if "amazon" in o.get("url", "").lower() or "amzn.to" in o.get("url", "").lower()),
                                None
                            )
                            if amazon_offer:
                                best_url = amazon_offer.get("url", "")
                                best_image = amazon_offer.get("image_url", "")
                            else:
                                offer = p.get("best_offer", {})
                                best_url = offer.get("url", "")
                                best_image = offer.get("image_url", "")
                            # If Amazon offer had no image, grab from any offer that has one
                            if not best_image:
                                for o in all_p_offers:
                                    if o.get("image_url"):
                                        best_image = o["image_url"]
                                        break
                            break
                    ui_blocks.insert(0, {
                        "type": "top_pick",
                        "title": "Our Top Pick",
                        "data": {
                            "product_name": best_product_name,
                            "headline": top_pick_result.get("headline", ""),
                            "best_for": top_pick_result.get("best_for", ""),
                            "not_for": top_pick_result.get("not_for", ""),
                            "image_url": best_image,
                            "affiliate_url": best_url,
                        }
                    })
                    logger.info(f"[product_compose] Added top_pick block for {best_product_name}")
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"[product_compose] Failed to parse top_pick: {e}")

        # ── Review consensus comparison block ──
        # One card per product: aggregated rating + review count + synthesized
        # consensus prose, ranked by quality_score, so users can compare the
        # shortlist at a glance. No source names surface (tone.md: "No source
        # citations. Synthesize."). Replaces the HTML comparison table whenever
        # real review data exists; the table remains as a fallback for queries
        # where review search returned nothing (e.g. providers out of credits).
        #
        # QA Round 5 (external bug 6): the consensus block must compare the SAME
        # products the user can actually buy below it. Review bundles can contain
        # products that never became cards (reviewed but no purchasable offer) or
        # that the budget filter pruned (a $600 espresso machine on an "Under $100"
        # ask). Ranking those #1 makes the response contradict its own cards.
        def _eligible_for_consensus(pname: str) -> bool:
            # Budget-pruned products must not re-enter via the consensus block
            if _budget_pruned_names and any(
                _fuzzy_product_match(pname, dropped) for dropped in _budget_pruned_names
            ):
                logger.info(
                    f"[product_compose] Suppressed budget-pruned product from consensus: {pname}"
                )
                return False
            # Only products with a real purchasable offer (i.e. products that get a card)
            has_offer = any(
                _fuzzy_product_match(p.get("name", ""), pname) and p.get("all_offers")
                for p in products_with_offers
            )
            if not has_offer:
                logger.info(
                    f"[product_compose] Suppressed offerless product from consensus: {pname}"
                )
            return has_offer

        consensus_products = []
        if review_bundles:
            ranked_bundles = sorted(
                review_bundles.items(),
                key=lambda kv: kv[1].get("quality_score", 0),
                reverse=True,
            )
            rank = 0
            for pname, bundle in ranked_bundles:
                consensus_text = _get_result(f'consensus:{pname}', '')
                if not consensus_text:
                    continue
                if not _eligible_for_consensus(pname):
                    continue
                rank += 1  # rank AFTER filtering so the list stays 1..N with no gaps
                consensus_products.append({
                    "name": pname,
                    "avg_rating": float(bundle.get("avg_rating") or 0),
                    "total_reviews": int(bundle.get("total_reviews") or 0),
                    "consensus": consensus_text,
                    "rank": rank,
                })

        if consensus_products:
            ui_blocks.append({
                "type": "review_consensus",
                "title": "How They Compare",
                "data": {"products": consensus_products},
            })
            logger.info(
                f"[product_compose] Added review_consensus block ({len(consensus_products)} products)"
            )
        elif comparison_html:
            # Fallback: old HTML comparison table (no review data this query)
            ui_blocks.append({
                "type": "comparison_html",
                "title": "Product Comparison",
                "data": {
                    "html": comparison_html,
                    "products": comparison_data.get("products", []) if comparison_data else []
                }
            })
            logger.info(f"[product_compose] Added comparison HTML block ({len(comparison_html)} chars)")

        # Apply descriptions to products — match by title (not index) to avoid mismatch
        if 'descriptions' in result_map:
            desc_raw = _get_result('descriptions')
            if desc_raw:
                try:
                    desc_data = json.loads(desc_raw)
                    descriptions = desc_data.get("descriptions", {})
                    matched = 0
                    if isinstance(descriptions, dict):
                        # Title-keyed dict: {"Product Title": "description"}
                        for product in all_products_for_desc:
                            title = product.get("title", "")
                            # Try exact match first, then fuzzy
                            desc = descriptions.get(title) or descriptions.get(title[:50])
                            if not desc:
                                for key, val in descriptions.items():
                                    if _fuzzy_product_match(title, key, threshold=0.4):
                                        desc = val
                                        break
                            if desc:
                                product["description"] = desc
                                matched += 1
                    elif isinstance(descriptions, list):
                        # Fallback: array of descriptions (old format)
                        for i, desc in enumerate(descriptions):
                            if i < len(all_products_for_desc):
                                all_products_for_desc[i]["description"] = desc
                                matched += 1
                    logger.info(f"[product_compose] Applied {matched} product descriptions")
                except (json.JSONDecodeError, Exception) as desc_error:
                    logger.warning(f"[product_compose] Failed to parse descriptions: {desc_error}")

        # ── Build unified product_review cards (one per product, multi-retailer) ──
        # Only include products that have offers from 2+ providers (e.g., both Amazon + eBay)
        # Skip products with placeholder/mock images or hallucinated data

        review_card_count = 0
        seen_card_names = set()

        for idx, product in enumerate(products_with_offers, 1):
            if review_card_count >= 5:
                break
            pname = product.get("name", "")
            all_offers = product.get("all_offers", [])
            if not all_offers:
                continue

            # Filter out offers with placeholder images (mock Amazon data)
            real_offers = [
                o for o in all_offers
                if o.get("url") and "placehold.co" not in o.get("image_url", "")
            ]

            # Require at least 1 real offer with a valid URL (relaxed from 2-provider gate)
            # Provider set is still computed for ranking/deduplication purposes
            providers_in_offers = set(o.get("source", "") for o in real_offers)
            if not real_offers:
                continue

            if pname in seen_card_names:
                continue
            seen_card_names.add(pname)

            # Build affiliate_links array for the card
            # Image priority: Serper/Google > Amazon > eBay (Google images are cleanest)
            # Offer priority: Amazon first, then one eBay, then other retailers
            def _offer_sort_key(o):
                src = o.get("source", "").lower()
                url = o.get("url", "").lower()
                if "amazon" in url or "amzn.to" in url or src == "amazon":
                    return (0, not o.get("image_url"))
                if src == "serper_shopping":
                    return (1, not o.get("image_url"))
                if src == "ebay":
                    return (2, not o.get("image_url"))
                return (3, not o.get("image_url"))

            # Offers eligible to become CLICKABLE buy-links. Exclude Google Shopping
            # (serper_shopping): we only earn on our Amazon affiliate links, so Shopping
            # data is used for price/image/rating CONTEXT only (it still backfills the
            # Amazon offer's price and supplies the card image above) — never as a buy
            # destination to a merchant we aren't an affiliate of.
            link_offers = [
                o for o in real_offers if o.get("source", "").lower() != "serper_shopping"
            ]
            # F1 (QA Round 5): every card must carry a monetizable AMAZON link.
            # eBay links are unmonetized until a real EPN campaign id is set, and
            # Google Shopping is context-only — so a card whose only clickable links
            # are eBay earns nothing (observed: 4 of 5 running-shoe cards, incl. the
            # top pick). Whenever the product has no real Amazon offer, add the
            # tagged Amazon SEARCH url alongside whatever marketplace offers exist.
            # This subsumes the old "Shopping was the only source" fallback (empty
            # link_offers → also no Amazon offer → fallback fires).
            has_amazon_offer = any(
                "amazon" in o.get("url", "").lower()
                or "amzn.to" in o.get("url", "").lower()
                or o.get("source", "").lower() == "amazon"
                for o in link_offers
            )
            if not has_amazon_offer:
                # Price/image context comes from Google Shopping when available (real
                # market data); otherwise price 0 → the card renders "Check price →"
                # rather than borrowing another merchant's price for an Amazon label.
                shop = next(
                    (o for o in real_offers if o.get("source", "").lower() == "serper_shopping"),
                    {},
                )
                link_offers = link_offers + [{
                    "source": "amazon",
                    "merchant": "Amazon",
                    "url": f"https://www.amazon.com/s?k={quote_plus(pname)}&tag=revguide-20",
                    "price": shop.get("price", 0),
                    "currency": shop.get("currency", "USD"),
                    "image_url": shop.get("image_url", ""),
                    "rating": shop.get("rating"),
                    "review_count": shop.get("review_count"),
                }]

            sorted_offers = sorted(link_offers, key=_offer_sort_key)

            # Dedupe by merchant — keep only 1 offer per merchant (e.g., one eBay, one Amazon)
            seen_merchants = set()
            deduped_offers = []
            for o in sorted_offers:
                merchant_key = o.get("source", "").lower()
                if merchant_key == "ebay":
                    merchant_key = "ebay"  # collapse all eBay sellers
                elif "amazon" in o.get("url", "").lower():
                    merchant_key = "amazon"
                else:
                    merchant_key = o.get("merchant", "").lower()
                if merchant_key in seen_merchants:
                    continue
                seen_merchants.add(merchant_key)
                deduped_offers.append(o)

            # Cap at 3 offers per product card
            capped_offers = deduped_offers[:3]

            affiliate_links = []
            best_image = ""

            # Pick best image separately — prefer Serper > Amazon > eBay
            def _image_priority(o):
                src = o.get("source", "").lower()
                if src == "serper_shopping":
                    return 0
                if "amazon" in o.get("url", "").lower() or src == "amazon":
                    return 1
                return 2

            for o in sorted(real_offers, key=_image_priority):
                img = o.get("image_url", "")
                if img and "placehold" not in img:
                    best_image = img
                    break

            for o in capped_offers:
                img = o.get("image_url", "")
                offer_url = o.get("url", "")
                offer_merchant = o.get("merchant", "")
                # Label-domain parity: correct merchant label if it doesn't match the URL domain
                derived_merchant = _domain_to_merchant(offer_url)
                if (
                    derived_merchant
                    and offer_merchant.lower() != derived_merchant.lower()
                    and "amazon" in offer_merchant.lower()
                    and "amazon" not in offer_url.lower()
                    and "amzn.to" not in offer_url.lower()
                ):
                    # Mislabeled as Amazon but URL is a different domain — correct the label
                    offer_merchant = derived_merchant
                _link_price = _extract_price(o)
                affiliate_links.append({
                    "product_id": f"{o.get('source', 'unknown')}-{idx}",
                    "title": offer_merchant + " - " + pname,
                    "price": o.get("price", 0),
                    "currency": o.get("currency", "USD"),
                    "affiliate_link": offer_url,
                    "merchant": offer_merchant,
                    "image_url": img,
                    "rating": o.get("rating"),
                    "review_count": o.get("review_count"),
                    # F2 (QA Round 6): on a RANGE budget, offers cheaper than the
                    # stated floor are kept as deals but flagged so the frontend
                    # renders an "Under budget" badge instead of silently showing
                    # a price below what the user asked for. ui_blocks passes
                    # through the validator as List[Any], so no schema change.
                    "below_budget_floor": bool(
                        budget_min is not None and budget_max is not None
                        and _link_price is not None and _link_price < budget_min
                    ),
                })

            if not affiliate_links:
                continue

            # Get review summary for this product
            review_bundle = review_data.get(pname, {})
            consensus = _get_result(f'consensus:{pname}', '')
            avg_rating = review_bundle.get("avg_rating", 0)
            total_reviews = review_bundle.get("total_reviews", 0)
            label = editorial_labels.get(pname, "")

            # Build sources list for citations
            sources = review_bundle.get("sources", [])
            pros = []
            cons = []
            for s in sources[:3]:
                snippet = s.get("snippet", "")
                site = s.get("site_name", "")
                url = s.get("url", "")
                if snippet:
                    pros.append({
                        "description": snippet[:150],
                        "citations": [{"id": 1, "url": url, "title": site}] if url else []
                    })

            card_data = {
                "product_name": pname,
                "image_url": best_image,
                "rating": f"{avg_rating}/5" if avg_rating else "",
                "summary": consensus if consensus else "",
                "features": [label] if label else [],
                "pros": pros,
                "cons": cons,
                "affiliate_links": affiliate_links,
                "rank": idx,
            }

            ui_blocks.append({
                "type": "product_review",
                "data": card_data,
            })
            review_card_count += 1

        logger.info(f"[product_compose] Built {review_card_count} unified product_review cards")

        # ── Fallback cards for blog-mentioned products without product_review blocks ──
        # Every product mentioned in the blog article must have a clickable card
        fallback_card_count = 0
        for pname in blog_product_names:
            if review_card_count + fallback_card_count >= 5:
                break   # cap reached — stop entirely
            if pname in seen_card_names:
                continue   # skip duplicate but keep iterating

            # Build Amazon search URL as fallback affiliate link
            amazon_search_url = f"https://www.amazon.com/s?k={quote_plus(pname)}&tag=revguide-20"

            # Get review data if available
            review_bundle = review_data.get(pname, {})
            consensus = _get_result(f'consensus:{pname}', '')
            avg_rating = review_bundle.get("avg_rating", 0)
            label = editorial_labels.get(pname, "")

            # Try to find image from any source
            fallback_image = ""
            for p in products_with_offers:
                if _fuzzy_product_match(p.get("name", ""), pname):
                    for o in p.get("all_offers", []):
                        if o.get("image_url") and "placehold" not in o.get("image_url", ""):
                            fallback_image = o["image_url"]
                            break
                    break

            fallback_links = [{
                "product_id": f"amazon-search-{fallback_card_count + 1}",
                "title": f"Amazon - {pname}",
                "price": 0,
                "currency": "USD",
                "affiliate_link": amazon_search_url,
                "merchant": "Amazon",
                "image_url": "",
                "rating": None,
                "review_count": None,
            }]

            card_data = {
                "product_name": pname,
                "image_url": fallback_image,
                "rating": f"{avg_rating}/5" if avg_rating else "",
                "summary": consensus if consensus else "",
                "features": [label] if label else [],
                "pros": [],
                "cons": [],
                "affiliate_links": fallback_links,
                "rank": review_card_count + fallback_card_count + 1,
            }

            ui_blocks.append({
                "type": "product_review",
                "data": card_data,
            })
            seen_card_names.add(pname)
            fallback_card_count += 1

        if fallback_card_count > 0:
            logger.info(f"[product_compose] Added {fallback_card_count} fallback product cards with Amazon search links")

        # NOTE: review_sources UI block intentionally removed.
        # tone.md mandates "No source citations. Synthesize." and
        # BACKEND_AGENT_CONTEXT.md done-criterion is "No client-facing
        # citation surface." The block previously rendered TechRadar /
        # The Verge / Wirecutter / RTINGS as user-visible badge pills
        # via SourceCitations.tsx, which directly contradicted both
        # specs. The PR #7 voice hotfix only sanitized assistant_text;
        # this surface bypassed it. Removed entirely along with the
        # frontend renderer. See PR #9.

        # ── Build blog-style assistant_text ──

        blog_article = _get_result('blog_article', '')
        # B.3: keep body and follow_up_question structurally separate so the
        # frontend can render the question distinctly (italic, own line)
        # below the blog body — the spec §11 / §13 #3 visual treatment.
        # chat.py emits the follow-up as a dedicated SSE event after the
        # content stream completes.
        follow_up_text: str = ""
        transitional_text: str = ""
        if blog_article:
            try:
                parsed = json.loads(blog_article)
                body = (parsed.get("body") or "").strip()
                follow_up_text = (parsed.get("follow_up_question") or "").strip()
                # Quiz-path transitional reasoning — emitted only when the latest
                # constraint changed the shortlist (LLM-judged; empty otherwise).
                transitional_text = (parsed.get("transitional_reasoning") or "").strip()
                # E2: the LLM rarely emits this even on clearly-constrained
                # queries. When it skips one but the query carries a budget /
                # use-case that shapes the pick, frame it deterministically.
                if not transitional_text:
                    transitional_text = _synthesize_transitional(user_message, slots)
                assistant_text = body
                logger.info(
                    f"[product_compose] LLM blog article: body={len(body)} chars, "
                    f"follow_up={len(follow_up_text)} chars"
                )
                # Tier 3 (Option B): draft→revise voice pass over the assembled body.
                if getattr(settings, "USE_VOICE_PASS", False) and body:
                    _revised = await _voice_revise_body(body, follow_up_text, transitional_text, user_message)
                    if _revised:
                        body = (_revised.get("body") or body).strip()
                        follow_up_text = (_revised.get("follow_up_question") or follow_up_text).strip()
                        transitional_text = (_revised.get("transitional_reasoning") or transitional_text).strip()
                        assistant_text = body
                        logger.info("[product_compose] Voice pass applied (Tier 3)")
            except (json.JSONDecodeError, TypeError, AttributeError) as e:
                logger.warning(
                    f"[product_compose] Blog JSON parse failed ({e}); "
                    f"using raw text. Raw prefix: {blog_article[:120]!r}"
                )
                assistant_text = blog_article
        elif review_data and review_bundles:
            # Fallback: template assembly (same as current code)
            opener = _get_result('opener', '')
            article_parts = []
            if opener:
                article_parts.append(opener)
            for idx, (product_name, bundle) in enumerate(review_bundles.items(), 1):
                consensus = _get_result(f'consensus:{product_name}', '')
                label = editorial_labels.get(product_name, '')
                heading = f"## {idx}. {product_name}"
                if label:
                    heading += f" — *{label}*"
                article_parts.append(heading)
                if consensus:
                    article_parts.append(consensus)
                product_offer = next(
                    (p for p in products_with_offers
                     if _fuzzy_product_match(p.get("name", ""), product_name) and p.get("best_offer")),
                    None
                )
                if product_offer:
                    all_offers = product_offer.get("all_offers", [])
                    if not all_offers and product_offer.get("best_offer"):
                        all_offers = [product_offer["best_offer"]]
                    for offer in all_offers:
                        price = offer.get("price", 0)
                        merchant = offer.get("merchant", "")
                        url = offer.get("url", "")
                        if url:
                            if price > 0:
                                article_parts.append(f"**${price:.2f}** — [Check price on {merchant} →]({url})")
                            else:
                                article_parts.append(f"[Check price on {merchant} →]({url})")
            conclusion = _get_result('conclusion', '')
            if conclusion:
                article_parts.append("## Our Verdict")
                article_parts.append(conclusion)
            assistant_text = "\n\n".join(article_parts)
        elif 'concierge' in result_map:
            concierge = _get_result('concierge', "Here's what I found for you.")
            article_parts = [concierge]
            seen_products = set()
            product_idx = 0
            for provider_name, data in products_by_provider.items():
                for product in data["products"]:
                    title = product.get("title", "")
                    if title in seen_products or product_idx >= 5:
                        continue
                    seen_products.add(title)
                    product_idx += 1
                    price = product.get("price", 0)
                    merchant = product.get("merchant", provider_name.title())
                    url = product.get("url", "")
                    description = product.get("description", "")
                    heading = f"### {product_idx}. {title}"
                    article_parts.append(heading)
                    # Product image
                    image_url = product.get("image_url", "")
                    if image_url:
                        article_parts.append(f"![{title}]({image_url})")
                    if description:
                        article_parts.append(description)
                    if price > 0 and url:
                        article_parts.append(f"**${price:.2f}** — [Check price on {merchant} →]({url})")
                    elif url:
                        article_parts.append(f"[View on {merchant} →]({url})")
            conclusion = _get_result('conclusion', '')
            if conclusion:
                article_parts.append("---")
                article_parts.append(conclusion)
            assistant_text = "\n\n".join(article_parts)
        else:
            if not assistant_text:
                assistant_text = "Here's what I found for you."

        # citations field: product-page URLs only (no review-source URLs).
        # The review-source URL accumulation that previously fed this
        # field has been removed along with the review_sources UI
        # block; surfacing review-site domains via citations would be
        # an alternate channel for the same tone.md violation. The
        # field exists for response_metadata.source_count + chat
        # history persistence; nothing in the frontend renders it.
        citations = [p["url"] for p in normalized_products if p.get("url") and p["url"].startswith("http")][:5]

        # Log summary
        provider_summary = ", ".join([f"{len(affiliate_products.get(p, []))} {p}" for p in sorted_providers])
        logger.info(f"[product_compose] Generated response: {len(assistant_text)} chars, providers: {provider_summary}")

        # Build search context for follow-up queries
        product_names = [p.get("name", "") for p in normalized_products if p.get("name")]
        new_context = {
            "category": slots.get("category", "") if slots else "",
            "product_type": slots.get("product_type", "") if slots else "",
            "product_names": product_names,
            "budget": slots.get("budget") if slots else None,
            "brand": slots.get("brand") if slots else None,
            "features": slots.get("features") if slots else None,
            "use_case": slots.get("use_case") if slots else None,
            "top_prices": {
                p["name"]: p["best_offer"]["price"]
                for p in products_with_offers
                if (p.get("best_offer") or {}).get("price")
            },
            "avg_rating": {
                name: rd.get("avg_rating", 0)
                for name, rd in review_data.items()
            } if review_data else {},
            "query": user_message,
            "timestamp": datetime.utcnow().isoformat(),
            "turn_index": len(state.get("conversation_history", [])),
        }

        # Push previous context to history
        prev = state.get("last_search_context", {})
        history = list(state.get("search_history", []))
        if prev:
            history.append(prev)
            history = history[-5:]

        logger.info(f"[product_compose] Saving search context: category={new_context['category']}, {len(product_names)} products")

        # Fire-and-forget: extract preferences from this query for cross-session memory
        meta_user_id = (state.get("metadata") or {}).get("user_id")
        if meta_user_id and slots:
            from app.services.preference_service import update_user_preferences
            asyncio.create_task(update_user_preferences(meta_user_id, slots or {}, new_context))

        return {
            "assistant_text": assistant_text,
            # B.3 — structurally separate from the body so the frontend
            # can render it distinctly (own line, italic) per spec §11.
            # chat.py emits a dedicated SSE `follow_up_question` event
            # after the content stream finishes.
            "follow_up_question": follow_up_text or None,
            # Quiz-path transitional reasoning — chat.py emits a dedicated SSE
            # event before the body; frontend renders it as a TransitionalBubble.
            "transitional_reasoning": transitional_text or None,
            "ui_blocks": ui_blocks,
            "citations": citations,
            "last_search_context": new_context,
            "search_history": history,
            "success": True
        }

    except Exception as e:
        logger.error(f"[product_compose] Error: {e}", exc_info=True)

        return {
            "assistant_text": "I encountered an error while formatting the response.",
            "ui_blocks": [],
            "citations": [],
            "error": str(e),
            "success": False
        }
