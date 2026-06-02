"""
RFC §1.1 — Stage Telemetry and Latency Budgets

Provides:
- StageTelemetry dataclass (serializable to dict for GraphState)
- STAGE_BUDGETS mapping of stage name -> (soft_s, hard_s)
- run_stage_with_budget() helper that enforces timeouts and emits telemetry
- MAX_TOTAL_REQUEST_S constant for the 60-second SSE connection limit
"""
from __future__ import annotations

import asyncio
import dataclasses
import time
from typing import Any, Optional

from app.core.centralized_logger import get_logger

logger = get_logger(__name__)


@dataclasses.dataclass
class StageTelemetry:
    """
    Telemetry record for a single pipeline stage.

    Fields match the RFC §1.1 schema exactly so they can be JSON-serialised
    and included in the SSE `done` event's `stage_telemetry` array.
    """

    stage: str            # e.g. "intent", "safety", "tool.product_search"
    start_ts: float       # wall-clock epoch (time.time()) at stage start
    end_ts: float         # wall-clock epoch at stage end
    duration_ms: int      # monotonic elapsed time in milliseconds
    input_size: int       # caller-provided hint (e.g. len of user message)
    output_size: int      # caller-provided hint (e.g. len of result repr)
    timeout_hit: bool     # True if the hard timeout fired
    degraded_mode: bool   # True if soft *or* hard timeout fired
    error_class: Optional[str]  # None | "transient" | "provider" | "schema" | "fatal"

    def to_dict(self) -> dict:
        """Return a plain dict suitable for JSON serialisation."""
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Stage latency budgets: stage_name -> (soft_timeout_s, hard_timeout_s)
# ---------------------------------------------------------------------------
STAGE_BUDGETS: dict[str, tuple[float, float]] = {
    "safety":       (2.0,   4.0),
    "intent":       (3.0,   6.0),
    # Clarifier needs up to TWO sequential LLM calls (slot extraction + question
    # generation). The old 8s hard budget raced against LLM latency: when extraction
    # alone took ~7s, the timeout fallback fired and SILENTLY SKIPPED clarification —
    # the flagship specialist-question flow disappeared at random (QA Round 4 — F6).
    # 20s keeps a hard bound while making questions reliable; the common "best X"
    # query shape also gets a no-LLM extraction fast path (see clarifier_agent.py).
    "clarifier":    (6.0,  20.0),
    "planner":      (5.0,  10.0),
    "tool":         (8.0,  15.0),
    "plan_exec":    (25.0, 45.0),
    "composition":  (6.0,  12.0),
    "finalization": (2.0,   4.0),
}

# Maximum wall-clock time allowed for the entire SSE streaming response.
MAX_TOTAL_REQUEST_S: float = 60.0


# ---------------------------------------------------------------------------
# Core helper
# ---------------------------------------------------------------------------

async def run_stage_with_budget(
    stage_name: str,
    coro: Any,
    input_size: int = 0,
    fallback_result: Any = None,
    error_class_on_timeout: str = "transient",
) -> tuple[Any, StageTelemetry]:
    """
    Run *coro* within the hard-timeout budget for *stage_name*.

    Algorithm
    ---------
    1. Await ``coro`` under ``asyncio.wait_for(coro, timeout=hard_s)``.
    2. If it finishes within *soft_s*, everything is fine.
    3. If it finishes between soft_s and hard_s: log a warning and mark
       ``degraded_mode=True`` (detected post-hoc from ``duration_ms``).
    4. If the hard timeout fires: log an error, return *fallback_result*,
       and mark ``timeout_hit=True, degraded_mode=True``.
    5. If the coro raises any other exception: log an error, return
       *fallback_result*, and mark ``error_class="fatal"``.

    Returns
    -------
    ``(result, telemetry)`` where *result* is either the coro's return value
    or *fallback_result*.
    """
    soft_s, hard_s = STAGE_BUDGETS.get(stage_name, (8.0, 15.0))

    mono_start = time.monotonic()
    start_ts = time.time()

    timeout_hit = False
    degraded_mode = False
    error_class: Optional[str] = None
    result = fallback_result

    # ------------------------------------------------------------------
    # Execute under the hard timeout
    # ------------------------------------------------------------------
    try:
        result = await asyncio.wait_for(coro, timeout=hard_s)

    except asyncio.TimeoutError:
        timeout_hit = True
        degraded_mode = True
        error_class = error_class_on_timeout
        logger.error(
            f"[stage_telemetry] {stage_name} hard timeout {hard_s}s exceeded"
            " — using fallback result"
        )

    except asyncio.CancelledError:
        raise  # propagate cooperative cancellation; do not treat as "fatal"

    except Exception as exc:
        error_class = "fatal"
        logger.error(
            f"[stage_telemetry] {stage_name} raised unexpected exception: {exc}",
            exc_info=True,
        )
        result = fallback_result

    # ------------------------------------------------------------------
    # Compute elapsed and check soft timeout (post-hoc)
    # ------------------------------------------------------------------
    mono_end = time.monotonic()
    end_ts = time.time()
    duration_ms = int((mono_end - mono_start) * 1000)

    if not timeout_hit and duration_ms > soft_s * 1000:
        degraded_mode = True
        logger.warning(
            f"[stage_telemetry] {stage_name} soft timeout exceeded:"
            f" {duration_ms}ms > {int(soft_s * 1000)}ms"
        )

    # ------------------------------------------------------------------
    # Build telemetry record
    # ------------------------------------------------------------------
    telemetry = StageTelemetry(
        stage=stage_name,
        start_ts=start_ts,
        end_ts=end_ts,
        duration_ms=duration_ms,
        input_size=input_size,
        output_size=0,   # callers may enrich this if they know the output size
        timeout_hit=timeout_hit,
        degraded_mode=degraded_mode,
        error_class=error_class,
    )

    return result, telemetry
