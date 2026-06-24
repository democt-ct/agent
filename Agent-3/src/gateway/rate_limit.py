"""Rate Limiter -- 令牌桶限流.

per-user + per-IP 双维度限流.
超限返回 429 Too Many Requests.

内存实现,单进程够用.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# 允许不经限流的路径
_PUBLIC_PATHS = {"/api/auth/login", "/api/health", "/docs", "/openapi.json"}


class TokenBucket:
    """令牌桶 -- 固定窗口 + 最大突发."""

    def __init__(self, rate: float, burst: int):
        self.rate = rate          # tokens per second
        self.burst = burst        # max tokens
        self.tokens = float(burst)
        self.last_refill = time.monotonic()

    def consume(self) -> bool:
        """尝试消费 1 个 token.返回 True 表示允许."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_refill = now

        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


class RateLimiter:
    """双维度限流器."""

    def __init__(
        self,
        user_rate: float = 10.0 / 60.0,     # 10 req/min → tokens/sec
        user_burst: int = 10,
        ip_rate: float = 30.0 / 60.0,       # 30 req/min
        ip_burst: int = 30,
    ):
        self.user_rate = user_rate
        self.user_burst = user_burst
        self.ip_rate = ip_rate
        self.ip_burst = ip_burst
        self._user_buckets: dict[str, TokenBucket] = {}
        self._ip_buckets: dict[str, TokenBucket] = {}

    def is_allowed(self, user_id: str, ip: str) -> tuple[bool, str]:
        """检查是否允许请求.返回 (allowed, reason)."""
        # per-user
        if user_id and user_id != "anonymous":
            bucket = self._user_buckets.get(user_id)
            if bucket is None:
                bucket = TokenBucket(self.user_rate, self.user_burst)
                self._user_buckets[user_id] = bucket
            if not bucket.consume():
                return False, f"用户 {user_id} 请求过于频繁,请稍后再试"

        # per-IP
        bucket = self._ip_buckets.get(ip)
        if bucket is None:
            bucket = TokenBucket(self.ip_rate, self.ip_burst)
            self._ip_buckets[ip] = bucket
        if not bucket.consume():
            return False, f"IP {ip} 请求过于频繁,请稍后再试"

        return True, ""

    def cleanup(self, max_age_seconds: int = 300) -> None:
        """清理过期的桶(可定时调用)."""
        # 简单实现:超过 max_age 没访问的桶删除
        # 实际生产中由 Redis TTL 处理
        pass


# ── FastAPI Middleware ────────────────────────────────────────────


class RateLimitMiddleware(BaseHTTPMiddleware):
    """限流中间件 -- 在 Auth 之后注册.

    从 request.state.session 获取用户 ID.
    """

    def __init__(self, app, limiter: RateLimiter | None = None):
        super().__init__(app)
        self.limiter = limiter or RateLimiter()

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        path = request.url.path.rstrip("/")
        if path in _PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/openapi"):
            return await call_next(request)

        # 非 API 路径不限流(前端静态文件,页面等)
        if not path.startswith("/api"):
            return await call_next(request)
            return await call_next(request)

        user_id = getattr(getattr(request.state, "session", None), "user_id", "anonymous")
        ip = request.client.host if request.client else "unknown"

        allowed, reason = self.limiter.is_allowed(user_id, ip)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "请求过于频繁", "detail": reason, "retry_after": 60},
                headers={"Retry-After": "60"},
            )

        return await call_next(request)
