"""Approvals REST API -- 审批操作.

端点:
    GET    /api/approvals/pending            -- 当前用户的待审批列表
    POST   /api/approvals/{step_id}/approve  -- 审批通过
    POST   /api/approvals/{step_id}/reject   -- 驳回
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.gateway.auth import SessionContext

router = APIRouter(tags=["approvals"])


# ── Request Models ──────────────────────────────────────────────

class ApproveRequest(BaseModel):
    comment: str = Field(default="", description="审批意见")


class RejectRequest(BaseModel):
    comment: str = Field(default="", description="驳回理由")


# ── Helpers ─────────────────────────────────────────────────────

def _get_session(request: Request) -> SessionContext | None:
    return getattr(request.state, "session", None)


# ── Endpoints ───────────────────────────────────────────────────

@router.get("/approvals/pending")
async def pending_approvals(request: Request):
    """获取当前用户的待审批列表.

    返回当前用户作为审批人的所有 pending 审批步骤,
    同时附带关联的请假记录详情.
    """
    session = _get_session(request)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})

    from src.tools.db import get_db

    with get_db() as conn:
        # 请假审批步骤
        leave_rows = conn.execute(
            """SELECT a.*, 'leave' as record_type,
                      l.user_id as applicant_id, l.leave_type,
                      l.start_date, l.end_date, l.total_days, l.reason,
                      l.status as record_status, l.created_at as record_created_at,
                      u.name as applicant_name, u.department_id as applicant_dept,
                      NULL as expense_type, NULL as amount
               FROM approval_flow a
               JOIN leave_records l ON a.record_id = l.id
               JOIN users u ON l.user_id = u.user_id
               WHERE a.approver_id = ? AND a.status = 'pending'""",
            (session.user_id,),
        ).fetchall()

        # 报销审批步骤
        expense_rows = conn.execute(
            """SELECT a.*, 'expense' as record_type,
                      e.user_id as applicant_id, NULL as leave_type,
                      NULL as start_date, NULL as end_date, NULL as total_days, e.description as reason,
                      e.status as record_status, e.created_at as record_created_at,
                      u.name as applicant_name, u.department_id as applicant_dept,
                      e.expense_type, e.amount
               FROM approval_flow a
               JOIN expense_reports e ON a.record_id = e.id
               JOIN users u ON e.user_id = u.user_id
               WHERE a.approver_id = ? AND a.status = 'pending'""",
            (session.user_id,),
        ).fetchall()

    items = []
    for r in list(leave_rows) + list(expense_rows):
        d = dict(r)
        item = {
            "step_id": d["id"],
            "step": d["step"],
            "record_id": d["record_id"],
            "record_type": d["record_type"],
            "approver_role": d["approver_role"],
            "status": d["status"],
            "created_at": d["created_at"],
            "applicant": {
                "user_id": d["applicant_id"],
                "name": d["applicant_name"],
                "department": d["applicant_dept"],
            },
        }
        if d["record_type"] == "leave":
            item["leave"] = {
                "leave_type": d["leave_type"],
                "start_date": d["start_date"],
                "end_date": d["end_date"],
                "total_days": d["total_days"],
                "reason": d["reason"],
                "status": d["record_status"],
            }
        else:
            item["expense"] = {
                "expense_type": d["expense_type"],
                "amount": d["amount"],
                "description": d["reason"],
                "status": d["record_status"],
            }
        items.append(item)

    items.sort(key=lambda x: x["created_at"], reverse=True)
    return {"pending": items, "total": len(items)}


@router.post("/approvals/{step_id}/approve")
async def approve_step(request: Request, step_id: str, body: ApproveRequest = ApproveRequest()):
    """审批通过某个审批步骤."""
    session = _get_session(request)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})

    from src.tools.db import get_db, db_get_approval_status, db_update_approval_step
    from src.workflow.state_machine import transition_approval_step, transition_leave_status

    # 验证步骤存在且属于当前审批人
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM approval_flow WHERE id = ?", (step_id,)
        ).fetchone()

    if row is None:
        return JSONResponse(status_code=404, content={"error": "审批步骤不存在"})

    step = dict(row)
    if step["approver_id"] != session.user_id:
        return JSONResponse(status_code=403, content={"error": "无权审批此步骤"})

    if step["status"] != "pending":
        return JSONResponse(status_code=400, content={"error": f"此步骤状态为 {step['status']},无法审批"})

    # FSM 校验 + 更新
    transition_approval_step(step_id, "approved")
    db_update_approval_step(step_id, "approved", body.comment)

    # 检查是否所有步骤都通过了
    record_id = step["record_id"]
    record_type = step["record_type"]
    updated = db_get_approval_status(record_type, record_id)
    all_done = all(s["status"] in ("approved", "skipped") for s in updated)

    if all_done:
        if record_type == "leave":
            transition_leave_status(record_id, "approved")
            from src.tools.db import db_deduct_leave_balance, db_create_notification
            with get_db() as conn:
                row = conn.execute(
                    "SELECT user_id, leave_type, total_days FROM leave_records WHERE id = ?",
                    (record_id,),
                ).fetchone()
            if row:
                db_deduct_leave_balance(row["user_id"], row["leave_type"], row["total_days"])
                db_create_notification(
                    row["user_id"], "approval_result",
                    f"✅ 请假申请已通过",
                    f"{row['leave_type']} {row['total_days']}天,审批人:{session.name}",
                    link_type="leave", link_id=record_id,
                )
        elif record_type == "expense":
            with get_db() as conn:
                conn.execute(
                    "UPDATE expense_reports SET status = 'approved', updated_at = datetime('now') WHERE id = ?",
                    (record_id,),
                )
                erow = conn.execute("SELECT user_id, expense_type, amount FROM expense_reports WHERE id = ?", (record_id,)).fetchone()
                conn.commit()
            if erow:
                from src.tools.db import db_create_notification
                db_create_notification(
                    erow["user_id"], "approval_result",
                    f"✅ 报销申请已通过",
                    f"{erow['expense_type']} ¥{erow['amount']},审批人:{session.name}",
                    link_type="expense", link_id=record_id,
                )

    # 发布事件
    from src.workflow.event_bus import get_event_bus
    bus = get_event_bus()
    bus.publish("approval.approved", {
        "record_id": record_id, "step_id": step_id,
        "approver_id": session.user_id, "comment": body.comment,
    })
    if all_done:
        bus.publish("approval.completed", {
            "record_id": record_id, "record_type": "leave", "all_approved": True,
        })

    return {
        "success": True,
        "step_id": step_id,
        "new_status": "approved",
        "all_approved": all_done,
        "message": "审批已通过" + (",请假已完全审批" if all_done else ""),
    }


@router.post("/approvals/{step_id}/reject")
async def reject_step(request: Request, step_id: str, body: RejectRequest = RejectRequest()):
    """驳回某个审批步骤."""
    session = _get_session(request)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})

    from src.tools.db import get_db, db_update_approval_step
    from src.workflow.state_machine import transition_approval_step, transition_leave_status

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM approval_flow WHERE id = ?", (step_id,)
        ).fetchone()

    if row is None:
        return JSONResponse(status_code=404, content={"error": "审批步骤不存在"})

    step = dict(row)
    if step["approver_id"] != session.user_id:
        return JSONResponse(status_code=403, content={"error": "无权审批此步骤"})

    if step["status"] != "pending":
        return JSONResponse(status_code=400, content={"error": f"此步骤状态为 {step['status']},无法审批"})

    # FSM 校验 + 更新
    transition_approval_step(step_id, "rejected")
    db_update_approval_step(step_id, "rejected", body.comment)

    record_type = step["record_type"]
    record_id = step["record_id"]
    if record_type == "leave":
        transition_leave_status(record_id, "rejected")
        with get_db() as conn:
            lrow = conn.execute("SELECT user_id, leave_type, total_days FROM leave_records WHERE id = ?", (record_id,)).fetchone()
        if lrow:
            from src.tools.db import db_create_notification
            db_create_notification(
                lrow["user_id"], "approval_result",
                f"❌ 请假申请已驳回",
                f"{lrow['leave_type']} {lrow['total_days']}天,理由:{body.comment or '无'}",
                link_type="leave", link_id=record_id,
            )
    elif record_type == "expense":
        with get_db() as conn:
            conn.execute(
                "UPDATE expense_reports SET status = 'rejected', updated_at = datetime('now') WHERE id = ?",
                (record_id,),
            )
            erow = conn.execute("SELECT user_id, expense_type, amount FROM expense_reports WHERE id = ?", (record_id,)).fetchone()
            conn.commit()
        if erow:
            from src.tools.db import db_create_notification
            db_create_notification(
                erow["user_id"], "approval_result",
                f"❌ 报销申请已驳回",
                f"{erow['expense_type']} ¥{erow['amount']},理由:{body.comment or '无'}",
                link_type="expense", link_id=record_id,
            )

    # 发布事件
    from src.workflow.event_bus import get_event_bus
    bus = get_event_bus()
    bus.publish("approval.rejected", {
        "record_id": step["record_id"], "step_id": step_id,
        "approver_id": session.user_id, "comment": body.comment,
    })

    return {
        "success": True,
        "step_id": step_id,
        "new_status": "rejected",
        "message": "已驳回" + (f",理由: {body.comment}" if body.comment else ""),
    }
