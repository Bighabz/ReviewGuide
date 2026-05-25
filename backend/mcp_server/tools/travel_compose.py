"""
Travel Compose Tool

Formats final travel response.
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

# No longer need LLM for compose - using template-based response for speed

logger = get_logger(__name__)

# Tool contract for planner
TOOL_CONTRACT = {
    "name": "travel_compose",
    "intent": "travel",
    "purpose": "Generate final user response with assistant text and UI blocks for travel recommendations. This is the final tool in the travel intent flow.",
    "tools": {
        "pre": [],  # Auto-added at end of travel intent
        "post": []
    },
    "produces": ["assistant_text", "ui_blocks", "citations"],
    "citation_message": "Putting it together…",
    "tool_order": 800,
    "is_default": True,
    "is_required": True
}


@tool_error_handler(tool_name="travel_compose", error_message="Failed to format travel response")
async def travel_compose(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format final travel response with UI blocks.

    Reads from state:
        - user_message: Original query
        - itinerary: Day-by-day itinerary (optional)
        - hotels: Hotel search results (optional)
        - flights: Flight search results (optional)
        - destination_facts: Destination information (optional)
        - travel_results: Combined results (optional)
        - intent: User intent (optional)

    Writes to state:
        - assistant_text: Final response text
        - ui_blocks: UI components for display
        - citations: Source citations

    Returns:
        {
            "assistant_text": str,
            "ui_blocks": [...],
            "citations": [...],
            "success": bool
        }
    """
    # Read from state
    itinerary = state.get("itinerary")
    hotels = state.get("hotels")
    flights = state.get("flights")
    cars = state.get("cars")
    activities = state.get("activities")
    destination_facts = state.get("destination_facts")
    general_travel_info = state.get("general_travel_info")
    travel_results = state.get("travel_results")
    intent = state.get("intent", "travel")

    logger.info(f"[travel_compose] Composing travel response")

    # --- Recovery path: all upstream tools failed/timed out ---
    if not any([itinerary, hotels, flights, activities, cars, destination_facts, general_travel_info]):
        logger.warning("[travel_compose] All travel data missing — returning recovery prompt")
        return {
            "assistant_text": (
                "I ran into an issue fetching travel details. "
                "You can try again, or ask for a specific piece -- "
                "e.g., 'Show me hotels in Paris' or 'Give me a 3-day itinerary for Tokyo.'"
            ),
            "ui_blocks": [],
            "citations": [],
            "success": True,
        }
    logger.info(f"[travel_compose] State keys: {list(state.keys())}")
    logger.info(f"[travel_compose] itinerary from state: {itinerary}")
    logger.info(f"[travel_compose] hotels from state: {hotels}")
    logger.info(f"[travel_compose] flights from state: {flights}")
    logger.info(f"[travel_compose] destination_facts from state: {destination_facts}")
    logger.info(f"[travel_compose] general_travel_info from state: {bool(general_travel_info)}")

    # Generate assistant text
    has_itinerary = itinerary and len(itinerary) > 0
    has_hotels = hotels and len(hotels) > 0
    has_flights = flights and len(flights) > 0
    has_cars = cars and len(cars) > 0
    has_activities = activities and len(activities) > 0
    has_destination_facts = destination_facts and isinstance(destination_facts, dict)
    has_general_info = general_travel_info and len(str(general_travel_info).strip()) > 0

    logger.info(f"[travel_compose] has_itinerary={has_itinerary}, has_hotels={has_hotels}, has_flights={has_flights}, has_cars={has_cars}, has_activities={has_activities}, has_destination_facts={has_destination_facts}, has_general_info={has_general_info}")

    # Build intro text directly without LLM call for speed
    # Extract key info from slots
    slots = state.get("slots", {})
    destination = slots.get("destination", "your destination")
    duration = slots.get("duration_days", "")

    # If we only have general_travel_info (no structured data), use it directly as the response
    if has_general_info and not has_itinerary and not has_hotels and not has_flights and not has_destination_facts:
        logger.info(f"[travel_compose] Using general_travel_info as direct response ({len(str(general_travel_info))} chars)")
        assistant_text = str(general_travel_info)
    else:
        # Build a simple but informative intro
        parts = []
        if duration:
            parts.append(f"Here's your {duration}-day trip to {destination}!")
        else:
            parts.append(f"Here's information about {destination}!")

        if has_itinerary and has_hotels and has_flights:
            parts.append("I've prepared a complete itinerary with activities, plus hotel and flight options for you.")
        elif has_itinerary:
            parts.append("I've created a day-by-day itinerary with activities, meals, and highlights.")
        elif has_hotels and has_flights:
            parts.append("I've found hotel and flight options for your trip.")
        elif has_hotels:
            parts.append("I've found hotel options for your stay.")
        elif has_flights:
            parts.append("I've found flight options for your trip.")

        if has_cars:
            parts.append("I've also found rental car options for you.")

        if has_activities:
            parts.append("I've found tours and activities for you to explore.")

        if has_destination_facts:
            # Extract activities, attractions, restaurants from destination_facts
            activities = destination_facts.get("activities", [])
            attractions = destination_facts.get("attractions", [])
            restaurants = destination_facts.get("restaurants", [])
            weather = destination_facts.get("weather", "")

            if activities or attractions or restaurants:
                parts.append("I've gathered some recommendations for your trip.")
            elif weather:
                parts.append("Here's what you should know about the destination.")

        # Partial data note: inform user about what couldn't be fetched
        missing = []
        if not has_itinerary and not has_general_info:
            missing.append("itinerary")
        if not has_flights:
            missing.append("flights")
        if not has_hotels:
            missing.append("hotels")

        # Only add a partial note when at least one thing succeeded but something is missing
        has_any = has_itinerary or has_hotels or has_flights or has_cars or has_activities or has_destination_facts
        if has_any and missing and len(missing) < 3:
            missing_str = " and ".join(missing)
            parts.append(
                f"I couldn't find {missing_str} for this trip -- "
                "you can ask me to search for those specifically."
            )

        assistant_text = " ".join(parts)

    # Create UI blocks
    ui_blocks = []
    if has_itinerary:
        ui_blocks.append({"type": "itinerary", "data": itinerary})
        logger.info(f"[travel_compose] Added itinerary UI block with {len(itinerary)} days")
    if has_flights:
        ui_blocks.append({"type": "flights", "data": flights[:5]})
        logger.info(f"[travel_compose] Added flights UI block with {len(flights[:5])} flights")
    if has_hotels:
        ui_blocks.append({"type": "hotels", "data": hotels[:5]})
        logger.info(f"[travel_compose] Added hotels UI block with {len(hotels[:5])} hotels")
    if has_cars:
        ui_blocks.append({"type": "cars", "data": cars})
        logger.info(f"[travel_compose] Added cars UI block with {len(cars)} car rental links")
    if has_activities:
        ui_blocks.append({"type": "activities_viator", "data": activities[:5]})
        logger.info(f"[travel_compose] Added Viator activities UI block with {len(activities[:5])} activities")

    # Add destination facts UI blocks
    if has_destination_facts:
        activities = destination_facts.get("activities", [])
        attractions = destination_facts.get("attractions", [])
        restaurants = destination_facts.get("restaurants", [])
        weather = destination_facts.get("weather", "")
        best_season = destination_facts.get("best_season", "")
        tips = destination_facts.get("tips", [])
        local_customs = destination_facts.get("local_customs", "")

        # Add activities block
        if activities and len(activities) > 0:
            ui_blocks.append({
                "type": "activities",
                "title": "Things to Do",
                "data": activities
            })
            logger.info(f"[travel_compose] Added activities UI block with {len(activities)} items")

        # Add attractions block
        if attractions and len(attractions) > 0:
            ui_blocks.append({
                "type": "attractions",
                "title": "Must-See Attractions",
                "data": attractions
            })
            logger.info(f"[travel_compose] Added attractions UI block with {len(attractions)} items")

        # Add restaurants block
        if restaurants and len(restaurants) > 0:
            ui_blocks.append({
                "type": "restaurants",
                "title": "Recommended Restaurants",
                "data": restaurants
            })
            logger.info(f"[travel_compose] Added restaurants UI block with {len(restaurants)} items")

        # Add destination info block (weather, season, tips, customs)
        destination_info = {}
        if weather:
            destination_info["weather"] = weather
        if best_season:
            destination_info["best_season"] = best_season
        if tips and len(tips) > 0:
            destination_info["tips"] = tips
        if local_customs:
            destination_info["local_customs"] = local_customs

        if destination_info:
            ui_blocks.append({
                "type": "destination_info",
                "title": "Destination Information",
                "data": destination_info
            })
            logger.info(f"[travel_compose] Added destination_info UI block")

    # Add a conclusion that invites the user to refine their search
    destination = state.get("slots", {}).get("destination", "your destination")
    ui_blocks.append({
        "type": "conclusion",
        "data": {"text": f"Want better results? Tell me your travel dates, number of travelers, or whether you prefer beach, city, or countryside — and I'll tailor everything for {destination}."}
    })

    logger.info(f"[travel_compose] Total UI blocks created: {len(ui_blocks)}")
    logger.info(f"[travel_compose] UI blocks: {ui_blocks}")

    return {
        "assistant_text": assistant_text,
        "ui_blocks": ui_blocks,
        "citations": [],
        "success": True
    }
