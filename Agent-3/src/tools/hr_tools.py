"""HR Agent 工具集 -- SQLite 持久化实现.

每个函数返回 dict,与 ToolDef.implementation 签名对齐.
"""

from __future__ import annotations

from src.tools.base import ToolDef
from src.tools.db import (
    db_get_leave_balance,
    db_submit_leave_request,
    db_get_org_chain,
    db_get_used_leave_days,
    db_create_approval_flow,
    db_get_approval_status,
    db_get_pending_approvals,
    db_update_approval_step,
    db_get_user,
    db_get_hr_approver,
    db_deduct_leave_balance,
    get_db,
)
from datetime import date as dt_date

from src.workflow.state_machine import transition_leave_status, transition_approval_step
from src.workflow.event_bus import get_event_bus

# ── 审批流构建 ─────────────────────────────────────────────────

def _build_approval_steps(user_id: str, total_days: float, chain: list[dict]) -> list[dict]:
    """根据请假天数和汇报链,构建审批步骤列表.

    Args:
        user_id: 申请人 ID
        total_days: 请假天数
        chain: 汇报链(本人 → 直属上级 → 部门负责人 → ...)

    Returns:
        [{"step": 1, "approver_id": "EMP002", "approver_role": "direct_manager"}, ...]
    """
    steps = []
    # chain[0] 是本人,chain[1] 是直属上级,chain[2] 是部门负责人
    direct_manager = chain[1] if len(chain) > 1 else None
    dept_head = None
    hr_director = None

    # 找部门负责人(跳过直属上级后的第一人,或 role 为 manager/hr 的)
    for node in chain[2:]:
        if node["role"] in ("manager", "hr"):
            dept_head = node
            break
    if dept_head is None:
        dept_head = chain[2] if len(chain) > 2 else None

    hr_director = db_get_hr_approver()

    if direct_manager:
        steps.append({
            "step": 1,
            "approver_id": direct_manager["user_id"],
            "approver_role": "direct_manager",
        })

    if total_days > 3 and dept_head:
        mgr_id = direct_manager["user_id"] if direct_manager else None
        if dept_head["user_id"] != mgr_id:
            steps.append({
                "step": len(steps) + 1,
                "approver_id": dept_head["user_id"],
                "approver_role": "dept_head",
            })

    if total_days > 7 and hr_director:
        # 避免重复(如果 HR 已经是前两步的审批人)
        existing_ids = {s["approver_id"] for s in steps}
        if hr_director["user_id"] not in existing_ids:
            steps.append({
                "step": len(steps) + 1,
                "approver_id": hr_director["user_id"],
                "approver_role": "hr",
            })

    return steps

# ── 工具实现 ─────────────────────────────────────────────────────

def get_leave_balance(user_id: str) -> dict:
    """查询员工的年假,病假和事假剩余天数.

    Args:
        user_id: 员工ID.

    Returns:
        各类假期剩余天数.
    """
    balance = db_get_leave_balance(user_id)
    if balance is None:
        return {"error": f"未找到员工 {user_id} 的假期记录"}
    return balance


def submit_leave_request(
    user_id: str,
    leave_type: str,
    start_date: str,
    end_date: str,
    reason: str = "",
) -> dict:
    """提交请假申请.

    Args:
        user_id: 员工ID.
        leave_type: 假期类型(年假/病假/事假).
        start_date: 开始日期 YYYY-MM-DD.
        end_date: 结束日期 YYYY-MM-DD.
        reason: 请假原因(可选).

    Returns:
        申请结果.
    """
    # 校验员工是否存在
    if db_get_leave_balance(user_id) is None:
        return {"error": f"未找到员工 {user_id} 的记录"}

    valid_types = {"年假", "病假", "事假"}
    if leave_type not in valid_types:
        return {"error": f"无效的假期类型: {leave_type},可选: {', '.join(valid_types)}"}

    # 检查余额
    from datetime import date as _dt
    try:
        s = _dt.fromisoformat(start_date)
        e = _dt.fromisoformat(end_date)
        total_days_check = (e - s).days + 1
    except (ValueError, TypeError):
        return {"error": "日期格式无效,请使用 YYYY-MM-DD"}
    if total_days_check <= 0:
        return {"error": "结束日期必须晚于或等于开始日期"}

    balance = db_get_leave_balance(user_id)
    leave_key = {"年假": "annual", "病假": "sick", "事假": "personal"}[leave_type]
    remaining = balance.get(leave_key, 0)
    if remaining < total_days_check:
        return {"error": f"{leave_type}余额不足,剩余 {remaining} 天,申请 {total_days_check} 天"}

    record = db_submit_leave_request(user_id, leave_type, start_date, end_date, reason)
    total_days = record["total_days"]
    record_id = record["id"]

    # ── 自动创建审批流 ──────────────────────────────────────
    chain = db_get_org_chain(user_id)
    # 确定审批步骤(按请假天数分级)
    # ≤3 天:直属上级
    # ≤7 天:直属上级 + 部门负责人
    # >7 天:直属上级 + 部门负责人 + HR 总监
    steps = _build_approval_steps(user_id, total_days, chain)
    if steps:
        db_create_approval_flow("leave", record_id, steps)
        approver_id = steps[0]["approver_id"]
    else:
        approver_id = None

    # 发布事件
    bus = get_event_bus()
    bus.publish("leave.submitted", {
        "record_id": record_id, "user_id": user_id,
        "leave_type": leave_type, "days": total_days,
        "approver_id": approver_id,
    })

    return {
        "success": True,
        "request_id": record_id,
        "message": f"{leave_type}申请已提交,等待审批",
        "approval_steps": len(steps) if steps else 0,
    }


def get_org_chain(user_id: str) -> dict:
    """获取用户的汇报链.

    Args:
        user_id: 员工ID.

    Returns:
        汇报链(本人→直属上级→部门负责人→...).
    """
    chain = db_get_org_chain(user_id)
    if not chain:
        return {"error": f"未找到员工 {user_id} 的组织信息"}
    return {
        "user_id": user_id,
        "chain": [{"user_id": n["user_id"], "name": n["name"], "role": n["role"]} for n in chain],
        "direct_manager": chain[1]["name"] if len(chain) > 1 else None,
    }


def check_policy(user_id: str, leave_type: str, start_date: str, end_date: str) -> dict:
    """请假前的制度合规检查.

    Args:
        user_id: 员工ID
        leave_type: 假期类型(年假/病假/事假)
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
    """
    user = db_get_user(user_id)
    if user is None:
        return {"error": f"未找到员工 {user_id}"}

    # 计算请假天数
    try:
        s = dt_date.fromisoformat(start_date)
        e = dt_date.fromisoformat(end_date)
        total_days = (e - s).days + 1
    except (ValueError, TypeError):
        return {"error": "日期格式无效,请使用 YYYY-MM-DD"}

    balance = db_get_leave_balance(user_id)
    if balance is None:
        return {"error": f"未找到员工 {user_id} 的假期记录"}

    leave_key = {"年假": "annual", "病假": "sick", "事假": "personal"}.get(leave_type)
    if leave_key is None:
        return {"error": f"无效的假期类型: {leave_type}"}

    remaining = balance.get(leave_key, 0)
    enough = remaining >= total_days

    # 确定审批级别
    if total_days <= 3:
        approval_level = "一级(直属上级)"
    elif total_days <= 7:
        approval_level = "二级(直属上级 + 部门总监)"
    else:
        approval_level = "三级(部门总监 + HR总监)"

    return {
        "allowed": enough,
        "leave_type": leave_type,
        "requested_days": total_days,
        "remaining_days": remaining,
        "remaining_after": remaining - total_days if enough else remaining,
        "approval_level": approval_level,
        "user_info": {
            "name": user.get("name"),
            "department": user.get("department_name"),
            "role": user.get("role"),
        },
    }


def approve_leave(record_id: str, approver_id: str, comment: str = "") -> dict:
    """审批通过某个请假申请的审批步骤.

    自动找到当前待审批的步骤中属于此审批人的第一条.

    Args:
        record_id: 请假记录 ID (leave_records.id)
        approver_id: 审批人 ID
        comment: 审批意见
    """
    steps = db_get_approval_status("leave", record_id)
    if not steps:
        return {"error": f"未找到请假记录 {record_id} 的审批流"}

    # 找到属于此审批人的第一个 pending 步骤
    target = None
    for s in steps:
        if s["approver_id"] == approver_id and s["status"] == "pending":
            target = s
            break

    if target is None:
        return {"error": f"审批人 {approver_id} 没有待审批的步骤"}

    # FSM 校验 + 更新
    transition_approval_step(target["id"], "approved")
    db_update_approval_step(target["id"], "approved", comment)

    # 检查是否所有步骤都通过了
    updated = db_get_approval_status("leave", record_id)
    all_done = all(s["status"] in ("approved", "skipped") for s in updated)

    if all_done:
        transition_leave_status(record_id, "approved")
        # 扣减假期余额
        with get_db() as conn:
            row = conn.execute(
                "SELECT user_id, leave_type, total_days FROM leave_records WHERE id = ?",
                (record_id,),
            ).fetchone()
        if row:
            db_deduct_leave_balance(row["user_id"], row["leave_type"], row["total_days"])

    # 发布事件
    bus = get_event_bus()
    bus.publish("approval.approved", {
        "record_id": record_id, "step_id": target["id"],
        "approver_id": approver_id, "comment": comment,
    })
    if all_done:
        bus.publish("approval.completed", {
            "record_id": record_id, "record_type": "leave", "all_approved": True,
        })

    return {
        "success": True,
        "step_id": target["id"],
        "step_number": target["step"],
        "new_status": "approved",
        "all_approved": all_done,
        "message": f"审批步骤 {target['step']} 已通过" + (",请假已完全审批" if all_done else ""),
    }


def reject_leave(record_id: str, approver_id: str, comment: str = "") -> dict:
    """驳回某个请假申请.

    Args:
        record_id: 请假记录 ID
        approver_id: 审批人 ID
        comment: 驳回理由
    """
    steps = db_get_approval_status("leave", record_id)
    if not steps:
        return {"error": f"未找到请假记录 {record_id} 的审批流"}

    target = None
    for s in steps:
        if s["approver_id"] == approver_id and s["status"] == "pending":
            target = s
            break

    if target is None:
        return {"error": f"审批人 {approver_id} 没有待审批的步骤"}

    # FSM 校验 + 更新
    transition_approval_step(target["id"], "rejected")
    db_update_approval_step(target["id"], "rejected", comment)
    transition_leave_status(record_id, "rejected")

    # 发布事件
    bus = get_event_bus()
    bus.publish("approval.rejected", {
        "record_id": record_id, "step_id": target["id"],
        "approver_id": approver_id, "comment": comment,
    })

    return {
        "success": True,
        "step_id": target["id"],
        "new_status": "rejected",
        "message": f"请假申请 {record_id} 已被驳回,理由: {comment or '无'}",
    }


def get_approval_progress(record_id: str) -> dict:
    """查询某个请假申请的审批进度.

    Args:
        record_id: 请假记录 ID
    """
    steps = db_get_approval_status("leave", record_id)
    if not steps:
        return {"error": f"未找到请假记录 {record_id} 的审批流"}

    progress = []
    for s in steps:
        progress.append({
            "step": s["step"],
            "approver": s["approver_name"],
            "role": s["approver_role"],
            "status": s["status"],
            "comment": s.get("comment"),
            "decided_at": s.get("decided_at"),
        })

    return {
        "record_id": record_id,
        "total_steps": len(progress),
        "completed": sum(1 for p in progress if p["status"] != "pending"),
        "steps": progress,
    }


def get_pending_approvals(approver_id: str) -> dict:
    """查询某审批人的待审批列表.

    Args:
        approver_id: 审批人 ID

    Returns:
        待审批的请假列表,含申请人信息和请假详情.
    """
    rows = db_get_pending_approvals(approver_id)
    if not rows:
        return {"pending": [], "total": 0, "message": "暂无待审批项"}

    items = []
    for r in rows:
        items.append({
            "step_id": r["id"],
            "step": r["step"],
            "record_id": r["record_id"],
            "approver_role": r["approver_role"],
            "status": r["status"],
            "created_at": r["created_at"],
            "applicant": {
                "user_id": r["applicant_id"],
                "name": r["applicant_name"],
                "department": r["applicant_dept"],
            },
            "leave": {
                "leave_type": r["leave_type"],
                "start_date": r["start_date"],
                "end_date": r["end_date"],
                "total_days": r["total_days"],
                "reason": r["reason"],
                "status": r["leave_status"],
            },
        })

    return {"pending": items, "total": len(items)}


# ── 工具列表 ─────────────────────────────────────────────────────

HR_TOOLS: list[ToolDef] = [
    ToolDef(
        name="get_leave_balance",
        description=(
            "查询员工的年假,病假和事假剩余天数."
            "输入员工ID,返回各类假期剩余天数."
        ),
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "员工ID",
                },
            },
            "required": ["user_id"],
        },
        implementation=get_leave_balance,
        quick_triggers=["年假", "病假", "事假", "假期", "假"],
        quick_args_builder=lambda ctx: {"user_id": ctx.user_id},
    ),
    ToolDef(
        name="submit_leave_request",
        description=(
            "提交请假申请.需要提供员工ID,假期类型(年假/病假/事假),"
            "开始和结束日期,请假原因."
        ),
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "员工ID",
                },
                "leave_type": {
                    "type": "string",
                    "description": "假期类型: 年假, 病假, 事假",
                    "enum": ["年假", "病假", "事假"],
                },
                "start_date": {
                    "type": "string",
                    "description": "开始日期 YYYY-MM-DD",
                },
                "end_date": {
                    "type": "string",
                    "description": "结束日期 YYYY-MM-DD",
                },
                "reason": {
                    "type": "string",
                    "description": "请假原因",
                },
            },
            "required": ["user_id", "leave_type", "start_date", "end_date"],
        },
        implementation=submit_leave_request,
        permission={"roles": ["employee", "manager", "hr"], "scope": "self"},
    ),
    ToolDef(
        name="get_org_chain",
        description="获取员工的汇报链,从本人到直属上级再到部门负责人.输入员工ID.",
        parameters={
            "type": "object",
            "properties": {"user_id": {"type": "string", "description": "员工ID"}},
            "required": ["user_id"],
        },
        implementation=get_org_chain,
        permission={"roles": ["employee", "manager", "hr"], "scope": "self"},
    ),
    ToolDef(
        name="check_policy",
        description="请假前检查:余额是否够,需要几级审批.输入员工ID,假期类型,起止日期.",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "员工ID"},
                "leave_type": {"type": "string", "enum": ["年假", "病假", "事假"]},
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["user_id", "leave_type", "start_date", "end_date"],
        },
        implementation=check_policy,
        permission={"roles": ["employee", "manager", "hr"], "scope": "self"},
    ),
    ToolDef(
        name="approve_leave",
        description="审批通过请假申请.需要请假记录ID和审批人ID.仅manager/hr可用.",
        parameters={
            "type": "object",
            "properties": {
                "record_id": {"type": "string", "description": "请假记录ID"},
                "approver_id": {"type": "string", "description": "审批人ID"},
                "comment": {"type": "string", "description": "审批意见"},
            },
            "required": ["record_id", "approver_id"],
        },
        implementation=approve_leave,
        permission={"roles": ["manager", "hr"], "scope": "department"},
    ),
    ToolDef(
        name="reject_leave",
        description="驳回请假申请.需要请假记录ID,审批人ID,驳回理由.仅manager/hr可用.",
        parameters={
            "type": "object",
            "properties": {
                "record_id": {"type": "string", "description": "请假记录ID"},
                "approver_id": {"type": "string", "description": "审批人ID"},
                "comment": {"type": "string", "description": "驳回理由"},
            },
            "required": ["record_id", "approver_id"],
        },
        implementation=reject_leave,
        permission={"roles": ["manager", "hr"], "scope": "department"},
    ),
    ToolDef(
        name="get_approval_progress",
        description="查询请假申请的审批进度.输入请假记录ID,返回各审批步骤状态.",
        parameters={
            "type": "object",
            "properties": {"record_id": {"type": "string", "description": "请假记录ID"}},
            "required": ["record_id"],
        },
        implementation=get_approval_progress,
        permission={"roles": ["employee", "manager", "hr"], "scope": "self"},
    ),
    ToolDef(
        name="get_pending_approvals",
        description=(
            "查询某审批人的所有待审批请假列表."
            "输入审批人ID,返回该审批人需要审批的所有请假申请,"
            "包含申请人信息,请假详情和审批步骤."
        ),
        parameters={
            "type": "object",
            "properties": {
                "approver_id": {
                    "type": "string",
                    "description": "审批人ID,如 EMP002",
                },
            },
            "required": ["approver_id"],
        },
        implementation=get_pending_approvals,
        permission={"roles": ["manager", "hr"], "scope": "department"},
        quick_triggers=["待审批", "审批列表", "审批"],
        quick_args_builder=lambda ctx: {"approver_id": ctx.user_id},
    ),
]
