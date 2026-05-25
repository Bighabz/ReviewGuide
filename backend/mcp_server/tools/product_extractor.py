"""
Product Extractor Tool

Extracts explicit product names from user messages when user wants to compare specific products.
This is a default tool that runs early in the product intent flow.
"""

import sys
import os
import json
from typing import Dict, Any, List
from app.core.error_manager import tool_error_handler

# Add backend to path (portable path)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.centralized_logger import get_logger
from app.core.error_manager import tool_error_handler
from app.services.model_service import model_service
from app.core.config import settings

logger = get_logger(__name__)

# Tool contract for planner
TOOL_CONTRACT = {
    "name": "product_extractor",
    "intent": "product",
    "purpose": "Extracts explicit product names from user messages when user provides specific product names to compare (e.g., 'compare Product A and Product B'). Use ONLY when user explicitly names products to compare. Do NOT use for general product discovery queries.",
    "tools": {
        "pre": [],  # Entry-point tool - no dependencies
        "post": []  # comparison runs after extractor
    },
    "produces": ["product_names"],
    "citation_message": "Reading the room…",
    "is_default": True
}


@tool_error_handler(tool_name="product_extractor", error_message="Failed to extract products")
async def product_extractor(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract explicit product names from user message.

    This tool checks if the user provided specific product names to compare
    (e.g., "compare iPhone 17 and iPhone 17 Pro").

    Reads from state:
        - user_message: Current user message
        - conversation_history: Previous messages for context

    Writes to state:
        - product_names: List of extracted product names (empty if none found)

    Returns:
        {
            "product_names": [...],
            "success": bool
        }
    """
    try:
        # Read from state
        user_message = state.get("user_message", "")
        conversation_history = state.get("conversation_history", [])

        logger.info(f"[product_extractor] Analyzing message: {user_message[:100]}")
        logger.info(f"[product_extractor] conversation_history length: {len(conversation_history)}")

        # Build messages list with conversation history for LLM
        messages = [
            {"role": "system", "content": """You are a product name extraction assistant. Extract exact product names from the conversation history provided.

Return only valid JSON."""}
        ]

        # Add all conversation history
        for msg in conversation_history:
            messages.append(msg)
        logger.info(f"[product_extractor] Added {len(conversation_history)} messages from conversation history")

        # Build the extraction prompt
        extraction_prompt = f"""User message: "{user_message}"

Extract product names from the conversation history above based on what user wants.

Rules:
1. If user says "compare first two" - extract the first 2 products from the most recent product list
2. If user says "compare first three" - extract the first 3 products from the most recent product list
3. If user names specific products - extract those exact names
4. Include brand + model + version when available
5. Look for product lists in assistant messages that contain product recommendations

Return JSON:
{{
    "product_names": ["Product Name 1", "Product Name 2", ...]
}}

Return ONLY valid JSON."""

        messages.append({"role": "user", "content": extraction_prompt})

        extraction_response = await model_service.generate(
            messages=messages,
            model=settings.COMPOSER_MODEL,
            temperature=0.1,
            max_tokens=500,
            response_format={"type": "json_object"},
            agent_name="product_extractor"
        )

        # Parse extraction
        extracted_data = json.loads(extraction_response)
        extracted_product_names = extracted_data.get("product_names", [])

        logger.info(f"[product_extractor] extracted names={extracted_product_names}")

        # Only write product_names if we actually extracted something.
        # Otherwise preserve what product_search already wrote to state.
        existing_names = state.get("product_names", [])
        if extracted_product_names:
            return {
                "product_names": extracted_product_names,
                "success": True
            }
        elif existing_names:
            logger.info(f"[product_extractor] No explicit names found, preserving {len(existing_names)} from product_search")
            return {"success": True}
        else:
            return {
                "product_names": [],
                "success": True
            }

    except Exception as e:
        logger.error(f"[product_extractor] Error: {e}", exc_info=True)
        return {
            "product_names": [],
            "error": str(e),
            "success": False
        }
