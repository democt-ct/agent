"""会话管理 API -- 列出/删除会话."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.api.models.schemas import ChatErrorResponse, SessionInfo
from src.gateway.auth import SessionContext

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sessions"])


def _get_state(request: Request) -> Any:
    return request.app.state.app_state

def _get_session(request: Request) -> SessionContext | None:
    return getattr(request.state, "session", None)


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions(request: Request) -> list[SessionInfo]:
    """列出当前用户的活跃会话."""
    state = _get_state(request)
    session = _get_session(request)
    if not state or not state.sessions:
        return []

    user_id = session.user_id if session else None
    owners = getattr(state, "session_owners", {})

    result = []
    for sid, messages in state.sessions.items():
        # 用户隔离:只返回自己的会话
        if user_id and owners.get(sid) and owners[sid] != user_id:
            continue
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m["content"]
                break

        result.append(SessionInfo(
            session_id=sid,
            message_count=len(messages),
            last_query=last_user_msg[:100],
            created_at=datetime.now(timezone.utc).isoformat(),
        ))

    # 最新活跃在前
    result.reverse()
    return result


@router.get("/sessions/{session_id}", response_model=None)
async def get_session(session_id: str, request: Request):
    """获取某次会话的完整消息记录(仅限本人)."""
    state = _get_state(request)
    session = _get_session(request)
    if not state or not state.sessions:
        return JSONResponse(
            status_code=404,
            content=ChatErrorResponse(error="会话不存在").model_dump(),
        )

    # 用户隔离检查
    user_id = session.user_id if session else None
    owners = getattr(state, "session_owners", {})
    if user_id and owners.get(session_id) and owners[session_id] != user_id:
        return JSONResponse(
            status_code=403,
            content=ChatErrorResponse(error="无权访问此会话").model_dump(),
        )

    messages = state.sessions.get(session_id)
    if messages is None:
        return JSONResponse(
            status_code=404,
            content=ChatErrorResponse(error=f"会话 {session_id} 不存在").model_dump(),
        )

    return messages


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request) -> dict:
    """删除某次会话(仅限本人)."""
    state = _get_state(request)
    session = _get_session(request)

    # 用户隔离检查
    user_id = session.user_id if session else None
    owners = getattr(state, "session_owners", {})
    if user_id and owners.get(session_id) and owners[session_id] != user_id:
        return {"deleted": False, "error": "无权删除此会话"}

    if state and state.sessions and session_id in state.sessions:
        del state.sessions[session_id]
        if hasattr(state, "session_owners") and session_id in state.session_owners:
            del state.session_owners[session_id]
    return {"deleted": True, "session_id": session_id}
