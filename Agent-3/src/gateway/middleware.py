"""Auth Middleware -- 从 Authorization header 提取 JWT,注入 SessionContext.

注册方式(app.py):
    from src.gateway.middleware import AuthMiddleware
    app.add_middleware(AuthMiddleware)

下游 handler 通过 request.state.session 获取 SessionContext.
"""

from __future__ import annotations

import logging
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.gateway.auth import get_user_from_token

logger = logging.getLogger(__name__)

# 不需要认证的路径
_PUBLIC_PATHS = {
    "/api/auth/login",
    "/api/agents",
    "/api/health",
    "/docs",
    "/openapi.json",
    "/redoc",
}


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT 认证中间件.

    从 Authorization: Bearer <token> 提取 JWT,
    验证通过后注入 request.state.session = SessionContext.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # 公开路径跳过
        path = request.url.path.rstrip("/")
        if path in _PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/openapi"):
            return await call_next(request)

        # 非 API 路径跳过(前端静态文件,页面等)
        if not path.startswith("/api"):
            return await call_next(request)

        # 提取 token
        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            # 也支持 query param(SSE 场景)
            token = request.query_params.get("token")

        if not token:
            return JSONResponse(
                status_code=401,
                content={"error": "未提供认证凭证", "detail": "请先 POST /api/auth/login 获取 token"},
            )

        session = get_user_from_token(token)
        if session is None:
            return JSONResponse(
                status_code=401,
                content={"error": "认证凭证无效或已过期", "detail": "请重新登录"},
            )

        # 注入 session
        request.state.session = session
        logger.debug("Auth: %s (%s) → %s %s", session.user_id, session.role, request.method, path)

        return await call_next(request)
