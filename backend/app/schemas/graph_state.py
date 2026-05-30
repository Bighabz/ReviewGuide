"""
GraphState Schema - Blackboard Pattern
This is the shared state that flows through all agents in the LangGraph workflow
"""
from typing import Optional, List, Dict, Any, Literal, TypedDict, Annotated
from pydantic import BaseModel
from datetime import datetime
import operator


class GraphState(TypedDict):
    """
    Shared state for the multi-agent LangGraph workflow
    Uses the blackboard pattern where all agents read/write to this shared state

    Note: Using TypedDict (not Pydantic) for LangGraph compatibility
    Annotated fields with operator.add will accumulate values across nodes
    """
    # Input
    user_message: str
    session_id: str
    conversation_history: Annotated[List[Dict[str, str]], operator.add]

    # Control Flow
    status: str  # "running", "halted", "completed", "error"
    current_agent: Optional[str]
    next_agent: Optional[str]
    halt: bool  # Whether workflow should halt and wait for user input
    plan: Optional[Dict[str, Any]]  # MCP execution plan from planner agent
    extended_search_confirmed: bool  # Whether user confirmed extended search consent

    # Slot Filling (Multi-turn Conversation)
    slots: Dict[str, Any]  # Extracted slots for the current intent (destination, dates, budget, etc.)
    followups: List[Dict[str, Any]]  # Follow-up questions for missing required slots

    # Safety & Policy
    policy_status: str  # "allow", "block", "needs_clarification"
    sanitized_text: Optional[str]
    redaction_map: Dict[str, str]

    # Intent
    intent: Optional[str]  # "product", "service", "travel", "general", "comparison"
    intro_text: Optional[str]  # Introduction text for first-time users

    # Search Results
    search_results: List[Dict[str, Any]]
    search_query: Optional[str]
    product_names: List[str]  # Extracted product names for product intent

    # Evidence & Reviews
    review_aspects: List[Dict[str, Any]]
    evidence_citations: Annotated[List[str], operator.add]
    confidence_score: float  # 0-1 confidence in recommendations

    # Review Data (from SerpAPI review search)
    review_data: Dict[str, Any]  # product_name -> ReviewBundle dict
    general_product_info: Optional[str]  # Factoid answer from product_general_information tool

    # Product Normalization
    entity: Optional[Dict[str, Any]]
    entity_key: Optional[str]
    normalized_products: List[Dict[str, Any]]  # Merged evidence + affiliate + ranking

    # Affiliate Links
    affiliate_products: Dict[str, List[Dict[str, Any]]]  # Provider -> products mapping {"ebay": [...], "amazon": [...]}
    link_health: Dict[str, bool]

    # Product Comparison
    comparison_table: Optional[Dict[str, Any]]  # Structured comparison data for table display

    # Travel Planning
    travel_info: Optional[Dict[str, Any]]  # Enriched travel information (destination, dates, budget, etc.)
    hotels: List[Dict[str, Any]]
    flights: List[Dict[str, Any]]
    cars: List[Dict[str, Any]]  # Rental car PLP search links
    itinerary: List[Dict[str, Any]]
    travel_results: Optional[Dict[str, Any]]  # Combined travel planning results

    # Streaming Data
    stream_chunk_data: Optional[Dict[str, Any]]  # Data to be streamed immediately: {"type": "itinerary", "data": [...]}

    # Tool Timing (per-tool elapsed seconds for diagnostics)
    # Ported from v3 commit 0bd88eb (Phase 23-03) 2026-04-21.
    # Must be initialized to {} in initial_state (backend/app/api/v1/chat.py) —
    # omission causes LangGraph TypedDict channels to crash.
    tool_timing: Dict[str, float]

    # Ranking
    ranked_items: List[Dict[str, Any]]

    # Response Composition
    assistant_text: Optional[str]
    # B.3 — Curious follow-up question. Carried as a structurally separate
    # field so the frontend can render it distinctly (italic, separate line)
    # below the blog body rather than concatenated into the streamed prose.
    # Populated by composer tools that emit a {body, follow_up_question}
    # JSON shape (product_compose today). Sanitized by sanitize_voice at the
    # SSE-exit gate (chat.py) alongside assistant_text.
    follow_up_question: Optional[str]
    # Quiz-path transitional reasoning — one compressed-consensus sentence shown
    # as a TransitionalBubble before the blog, only when the latest constraint
    # changed the shortlist. Emitted by product_compose, threaded through the same
    # five layers as follow_up_question, sanitized at the SSE-exit gate (chat.py).
    transitional_reasoning: Optional[str]
    ui_blocks: List[Dict[str, Any]]
    citations: Annotated[List[str], operator.add]
    next_suggestions: List[Dict[str, Any]]  # Follow-up questions from next_step_suggestion tool

    # Agent Status Updates (for intermediate progress messages)
    agent_statuses: Annotated[List[Dict[str, str]], operator.add]  # [{agent: "itinerary", message: "writing itinerary..."}]

    # Tool Status Updates (for tool citation messages)
    tool_citations: Annotated[List[Dict[str, str]], operator.add]  # [{tool: "travel_search_hotels", message: "Searching for hotels..."}]

    # Search Context Persistence (for follow-up queries)
    last_search_context: Dict[str, Any]  # Current/latest product search context
    search_history: List[Dict[str, Any]]  # Previous search contexts (max 5)

    # Errors
    errors: Annotated[List[str], operator.add]

    # RFC §1.1 — Stage Telemetry (list of StageTelemetry.to_dict() records)
    stage_telemetry: Annotated[List[Dict[str, Any]], operator.add]

    # Metadata
    metadata: Dict[str, Any]
    created_at: datetime


class GraphOutput(BaseModel):
    """Output from the graph execution"""
    assistant_text: str
    ui_blocks: List[Dict[str, Any]] = []
    citations: List[str] = []
    session_id: str
    status: str
    followups: List[str] = []
    next_suggestions: List[Dict[str, Any]] = []  # Follow-up questions from next_step_suggestion tool
