from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from app.services.history_service import HistoryService

router = APIRouter()
history_svc = HistoryService()


# ── Pydantic models ────────────────────────────────────────

class SessionCreate(BaseModel):
    name: Optional[str] = None

class MessageAppend(BaseModel):
    role: str          # "user" | "assistant"
    text: str
    image_id: Optional[str] = None
    params: Optional[Dict] = None
    diagnosis: Optional[Dict] = None


# ── Sessions ────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions():
    """列出所有会话（按创建时间降序）。"""
    return history_svc.list_sessions()


@router.post("/sessions")
async def create_session(body: SessionCreate = SessionCreate()):
    """创建新会话。"""
    return history_svc.create_session(name=body.name)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    session = history_svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    ok = history_svc.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}


# ── Messages ───────────────────────────────────────────────

@router.get("/sessions/{session_id}/messages")
async def list_messages(session_id: str):
    """获取某会话的所有消息。"""
    session = history_svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return history_svc.list_messages(session_id)


@router.post("/sessions/{session_id}/messages")
async def append_message(session_id: str, body: MessageAppend):
    """追加一条消息到会话。"""
    session = history_svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    msg = history_svc.append_message(
        session_id=session_id,
        role=body.role,
        text=body.text,
        image_id=body.image_id,
        params=body.params,
        diagnosis=body.diagnosis,
    )
    return msg


# ── Preferences ────────────────────────────────────────────

@router.get("/preferences")
async def get_preferences():
    """获取用户长期偏好（风格偏好、平均参数偏移）。"""
    return history_svc.get_preferences()
