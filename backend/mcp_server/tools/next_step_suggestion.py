"""
Next Step Suggestion Tool

Generates relevant follow-up questions based on conversation history and current intent.
This tool should be used at the end of every response to suggest next actions.
"""

from app.core.centralized_logger import get_logger
import sys
import os
import json
from typing import Dict, Any, List
from app.core.error_manager import tool_error_handler

# Add backend to path (portable path)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.services.model_service import model_service
from app.services.prompts.voice import build_system_prompt
from app.core.config import settings

logger = get_logger(__name__)

# Tool contract for planner - available for ALL intents
TOOL_CONTRACT = {
    "name": "next_step_suggestion",
    "intent": "all",
    "purpose": "Generate follow-up questions to display at the end of every response. MUST be called as the LAST tool in every plan after the compose tool.",
    "tools": {
        "pre": [],  # Auto-added at very end of all intents
        "post": []
    },
    "produces": ["next_suggestions"],
    "citation_message": "Reading the room…",
    "tool_order": 900,
    "is_default": True,
    "is_required": True
}


def _build_conversation_context(state: Dict[str, Any]) -> str:
    """
    Build conversation context from history + current response.

    The current assistant_text is already in state (set by compose tool that runs before this).
    conversation_history contains previous messages but NOT the current response.

    Args:
        state: Current state with conversation_history and assistant_text

    Returns:
        Formatted conversation context string
    """
    # Get conversation history from state (already limited by ChatHistoryManager)
    conversation_history = state.get("conversation_history", [])
    user_message = state.get("user_message", "")
    assistant_text = state.get("assistant_text", "")  # Current response from compose tool

    # Use history from state directly (already limited)
    recent_messages = conversation_history if conversation_history else []

    # Build context: history + current turn
    history_parts = []

    # Add previous messages from history - NO TRUNCATION
    # The LLM needs to see full context to know what was already done
    for msg in recent_messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")  # Full content, no truncation
        history_parts.append(f"{role.capitalize()}: {content}")

    # Add current turn (user message + assistant response) - NO TRUNCATION
    if user_message:
        history_parts.append(f"User: {user_message}")
    if assistant_text:
        history_parts.append(f"Assistant: {assistant_text}")

    return "\n".join(history_parts) if history_parts else f"User: {user_message}"


def _get_intent_specific_guidance(intent: str, slots: Dict[str, Any]) -> str:
    """
    Get intent-specific guidance for generating relevant follow-up questions.
    Dynamically loads available tool capabilities from contracts.

    Args:
        intent: Current intent (travel, product, general, intro)
        slots: Current slots/preferences

    Returns:
        Guidance string for the LLM
    """
    # Import here to avoid circular dependency
    sys.path.insert(0, os.path.join(backend_dir, 'mcp_server'))
    from tool_contracts import _get_contracts_cached

    # Get all entry-point tools for this intent (tools with no pre dependencies)
    all_contracts = _get_contracts_cached()
    intent_tools = [
        c for c in all_contracts
        if (c.get("intent") == intent or c.get("intent") == "all")
        and c.get("name") != "next_step_suggestion"
        and not c.get("tools", {}).get("pre", [])  # Only entry-point tools (no pre dependencies)
    ]

    if not intent_tools:
        return "Suggest helpful follow-up questions based on the conversation context."

    # Build capabilities list from tool purposes
    capabilities = []
    for tool in intent_tools:
        tool_name = tool.get("name", "")
        purpose = tool.get("purpose", "")
        if purpose:
            capabilities.append(f"- {tool_name}: {purpose}")

    capabilities_text = "\n".join(capabilities)

    if intent == "travel":
        destination = slots.get("destination", "the destination")
        return f"""You are suggesting follow-up questions for TRAVEL intent about {destination}.

AVAILABLE CAPABILITIES - suggest questions based on these tools only:
{capabilities_text}

IMPORTANT:
- ONLY suggest questions that can be answered by the tools listed above
- Be specific to {destination} when relevant
- Use conversational tone ("Would you like...", "Shall I...", "Interested in...")
- Keep questions short (under 15 words)
- DO NOT suggest questions about capabilities not listed above"""

    elif intent == "product":
        product_type = slots.get("product_type", "products")

        # Detect unfilled slots for criteria-narrowing suggestions
        product_slots = ["budget", "brand", "features", "use_case", "size", "color", "material", "style", "gender"]
        filled = [s for s in product_slots if slots.get(s)]
        unfilled = [s for s in product_slots if not slots.get(s)]

        unfilled_hint = ""
        if unfilled:
            examples = {
                "budget": "a specific budget range",
                "brand": "a brand preference",
                "features": "specific features (e.g., wireless, waterproof)",
                "use_case": "how they plan to use it",
                "size": "a size preference",
                "color": "a color preference",
                "material": "a material preference",
                "style": "a style (casual, professional, gaming)",
                "gender": "who it's for",
            }
            hints = [examples[s] for s in unfilled[:3]]
            unfilled_hint = f"\n\nUNFILLED CRITERIA the user hasn't specified yet (suggest asking about these):\n- " + "\n- ".join(hints)

        return f"""You are suggesting follow-up questions for PRODUCT intent about {product_type}.

AVAILABLE CAPABILITIES - suggest questions based on these tools only:
{capabilities_text}
{unfilled_hint}

IMPORTANT:
- One suggestion should narrow by an unfilled criterion (budget, features, use case, etc.)
- One suggestion should reference a specific product from the results if product names are provided below
- ONLY suggest questions that can be answered by the tools listed above
- Be specific to {product_type} when relevant
- Use conversational tone ("Would you like...", "Want to...", "Interested in...", "Do you have...")
- Keep questions short (under 15 words)
- DO NOT suggest questions about capabilities not listed above"""

    elif intent == "general":
        return f"""You are suggesting follow-up questions for GENERAL intent.

AVAILABLE CAPABILITIES - suggest questions based on these tools only:
{capabilities_text}

IMPORTANT:
- Suggest questions that dive deeper or explore related topics
- Use conversational tone
- Keep questions short (under 15 words)"""

    else:  # intro or unknown
        return """Suggest diverse questions that showcase different capabilities:
- A travel planning question
- A product recommendation question
- A general information question"""


def _build_refinement_suggestions(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Outcome 2: deterministic slot-aware refinement chips after product results.

    Built from last_search_context (written to shared state by product_compose)
    rather than the LLM — so they're always grounded in the actual shortlist,
    cost nothing, and never miss the 2s background-task timeout. The clarifier
    recognizes each chip's text and adjusts the inherited slots so the search
    re-runs WITHOUT re-asking answered questions:

      "Show cheaper options"  → budget ceiling below the cheapest shown price
      "More premium picks"    → budget floor above the priciest shown price
      "Only <brand>"          → brand slot pinned to the top pick's brand
      "Different use case"    → re-asks the use_case question only
    """
    ctx = state.get("last_search_context") or {}
    product_names = ctx.get("product_names") or []
    top_prices = ctx.get("top_prices") or {}
    if not product_names and not top_prices:
        return []

    suggestions = [
        {
            "id": "refine_cheaper",
            "question": "Show cheaper options",
            "category": "refine_budget",
            "confidence": 0.95,
        },
        {
            "id": "refine_premium",
            "question": "More premium picks",
            "category": "refine_budget",
            "confidence": 0.9,
        },
    ]

    # "Only <brand>" — brand = leading word of the top pick's name ("Sony
    # WH-1000XM5" → "Sony"). Skip when it doesn't look like a brand word.
    if product_names:
        brand = str(product_names[0]).split()[0].strip()
        if brand and brand[0].isupper() and len(brand) >= 3 and not any(c.isdigit() for c in brand):
            suggestions.append({
                "id": "refine_brand",
                "question": f"Only {brand}",
                "category": "refine_features",
                "confidence": 0.85,
            })

    suggestions.append({
        "id": "refine_use_case",
        "question": "Different use case",
        "category": "clarify",
        "confidence": 0.8,
    })
    return suggestions


async def next_step_suggestion(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate relevant follow-up questions based on conversation history.

    This tool analyzes the conversation context and generates 2 relevant
    follow-up questions that the user might want to ask next.

    Reads from state:
        - intent: Current intent (travel, product, general, intro)
        - conversation_history: Recent conversation messages
        - user_message: Current user message
        - assistant_text: The composed response being shown to user
        - slots: Current slots/preferences
        - ui_blocks: UI blocks being displayed (optional)

    Writes to state:
        - next_suggestions: List of suggested follow-up questions

    Returns:
        {
            "next_suggestions": [...],
            "success": bool
        }
    """
    try:
        # Read from state
        intent = state.get("intent", "general")
        user_message = state.get("user_message", "")
        assistant_text = state.get("assistant_text", "")
        slots = state.get("slots", {})
        ui_blocks = state.get("ui_blocks", [])

        # Gather top product names for product-specific suggestions
        product_names = state.get("product_names", [])
        normalized_products = state.get("normalized_products", [])
        top_product_names = [p.get("name", "") for p in (normalized_products or [])[:3] if p.get("name")] or product_names[:3]

        logger.info(f"[next_step_suggestion] Generating suggestions for intent={intent}")

        # Outcome 2: when a product shortlist was just rendered, the deterministic
        # slot-aware refinement chips ARE the next-step suggestions. Skip the LLM
        # call entirely — instant (always beats the 2s background-task timeout),
        # free, and grounded in the actual results.
        if intent == "product":
            refinement_suggestions = _build_refinement_suggestions(state)
            if refinement_suggestions:
                logger.info(
                    f"[next_step_suggestion] Using {len(refinement_suggestions)} deterministic "
                    f"refinement chips (skipping LLM): {[s['question'] for s in refinement_suggestions]}"
                )
                return {
                    "next_suggestions": refinement_suggestions,
                    "success": True
                }

        # Build conversation context
        conversation_context = _build_conversation_context(state)
        logger.info(f"[next_step_suggestion] Conversation context length: {len(conversation_context)} chars")
        logger.debug(f"[next_step_suggestion] Full conversation context:\n{conversation_context}")

        # Get intent-specific guidance
        intent_guidance = _get_intent_specific_guidance(intent, slots)
        logger.info(f"[next_step_suggestion] Intent guidance:\n{intent_guidance}")

        # Determine what was shown to user - use title from UI block or format type name
        content_shown = []
        for block in ui_blocks:
            block_title = block.get("title", "")
            block_type = block.get("type", "")
            if block_title:
                content_shown.append(block_title.lower())
            elif block_type:
                # Convert type like "ebay_products" to "ebay products"
                content_shown.append(block_type.replace("_", " "))

        content_summary = ", ".join(content_shown) if content_shown else "information"

        prompt = f"""You are a helpful assistant generating follow-up questions for a user.

CONVERSATION HISTORY:
{conversation_context}

CURRENT CONTEXT:
- Intent: {intent}
- User's current request: {user_message}
- Content shown to user: {content_summary}
- User preferences: {json.dumps(slots, default=str) if slots else "None specified"}
- Top products shown: {', '.join(top_product_names) if top_product_names else 'N/A'}

GUIDANCE FOR {intent.upper()} INTENT:
{intent_guidance}

TASK:
Generate exactly 2 natural, helpful follow-up questions that:
1. Are directly relevant to what the user just asked about
2. Would help the user explore related topics or take next steps
3. Feel conversational and warm (use "Would you like..." or "Shall I..." tone)
4. Are specific to the context, NOT generic

CRITICAL RULES - READ THE CONVERSATION HISTORY CAREFULLY:
- Analyze the conversation history to understand what information has ALREADY been provided to the user
- DO NOT suggest questions about topics, information, or actions that were ALREADY addressed in previous messages
- Look for what the assistant has already shown, created, searched for, or recommended
- ONLY suggest questions that lead to NEW information or actions not yet taken
- If the user already received something, suggest the logical NEXT step, not a repeat of what was done
- Questions should be SHORT (under 15 words each)
- Each question should lead to a different type of action
- Make them feel like a helpful friend suggesting next steps

CATEGORY ASSIGNMENT (RFC §2.4):
Each suggestion must include a "category" field. Choose the best-fitting category:
- "clarify"              — asks for missing information needed to refine results (e.g. budget, use case, preferences)
- "refine_budget"        — specifically narrows by price or budget range
- "refine_features"      — narrows by technical features, specs, or attributes
- "alternate_destination" — suggests a different destination or alternative option (travel intent)
- "compare"             — compares two or more products, destinations, or options head-to-head
- "deeper_research"     — digs into reviews, expert opinions, or detailed analysis

Also include a "confidence" field (float 0.0–1.0) reflecting how confident you are the user will find this suggestion useful in context.

Return ONLY valid JSON:
{{
  "next_suggestions": [
    {{
      "id": "suggestion_1",
      "question": "Your follow-up question here?",
      "category": "clarify",
      "confidence": 0.9
    }},
    {{
      "id": "suggestion_2",
      "question": "Another follow-up question?",
      "category": "compare",
      "confidence": 0.75
    }}
  ]
}}"""

        suggestion_role = (
            "You generate contextual follow-up suggestions that the user "
            "could tap as next-step chips. Each suggestion must reference "
            "something specific from the conversation — a product just "
            "discussed, a tradeoff surfaced, a constraint the user mentioned. "
            "Avoid generic offers ('Anything else?', 'Want to dig deeper?'). "
            "Return JSON in the schema specified by the user prompt."
        )
        # Generate suggestions using LLM
        response = await model_service.generate(
            messages=[
                {"role": "system", "content": build_system_prompt(role_prompt=suggestion_role, kind="snippet")},
                {"role": "user", "content": prompt}
            ],
            model=settings.DEFAULT_MODEL,
            temperature=0.7,
            max_tokens=300,
            response_format={"type": "json_object"},
            agent_name="next_step_suggestion"
        )

        data = json.loads(response)
        suggestions = data.get("next_suggestions", [])[:2]  # Limit to max 2 questions

        logger.info(f"[next_step_suggestion] Generated {len(suggestions)} suggestions:")
        for i, s in enumerate(suggestions):
            category = s.get('category', 'uncategorized')
            confidence = s.get('confidence', 'N/A')
            logger.info(f"  {i+1}. [{category}] (conf={confidence}) {s.get('question', 'N/A')}")

        return {
            "next_suggestions": suggestions,
            "success": True
        }

    except Exception as e:
        logger.error(f"[next_step_suggestion] Error: {e}", exc_info=True)
        return {
            "next_suggestions": [],
            "error": str(e),
            "success": False
        }
