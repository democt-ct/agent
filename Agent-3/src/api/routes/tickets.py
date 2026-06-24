"""IT 工单 API(前端卡片直接调用)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(tags=["tickets"])


class TicketRequest(BaseModel):
    issue_type: str
    description: str
    priority: str = "中"


@router.post("/tickets")
async def create_it_ticket(request: Request, body: TicketRequest):
    session = getattr(request.state, "session", None)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})

    from src.tools.it_tools import create_ticket

    result = create_ticket(
        user_id=session.user_id,
        issue_type=body.issue_type,
        description=body.description,
        priority=body.priority,
    )
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result
