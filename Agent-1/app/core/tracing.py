"""分布式追踪 —— OpenTelemetry 集成.

提供轻量级追踪能力：
  - 本地 span 记录（默认无需外部 collector）
  - 可选 OTLP 导出到 Jaeger/Tempo（通过 OTEL_EXPORTER_OTLP_ENDPOINT 环境变量）
  - 关键节点自动埋点：agent_query → intent → plan → tool_exec → answer

使用方式：
  from app.core.tracing import trace_agent_phase

  with trace_agent_phase("intent_identification", session_id="...", patient_id="..."):
      intent = identify_intent(question)
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Optional

from prometheus_client import Counter, Histogram

# ── Metrics (augment existing agent metrics with trace-level granularity) ──

TRACE_SPAN_COUNT = Counter(
    "trace_spans_total",
    "Total trace spans created",
    ["phase", "status"],
)

TRACE_SPAN_LATENCY = Histogram(
    "trace_span_duration_seconds",
    "Trace span duration in seconds",
    ["phase"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

# ── Error / Escalation Counters ──

AGENT_QUERY_ERROR_COUNT = Counter(
    "agent_query_errors_total",
    "Total agent query errors",
    ["error_type"],
)

ESCALATION_COUNT = Counter(
    "escalations_total",
    "Total escalations triggered",
    ["reason", "severity"],
)

# ── OTel optional integration ──

_otel_available = False
try:
    from opentelemetry import trace as otel_trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _otel_available = True
except ImportError:
    pass


_tracer = None


def _get_tracer(name: str = "agent-1"):
    global _tracer
    if _tracer is not None:
        return _tracer

    if _otel_available and os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        try:
            resource = Resource(attributes={"service.name": "patient-agent"})
            provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(exporter))
            otel_trace.set_tracer_provider(provider)
            _tracer = otel_trace.get_tracer(name)
            return _tracer
        except Exception:
            pass

    # Fallback: null tracer — always returns a no-op span
    class _NoOpSpan:
        def set_attribute(self, *a, **kw): pass
        def set_status(self, *a, **kw): pass
        def end(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a, **kw): pass

    class _NoOpTracer:
        def start_as_current_span(self, name, attributes=None):
            return _NoOpSpan()

    _tracer = _NoOpTracer()
    return _tracer


def _normalize_attributes(attrs: Optional[dict] = None, **kwargs) -> dict:
    """将任意值转为 OTel 兼容的字符串 attribute."""
    result = dict(attrs or {})
    result.update(kwargs)
    return {k: str(v)[:256] for k, v in result.items() if v is not None}


@contextmanager
def trace_agent_phase(
    phase: str,
    *,
    session_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    intent: Optional[str] = None,
    model: Optional[str] = None,
    chat_mode: Optional[str] = None,
    **extra,
):
    """追踪 Agent Pipeline 的一个阶段.

    Usage:
        with trace_agent_phase("intent_identification", session_id=sid, patient_id=pid):
            result = _identify_intent(...)
    """
    start = time.time()
    status = "success"
    try:
        tracer = _get_tracer()
        attrs = _normalize_attributes(
            session_id=session_id,
            patient_id=patient_id,
            intent=intent,
            model=model,
            chat_mode=chat_mode,
            **extra,
        )
        with tracer.start_as_current_span(f"agent.{phase}", attributes=attrs):
            yield
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.time() - start
        TRACE_SPAN_COUNT.labels(phase=phase, status=status).inc()
        TRACE_SPAN_LATENCY.labels(phase=phase).observe(duration)


def record_agent_error(error_type: str) -> None:
    """记录 Agent 错误计数."""
    AGENT_QUERY_ERROR_COUNT.labels(error_type=error_type).inc()


def record_escalation(reason: str, severity: str) -> None:
    """记录升级事件."""
    ESCALATION_COUNT.labels(reason=reason, severity=severity).inc()


# ── Convenience wrappers for key pipeline phases ──

def trace_intent(session_id: str = "", patient_id: str = "", **kw):
    return trace_agent_phase("intent_identification", session_id=session_id, patient_id=patient_id, **kw)


def trace_planning(session_id: str = "", patient_id: str = "", **kw):
    return trace_agent_phase("plan_generation", session_id=session_id, patient_id=patient_id, **kw)


def trace_tool_execution(session_id: str = "", patient_id: str = "", **kw):
    return trace_agent_phase("tool_execution", session_id=session_id, patient_id=patient_id, **kw)


def trace_answer_generation(session_id: str = "", patient_id: str = "", **kw):
    return trace_agent_phase("answer_generation", session_id=session_id, patient_id=patient_id, **kw)


def trace_safety_check(session_id: str = "", patient_id: str = "", **kw):
    return trace_agent_phase("safety_check", session_id=session_id, patient_id=patient_id, **kw)
