"""ComposeResult — THE single definition of composer output (DOCTRINE D2).

Before this model, a composer field only reached the browser if FIVE layers
each named it by hand: composer → tool_validator (Pydantic schema) →
plan_executor._extract_results → workflow.plan_executor_node merge → chat.py
SSE payload. Any layer that forgot the field dropped it silently — three
shipped incidents (follow_up_question, transitional_reasoning,
last_search_context) were each patched at whichever layer caught them.

Now every layer consumes THIS model:
- tool_validator validates compose output against it (extra fields are kept,
  never stripped — the model_dump() silent-drop trap is gone).
- _extract_results copies its declared fields mechanically.
- plan_executor_node builds its state update from state_update() — including
  the timeout fallback, so the two can never drift apart.
- chat.py's emission of each field is pinned by the golden source audit in
  tests/test_compose_result_golden.py.

ADDING A FIELD: declare it below (with a default), make the composer emit it,
and — if the browser must see it — emit it in chat.py and extend the golden
test's CHAT_EMISSION_FIELDS. Two deliberate places instead of five silent ones,
with a red test if either is missed.

Only DECLARED fields enter the GraphState update (state_update): every one of
them must be an existing GraphState channel, or LangGraph crashes at the node
boundary. Extra (undeclared) fields still survive validation and
_extract_results, but stop before GraphState by design.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# Fields that describe the tool call itself, not content — they stay out of
# results/state updates. (Module-level: Pydantic v2 converts underscore class
# attributes into ModelPrivateAttr.)
_META_FIELDS = ("success", "error")


class ComposeResult(BaseModel):
    """Canonical composer output. See module docstring for the contract."""

    # extra="allow": unknown keys survive validation and model_dump() so the
    # validator layer can never silently strip a field again.
    model_config = ConfigDict(extra="allow")

    assistant_text: str = ""
    ui_blocks: List[Any] = Field(default_factory=list)
    citations: List[Any] = Field(default_factory=list)
    # B.3: emitted by chat.py as its own SSE event after the body finishes.
    follow_up_question: Optional[str] = None
    # Quiz-path: emitted by chat.py as its own SSE event (TransitionalBubble).
    transitional_reasoning: Optional[str] = None
    # Outcome 2: persisted across turns by chat.py for refinement chips.
    last_search_context: Dict[str, Any] = Field(default_factory=dict)
    search_history: List[Any] = Field(default_factory=list)
    success: bool = False
    error: Optional[str] = None

    @classmethod
    def content_field_names(cls) -> List[str]:
        """Declared fields that carry composer CONTENT (everything the
        downstream layers must propagate)."""
        return [f for f in cls.model_fields if f not in _META_FIELDS]

    def content_items(self) -> Dict[str, Any]:
        """Declared content fields only — the mechanical copy for
        _extract_results. Extra fields are intentionally excluded from state
        propagation (undeclared keys must never reach GraphState channels)."""
        dumped = self.model_dump()
        return {f: dumped[f] for f in self.content_field_names()}

    def state_update(
        self,
        prior_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """The composer's share of a LangGraph node update.

        last_search_context / search_history fall back to the incoming state's
        values so a non-product turn doesn't wipe the context a previous
        product turn established (Outcome 2 contract, unchanged).
        """
        prior_state = prior_state or {}
        update = self.content_items()
        if not update.get("last_search_context"):
            update["last_search_context"] = prior_state.get("last_search_context", {}) or {}
        if not update.get("search_history"):
            update["search_history"] = prior_state.get("search_history", []) or []
        return update
