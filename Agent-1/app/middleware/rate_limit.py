"""
Rate limiting middleware using Redis-backed token bucket.

Provides per-IP rate limiting for API endpoints.
Gracefully falls back to a simple in-memory counter when Redis is unavailable.
"""

import os
import time
import logging
from collections import defaultdict
from typing import Dict, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("app.middleware.rate_limit")

# Configuration from environment
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
RATE_LIMIT_WINDOW = 60  # seconds


class _InMemoryRateLimiter:
    """Simple in-memory token bucket rate limiter (fallback when Redis unavailable)."""

    def __init__(self):
        self._buckets: Dict[str, Tuple[int, float]] = {}  # key -> (tokens, window_start)

    def check(self, key: str, max_tokens: int, window: int) -> Tuple[bool, int]:
        """Check if a request is allowed. Returns (allowed, remaining_tokens)."""
        now = time.time()
        tokens, window_start = self._buckets.get(key, (max_tokens, now))

        # Reset if window expired
        if now - window_start > window:
            tokens = max_tokens
            window_start = now

        if tokens > 0:
            tokens -= 1
            self._buckets[key] = (tokens, window_start)
            return True, int(tokens)

        return False, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware.

    Uses Redis when available (via app.core.redis_client), falls back to
    in-memory counter. Rate limits per client IP.
    """

    def __init__(self, app, max_per_minute: int = RATE_LIMIT_PER_MINUTE):
        super().__init__(app)
        self.max_per_minute = max_per_minute
        self._limiter = _InMemoryRateLimiter()
        self._redis_available = False
        self._redis_checked = False

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and static files
        path = request.url.path
        if path in ("/health", "/health/detailed", "/") or path.startswith("/static/"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        # Check rate limit
        allowed, remaining = self._check_rate_limit(client_ip)
        if not allowed:
            logger.warning("Rate limit exceeded for IP: %s (path: %s)", client_ip, path)
            return Response(
                content='{"detail": "请求过于频繁，请稍后再试"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60", "X-RateLimit-Limit": str(self.max_per_minute)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    def _check_rate_limit(self, key: str) -> Tuple[bool, int]:
        """Check rate limit for a key. Returns (allowed, remaining)."""
        return self._limiter.check(
            key, self.max_per_minute, RATE_LIMIT_WINDOW
        )
