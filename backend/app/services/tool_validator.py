"""
Tool Output Validator — RFC §3.4
Contract validation at tool boundaries.

Validates the output dicts returned by the 5 highest-risk MCP tools against
Pydantic schemas.  On a schema violation the offending output is quarantined:
an ERROR is logged and an empty-but-valid default dict is returned so that
downstream tools never receive a corrupt value.

Usage (in plan_executor.py):

    from app.services.tool_validator import ToolOutputValidator

    raw_output = await tool_fn(state)
    validated_output = ToolOutputValidator.validate(tool_name, raw_output)
    # use validated_output from here on
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ValidationError

from app.core.centralized_logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Per-tool output schemas
# ---------------------------------------------------------------------------

class ProductSearchOutput(BaseModel):
    """Schema for product_search tool output.

    The tool returns:
        product_names: List[Any]   — list of product name strings
        success:       bool
        error:         Optional[str]   — present only on failure path
        timed_out:     Optional[bool]  — set True by _call_tool_direct on timeout
    """
    product_names: Optional[List[Any]] = []
    success: Optional[bool] = False
    error: Optional[str] = None
    timed_out: Optional[bool] = None


class ProductComposeOutput(BaseModel):
    """Schema for product_compose tool output.

    The tool returns:
        assistant_text:      str
        follow_up_question:  Optional[str]  — B.3 curious follow-up emitted as
                             its own SSE event by chat.py after the body finishes
        ui_blocks:           List[Any]  — list of UI block dicts
        citations:           List[Any]  — list of citation URL strings
        last_search_context: dict       — optional context dict for follow-ups
        search_history:      List[Any]  — optional search history list
        success:             bool
        error:               Optional[str]

    Any field not declared here is silently dropped by ``model_dump()`` at
    ``validate()`` (line ~163). PRs #13 and #14 fixed the lower layers
    (_extract_results, plan_executor_node wrapper) but the validator was
    quietly stripping ``follow_up_question`` upstream of both, so the
    end-to-end SSE event never fired in prod despite the composer emitting
    100+ char follow-ups (per ``[product_compose] LLM blog article: ...``
    log line). Declaring the field here unblocks the chain.
    """
    assistant_text: Optional[str] = ""
    follow_up_question: Optional[str] = None
    # Quiz-path transitional reasoning — declared here or model_dump() silently
    # drops it (same trap that hid follow_up_question pre-PR #15). See graph_state.py.
    transitional_reasoning: Optional[str] = None
    ui_blocks: Optional[List[Any]] = []
    citations: Optional[List[Any]] = []
    last_search_context: Optional[Dict[str, Any]] = {}
    search_history: Optional[List[Any]] = []
    success: Optional[bool] = False
    error: Optional[str] = None


class TravelSearchHotelsOutput(BaseModel):
    """Schema for travel_search_hotels tool output.

    The tool returns:
        hotels:    List[Any]       — list of hotel result dicts (may be PLP link objects)
        citations: List[Any]       — list of search URL strings
        success:   bool
        error:     Optional[str]
        timed_out: Optional[bool]  — set True by _call_tool_direct on timeout
    """
    hotels: Optional[List[Any]] = []
    citations: Optional[List[Any]] = []
    success: Optional[bool] = False
    error: Optional[str] = None
    timed_out: Optional[bool] = None


class TravelSearchFlightsOutput(BaseModel):
    """Schema for travel_search_flights tool output.

    The tool returns:
        flights:   List[Any]       — list of flight result dicts (may be PLP link objects)
        citations: List[Any]       — list of search URL strings
        success:   bool
        error:     Optional[str]
        timed_out: Optional[bool]  — set True by _call_tool_direct on timeout
    """
    flights: Optional[List[Any]] = []
    citations: Optional[List[Any]] = []
    success: Optional[bool] = False
    error: Optional[str] = None
    timed_out: Optional[bool] = None


class ProductNormalizeOutput(BaseModel):
    """Schema for product_normalize tool output.

    The tool returns:
        normalized_products: List[Any]  — list of normalized product dicts
        success:             bool
        error:               Optional[str]
    """
    normalized_products: Optional[List[Any]] = []
    success: Optional[bool] = False
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class ToolOutputValidator:
    """Validates tool output dicts against registered Pydantic schemas.

    Only the 5 highest-risk tools have registered schemas.  All other tools
    pass through unchanged.

    Behaviour on schema violation:
    - logs ERROR with full Pydantic error detail
    - returns an empty-but-valid dict constructed via schema() (normal constructor,
      applies all field defaults correctly)
    - does NOT raise — the pipeline must always continue
    """

    _schemas: Dict[str, type[BaseModel]] = {
        "product_search": ProductSearchOutput,
        "product_compose": ProductComposeOutput,
        "travel_search_hotels": TravelSearchHotelsOutput,
        "travel_search_flights": TravelSearchFlightsOutput,
        "product_normalize": ProductNormalizeOutput,
    }

    @classmethod
    def validate(cls, tool_name: str, output: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and return the tool output, quarantining violations.

        Args:
            tool_name: The registered tool name (e.g. "product_search").
            output:    The raw dict returned by the tool function.

        Returns:
            The validated dict (unchanged) on success, or an empty-but-valid
            dict of the same shape if validation fails.
            Unregistered tool names are passed through unchanged.
        """
        schema = cls._schemas.get(tool_name)

        if schema is None:
            # No schema registered for this tool — pass through unchanged
            return output

        try:
            validated = schema(**output)
            return validated.model_dump()
        except ValidationError as exc:
            logger.error(
                "[tool_validator] %s output schema violation — quarantining output. "
                "Pydantic errors: %s",
                tool_name,
                exc,
            )
            # Quarantine: return empty-but-valid output so downstream tools
            # always receive a dict of the correct shape (never a corrupt value).
            # Use schema() (normal constructor) so Optional[List] = [] defaults
            # are populated correctly; model_construct() bypasses defaults.
            return schema().model_dump()
        except (TypeError, AttributeError) as exc:
            # output is not a dict (e.g. a bare string), so schema(**output) raised
            logger.error(
                "[tool_validator] %s validate() received non-dict output — quarantining. Error: %s",
                tool_name,
                exc,
            )
            return schema().model_dump()
