"""
Product Search Tool

Uses OpenAI to generate a list of REAL product names based on user query.
Returns ONLY product names - other tools handle specs, reviews, affiliate links.
"""

import sys
import os
import json
import datetime
from typing import Dict, Any, List
from app.core.error_manager import tool_error_handler

# Add backend to path (portable path)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Tool contract for planner
TOOL_CONTRACT = {
    "name": "product_search",
    "intent": "product",
    "purpose": "Search for products to buy",
    "tools": {
        "pre": [],  # Entry-point tool - no dependencies
        # "post": ['product_evidence']  # Compose is auto-added at end of intent
        "post": ['product_normalize']  # Compose is auto-added at end of intent
    },
    "produces": ["product_names"],
    "optional_slots": ["product_name", "category", "brand", "budget", "size", "color", "material", "style", "features", "use_case", "gender"],
    "slot_types": {
        "product_name": {"type": "string", "description": "Specific product name or model (e.g., 'MacBook Pro', 'Air Jordan 1')"},
        "category": {"type": "string", "description": "Product category (e.g., 'laptop', 'headphones', 'shoes', 'camera')"},
        "brand": {"type": "string", "description": "Brand preference (e.g., 'Apple', 'Nike', 'Sony', 'Samsung')"},
        "budget": {"type": "string", "description": "Price range or budget (e.g., 'under $500', '$100-$200', 'below 1000')"},
        "size": {"type": "string", "description": "Size specification (e.g., '13 inch', 'medium', '42', 'XL')"},
        "color": {"type": "string", "description": "Color preference (e.g., 'black', 'silver', 'red', 'space gray')"},
        "material": {"type": "string", "description": "Material preference (e.g., 'leather', 'cotton', 'aluminum', 'stainless steel')"},
        "style": {"type": "string", "description": "Style preference (e.g., 'casual', 'gaming', 'professional', 'minimalist')"},
        "features": {"type": "string", "description": "Desired features (e.g., 'wireless', 'waterproof', 'noise-cancelling', '4K')"},
        "use_case": {"type": "string", "description": "Intended use (e.g., 'running', 'office work', 'travel', 'photography')"},
        "gender": {"type": "string", "description": "Gender specification (e.g., 'men', 'women', 'unisex')"},
    },
    "citation_message": "Sorting the contenders…"
}


@tool_error_handler(tool_name="product_search", error_message="Failed to search products")
async def product_search(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate list of real product names using OpenAI.

    Reads from state:
        - user_message: User's search query
        - slots: Optional structured data with the following fields:
            - product_name: Specific product name or model
            - category: Product category (e.g., "laptop", "headphones", "shoes")
            - brand: Brand preference (e.g., "Apple", "Nike", "Sony")
            - budget: Price range or budget (e.g., "under $500", "$100-$200")
            - size: Size specification (e.g., "13 inch", "medium", "42")
            - color: Color preference (e.g., "black", "silver", "red")
            - material: Material preference (e.g., "leather", "cotton", "aluminum")
            - style: Style preference (e.g., "casual", "gaming", "professional")
            - features: Desired features (e.g., "wireless", "waterproof", "noise-cancelling")
            - use_case: Intended use (e.g., "running", "office work", "travel")
            - gender: Gender specification (e.g., "men", "women", "unisex")

    Writes to state:
        - product_names: List of specific product model names

    Returns:
        {
            "product_names": ["Product Name 1", "Product Name 2", ...],
            "success": bool
        }
    """
    # Import here to avoid settings validation at module load
    from app.core.centralized_logger import get_logger
    from app.core.config import settings
    from app.services.model_service import model_service

    logger = get_logger(__name__)

    try:
        query = state.get("user_message", "")
        slots = state.get("slots", {})
        conversation_history = state.get("conversation_history", [])
        last_search_context = state.get("last_search_context", {})
        search_history = state.get("search_history", [])

        # Check if user is referencing a previous search ("go back to vacuums")
        if search_history and not slots.get("category"):
            q_lower = query.lower()
            for ctx in reversed(search_history):
                cat = ctx.get("category", "").lower()
                ptype = ctx.get("product_type", "").lower()
                if (cat and cat in q_lower) or (ptype and ptype in q_lower):
                    last_search_context = ctx
                    logger.info(f"[product_search] Found matching history context: category={cat}")
                    break

        # Extract optional slots for product search, with context fallback
        product_name = slots.get("product_name", "")

        # If no product_name in slots, try to extract from user message directly
        if not product_name:
            import re
            # Match patterns like: "tell me more about X", "more about X", "what about X"
            name_patterns = [
                r"(?:tell me )?more about (?:the |a |an )?([A-Za-z0-9][^?.,!]{3,40})",
                r"what (?:about|can you tell me about) (?:the |a |an )?([A-Za-z0-9][^?.,!]{3,40})",
                r"(?:info|information|details|specs) (?:on|about|for) (?:the |a |an )?([A-Za-z0-9][^?.,!]{3,40})",
                r"(?:show me|find|search for|look up) (?:the |a |an )?([A-Za-z0-9][^?.,!]{3,40})",
            ]
            for pattern in name_patterns:
                match = re.search(pattern, query.lower())
                if match:
                    extracted = match.group(1).strip().rstrip('?.!')
                    # Only use if it looks like a specific product name (2+ words or contains digits)
                    if len(extracted.split()) >= 2 or any(c.isdigit() for c in extracted):
                        product_name = extracted
                        logger.info(f"[product_search] Extracted product name from message: '{product_name}'")
                        break

        # Check if last_search_context is relevant to the current query.
        # If the user is asking about a clearly different product/category, don't use stale context.
        _context_is_relevant = True
        if last_search_context and product_name:
            # We extracted a specific product name from the current message.
            # Check if it's related to the previous context.
            prev_cat = last_search_context.get("category", "").lower()
            prev_prods = [p.lower() for p in last_search_context.get("product_names", [])]
            pname_lower = product_name.lower()

            topic_in_context = (
                (prev_cat and (prev_cat in pname_lower or any(w in pname_lower for w in prev_cat.split())))
                or any(pp in pname_lower or pname_lower in pp for pp in prev_prods)
            )
            if not topic_in_context:
                _context_is_relevant = False
                logger.info(
                    f"[product_search] Stale context detected "
                    f"(prev: '{prev_cat}', current: '{product_name}') — ignoring last_search_context"
                )

        category = slots.get("category", "") or (last_search_context.get("category", "") if _context_is_relevant else "")
        brand = slots.get("brand", "") or (last_search_context.get("brand", "") if _context_is_relevant else "")
        budget = slots.get("budget", "") or (last_search_context.get("budget", "") if _context_is_relevant else "")
        size = slots.get("size", "")
        color = slots.get("color", "")
        material = slots.get("material", "")
        style = slots.get("style", "")
        features = slots.get("features", "") or (last_search_context.get("features", "") if _context_is_relevant else "")
        use_case = slots.get("use_case", "") or (last_search_context.get("use_case", "") if _context_is_relevant else "")
        gender = slots.get("gender", "")

        # Build search criteria from slots
        criteria_parts = []
        if product_name:
            criteria_parts.append(f"Product: {product_name}")
        if category:
            criteria_parts.append(f"Category: {category}")
        if brand:
            criteria_parts.append(f"Brand: {brand}")
        if budget:
            criteria_parts.append(f"Budget: {budget}")
        if size:
            criteria_parts.append(f"Size: {size}")
        if color:
            criteria_parts.append(f"Color: {color}")
        if material:
            criteria_parts.append(f"Material: {material}")
        if style:
            criteria_parts.append(f"Style: {style}")
        if features:
            criteria_parts.append(f"Features: {features}")
        if use_case:
            criteria_parts.append(f"Use case: {use_case}")
        if gender:
            criteria_parts.append(f"Gender: {gender}")

        # Combine query with slot criteria
        slot_criteria = "\n".join(criteria_parts) if criteria_parts else ""
        combined_query = query
        if slot_criteria:
            combined_query = f"{query}\n\nAdditional criteria:\n{slot_criteria}"

        # "X vs Y" shortlists must represent BOTH sides (QA 2026-06-10: "nike vs
        # adidas sneakers" generated all-Nike). The clarifier's comparison
        # detection (Outcome 5) stores the pair in slots; demand balanced
        # coverage from the generator.
        comparison_products = slots.get("comparison_products") or []
        comparison_block = ""
        if isinstance(comparison_products, list) and len(comparison_products) == 2:
            side_a, side_b = comparison_products
            comparison_block = f"""
COMPARISON REQUEST — the user is deciding between "{side_a}" and "{side_b}":
- Include 2-4 specific products for EACH side ("{side_a}" AND "{side_b}")
- A list where either side has fewer than 2 products is WRONG — never let one side dominate
"""

        logger.info(f"[product_search] Query: {query}")
        if slot_criteria:
            logger.info(f"[product_search] Slot criteria:\n{slot_criteria}")

        # Build conversation context for resolving references
        conversation_context = ""
        if conversation_history:
            recent = conversation_history[-6:]
            context_lines = []
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content and role in ["user", "assistant"]:
                    context_lines.append(f"{role}: {content[:200]}")
            if context_lines:
                conversation_context = "\n".join(context_lines)

        # Add previous search context for follow-up resolution.
        # Only inject when the context is relevant to the current query to avoid contamination.
        prev_products_block = ""
        if last_search_context.get("product_names") and _context_is_relevant:
            prev_names = ", ".join(last_search_context["product_names"][:5])
            prev_cat = last_search_context.get("category", "")
            prev_products_block = f"\nPreviously discussed products ({prev_cat}): {prev_names}\n"

        # Build prompt with optional conversation context
        context_block = ""
        if conversation_context or prev_products_block:
            context_block = f"""Recent conversation (resolve references like "those", "the ones", "the best reviewed ones", "cheapest one", etc.):
{conversation_context}
{prev_products_block}
"""

        # Build user preference context hints (from cross-session memory)
        user_prefs = (state.get("metadata") or {}).get("user_preferences", {})
        pref_context = ""
        if user_prefs:
            parts = []
            if user_prefs.get("brands"):
                top = sorted(user_prefs["brands"].items(), key=lambda x: x[1], reverse=True)[:3]
                parts.append(f"frequently searches: {', '.join(b[0] for b in top)}")
            if user_prefs.get("budget_ranges"):
                parts.append(f"typical budget: {user_prefs['budget_ranges'][0]}")
            if parts:
                pref_context = f"\nUser preferences (for context only, do not override query): {'; '.join(parts)}"
                logger.info(f"[product_search] User preferences: {pref_context.strip()}")

        prompt = f"""{context_block}User is looking for: "{combined_query}"{pref_context}

Generate a list of 5-8 SPECIFIC product model names that match this request.

Requirements:
- FIRST identify what TYPE of purchasable product the user is shopping for; every name you return must be that type of product
- Use conversation context to understand what the user is referring to
- If user says "the best reviewed ones" or "those headphones", use conversation to identify the product category
- Include brand name + specific model/version when user specifies (e.g., "iPhone 16 Pro Max")
- If user asks for a specific product (e.g., "iPhone 16"), include variations of that product
- Be specific: "Nike Air Zoom Pegasus 40" not just "Nike running shoes"
- If unsure about exact model numbers, use the product name the user specified
- NEVER pad the list with items of a different product type that merely contain the user's words (a movie, perfume, or toy that happens to carry a brand name is wrong)
{comparison_block}
ESCAPE HATCH: if the message names only brands or companies and you cannot tell what type of product they want (e.g. "ford or chevy" with no category), do NOT guess across categories — return {{"products": []}}.

Return ONLY a JSON object with product names:
{{"products": ["Product Name 1", "Product Name 2", ...]}}"""

        # Callbacks are automatically inherited from LangGraph context
        # Use PRODUCT_SEARCH_MODEL with configurable max_tokens (important for reasoning models)
        response = await model_service.generate(
            messages=[
                {"role": "system", "content": f"You are a product name generator. Today's date is {datetime.date.today().isoformat()}. Generate product names based on user's request using the LATEST models and versions available as of today. For example, if asked about iPhones, use the current generation (not older ones). Always return valid JSON. When the product type is clear, return product names; when it is NOT identifiable (bare brand names, no category), return an empty products list rather than guessing across categories. IMPORTANT: Do NOT include accessories, replacement parts, cases, chargers, cables, adapters, filters, or other add-on items. Only return the primary products the user is asking about."},
                {"role": "user", "content": prompt}
            ],
            model=settings.PRODUCT_SEARCH_MODEL,
            temperature=0.7,
            max_tokens=settings.PRODUCT_SEARCH_MAX_TOKENS,
            response_format={"type": "json_object"},
            agent_name="product_search"
        )

        # Parse response
        try:
            # Try to parse as JSON object first
            data = json.loads(response)
            if isinstance(data, dict):
                # Extract array from object (might be {"products": [...]} or {"product_names": [...]})
                product_names = data.get("products") or data.get("product_names") or data.get("items") or []
            elif isinstance(data, list):
                product_names = data
            else:
                raise ValueError("Response is not a list or object containing a list")
        except:
            # Fallback: try to find JSON array in response
            import re
            match = re.search(r'\[.*?\]', response, re.DOTALL)
            if match:
                product_names = json.loads(match.group(0))
            else:
                raise ValueError("Could not parse product names from response")

        # Validate and clean
        product_names = [str(p).strip() for p in product_names if p and str(p).strip()]

        logger.info(f"[product_search] Generated {len(product_names)} product names")
        for i, name in enumerate(product_names, 1):
            logger.info(f"  {i}. {name}")

        return {
            "product_names": product_names,
            "success": True
        }

    except Exception as e:
        logger.error(f"[product_search] Error: {e}", exc_info=True)

        return {
            "product_names": [],
            "error": str(e),
            "success": False
        }
