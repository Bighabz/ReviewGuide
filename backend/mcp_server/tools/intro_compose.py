"""
Intro Compose Tool

Generates and returns introduction/greeting response directly to customer using LLM.
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

from app.services.model_service import model_service
from app.services.prompts.voice import build_system_prompt
from app.core.config import settings

logger = get_logger(__name__)

# Tool contract for planner
TOOL_CONTRACT = {
    "name": "intro_compose",
    "intent": "intro",
    "purpose": "Generate and return introduction/greeting response to customer",
    "tools": {
        "pre": [],
        "post": []
    },
    "produces": ["assistant_text"],
    "tool_order": 800,
    "is_default": True,
    "is_required": True
}


@tool_error_handler(tool_name="intro_compose", error_message="Failed to compose intro response")
async def intro_compose(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate introduction text and return it directly to customer using LLM.

    Args:
        state: State dict (no specific inputs required)

    Returns:
        {
            "success": bool,
            "assistant_text": str  # Final text to display to customer
        }
    """
    try:
        logger.info("Generating intro response...")

        # Prompt for generating minimal, one-screen introduction
        intro_role = (
            "You are ReviewGuide and you just opened a chat with this person. "
            "Welcome them in 2-3 sentences. Mention you help with product "
            "reviews, travel planning, and general information. Include three "
            "diverse example questions as bullet points. End with one short "
            "contextual invitation — not a generic 'how can I help'. Keep it "
            "to one screen; no long capability lists."
        )
        user_prompt = (
            "Generate the welcome message now. Return only the message text — "
            "no JSON, no preamble, no closing meta-commentary."
        )

        # Generate intro using model service
        intro_message = await model_service.generate(
            messages=[
                {"role": "system", "content": build_system_prompt(role_prompt=intro_role, kind="response")},
                {"role": "user", "content": user_prompt}
            ],
            model=settings.COMPOSER_MODEL,
            temperature=0.7,
            max_tokens=300,
            agent_name="intro"
        )

        logger.info(f"✅ Intro message generated successfully")

        return {
            "success": True,
            "assistant_text": intro_message
        }

    except Exception as e:
        logger.error(f"Error generating intro: {str(e)}", exc_info=True)
        # Fallback to minimal hardcoded intro
        fallback_message = """Hello 👋
I'm your smart assistant for reviews, product discovery, and trip planning.

Try asking:
• "Best Dyson for pet hair?"
• "Top things to do in Tokyo"
• "Compare iPhone vs Samsung"

Ask anything — I'll guide you."""

        return {
            "success": True,
            "assistant_text": fallback_message
        }
