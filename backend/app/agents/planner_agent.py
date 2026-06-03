"""
Planner Agent

Responsibilities:
- Analyze user request and available MCP tools
- Generate dynamic execution plan (DAG)
- Optimize for parallelism where possible
- NO hardcoded intent-based routing
"""

from app.core.centralized_logger import get_logger
import json
import sys
import os
from typing import Dict, Any, List, Optional

# Add MCP server to path for tool contract imports
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
mcp_server_path = os.path.join(backend_dir, 'mcp_server')
if mcp_server_path not in sys.path:
    sys.path.insert(0, mcp_server_path)

from tool_contracts import (  # noqa: E402
    get_tool_catalog,
    get_tool_contracts_dict,
    get_required_tools_from_dependencies,
    format_non_default_contracts_for_prompt,
    get_selectable_tools_for_intent,
    _get_contracts_cached
)

from app.agents.base_agent import BaseAgent
from app.agents.query_complexity import classify_query_complexity
from app.core.error_manager import AgentError
from app.services.model_service import model_service

logger = get_logger(__name__)


# Planner system prompt - returns simple tool list
# The system handles dependency ordering automatically based on pre/post in tool contracts
PLANNER_SYSTEM_PROMPT = """You are a tool selector for intent={intent}.

Your job: Select which entry-point tools are needed based on the user's request.

Read each tool's "purpose" field and decide if it matches what the user is asking for.

TOOL SELECTION RULES:
1. ONLY select tools from the provided list
2. Read the "purpose" field to understand what each tool DOES
3. Read the "not_for" field to understand what each tool should NOT be used for
4. The "not_for" field lists purposes handled by OTHER specialized tools
5. DO NOT select a tool if the user's request matches its "not_for" field
6. Prefer specialized tools over general/fallback tools when applicable
7. Return tool names as a flat JSON array
8. Downstream tools (normalize, affiliate, compose) are auto-added based on dependencies
9. Don't worry about ordering - the system will sort tools by dependencies
10. You must select at least one entry-point tool

EXAMPLE:
User asks: "compare iPhone 16 and Samsung S24"
- product_comparison: purpose="compare products", not_for=None → SELECT (matches request)
- product_general_information: purpose="general knowledge", not_for=["product search", "product comparison"] → DO NOT SELECT (user wants comparison, which is in not_for)

OUTPUT FORMAT:
{{"tools": ["tool_name_1", "tool_name_2"]}}"""


class PlannerAgent(BaseAgent):
    """
    Planner Agent - Creates dynamic execution plans

    Uses GPT-4o-mini to analyze user requests and generate execution plans
    that specify which MCP tools to call, in what order, with what arguments.
    """

    COMPLEXITY_CONFIDENCE_THRESHOLD = 0.7

    def __init__(self):
        super().__init__(
            agent_name="planner",
            on_chain_start_message="Planning your request..."
        )

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point - implements BaseAgent.run()
        """
        return await self.execute(state)

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate execution plan based on user request and available tools.

        Args:
            state: Graph state containing user_message, intent, slots, etc.

        Returns:
            Updated state with plan field
        """
        
        try:
            # Log agent input (GREEN)
            self.log_input(
                user_message=state.get("user_message"),
                intent=state.get("intent"),
                slots=state.get("slots")
            )

            self.colored_logger.info("🧠 Planner Agent starting...")

            intent = state.get("intent", "general")

            # Handle simple intents with manual plans (no LLM needed)
            if intent == "unclear":
                plan = self._create_manual_plan_for_unclear()
                self.colored_logger.info("📋 Using manual plan for unclear intent")
            elif intent == "intro":
                plan = self._create_manual_plan_for_intro()
                self.colored_logger.info("📋 Using manual plan for intro intent")
            elif intent == "travel":
                plan = self._create_fast_path_travel_plan()
                self.colored_logger.info("🚀 FAST PATH: travel intent → hardcoded template")
            elif intent == "product":
                user_message = state.get("user_message", "")
                slots = state.get("slots", {})
                complexity, confidence = classify_query_complexity(user_message, slots, intent)
                logger.info(f"[planner] Query complexity: {complexity} (confidence={confidence:.2f})")

                if confidence < self.COMPLEXITY_CONFIDENCE_THRESHOLD:
                    # Fall back to LLM planner for uncertain cases
                    logger.info(
                        f"[planner] Confidence {confidence:.2f} < threshold "
                        f"{self.COMPLEXITY_CONFIDENCE_THRESHOLD}, using LLM planner"
                    )
                    available_tools = list(get_tool_contracts_dict().values())
                    context = await self._build_planning_context(state, available_tools)
                    plan = await self._generate_plan(context, state)
                    self._validate_plan(plan, available_tools)
                else:
                    plan = self._get_product_plan_for_complexity(complexity)
                    # Validate fast-path plans same as LLM-generated plans
                    available_tools_for_validation = list(get_tool_contracts_dict().values())
                    self._validate_plan(plan, available_tools_for_validation)
                    self.colored_logger.info(
                        f"🚀 FAST PATH: product intent → {complexity} template "
                        f"(confidence={confidence:.2f})"
                    )
            else:
                # Get tool contracts directly (no MCP subprocess needed)
                available_tools = list(get_tool_contracts_dict().values())

                self.colored_logger.info(f"📋 {len(available_tools)} tools available")

                # Build context for planner
                context = await self._build_planning_context(state, available_tools)

                # Generate plan using LLM
                plan = await self._generate_plan(context, state)

                # Validate plan
                self._validate_plan(plan, available_tools)

            self.colored_logger.info(f"✅ Generated plan with {len(plan['steps'])} steps")

            # Log plan for debugging
            for i, step in enumerate(plan['steps'], 1):
                # Handle both old format (dicts) and new format (strings)
                tools = step.get('tools', [])
                tool_names = [tool.get('name', 'unknown') if isinstance(tool, dict) else tool for tool in tools]
                self.colored_logger.info(
                    f"  Step {i} ({step['id']}): "
                    f"{len(step['tools'])} tool(s) [{', '.join(tool_names)}], "
                    f"parallel={step.get('parallel', False)}"
                )

            result = {
                "plan": plan,
                "status": "running",
                "next_agent": "plan_executor"
            }

            # Log agent output (GREEN)
            self.log_output({
                "plan_steps": len(plan['steps']),
                "total_tools": sum(len(step['tools']) for step in plan['steps'])
            })

            return result

        except Exception as e:
            logger.error(f"Planner Agent error: {str(e)}", exc_info=True)
            raise AgentError(self.agent_name, f"Planning failed: {str(e)}", e)

    async def _build_planning_context(
        self,
        state: Dict[str, Any],
        available_tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Build context dict for the planner LLM.

        Args:
            state: Graph state
            available_tools: List of available MCP tools

        Returns:
            Planning context dict
        """
        context = {
            "user_message": state.get("user_message", ""),
            "intent": state.get("intent", "general"),
            "slots": state.get("slots", {}),
            "conversation_history": state.get("conversation_history", [])[-3:],  # Last 3 messages
            "available_tools": available_tools
        }

        return context

    async def _generate_plan(
        self,
        context: Dict[str, Any],
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate execution plan using LLM.

        Args:
            context: Planning context
            state: Graph state (for tracing)

        Returns:
            Execution plan dict

        Raises:
            AgentError: If plan generation fails
        """
        intent = context.get("intent", "general")

        # Get only non-default tools for LLM to plan with
        # Default tools (compose, normalize, affiliate, next_step_suggestion) are auto-injected
        tool_catalog = format_non_default_contracts_for_prompt(intent)
        logger.info(f"Tool catalog for LLM:\\n{tool_catalog}")

        # Build conversation context for planner
        conversation_context = ""
        conversation_history = context.get("conversation_history", [])
        if conversation_history:
            history_lines = []
            for msg in conversation_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content and role in ["user", "assistant"]:
                    history_lines.append(f"{role}: {content}")
            if history_lines:
                conversation_context = "\n\nRecent conversation:\n" + "\n".join(history_lines)
                logger.info(f"[Planner] Added {len(history_lines)} messages from conversation history")

        # Build user message for planner
        user_prompt = f"""Select entry-point tools for this request:

User message: {context['user_message']}
Intent: {context['intent']}
Slots: {json.dumps(context['slots'], indent=2)}
{conversation_context}

{tool_catalog}

Return ONLY the tool names as a JSON array. Downstream tools will be auto-added based on dependencies.
Example: {{"tools": ["product_search"]}} - this will auto-add normalize, affiliate, compose"""

        # Call LLM to generate tool list
        try:
            response = await self.generate(
                messages=[
                    {"role": "system", "content": "You are a tool selector. Analyze user message and conversation history to select the right tools. Return tool names as JSON array."},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.settings.PLANNER_MODEL,
                temperature=0.3,  # Low temperature for consistent planning
                max_tokens=self.settings.PLANNER_MAX_TOKENS,
                response_format={"type": "json_object"},
                session_id=state.get("session_id"),
                max_retries=2
            )

            # Log the raw LLM response in YELLOW
            self.colored_logger.api_output(
                response,
                endpoint="Planner LLM Response"
            )

            # Parse tool list
            result = json.loads(response)

            if "tools" not in result:
                raise AgentError(self.agent_name, "Response missing 'tools' field")

            selected_tools = result["tools"]
            logger.info(f"LLM selected tools: {selected_tools}")

            # Step 2: Expand selected tools by following post dependencies
            # Downstream tools (normalize, affiliate, compose, next_step) are auto-added
            all_tool_names = get_required_tools_from_dependencies(selected_tools, intent)
            logger.info(f"Tools after dependency expansion: {all_tool_names}")

            # Step 3: Sort tools by dependencies using topological sort
            sorted_tools = self._sort_by_dependencies(all_tool_names)
            logger.info(f"Dependency-sorted tools: {sorted_tools}")

            # Step 4: Create execution plan from sorted tools
            plan = self._create_plan_from_sorted_tools(sorted_tools)

            return plan

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse plan JSON: {e}\nResponse: {response}")
            raise AgentError(self.agent_name, f"Invalid plan JSON: {e}", e)
        except Exception as e:
            raise AgentError(self.agent_name, f"Plan generation failed: {e}", e)

    def _sort_by_dependencies(self, tool_names: List[str]) -> List[str]:
        """
        Sort tools using topological sort based on their pre/post dependencies.

        Args:
            tool_names: List of tool names to sort

        Returns:
            List of tool names sorted by dependency order

        Raises:
            AgentError: If circular dependency detected
        """
        # Get contracts for these tools
        all_contracts = _get_contracts_cached()
        tool_contracts = {
            c["name"]: c for c in all_contracts
            if c["name"] in tool_names
        }

        # Build dependency graph using "pre" field
        # graph[tool] = list of tools that must come before it (from "pre" field)
        graph = {}
        in_degree = {}

        # Build dependency graph from "tools.pre" field
        for tool_name in tool_names:
            contract = tool_contracts.get(tool_name)
            if not contract:
                # Tool not found - add it anyway with no dependencies
                graph[tool_name] = []
                in_degree[tool_name] = 0
                continue

            # Get "tools.pre" dependencies - tools that must run before this one
            tools_field = contract.get("tools", {})
            pre_tools = tools_field.get("pre", [])

            # Filter to only include tools that are in our current plan
            dependencies = [t for t in pre_tools if t in tool_names]

            graph[tool_name] = dependencies
            in_degree[tool_name] = len(dependencies)

        # Add reverse dependencies from "tools.post" field
        # If tool A has post=[B], then B must run after A, meaning A is a dependency of B
        for tool_name in tool_names:
            contract = tool_contracts.get(tool_name)
            if not contract:
                continue

            tools_field = contract.get("tools", {})
            post_tools = tools_field.get("post", [])
            for post_tool in post_tools:
                if post_tool in tool_names:
                    # post_tool must run after tool_name
                    # So tool_name is a dependency of post_tool
                    if tool_name not in graph[post_tool]:
                        graph[post_tool].append(tool_name)
                        in_degree[post_tool] += 1

        # Topological sort using Kahn's algorithm
        sorted_tools = []
        queue = [tool for tool, degree in in_degree.items() if degree == 0]

        # Helper to get sort key - only use tool_order if defined
        def get_sort_key(tool_name: str) -> tuple:
            contract = tool_contracts.get(tool_name, {})
            has_order = "tool_order" in contract
            order = contract.get("tool_order", 0)
            # Tools with tool_order come after tools without (sorted by order)
            # Tools without tool_order maintain their original position
            return (has_order, order)

        while queue:
            # Sort queue: tools without tool_order first, then by tool_order
            queue.sort(key=get_sort_key)

            current = queue.pop(0)
            sorted_tools.append(current)

            # Reduce in-degree for tools that depend on current tool
            for tool_name, deps in graph.items():
                if current in deps:
                    in_degree[tool_name] -= 1
                    if in_degree[tool_name] == 0:
                        queue.append(tool_name)

        # Check for circular dependencies
        if len(sorted_tools) != len(tool_names):
            missing = set(tool_names) - set(sorted_tools)
            raise AgentError(
                self.agent_name,
                f"Circular dependency detected in tools: {missing}"
            )

        # Post-process: Move tools with tool_order to their correct position
        # Tools with tool_order should be sorted among themselves at the end
        tools_without_order = []
        tools_with_order = []

        for tool in sorted_tools:
            contract = tool_contracts.get(tool, {})
            if "tool_order" in contract:
                tools_with_order.append(tool)
            else:
                tools_without_order.append(tool)

        # Sort tools with order by their tool_order value
        tools_with_order.sort(key=lambda t: tool_contracts.get(t, {}).get("tool_order", 0))

        return tools_without_order + tools_with_order

    def _create_plan_from_sorted_tools(self, sorted_tools: List[str]) -> Dict[str, Any]:
        """
        Create execution plan from sorted tool list.

        Each tool becomes a separate step for now (no parallelization).
        Future enhancement: detect tools with no dependencies between them and run in parallel.

        Args:
            sorted_tools: List of tool names in dependency order

        Returns:
            Execution plan dict with steps
        """
        steps = []
        for i, tool_name in enumerate(sorted_tools, 1):
            steps.append({
                "id": f"step_{i}",
                "tools": [tool_name],
                "parallel": False
            })

        return {"steps": steps}

    def _validate_plan(
        self,
        plan: Dict[str, Any],
        available_tools: List[Dict[str, Any]]
    ) -> None:
        """
        Validate that the plan is well-formed.

        Args:
            plan: Generated plan
            available_tools: Available tools

        Raises:
            AgentError: If validation fails
        """
        tool_names = {tool["name"] for tool in available_tools}
        step_ids = set()

        for step in plan.get("steps", []):
            # Check required fields
            if "id" not in step:
                raise AgentError(self.agent_name, "Step missing 'id' field")
            if "tools" not in step:
                raise AgentError(self.agent_name, f"Step {step['id']} missing 'tools' field")

            # Check for duplicate step IDs
            if step["id"] in step_ids:
                raise AgentError(self.agent_name, f"Duplicate step ID: {step['id']}")
            step_ids.add(step["id"])

            # Validate dependencies
            for dep in step.get("depends_on", []):
                if dep not in step_ids:
                    # Dependency might be forward reference - we'll validate at execution time
                    pass

            # Validate tool names (now just strings, not dicts)
            for tool_name in step["tools"]:
                # Handle both old format (dicts) and new format (strings)
                if isinstance(tool_name, dict):
                    tool_name = tool_name.get("name")

                if not tool_name:
                    raise AgentError(self.agent_name, f"Tool call missing name in step {step['id']}")
                if tool_name not in tool_names:
                    raise AgentError(
                        self.agent_name,
                        f"Unknown tool '{tool_name}' in step {step['id']}"
                    )

        logger.info(f"Plan validation passed: {len(plan['steps'])} steps, {len(step_ids)} unique IDs")

    def _ensure_next_step_suggestion(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure next_step_suggestion is always the final step in the plan.
        This guarantees follow-up questions are generated for every response.

        Args:
            plan: Generated plan from LLM

        Returns:
            Plan with next_step_suggestion as the final step
        """
        steps = plan.get("steps", [])

        # Check if next_step_suggestion is already in the plan
        has_next_step = any(
            "next_step_suggestion" in step.get("tools", [])
            for step in steps
        )

        if has_next_step:
            # Ensure it's the last step
            for i, step in enumerate(steps):
                if "next_step_suggestion" in step.get("tools", []):
                    if i != len(steps) - 1:
                        # Move it to the end
                        next_step = steps.pop(i)
                        steps.append(next_step)
                        logger.info("Moved next_step_suggestion to final step")
                    break
        else:
            # Add next_step_suggestion as the final step
            final_step_id = f"step_{len(steps) + 1}"
            steps.append({
                "id": final_step_id,
                "tools": ["next_step_suggestion"],
                "parallel": False
            })
            logger.info(f"Added next_step_suggestion as final step: {final_step_id}")

        plan["steps"] = steps
        return plan

    def _create_manual_plan_for_unclear(self) -> Dict[str, Any]:
        """
        Create a manual plan for unclear/gibberish input.
        No LLM needed - just run unclear_compose tool.

        Returns:
            Execution plan dict
        """
        return {
            "steps": [
                {
                    "id": "step_1",
                    "tools": ["unclear_compose"],
                    "parallel": False
                }
            ]
        }

    def _get_product_plan_for_complexity(self, complexity: str) -> Dict[str, Any]:
        """Return execution plan template based on query complexity class."""
        # product_extractor is only needed for comparisons (to parse "X vs Y") and factoids.
        # For recommendations/deep_research, product_search already resolves products.
        needs_extractor = complexity in ("factoid", "comparison")
        if complexity == "factoid":
            plan = self._create_minimal_product_plan()
        elif complexity in ("comparison", "recommendation"):
            plan = self._create_standard_product_plan(include_extractor=needs_extractor)
        else:  # deep_research
            plan = self._create_fast_path_product_plan(include_extractor=False)
        return self._ensure_next_step_suggestion(plan)

    def _create_minimal_product_plan(self) -> Dict[str, Any]:
        """
        Minimal plan for factoid queries (e.g., 'what year was Sony XM5 released?').
        Pipeline: extractor → product_general_information → compose → suggestions
        Skips search, reviews, affiliate, ranking.
        """
        return {
            "steps": [
                {"id": "step_1", "tools": ["product_extractor"], "parallel": False},
                {"id": "step_2", "tools": ["product_general_information"], "parallel": False},
                {"id": "step_3", "tools": ["product_compose"], "parallel": False},
            ]
        }

    def _create_standard_product_plan(self, include_extractor: bool = True) -> Dict[str, Any]:
        """
        Standard plan for comparison and recommendation queries.
        Pipeline: [extractor →] [product_search ∥ evidence] → [review_search →] normalize → affiliate → ranking → compose → suggestions
        review_search is inserted only when
        USE_REVIEW_GROUNDING is on — it fetches real review evidence (so the
        composer takes the editorial path) at a ~+8s latency cost, and self-gates
        on ENABLE_SERPAPI (empty review_data → concierge path, unchanged).

        product_ranking (Outcome 9) runs after affiliate so it can see real offer
        prices, and before compose so the composer can mirror its budget-aware
        value order. It's pure computation — no LLM, no network — so the latency
        cost is negligible.
        """
        steps = []
        step_num = 1
        if include_extractor:
            steps.append({"id": f"step_{step_num}", "tools": ["product_extractor"], "parallel": False})
            step_num += 1
        steps.append({"id": f"step_{step_num}", "tools": ["product_search", "product_evidence"], "parallel": True})
        step_num += 1
        # Tier 5 / A1: real review evidence in the standard flow. review_search must
        # run after product_search (pre-req) and before product_normalize (its
        # review_data is merged in normalize and flips compose to the editorial path).
        if self.settings.USE_REVIEW_GROUNDING:
            steps.append({"id": f"step_{step_num}", "tools": ["review_search"], "parallel": False})
            step_num += 1
        steps.extend([
            {"id": f"step_{step_num}", "tools": ["product_normalize"], "parallel": False},
            {"id": f"step_{step_num + 1}", "tools": ["product_affiliate"], "parallel": False},
            {"id": f"step_{step_num + 2}", "tools": ["product_ranking"], "parallel": False},
            {"id": f"step_{step_num + 3}", "tools": ["product_compose"], "parallel": False},
        ])
        return {"steps": steps}

    def _create_fast_path_product_plan(self, include_extractor: bool = True) -> Dict[str, Any]:
        """
        Hardcoded optimal execution plan for product intent.
        Bypasses the LLM Planner entirely to save ~1.5s latency.

        Pipeline:
          [Step 1: product_extractor (only for comparisons)]
          Step N: product_search + product_evidence (PARALLEL - both I/O bound)
          Step N+1: review_search (needs product_search output)
          Step N+2: product_normalize (merges search + evidence + ranking)
          Step N+3: product_affiliate (needs normalized products)
          Step N+4: product_ranking (needs affiliate data)
          Step N+5: product_compose (final assembly, tool_order 800)
          next_step_suggestion appended by _get_product_plan_for_complexity

        Returns:
            Execution plan dict with parallel step 2
        """
        steps = []
        step_num = 1

        if include_extractor:
            steps.append({"id": f"step_{step_num}", "tools": ["product_extractor"], "parallel": False})
            step_num += 1

        steps.extend([
            {"id": f"step_{step_num}", "tools": ["product_search", "product_evidence"], "parallel": True},
            {"id": f"step_{step_num + 1}", "tools": ["review_search"], "parallel": False},
            {"id": f"step_{step_num + 2}", "tools": ["product_normalize"], "parallel": False},
            {"id": f"step_{step_num + 3}", "tools": ["product_affiliate"], "parallel": False},
            {"id": f"step_{step_num + 4}", "tools": ["product_ranking"], "parallel": False},
            {"id": f"step_{step_num + 5}", "tools": ["product_compose"], "parallel": False},
        ])
        return {"steps": steps}

    def _create_fast_path_travel_plan(self) -> Dict[str, Any]:
        """
        Hardcoded execution plan for travel intent.
        Bypasses the LLM Planner to avoid 10s timeout.

        Pipeline:
          Step 1: travel_itinerary + travel_destination_facts (PARALLEL)
          Step 2: travel_search_hotels + travel_search_flights (PARALLEL)
          Step 3: travel_compose
          Step 4: next_step_suggestion
        """
        return {
            "steps": [
                {"id": "step_1", "tools": ["travel_itinerary", "travel_destination_facts"], "parallel": True},
                {"id": "step_2", "tools": ["travel_search_hotels", "travel_search_flights"], "parallel": True},
                {"id": "step_3", "tools": ["travel_compose"], "parallel": False},
                {"id": "step_4", "tools": ["next_step_suggestion"], "parallel": False},
            ]
        }

    def _create_manual_plan_for_intro(self) -> Dict[str, Any]:
        """
        Create a manual plan for intro/greeting intent.
        No LLM needed - just run intro_compose tool.

        Returns:
            Execution plan dict
        """
        return {
            "steps": [
                {
                    "id": "step_1",
                    "tools": ["intro_compose"],
                    "parallel": False
                }
            ]
        }
