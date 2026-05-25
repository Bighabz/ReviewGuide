"""
Travel Search Cars Tool

Generates Expedia PLP (Product Listing Page) search links for car rentals.
Returns affiliate search links instead of individual car listings.
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
    "name": "travel_search_cars",
    "purpose": "Search for rental car deals",
    "intent": "travel",
    "tools": {
        "pre": [],  # Entry-point tool - no dependencies
        "post": []  # Compose is auto-added at end of intent
    },
    "produces": ["cars"],
    "required_slots": ["destination"],
    "optional_slots": ["departure_date", "duration_days", "return_date"],
    "citation_message": "Asking around…",
    "tool_order": 100,
    "slot_types": {
        "destination": {"type": "string", "format": "city"},
        "departure_date": {"type": "date", "format": "YYYY-MM-DD"},
        "duration_days": {"type": "integer", "format": "number"},
        "return_date": {"type": "date", "format": "YYYY-MM-DD"},
    }
}


@tool_error_handler(tool_name="travel_search_cars", error_message="Failed to search rental cars")
async def travel_search_cars(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate Expedia car rental search PLP link.

    Reads from state:
        - slots: Contains destination, departure_date, return_date, duration_days

    Returns:
        {
            "cars": [{
                "type": "plp_link",
                "provider": "expedia",
                "location": str,
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
        destination = slots.get("destination", "")
        departure_date = slots.get("departure_date")
        return_date = slots.get("return_date", "")
        duration_days = slots.get("duration_days")

        # Calculate return_date from departure_date + duration_days if not provided
        if not return_date and duration_days and departure_date:
            try:
                dep_date = datetime.strptime(departure_date, "%Y-%m-%d")
                ret_date = dep_date + timedelta(days=int(duration_days))
                return_date = ret_date.strftime("%Y-%m-%d")
                logger.info(f"[travel_search_cars] Calculated return_date={return_date} from departure_date={departure_date} + duration_days={duration_days}")
            except Exception as e:
                logger.warning(f"[travel_search_cars] Could not calculate return_date: {e}")

        logger.info(f"[travel_search_cars] Generating Expedia PLP link for car rental in: {destination}")

        # Convert date strings to date objects
        pickup_date_obj = datetime.strptime(departure_date, "%Y-%m-%d").date() if departure_date else None
        dropoff_date_obj = datetime.strptime(return_date, "%Y-%m-%d").date() if return_date else None

        # Loop over all registered PLP car rental providers
        cars = []
        citations = []

        plp_generators = {
            "expedia_plp": ExpediaPLPLinkGenerator.generate_car_rental_search_url,
        }

        for provider_key, generate_fn in plp_generators.items():
            try:
                search_url = generate_fn(
                    location=destination,
                    pickup_date=pickup_date_obj,
                    dropoff_date=dropoff_date_obj,
                )
                provider_label = provider_key.replace("_plp", "")
                car_result = {
                    "type": "plp_link",
                    "provider": provider_label,
                    "location": destination,
                    "search_url": search_url,
                    "title": f"Rental cars in {destination}",
                    "pickup_date": departure_date,
                    "dropoff_date": return_date,
                }
                cars.append(car_result)
                citations.append(search_url)
                logger.info(f"[travel_search_cars] Generated {provider_label} car rental search URL: {search_url}")
            except Exception as e:
                logger.warning(f"[travel_search_cars] Provider {provider_key} failed: {e}")

        return {
            "cars": cars,
            "citations": citations,
            "success": len(cars) > 0,
        }

    except Exception as e:
        logger.error(f"[travel_search_cars] Error: {e}", exc_info=True)
        return {
            "cars": [],
            "citations": [],
            "error": str(e),
            "success": False
        }
