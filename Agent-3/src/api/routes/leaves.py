"""Leaves REST API -- 请假记录 CRUD.

端点:
    GET    /api/leaves         -- 请假列表(自己的;manager/hr 可看下属)
    GET    /api/leaves/{id}    -- 单条详情 + 审批进度
    POST   /api/leaves         -- 提交新请假
    PUT    /api/leaves/{id}    -- 编辑请假(仅 draft/pending + 本人)
    DELETE /api/leaves/{id}    -- 取消请假(仅 pending + 本人)
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.gateway.auth import SessionContext

router = APIRouter(tags=["leaves"])


# ── Request Models ──────────────────────────────────────────────

class CreateLeaveRequest(BaseModel):
    leave_type: str = Field(..., description="假期类型: 年假/病假/事假")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    reason: str = Field(default="", description="请假原因")


class UpdateLeaveRequest(BaseModel):
    leave_type: str | None = Field(default=None, description="假期类型")
    start_date: str | None = Field(default=None, description="开始日期 YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="结束日期 YYYY-MM-DD")
    reason: str | None = Field(default=None, description="请假原因")


# ── Helpers ─────────────────────────────────────────────────────

def _get_session(request: Request) -> SessionContext | None:
    return getattr(request.state, "session", None)


def _can_edit(record: dict, session: SessionContext) -> bool:
    """只有本人且状态为 draft 或 pending 时可编辑."""
    if record["user_id"] != session.user_id:
        return False
    return record["status"] in ("draft", "pending")


def _can_cancel(record: dict, session: SessionContext) -> bool:
    """只有本人且状态为 pending 时可取消."""
    if record["user_id"] != session.user_id:
        return False
    return record["status"] == "pending"


def _can_view(record: dict, session: SessionContext) -> bool:
    """本人可看;manager 可看下属的;hr/admin 可看全部."""
    if record["user_id"] == session.user_id:
        return True
    if session.role in ("hr", "admin"):
        return True
    if session.role == "manager":
        # 只能看自己下属:检查 record 的 user_id 是否在自己的汇报链中
        return session.can_approve(record["user_id"])
    return False


# ── Endpoints ───────────────────────────────────────────────────

@router.get("/leaves")
async def list_leaves(request: Request):
    """获取请假记录列表.

    普通员工只能看自己的;manager/hr 可查看所有下属的.
    支持 ?status=pending 过滤.
    """
    session = _get_session(request)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})

    from src.tools.db import get_db

    status_filter = request.query_params.get("status", "").strip()

    with get_db() as conn:
        if session.role in ("manager", "hr", "admin"):
            # 管理者:自己的 + 所有下属的(递归)
            subordinate_sql = """
                WITH RECURSIVE subordinates AS (
                    SELECT user_id FROM users WHERE manager_id = ?
                    UNION ALL
                    SELECT u.user_id FROM users u
                    JOIN subordinates s ON u.manager_id = s.user_id
                )
                SELECT l.*, u.name as user_name, u.department_id as dept_id
                FROM leave_records l
                JOIN users u ON l.user_id = u.user_id
                WHERE l.user_id = ?
                   OR l.user_id IN (SELECT user_id FROM subordinates)
            """
            params = [session.user_id, session.user_id]
            if status_filter:
                subordinate_sql += " AND l.status = ?"
                params.append(status_filter)
            subordinate_sql += " ORDER BY l.created_at DESC LIMIT 100"
            rows = conn.execute(subordinate_sql, params).fetchall()
        else:
            if status_filter:
                rows = conn.execute(
                    """SELECT l.*, u.name as user_name, u.department_id as dept_id
                       FROM leave_records l
                       JOIN users u ON l.user_id = u.user_id
                       WHERE l.user_id = ? AND l.status = ?
                       ORDER BY l.created_at DESC LIMIT 50""",
                    (session.user_id, status_filter),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT l.*, u.name as user_name, u.department_id as dept_id
                       FROM leave_records l
                       JOIN users u ON l.user_id = u.user_id
                       WHERE l.user_id = ?
                       ORDER BY l.created_at DESC LIMIT 50""",
                    (session.user_id,),
                ).fetchall()

    return {"leaves": [dict(r) for r in rows]}


@router.get("/leaves/{record_id}")
async def get_leave(request: Request, record_id: str):
    """获取单条请假记录详情,包含审批进度."""
    session = _get_session(request)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})

    from src.tools.db import get_db, db_get_approval_status

    with get_db() as conn:
        row = conn.execute(
            """SELECT l.*, u.name as user_name, u.department_id as dept_id
               FROM leave_records l
               JOIN users u ON l.user_id = u.user_id
               WHERE l.id = ?""",
            (record_id,),
        ).fetchone()

    if row is None:
        return JSONResponse(status_code=404, content={"error": "请假记录不存在"})

    record = dict(row)
    if not _can_view(record, session):
        return JSONResponse(status_code=403, content={"error": "无权查看此记录"})

    # 审批进度
    approval_steps = db_get_approval_status("leave", record_id)

    # 当前用户可以审批的步骤(pending + approver_id 匹配)
    my_pending_steps = [
        {"step_id": s["id"], "step": s["step"], "approver_role": s["approver_role"]}
        for s in approval_steps
        if s["status"] == "pending" and s["approver_id"] == session.user_id
    ]

    return {
        "leave": record,
        "approval": [dict(s) for s in approval_steps],
        "can_edit": _can_edit(record, session),
        "can_cancel": _can_cancel(record, session),
        "can_approve": len(my_pending_steps) > 0,
        "my_pending_steps": my_pending_steps,
    }


@router.post("/leaves")
async def create_leave(request: Request, body: CreateLeaveRequest):
    """提交新请假申请."""
    session = _get_session(request)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})

    from src.tools.hr_tools import submit_leave_request

    result = submit_leave_request(
        user_id=session.user_id,
        leave_type=body.leave_type,
        start_date=body.start_date,
        end_date=body.end_date,
        reason=body.reason,
    )

    if "error" in result:
        return JSONResponse(status_code=400, content=result)

    return result


@router.put("/leaves/{record_id}")
async def update_leave(request: Request, record_id: str, body: UpdateLeaveRequest):
    """编辑请假记录(仅 draft/pending + 本人)."""
    session = _get_session(request)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})

    from src.tools.db import get_db

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM leave_records WHERE id = ?", (record_id,)
        ).fetchone()

    if row is None:
        return JSONResponse(status_code=404, content={"error": "请假记录不存在"})

    record = dict(row)
    if not _can_edit(record, session):
        return JSONResponse(
            status_code=403,
            content={"error": "只能编辑自己的草稿/待审批记录"},
        )

    # 构建更新字段
    updates = {}
    if body.leave_type is not None:
        updates["leave_type"] = body.leave_type
    if body.start_date is not None:
        updates["start_date"] = body.start_date
    if body.end_date is not None:
        updates["end_date"] = body.end_date
    if body.reason is not None:
        updates["reason"] = body.reason

    if not updates:
        return JSONResponse(status_code=400, content={"error": "没有要更新的字段"})

    # 重算天数(如果日期变了)
    if "start_date" in updates or "end_date" in updates:
        from datetime import date as dt_date
        try:
            s = dt_date.fromisoformat(updates.get("start_date", record["start_date"]))
            e = dt_date.fromisoformat(updates.get("end_date", record["end_date"]))
            updates["total_days"] = (e - s).days + 1
        except (ValueError, TypeError):
            return JSONResponse(status_code=400, content={"error": "日期格式无效"})

    from datetime import datetime, timezone
    updates["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [record_id]

    with get_db() as conn:
        conn.execute(
            f"UPDATE leave_records SET {set_clause} WHERE id = ?", values
        )
        conn.commit()

    return {"success": True, "message": "请假记录已更新"}


@router.delete("/leaves/{record_id}")
async def cancel_leave(request: Request, record_id: str):
    """取消请假(仅 pending + 本人)."""
    session = _get_session(request)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})

    from src.tools.db import get_db

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM leave_records WHERE id = ?", (record_id,)
        ).fetchone()

    if row is None:
        return JSONResponse(status_code=404, content={"error": "请假记录不存在"})

    record = dict(row)
    if not _can_cancel(record, session):
        return JSONResponse(
            status_code=403,
            content={"error": "只能取消自己的待审批记录"},
        )

    from src.workflow.state_machine import transition_leave_status
    transition_leave_status(record_id, "cancelled")

    return {"success": True, "message": "请假已取消"}
