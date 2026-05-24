"""
Travel Destination Facts Tool

Provides destination facts (weather, best season, tips, activities, attractions, restaurants).
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

logger = get_logger(__name__)

# Tool contract for planner
TOOL_CONTRACT = {
    "name": "travel_destination_facts",
    "intent": "travel",
    "purpose": "Get destination weather, best season, tips, local customs, attractions, restaurants",
    "not_for": ["travel itinerary"],
    "tools": {
        "pre": [],  # Entry-point tool - no dependencies
        "post": ["travel_search_hotels", "travel_search_flights"]
    },
    "produces": ["destination_facts"],
    "citation_message": "Researching your destination...",
    "tool_order": 100
}


@tool_error_handler(tool_name="travel_destination_facts", error_message="Failed to get destination facts")
async def travel_destination_facts(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get destination facts and tips.

    Reads from state:
        - slots: Contains destination and optionally month
        - conversation_history: Previous messages for context
        - user_message: Current user query

    Writes to state:
        - destination_facts: Weather, best season, tips, local customs, attractions, restaurants

    Returns:
        {
            "weather": str,
            "best_season": str,
            "tips": [str],
            "local_customs": str,
            "attractions": [str],
            "restaurants": [str],
            "success": bool
        }
    """
    try:
        # Read from state
        slots = state.get("slots", {})
        destination = slots.get("destination", "")
        month = slots.get("month")
        user_message = state.get("user_message", "")
        conversation_history = state.get("conversation_history", [])

        logger.info(f"[travel_destination_facts] Getting facts for {destination}")

        # Fetch real-time web results via Perplexity (if configured)
        web_context = ""
        try:
            from app.services.search.config import get_search_manager
            search_manager = get_search_manager()
            if search_manager:
                search_query = f"{destination} travel tips"
                if month:
                    search_query += f" {month}"
                search_results = await search_manager.search(
                    query=search_query,
                    intent="travel",
                    max_results=5
                )
                if search_results:
                    from app.services.search.web_context import build_web_context
                    wc = build_web_context(
                        results=search_results,
                        query=search_query,
                        slots=slots,
                    )
                    web_context = wc.text
                    if wc.omitted_count:
                        logger.info(f"[travel_destination_facts] Web context: {wc.source_count} sources used, {wc.omitted_count} omitted, ~{wc.token_estimate} tokens")
                    logger.info(f"[travel_destination_facts] Got {len(search_results)} web results")
        except Exception as search_err:
            logger.warning(f"[travel_destination_facts] Web search failed, continuing with LLM-only: {search_err}")

        # Build conversation context
        history_context = ""
        if conversation_history:
            recent_history = conversation_history[-3:]  # Last 3 messages
            history_lines = []
            for msg in recent_history:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if content and role in ["user", "assistant"]:
                    history_lines.append(f"{role.capitalize()}: {content[:200]}")
            if history_lines:
                history_context = "\n\nConversation context:\n" + "\n".join(history_lines)

        web_section = f"\n\nRecent travel information:\n{web_context}\n" if web_context else ""
        knowledge_source = " and the web results below" if web_context else ""
        prompt = f"""Provide travel information for {destination} based on what the user is asking about{knowledge_source}.

User's question: {user_message}
{web_section}
{f"Specific month: {month}" if month else ""}
{history_context}

Analyze the user's question and return ONLY the relevant information they need.

Return valid JSON with ONLY the fields that match their question. Use these field names:
- "weather": string - Current weather and climate (only if asked about weather/climate)
- "best_season": string - Best time to visit (only if asked about when to visit/best time/season)
- "tips": array of strings - Practical travel tips (only if asked for tips/advice)
- "local_customs": string - Cultural customs and etiquette (only if asked about customs/culture/traditions)
- "attractions": array of strings - Must-see places, 5-10 items (only if asked about attractions/sightseeing/places to visit)
- "restaurants": array of strings - Restaurant recommendations with cuisine type, 5-10 items (only if asked about food/restaurants/dining)

IMPORTANT:
- ONLY include fields that are relevant to the user's specific question
- Do NOT include fields the user didn't ask about
- Be specific, accurate, and helpful
- For arrays, provide 5-10 quality recommendations
- Activities/things to do are handled by a separate itinerary tool - do NOT include them here

Examples:
User asks "weather in Paris" → Return: {{"weather": "..."}}
User asks "best restaurants in Tokyo" → Return: {{"restaurants": ["...", "...", ...]}}
User asks "attractions in Rome" → Return: {{"attractions": ["...", "...", ...]}}
User asks "attractions and where to eat in Barcelona" → Return: {{"attractions": [...], "restaurants": [...]}}"""

        facts_role = (
            "You return factual destination information shaped to what the "
            "user actually asked about — weather, restaurants, attractions, "
            "activities, customs, tips. Tailor the JSON fields populated to "
            "the question; do not return data the user didn't ask for. The "
            "downstream renderer turns each field into a separate UI card."
        )
        # Callbacks are automatically inherited from LangGraph context
        response = await model_service.generate(
            messages=[
                {"role": "system", "content": build_system_prompt(role_prompt=facts_role, kind="snippet")},
                {"role": "user", "content": prompt}
            ],
            model=settings.DEFAULT_MODEL,
            temperature=0.3,
            response_format={"type": "json_object"},
            agent_name="travel_destination_facts"
        )

        logger.info(f"[travel_destination_facts] Raw LLM response: {response}")

        data = json.loads(response)
        logger.info(f"[travel_destination_facts] Parsed JSON response fields: {list(data.keys())}")
        logger.debug(f"[travel_destination_facts] Full response data: {json.dumps(data, indent=2)}")

        return {
            "destination_facts": data,
            "success": True
        }

    except Exception as e:
        logger.error(f"[travel_destination_facts] Error: {e}", exc_info=True)
        return {
            "destination_facts": {},
            "error": str(e),
            "success": False
        }
