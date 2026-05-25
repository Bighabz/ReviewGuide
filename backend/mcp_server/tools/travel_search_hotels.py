"""
Travel Search Hotels Tool

Generates Expedia PLP (Product Listing Page) search links for hotels.
Returns affiliate search links instead of individual hotel cards.
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
from app.services.travel.registry import ProviderRegistry
from app.services.travel.loader import _auto_import_providers
from app.core.config import settings

logger = get_logger(__name__)

# Ensure all provider modules are imported so decorators fire
_auto_import_providers()

# Tool contract for planner
TOOL_CONTRACT = {
    "name": "travel_search_hotels",
    "purpose": "Search for hotels deals, offers",
    "intent": "travel",
    "tools": {
        "pre": [],  # Entry-point tool - no dependencies
        "post": []  # Compose is auto-added at end of intent
    },
    "produces": ["hotels"],
    "required_slots": ["destination", "duration_days", "adults", "check_in"],
    "optional_slots": ["check_out", "return_date", "children"],
    "slot_replacements": {
        "check_in": "departure_date",
        "check_out": "return_date",
    },
    "citation_message": "Asking around…",
    "tool_order": 100,
    "slot_types": {
        "destination": {"type": "string", "format": "city"},
        "duration_days": {"type": "integer", "format": "number"},
        "adults": {"type": "integer", "format": "number"},
        "check_in": {"type": "date", "format": "YYYY-MM-DD"},
        "check_out": {"type": "date", "format": "YYYY-MM-DD"},
        "return_date": {"type": "date", "format": "YYYY-MM-DD"},
        "children": {"type": "integer", "format": "number"},
    }
}




@tool_error_handler(tool_name="travel_search_hotels", error_message="Failed to search hotels")
async def travel_search_hotels(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate Expedia hotel search PLP link.

    Reads from state:
        - slots: Contains destination, check_in, check_out, adults, children

    Returns:
        {
            "hotels": [{
                "type": "plp_link",
                "provider": "expedia",
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
        destination = slots.get("destination")
        check_in = slots.get("check_in", "")
        check_out = slots.get("check_out", "")
        return_date = slots.get("return_date", "")
        departure_date = slots.get("departure_date", "")
        duration_days = slots.get("duration_days")
        adults = slots.get("adults", 2)
        children = slots.get("children", 0)

        # Determine check_in date with fallback logic:
        # 1. Use check_in if provided
        # 2. Otherwise use departure_date if provided
        if not check_in and departure_date:
            check_in = departure_date

        # Determine check_out date with fallback logic:
        # 1. Use check_out if provided
        # 2. Otherwise use return_date if provided
        # 3. Otherwise calculate from check_in + duration_days
        if not check_out:
            if return_date:
                check_out = return_date
            elif duration_days and check_in:
                try:
                    checkin_date = datetime.strptime(check_in, "%Y-%m-%d")
                    checkout_date = checkin_date + timedelta(days=int(duration_days))
                    check_out = checkout_date.strftime("%Y-%m-%d")
                    logger.info(f"[travel_search_hotels] Calculated check_out={check_out} from check_in={check_in} + duration_days={duration_days}")
                except Exception as e:
                    logger.warning(f"[travel_search_hotels] Could not calculate check_out: {e}")
                    check_out = ""
            else:
                check_out = ""

        logger.info(f"[travel_search_hotels] Generating Expedia PLP link for hotels in {destination}")

        # Convert date strings to date objects
        check_in_obj = datetime.strptime(check_in, "%Y-%m-%d").date() if check_in else None
        check_out_obj = datetime.strptime(check_out, "%Y-%m-%d").date() if check_out else None

        # Loop over all registered PLP hotel providers
        hotels = []
        citations = []

        # Map provider name -> link generator for PLP providers
        plp_generators = {
            "expedia_plp": ExpediaPLPLinkGenerator.generate_hotel_search_url,
        }

        # Add Booking.com PLP if configured
        if settings.BOOKING_AFFILIATE_ID:
            try:
                from app.services.travel.providers.booking_plp_provider import BookingPLPLinkGenerator
                plp_generators["booking_plp"] = BookingPLPLinkGenerator.generate_hotel_search_url
            except Exception as e:
                logger.warning(f"[travel_search_hotels] Could not load Booking PLP provider: {e}")

        for provider_key, generate_fn in plp_generators.items():
            try:
                search_url = generate_fn(
                    destination=destination,
                    check_in=check_in_obj,
                    check_out=check_out_obj,
                    guests=adults + children,
                    rooms=1,
                )
                provider_label = provider_key.replace("_plp", "")
                hotel_result = {
                    "type": "plp_link",
                    "provider": provider_label,
                    "destination": destination,
                    "search_url": search_url,
                    "title": f"Hotels in {destination}",
                    "check_in": check_in,
                    "check_out": check_out,
                    "guests": adults + children,
                }
                hotels.append(hotel_result)
                citations.append(search_url)
                logger.info(f"[travel_search_hotels] Generated {provider_label} hotel search URL: {search_url}")
            except Exception as e:
                logger.warning(f"[travel_search_hotels] Provider {provider_key} failed: {e}")

        return {
            "hotels": hotels,
            "citations": citations,
            "success": len(hotels) > 0,
        }

    except Exception as e:
        logger.error(f"[travel_search_hotels] Error: {e}", exc_info=True)
        return {
            "hotels": [],
            "citations": [],
            "error": str(e),
            "success": False
        }
