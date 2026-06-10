"""
MCP Server for ReviewGuide.ai

Single MCP server exposing all tools as individual functions.

# Tool output convention (RFC §1.6):
# New tools MUST write results under:
#   return {"tool_outputs": {"<tool_name>": {"key": value, ...}}}
# NOT flat keys. Existing tools keep flat keys during transition.
"""

import asyncio
import sys
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging using centralized logger
from app.core.centralized_logger import get_logger
from app.core.logging_config import setup_logging

# Setup logging for MCP server (outputs to stderr for MCP protocol)
# CRITICAL: MCP servers MUST use stderr for logs to avoid breaking JSON-RPC on stdout
setup_logging(log_level="INFO", use_json=False, use_colors=True, enabled=True, use_stderr=True)
logger = get_logger("mcp_server")

# Initialize MCP server
app = Server("reviewguide-mcp")

# Import all tool functions
from tools.product_search import product_search
from tools.product_evidence import product_evidence
from tools.product_affiliate import product_affiliate
from tools.product_ranking import product_ranking
from tools.product_normalize import product_normalize
from tools.product_compose import product_compose
from tools.product_comparison import product_comparison
from tools.general_search import general_search
from tools.general_compose import general_compose
from tools.travel_itinerary import travel_itinerary
from tools.travel_search_hotels import travel_search_hotels
from tools.travel_search_flights import travel_search_flights
from tools.travel_search_cars import travel_search_cars
from tools.travel_destination_facts import travel_destination_facts
from tools.travel_compose import travel_compose
from tools.intro_compose import intro_compose
from tools.unclear_compose import unclear_compose
from tools.next_step_suggestion import next_step_suggestion
from tools.review_search import review_search
from tools.strain_search import strain_search
from tools.strain_compose import strain_compose


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List all available MCP tools."""
    # All tools now use state-based execution - they receive the entire state object
    # and read what they need from it
    state_schema = {
        "type": "object",
        "properties": {
            "state": {
                "type": "object",
                "description": "Shared state object containing all workflow data"
            }
        },
        "required": ["state"]
    }

    tools = [
        # Product tools
        Tool(
            name="product_search",
            description="Search for products on the web/catalog. Reads: user_message, slots. Writes: search_results, products.",
            inputSchema=state_schema
        ),
        Tool(
            name="review_search",
            description="Search for real product reviews from trusted editorial and community sources. Reads: product_names, slots. Writes: review_data.",
            inputSchema=state_schema
        ),
        Tool(
            name="product_evidence",
            description="Analyze product reviews for pros/cons. Reads: products. Writes: review_aspects.",
            inputSchema=state_schema
        ),
        # Strain tools (SmartVape cannabis vertical)
        Tool(
            name="strain_search",
            description="Recommend, compare, or find similar cannabis strains from the in-house strain database. Reads: user_message, slots. Writes: strain_results, strain_mode.",
            inputSchema=state_schema
        ),
        Tool(
            name="strain_compose",
            description="Generate the final strain recommendation response with verdict prose and Leafly link-out cards. Reads: strain_results, strain_mode. Writes: assistant_text, ui_blocks.",
            inputSchema=state_schema
        ),
        Tool(
            name="product_affiliate",
            description="Find affiliate/monetized links. Reads: normalized_products. Writes: affiliate_links. IMPORTANT: Must run AFTER product_normalize to get merged affiliate data into products.",
            inputSchema=state_schema
        ),
        Tool(
            name="product_ranking",
            description="Rank products by quality. Reads: search_results, review_aspects. Writes: ranked_items.",
            inputSchema=state_schema
        ),
        Tool(
            name="product_normalize",
            description="Merge product data from all sources (evidence, ranking) into normalized format. Reads: search_results, review_aspects, ranked_items. Writes: normalized_products. IMPORTANT: Must run BEFORE product_affiliate.",
            inputSchema=state_schema
        ),
        Tool(
            name="product_compose",
            description="Format final product response and merge affiliate links into products. Reads: user_message, normalized_products, affiliate_links. Writes: assistant_text, ui_blocks, citations.",
            inputSchema=state_schema
        ),
        Tool(
            name="product_comparison",
            description="Compare products side-by-side when customer asks to compare products. Reads: user_message, affiliate_products, conversation_history. Writes: comparison_table, assistant_text, ui_blocks.",
            inputSchema=state_schema
        ),

        # General tools
        Tool(
            name="general_search",
            description="Web search for factual information, specifications, definitions (intent=general ONLY). Reads: user_message. Writes: search_results, search_query.",
            inputSchema=state_schema
        ),
        Tool(
            name="general_compose",
            description="Generate final text response for general information queries (intent=general ONLY). Reads: user_message, search_results. Writes: assistant_text, ui_blocks, citations.",
            inputSchema=state_schema
        ),

        # Travel tools
        Tool(
            name="travel_itinerary",
            description="Generate day-by-day travel itinerary. Reads: destination, duration_days from slots. Writes: itinerary.",
            inputSchema=state_schema
        ),
        Tool(
            name="travel_search_hotels",
            description="Search for hotel options. Reads: destination, check_in, check_out from slots. Writes: hotels.",
            inputSchema=state_schema
        ),
        Tool(
            name="travel_search_flights",
            description="Search for flight options. Reads: origin, destination, dates from slots. Writes: flights.",
            inputSchema=state_schema
        ),
        Tool(
            name="travel_search_cars",
            description="Search for rental car options. Reads: destination, departure_date, return_date from slots. Writes: cars.",
            inputSchema=state_schema
        ),
        Tool(
            name="travel_destination_facts",
            description="Get destination facts (weather, best season, tips). Reads: destination, month from slots. Writes: destination_facts.",
            inputSchema=state_schema
        ),
        Tool(
            name="travel_compose",
            description="Format final travel response. Reads: user_message, itinerary, hotels, flights. Writes: assistant_text, ui_blocks.",
            inputSchema=state_schema
        ),

        # Intro tool
        Tool(
            name="intro_compose",
            description="Generate and return introduction/greeting response directly to customer using LLM. Reads: user_message (optional). Writes: assistant_text.",
            inputSchema=state_schema
        ),

        # Unclear tool
        Tool(
            name="unclear_compose",
            description="Generate a friendly message asking user to enter meaningful text when gibberish/unclear input is detected. Reads: user_message. Writes: assistant_text.",
            inputSchema=state_schema
        ),

        # Meta tools
        Tool(
            name="next_step_suggestion",
            description="Suggest next actions to user. Reads: intent, recent_tools. Writes: suggestions.",
            inputSchema=state_schema
        )
    ]

    logger.info(f"Listing {len(tools)} available tools")
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool execution requests.

    All tools now receive the entire state object and read what they need.
    Arguments should contain a 'state' key with the shared state dict.

    NOTE: This MCP server is kept for potential future MCP protocol support,
    but tools are currently called directly in-process via plan_executor.
    """
    logger.info(f"Tool called: {name}")

    try:
        # Extract state from arguments
        state = arguments.get("state", {})

        # Route to appropriate tool function - all tools receive state
        if name == "product_search":
            result = await product_search(state)
        elif name == "review_search":
            result = await review_search(state)
        elif name == "strain_search":
            result = await strain_search(state)
        elif name == "strain_compose":
            result = await strain_compose(state)
        elif name == "product_evidence":
            result = await product_evidence(state)
        elif name == "product_affiliate":
            result = await product_affiliate(state)
        elif name == "product_ranking":
            result = await product_ranking(state)
        elif name == "product_normalize":
            result = await product_normalize(state)
        elif name == "product_compose":
            result = await product_compose(state)
        elif name == "product_comparison":
            result = await product_comparison(state)
        elif name == "general_search":
            result = await general_search(state)
        elif name == "general_compose":
            result = await general_compose(state)
        elif name == "travel_itinerary":
            result = await travel_itinerary(state)
        elif name == "travel_search_hotels":
            result = await travel_search_hotels(state)
        elif name == "travel_search_flights":
            result = await travel_search_flights(state)
        elif name == "travel_search_cars":
            result = await travel_search_cars(state)
        elif name == "travel_destination_facts":
            result = await travel_destination_facts(state)
        elif name == "travel_compose":
            result = await travel_compose(state)
        elif name == "intro_compose":
            result = await intro_compose(state)
        elif name == "unclear_compose":
            result = await unclear_compose(state)
        elif name == "next_step_suggestion":
            result = await next_step_suggestion(state)
        else:
            raise ValueError(f"Unknown tool: {name}")

        logger.info(f"Tool {name} completed")

        # Log the complete output (minified, no indent)
        import json
        result_json = json.dumps(result, ensure_ascii=False)
        logger.info(f"[TOOL OUTPUT: {name}] {result_json}")

        # Return result as TextContent
        return [TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2)
        )]

    except Exception as e:
        logger.error(f"Tool {name} failed: {str(e)}", exc_info=True)
        import json
        error_result = {"error": str(e), "tool": name, "success": False}
        return [TextContent(type="text", text=json.dumps(error_result, ensure_ascii=False, indent=2))]


async def main():
    """Run the MCP server via stdio"""
    logger.info("Starting ReviewGuide MCP Server...")

    # Initialize search provider
    import sys
    import os

    # Add backend to path (portable path)
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    # Load .env explicitly before initializing search provider
    from dotenv import load_dotenv
    env_path = os.path.join(backend_dir, '.env')
    load_dotenv(env_path)
    logger.info(f"Loaded .env from {env_path}")

    from app.services.search.config import setup_search_provider
    setup_search_provider()
    logger.info("Search provider initialized for MCP server")

    # Initialize travel providers
    from app.services.travel.loader import setup_providers
    setup_providers(use_env=True)
    logger.info("Travel providers initialized for MCP server")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
