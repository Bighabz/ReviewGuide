"""
General Search Tool

Performs web search for general information queries (NOT product recommendations).
For intent="general" - factual questions, information lookup, specifications, etc.
"""

from app.core.centralized_logger import get_logger
from app.core.error_manager import tool_error_handler
import sys
import os
from typing import Dict, Any
from app.core.error_manager import tool_error_handler

# Add backend to path (portable path)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.services.search.config import get_search_manager

logger = get_logger(__name__)

# Tool contract for planner
TOOL_CONTRACT = {
    "name": "general_search",
    "intent": "general",
    "purpose": "Search for general information",
    "tools": {
        "pre": [],  # Entry-point tool - no dependencies
        "post": []  # Compose is auto-added at end of intent
    },
    "produces": ["search_results", "search_query"],
    "citation_message": "Searching the web…",
    "tool_order": 50
}


@tool_error_handler(tool_name="general_search", error_message="Failed to perform general search")
async def general_search(
    state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Perform web search for general information queries.

    Reads from state:
        - user_message: User's question
        - session_id: Session ID for loading conversation history

    Writes to state:
        - search_results: List of search results
        - search_query: The search query used

    Returns:
        {
            "search_results": [...],
            "search_query": str,
            "success": bool
        }
    """
    try:
        user_message = state.get("user_message", "")
        session_id = state.get("session_id")
        conversation_history = state.get("conversation_history", [])

        logger.info(f"[general_search] Searching for: {user_message}")

        # Build search query with conversation context
        # This helps the search understand what the user is referring to
        search_query = user_message
        if conversation_history:
            context_parts = []
            for msg in conversation_history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if content and role in ["user", "assistant"]:
                    context_parts.append(f"{role}: {content}")

            if context_parts:
                context_str = "\n".join(context_parts)
                search_query = f"Context from conversation:\n{context_str}\n\nCurrent query: {user_message}"
                logger.info(f"[general_search] Added {len(context_parts)} messages as conversation context")

        # Get search manager
        search_manager = get_search_manager()

        # Perform search - pass conversation_history directly instead of having provider load it
        search_result_objects = await search_manager.search(
            query=search_query,
            intent="general",
            max_results=5,
            conversation_history=conversation_history  # Pass history from state
        )

        # Convert to dict format
        search_results = [
            {
                "url": r.url,
                "title": r.title,
                "snippet": r.snippet,
                "source_rank": r.source_rank,
                "freshness": r.freshness,
                "authority_score": getattr(r, 'authority_score', 5)
            }
            for r in search_result_objects
        ]

        logger.info(f"[general_search] Found {len(search_results)} results")

        return {
            "search_results": search_results,
            "search_query": user_message,
            "success": True
        }

    except Exception as e:
        logger.error(f"[general_search] Error: {e}", exc_info=True)
        return {
            "search_results": [],
            "search_query": "",
            "error": str(e),
            "success": False
        }
