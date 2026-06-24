"""TraceCollector -- per-request trace accumulator with JSONL flush.

Design:
- One TraceCollector per request (lightweight, no global state).
- Events are appended in-memory; on end_trace() the full Trace is
  serialised as one JSON line appended to a date-rotated file.
- All I/O is wrapped in try-except -- trace failures never bubble up
  to the main request flow.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any

from src.config import config
from src.observability.trace_models import Trace, TraceEvent

logger = logging.getLogger(__name__)


class TraceCollector:
    """Per-request trace accumulator.

    Usage:
        tc = TraceCollector()
        tc.start_trace("年假还剩几天", session_id="abc123")
        tc.add_event("routing", {"primary": "hr_agent"})
        tc.add_event("retrieval", {"count": 5})
        tc.end_trace("success", total_tokens=1200)
    """

    def __init__(self) -> None:
        self._enabled: bool = config.trace_enabled
        self._trace: Trace | None = None
        self._lock = threading.Lock()

    # ── Public API ──────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        """Whether tracing is active (driven by TRACE_ENABLED env var)."""
        return self._enabled

    @property
    def trace(self) -> Trace | None:
        """The current trace, or None if not started / disabled."""
        return self._trace

    def start_trace(self, query: str, session_id: str = "") -> Trace | None:
        """Begin a new trace for the given query.

        Returns the Trace object if tracing is enabled, else None.
        Callers should guard add_event / end_trace with a None check
        or simply call them unconditionally (they are no-ops when disabled).
        """
        if not self._enabled:
            return None

        with self._lock:
            self._trace = Trace(
                session_id=session_id or "unknown",
                query=query,
            )
            logger.debug("Trace started: %s", self._trace.trace_id)
            return self._trace

    def add_event(
        self,
        event_type: str,
        data: dict[str, Any],
        agent_name: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Record an event in the current trace. No-op if disabled or not started.

        Args:
            event_type: One of routing | retrieval | tool_call | llm_call | answer | error.
            data: Arbitrary JSON-serialisable dict with event details.
            agent_name: Optional agent that produced this event.
            duration_ms: Optional wall-clock duration for this event.
        """
        if not self._enabled or self._trace is None:
            return

        try:
            event = TraceEvent(
                event_type=event_type,  # type: ignore[arg-type]
                agent_name=agent_name,
                data=data,
                duration_ms=duration_ms,
            )
            with self._lock:
                self._trace.events.append(event)
        except Exception:
            logger.warning("Failed to record trace event", exc_info=True)

    def end_trace(
        self,
        status: str = "success",
        total_tokens: int = 0,
    ) -> None:
        """Finalise the current trace and flush to disk. No-op if disabled.

        Args:
            status: One of success | error | fallback.
            total_tokens: Aggregate token count for the whole request.
        """
        if not self._enabled or self._trace is None:
            return

        try:
            with self._lock:
                self._trace.end_time = __import__("time").time()
                self._trace.status = status  # type: ignore[arg-type]
                self._trace.total_tokens = total_tokens
            self._flush()
        except Exception:
            logger.warning("Failed to finalise trace", exc_info=True)
        finally:
            self._trace = None

    # ── Internal ─────────────────────────────────────────────────

    def _flush(self) -> None:
        """Append the trace as one JSON line to the date-rotated output file.

        File path:  {trace_output_dir}/trace_{YYYY-MM-DD}.jsonl
        """
        if self._trace is None:
            return

        try:
            output_dir = config.trace_output_dir
            os.makedirs(output_dir, exist_ok=True)

            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            filepath = os.path.join(output_dir, f"trace_{date_str}.jsonl")

            line = self._trace.model_dump_json()
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(line + "\n")

            logger.debug("Trace flushed: %s → %s", self._trace.trace_id, filepath)
        except Exception:
            logger.warning("Failed to flush trace to disk", exc_info=True)
