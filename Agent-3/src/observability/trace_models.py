"""Pydantic models for structured tracing.

Every Trace is a sequence of TraceEvent records, flushed as one JSON line per trace.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    """A single observation point within a trace.

    Examples:
        routing  -- {"primary": "hr_agent", "confidence": 0.95, "method": "keyword"}
        retrieval -- {"count": 8, "sources": [{"source": "...", "score": 0.87}, ...]}
        tool_call -- {"name": "get_leave_balance", "arguments": {...}, "result": {...}}
        llm_call  -- {"model": "deepseek-v4-flash", "tokens": 450, "duration_ms": 820}
        answer    -- {"content": "您的年假剩余7天...", "agent_name": "hr_agent"}
        error     -- {"message": "Connection timeout", "stage": "llm_call"}
    """

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = Field(default_factory=lambda: __import__("time").time())
    event_type: str
    agent_name: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int | None = None


class Trace(BaseModel):
    """Full trace for one user query, serialised as a single JSONL line.

    Lifecycle:
        pending → (events appended) → success | error | fallback
    """

    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    session_id: str
    query: str
    start_time: float = Field(default_factory=lambda: __import__("time").time())
    end_time: float | None = None
    events: list[TraceEvent] = Field(default_factory=list)
    total_tokens: int = 0
    status: Literal["pending", "success", "error", "fallback"] = "pending"
