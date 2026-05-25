"""
Travel Search Flights Tool

Generates Expedia PLP (Product Listing Page) search links for flights.
Returns affiliate search links instead of individual flight cards.
"""

from app.core.centralized_logger import get_logger
from app.core.error_manager import tool_error_handler
import sys
import os
from typing import Dict, Any
from datetime import datetime, timedelta

# Add backend to path (portable path)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.services.travel.providers.expedia_plp_provider import ExpediaPLPLinkGenerator

logger = get_logger(__name__)


# Tool contract for planner
TOOL_CONTRACT = {
    "name": "travel_search_flights",
    "purpose": "Search for flights deals",
    "intent": "travel",
    "tools": {
        "pre": [],  # Entry-point tool - no dependencies
        "post": []  # Compose is auto-added at end of intent
    },
    "produces": ["flights"],
    "required_slots": ["origin", "destination", "departure_date", "duration_days", "adults"],
    "optional_slots": ["return_date", "children"],
    "citation_message": "Asking around…",
    "tool_order": 100,
    "slot_types": {
        "origin": {"type": "string", "format": "city"},
        "destination": {"type": "string", "format": "city"},
        "departure_date": {"type": "date", "format": "YYYY-MM-DD"},
        "duration_days": {"type": "integer", "format": "number"},
        "adults": {"type": "integer", "format": "number"},
        "return_date": {"type": "date", "format": "YYYY-MM-DD"},
        "children": {"type": "integer", "format": "number"},
    }
}




@tool_error_handler(tool_name="travel_search_flights", error_message="Failed to search flights")
async def travel_search_flights(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate Expedia flight search PLP link.

    Reads from state:
        - slots: Contains origin, destination, departure_date, return_date, adults, children

    Returns:
        {
            "flights": [{
                "type": "plp_link",
                "provider": "expedia",
                "origin": str,
                "destination": str,
                "search_url": str,
                "title": str
            }],
            "citations": [...],
            "success": bool
        }
    """
    try:
        # Read from state
        slots = state.get("slots", {})
        origin = slots.get("origin")
        destination = slots.get("destination")
        departure_date = slots.get("departure_date")
        return_date = slots.get("return_date", "")
        duration_days = slots.get("duration_days")
        adults = slots.get("adults", 1)
        children = slots.get("children", 0)

        # Calculate return_date from departure_date + duration_days if not provided
        if not return_date and duration_days and departure_date:
            try:
                dep_date = datetime.strptime(departure_date, "%Y-%m-%d")
                ret_date = dep_date + timedelta(days=int(duration_days))
                return_date = ret_date.strftime("%Y-%m-%d")
                logger.info(f"[travel_search_flights] Calculated return_date={return_date} from departure_date={departure_date} + duration_days={duration_days}")
            except Exception as e:
                logger.warning(f"[travel_search_flights] Could not calculate return_date: {e}")

        logger.info(f"[travel_search_flights] Generating Expedia PLP link for flights: {origin} -> {destination}")

        # Convert date strings to date objects
        depart_date_obj = datetime.strptime(departure_date, "%Y-%m-%d").date() if departure_date else None
        return_date_obj = datetime.strptime(return_date, "%Y-%m-%d").date() if return_date else None

        # Determine trip type for title
        trip_type = "Round-trip" if return_date else "One-way"

        # Loop over all registered PLP flight providers
        flights = []
        citations = []

        plp_generators = {
            "expedia_plp": ExpediaPLPLinkGenerator.generate_flight_search_url,
        }

        for provider_key, generate_fn in plp_generators.items():
            try:
                search_url = generate_fn(
                    origin=origin,
                    destination=destination,
                    departure_date=depart_date_obj,
                    return_date=return_date_obj,
                    passengers=adults + children,
                    cabin_class="economy",
                )
                provider_label = provider_key.replace("_plp", "")
                flight_result = {
                    "type": "plp_link",
                    "provider": provider_label,
                    "origin": origin,
                    "destination": destination,
                    "search_url": search_url,
                    "title": f"{trip_type} flights from {origin} to {destination}",
                    "departure_date": departure_date,
                    "return_date": return_date,
                    "passengers": adults + children,
                }
                flights.append(flight_result)
                citations.append(search_url)
                logger.info(f"[travel_search_flights] Generated {provider_label} flight search URL: {search_url}")
            except Exception as e:
                logger.warning(f"[travel_search_flights] Provider {provider_key} failed: {e}")

        return {
            "flights": flights,
            "citations": citations,
            "success": len(flights) > 0,
        }

    except Exception as e:
        logger.error(f"[travel_search_flights] Error: {e}", exc_info=True)
        return {
            "flights": [],
            "citations": [],
            "error": str(e),
            "success": False
        }
