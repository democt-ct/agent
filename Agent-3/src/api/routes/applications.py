"""Applications REST API -- 统一申请记录查询与 CRUD.

端点:
    GET    /api/applications                      -- 当前用户的所有申请记录
    GET    /api/applications/{app_type}/{app_id}  -- 单条申请详情
    PUT    /api/applications/{app_type}/{app_id}  -- 编辑申请
    DELETE /api/applications/{app_type}/{app_id}  -- 删除申请
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.gateway.auth import SessionContext
from src.tools.db import (
    db_get_my_applications,
    db_get_application,
    db_update_application,
    db_delete_application,
    db_update_status,
)

router = APIRouter(tags=["applications"])

STATUS_MAP = {
    "pending": "待审批", "approved": "已通过", "rejected": "已驳回",
    "draft": "草稿", "cancelled": "已取消", "completed": "已完成",
    "待处理": "待处理", "处理中": "处理中", "已完成": "已完成",
    "reimbursed": "已报销",
}


def _get_session(request: Request) -> SessionContext | None:
    return getattr(request.state, "session", None)


def _format_app(r: dict) -> dict:
    raw_status = r.get("status", "")
    return {
        "app_type": r.get("app_type"),
        "app_type_label": r.get("app_type_label"),
        "id": r.get("id"),
        "subtype": r.get("subtype"),
        "start_date": r.get("start_date"),
        "end_date": r.get("end_date"),
        "amount": r.get("amount_val"),
        "description": r.get("description"),
        "status": raw_status,
        "status_label": STATUS_MAP.get(raw_status, raw_status),
        "created_at": r.get("created_at"),
    }


# ── 可编辑字段定义 ──────────────────────────────────────────────

_EDITABLE_FIELDS = {
    "leave": ["leave_type", "start_date", "end_date", "reason"],
    "ticket": ["issue_type", "description", "priority"],
    "expense": ["expense_type", "amount", "description"],
}

_LEAVE_TYPES = ["年假", "病假", "事假"]
_TICKET_TYPES = ["硬件报修", "软件安装", "网络问题", "账号问题", "其他"]
_EXPENSE_TYPES = ["差旅", "办公", "招待", "培训", "其他"]
_TICKET_PRIORITIES = ["高", "中", "低"]


class UpdateApplicationRequest(BaseModel):
    leave_type: str | None = Field(default=None, description="假期类型")
    start_date: str | None = Field(default=None, description="开始日期 YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="结束日期 YYYY-MM-DD")
    reason: str | None = Field(default=None, description="原因/说明")
    issue_type: str | None = Field(default=None, description="问题类型")
    description: str | None = Field(default=None, description="问题描述")
    priority: str | None = Field(default=None, description="优先级")
    expense_type: str | None = Field(default=None, description="报销类型")
    amount: float | None = Field(default=None, description="金额")


# ── 列表 ──────────────────────────────────────────────────────────

@router.get("/applications")
async def list_applications(request: Request):
    """获取当前用户的所有申请记录(请假 + IT工单 + 报销)."""
    session = _get_session(request)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})

    type_filter = request.query_params.get("type", "").strip()
    status_filter = request.query_params.get("status", "").strip()

    rows = db_get_my_applications(session.user_id, limit=100)
    if type_filter:
        rows = [r for r in rows if r.get("app_type") == type_filter]
    if status_filter:
        rows = [r for r in rows if r.get("status") == status_filter]

    return {
        "user_id": session.user_id,
        "total": len(rows),
        "applications": [_format_app(r) for r in rows],
    }


# ── 详情 ──────────────────────────────────────────────────────────

@router.get("/applications/{app_type}/{app_id}")
async def get_application(request: Request, app_type: str, app_id: str):
    """获取单条申请记录详情."""
    session = _get_session(request)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})

    if app_type not in ("leave", "ticket", "expense"):
        return JSONResponse(status_code=400, content={"error": f"无效的申请类型: {app_type}"})

    row = db_get_application(app_type, app_id)
    if row is None:
        return JSONResponse(status_code=404, content={"error": "申请记录不存在"})

    # 权限检查:申请人自己,部门经理,HR,admin 可查看
    allowed = False
    if row.get("user_id") == session.user_id:
        allowed = True
    elif session.role in ("hr", "admin", "manager"):
        allowed = True
    # 如果是工单且当前用户是 assigned_to,也允许
    elif app_type == "ticket" and row.get("assigned_to") and session.name and row.get("assigned_to") == session.name:
        allowed = True

    if not allowed:
        return JSONResponse(status_code=403, content={"error": "无权查看此记录"})

    editable_fields = _EDITABLE_FIELDS.get(app_type, [])
    can_edit = row.get("status") in ("draft", "pending", "待处理")
    can_delete = row.get("status") in ("draft", "pending", "待处理")

    return {
        "application": dict(row),
        "meta": {
            "app_type": app_type,
            "editable_fields": editable_fields,
            "can_edit": can_edit,
            "can_delete": can_delete,
        },
    }


# ── 状态切换 ──────────────────────────────────────────────────────

@router.patch("/applications/{app_type}/{app_id}/status")
async def update_application_status(request: Request, app_type: str, app_id: str):
    """更新申请状态(如标记工单为已完成)."""
    session = _get_session(request)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})

    body = await request.json()
    new_status = body.get("status", "")
    if not new_status:
        return JSONResponse(status_code=400, content={"error": "缺少 status 字段"})

    row = db_get_application(app_type, app_id)
    if row is None:
        return JSONResponse(status_code=404, content={"error": "申请记录不存在"})

    # 权限:申请人自己,manager,hr,admin 可操作
    allowed = row.get("user_id") == session.user_id or session.role in ("hr", "admin", "manager")
    if not allowed:
        return JSONResponse(status_code=403, content={"error": "无权操作"})

    # 状态流转规则
    current = row.get("status", "")
    if app_type == "ticket":
        valid_transitions = {"待处理": "已完成", "处理中": "已完成"}
        if current not in valid_transitions:
            return JSONResponse(status_code=400, content={"error": f"当前状态 '{current}' 不可变更"})
        if new_status != valid_transitions[current]:
            return JSONResponse(status_code=400,
                content={"error": f"只能从 '{current}' 变更为 '{valid_transitions[current]}'"})
    elif app_type == "leave":
        if new_status != "cancelled":
            return JSONResponse(status_code=400, content={"error": "请假只能取消"})
        if current not in ("draft", "pending"):
            return JSONResponse(status_code=400, content={"error": f"当前状态 '{current}' 不可取消"})
    else:
        return JSONResponse(status_code=400, content={"error": f"不支持的类型: {app_type}"})

    ok = db_update_status(app_type, app_id, new_status)
    if not ok:
        return JSONResponse(status_code=500, content={"error": "更新失败"})

    return {"success": True, "app_type": app_type, "app_id": app_id, "status": new_status}


# ── 编辑 ──────────────────────────────────────────────────────────

@router.put("/applications/{app_type}/{app_id}")
async def update_application(request: Request, app_type: str, app_id: str, body: UpdateApplicationRequest):
    """编辑申请记录.仅 draft/pending/待处理 状态可编辑."""
    session = _get_session(request)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})

    if app_type not in ("leave", "ticket", "expense"):
        return JSONResponse(status_code=400, content={"error": f"无效的申请类型: {app_type}"})

    # 权限检查
    row = db_get_application(app_type, app_id)
    if row is None:
        return JSONResponse(status_code=404, content={"error": "申请记录不存在"})
    if row.get("user_id") != session.user_id:
        return JSONResponse(status_code=403, content={"error": "只能编辑自己的申请"})

    # 校验状态
    if row.get("status") not in ("draft", "pending", "待处理"):
        return JSONResponse(status_code=400, content={"error": "当前状态不可编辑"})

    # 构建更新字段(按类型提取非 None 字段)
    updates = {}
    field_map = {
        "leave_type": "leave_type", "start_date": "start_date",
        "end_date": "end_date", "reason": "reason",
        "issue_type": "issue_type", "description": "description",
        "priority": "priority", "expense_type": "expense_type", "amount": "amount",
    }
    for body_field, db_field in field_map.items():
        val = getattr(body, body_field, None)
        if val is not None:
            # 基本校验
            if body_field == "leave_type" and val not in _LEAVE_TYPES:
                return JSONResponse(status_code=400, content={"error": f"无效假期类型: {val}"})
            if body_field == "issue_type" and val not in _TICKET_TYPES:
                return JSONResponse(status_code=400, content={"error": f"无效问题类型: {val}"})
            if body_field == "priority" and val not in _TICKET_PRIORITIES:
                return JSONResponse(status_code=400, content={"error": f"无效优先级: {val}"})
            if body_field == "expense_type" and val not in _EXPENSE_TYPES:
                return JSONResponse(status_code=400, content={"error": f"无效报销类型: {val}"})
            if body_field == "amount" and val <= 0:
                return JSONResponse(status_code=400, content={"error": "金额必须大于0"})
            updates[db_field] = val

    if not updates:
        return JSONResponse(status_code=400, content={"error": "没有要更新的字段"})

    ok = db_update_application(app_type, app_id, updates)
    if not ok:
        return JSONResponse(status_code=500, content={"error": "更新失败"})

    # 返回更新后的记录
    updated = db_get_application(app_type, app_id)
    return {
        "success": True,
        "message": "申请已更新",
        "application": dict(updated) if updated else None,
    }


# ── 删除 ──────────────────────────────────────────────────────────

@router.delete("/applications/{app_type}/{app_id}")
async def delete_application(request: Request, app_type: str, app_id: str):
    """删除申请记录.仅 draft/pending/待处理 状态可删除."""
    session = _get_session(request)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})

    if app_type not in ("leave", "ticket", "expense"):
        return JSONResponse(status_code=400, content={"error": f"无效的申请类型: {app_type}"})

    # 权限检查
    row = db_get_application(app_type, app_id)
    if row is None:
        return JSONResponse(status_code=404, content={"error": "申请记录不存在"})
    if row.get("user_id") != session.user_id and session.role not in ("hr", "admin", "manager"):
        return JSONResponse(status_code=403, content={"error": "只能删除自己的申请"})

    ok = db_delete_application(app_type, app_id)
    if not ok:
        return JSONResponse(status_code=400, content={"error": "删除失败,当前状态不可删除"})

    return {"success": True, "message": "申请已删除"}
