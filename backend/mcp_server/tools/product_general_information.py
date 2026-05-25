"""
Product General Information Tool

Fallback tool for product knowledge questions that other specialized tools cannot answer.
Only used when product_search, product_comparison, and product_ranking cannot help.
"""

import sys
import os
import json
from typing import Dict, Any
from app.core.error_manager import tool_error_handler

# Add backend to path (portable path)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Tool contract for planner
TOOL_CONTRACT = {
    "name": "product_general_information",
    "intent": "product",
    "purpose": "Answer general product questions",
    "not_for": ["product search", "product comparison"],
    "tools": {
        "pre": [],  # Entry-point tool - no dependencies
        "post": []  # Compose is auto-added at end of intent
    },
    "produces": ["general_product_info"],
    "citation_message": "Digging for answers…",
    "tool_order": 150  # Lower priority - fallback tool
}


@tool_error_handler(tool_name="product_general_information", error_message="Failed to search product information")
async def product_general_information(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for general product knowledge using web search.

    Reads from state:
        - user_message: User's question
        - slots: Optional structured data

    Writes to state:
        - general_product_info: Information gathered from search

    Returns:
        {
            "general_product_info": str,
            "success": bool
        }
    """
    from app.core.centralized_logger import get_logger
    from app.services.model_service import model_service
    from app.core.config import settings

    logger = get_logger(__name__)

    try:
        user_message = state.get("user_message", "")
        slots = state.get("slots", {})

        logger.info(f"[product_general_information] Searching for: {user_message}")

        # Use perplexity for web search (if available in settings)
        search_query = user_message

        # Fetch real-time web results via Perplexity (if configured)
        web_context = ""
        try:
            from app.services.search.config import get_search_manager
            search_manager = get_search_manager()
            if search_manager:
                search_results = await search_manager.search(
                    query=search_query,
                    intent="product",
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
                        logger.info(f"[product_general_information] Web context: {wc.source_count} sources used, {wc.omitted_count} omitted, ~{wc.token_estimate} tokens")
                    logger.info(f"[product_general_information] Got {len(search_results)} web results")
        except Exception as search_err:
            logger.warning(f"[product_general_information] Web search failed, continuing with LLM-only: {search_err}")

        # Build prompt for general product knowledge
        web_section = f"\n\nRecent web results:\n{web_context}\n" if web_context else ""
        knowledge_source = "your knowledge and the web results below" if web_context else "your knowledge"
        prompt = f"""Answer this product-related question using {knowledge_source}: "{user_message}"
{web_section}
Provide a helpful, accurate answer that explains the concept clearly.
Focus on:
- Technical explanations if asked
- Buying guide advice if asked
- Product category overviews if asked
- Industry trends if asked
- How things work if asked

Keep the answer concise (2-3 paragraphs) and helpful.

Return valid JSON:
{{"answer": "Your answer here", "follow_up_question": "<exactly one contextual curious question that references something specific from the answer>", "sources": []}}"""

        from app.services.prompts.voice import build_system_prompt
        role_prompt = (
            "You answer product knowledge questions with clear, opinionated "
            "explanations. Return a JSON object with three fields: answer "
            "(the explanation, 2-3 paragraphs of markdown), follow_up_question "
            "(exactly one contextual curious question that references "
            "something specific from the answer — not a generic offer), and "
            "sources (an empty list unless you have explicit URLs to cite)."
        )
        response = await model_service.generate(
            messages=[
                {"role": "system", "content": build_system_prompt(role_prompt=role_prompt, kind="response")},
                {"role": "user", "content": prompt}
            ],
            model=settings.DEFAULT_MODEL,
            temperature=0.3,
            max_tokens=1000,
            response_format={"type": "json_object"},
            agent_name="product_general_information"
        )

        data = json.loads(response)
        answer = (data.get("answer") or "").strip()
        follow_up = (data.get("follow_up_question") or "").strip()
        # Concatenate the follow-up so the existing product_compose consumer
        # path (general_product_info → assistant_text at product_compose.py:444)
        # delivers the structurally-separated follow-up to the user.
        combined = answer + (f"\n\n{follow_up}" if follow_up else "")

        logger.info(f"[product_general_information] Generated answer ({len(answer)} chars), follow_up ({len(follow_up)} chars)")

        return {
            "general_product_info": combined,
            "success": True
        }

    except Exception as e:
        logger.error(f"[product_general_information] Error: {e}", exc_info=True)
        return {
            "general_product_info": "",
            "error": str(e),
            "success": False
        }
