"""
Intent Agent
Responsibilities:
- Classify user intent (product/service/travel/general/intro)
- Determine if general queries need web search
"""
from app.core.centralized_logger import get_logger
import hashlib
import json
import time
from typing import Dict, Any, Tuple
from ..schemas.graph_state import GraphState
from .base_agent import BaseAgent

logger = get_logger(__name__)

# Intent classification cache: key -> (result_dict, timestamp)
_intent_cache: Dict[str, Tuple[Dict, float]] = {}
_INTENT_CACHE_TTL = 300  # 5 minutes


class IntentAgent(BaseAgent):
    """Intent classification and slot extraction agent"""

    def __init__(self):
        super().__init__(
            agent_name="Intent",
            on_chain_start_message="Understanding your request..."
        )

    async def run(self, state: GraphState) -> GraphState:
        """
        Main entry point - calls execute()
        Implements BaseAgent.run() abstract method
        """
        return await self.execute(state)

    async def execute(self, state: GraphState) -> Dict[str, Any]:
        """
        Execute intent classification only (slot extraction moved to Clarifier Agent)

        Input: sanitized_text, conversation_history
        Output: {intent}
        """
        try:
            logger.info(f"Intent Agent executing")

            text = state.get("sanitized_text") or state["user_message"]

            # Get conversation history from state (already limited by ChatHistoryManager)
            conversation_history = state.get("conversation_history", [])
            last_search_context = state.get("last_search_context", {})
            logger.info(f"[Intent Agent] Using {len(conversation_history)} messages from history for context")
            if last_search_context:
                logger.info(f"[Intent Agent] Last search context: category={last_search_context.get('category')}, products={len(last_search_context.get('product_names', []))}")

            # Call LLM for intent classification with history context
            intent_result = await self._quick_intent_classification(text, conversation_history, last_search_context)
            intent = intent_result["intent"]

            return {"intent": intent}

        except Exception as e:
            logger.error(f"Intent Agent error: {str(e)}", exc_info=True)
            return {"intent": "general"}


    async def _quick_intent_classification(self, text: str, conversation_history: list = None, last_search_context: dict = None) -> Dict[str, Any]:
        """Call 1: Quick intent classification only (lightweight, ~1-2s)"""
        global _intent_cache

        # Cache check — only for standalone messages (no conversation context that would change intent)
        has_context = bool(conversation_history) or bool(last_search_context and last_search_context.get("category"))
        if not has_context:
            cache_key = hashlib.md5(text.strip().lower().encode()).hexdigest()
            now = time.time()
            if cache_key in _intent_cache:
                cached_result, cached_at = _intent_cache[cache_key]
                if now - cached_at < _INTENT_CACHE_TTL:
                    logger.info(f"[Intent Agent] Cache HIT for: {text[:50]}")
                    return cached_result
        else:
            cache_key = None

        # Build context hint from last search if available
        context_hint = ""
        if last_search_context and last_search_context.get("category"):
            cat = last_search_context.get("category", "")
            products = ", ".join(last_search_context.get("product_names", [])[:3])
            context_hint = f"""
ACTIVE PRODUCT CONTEXT:
The user was recently searching for {cat} products. Products discussed: {products}.
Short follow-up messages like "cheapest one", "which is best", "compare them", "tell me more" should be classified as "product" since they reference this active context."""

        system_prompt = f"""You are a fast intent classifier. Classify the user's CURRENT message into ONE category.

Categories:
- intro → greetings, asking what the bot can do, or asking for help, not an bot option choose
- product → user wants to find, buy, compare, or get recommendations for a physical product
- service → user wants a service (not a physical product)
- travel → anything related to trip planning, destinations, activities at a location, accommodations, transportation, or travel comparisons
- strain → cannabis strains or products: strain names or comparisons ("sour d vs blue dream"), indica/sativa/hybrid questions, terpenes, weed/THC recommendations, "what should I smoke for X"
- general → information only
- unclear → gibberish, random characters, nonsense text
{context_hint}
CRITICAL CONTEXT RULE:
When conversation history is provided, you MUST consider it. If the user's current message is a follow-up or continuation of a previous topic, maintain that topic's intent. A short or ambiguous message in an ongoing conversation should inherit the context's intent, not be classified as "general" or "unclear".

However, if the current message clearly indicates a new intent (contains specific keywords or request patterns), prioritize the current message's intent over conversation history.

Think about: "What is the user trying to accomplish in THIS conversation?" not just "What does this single message mean in isolation?"

Return ONLY valid JSON:
{{
  "intent": "intro|product|service|travel|strain|general|unclear"
}}"""

        # Build messages with conversation history for context
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history if available (for context)
        if conversation_history:
            for msg in conversation_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ["user", "assistant"] and content:
                    messages.append({"role": role, "content": content})

        # Add current message
        user_prompt = f"User message: {text}"
        messages.append({"role": "user", "content": user_prompt})

        try:
            # Blue color for LLM query logs
            BLUE = "\033[94m"
            RESET = "\033[0m"
            logger.info(f"{BLUE}{'=' * 80}{RESET}")
            logger.info(f"{BLUE}[CALL 1] QUICK INTENT CLASSIFICATION:{RESET}")
            logger.info(f"{BLUE}  Message: {text}{RESET}")
            logger.info(f"{BLUE}  History messages: {len(conversation_history) if conversation_history else 0}{RESET}")
            logger.info(f"{BLUE}  System prompt: {len(system_prompt)} chars{RESET}")

            result_text = await self.generate(
                messages=messages,
                model=self.settings.INTENT_MODEL,
                temperature=0.1,
                max_tokens=self.settings.INTENT_MAX_TOKENS,
                response_format={"type": "json_object"},
                session_id=text[:50] if text else "unknown"
            )

            result = json.loads(result_text)
            intent = result.get("intent", "general")

            logger.info(f"{BLUE}[CALL 1] Intent detected: {intent}{RESET}")
            logger.info(f"{BLUE}{'=' * 80}{RESET}")

            # Store in cache (only standalone messages without context)
            intent_result = {"intent": intent}
            if cache_key is not None:
                _intent_cache[cache_key] = (intent_result, time.time())
                # Periodic cleanup to prevent memory leak
                if len(_intent_cache) > 10000:
                    cutoff = time.time() - _INTENT_CACHE_TTL
                    _intent_cache = {k: v for k, v in _intent_cache.items() if v[1] > cutoff}

            return intent_result

        except Exception as e:
            logger.error(f"[CALL 1] Quick intent classification error: {str(e)}")
            return {"intent": "general"}


    def _fallback_classification(self, text: str) -> Dict[str, Any]:
        """Simple keyword-based classification as fallback"""
        text_lower = text.lower()

        # Check for travel keywords (including deals/packages when combined with location context)
        travel_keywords = ["hotel", "flight", "trip", "travel", "vacation", "visit", "destination"]
        if any(keyword in text_lower for keyword in travel_keywords):
            return {"intent": "travel"}

        # Check for travel deals/packages pattern (deals/packages + travel context)
        if ("deals" in text_lower or "packages" in text_lower or "package" in text_lower):
            # Common travel destinations/indicators
            travel_indicators = ["bali", "paris", "tokyo", "london", "new york", "beach", "island", "city", "country"]
            if any(indicator in text_lower for indicator in travel_indicators):
                return {"intent": "travel"}

        # Check for product keywords (including comparison keywords)
        product_keywords = ["buy", "purchase", "best", "recommend", "laptop", "phone", "camera", "compare", " vs ", "versus"]
        if any(keyword in text_lower for keyword in product_keywords):
            return {"intent": "product"}

        # Default to general
        return {"intent": "general"}



# Agent node function for LangGraph
async def intent_agent_node(state: GraphState, agent: IntentAgent) -> GraphState:
    """
    LangGraph node wrapper for Intent Agent
    Simplified to only handle intent classification
    """
    result = await agent.execute(state)

    # Update state with intent only
    state.intent = result["intent"]
    state.current_agent = "intent"

    # All intents now route to planner (clarifier handles slot checking)
    if result["intent"] in ["product", "service", "travel", "strain", "general", "intro", "unclear"]:
        state.next_agent = "planner"
    else:
        # Unknown intent - end workflow
        state.status = "error"
        state.assistant_text = "I'm not sure how to help with that."
        state.next_agent = None

    return state
