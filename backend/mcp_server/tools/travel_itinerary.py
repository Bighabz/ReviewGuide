"""
Travel Itinerary Tool

Generates day-by-day travel itinerary.
"""

from app.core.centralized_logger import get_logger
from app.core.error_manager import tool_error_handler
import sys
import os
import json
from typing import Dict, Any
from datetime import datetime, timedelta
from app.core.error_manager import tool_error_handler

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
    "name": "travel_itinerary",
    "purpose": "Create day-by-day trip itinerary, travel plans, travel details",
    "intent": "travel",
    "tools": {
        "pre": [],  # Entry-point tool - no dependencies
        "post": ["travel_search_hotels", "travel_search_flights", "travel_search_cars"]
    },
    "produces": ["itinerary"],
    "required_slots": ["destination", "duration_days"],
    "citation_message": "Creating your itinerary...",
    "tool_order": 100,
    "slot_types": {
        "destination": {"type": "string", "format": "city"},
        "duration_days": {"type": "integer", "format": "number"},
    }
}


@tool_error_handler(tool_name="travel_itinerary", error_message="Failed to create itinerary")
async def travel_itinerary(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate day-by-day travel itinerary.

    Reads from state:
        - slots: Contains destination, duration_days, check_in, check_out, interests, travelers

    Writes to state:
        - itinerary: Day-by-day itinerary plan
        - destination_overview: Brief destination description

    Returns:
        {
            "itinerary": [...],
            "destination_overview": str,
            "success": bool
        }
    """
    try:
        # Read from state
        slots = state.get("slots", {})
        destination = slots.get("destination")
        duration_days = slots.get("duration_days")
        interests = slots.get("interests")
        travelers = slots.get("travelers")

        logger.info(f"[travel_itinerary] Generating {duration_days}-day itinerary for {destination}")

        interests_str = ", ".join(interests) if interests else "general sightseeing"

        prompt = f"""Create a {duration_days}-day itinerary for {destination}.

Interests: {interests_str}
Travelers: {travelers or {'adults': 1}}

Return JSON:
{{"itinerary":[{{"day":1,"title":"Title","activities":["Morning:X","Afternoon:Y","Evening:Z"],"meals":{{"breakfast":"A","lunch":"B","dinner":"C"}},"highlights":["H1","H2"]}}]}}

Keep activities concise (max 15 words each). Max 2 highlights per day."""

        # Limit max_tokens to speed up response - each day needs ~150 tokens
        max_tokens = min(200 + (duration_days * 180), 1500)

        itinerary_role = (
            "You generate a tight day-by-day itinerary as JSON. Each activity "
            "string must be concrete (≤15 words), not generic. Vary the rhythm "
            "across days — don't repeat the same structure verbatim."
        )
        response = await model_service.generate(
            messages=[
                {"role": "system", "content": build_system_prompt(role_prompt=itinerary_role, kind="snippet")},
                {"role": "user", "content": prompt}
            ],
            model=settings.DEFAULT_MODEL,
            temperature=0.5,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            agent_name="travel_itinerary"
        )

        data = json.loads(response)

        logger.info(f"[travel_itinerary] Generated {len(data.get('itinerary', []))} days")

        return {
            "itinerary": data.get("itinerary", []),
            "destination_overview": data.get("overview", ""),
            "success": True
        }

    except Exception as e:
        logger.error(f"[travel_itinerary] Error: {e}", exc_info=True)

        return {
            "itinerary": [],
            "destination_overview": "",
            "error": str(e),
            "success": False
        }
