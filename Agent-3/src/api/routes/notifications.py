"""通知中心 API."""
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
async def list_notifications(request: Request, unread_only: int = 0):
    session = getattr(request.state, "session", None)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})
    from src.tools.db import db_get_notifications, db_unread_count
    items = db_get_notifications(session.user_id, unread_only=bool(unread_only))
    count = db_unread_count(session.user_id)
    return {"notifications": items, "unread_count": count}


@router.post("/notifications/read")
async def mark_read(request: Request):
    session = getattr(request.state, "session", None)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})
    body = await request.json()
    ids = body.get("ids")  # None = 全部已读
    from src.tools.db import db_mark_notifications_read
    db_mark_notifications_read(session.user_id, ids)
    return {"success": True}


@router.get("/notifications/count")
async def unread_count(request: Request):
    session = getattr(request.state, "session", None)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})
    from src.tools.db import db_unread_count
    return {"unread_count": db_unread_count(session.user_id)}
