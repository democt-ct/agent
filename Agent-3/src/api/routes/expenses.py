"""报销申请 API(前端卡片直接调用)."""
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(tags=["expenses"])


class ExpenseRequest(BaseModel):
    expense_type: str
    amount: float
    description: str = ""
    receipt_url: str = ""
    metadata: str = ""


@router.post("/expenses")
async def create_expense(request: Request, body: ExpenseRequest):
    session = getattr(request.state, "session", None)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})

    from src.tools.finance_tools import submit_expense_report
    result = submit_expense_report(
        user_id=session.user_id,
        expense_type=body.expense_type,
        amount=body.amount,
        description=body.description,
        receipt_url=body.receipt_url,
        metadata=body.metadata,
    )
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result


@router.get("/expenses")
async def list_expenses(request: Request):
    session = getattr(request.state, "session", None)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})
    from src.tools.db import get_db
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM expense_reports WHERE user_id=? ORDER BY created_at DESC LIMIT 50",
            (session.user_id,),
        ).fetchall()
    return {"expenses": [dict(r) for r in rows]}
