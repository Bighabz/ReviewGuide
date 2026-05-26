"""
LangGraph Workflow - Simplified MCP Architecture
5 main agents: Safety, Intent, Planner, Clarifier, Executor
Plus tiered routing nodes: routing_gate, tiered_executor
"""
from app.core.centralized_logger import get_logger
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from app.schemas.graph_state import GraphState
from app.core.config import settings
from app.core.colored_logging import get_colored_logger

# Import the 5 main agent classes
from app.agents.safety_agent import SafetyAgent
from app.agents.intent_agent import IntentAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.clarifier_agent import ClarifierAgent
from app.services.plan_executor import PlanExecutor

# Import tiered routing nodes
from app.services.langgraph.nodes.routing_gate import routing_gate_node
from app.services.langgraph.nodes.tiered_executor import tiered_executor_node

# RFC §1.1 — stage telemetry
from app.services.stage_telemetry import run_stage_with_budget

logger = get_logger(__name__)
colored_logger = get_colored_logger(__name__)


# Initialize agent instances
safety_agent_instance = SafetyAgent(openai_api_key=settings.OPENAI_API_KEY)
intent_agent_instance = IntentAgent()
planner_agent_instance = PlannerAgent()
clarifier_agent_instance = ClarifierAgent()
plan_executor_instance = PlanExecutor()


# Agent name to instance mapping for dynamic status message lookup
AGENT_NAME_TO_INSTANCE = {
    "agent_safety": safety_agent_instance,
    "agent_intent": intent_agent_instance,
    "agent_planner": planner_agent_instance,
    "agent_clarifier": clarifier_agent_instance,
    "agent_plan_executor": plan_executor_instance,
}


# Agent node wrapper functions
async def safety_node(state: GraphState) -> Dict[str, Any]:
    """Safety & Policy Agent Node"""
    colored_logger.agent_title("SAFETY AGENT - INPUT", agent_name="SafetyAgent")
    colored_logger.agent_data({
        "user_message": state.get('user_message', '')[:100] + "...",
        "session_id": state.get('session_id')
    }, label="Input")

    async def _run_safety(state: GraphState) -> Dict[str, Any]:
        """Inner coroutine so run_stage_with_budget can cancel it cleanly."""
        # Check if we're resuming from a halted state
        session_id = state.get("session_id")
        logger.info(f"  Checking for halt state with session_id: {session_id}")
        if session_id:
            try:
                from app.services.halt_state_manager import HaltStateManager

                halted_state_exists = await HaltStateManager.check_halt_exists(session_id)
                logger.info(f"  Halt state exists: {halted_state_exists}")

                if halted_state_exists:
                    halt_state_data = await HaltStateManager.load_halt_state(session_id)

                    if halt_state_data:
                        logger.info(f"  Found halt state - intent: {halt_state_data.get('intent')}, slots: {halt_state_data.get('slots')}")

                        followups = halt_state_data.get("followups", [])

                        if not followups or len(followups) == 0:
                            logger.info("  ✗ Halt state exists but NO followups - treating as NEW query, clearing stale halt state")
                            await HaltStateManager.delete_halt_state(session_id)
                        else:
                            logger.info(f"  ✓ Halt state has {len(followups)} followup(s) - RESUMING TO CLARIFIER")

                            resume_update = {
                                "policy_status": "allow",
                                "sanitized_text": state.get("user_message"),
                                "redaction_map": {},
                                "current_agent": "safety",
                                "next_agent": "clarifier",
                            }

                            if halt_state_data.get("intent"):
                                resume_update["intent"] = halt_state_data["intent"]
                                logger.info(f"  ✓ RESTORED INTENT: {halt_state_data['intent']}")

                            if halt_state_data.get("slots"):
                                resume_update["slots"] = halt_state_data["slots"]
                                logger.info(f"  ✓ RESTORED SLOTS: {halt_state_data['slots']}")

                            if halt_state_data.get("plan"):
                                resume_update["plan"] = halt_state_data["plan"]
                                num_steps = len(halt_state_data["plan"].get("steps", []))
                                logger.info(f"  ✓ RESTORED PLAN: {num_steps} steps")

                            return resume_update
                else:
                    logger.info("  No halt state found - routing to intent agent (normal flow)")
            except Exception as e:
                logger.error(f"Error checking halt state: {e}", exc_info=True)

        result = await safety_agent_instance.execute(state)

        user_message = state.get("user_message")
        conversation_history = state.get("conversation_history", []).copy()

        if user_message:
            conversation_history.append({
                "role": "user",
                "content": user_message
            })
            logger.info(f"[SafetyAgent] Added user message to conversation_history state ({len(conversation_history)} total messages)")

        update = {
            "policy_status": result["policy_status"],
            "sanitized_text": result["sanitized_text"],
            "redaction_map": result["redaction_map"],
            "current_agent": "safety",
            "conversation_history": conversation_history,
        }

        if result.get("errors"):
            update["errors"] = result["errors"]
            update["status"] = "error"
            update["next_agent"] = None
        elif result["policy_status"] == "block":
            update["status"] = "error"
            update["assistant_text"] = "I cannot process this request due to content policy violations."
            update["next_agent"] = None
        else:
            update["next_agent"] = "intent"

        return update

    # RFC §1.1 — fallback on hard timeout: pass through with policy_status="unchecked"
    fallback = {
        "policy_status": "unchecked",
        "sanitized_text": state.get("user_message"),
        "redaction_map": {},
        "current_agent": "safety",
        "next_agent": "intent",
    }

    update, telemetry = await run_stage_with_budget(
        "safety",
        _run_safety(state),
        input_size=len(state.get("user_message", "")),
        fallback_result=fallback,
        error_class_on_timeout="transient",
    )

    update["stage_telemetry"] = [telemetry.to_dict()]

    colored_logger.agent_title("SAFETY AGENT - OUTPUT", agent_name="SafetyAgent")
    colored_logger.agent_data({
        "policy_status": update.get('policy_status'),
        "next_agent": update.get('next_agent'),
        "errors": update.get('errors', []),
        "telemetry_ms": telemetry.duration_ms,
        "timeout_hit": telemetry.timeout_hit,
    }, label="Output")

    return update


async def intent_node(state: GraphState) -> Dict[str, Any]:
    """Intent & Slot-Filling Agent Node"""
    colored_logger.agent_title("INTENT AGENT - INPUT", agent_name="IntentAgent")
    colored_logger.agent_data({
        "sanitized_text": state.get('sanitized_text', '')[:100] + "..."
    }, label="Input")

    async def _run_intent(state: GraphState) -> Dict[str, Any]:
        """Inner coroutine wrapped by run_stage_with_budget."""
        result = await intent_agent_instance.execute(state)

        from app.services.halt_state_manager import HaltStateManager
        session_id = state.get("session_id")
        halt_state = await HaltStateManager.get_halt_state(session_id) if session_id else None

        slots = halt_state.get("slots", {}) if halt_state else {}
        followups = halt_state.get("followups", []) if halt_state else []

        update = {
            "intent": result["intent"],
            "current_agent": "intent",
            "_slots_for_log": slots,
            "_followups_for_log": followups,
        }

        if result.get("intro_text"):
            update["intro_text"] = result["intro_text"]
            update["assistant_text"] = result["intro_text"]
            logger.info(f"  Added intro to assistant_text: {result['intro_text'][:100]}...")

        if result["intent"] in ["product", "travel", "service", "comparison", "general", "intro", "unclear"]:
            update["next_agent"] = "planner"
            logger.info(f"  {result['intent']} intent -> PLANNER AGENT")
        else:
            update["status"] = "error"
            update["assistant_text"] = "I'm not sure how to help with that."
            update["next_agent"] = None
            logger.warning(f"  Unknown intent: {result['intent']}")

        return update

    # RFC §1.1 — fallback on hard timeout: default to "general" intent
    fallback = {
        "intent": "general",
        "current_agent": "intent",
        "next_agent": "planner",
        "_slots_for_log": {},
        "_followups_for_log": [],
    }

    update, telemetry = await run_stage_with_budget(
        "intent",
        _run_intent(state),
        input_size=len(state.get("sanitized_text") or state.get("user_message", "")),
        fallback_result=fallback,
        error_class_on_timeout="transient",
    )

    # Pop internal log-only keys before returning to LangGraph
    slots = update.pop("_slots_for_log", {})
    followups = update.pop("_followups_for_log", [])
    missing_slots = [f["slot"] for f in followups if isinstance(f, dict) and "slot" in f]

    update["stage_telemetry"] = [telemetry.to_dict()]

    colored_logger.agent_title("INTENT AGENT - OUTPUT", agent_name="IntentAgent")
    colored_logger.agent_data({
        "intent": update.get('intent'),
        "slots": list(slots.keys()),
        "missing_slots": missing_slots,
        "intro_text": (update.get('intro_text', '')[:50] + "...") if update.get('intro_text') else 'None',
        "next_agent": update.get('next_agent'),
        "telemetry_ms": telemetry.duration_ms,
        "timeout_hit": telemetry.timeout_hit,
    }, label="Output")

    return update


async def planner_node(state: GraphState) -> Dict[str, Any]:
    """Planner Agent Node - Generates dynamic execution plan using MCP tools"""
    colored_logger.agent_title("PLANNER AGENT - INPUT", agent_name="PlannerAgent")
    colored_logger.agent_data({
        "user_message": state.get('user_message', '')[:100] + "...",
        "intent": state.get('intent'),
        "slots": state.get('slots', {}),
    }, label="Input")

    async def _run_planner(state: GraphState) -> Dict[str, Any]:
        """Inner coroutine wrapped by run_stage_with_budget."""
        result = await planner_agent_instance.execute(state)
        return {
            "plan": result["plan"],
            "current_agent": "planner",
            "status": result.get("status", "running"),
            "next_agent": "clarifier",
        }

    # RFC §1.1 — fallback on hard timeout: use a minimal fast-path template plan
    _intent = state.get("intent", "general")
    fallback_plan = {
        "steps": [
            {
                "id": "compose",
                "tools": [f"{_intent}_compose" if _intent in ("product", "travel", "general") else "general_compose"],
                "description": "Fast-path composition (planner timed out)",
                "parallel": False,
                "depends_on": [],
            }
        ]
    }
    fallback = {
        "plan": fallback_plan,
        "current_agent": "planner",
        "status": "running",
        "next_agent": "clarifier",
    }

    update, telemetry = await run_stage_with_budget(
        "planner",
        _run_planner(state),
        input_size=len(state.get("user_message", "")),
        fallback_result=fallback,
        error_class_on_timeout="transient",
    )

    update["stage_telemetry"] = [telemetry.to_dict()]

    plan = update.get("plan") or {}
    colored_logger.agent_title("PLANNER AGENT - OUTPUT", agent_name="PlannerAgent")
    colored_logger.agent_data({
        "num_steps": len(plan.get("steps", [])),
        "steps": [step["id"] for step in plan.get("steps", [])],
        "status": update.get('status'),
        "next_agent": update.get('next_agent'),
        "telemetry_ms": telemetry.duration_ms,
        "timeout_hit": telemetry.timeout_hit,
    }, label="Output")

    return update


async def clarifier_node(state: GraphState) -> Dict[str, Any]:
    """Clarifier Agent Node - Checks required slots and generates follow-up questions"""
    colored_logger.agent_title("CLARIFIER AGENT - INPUT", agent_name="ClarifierAgent")
    colored_logger.agent_data({
        "plan_steps": len(state.get('plan', {}).get('steps', [])),
        "current_slots": list(state.get('slots', {}).keys()),
    }, label="Input")

    async def _run_clarifier(state: GraphState) -> Dict[str, Any]:
        """Inner coroutine wrapped by run_stage_with_budget."""
        result = await clarifier_agent_instance.execute(state)

        update = {
            "slots": result.get("slots", state.get("slots", {})),
            "followups": result.get("followups", []),
            "current_agent": "clarifier",
            "_proceed": result.get("proceed_to_execution", False),
            "_next_question": result.get("next_question"),
        }

        logger.info(f"DEBUG: Clarifier returning slots to state: {update['slots']}")

        if result.get("next_question"):
            update["assistant_text"] = result["next_question"]
            update["status"] = "halted"
            update["halt"] = True
            update["next_agent"] = None
            logger.info(f"[Clarifier] HALTED - returning question: {result['next_question']}")
        elif result.get("proceed_to_execution"):
            update["next_agent"] = "plan_executor"
            update["status"] = "running"
            logger.info(f"[Clarifier] All slots filled - proceeding to execution")
        else:
            update["next_agent"] = "plan_executor"
            update["status"] = "running"

        return update

    # RFC §1.1 — fallback on hard timeout: skip clarification and proceed as-is
    fallback = {
        "slots": state.get("slots", {}),
        "followups": [],
        "current_agent": "clarifier",
        "next_agent": "plan_executor",
        "status": "running",
        "_proceed": True,
        "_next_question": None,
    }

    update, telemetry = await run_stage_with_budget(
        "clarifier",
        _run_clarifier(state),
        input_size=len(state.get("user_message", "")),
        fallback_result=fallback,
        error_class_on_timeout="transient",
    )

    # Pop internal log-only keys
    proceed = update.pop("_proceed", False)
    next_question = update.pop("_next_question", None)

    update["stage_telemetry"] = [telemetry.to_dict()]

    colored_logger.agent_title("CLARIFIER AGENT - OUTPUT", agent_name="ClarifierAgent")
    colored_logger.agent_data({
        "slots": list(update.get('slots', {}).keys()),
        "num_followups": len(update.get('followups', [])),
        "next_question": next_question or 'None',
        "proceed": proceed,
        "status": update.get('status'),
        "next_agent": update.get('next_agent'),
        "telemetry_ms": telemetry.duration_ms,
        "timeout_hit": telemetry.timeout_hit,
    }, label="Output")

    return update


async def plan_executor_node(state: GraphState) -> Dict[str, Any]:
    """Plan Executor Node - Executes MCP-based dynamic plan with parallel execution"""
    colored_logger.agent_title("PLAN EXECUTOR - INPUT", agent_name="PlanExecutor")
    plan = state.get("plan", {})

    slots_in_state = state.get("slots", {})
    logger.info(f"DEBUG: Plan Executor node received state with slots: {slots_in_state}")

    colored_logger.agent_data({
        "num_steps": len(plan.get("steps", [])),
        "step_ids": [step["id"] for step in plan.get("steps", [])],
    }, label="Input")

    async def _run_plan_executor(state: GraphState) -> Dict[str, Any]:
        """Inner coroutine wrapped by run_stage_with_budget."""
        # Create a fresh PlanExecutor per request to prevent cross-session state leaks.
        # The old module-level singleton shared self.context/self.state across concurrent requests.
        executor = PlanExecutor()
        results = await executor.execute(plan, state)
        inner_update = {
            "assistant_text": results.get("assistant_text", ""),
            "ui_blocks": results.get("ui_blocks", []),
            "citations": results.get("citations", []),
            "next_suggestions": results.get("next_suggestions", []),
            "tool_citations": results.get("tool_citations", []),
            # B.3 follow-up — propagate the structured follow_up_question
            # from plan_executor's results into the LangGraph state update.
            # Without this, PR #13's _extract_results fix is silently dropped
            # at the node boundary: LangGraph only merges what the node
            # returns, so a field present in `results` but missing from
            # `inner_update` never lands in GraphState. chat.py then reads
            # result_state.get("follow_up_question") as None and skips the
            # SSE event. Detected 2026-05-25 post-PR #13 prod verification.
            "follow_up_question": results.get("follow_up_question"),
            # affiliate_products is written to self.state by product_affiliate
            # via _write_tool_outputs_to_state, then lifted into results by
            # _extract_results. Without this entry, chat.py never sees it and
            # always reports amazon/ebay as "unavailable".
            "affiliate_products": results.get("affiliate_products", {}),
            "current_agent": "plan_executor",
            "status": "halted" if results.get("halt") else "completed",
            "next_agent": None,
            "_halt": results.get("halt", False),
            "_followups": results.get("followups", []),
            "_questions": results.get("questions", []),
        }
        return inner_update

    # RFC §1.1 — fallback on hard timeout: partial results with degraded flag
    fallback = {
        "assistant_text": "I was only able to gather partial results. Please try again for a complete response.",
        "ui_blocks": [],
        "citations": [],
        "next_suggestions": [],
        "tool_citations": [],
        "follow_up_question": None,
        "affiliate_products": {},
        "current_agent": "plan_executor",
        "status": "completed",
        "next_agent": None,
        "_halt": False,
        "_followups": [],
        "_questions": [],
    }

    update, telemetry = await run_stage_with_budget(
        "plan_exec",
        _run_plan_executor(state),
        input_size=len(plan.get("steps", [])),
        fallback_result=fallback,
        error_class_on_timeout="transient",
    )

    # Pop internal keys, handle halt state
    halt = update.pop("_halt", False)
    followups = update.pop("_followups", [])
    questions = update.pop("_questions", [])

    if halt:
        update["halt"] = True
        update["followups"] = followups
        update["followup_questions"] = questions

    update["stage_telemetry"] = [telemetry.to_dict()]

    colored_logger.agent_title("PLAN EXECUTOR - OUTPUT", agent_name="PlanExecutor")
    colored_logger.agent_data({
        "assistant_text_length": len(update.get('assistant_text', '')),
        "num_citations": len(update.get('citations', [])),
        "num_ui_blocks": len(update.get('ui_blocks', [])),
        "halted": halt,
        "status": update.get('status'),
        "telemetry_ms": telemetry.duration_ms,
        "timeout_hit": telemetry.timeout_hit,
    }, label="Output")

    return update


# Routing function
def route_next_agent(state: GraphState) -> str:
    """Determine next agent based on state"""
    status = state.get("status", "running")
    next_agent = state.get("next_agent")

    if status in ["error", "completed", "halted"]:
        return END

    # Route based on next_agent field
    if next_agent:
        return next_agent

    return END


# Build the graph
def build_workflow() -> StateGraph:
    """Build the LangGraph workflow with 5 agents plus tiered routing nodes"""
    logger.info("Building LangGraph workflow (5 agents + tiered routing)")

    workflow = StateGraph(GraphState)

    # Add the 5 main agent nodes
    workflow.add_node("agent_safety", safety_node)
    workflow.add_node("agent_intent", intent_node)
    workflow.add_node("agent_planner", planner_node)
    workflow.add_node("agent_clarifier", clarifier_node)
    workflow.add_node("agent_plan_executor", plan_executor_node)

    # Add tiered routing nodes
    workflow.add_node("routing_gate", routing_gate_node)
    workflow.add_node("tiered_executor", tiered_executor_node)

    # Set entry point
    workflow.set_entry_point("agent_safety")

    # Add conditional edges
    workflow.add_conditional_edges(
        "agent_safety",
        route_next_agent,
        {
            "intent": "agent_intent",
            "clarifier": "agent_clarifier",  # For resuming halt state
            "tiered_executor": "tiered_executor",  # For resuming from consent halt
            END: END,
        }
    )

    workflow.add_conditional_edges(
        "agent_intent",
        route_next_agent,
        {
            "planner": "agent_planner",
            END: END,
        }
    )

    workflow.add_conditional_edges(
        "agent_planner",
        route_next_agent,
        {
            "clarifier": "agent_clarifier",
            END: END,
        }
    )

    workflow.add_conditional_edges(
        "agent_clarifier",
        route_next_agent,
        {
            "plan_executor": "agent_plan_executor",
            "routing_gate": "routing_gate",  # Route to hybrid routing gate
            END: END,
        }
    )

    # Routing gate decides between tiered executor and LLM planner
    workflow.add_conditional_edges(
        "routing_gate",
        route_next_agent,
        {
            "tiered_executor": "tiered_executor",
            "planner": "agent_planner",
            END: END,
        }
    )

    # Tiered executor routes to plan_executor (synthesizer) or halts
    workflow.add_conditional_edges(
        "tiered_executor",
        route_next_agent,
        {
            "synthesizer": "agent_plan_executor",  # synthesizer maps to plan_executor
            "plan_executor": "agent_plan_executor",
            END: END,
        }
    )

    workflow.add_conditional_edges(
        "agent_plan_executor",
        route_next_agent,
        {
            END: END,
        }
    )

    logger.info("✅ Workflow compiled: Safety → Intent → Planner → Clarifier → [RoutingGate → TieredExecutor] → Executor")
    return workflow.compile()


# Create global workflow instance
graph = build_workflow()
logger.info("LangGraph workflow compiled successfully")
