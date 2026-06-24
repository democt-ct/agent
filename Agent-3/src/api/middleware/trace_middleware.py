"""FastAPI middleware that injects a TraceCollector into every request.

Usage (in app.py):
    from src.api.middleware import TraceMiddleware
    app.add_middleware(TraceMiddleware)

Downstream handlers access the collector via:
    collector = request.state.trace_collector   # TraceCollector or None
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.observability.trace_collector import TraceCollector

logger = logging.getLogger(__name__)


class TraceMiddleware(BaseHTTPMiddleware):
    """Injects a TraceCollector into request.state for every HTTP request.

    The collector is created on every request (lightweight -- no global state).
    If TRACE_ENABLED is false the collector is still created but its methods
    are no-ops, so downstream code doesn't need conditional logic.

    The collector is NOT finalised here because:
    - SSE endpoints are long-lived and finalise internally.
    - POST /chat finalises after the chat_service call completes.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Create collector, call downstream, return response."""
        try:
            request.state.trace_collector = TraceCollector()
        except Exception:
            # Trace init failure must never break the request
            request.state.trace_collector = None
            logger.warning("Failed to create TraceCollector", exc_info=True)

        response = await call_next(request)
        return response
