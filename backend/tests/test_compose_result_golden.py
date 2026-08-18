"""DOCTRINE D2 golden test — every ComposeResult field reaches the wire.

Drives a fully-populated ComposeResult through the layers that used to drop
fields silently (validator → _extract_results → plan_executor_node), then
source-audits chat.py's emission of each user-facing field. A field silently
dropped anywhere turns this file red.
"""
import os
import re

import pytest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from app.schemas.compose_result import ComposeResult
from app.services.tool_validator import ToolOutputValidator

# One sentinel per declared content field. Anything added to ComposeResult
# MUST be added here too — the completeness test below enforces that.
GOLDEN = ComposeResult(
    assistant_text="GOLDEN_TEXT",
    ui_blocks=[{"type": "product_review", "data": {"marker": "GOLDEN_BLOCK"}}],
    citations=["https://golden.example/citation"],
    follow_up_question="GOLDEN_FOLLOWUP?",
    transitional_reasoning="GOLDEN_TRANSITIONAL.",
    last_search_context={"category": "GOLDEN_CONTEXT"},
    search_history=[{"query": "GOLDEN_HISTORY"}],
    success=True,
)

# Fields chat.py must emit to the browser (SSE done payload or a dedicated
# event). last_search_context/search_history are persistence-side (Redis),
# asserted in the same audit.
CHAT_EMISSION_FIELDS = [
    "ui_blocks",
    "citations",
    "follow_up_question",
    "transitional_reasoning",
    "last_search_context",
    "search_history",
]


def test_golden_fixture_covers_every_declared_content_field():
    dumped = GOLDEN.model_dump()
    for field in ComposeResult.content_field_names():
        assert dumped.get(field), (
            f"GOLDEN fixture leaves '{field}' unset — set a sentinel so the "
            "layer tests below actually exercise it"
        )


def test_validator_drops_nothing_declared_or_extra():
    """The validator layer was the original silent-drop site: model_dump() on
    a schema without the field stripped it. With ComposeResult (extra=allow),
    declared AND undeclared fields both survive."""
    payload = {**GOLDEN.model_dump(), "future_field": "GOLDEN_EXTRA"}
    out = ToolOutputValidator.validate("product_compose", payload)
    for field in ComposeResult.content_field_names():
        assert out[field] == payload[field], f"validator dropped '{field}'"
    assert out.get("future_field") == "GOLDEN_EXTRA", (
        "validator stripped an undeclared field — the silent-drop trap is back"
    )


def test_extract_results_copies_every_content_field():
    from app.services.plan_executor import PlanExecutor

    executor = PlanExecutor()
    executor.context = {"step_5.product_compose": GOLDEN.model_dump()}
    executor.state = {}
    results = executor._extract_results()
    for field in ComposeResult.content_field_names():
        assert results.get(field) == GOLDEN.model_dump()[field], (
            f"_extract_results dropped '{field}'"
        )


@pytest.mark.asyncio
async def test_node_update_carries_every_content_field():
    from app.services.langgraph import workflow as wf

    fake_results = {**GOLDEN.model_dump(), "next_suggestions": [], "tool_citations": []}
    with patch.object(wf.PlanExecutor, "execute", new=AsyncMock(return_value=fake_results)):
        update = await wf.plan_executor_node({
            "plan": {"steps": []},
            "slots": {},
            "user_message": "golden",
            "session_id": "s1",
        })
    for field in ComposeResult.content_field_names():
        assert update.get(field) == GOLDEN.model_dump()[field], (
            f"plan_executor_node dropped '{field}' at the node boundary"
        )


def test_chat_layer_emits_every_user_facing_field():
    """Source audit of chat.py (the 5th layer runs inside an SSE generator —
    audited statically, like test_voice_integration pins compose): every
    user-facing ComposeResult field must be read from result_state for
    emission or persistence."""
    import app.api.v1.chat as chat_module
    import inspect

    src = inspect.getsource(chat_module)
    for field in CHAT_EMISSION_FIELDS:
        assert re.search(rf'''result_state\.get\(\s*["']{field}["']''', src), (
            f"chat.py never reads '{field}' from result_state — the field "
            "dies one layer short of the browser"
        )


def test_state_update_falls_back_to_prior_context():
    """Outcome 2 contract preserved: an empty context/history falls back to
    the incoming state's values instead of wiping them."""
    empty = ComposeResult(assistant_text="x", success=True)
    update = empty.state_update({
        "last_search_context": {"category": "prior"},
        "search_history": [{"query": "prior"}],
    })
    assert update["last_search_context"] == {"category": "prior"}
    assert update["search_history"] == [{"query": "prior"}]
