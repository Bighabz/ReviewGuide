"""
Clarifier Agent
Responsibilities:
- Load execution plan from state
- Check required_slots for all tools in the plan
- Generate follow-up questions for missing slots
- Extract slots from user answers
- Manage halt state for multi-turn conversations
"""
from app.core.centralized_logger import get_logger
import json
import re
import sys
import os
from typing import Dict, Any, List, Optional, Set

# Add MCP server to path for tool contract imports
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
mcp_server_path = os.path.join(backend_dir, 'mcp_server')
if mcp_server_path not in sys.path:
    sys.path.insert(0, mcp_server_path)

from tool_contracts import get_tool_contracts_dict  # noqa: E402

from ..schemas.graph_state import GraphState
from .base_agent import BaseAgent
from .category_question_packs import format_pack_hint, get_category_pack
from ..services.halt_state_manager import HaltStateManager
from ..services.prompts.voice import build_system_prompt
from app.lib.toon_python import encode

logger = get_logger(__name__)


# ── Outcome 2: post-results refinement chips ────────────────────────────────
# After a shortlist renders, next_step_suggestion emits deterministic refinement
# chips ("Show cheaper options", "Only Sony", "More premium picks", "Different
# use case"). Tapping one sends "You chose: <chip text>". These helpers map that
# message to a slot adjustment so the previous search re-runs immediately —
# answered questions are never re-asked.

_SUGGESTION_PREFIX = "you chose:"


def _strip_suggestion_prefix(message: str) -> str:
    """Remove the frontend's suggestion-click prefix ("You chose: ...")."""
    msg = (message or "").strip()
    if msg.lower().startswith(_SUGGESTION_PREFIX):
        msg = msg[len(_SUGGESTION_PREFIX):].strip()
    return msg


def _detect_refinement_action(message: str) -> Optional[str]:
    """Map a refinement-chip message to an action.

    Returns "cheaper", "premium", "different_use_case", "brand:<name>", or None.
    Handles both the tapped form ("You chose: Show cheaper options") and typed
    equivalents ("show cheaper options").
    """
    msg = _strip_suggestion_prefix(message).lower().strip().rstrip(".!?")
    if msg in ("show cheaper options", "show me cheaper options", "cheaper options", "show cheaper"):
        return "cheaper"
    if msg in ("more premium picks", "more premium", "more premium options", "show premium options"):
        return "premium"
    if msg in ("different use case", "different use-case", "change use case"):
        return "different_use_case"
    m = re.match(r"^only ([a-z0-9][a-z0-9 \-&']{1,30})$", msg)
    if m:
        return f"brand:{m.group(1).strip()}"
    return None


def _shown_prices(last_search_context: dict) -> List[float]:
    """Real prices from the shortlist the user just saw."""
    return [
        float(p) for p in (last_search_context.get("top_prices") or {}).values()
        if isinstance(p, (int, float)) and p > 0
    ]


def _apply_refinement_action(action: str, slots: dict, last_search_context: dict) -> dict:
    """Adjust slots for a refinement action ("cheaper" / "premium" / "brand:<name>")."""
    adjusted = dict(slots)
    prices = _shown_prices(last_search_context)

    if action == "cheaper":
        # New ceiling = 80% of the cheapest item just shown, so every new pick is
        # cheaper than everything the user saw. Without price data, keep slots
        # unchanged — re-running the search is still harmless.
        if prices:
            adjusted["budget"] = f"under ${int(min(prices) * 0.8)}"
    elif action == "premium":
        # New floor = 120% of the priciest item shown; replaces any old ceiling.
        if prices:
            adjusted["budget"] = f"over ${int(max(prices) * 1.2)}"
    elif action.startswith("brand:"):
        adjusted["brand"] = action.split(":", 1)[1].strip().title()
    return adjusted


class ClarifierAgent(BaseAgent):
    """Clarifier agent for slot filling and follow-up questions"""

    def __init__(self):
        super().__init__(
            agent_name="Clarifier",
            on_chain_start_message="Checking if I need more information..."
        )

    async def run(self, state: GraphState) -> GraphState:
        """
        Main entry point - calls execute()
        Implements BaseAgent.run() abstract method
        """
        return await self.execute(state)

    async def execute(self, state: GraphState) -> Dict[str, Any]:
        """
        Execute clarifier logic:
        1. Load halt state if exists (for resumed sessions)
        2. Check if this is a new plan or a resumed session
        3. If new plan: load tool contracts, check required_slots, generate follow-up questions
        4. If resumed: extract slot from user answer, validate, fill slots
        5. If all slots filled: proceed to execution
        6. If slots still missing: return next follow-up question

        Input: plan, slots, halt_state (optional)
        Output: {slots, followups, missing_required_slots, next_question, proceed_to_execution}
        """
        session_id = state.get("session_id")
        intent = state.get("intent", "")

        try:
            logger.info(f"[Clarifier Agent] Executing for session: {session_id}")

            # Skip clarifier logic for "intro" or "unclear" intents - route directly to next step
            if intent in ["intro", "unclear"]:
                logger.info(f"[Clarifier Agent] Intent is '{intent}' - skipping clarifier logic and routing to next step")
                return {
                    "slots": state.get("slots", {}),
                    "followups": [],
                    "missing_required_slots": [],
                    "proceed_to_execution": True  # Skip to next agent
                }

            # Skip clarification for follow-up queries when search context exists
            last_search_context = state.get("last_search_context", {})
            if last_search_context and intent == "product":
                # ── Outcome 2: refinement chips ──
                # A tapped refinement chip ("You chose: Show cheaper options") re-runs
                # the previous search with adjusted slots — nothing is re-asked.
                raw_message = state.get("sanitized_text") or state.get("user_message", "")
                refinement_action = _detect_refinement_action(raw_message)
                if refinement_action:
                    inherited = dict(state.get("slots", {}) or {})
                    for key in ["budget", "brand", "features", "use_case", "category", "product_type"]:
                        if not inherited.get(key) and last_search_context.get(key):
                            inherited[key] = last_search_context[key]

                    if refinement_action == "different_use_case":
                        # Re-ask ONLY the use_case question; everything else stays answered.
                        inherited.pop("use_case", None)
                        followups_data = await self._generate_followup_questions(
                            ["use_case"],
                            inherited,
                            raw_message,
                            intent,
                            conversation_history=state.get("conversation_history", []),
                        )
                        await HaltStateManager.update_halt_state(session_id, {
                            "intent": intent,
                            "slots": inherited,
                            "followups": followups_data.get("questions", []),
                            "missing_required_slots": ["use_case"],
                            "plan": state.get("plan"),
                            "tools_by_required_slot": {},
                        })
                        logger.info("[Clarifier Agent] Refinement: 'Different use case' → re-asking use_case only")
                        return {
                            "slots": inherited,
                            "followups": followups_data.get("questions", []),
                            "missing_required_slots": ["use_case"],
                            "next_question": followups_data,
                            "proceed_to_execution": False
                        }

                    adjusted = _apply_refinement_action(refinement_action, inherited, last_search_context)
                    logger.info(
                        f"[Clarifier Agent] Refinement chip '{refinement_action}' → "
                        f"budget={adjusted.get('budget')}, brand={adjusted.get('brand')} — re-running search"
                    )
                    return {
                        "slots": adjusted,
                        "followups": [],
                        "missing_required_slots": [],
                        "proceed_to_execution": True
                    }

                user_msg = (state.get("sanitized_text") or state.get("user_message", "")).lower().strip()
                reference_signals = [
                    "that one", "the first", "the second", "the third",
                    "cheapest", "most expensive", "best rated", "any of",
                    "compare them", "which one", "between those",
                    "more about", "tell me more", "go back to",
                    "the one with", "how about the",
                ]
                matched_signal = any(signal in user_msg for signal in reference_signals)
                is_follow_up = matched_signal or len(user_msg.split()) <= 4

                # Now that search context PERSISTS across turns (Outcome 2), the
                # "short message = follow-up" rule needs a topic guard: a short message
                # that names a DIFFERENT category than the context ("best mattress"
                # right after a laptop search) is a NEW query — inheriting laptop
                # slots into a mattress search produces garbage results.
                if is_follow_up and not matched_signal:
                    generic_words = {
                        "best", "good", "top", "great", "cheap", "show", "me", "a", "an",
                        "the", "find", "get", "buy", "for", "of", "to", "i", "want",
                        "need", "one", "ones", "some", "any", "you", "chose", "more",
                        "options", "picks", "deals", "recommend", "suggest", "what",
                        "which", "is", "are", "my", "new",
                    }
                    context_words: set = set()
                    for src in (
                        [last_search_context.get("category", ""), last_search_context.get("product_type", "")]
                        + list(last_search_context.get("product_names", []) or [])
                    ):
                        context_words.update(str(src).lower().replace("-", " ").split())
                    content_words = [
                        w for w in re.sub(r"[^a-z0-9 ]", " ", user_msg).split()
                        if w not in generic_words and len(w) >= 3
                    ]
                    if content_words and context_words and not any(
                        w in context_words or any(w in cw or cw in w for cw in context_words)
                        for w in content_words
                    ):
                        logger.info(
                            f"[Clarifier Agent] Short message names a different topic than the search "
                            f"context — treating as NEW query: '{user_msg}'"
                        )
                        is_follow_up = False

                # If a reference signal matched, check whether it contains an anaphoric reference
                # (e.g. "tell me more about the blue one") vs. a genuinely new topic
                # (e.g. "tell me more about Sony headphones" when previous context was laptops).
                if is_follow_up:
                    # Try to extract the noun phrase following reference-signal phrases
                    topic_patterns = [
                        r"(?:tell me )?more about (?:the |a |an )?(.+)",
                        r"what (?:about|can you tell me about) (?:the |a |an )?(.+)",
                        r"(?:info|information|details|specs) (?:on|about|for) (?:the |a |an )?(.+)",
                    ]
                    new_topic = None
                    for tp in topic_patterns:
                        tm = re.search(tp, user_msg)
                        if tm:
                            new_topic = tm.group(1).strip().rstrip('?.!')
                            break

                    if new_topic:
                        # Anaphoric patterns — these clearly refer to a previous item, not a new product
                        anaphoric_patterns = [
                            r"^(?:the |a |an )?(?:first|second|third|last|other|that|this|those|these)? ?(?:one|ones|option|options|model|item|thing|version)$",
                            r"^(?:blue|red|black|white|silver|gold|gray|grey|green|purple|pink|yellow|orange) (?:one|ones|option|version|model)$",
                            r"^(?:cheap(?:er|est)?|expensive|best|worst|top|bottom) (?:one|ones|option|version|model)$",
                        ]
                        is_anaphoric = any(re.match(pattern, new_topic) for pattern in anaphoric_patterns)

                        if is_anaphoric:
                            logger.info(f"[Clarifier Agent] Anaphoric reference detected: '{new_topic}' — keeping as follow-up")
                            # is_follow_up stays True
                        else:
                            # Check whether the topic relates to the existing search context
                            prev_names_lower = [n.lower() for n in last_search_context.get("product_names", [])]
                            prev_category = last_search_context.get("category", "").lower()
                            prev_product_type = last_search_context.get("product_type", "").lower()
                            topic_is_related_to_context = (
                                any(new_topic in n or n in new_topic for n in prev_names_lower)
                                or (prev_category and prev_category in new_topic)
                                or (prev_product_type and prev_product_type in new_topic)
                            )
                            if not topic_is_related_to_context:
                                logger.info(f"[Clarifier Agent] New topic detected: '{new_topic}' — treating as new query")
                                is_follow_up = False

                if is_follow_up:
                    logger.info(f"[Clarifier Agent] Follow-up query detected with search context — skipping clarification")
                    # Inherit unfilled slots from context
                    current_slots = state.get("slots", {})
                    for key in ["budget", "brand", "features", "use_case", "category", "product_type"]:
                        if not current_slots.get(key) and last_search_context.get(key):
                            current_slots[key] = last_search_context[key]
                    return {
                        "slots": current_slots,
                        "followups": [],
                        "missing_required_slots": [],
                        "proceed_to_execution": True
                    }

            # Check if halt state exists (resumed session)
            halt_state = await HaltStateManager.get_halt_state(session_id)

            # Check if we have actual followup questions (not just empty list)
            has_followups = halt_state and halt_state.get("followups") and len(halt_state.get("followups", [])) > 0

            if has_followups:
                # RESUMED SESSION: User is answering follow-up questions
                logger.info(f"[Clarifier Agent] Resumed session - extracting slots from user answer")
                return await self._handle_user_answer(state, halt_state, session_id)
            else:
                # NEW SESSION: Check if plan requires slots
                logger.info(f"[Clarifier Agent] New session - checking plan for required slots")
                return await self._handle_new_plan(state, session_id)

        except Exception as e:
            logger.error(f"[Clarifier Agent] Error: {str(e)}", exc_info=True)
            return {
                "slots": state.get("slots", {}),
                "followups": [],
                "missing_required_slots": [],
                "proceed_to_execution": True  # Fail open - proceed despite error
            }

    async def _handle_new_plan(self, state: GraphState, session_id: str) -> Dict[str, Any]:
        """
        Handle new plan: check required_slots for all tools in plan.

        Args:
            state: Graph state with plan
            session_id: Session ID

        Returns:
            Dict with slots, followups, missing_required_slots, proceed_to_execution
        """
        plan = state.get("plan", {})
        current_slots = state.get("slots", {})

        if not plan or not plan.get("steps"):
            logger.info(f"[Clarifier Agent] No plan found, proceeding to execution")
            return {
                "slots": current_slots,
                "followups": [],
                "missing_required_slots": [],
                "proceed_to_execution": True
            }

        # Get tool contracts
        tool_contracts = get_tool_contracts_dict()

        # Collect all required slots from all tools in the plan
        all_required_slots: Set[str] = set()
        all_optional_slots: Set[str] = set()  # Also collect optional slots for extraction
        tools_by_required_slot: Dict[str, List[str]] = {}  # slot_name -> [tool_names]
        slot_replacements: Dict[str, str] = {}  # slot_name -> replacement_slot

        for step in plan["steps"]:
            for tool_name in step.get("tools", []):
                contract = tool_contracts.get(tool_name)
                if contract:
                    if "required_slots" in contract:
                        required_slots = contract["required_slots"]
                        logger.info(f"  Tool '{tool_name}' requires slots: {required_slots}")

                        for slot in required_slots:
                            all_required_slots.add(slot)
                            if slot not in tools_by_required_slot:
                                tools_by_required_slot[slot] = []
                            tools_by_required_slot[slot].append(tool_name)

                    # Also collect optional slots for extraction (e.g., children)
                    if "optional_slots" in contract:
                        optional_slots = contract["optional_slots"]
                        logger.info(f"  Tool '{tool_name}' has optional slots: {optional_slots}")
                        all_optional_slots.update(optional_slots)

                    # Collect slot replacements (e.g., check_in can be replaced by departure_date)
                    if "slot_replacements" in contract:
                        for slot_name, replacement_slot in contract["slot_replacements"].items():
                            slot_replacements[slot_name] = replacement_slot
                            logger.info(f"  Tool '{tool_name}' slot replacement: '{slot_name}' can use '{replacement_slot}'")

        if not all_required_slots and not all_optional_slots:
            logger.info(f"[Clarifier Agent] No required or optional slots in plan, proceeding to execution")
            return {
                "slots": current_slots,
                "followups": [],
                "missing_required_slots": [],
                "proceed_to_execution": True
            }

        # EXTRACT initial slots from user message FIRST (before calculating what's missing)
        logger.info(f"[Clarifier Agent] Attempting to extract slots from user message")

        user_message = state.get("sanitized_text") or state.get("user_message", "")
        intent = state.get("intent", "")

        # Get conversation history from state (already loaded in chat.py before workflow started)
        conversation_history = state.get("conversation_history", [])

        logger.info(f"[Clarifier Agent] Loaded {len(conversation_history)} messages from conversation history")

        # Find which slots need extraction (both required and optional)
        # Required slots that are missing - BUT skip slots that have replacements (we'll extract the replacement instead)
        required_slots_to_extract = [
            slot for slot in all_required_slots
            if (slot not in current_slots or not current_slots[slot])
            and slot not in slot_replacements  # Skip slots that have replacements
        ]
        # Also add replacement slots that are not yet filled
        for slot_name, replacement_slot in slot_replacements.items():
            if replacement_slot not in required_slots_to_extract and (replacement_slot not in current_slots or not current_slots[replacement_slot]):
                required_slots_to_extract.append(replacement_slot)
                logger.info(f"[Clarifier Agent] Will extract '{replacement_slot}' instead of '{slot_name}' (slot replacement)")

        # Optional slots that are missing (e.g., children)
        optional_slots_to_extract = [slot for slot in all_optional_slots if slot not in current_slots or not current_slots[slot]]
        # Combine both lists
        slots_to_extract = required_slots_to_extract + optional_slots_to_extract

        if slots_to_extract:
            logger.info(f"[Clarifier Agent] Attempting to extract {len(slots_to_extract)} slots in one LLM call: {slots_to_extract} (required: {required_slots_to_extract}, optional: {optional_slots_to_extract})")

            extracted_slots = await self._extract_all_slots_from_conversation(
                slot_names=slots_to_extract,
                user_message=user_message,
                conversation_history=conversation_history,
                intent=intent
            )

            # Update current_slots with extracted values
            for slot_name, slot_value in extracted_slots.items():
                if slot_value is not None:
                    current_slots[slot_name] = slot_value
                    logger.info(f"[Clarifier Agent] ✅ Extracted slot '{slot_name}' = {slot_value}")
                else:
                    logger.info(f"[Clarifier Agent] ❌ Could not extract slot '{slot_name}' from message or history")
        else:
            logger.info(f"[Clarifier Agent] All required slots already filled")

        # Apply slot replacements: if a required slot is missing but its replacement is filled, copy the value
        for slot_name, replacement_slot in slot_replacements.items():
            if (slot_name not in current_slots or not current_slots[slot_name]) and \
               (replacement_slot in current_slots and current_slots[replacement_slot]):
                current_slots[slot_name] = current_slots[replacement_slot]
                logger.info(f"[Clarifier Agent] 🔄 Applied slot replacement: '{slot_name}' = '{replacement_slot}' value ({current_slots[slot_name]})")

        # NOW calculate which required slots are STILL missing (after extraction and replacements)
        # Skip slots that have replacements - we'll ask for the replacement slot instead
        missing_required_slots = []
        for slot in all_required_slots:
            if slot not in current_slots or not current_slots[slot]:
                # If this slot has a replacement, check if replacement is also missing
                if slot in slot_replacements:
                    replacement_slot = slot_replacements[slot]
                    if replacement_slot not in current_slots or not current_slots[replacement_slot]:
                        # Add the replacement slot instead (if not already added)
                        if replacement_slot not in missing_required_slots:
                            missing_required_slots.append(replacement_slot)
                            logger.info(f"  Missing required slot: '{replacement_slot}' (replacement for '{slot}', needed by {tools_by_required_slot[slot]})")
                    # Don't add the original slot - it will be filled from replacement
                else:
                    missing_required_slots.append(slot)
                    logger.info(f"  Missing required slot: '{slot}' (needed by {tools_by_required_slot[slot]})")

        # Travel intent: inject sensible defaults so we produce results immediately
        intent = state.get("intent", "")
        if intent == "travel" and missing_required_slots:
            from datetime import datetime, timedelta
            defaults = {
                "adults": 2,
                "duration_days": 5,
                "departure_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            }
            for slot_name, default_value in defaults.items():
                if slot_name in missing_required_slots and (slot_name not in current_slots or not current_slots[slot_name]):
                    current_slots[slot_name] = default_value
                    logger.info(f"[Clarifier Agent] Injected travel default: {slot_name}={default_value}")
            # Apply departure_date as check_in if check_in is missing
            if "check_in" not in current_slots or not current_slots["check_in"]:
                if current_slots.get("departure_date"):
                    current_slots["check_in"] = current_slots["departure_date"]
            # Recalculate missing required slots after defaults
            missing_required_slots = [
                slot for slot in all_required_slots
                if (slot not in current_slots or not current_slots[slot])
                and not (slot in slot_replacements and (slot_replacements[slot] in current_slots and current_slots[slot_replacements[slot]]))
            ]
            if missing_required_slots:
                logger.info(f"[Clarifier Agent] Still missing after travel defaults: {missing_required_slots}")
            else:
                logger.info(f"[Clarifier Agent] All travel slots filled via defaults, proceeding")

        # Product intent: detect ambiguous brand-only queries that need category clarification
        # e.g. "Dyson vs Shark" could mean vacuums OR kitchen appliances
        if intent == "product" and not missing_required_slots:
            has_brand = bool(current_slots.get("brand"))
            has_category = bool(current_slots.get("category"))
            has_product_name = bool(current_slots.get("product_name"))

            if has_brand and not has_category and not has_product_name:
                # Brands mentioned without category — check if brands span multiple categories
                user_msg_lower = (state.get("sanitized_text") or state.get("user_message", "")).lower()
                # Multi-category brands that commonly cause confusion
                ambiguous_brands = {
                    "dyson": ["vacuums", "air purifiers", "hair dryers", "fans"],
                    "shark": ["vacuums", "steam mops", "hair dryers", "blenders"],
                    "ninja": ["blenders", "air fryers", "coffee makers", "grills"],
                    "bissell": ["vacuums", "carpet cleaners", "steam mops"],
                    "kitchenaid": ["stand mixers", "blenders", "food processors", "cookware"],
                    "samsung": ["phones", "TVs", "laptops", "tablets", "appliances"],
                    "apple": ["phones", "laptops", "tablets", "watches", "headphones"],
                    "sony": ["headphones", "TVs", "cameras", "gaming consoles", "speakers"],
                    "lg": ["TVs", "monitors", "appliances", "phones"],
                    "philips": ["shavers", "toothbrushes", "TVs", "kitchen appliances"],
                    "breville": ["espresso machines", "toaster ovens", "blenders", "juicers"],
                    "cuisinart": ["food processors", "coffee makers", "cookware", "toasters"],
                    "dewalt": ["drills", "saws", "impact drivers", "grinders"],
                    "makita": ["drills", "saws", "impact drivers", "grinders"],
                    "bosch": ["power tools", "dishwashers", "washing machines", "ovens"],
                }
                detected_ambiguous = [
                    brand for brand in ambiguous_brands
                    if brand in user_msg_lower
                ]
                if detected_ambiguous:
                    logger.info(f"[Clarifier Agent] Detected ambiguous brand-only query: {detected_ambiguous} — requesting category clarification")
                    missing_required_slots.append("category")

        # Conversational-expert flow (supersedes the old blueprint §8 budget-first
        # rule): on a substantive product query, ask what a domain specialist would
        # ask — three questions, in this order:
        #   1. use_case  — the category-translated lead question ("How do you usually
        #                  sleep?" for mattresses, "What kind of riding?" for bikes)
        #   2. features  — the most differentiating spec/preference for the category
        #                  (firmness for mattresses, terrain for bikes); its chips
        #                  always include a "No strong preference" escape hatch
        #   3. budget    — LAST, with category-realistic price brackets generated by
        #                  the LLM, never a generic "Under $50" tier list
        # All three are OPTIONAL slots on product_search, so the clarifier would
        # never ask them on its own.
        if intent == "product":
            _ctx = state.get("last_search_context", {}) or {}
            substantive = bool(
                current_slots.get("category")
                or current_slots.get("product_name")
                or current_slots.get("product_type")
            )
            has_budget = bool(current_slots.get("budget")) or bool(_ctx.get("budget"))
            has_use_case = bool(current_slots.get("use_case")) or bool(_ctx.get("use_case"))
            has_features = bool(current_slots.get("features")) or bool(_ctx.get("features"))
            if substantive:
                needs_use_case = not has_use_case
                needs_budget = not has_budget
                if needs_use_case and "use_case" not in missing_required_slots:
                    missing_required_slots.append("use_case")
                    logger.info("[Clarifier Agent] use_case missing on substantive product query — asking it (expert-first flow)")
                if needs_budget and "budget" not in missing_required_slots:
                    missing_required_slots.append("budget")
                    logger.info("[Clarifier Agent] Budget missing on substantive product query — asking it last (expert-first flow)")
                # features rides along only when we're already asking something — it must
                # never be the sole reason to halt an otherwise-complete query like
                # "gaming laptop under $1500" (use case + budget present → straight to results).
                if (needs_use_case or needs_budget) and not has_features and "features" not in missing_required_slots:
                    missing_required_slots.append("features")
                    logger.info("[Clarifier Agent] features missing — asking the category's differentiator alongside")
            # Ordering: use_case always first, budget always last (features lands between).
            if "use_case" in missing_required_slots:
                missing_required_slots = ["use_case"] + [s for s in missing_required_slots if s != "use_case"]
            if "budget" in missing_required_slots:
                missing_required_slots = [s for s in missing_required_slots if s != "budget"] + ["budget"]

        # Check if all slots are now filled after extraction
        if not missing_required_slots:
            logger.info(f"[Clarifier Agent] All required slots extracted from initial message, proceeding to execution")
            return {
                "slots": current_slots,
                "followups": [],
                "missing_required_slots": [],
                "proceed_to_execution": True
            }

        logger.info(f"[Clarifier Agent] {len(missing_required_slots)} slots still missing after extraction, will ask follow-up questions")

        # Generate follow-up questions with intro and closing (all from LLM)
        logger.info(f"[Clarifier Agent] Generating follow-up questions for {len(missing_required_slots)} missing slots")

        followups_data = await self._generate_followup_questions(
            missing_required_slots,
            current_slots,
            state.get("user_message", ""),
            state.get("intent", ""),
            conversation_history=conversation_history
        )

        # Save to halt state (store questions array for slot extraction later)
        halt_state_data = {
            "intent": state.get("intent"),
            "slots": current_slots,
            "followups": followups_data.get("questions", []),  # Store just questions for extraction
            "missing_required_slots": missing_required_slots,
            "plan": plan,
            "tools_by_required_slot": tools_by_required_slot
        }
        await HaltStateManager.update_halt_state(session_id, halt_state_data)

        logger.info(f"[Clarifier Agent] Returning all follow-up questions as structured data")

        return {
            "slots": current_slots,
            "followups": followups_data.get("questions", []),
            "missing_required_slots": missing_required_slots,
            "next_question": followups_data,  # Full structured data for frontend
            "proceed_to_execution": False  # HALT - wait for user answer
        }

    async def _handle_user_answer(
        self,
        state: GraphState,
        halt_state: Dict[str, Any],
        session_id: str
    ) -> Dict[str, Any]:
        """
        Handle user's answer to ALL follow-up questions at once.
        Extract all slots from the user's single response containing all answers.

        Args:
            state: Graph state with user_message
            halt_state: Halt state from Redis
            session_id: Session ID

        Returns:
            Dict with slots, followups, missing_required_slots, next_question, proceed_to_execution
        """
        user_message = state.get("sanitized_text") or state.get("user_message", "")
        followups = halt_state.get("followups", [])
        current_slots = halt_state.get("slots", {})
        conversation_history = state.get("conversation_history", [])

        if not followups:
            logger.warning(f"[Clarifier Agent] No followups in halt state, proceeding to execution")
            return {
                "slots": current_slots,
                "followups": [],
                "missing_required_slots": [],
                "proceed_to_execution": True
            }

        # Get intent from halt state for context
        intent = halt_state.get("intent", "")

        # Get required slots from followups
        required_slot_names = [f["slot"] for f in followups]

        # Also get optional slots and slot replacements from plan's tool contracts
        optional_slot_names = []
        slot_replacements: Dict[str, str] = {}
        plan = halt_state.get("plan", {})
        if plan and plan.get("steps"):
            tool_contracts = get_tool_contracts_dict()
            for step in plan["steps"]:
                for tool_name in step.get("tools", []):
                    contract = tool_contracts.get(tool_name)
                    if contract:
                        if "optional_slots" in contract:
                            for slot in contract["optional_slots"]:
                                # A slot already being asked as REQUIRED must not also be
                                # listed as optional — duplicate slot names make the LLM
                                # extractor emit duplicate JSON keys, and json.loads keeps
                                # the LAST occurrence, so the real extracted value gets
                                # overwritten by the optional duplicate's null. That's the
                                # "Extracted 0/13 slots" clarifier loop seen in prod
                                # (2026-06-02): the user answers, extraction silently
                                # discards it, and the same questions come back forever.
                                if (
                                    slot not in current_slots
                                    and slot not in optional_slot_names
                                    and slot not in required_slot_names
                                ):
                                    optional_slot_names.append(slot)
                        # Collect slot replacements
                        if "slot_replacements" in contract:
                            for slot_name, replacement_slot in contract["slot_replacements"].items():
                                slot_replacements[slot_name] = replacement_slot

        # Combine required and optional slots for extraction (dedupe defensively —
        # see the duplicate-JSON-key trap documented above)
        slot_names = list(dict.fromkeys(required_slot_names + optional_slot_names))
        logger.info(f"[Clarifier Agent] Extracting {len(slot_names)} slots from user answer: {slot_names} (required: {required_slot_names}, optional: {optional_slot_names})")

        extracted_slots = await self._extract_all_slots_from_answer(
            slot_names=slot_names,
            user_message=user_message,
            followups=followups,
            optional_slots=optional_slot_names
        )

        # Update current_slots with extracted values
        still_missing_required = []
        for slot_name in slot_names:
            slot_value = extracted_slots.get(slot_name)
            if slot_value is not None:
                current_slots[slot_name] = slot_value
                is_optional = slot_name in optional_slot_names
                logger.info(f"[Clarifier Agent] ✅ Extracted {'optional ' if is_optional else ''}slot '{slot_name}' = {slot_value}")

        # Apply slot replacements: if a required slot is missing but its replacement is filled, copy the value
        for slot_name, replacement_slot in slot_replacements.items():
            if (slot_name not in current_slots or not current_slots[slot_name]) and \
               (replacement_slot in current_slots and current_slots[replacement_slot]):
                current_slots[slot_name] = current_slots[replacement_slot]
                logger.info(f"[Clarifier Agent] 🔄 Applied slot replacement: '{slot_name}' = '{replacement_slot}' value ({current_slots[slot_name]})")

        # Now calculate which required slots are still missing (after extraction and replacements)
        for slot_name in slot_names:
            slot_value = current_slots.get(slot_name)
            if slot_value is None:
                # Only track required slots as "missing" - optional slots are fine to skip
                if slot_name in required_slot_names:
                    still_missing_required.append(slot_name)
                    logger.warning(f"[Clarifier Agent] ❌ Required slot '{slot_name}' still missing after extraction and replacements")
                else:
                    logger.info(f"[Clarifier Agent] ⏭️ Optional slot '{slot_name}' not found in answer (skipping)")

        if not still_missing_required:
            # All slots successfully extracted - proceed to execution
            logger.info(f"[Clarifier Agent] All follow-up questions answered, proceeding to execution")

            # Clear halt state
            await HaltStateManager.delete_halt_state(session_id)

            return {
                "slots": current_slots,
                "followups": [],
                "missing_required_slots": [],
                "proceed_to_execution": True
            }
        else:
            # Some required slots still missing - regenerate questions for remaining slots
            logger.info(f"[Clarifier Agent] {len(still_missing_required)} required slots still missing: {still_missing_required}")

            # Regenerate follow-up questions for remaining missing slots (with fresh intro/closing)
            followups_data = await self._generate_followup_questions(
                still_missing_required,
                current_slots,
                user_message,
                intent,
                conversation_history=conversation_history
            )

            remaining_followups = followups_data.get("questions", [])

            # Update halt state with new slots and remaining followups
            halt_state["slots"] = current_slots
            halt_state["followups"] = remaining_followups
            await HaltStateManager.update_halt_state(session_id, halt_state)

            return {
                "slots": current_slots,
                "followups": remaining_followups,
                "missing_required_slots": still_missing_required,
                "next_question": followups_data,  # Full structured data for frontend
                "proceed_to_execution": False  # HALT - wait for remaining answers
            }

    async def _generate_followup_questions(
        self,
        missing_slots: List[str],
        current_slots: Dict[str, Any],
        user_message: str,
        intent: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Generate follow-up questions with intro and closing using LLM.

        Args:
            missing_slots: List of slot names that are missing
            current_slots: Already filled slots
            user_message: Original user message
            intent: User intent (travel, product, etc.)
            conversation_history: Full conversation history for context

        Returns:
            Dict with intro, questions array, and closing for frontend rendering
        """
        slots_str = ", ".join(missing_slots)
        filled_slots_str = json.dumps(current_slots) if current_slots else "{}"

        # Build conversation context from history
        conversation_context = ""
        if conversation_history:
            recent_messages = conversation_history[-6:]  # Last 6 messages for context
            conversation_context = "\n\nConversation history:\n"
            for msg in recent_messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content:
                    conversation_context += f"- {role}: {content[:200]}{'...' if len(content) > 200 else ''}\n"

        # Build disambiguation hint for product category ambiguity
        disambiguation_hint = ""
        if intent == "product" and "category" in missing_slots:
            brand = current_slots.get("brand", "")
            if brand:
                disambiguation_hint = f"""
IMPORTANT - Category Disambiguation:
The user mentioned brand(s) "{brand}" without specifying what TYPE of product.
Many brands make multiple product types. For the "category" question:
- List 2-3 most likely product types for this brand
- Example: "Are you comparing Dyson vs Shark vacuums, hair dryers, or something else?"
- Keep it natural — don't just say "what category?"
"""

        # Category-expert framing: a laptop question set should read like it came
        # from a laptop specialist (use case, specs, realistic price brackets), a
        # mattress set from a sleep specialist, etc. The category drives both the
        # questions AND the tappable options the frontend renders as chips.
        category = ""
        if intent == "product":
            category = str(
                current_slots.get("category")
                or current_slots.get("product_type")
                or current_slots.get("product_name")
                or ""
            )
        expert_hint = f"""
You are answering as a {category} specialist{f" (the user is shopping for: {category})" if category else ""} — ask exactly what a knowledgeable salesperson in that department would ask, in plain language.

TRANSLATE each slot into the question THAT specialist actually leads with — never ask the slot name literally:
- "use_case" slot = the FIRST question a {category or 'product'} expert asks to understand the need:
  * mattresses → "How do you usually sleep?" (Side sleeper / Back sleeper / Stomach sleeper / It varies)
  * bikes → "What kind of riding will you mostly do?" (Road / Trails & mountain / Commuting / Casual rides)
  * laptops → "What will you mainly use it for?" (Student / everyday, Gaming, Creative / video editing, Business / office)
  * headphones → "Where will you use them most?" (Commute & travel / Gym & runs / At a desk / Studio)
  * TVs → "What will you watch most?" (Movies & shows / Sports / Gaming / Everyday TV)
  Generalize this pattern for any other category.
- "features" slot = the single most differentiating spec/preference question for this category:
  * mattresses → firmness ("Soft", "Medium", "Firm", "Not sure") or sleep temperature
  * bikes → terrain or frame preference
  * laptops → performance level ("Just the basics", "Mid-range power", "High-end specs")
  * headphones → "Noise cancelling?", "Wireless?", form factor
  The LAST option for the features question must always be "No strong preference".
- "budget" slot = realistic price brackets for THIS category's actual market (laptops: "Under $500", "$500–$800", "$800–$1,200", "$1,200+"; mattresses: "Under $500", "$500–$1,000", "$1,000–$2,000", "$2,000+"). NEVER offer brackets that make no sense for the category (no "Under $50" for laptops).
- other slots = the 3-5 most common real answers for that category (actual brands, sizes, styles)

For EVERY question, generate "options": 3-5 short tappable answer choices (1-4 words each), plus "free_text_hint": a short affordance like "or describe your own use" / "or type an amount".

MULTI-SELECT: when a question naturally takes SEVERAL answers at once — typically the "features" question ("Which features matter to you?" → Noise cancelling + Waterproof both apply) — add "type": "multi_select" to that question. Questions where exactly one answer makes sense (use case, budget, size) get "type": "single_select" or no type at all. Never make budget or use_case multi-select.

Question ORDER: use case / purpose first, then specifics, budget LAST.
""" if intent == "product" else """
For EVERY question, also generate "options": 3-5 short tappable answer choices covering the most common realistic answers (e.g. travel companions: "Solo", "Couple", "Family with kids", "Friends"; trip length: "Weekend", "4-5 days", "1 week", "2+ weeks").
Each option is 1-4 words. Also generate "free_text_hint": a short affordance like "or type your own".
"""

        # Outcome 4: category question packs. When the category matches one of the
        # top ~20 curated packs, inject it as the authoritative question set — the
        # specialist questions, options, multi-select flags, and budget brackets are
        # pinned rather than improvised. Unlisted categories keep the generic expert
        # framing above and generalize via the LLM.
        if intent == "product" and category:
            pack = get_category_pack(category)
            if pack:
                expert_hint += format_pack_hint(pack)
                logger.info(f"[Clarifier Agent] Using curated question pack for category '{category}'")

        role_prompt = f"""You collect missing information from the user before downstream tools run.

Context:
- Current user message: "{user_message}"
- Intent: {intent}
- Missing info: {slots_str}
- Already provided: {filled_slots_str}
{conversation_context}{disambiguation_hint}{expert_hint}
Generate a JSON response with:
1. "intro" - one short sentence acknowledging their request and asking for details (based on FULL conversation context, not just current message)
2. "questions" - one question per missing slot (12-25 words each, no technical terms), each with "options" and "free_text_hint"
3. "closing" - one short sentence about what you'll create for them (based on context)

Rules:
- Be contextual — reference what they already told you in the conversation
- Use the CORRECT destination from conversation history (e.g., if they said "Paris" earlier, say "Paris" not "Berlin")
- No hardcoded phrases — generate based on actual context
- Options must be answers to YOUR question, never questions themselves

Return ONLY valid JSON:
{{
  "intro": "<your generated intro>",
  "questions": [
    {{"slot": "<slot_name>", "question": "<your question>", "options": ["<choice 1>", "<choice 2>", "<choice 3>"], "free_text_hint": "<or type ...>", "type": "<single_select or multi_select>"}},
    ...
  ],
  "closing": "<your generated closing>"
}}
"""

        system_prompt = build_system_prompt(role_prompt=role_prompt, kind="snippet")
        user_prompt = f"Generate follow-up questions for these missing slots: {slots_str}"

        try:
            result_text = await self.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.settings.CLARIFIER_MODEL,
                temperature=0.3,
                max_tokens=self.settings.CLARIFIER_MAX_TOKENS,
                response_format={"type": "json_object"},
                session_id=user_message[:50] if user_message else "unknown"
            )

            result = json.loads(result_text)
            questions = result.get("questions", [])
            logger.info(f"[Clarifier Agent] Generated {len(questions)} followup questions for {len(missing_slots)} missing slots")

            # Normalize each question: require slot + question; options must be a
            # short list of non-empty strings (cap 6); free_text_hint is always
            # present when options are (the frontend renders it under the chips).
            normalized = []
            for q in questions:
                if not isinstance(q, dict) or not q.get("slot") or not q.get("question"):
                    continue
                nq: Dict[str, Any] = {"slot": q["slot"], "question": q["question"]}
                opts = q.get("options")
                if isinstance(opts, list):
                    opts = [str(o).strip() for o in opts if str(o).strip()][:6]
                    if opts:
                        nq["options"] = opts
                        nq["free_text_hint"] = str(q.get("free_text_hint") or "").strip() or "or type your own answer"
                        # Multi-select flag: only "multi_select" is meaningful (single_select
                        # is the default behavior and stays implicit). budget/use_case are
                        # always single-answer regardless of what the LLM emitted.
                        if (
                            q.get("type") == "multi_select"
                            and q["slot"] not in ("budget", "use_case")
                        ):
                            nq["type"] = "multi_select"
                normalized.append(nq)
            questions = normalized

            # Ensure we have questions for all missing slots
            if len(questions) != len(missing_slots):
                logger.warning(f"[Clarifier Agent] LLM generated {len(questions)} questions for {len(missing_slots)} slots")
                for slot in missing_slots:
                    if not any(q["slot"] == slot for q in questions):
                        questions.append({"slot": slot, "question": f"What is the {slot.replace('_', ' ')}?"})

            # Expert-first ordering, belt and braces: use_case leads, budget closes —
            # even if the LLM ignored the ordering instruction.
            questions = (
                [q for q in questions if q["slot"] == "use_case"]
                + [q for q in questions if q["slot"] not in ("use_case", "budget")]
                + [q for q in questions if q["slot"] == "budget"]
            )

            return {
                "intro": result.get("intro", "I need a few more details:"),
                "questions": questions,
                "closing": result.get("closing", "")
            }

        except Exception as e:
            logger.error(f"[Clarifier Agent] Error generating follow-up questions: {e}", exc_info=True)
            # Fallback
            return {
                "intro": "I need a few more details to help you:",
                "questions": [{"slot": slot, "question": f"What is the {slot.replace('_', ' ')}?"} for slot in missing_slots],
                "closing": ""
            }

    async def _extract_all_slots_from_answer(
        self,
        slot_names: List[str],
        user_message: str,
        followups: List[Dict[str, str]],
        optional_slots: List[str] = None
    ) -> Dict[str, Any]:
        """
        Extract ALL slot values from user's answer to follow-up questions in ONE LLM call.

        Args:
            slot_names: List of slot names to extract (both required and optional)
            user_message: User's answer message
            followups: List of followup questions that were asked (for required slots)
            optional_slots: List of optional slot names (may be mentioned but not asked)

        Returns:
            Dict mapping slot_name -> extracted_value (or None if not found)
        """
        optional_slots = optional_slots or []

        # Defense in depth: duplicate slot names make the LLM emit duplicate JSON
        # keys, and json.loads keeps the LAST occurrence — so a real value extracted
        # for the first occurrence is silently overwritten by the duplicate's null.
        # Dedupe here regardless of what the caller passed.
        slot_names = list(dict.fromkeys(slot_names))

        # Build questions context for the LLM (only for required slots that have questions).
        # Include the offered chip options so a tapped chip ("Student / everyday")
        # maps unambiguously back to its slot.
        questions_context = "\n".join([
            f"- {f['slot']}: \"{f['question']}\""
            + (f" (offered choices: {', '.join(f['options'])})" if f.get("options") else "")
            + (
                " [multi-select: the user may have picked SEVERAL choices joined by commas —"
                " the whole combined list is this ONE slot's value]"
                if f.get("type") == "multi_select" else ""
            )
            for f in followups
        ])

        # Build optional slots context
        optional_slots_context = ""
        if optional_slots:
            optional_slots_context = f"\n\nOptional slots to extract if mentioned: {', '.join(optional_slots)}"

        # Get current date for context
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")

        system_prompt = f"""You are a slot extractor. The user was asked these follow-up questions:

{questions_context}
{optional_slots_context}

The user's answer is: "{user_message}"

Extract ALL the requested slot values from the user's answer.

Rules:
- Extract ALL slots mentioned in the questions above
- ALSO extract optional slots if user mentions them (e.g., "1 child" → children: 1)
- For numbers (duration_days, adults, children, budget): return as number
- For text (destination, origin, month, budget_level, travel_style, likes): return as string
- For dates (departure_date, return_date, check_in, check_out):
  * Return in YYYY-MM-DD format
  * Today is {current_date}
  * Travel dates are ALWAYS in the future (never in the past)
  * If year is missing, infer the current year
- For budget_level: normalize to "low", "medium", or "high"
- For travel_style: extract who they're traveling with (solo, couple, family, friends, etc.)
- For likes: extract their interests/preferences as a comma-separated string
- If a slot value is not found in the answer, set it to null
- Look for common patterns:
  * "3 days" or "three days" → duration_days: 3
  * "Dec 15-20" → departure_date and return_date
  * "medium budget" or "moderate" → budget_level: "medium"
  * "with my partner" or "couple" → travel_style: "couple"
  * "food, museums" → likes: "food, museums"
  * "2 adults 1 child" or "1 kid" → adults: 2, children: 1

Return ONLY valid JSON with ALL requested slots:
{{
  {', '.join([f'"{slot}": <value or null>' for slot in slot_names])}
}}"""

        # Build messages list
        messages = [{"role": "system", "content": system_prompt}]

        # Add the user's answer
        messages.append({"role": "user", "content": f"Extract these slots from my answer: {', '.join(slot_names)}"})

        try:
            result_text = await self.generate(
                messages=messages,
                model=self.settings.CLARIFIER_MODEL,
                temperature=0.1,
                max_tokens=self.settings.CLARIFIER_MAX_TOKENS,
                response_format={"type": "json_object"},
                session_id=user_message[:50] if user_message else "unknown"
            )

            result = json.loads(result_text)

            # Filter to only return the requested slots
            extracted_slots = {slot: result.get(slot) for slot in slot_names}

            logger.info(f"[Clarifier Agent] Extracted {len([v for v in extracted_slots.values() if v is not None])}/{len(slot_names)} slots from answer")

            return extracted_slots

        except Exception as e:
            logger.error(f"[Clarifier Agent] Error extracting slots from answer: {e}", exc_info=True)
            return {slot: None for slot in slot_names}

    async def _extract_all_slots_from_conversation(
        self,
        slot_names: list,
        user_message: str,
        conversation_history: list,
        intent: str = ""
    ) -> dict:
        """
        Extract ALL missing slot values from conversation in ONE LLM call (much more efficient!).

        Args:
            slot_names: List of slot names to extract
            user_message: Current user message
            conversation_history: Full conversation history for context
            intent: User intent (travel, product, general) for context-aware extraction

        Returns:
            Dict mapping slot_name -> extracted_value (or None if not found)
        """
        # For travel intent, collect all available slots from travel tool contracts
        predefined_slots_info = ""
        slot_definitions = []

        if intent == "travel":
            tool_contracts = get_tool_contracts_dict()
            all_slots = set()
            optional_slots = set()

            # Collect all slots and their types from travel tools
            # Build slot_type_map dynamically from tool contracts
            slot_type_map = {}

            for _, contract in tool_contracts.items():
                if contract.get("intent") == "travel":
                    if "required_slots" in contract:
                        all_slots.update(contract["required_slots"])
                    if "optional_slots" in contract:
                        optional_slots.update(contract["optional_slots"])
                        all_slots.update(contract["optional_slots"])

                    # Extract slot types from contract (if defined)
                    if "slot_types" in contract:
                        for slot_name, slot_info in contract["slot_types"].items():
                            # Only add if not already defined (first contract wins)
                            if slot_name not in slot_type_map:
                                slot_type_map[slot_name] = slot_info

            # Build slot definitions for TOON format
            if all_slots:
                for slot in sorted(all_slots):
                    slot_info = slot_type_map.get(slot, {"type": "string", "format": "text"})
                    slot_definitions.append({
                        "slot": slot,
                        "type": slot_info["type"],
                        "format": slot_info["format"]
                    })

                # Format as TOON
                predefined_slots_info = "\n\nPredefined travel slots (TOON format):\n"
                predefined_slots_info += encode({"slots": slot_definitions})

        # Get current date for context
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Build slot extraction list in TOON format
        slots_to_extract = [{"slot": slot} for slot in slot_names]
        slots_to_extract_str = f"Extract these slots:\n{encode({'slots_to_extract': slots_to_extract})}"

        system_prompt = f"""You are a slot extractor. Extract ALL the following slot values from the conversation:

{slots_to_extract_str}
{predefined_slots_info}
Rules:
- Extract ALL requested slots in ONE response
- CRITICAL: Search through the ENTIRE conversation history for each slot value
- Look through ALL messages (both user and assistant) for slot values
- Common patterns when users reference previous context:
  * "show me hotels and flights for the trip" → extract origin/destination from earlier messages
  * "that fit to the trip" → extract travel details from earlier messages
  * "for this plan" → extract details from the plan discussed earlier
- For numbers (duration_days, adults, children, budget): return as number
- For text (destination, origin, month): return as string
- For dates (departure_date, return_date, check_in, check_out):
  * Return in YYYY-MM-DD format
  * Today is {current_date}
  * Travel dates are ALWAYS in the future (never in the past)
  * If year is missing, infer the current year
- If you cannot find a slot value anywhere in the conversation history, set it to null

Return ONLY valid JSON with ALL slots:
{{
  "origin": <value or null>,
  "destination": <value or null>,
  "duration_days": <value or null>,
  ...
}}"""

        # Build messages list including conversation history
        # Use new config to limit ONLY user messages (not assistant messages)
        max_user_history = self.settings.MAX_USER_HISTORY_FOR_SLOT_EXTRACTION
        logger.info(f"[Clarifier Agent] MAX_USER_HISTORY_FOR_SLOT_EXTRACTION: {max_user_history}")
        messages = [{"role": "system", "content": system_prompt}]

        # Filter and add only recent user messages from conversation history
        logger.info(f"[Clarifier Agent] conversation_history length: {len(conversation_history) if conversation_history else 0}")
        if conversation_history:
            # Extract only user messages
            user_messages = [msg for msg in conversation_history if msg.get("role") == "user"]
            logger.info(f"[Clarifier Agent] Found {len(user_messages)} user messages in history")

            # Take the last N user messages based on config
            recent_user_messages = user_messages[-max_user_history:] if len(user_messages) > max_user_history else user_messages
            logger.info(f"[Clarifier Agent] Using {len(recent_user_messages)} recent user messages for slot extraction")

            for idx, msg in enumerate(recent_user_messages):
                content = msg.get("content", "")
                logger.info(f"[Clarifier Agent] User message {idx}: content_length={len(content) if content else 0}")
                if content:
                    messages.append({"role": "user", "content": content})
                else:
                    logger.warning(f"[Clarifier Agent] Skipping user message {idx} - empty content!")

        # Always add the current user message (this is the most important one!)
        if user_message:
            messages.append({"role": "user", "content": user_message})
            logger.info(f"[Clarifier Agent] Added current user message: {user_message[:100]}...")

        logger.info(f"[Clarifier Agent] Total messages to send to LLM: {len(messages)} (system + {len(messages)-1} user messages)")

        # Add the final extraction request with priority guidance
        messages.append({"role": "user", "content": f"Extract these slots from all messages above: {', '.join(slot_names)}. The last message is the newest message. Prioritize information from newer (later) messages over older (earlier) messages when there are conflicts."})

        try:
            result_text = await self.generate(
                messages=messages,
                model=self.settings.CLARIFIER_MODEL,
                temperature=0.1,
                max_tokens=self.settings.CLARIFIER_MAX_TOKENS,
                response_format={"type": "json_object"},
                session_id=user_message[:50] if user_message else "unknown"
            )

            result = json.loads(result_text)

            # Filter to only return the requested slots
            extracted_slots = {slot: result.get(slot) for slot in slot_names}

            logger.info(f"[Clarifier Agent] Extracted {len([v for v in extracted_slots.values() if v is not None])}/{len(slot_names)} slots")

            return extracted_slots

        except Exception as e:
            logger.error(f"[Clarifier Agent] Error extracting slots: {e}", exc_info=True)
            return {slot: None for slot in slot_names}


# Agent node function for LangGraph
async def clarifier_agent_node(state: GraphState, agent: ClarifierAgent) -> GraphState:
    """
    LangGraph node wrapper for Clarifier Agent
    """
    result = await agent.execute(state)

    # Update state with clarifier results
    state.slots = result.get("slots", state.get("slots", {}))
    state.followups = result.get("followups", [])

    if result.get("next_question"):
        # HALT - return follow-up question to user
        state.assistant_text = result["next_question"]
        state.status = "halted"
        state.halt = True
        state.next_agent = None  # No next agent - waiting for user
    elif result.get("proceed_to_execution"):
        # All slots filled - proceed to plan executor
        state.next_agent = "plan_executor"
        state.status = "processing"
        state.halt = False
    else:
        # Default: proceed to plan executor
        state.next_agent = "plan_executor"
        state.status = "processing"
        state.halt = False

    state.current_agent = "clarifier"

    return state
