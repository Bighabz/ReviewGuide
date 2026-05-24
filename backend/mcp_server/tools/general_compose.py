"""
General Compose Tool

Generates final response for general information queries (NOT product recommendations).
For intent="general" - factual answers based on search results.
"""

from app.core.centralized_logger import get_logger
from app.core.error_manager import tool_error_handler
import sys
import os
import json
from typing import Dict, Any

# Add backend to path (portable path)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.services.model_service import model_service
from app.services.prompts.voice import build_system_prompt
from app.core.config import settings
from app.utils.date_utils import get_current_date_str

logger = get_logger(__name__)

# Tool contract for planner
TOOL_CONTRACT = {
    "name": "general_compose",
    "intent": "general",
    "purpose": "Generate final text response for general information queries (intent=general ONLY, NOT for product recommendations). This is the final tool in the general intent flow.",
    "tools": {
        "pre": [],  # Auto-added at end of general intent
        "post": []
    },
    "produces": ["assistant_text", "ui_blocks", "citations"],
    "citation_message": "Writing answer...",
    "tool_order": 800,
    "is_default": True,
    "is_required": True
}


@tool_error_handler(tool_name="general_compose", error_message="Failed to compose general response")
async def general_compose(
    state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compose final response for general queries.

    Reads from state:
        - user_message: User's question
        - search_results: Search results from general_search

    Writes to state:
        - assistant_text: Final response text
        - ui_blocks: UI blocks (empty for general queries)
        - citations: Source citations

    Returns:
        {
            "assistant_text": str,
            "ui_blocks": [],
            "citations": [],
            "success": bool
        }
    """
    try:
        user_message = state.get("user_message", "")
        search_results = state.get("search_results", [])

        logger.info(f"[general_compose] Composing response for: {user_message}")

        # Always load conversation history for context awareness
        conversation_history = state.get("conversation_history", [])

        if not search_results:
            # No search results - generate conversational response using LLM
            # Build messages with actual conversation history as structured messages
            system_prefix = (
                f"Today's date is {get_current_date_str()}.\n"
                "If discussing specific products or models that may have been released after your training "
                "cutoff, briefly acknowledge that you may not have the most current specifications or pricing.\n\n"
            )
            no_search_role = system_prefix + (
                "You are answering a conversational question with no search "
                "results available. Use the conversation history as context "
                "— if the user shared their name, preferences, family, or "
                "budget earlier, weave those details in naturally. Keep the "
                "response under 50 words. Do NOT describe your process or "
                "mention how many sources you searched."
            )
            messages = [
                {"role": "system", "content": build_system_prompt(role_prompt=no_search_role, kind="response")},
            ]

            # Add recent history as actual message objects so the LLM sees real context
            if conversation_history:
                for msg in conversation_history[-10:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if content and role in ("user", "assistant", "human", "ai"):
                        mapped_role = "assistant" if role in ("assistant", "ai") else "user"
                        messages.append({"role": mapped_role, "content": content[:500]})

            messages.append({"role": "user", "content": user_message})

            assistant_text = await model_service.generate(
                messages=messages,
                model=settings.COMPOSER_MODEL,
                temperature=0.8,
                max_tokens=150,
                agent_name="general_compose_conversational"
            )

            logger.info(f"[general_compose] Generated conversational response: {len(assistant_text)} chars")

            return {
                "assistant_text": assistant_text.strip(),
                "ui_blocks": [],
                "citations": [],
                "success": True
            }

        # Build context from search results
        context = ""
        for idx, result in enumerate(search_results[:5], 1):
            context += f"[{idx}] {result.get('title', '')}\n{result.get('snippet', '')}\n\n"

        # Build conversation context for search-results path
        conversation_context = ""
        if conversation_history:
            recent = conversation_history[-6:]
            history_lines = []
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content and role in ("user", "assistant", "human", "ai"):
                    history_lines.append(f"{role}: {content[:200]}")
            if history_lines:
                conversation_context = "Recent conversation:\n" + "\n".join(history_lines) + "\n\n"

        # Generate response using LLM
        prompt = f"""User asked: "{user_message}"

{conversation_context}Based on these search results, provide a clear, accurate answer:

{context}

Answer the user's question directly and concisely. If the user's question refers to something from the conversation (like their name, preferences, or previous topics), answer from conversation context instead of search results. Use citation markers [1], [2], etc. when referencing sources."""

        # Callbacks are automatically inherited from LangGraph context
        search_system_prefix = (
            f"Today's date is {get_current_date_str()}.\n"
            "If discussing specific products or models that may have been released after your training "
            "cutoff, briefly acknowledge that you may not have the most current specifications or pricing.\n\n"
        )
        search_role = search_system_prefix + (
            "You are answering a question using both search results and the "
            "conversation so far. Use the search results for factual "
            "questions; use the conversation history for personal ones "
            "(names, preferences, family, budget). Weave personal details in "
            "naturally when relevant. Do NOT describe your process or mention "
            "how many sources you searched."
        )
        assistant_text = await model_service.generate(
            messages=[
                {"role": "system", "content": build_system_prompt(role_prompt=search_role, kind="response")},
                {"role": "user", "content": prompt}
            ],
            model=settings.COMPOSER_MODEL,
            temperature=0.7,
            max_tokens=500,
            agent_name="general_compose"
        )

        # Extract citations
        citations = [r.get("url", "") for r in search_results[:5]]

        logger.info(f"[general_compose] Generated response: {len(assistant_text)} chars")

        return {
            "assistant_text": assistant_text,
            "ui_blocks": [],  # No special UI blocks for general queries
            "citations": citations,
            "success": True
        }

    except Exception as e:
        logger.error(f"[general_compose] Error: {e}", exc_info=True)
        return {
            "assistant_text": "I encountered an error generating the response. Please try again.",
            "ui_blocks": [],
            "citations": [],
            "error": str(e),
            "success": False
        }
