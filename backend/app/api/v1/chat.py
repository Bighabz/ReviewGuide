"""
Chat Endpoints
SSE streaming chat endpoint with LangGraph integration
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import AsyncGenerator, Optional
import json
import time
from app.core.centralized_logger import get_logger
import uuid
import asyncio
from datetime import datetime, date

from app.schemas.graph_state import GraphState
from app.services.langgraph.workflow import graph, AGENT_NAME_TO_INSTANCE
from app.core.redis_client import get_redis
from app.core.database import get_db
from app.core.config import settings
from app.core.dependencies import get_current_user, check_rate_limit
from app.repositories.conversation_repository import ConversationRepository
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from app.core.colored_logging import get_colored_logger
from app.services.halt_state_manager import HaltStateManager
from app.services.chat_history_manager import chat_history_manager


async def _load_session_context(session_id: str) -> tuple[dict | None, list]:
    """Load halt state and conversation history concurrently."""
    halt_state_data, conversation_history = await asyncio.gather(
        HaltStateManager.get_halt_state(session_id),
        chat_history_manager.get_history(session_id),
    )
    return halt_state_data, conversation_history


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime and date objects"""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def _sse_event(event_type: str, data: dict, encoder_cls=DateTimeEncoder) -> str:
    """
    Format a Server-Sent Event with a named event type.

    Produces the wire format:
        event: <event_type>\\n
        data: <json>\\n
        \\n

    Args:
        event_type: SSE event name (status, content, artifact, done, error)
        data: Dict to JSON-encode as the event data payload
        encoder_cls: Optional custom JSON encoder class

    Returns:
        Fully-formed SSE string ready to yield to the client
    """
    # Sanitize to prevent header injection via newlines
    safe_type = event_type.replace('\r', '').replace('\n', '')
    json_payload = json.dumps(data, cls=encoder_cls)
    return f"event: {safe_type}\ndata: {json_payload}\n\n"


def _preference_summary(prefs: Optional[dict]) -> list:
    """B-phase 3: derive a tiny list of interest keywords (top categories /
    brands / use-cases) from this user's accumulated preferences, so the
    frontend can bias the chat empty-state starter toward what they research.

    Privacy: returned only in the requesting user's OWN chat 'done' event —
    never via an enumerable by-id endpoint. Counts are dropped (keys only).
    """
    if not prefs or not isinstance(prefs, dict):
        return []
    out: list = []
    for key in ("categories", "brands", "use_cases"):
        bucket = prefs.get(key)
        if isinstance(bucket, dict) and bucket:
            ranked = sorted(bucket.items(), key=lambda kv: kv[1] if isinstance(kv[1], (int, float)) else 0, reverse=True)
            out.extend(str(k) for k, _ in ranked[:3] if k)
    # De-dupe, preserve order, cap.
    seen: set = set()
    summary = []
    for token in out:
        low = token.lower()
        if low not in seen:
            seen.add(low)
            summary.append(token)
    return summary[:6]


logger = get_logger(__name__)
colored_logger = get_colored_logger(__name__)

router = APIRouter()

# Retains references to fire-and-forget background tasks so they are not
# garbage-collected before they complete.
_background_tasks: set = set()

# Initialize Langfuse with CallbackHandler but disable unwanted OpenTelemetry instrumentation
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

# Initialize Langfuse client at module scope (stateless — safe to share across requests).
# The CallbackHandler is created per-request inside generate_chat_stream to prevent trace
# context bleeding between concurrent SSE streams (fixed 2026-04-21, previously module-level).
langfuse_client = None

if settings.ENABLE_TRACING and settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
    # Configure Langfuse client to block OpenTelemetry HTTP exporter instrumentation
    # This prevents "opentelemetry.exporter.otlp.proto.http" errors
    langfuse_client = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
        blocked_instrumentation_scopes=[
            "opentelemetry.exporter.otlp.proto.http._internal",
            "opentelemetry.instrumentation.httpx",
            "opentelemetry.instrumentation.requests"
        ]
    )


def _new_langfuse_handler():
    """Create a fresh CallbackHandler per request.
    Returns None if Langfuse is disabled or not configured."""
    if langfuse_client is None:
        return None
    # CallbackHandler - data truncated automatically by Langfuse.
    return CallbackHandler()

class ChatRequest(BaseModel):
    """Chat request model"""
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None
    user_id: Optional[int] = None  # For anonymous users to reuse existing user
    country_code: Optional[str] = None  # User's country code for regional affiliate links
    action: Optional[str] = None  # Optional action for button clicks (e.g., "consent_confirm")


def is_consent_confirmation(request) -> bool:
    """Detect consent confirmations vs new queries.

    Used for two-layer consent flow when user needs to approve
    extended search (Tier 3-4) that may incur additional API costs.

    Args:
        request: ChatRequest with message and optional action

    Returns:
        True if this is a consent confirmation
    """
    # Structured payload from button click
    if getattr(request, "action", None) == "consent_confirm":
        return True

    # Text-based confirmation
    message = getattr(request, "message", None)
    if message:
        consent_patterns = {"yes", "search deeper", "continue", "ok", "proceed", "go ahead"}
        normalized = message.strip().lower()
        return normalized in consent_patterns or normalized.startswith("yes")

    return False



def _build_qos_log(
    request_id: str,
    session_id: str,
    result_state: dict,
    duration_ms: int,
) -> dict:
    """Build the RFC §4.2 QoS structured log payload."""
    return {
        "event": "request_completed",
        "request_id": request_id,
        "session_id": session_id,
        "intent": result_state.get("intent", "unknown"),
        "total_duration_ms": duration_ms,
        "completeness": result_state.get("completeness", "full"),
        "tool_durations": result_state.get("tool_durations", {}),
        "provider_errors": result_state.get("provider_errors", []),
    }


async def _write_request_metric(metric_data: dict) -> None:
    """Fire-and-forget: persist QoS metric row to request_metrics table."""
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.request_metric import RequestMetric
        async with AsyncSessionLocal() as db:
            metric = RequestMetric(**metric_data)
            db.add(metric)
            await db.commit()
    except Exception as e:
        logger.warning(f"[qos] Failed to write request metric: {e}")


async def generate_chat_stream(
    message: str,
    session_id: str,
    user_id: int,
    country_code: Optional[str] = None,
    user_preferences: Optional[dict] = None,
    request_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Generate SSE stream for chat responses with Langfuse tracking
    Uses CallbackHandler for comprehensive LLM observability

    Args:
        message: User's message
        session_id: Session UUID (string)
        user_id: User ID (integer) to return to frontend for persistence
        country_code: User's country code for regional affiliate links
        request_id: RFC §4.1 correlation ID propagated from X-Interaction-ID header
    """
    # RFC §4.2 — capture stream start time for total_duration_ms calculation
    stream_start_time = time.time()

    # Generate conversation_id for this query
    conversation_id = str(uuid.uuid4())

    # RFC §4.1 — fall back to a fresh UUID if the caller didn't supply one
    if not request_id:
        request_id = str(uuid.uuid4())

    # Save original user message BEFORE it gets overwritten by status updates
    original_user_message = message

    # Per-request Langfuse handler — isolated trace context per SSE stream.
    # Do NOT hoist to module scope; doing so causes trace context to bleed
    # between concurrent users (documented in 2026-03-15 audit).
    langfuse_handler = _new_langfuse_handler()

    try:
        # RFC §4.1 — log request start with correlation ID
        logger.info(
            "[chat] stream_start",
            extra={"request_id": request_id, "session_id": session_id, "user_id": user_id},
        )

        # Send initial placeholder message IMMEDIATELY
        yield _sse_event("status", {
            "text": "Thinking...",
            "agent": "init",
            "step": 0,
            "placeholder": True,
        })

        # Load halt state and conversation history concurrently (no data dependency).
        # get_halt_state returns None when no halt exists, so it replaces the older
        # check_halt_exists + load_halt_state two-step pattern.
        halt_state_data, conversation_history = await _load_session_context(session_id)

        halt_exists = halt_state_data is not None
        extended_search_confirmed = False  # Flag for consent resume flow

        if halt_exists:
            # Check for consent_required halt (Tier 3-4 extended search)
            halt_reason = halt_state_data.get("halt_reason") if halt_state_data else None
            if halt_reason == "consent_required":
                # Create a mock request object for consent detection
                class MockRequest:
                    def __init__(self, msg):
                        self.message = msg
                        self.action = None

                if is_consent_confirmation(MockRequest(message)):
                    # User confirmed extended search
                    logger.info(f"[ChatEndpoint] User confirmed extended search for session {session_id}")
                    extended_search_confirmed = True
                    # Keep halt_state_data to restore partial results
                else:
                    # User sent a different message - clear halt and treat as new query
                    logger.info(f"[ChatEndpoint] User declined extended search, treating as new query")
                    await HaltStateManager.delete_halt_state(session_id)
                    halt_state_data = None
                    halt_exists = False

            # Check if this is actually a halted state (has followup questions)
            # vs just stored slots from previous request
            elif halt_state_data:
                followups = halt_state_data.get("followups", [])
                if not followups:
                    # No followups = not a real halt, just the search context persisted
                    # after a completed search. Treat as a new query, BUT keep the
                    # context fields (Outcome 2): they're what lets a refinement chip
                    # ("Show cheaper options") adjust the previous search instead of
                    # starting cold, and what the intent agent uses to classify short
                    # follow-ups. Everything else (plan, questions) is dropped.
                    logger.info(f"Halt state exists but no followups - treating as new query (keeping search context)")
                    await HaltStateManager.delete_halt_state(session_id)
                    halt_state_data = {
                        "last_search_context": halt_state_data.get("last_search_context", {}),
                        "search_history": halt_state_data.get("search_history", []),
                    }
                    halt_exists = False

        logger.info(f"[ChatEndpoint] Loading conversation history for session {session_id}...")
        if conversation_history:
            logger.info(f"[ChatEndpoint] ✅ Loaded {len(conversation_history)} messages from conversation history for session {session_id}")
            # Log first and last message for debugging
            if len(conversation_history) > 0:
                first_msg = conversation_history[0]
                last_msg = conversation_history[-1]
                logger.info(f"[ChatEndpoint] First message: role={first_msg.get('role')}, content_preview={first_msg.get('content', '')[:50]}...")
                logger.info(f"[ChatEndpoint] Last message: role={last_msg.get('role')}, content_preview={last_msg.get('content', '')[:50]}...")
        else:
            logger.info(f"[ChatEndpoint] ❌ No conversation history found for session {session_id} (new conversation or empty history)")

        # Initialize graph state (TypedDict)
        from datetime import datetime, timezone

        # Initialize slots with country_code from request (if provided)
        initial_slots = halt_state_data.get("slots", {}) if halt_state_data else {}
        if not initial_slots.get("country_code"):
            # Set country_code from request or default to settings
            initial_slots["country_code"] = country_code or settings.AMAZON_DEFAULT_COUNTRY

        # Set next_agent for consent resume flow
        resume_next_agent = None
        if extended_search_confirmed and halt_state_data:
            # Resume at tiered_executor with consent confirmed
            resume_next_agent = "tiered_executor"
            logger.info(f"[ChatEndpoint] Setting resume flow to tiered_executor with consent confirmed")

        initial_state: GraphState = {
            "user_message": message,
            "session_id": session_id,
            "conversation_history": conversation_history,
            "status": "running",
            "current_agent": None,
            "next_agent": resume_next_agent,  # Set for consent resume, None otherwise
            "halt": False,  # Required field - reset to False so workflow can continue
            "plan": None,
            "slots": initial_slots,  # Initialize with country_code
            "followups": halt_state_data.get("followups", []) if halt_state_data else [],
            "policy_status": "allow",
            "extended_search_confirmed": extended_search_confirmed,  # Flag for tiered executor
            "sanitized_text": None,
            "redaction_map": {},
            "intent": halt_state_data.get("intent") if halt_state_data else None,
            "intro_text": None,
            # Restore partial_items if resuming from consent halt
            "search_results": halt_state_data.get("partial_items", []) if extended_search_confirmed else [],
            "search_query": None,
            "product_names": [],
            "review_aspects": [],
            "evidence_citations": [],
            "confidence_score": 0.0,
            "review_data": {},
            "general_product_info": "",
            "entity": None,
            "entity_key": None,
            "normalized_products": [],
            "affiliate_products": {},
            "link_health": {},
            "comparison_table": None,
            "travel_info": halt_state_data.get("travel_info", {}) if halt_state_data else {},
            "hotels": halt_state_data.get("hotels", []) if halt_state_data else [],
            "flights": halt_state_data.get("flights", []) if halt_state_data else [],
            "cars": halt_state_data.get("cars", []) if halt_state_data else [],
            "itinerary": halt_state_data.get("itinerary", []) if halt_state_data else [],
            "travel_results": halt_state_data.get("travel_results") if halt_state_data else None,
            "stream_chunk_data": None,
            # tool_timing ported from v3 (0bd88eb) 2026-04-21 — must be present
            # or LangGraph TypedDict channels crash. See schemas/graph_state.py.
            "tool_timing": {},
            "ranked_items": [],
            "assistant_text": None,
            # B.3 — Initialize follow_up_question so LangGraph's TypedDict
            # channel validator doesn't crash when product_compose tries
            # to write it. See CONCERNS.md "GraphState ↔ initial_state
            # Coupling" for the recurring pattern.
            "follow_up_question": None,
            # Quiz-path transitional reasoning — init so the TypedDict channel
            # accepts product_compose's write (same pattern as follow_up_question).
            "transitional_reasoning": None,
            "ui_blocks": [],
            "citations": [],
            "next_suggestions": [],  # Follow-up questions from next_step_suggestion tool
            "agent_statuses": [],
            "tool_citations": [],  # Initialize tool citations list
            "last_search_context": halt_state_data.get("last_search_context", {}) if halt_state_data else {},
            "search_history": halt_state_data.get("search_history", []) if halt_state_data else [],
            "errors": [],
            "stage_telemetry": [],  # RFC §1.1 — populated by each agent node
            "metadata": {
                # NOTE: Do NOT add langfuse_handler or callbacks here!
                # CallbackHandler is passed via LangGraph config, not state
                # Adding it to state causes massive JSON serialization that crashes browser
                "user_id": user_id,
                "user_preferences": user_preferences or {},
            },
            "created_at": datetime.now(timezone.utc),
        }

        # Log restored state (state was already restored during initialization above)
        if halt_state_data:
            logger.info("🔄 Resumed from HALT state")
            # Log slots from halt_state_data (not from initial_state, as they're removed from GraphState)
            slots = halt_state_data.get("slots", {})
            followups = halt_state_data.get("followups", [])
            logger.info(f"✅ Restored state: intent={initial_state['intent']}, slots={list(slots.keys())}, followups_remaining={len(followups)}")

        # Execute the workflow and stream intermediate states
        # Cost tracking is handled by langfuse_handler passed to graph.astream_events()
        # Citation logging handled per-instance by PlanExecutor (no global callbacks needed)
        citation_buffer = []
        workflow_running = True

        # Event queue for streaming
        from app.services.plan_executor import clear_tool_citation_callbacks

        # Background task that polls event stream
        event_queue = asyncio.Queue()
        # RFC §1.1 — track whether the 60-second hard limit fired
        sse_total_timeout_hit = False

        async def consume_events():
            """Consume LangGraph events and put them in queue"""
            nonlocal workflow_running
            try:
                async for event in graph.astream_events(initial_state, version="v2", config={"callbacks": [langfuse_handler]}):
                    await event_queue.put(event)
            finally:
                workflow_running = False
                await event_queue.put(None)  # Sentinel value

        # Start event consumer in background
        event_task = asyncio.create_task(consume_events())

        # Use astream_events to get intermediate node executions WITH start/end events
        result_state = None
        last_node_name = None
        data_already_streamed = False  # Track if we already streamed any data (from stream_chunk_data)

        # RFC §1.1 — enforce 60-second hard limit on the entire SSE connection.
        # asyncio.wait_for cannot wrap an async generator, so the deadline is
        # enforced inline inside _drain_event_loop on every iteration.
        from app.services.stage_telemetry import MAX_TOTAL_REQUEST_S

        async def _drain_event_loop():
            """Drain the event queue until the workflow sentinel arrives or the 60-second hard cap fires."""
            nonlocal result_state, last_node_name, data_already_streamed, sse_total_timeout_hit
            # RFC §1.1 — enforce hard cap by checking elapsed time on every iteration.
            # asyncio.wait_for cannot wrap an async generator directly, so the deadline
            # is enforced inline: the check fires within one CHAT_EVENT_QUEUE_TIMEOUT
            # tick of MAX_TOTAL_REQUEST_S.
            deadline = stream_start_time + MAX_TOTAL_REQUEST_S
            # Main loop: check both citation buffer and event queue
            while True:
                # RFC §1.1 — abort if the wall-clock deadline has passed
                if time.time() >= deadline:
                    sse_total_timeout_hit = True
                    logger.error(
                        f"[stage_telemetry] SSE total 60s hard limit exceeded for session {session_id}"
                        " — cancelling background event consumer"
                    )
                    event_task.cancel()
                    break

                # Drain citation buffer (log only, don't stream to frontend)
                while citation_buffer:
                    citation = citation_buffer.pop(0)
                    tool_name = citation.get("tool", "")
                    message = citation.get("message", "")
                    if message:
                        logger.info(f"Tool citation (suppressed): {tool_name} - {message}")

                # Then try to get event with short timeout
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=settings.CHAT_EVENT_QUEUE_TIMEOUT)
                    if event is None:  # Sentinel - workflow finished
                        break
                except asyncio.TimeoutError:
                    # No event yet, loop back to check citations
                    continue

                event_type = event.get("event")
                event_name = event.get("name", "")

                # Detect when agents START (on_chain_start) - log only
                if event_type == "on_chain_start":
                    agent_instance = AGENT_NAME_TO_INSTANCE.get(event_name)
                    if agent_instance and hasattr(agent_instance, 'on_chain_start_message') and agent_instance.on_chain_start_message:
                        agent_short_name = event_name.split("_")[-1] if "_" in event_name else event_name
                        logger.info(f"Agent status (suppressed): {event_name} - {agent_instance.on_chain_start_message}")
                        last_node_name = agent_short_name

                # Detect when nodes complete
                elif event_type == "on_chain_end":
                    if event_name == "LangGraph":
                        result_state = event.get("data", {}).get("output", {})
                    else:
                        output_data = event.get("data", {}).get("output", {})

                        # STREAM DATA IMMEDIATELY if agent returned stream_chunk_data
                        if isinstance(output_data, dict):
                            stream_data = output_data.get("stream_chunk_data")
                            if stream_data:
                                data_type = stream_data.get("type")
                                data_content = stream_data.get("data")

                                # Emit tool citations as status messages for progress indicator
                                if data_type == "tool_citation" and isinstance(data_content, dict):
                                    citation_message = data_content.get("message", "")
                                    if citation_message:
                                        yield _sse_event("status", {"text": citation_message})
                                        logger.info(f"Streamed status: {citation_message}")
                                elif data_type and data_content:
                                    artifact_payload = {
                                        "type": data_type,
                                        "blocks": data_content,
                                        "clear": True,
                                    }
                                    if stream_data.get("create_new_message"):
                                        artifact_payload["create_new_message"] = True
                                    yield _sse_event("artifact", artifact_payload)

                                    data_already_streamed = True
                                    logger.info(f"Streamed {data_type} from {event_name}")

                        if isinstance(output_data, dict) and output_data.get("next_agent") == "travel_planner":
                            logger.info(f"Travel planner status (suppressed): from {event_name}")
                            last_node_name = "planner"

        try:
            # RFC §1.1 — drain; the 60-second hard cap fires inside _drain_event_loop
            # on every iteration, so this loop is always bounded by MAX_TOTAL_REQUEST_S
            # plus at most one CHAT_EVENT_QUEUE_TIMEOUT tick.
            async for sse_chunk in _drain_event_loop():
                yield sse_chunk
        except Exception:
            pass  # handled below

        # RFC §1.1 — await background task to surface any exception.
        # If the hard cap fired, event_task was already cancelled inside _drain_event_loop;
        # CancelledError is expected and swallowed here.
        try:
            await event_task
        except asyncio.CancelledError:
            pass  # expected when hard cap cancels event_task inside _drain_event_loop
        except Exception as exc:
            logger.warning(f"[stage_telemetry] Background event consumer raised an unexpected error: {exc}")

        # RFC §1.1 — if the 60-second hard cap fired, terminate the stream immediately
        if sse_total_timeout_hit:
            clear_tool_citation_callbacks()
            yield _sse_event("error", {
                "code": "request_timeout",
                "message": "Took longer than expected on this one. Want to try narrowing it down?",
                "recoverable": True,
            })
            return

        # Drain any remaining citations (log only)
        while citation_buffer:
            citation = citation_buffer.pop(0)
            logger.info(f"Remaining citation (suppressed): {citation.get('tool')} - {citation.get('message')}")

        # Fallback: if we didn't get final state from events, use astream to get it
        if not result_state:
            logger.warning("⚠️ No final state from astream_events, falling back to astream")
            async for state_update in graph.astream(initial_state, config={"callbacks": [langfuse_handler]}):
                result_state = state_update

        # Clear callbacks after workflow completes
        clear_tool_citation_callbacks()

        # DEBUG: Log result_state keys
        logger.info(f"🔍 DEBUG: result_state keys: {list(result_state.keys())}")

        # Prepare SINGLE consolidated log with ALL metrics
        assistant_text = result_state.get('assistant_text') or ''
        detected_intent = result_state.get("intent", "unknown")

        # Voice compliance gate (PR #voice-hotfix + A.1). Universal SSE-exit
        # point — runs regardless of which composer produced assistant_text,
        # so we don't have to re-wire every composer individually (that's
        # how dead code regrew last time). Sanitization is mechanical regex
        # replacement; the underlying prompt regression surfaces in the
        # warning log so it can be triaged in Langfuse.
        #
        # ``sanitize_voice_payload`` (A.1) handles both string and dict
        # shapes. The clarifier agent emits ``assistant_text`` as a dict
        # ``{intro, followups, questions}`` on halt, which the prior
        # string-only ``sanitize_voice`` would have crashed on. The
        # downstream halt path at line ~654 reads this same field and
        # passes it through to the SSE ``done`` event — sanitizing here
        # covers that path too.
        if assistant_text:
            from app.services.prompts import sanitize_voice_payload
            cleaned_payload, voice_violations = sanitize_voice_payload(assistant_text)
            if voice_violations:
                # Size diagnostics only apply when both sides are strings;
                # for dict payloads, fall back to a structural marker.
                if isinstance(assistant_text, str) and isinstance(cleaned_payload, str):
                    size_note = (
                        f"original={len(assistant_text)} chars "
                        f"-> cleaned={len(cleaned_payload)} chars"
                    )
                else:
                    size_note = f"payload_type={type(assistant_text).__name__}"
                logger.warning(
                    f"[voice_compliance] Stripped {len(voice_violations)} violation(s) "
                    f"from assistant_text (session={session_id}, intent={detected_intent}, "
                    f"{size_note}). Violations: {voice_violations}"
                )
                # Mutate result_state so the re-read at line ~612 (response_text)
                # AND the halt-state read at line ~654 (followups_to_send)
                # both pick up the cleaned payload.
                assistant_text = cleaned_payload
                result_state['assistant_text'] = cleaned_payload

        # B.3 — also sanitize the structured follow_up_question. The body
        # gate above only covers assistant_text; the follow-up emits via
        # its own SSE event after the content stream and would otherwise
        # bypass voice enforcement.
        follow_up_question_text = result_state.get("follow_up_question") or ""
        if follow_up_question_text:
            from app.services.prompts import sanitize_voice as _sanitize_voice
            cleaned_fu, fu_violations = _sanitize_voice(follow_up_question_text)
            if fu_violations:
                logger.warning(
                    f"[voice_compliance] Stripped {len(fu_violations)} violation(s) "
                    f"from follow_up_question (session={session_id}, intent={detected_intent}). "
                    f"Violations: {fu_violations}"
                )
                follow_up_question_text = cleaned_fu
                result_state['follow_up_question'] = cleaned_fu

        # Quiz-path transitional reasoning — sanitize the same way (it's AI voice
        # and emits via its own SSE event, bypassing the assistant_text gate).
        transitional_reasoning_text = result_state.get("transitional_reasoning") or ""
        if transitional_reasoning_text:
            from app.services.prompts import sanitize_voice as _sanitize_voice
            cleaned_tr, tr_violations = _sanitize_voice(transitional_reasoning_text)
            if tr_violations:
                logger.warning(
                    f"[voice_compliance] Stripped {len(tr_violations)} violation(s) "
                    f"from transitional_reasoning (session={session_id}, intent={detected_intent})."
                )
                transitional_reasoning_text = cleaned_tr
                result_state['transitional_reasoning'] = cleaned_tr

        # Get CallbackHandler trace data
        langfuse_trace_url = None
        if langfuse_handler:
            try:
                # Get the trace URL from CallbackHandler
                trace = langfuse_handler.trace
                if trace:
                    langfuse_trace_url = f"https://cloud.langfuse.com/trace/{trace.id}"
                    # RFC §4.1 — tag the Langfuse trace with the correlation request_id
                    # so it can be looked up via GET /v1/admin/trace/:interaction_id
                    if langfuse_client:
                        try:
                            langfuse_client.trace(
                                id=trace.id,
                                tags=["request_id:" + request_id],
                            )
                        except Exception as tag_err:
                            logger.debug(f"Could not tag Langfuse trace: {tag_err}")
            except Exception as e:
                logger.debug(f"Could not get langfuse trace URL: {e}")

        # SINGLE CONSOLIDATED LOG - All data in one place
        # Cost/token metrics are tracked by Langfuse CallbackHandler and visible in trace URL
        consolidated_log = {
            "event": "query_completed",
            "request_id": request_id,  # RFC §4.1 correlation ID
            "session_id": session_id,
            "conversation_id": conversation_id,
            "query": message[:200],
            "intent": detected_intent,
            "status": result_state.get("status", "unknown"),
            "final_agent": result_state.get("current_agent"),
            "response_length": len(assistant_text),
            # Langfuse tracking (token/cost data available in trace)
            "langfuse_trace_url": langfuse_trace_url,
        }

        # Log consolidated response metrics in YELLOW
        colored_logger.api_output(consolidated_log, endpoint="/v1/chat/stream")

        # Clear halt state if workflow completed successfully (not halted)
        # NOTE: We don't save halt state here because agents handle that themselves
        # (intent_agent, clarifier_agent, travel_clarifier_agent save to HaltStateManager)
        if result_state.get("status") != "halted" and halt_exists:
            # Workflow completed - clear halt state
            await HaltStateManager.delete_halt_state(session_id)

        # Outcome 2 (refinement chips): after a completed product search, persist the
        # search context to Redis as a context-only halt state (no followups). The
        # next turn's initial_state restores last_search_context from it (line ~384),
        # which is what lets "Show cheaper options" / "Only Sony" re-run the search
        # with adjusted slots instead of starting from scratch — and what lets the
        # clarifier skip re-asking questions the user already answered.
        # The workflow treats a followups-less halt state as "not halted" (it clears
        # it and proceeds as a new query), so this never traps the session in a halt.
        if (
            result_state.get("status") != "halted"
            and result_state.get("last_search_context")
        ):
            try:
                await HaltStateManager.update_halt_state(session_id, {
                    "intent": result_state.get("intent"),
                    "slots": result_state.get("slots", {}),
                    "followups": [],  # context-only: NOT a real halt
                    "last_search_context": result_state.get("last_search_context", {}),
                    "search_history": result_state.get("search_history", []),
                })
                logger.info("💾 Persisted search context for follow-up turns (context-only halt state)")
            except Exception as ctx_err:
                logger.warning(f"Failed to persist search context (non-fatal): {ctx_err}")

        # Get the response text and ui_blocks
        response_text = result_state.get("assistant_text", "")
        ui_blocks = result_state.get("ui_blocks", [])

        # Check if workflow is halted - if so, don't stream any text (questions will be in blue box)
        is_halted = result_state.get("status") == "halted" and result_state.get("halt")

        # For product intent, send ui_blocks in the SAME chunk as clear to avoid race condition
        ui_blocks_sent_early = False
        if ui_blocks and result_state.get("intent") == "product" and not data_already_streamed:
            logger.info(f"🔍 DEBUG: Sending UI blocks WITH clear for product intent ({len(ui_blocks)} blocks)")
            # Send ui_blocks AND clear in the same artifact event
            yield _sse_event("artifact", {
                "type": "ui_blocks",
                "blocks": ui_blocks,
                "clear": True,
            })
            ui_blocks_sent_early = True
            logger.info(f"📤 Sent {len(ui_blocks)} UI blocks with clear signal")
        elif not data_already_streamed:
            # Clear placeholder ONLY if we haven't already streamed data
            # (If data was streamed, we want to keep it and append followups below it)
            yield _sse_event("artifact", {"clear": True})
        else:
            logger.info("🔍 Skipping clear chunk - data already streamed, will append followups")

        # Stream response text if available and NOT halted and NOT already streamed data
        should_stream_text = not is_halted and response_text and not data_already_streamed

        if should_stream_text:
            logger.info(f"🔍 DEBUG: Streaming response text ({len(response_text)} chars)")
            # Chunked emission — preserves progressive UX feel without per-char tax
            STREAM_CHUNK_SIZE = 24  # ~24 chars per chunk ≈ a few words at a time
            for i in range(0, len(response_text), STREAM_CHUNK_SIZE):
                yield _sse_event("content", {"token": response_text[i:i + STREAM_CHUNK_SIZE]})
                await asyncio.sleep(0.02)  # 20ms typing effect between chunks
        else:
            logger.info(f"🔍 DEBUG: Skipping text streaming (halted={is_halted}, has_text={bool(response_text)}, data_streamed={data_already_streamed})")

        # B.3 — emit the curious follow-up question as its own SSE event,
        # after the body finishes streaming and before the terminal `done`
        # event. The frontend renders this distinctly (italic, own line)
        # below the blog body per spec §11 / §13 #3. Skipped on halt — the
        # clarifier owns the followups field in that case.
        if follow_up_question_text and not is_halted:
            yield _sse_event("follow_up_question", {"text": follow_up_question_text})
            logger.info(
                f"🔍 Emitted follow_up_question SSE event ({len(follow_up_question_text)} chars)"
            )

        # Quiz-path transitional reasoning — its own SSE event; frontend renders it
        # as a TransitionalBubble before the AI bubble (field on the message, so
        # arrival order vs the body stream doesn't matter).
        if transitional_reasoning_text and not is_halted:
            yield _sse_event("transitional_reasoning", {"text": transitional_reasoning_text})
            logger.info(
                f"🔍 Emitted transitional_reasoning SSE event ({len(transitional_reasoning_text)} chars)"
            )

        # Only include followup questions if the workflow is HALTED (not completed)
        # Just pass through whatever the clarifier agent returns - no processing here
        followups_to_send = None
        if result_state.get("status") == "halted" and result_state.get("halt"):
            followups_to_send = result_state.get("assistant_text")
            logger.info(f"🔍 Workflow HALTED - passing through followups from clarifier agent")
        else:
            logger.info(f"🔍 Workflow COMPLETED - no followup questions")

        # DON'T send ui_blocks in final chunk if we already sent them early (avoids duplicates)
        # Get next_suggestions for follow-up questions at end of response
        next_suggestions = result_state.get("next_suggestions", [])
        if next_suggestions:
            logger.info(f"🔍 Found {len(next_suggestions)} next step suggestions to send")

        # RFC §2.5 — Build ResponseMetadata for content trust / explainability UI.
        # Derive metadata from what is already available in result_state without
        # requiring new GraphState fields.  A richer implementation can replace
        # this stub once plan_executor exposes per-provider timing data.
        _errors: list = result_state.get("errors", []) or []
        _provider_errors: list = result_state.get("provider_errors", []) or []
        _tool_durations: dict = result_state.get("tool_durations", {}) or {}

        # Determine which providers ran based on affiliate_products and travel data present
        _affiliate_products: dict = result_state.get("affiliate_products", {}) or {}
        _provider_coverage = []
        # Only include amazon/ebay coverage when the intent was product — these providers
        # are never queried for travel or general intents, so including them unconditionally
        # would always report them as "unavailable" and wrongly degrade the confidence score.
        _intent = result_state.get("intent", "")
        if _intent == "product":
            for provider_key in ["amazon", "ebay"]:
                items = _affiliate_products.get(provider_key, [])
                _provider_coverage.append({
                    "provider": provider_key,
                    "status": "ok" if items else "unavailable",
                    "result_count": len(items) if items else 0,
                })
        if result_state.get("hotels"):
            _provider_coverage.append({"provider": "booking", "status": "ok", "result_count": len(result_state["hotels"])})
        if result_state.get("flights"):
            _provider_coverage.append({"provider": "amadeus", "status": "ok", "result_count": len(result_state["flights"])})
        if result_state.get("search_results"):
            _provider_coverage.append({"provider": "perplexity", "status": "ok", "result_count": len(result_state["search_results"])})

        # Mark any provider errors as timed_out / unavailable.
        # The inner for/else is intentional: the `else` branch runs only when the inner
        # loop exhausted all items without hitting `break`, meaning no existing coverage
        # entry matched this error provider — so we append a new timed_out entry.
        for err in _provider_errors:
            err_provider = err if isinstance(err, str) else err.get("provider", "")
            for cov in _provider_coverage:
                if cov["provider"] == err_provider:
                    cov["status"] = "timed_out"
                    break
            else:
                # No existing coverage entry matched — add a new timed_out entry.
                if err_provider:
                    _provider_coverage.append({"provider": err_provider, "status": "timed_out"})

        _missing_sources = [
            p["provider"] for p in _provider_coverage if p["status"] in ("timed_out", "unavailable")
            and p.get("result_count", 0) == 0
        ]
        _degraded = bool(_provider_errors) or bool(_errors and result_state.get("status") != "completed")

        # confidence_score: 1.0 if all ok, 0.5 if some providers failed, 0.3 if critical (affiliate) failed
        _affiliate_failed = any(
            p["status"] in ("timed_out", "unavailable") for p in _provider_coverage
            if p["provider"] in ("amazon", "ebay")
        )
        if _affiliate_failed or (_degraded and _provider_errors):
            _confidence_score = 0.3
        elif _missing_sources:
            _confidence_score = 0.5
        else:
            _confidence_score = result_state.get("confidence_score", 1.0) or 1.0

        _response_metadata = {
            "source_count": len(result_state.get("citations", []) or []),
            "provider_coverage": _provider_coverage,
            "confidence_score": float(_confidence_score),
            "omitted_sections": [],  # Populated by future tool-level tracking
            "degraded": _degraded,
            "missing_sources": _missing_sources,
            "web_context_cache_age_s": None,
        }

        final_done_payload = {
            "session_id": session_id,
            "request_id": request_id,  # RFC §4.1 correlation ID for frontend trace lookup
            "status": result_state.get("status", "completed"),
            "intent": result_state.get("intent"),
            "ui_blocks": [] if ui_blocks_sent_early else ui_blocks,
            "citations": result_state.get("citations", []),
            "followups": followups_to_send,  # Pass through structured data from clarifier agent
            "next_suggestions": next_suggestions,  # Follow-up questions from next_step_suggestion tool
            "user_id": user_id,
            "completeness": "full",  # RFC §1.8: degraded logic deferred to a later phase
            "response_metadata": _response_metadata,  # RFC §2.5 content trust metadata
            # B-phase 3: the user's own interest keywords, to personalize the
            # chat empty-state starter on their next visit (privacy-safe — own stream).
            "preference_summary": _preference_summary(user_preferences),
            # RFC §1.1 — stage-level latency telemetry
            "stage_telemetry": result_state.get("stage_telemetry") or [],
        }

        logger.info(f"🔍 DEBUG: Final chunk - has_followups: {followups_to_send is not None}")
        logger.info(f"🔍 DEBUG: Final chunk ui_blocks: {len(final_done_payload['ui_blocks'])} blocks")
        yield _sse_event("done", final_done_payload)

        # RFC §4.2 — emit structured QoS log line after stream completes
        _qos_duration_ms = int((time.time() - stream_start_time) * 1000)
        qos_log = _build_qos_log(request_id, session_id, result_state, _qos_duration_ms)
        logger.info(f"[qos] {json.dumps(qos_log)}")

        # RFC §4.2 — persist QoS metric to database (fire-and-forget)
        _metric_task = asyncio.create_task(
            _write_request_metric({
                "request_id": request_id,
                "session_id": session_id,
                "intent": result_state.get("intent", "unknown"),
                "total_duration_ms": _qos_duration_ms,
                "completeness": result_state.get("completeness", "full"),
                "tool_durations": result_state.get("tool_durations", {}),
                "provider_errors": result_state.get("provider_errors", []),
            })
        )
        _background_tasks.add(_metric_task)
        _metric_task.add_done_callback(_background_tasks.discard)

        # Fire-and-forget: save turn after stream is already done
        user_message_text = original_user_message
        is_suggestion_click = original_user_message.startswith("You chose:")
        user_metadata = {"is_suggestion_click": True} if is_suggestion_click else None

        if is_halted and followups_to_send and isinstance(followups_to_send, dict):
            assistant_content = followups_to_send.get("intro", "")
        else:
            assistant_content = response_text

        assistant_metadata = {}
        if followups_to_send:
            assistant_metadata["followups"] = followups_to_send
        if ui_blocks:
            assistant_metadata["ui_blocks"] = ui_blocks
        if next_suggestions:
            assistant_metadata["next_suggestions"] = next_suggestions
        if result_state.get("citations"):
            assistant_metadata["citations"] = result_state.get("citations")
        if result_state.get("intent"):
            assistant_metadata["intent"] = result_state.get("intent")
        if result_state.get("status"):
            assistant_metadata["status"] = result_state.get("status")
        # Persist the follow-up so reloaded history renders the italic
        # line below the body, matching the live turn. Stored under the
        # camelCase key the frontend Message component reads
        # (Message.tsx:223 `message.followUpQuestion`) — the rehydration
        # spread in ChatContainer.tsx:210 does no case conversion, and
        # the live SSE path already normalizes snake→camel at
        # ChatContainer.tsx:500, so persisting camelCase keeps both
        # paths consistent. Sanitization already happened at line ~593;
        # the stored value is voice-clean.
        if follow_up_question_text and not is_halted:
            assistant_metadata["followUpQuestion"] = follow_up_question_text
        # Persist transitional reasoning camelCase for the history-load path
        if transitional_reasoning_text and not is_halted:
            assistant_metadata["transitionalReasoning"] = transitional_reasoning_text

        _save_task = asyncio.create_task(
            chat_history_manager.save_turn(
                session_id=session_id,
                user_content=user_message_text,
                assistant_content=assistant_content,
                user_metadata=user_metadata,
                assistant_metadata=assistant_metadata if assistant_metadata else None,
            )
        )
        _background_tasks.add(_save_task)
        _save_task.add_done_callback(_background_tasks.discard)
        logger.info(f"[ChatEndpoint] Scheduled turn persistence for session {session_id}")

        # Flush Langfuse traces immediately after request completes
        if langfuse_handler:
            try:
                langfuse_client.flush()
                logger.debug("Langfuse traces flushed")
            except Exception as flush_error:
                logger.debug(f"Langfuse flush warning: {flush_error}")

    except Exception as e:
        # Log error with centralized logger including RFC §4.1 correlation ID
        logger.error(
            f"Error in chat_stream: {str(e)}",
            exc_info=True,
            extra={
                "request_id": request_id,
                "session_id": session_id,
                "user_id": user_id,
                "message_preview": message[:100] if message else ""
            }
        )

        # Emit a named error event so the stream always ends with a terminal event.
        # Copy follows tone.md §10.5 error-state voice — curious, low-alarm.
        yield _sse_event("error", {
            "code": "internal_error",
            "message": "Hit a wall pulling info on this one. Want to try a different angle?",
            "recoverable": True,
        })


@router.get("/conversations")
async def list_conversations(
    session_id: Optional[str] = None,
    session_ids: Optional[str] = None,  # Comma-separated list of session IDs
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    List conversations with proper authorization.

    - Admin users: Can see all conversations (for moderation)
    - Authenticated users: Can see their own conversations
    - Anonymous users: Must provide session_id(s) to see only those sessions

    SECURITY: Never expose all conversations without proper authorization.
    """
    try:
        from app.models.conversation_message import ConversationMessage

        # SECURITY: Authorization check
        is_admin = current_user and current_user.get("type") == "admin"

        # Parse session_ids if provided (comma-separated)
        allowed_sessions = []
        if session_ids:
            allowed_sessions = [s.strip() for s in session_ids.split(',') if s.strip()]
        elif session_id:
            allowed_sessions = [session_id]

        # If not admin and no session_ids provided, return empty (fail-safe)
        if not is_admin and not allowed_sessions:
            logger.warning("Unauthorized attempt to list all conversations without session_ids")
            return {
                "success": True,
                "conversations": []
            }

        # Build base query
        first_msg_subq = (
            select(
                ConversationMessage.session_id,
                func.min(ConversationMessage.sequence_number).label('first_seq')
            )
            .group_by(ConversationMessage.session_id)
            .subquery()
        )

        # Get conversations with first message content
        stmt = (
            select(
                ConversationMessage.session_id,
                ConversationMessage.content,
                ConversationMessage.created_at,
                func.count(ConversationMessage.id).over(partition_by=ConversationMessage.session_id).label('message_count')
            )
            .join(
                first_msg_subq,
                (ConversationMessage.session_id == first_msg_subq.c.session_id) &
                (ConversationMessage.sequence_number == first_msg_subq.c.first_seq)
            )
            .where(ConversationMessage.role == 'user')
        )

        # SECURITY: Filter by allowed session_ids if not admin
        if not is_admin and allowed_sessions:
            stmt = stmt.where(ConversationMessage.session_id.in_(allowed_sessions))

        stmt = stmt.order_by(desc(ConversationMessage.created_at)).limit(50)

        result = await db.execute(stmt)
        rows = result.all()

        conversations = []
        seen_sessions = set()

        for row in rows:
            if row.session_id not in seen_sessions:
                seen_sessions.add(row.session_id)
                conversations.append({
                    "session_id": row.session_id,
                    "preview": row.content[:100] + "..." if len(row.content) > 100 else row.content,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "message_count": row.message_count
                })

        logger.info(f"Listed {len(conversations)} conversations (admin={is_admin}, session_filter={session_id is not None})")

        return {
            "success": True,
            "conversations": conversations
        }

    except Exception as e:
        logger.error(f"Failed to list conversations: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list conversations: {str(e)}"
        )


@router.post("/conversations")
async def create_conversation():
    """
    Create a new conversation session.

    Returns a new session_id that can be used for chatting.
    """
    new_session_id = str(uuid.uuid4())
    logger.info(f"Created new conversation: {new_session_id}")

    return {
        "success": True,
        "session_id": new_session_id
    }


@router.delete("/conversations/{session_id}")
async def delete_conversation(
    session_id: str,
    current_user: Optional[dict] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """
    Delete a conversation and all its messages.

    Security (fixed 2026-04-21): requires the caller to be authenticated AND
    own the target session. Prior version accepted any request with a known
    session_id — guessable UUID enumeration could delete arbitrary conversations.
    """
    # Verify caller is authenticated and owns the session.
    if current_user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to delete a conversation.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Resolve session → user_id, compare against current_user.id
        from app.models.session import Session as ChatSession
        from sqlalchemy import select
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        session_row = result.scalar_one_or_none()
        if session_row is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")

        # current_user["username"] is the subject; resolve it to user_id.
        # Cheap check: the username claim should match the session's user email/username.
        # If your auth maps differently, this is the integration point.
        user_id_claim = current_user.get("user_id")
        if user_id_claim is not None and session_row.user_id != user_id_claim:
            raise HTTPException(status_code=403, detail="You do not own this conversation.")

        conversation_repo = ConversationRepository(db=db, redis=redis)
        success = await conversation_repo.delete_history(session_id)

        if success:
            logger.info(f"Deleted conversation: {session_id} (by user {user_id_claim})")
            return {"success": True, "message": "Conversation deleted"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete conversation")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation {session_id}: {e}", exc_info=True)
        # Do not leak exception internals in the 500 response
        raise HTTPException(
            status_code=500,
            detail="Failed to delete conversation"
        )


@router.get("/history/{session_id}")
async def get_conversation_history(
    session_id: str,
    current_user: Optional[dict] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """
    Get conversation history for a session

    Args:
        session_id: Session UUID string

    Returns:
        List of messages with role, content, and optional structured_data

    Security (fixed 2026-04-21): requires the caller to be authenticated AND
    own the target session (same model as DELETE above). Anonymous reads of
    arbitrary session_ids are no longer allowed.
    """
    # Verify caller is authenticated and owns the session.
    if current_user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to read conversation history.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Ownership gate: resolve session → user_id, compare
        from app.models.session import Session as ChatSession
        from sqlalchemy import select as _select
        _res = await db.execute(_select(ChatSession).where(ChatSession.id == session_id))
        _session_row = _res.scalar_one_or_none()
        if _session_row is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        _user_id_claim = current_user.get("user_id")
        if _user_id_claim is not None and _session_row.user_id != _user_id_claim:
            raise HTTPException(status_code=403, detail="You do not own this conversation.")

        # Create conversation repository
        conversation_repo = ConversationRepository(db=db, redis=redis)

        # Get conversation history from database/Redis
        history = await conversation_repo.get_history(session_id)

        logger.debug(f"Retrieved {len(history)} messages for session {session_id}")

        return {
            "success": True,
            "session_id": session_id,
            "messages": history
        }

    except Exception as e:
        logger.error(f"Failed to get conversation history for session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve conversation history: {str(e)}"
        )


@router.post("/stream")
async def chat_stream(
    chat_request: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user),
    _rate_limit: None = Depends(check_rate_limit)
):
    """
    Streaming chat endpoint with optional authentication and rate limiting
    Returns Server-Sent Events (SSE) stream

    - **message**: User message
    - **session_id**: Optional session ID (will be created if not provided)

    Authentication: Optional (Bearer token)
    - Authenticated users: Sessions linked to user account, 100 req/hour
    - Anonymous users: Sessions tracked without user link, 10 req/hour

    Rate Limiting:
    - Guest users (no auth): 10 requests per hour (by IP)
    - Authenticated users: 100 requests per hour (by user ID)
    """
    # Generate or use provided session ID
    session_id = chat_request.session_id or str(uuid.uuid4())

    # SECURITY: Check session ownership before resolving user
    # Prevents anonymous clients from loading another user's session context
    # by guessing/supplying a known session_id.
    if chat_request.session_id:
        from sqlalchemy import cast, String as SQLString
        from app.models.session import Session as SessionModel
        _stmt = select(SessionModel).where(
            cast(SessionModel.meta['client_session_id'], SQLString) == session_id
        )
        _result = await db.execute(_stmt)
        _existing_session = _result.scalar_one_or_none()
        if (
            _existing_session is not None
            and _existing_session.user_id is not None
            and not current_user  # Only enforce for anonymous requests; JWT-auth handled by session_service
            and chat_request.user_id != _existing_session.user_id  # Client didn't claim this user_id
        ):
            logger.warning(
                f"[security] Anonymous client supplied session_id={session_id} owned by "
                f"user_id={_existing_session.user_id} but claimed user_id={chat_request.user_id}. "
                "Forcing new session context."
            )
            session_id = str(uuid.uuid4())  # Force new session — do not load other user's state

    colored_logger.api_input({
        "message": chat_request.message,
        "session_id": session_id,
        "user_id": chat_request.user_id,
        "auth": current_user['username'] if current_user else 'anonymous'
    }, endpoint="/v1/chat/stream")

    # Get or create session with country detection
    from app.services.session_service import get_or_create_session

    db_session_id, returned_user_id, country_code = await get_or_create_session(
        db, request, session_id, chat_request.user_id, current_user
    )
    if not db_session_id or not returned_user_id:
        raise HTTPException(
            status_code=500,
            detail="Failed to create or retrieve session"
        )

    logger.debug(f"Session {session_id} → DB ID: {db_session_id}, user: {returned_user_id}, country: {country_code}")

    # Load user preferences for cross-session context
    from app.services.preference_service import load_user_preferences
    user_preferences = await load_user_preferences(db, returned_user_id) if returned_user_id else {}

    # RFC §4.1 — extract or generate request_id for end-to-end trace correlation
    from uuid import uuid4
    request_id = request.headers.get("X-Interaction-ID") or str(uuid4())
    logger.info(
        "[chat] request received",
        extra={"request_id": request_id, "session_id": session_id},
    )

    # Return streaming response with user_id
    # Note: ChatHistoryManager is used internally for saving/loading messages
    return StreamingResponse(
        generate_chat_stream(
            chat_request.message,
            session_id,
            returned_user_id,
            country_code,  # Pass detected/stored country_code
            user_preferences,  # Pass loaded preferences
            request_id,  # RFC §4.1 correlation ID
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering in nginx
        }
    )
