"""
Prometheus metrics for the application.

Exposes a /metrics endpoint with:
- HTTP request count and latency (by method, path, status)
- Active patient count
- Knowledge chunk count
- LLM call count and latency
"""

import os
import time
from functools import wraps
from typing import Callable

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from starlette.responses import Response

# ── HTTP Metrics ──

HTTP_REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

HTTP_REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

# ── Business Metrics ──

ACTIVE_PATIENTS = Gauge(
    "active_patients_total",
    "Total number of active patients in the system",
)

KNOWLEDGE_CHUNKS = Gauge(
    "knowledge_chunks_total",
    "Total number of knowledge chunks stored",
)

# ── Agent Metrics ──

AGENT_QUERY_COUNT = Counter(
    "agent_queries_total",
    "Total agent queries processed",
    ["intent", "chat_mode"],
)

AGENT_QUERY_LATENCY = Histogram(
    "agent_query_duration_seconds",
    "Agent query latency in seconds",
    ["intent"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

LLM_CALL_COUNT = Counter(
    "llm_calls_total",
    "Total LLM API calls",
    ["model", "status"],
)

LLM_CALL_LATENCY = Histogram(
    "llm_call_duration_seconds",
    "LLM API call latency in seconds",
    ["model"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

LLM_CALL_TOKENS = Counter(
    "llm_tokens_total",
    "Total LLM tokens consumed",
    ["model", "type"],
)


def metrics_endpoint(request):
    """Return Prometheus metrics in the standard format."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def observe_llm_call(model: str = "unknown", status: str = "success", duration: float = 0, tokens: int = 0):
    """Record an LLM call metric."""
    LLM_CALL_COUNT.labels(model=model, status=status).inc()
    LLM_CALL_LATENCY.labels(model=model).observe(duration)
    if tokens:
        LLM_CALL_TOKENS.labels(model=model, type="total").inc(tokens)


# ── Convenience Functions ──

def track_agent_query(intent: str, chat_mode: str = "memory"):
    """Decorator to track agent query metrics."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                AGENT_QUERY_COUNT.labels(intent=intent, chat_mode=chat_mode).inc()
                return result
            finally:
                duration = time.time() - start
                AGENT_QUERY_LATENCY.labels(intent=intent).observe(duration)
        return wrapper
    return decorator
