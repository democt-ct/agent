"""Observability module -- structured tracing with JSONL output.

Usage:
    from src.observability.trace_collector import TraceCollector

    collector = TraceCollector(enabled=True)
    collector.start_trace(query="...", session_id="...")
    collector.add_event("routing", {"primary": "hr_agent"})
    collector.add_event("retrieval", {"count": 5})
    collector.end_trace("success", total_tokens=1200)
"""

from src.observability.trace_collector import TraceCollector
from src.observability.trace_models import Trace, TraceEvent

__all__ = ["TraceCollector", "Trace", "TraceEvent"]
