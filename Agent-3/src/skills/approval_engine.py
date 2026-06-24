"""通用审批引擎 -- 请假/报销/设备申领等所有审批流程的统一入口.

从 hr_tools.py 和 finance_tools.py 中提取通用审批逻辑,提供:
  - build_approval_chain() -- 按金额/天数自动确定审批链
  - submit_for_approval() -- 提交审批 + 创建审批流 + 发通知
  - approve_step() -- 通过当前步骤(自动推进或完成)
  - reject_step() -- 驳回(整条记录驳回)
  - get_approval_status() -- 查看审批进度
  - get_pending_approvals() -- 某人待审批列表

审批层级规则:
  请假:
    ≤3 天: 直属上级 (1 级)
    ≤7 天: 直属上级 + 部门负责人 (2 级)
    >7 天: 直属上级 + 部门负责人 + HR 总监 (3 级)
  报销:
    <5000 元: 直属上级 (1 级)
    ≥5000 元: 直属上级 + 财务经理 (2 级)

Usage:
    from src.skills.approval_engine import submit_for_approval, approve_step

    # 提交审批
    result = submit_for_approval(
        record_type="leave", record_id="abc123",
        user_id="EMP001", total_days=5,
    )
    # 审批通过
    result = approve_step(step_id="xyz789", approver_id="EMP002", comment="同意")
"""

from __future__ import annotations

import logging
from typing import Any

from src.tools.db import (
    get_db, _uid, _now,
    db_get_leave_balance, db_get_user, db_get_org_chain,
    db_get_hr_approver, db_get_finance_approver,
    db_get_approval_status, db_get_pending_approvals,
    db_create_approval_flow, db_update_approval_step,
    db_deduct_leave_balance,
)
from src.workflow.state_machine import transition_leave_status, transition_approval_step
from src.workflow.event_bus import get_event_bus
from src.skills.notification import send_notification

logger = logging.getLogger(__name__)

# ── 审批规则配置 ──────────────────────────────────────────────────

# 请假审批层级规则
LEAVE_APPROVAL_RULES = [
    # (最大天数, 审批角色, 角色标签)
    (3,   "direct_manager", "直属上级"),
    (7,   "dept_head",      "部门负责人"),
    (float("inf"), "hr",     "HR 总监"),
]

# 报销审批层级规则
EXPENSE_APPROVAL_RULES = [
    # (最大金额, 审批角色, 角色标签)
    (5000,         "direct_manager", "直属上级"),
    (float("inf"), "finance",        "财务经理"),
]

# 审批类型 → 通知标题模板
_NOTIFY_TEMPLATES = {
    "leave": {
        "submitted": "请假申请已提交",
        "approved_step": "请假审批通过(步骤 {step})",
        "approved_all": "请假申请已通过",
        "rejected": "请假申请已驳回",
    },
    "expense": {
        "submitted": "报销申请已提交",
        "approved_step": "报销审批通过(步骤 {step})",
        "approved_all": "报销申请已通过",
        "rejected": "报销申请已驳回",
    },
}


def _get_approval_rules(record_type: str) -> list[tuple]:
    """获取某类记录的审批规则."""
    if record_type == "leave":
        return LEAVE_APPROVAL_RULES
    if record_type == "expense":
        return EXPENSE_APPROVAL_RULES
    # 默认:单级直属上级
    return [(float("inf"), "direct_manager", "直属上级")]


def _get_record_user_id(record_type: str, record_id: str) -> str | None:
    """获取审批记录对应的申请人 ID."""
    with get_db() as conn:
        if record_type == "leave":
            row = conn.execute(
                "SELECT user_id FROM leave_records WHERE id = ?", (record_id,)
            ).fetchone()
        elif record_type == "expense":
            row = conn.execute(
                "SELECT user_id FROM expense_reports WHERE id = ?", (record_id,)
            ).fetchone()
        else:
            return None
    return row["user_id"] if row else None


# ── 公共 API ──────────────────────────────────────────────────────


def build_approval_chain(
    record_type: str,
    user_id: str,
    threshold_value: float,
    chain: list[dict] | None = None,
) -> list[dict]:
    """根据审批规则和汇报链,构建审批步骤列表.

    Args:
        record_type: 记录类型: leave | expense
        user_id: 申请人 ID
        threshold_value: 阈值(请假天数 / 报销金额)
        chain: 汇报链(可选,不传则自动查询)

    Returns:
        [{"step": 1, "approver_id": "EMP002", "approver_role": "direct_manager"}, ...]
    """
    if chain is None:
        chain = db_get_org_chain(user_id)

    rules = _get_approval_rules(record_type)
    steps: list[dict] = []
    existing_ids: set[str] = set()

    # chain[0] 是本人,chain[1] 是直属上级
    direct_manager = chain[1] if len(chain) > 1 else None

    for max_val, role, _label in rules:
        if threshold_value <= max_val:
            approver = _resolve_approver(role, chain, direct_manager)
            if approver and approver["user_id"] not in existing_ids:
                steps.append({
                    "step": len(steps) + 1,
                    "approver_id": approver["user_id"],
                    "approver_role": role,
                })
                existing_ids.add(approver["user_id"])
            break  # 命中第一档规则即停止
        else:
            approver = _resolve_approver(role, chain, direct_manager)
            if approver and approver["user_id"] not in existing_ids:
                steps.append({
                    "step": len(steps) + 1,
                    "approver_id": approver["user_id"],
                    "approver_role": role,
                })
                existing_ids.add(approver["user_id"])

    return steps


def _resolve_approver(role: str, chain: list[dict], direct_manager: dict | None) -> dict | None:
    """根据角色找到对应审批人."""
    if role == "direct_manager":
        return direct_manager

    if role == "dept_head":
        # 跳过直属上级后的第一个 manager/hr
        skip = direct_manager["user_id"] if direct_manager else None
        for node in chain[2:]:
            if node["role"] in ("manager", "hr"):
                if skip and node["user_id"] == skip:
                    continue
                return node
        # 回退: chain[2]
        return chain[2] if len(chain) > 2 else None

    if role == "hr":
        return db_get_hr_approver()

    if role == "finance":
        return db_get_finance_approver()

    return None


def submit_for_approval(
    record_type: str,
    record_id: str,
    user_id: str,
    threshold_value: float,
    extra: dict[str, Any] | None = None,
) -> dict:
    """提交审批 -- 自动构建审批链 + 创建审批步骤 + 通知第一位审批人.

    Args:
        record_type: 记录类型: leave | expense
        record_id: 关联记录 ID
        user_id: 申请人 ID
        threshold_value: 阈值(请假天数 / 报销金额)
        extra: 额外信息(leave_type / expense_type / description 等)

    Returns:
        {"success": True, "steps_count": N, "first_approver": "EMP002", ...}
    """
    chain = db_get_org_chain(user_id)
    steps = build_approval_chain(record_type, user_id, threshold_value, chain)

    if not steps:
        return {
            "success": True,
            "steps_count": 0,
            "message": "无需审批(未找到审批人)",
        }

    # 创建审批流记录
    created = db_create_approval_flow(record_type, record_id, steps)

    # 通知第一位审批人
    first_approver = steps[0]["approver_id"]
    templates = _NOTIFY_TEMPLATES.get(record_type, _NOTIFY_TEMPLATES["leave"])
    applicant = db_get_user(user_id)
    applicant_name = applicant["name"] if applicant else user_id

    send_notification(
        user_id=first_approver,
        type_="pending_approval",
        title=f"新的{_record_label(record_type)}待审批",
        body=f"{applicant_name} 提交了{_record_label(record_type)}申请" +
             (f",共 {threshold_value} 天" if record_type == "leave" else f",金额 ¥{threshold_value:,.0f}"),
        link_type=record_type,
        link_id=record_id,
    )

    # 通知申请人
    send_notification(
        user_id=user_id,
        type_="system",
        title=templates["submitted"],
        body=f"你的{_record_label(record_type)}申请已提交,共 {len(steps)} 级审批",
        link_type=record_type,
        link_id=record_id,
    )

    # 发布事件
    bus = get_event_bus()
    bus.publish(f"{record_type}.submitted", {
        "record_id": record_id,
        "user_id": user_id,
        "approver_id": first_approver,
        **(extra or {}),
    })

    return {
        "success": True,
        "record_type": record_type,
        "record_id": record_id,
        "steps_count": len(steps),
        "first_approver": first_approver,
        "message": f"{_record_label(record_type)}申请已提交,共 {len(steps)} 级审批",
    }


def approve_step(step_id: str, approver_id: str, comment: str = "") -> dict:
    """审批通过某个审批步骤.

    自动推进:如果所有步骤都已通过,则更新主记录状态 + 扣减/执行.

    Args:
        step_id: 审批步骤 ID (approval_flow.id)
        approver_id: 审批人 ID
        comment: 审批意见

    Returns:
        审批结果,含 all_approved 标识.
    """
    # 查找步骤
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM approval_flow WHERE id = ?", (step_id,)
        ).fetchone()
    if row is None:
        return {"error": f"未找到审批步骤 {step_id}"}

    step = dict(row)
    if step["status"] != "pending":
        return {"error": f"步骤 {step_id} 当前状态为 '{step['status']}',不可审批"}

    if step["approver_id"] != approver_id:
        return {"error": f"审批人身份不匹配: 步骤属于 {step['approver_id']},当前 {approver_id}"}

    # FSM 校验 + 更新
    transition_approval_step(step_id, "approved")
    db_update_approval_step(step_id, "approved", comment)

    # 检查是否所有步骤都通过了
    all_steps = db_get_approval_status(step["record_type"], step["record_id"])
    all_done = all(s["status"] in ("approved", "skipped") for s in all_steps)

    record_type = step["record_type"]
    record_id = step["record_id"]
    templates = _NOTIFY_TEMPLATES.get(record_type, _NOTIFY_TEMPLATES["leave"])

    if all_done:
        # 更新主记录状态
        _finalize_record(record_type, record_id)

        # 通知申请人
        user_id = _get_record_user_id(record_type, record_id)
        if user_id:
            send_notification(
                user_id=user_id,
                type_="approval_result",
                title=templates["approved_all"],
                body=f"你的{_record_label(record_type)}申请已全部审批通过",
                link_type=record_type,
                link_id=record_id,
            )

        bus = get_event_bus()
        bus.publish("approval.completed", {
            "record_id": record_id,
            "record_type": record_type,
            "all_approved": True,
        })
    else:
        # 通知下一位审批人
        next_step = next((s for s in all_steps if s["status"] == "pending"), None)
        if next_step:
            send_notification(
                user_id=next_step["approver_id"],
                type_="pending_approval",
                title=f"新的{_record_label(record_type)}待审批",
                body=f"上一级已审批通过,请处理",
                link_type=record_type,
                link_id=record_id,
            )

    bus = get_event_bus()
    bus.publish("approval.approved", {
        "record_id": record_id,
        "step_id": step_id,
        "approver_id": approver_id,
        "comment": comment,
    })

    return {
        "success": True,
        "step_id": step_id,
        "step_number": step["step"],
        "record_type": record_type,
        "record_id": record_id,
        "new_status": "approved",
        "all_approved": all_done,
        "message": (
            f"审批步骤 {step['step']}/{len(all_steps)} 已通过"
            + (",申请已完全审批" if all_done else f",等待下一级审批")
        ),
    }


def reject_step(step_id: str, approver_id: str, comment: str = "") -> dict:
    """驳回某个审批步骤 -- 整条记录被驳回.

    Args:
        step_id: 审批步骤 ID
        approver_id: 审批人 ID
        comment: 驳回理由

    Returns:
        驳回结果.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM approval_flow WHERE id = ?", (step_id,)
        ).fetchone()
    if row is None:
        return {"error": f"未找到审批步骤 {step_id}"}

    step = dict(row)
    if step["status"] != "pending":
        return {"error": f"步骤 {step_id} 当前状态为 '{step['status']}',不可审批"}

    if step["approver_id"] != approver_id:
        return {"error": f"审批人身份不匹配"}

    # FSM 校验 + 更新
    transition_approval_step(step_id, "rejected")
    db_update_approval_step(step_id, "rejected", comment)

    record_type = step["record_type"]
    record_id = step["record_id"]

    # 驳回主记录
    _reject_record(record_type, record_id)

    # 通知申请人
    user_id = _get_record_user_id(record_type, record_id)
    templates = _NOTIFY_TEMPLATES.get(record_type, _NOTIFY_TEMPLATES["leave"])
    if user_id:
        reason_text = f",理由: {comment}" if comment else ""
        send_notification(
            user_id=user_id,
            type_="approval_result",
            title=templates["rejected"],
            body=f"你的{_record_label(record_type)}申请已被驳回{reason_text}",
            link_type=record_type,
            link_id=record_id,
        )

    bus = get_event_bus()
    bus.publish("approval.rejected", {
        "record_id": record_id,
        "step_id": step_id,
        "approver_id": approver_id,
        "comment": comment,
    })

    return {
        "success": True,
        "step_id": step_id,
        "step_number": step["step"],
        "record_type": record_type,
        "record_id": record_id,
        "new_status": "rejected",
        "message": f"{_record_label(record_type)}申请已被驳回",
    }


def get_approval_status(record_type: str, record_id: str) -> dict:
    """查询某条记录的审批进度.

    Args:
        record_type: 记录类型
        record_id: 记录 ID

    Returns:
        审批进度详情.
    """
    steps = db_get_approval_status(record_type, record_id)
    if not steps:
        return {"error": f"未找到 {record_type} 记录 {record_id} 的审批流"}

    progress = []
    for s in steps:
        progress.append({
            "step": s["step"],
            "approver": s.get("approver_name", s["approver_id"]),
            "role": s["approver_role"],
            "status": s["status"],
            "comment": s.get("comment"),
            "decided_at": s.get("decided_at"),
        })

    completed = sum(1 for p in progress if p["status"] != "pending")

    return {
        "record_type": record_type,
        "record_id": record_id,
        "total_steps": len(progress),
        "completed": completed,
        "steps": progress,
    }


def get_pending_approvals(approver_id: str) -> dict:
    """查询某审批人的所有待审批项(请假 + 报销).

    Args:
        approver_id: 审批人 ID

    Returns:
        待审批列表.
    """
    with get_db() as conn:
        # 请假
        leave_rows = conn.execute(
            """SELECT a.*, l.user_id as applicant_id, l.leave_type as subtype,
                      l.start_date, l.end_date, l.total_days as amount_val,
                      l.reason as description, l.status as record_status,
                      u.name as applicant_name, u.department_id as applicant_dept
               FROM approval_flow a
               JOIN leave_records l ON a.record_id = l.id
               JOIN users u ON l.user_id = u.user_id
               WHERE a.approver_id = ? AND a.status = 'pending'""",
            (approver_id,),
        ).fetchall()

        # 报销
        expense_rows = conn.execute(
            """SELECT a.*, e.user_id as applicant_id, e.expense_type as subtype,
                      NULL as start_date, NULL as end_date,
                      e.amount as amount_val, e.description,
                      e.status as record_status,
                      u.name as applicant_name, u.department_id as applicant_dept
               FROM approval_flow a
               JOIN expense_reports e ON a.record_id = e.id
               JOIN users u ON e.user_id = u.user_id
               WHERE a.approver_id = ? AND a.status = 'pending'""",
            (approver_id,),
        ).fetchall()

    pending = []
    for r in leave_rows:
        pending.append(_format_approval_item("leave", r))
    for r in expense_rows:
        pending.append(_format_approval_item("expense", r))

    return {
        "approver_id": approver_id,
        "total": len(pending),
        "pending": sorted(pending, key=lambda x: x.get("created_at", ""), reverse=True),
    }


# ── 内部辅助 ──────────────────────────────────────────────────────


def _record_label(record_type: str) -> str:
    """记录类型中文标签."""
    return {"leave": "请假", "expense": "报销"}.get(record_type, record_type)


def _finalize_record(record_type: str, record_id: str) -> None:
    """审批全部通过后的收尾操作."""
    if record_type == "leave":
        transition_leave_status(record_id, "approved")
        with get_db() as conn:
            row = conn.execute(
                "SELECT user_id, leave_type, total_days FROM leave_records WHERE id = ?",
                (record_id,),
            ).fetchone()
        if row:
            db_deduct_leave_balance(row["user_id"], row["leave_type"], row["total_days"])

    elif record_type == "expense":
        with get_db() as conn:
            conn.execute(
                "UPDATE expense_reports SET status = 'approved', updated_at = ? WHERE id = ?",
                (_now(), record_id),
            )
            conn.commit()


def _reject_record(record_type: str, record_id: str) -> None:
    """驳回主记录."""
    if record_type == "leave":
        transition_leave_status(record_id, "rejected")
    elif record_type == "expense":
        with get_db() as conn:
            conn.execute(
                "UPDATE expense_reports SET status = 'rejected', updated_at = ? WHERE id = ?",
                (_now(), record_id),
            )
            conn.commit()


def _format_approval_item(record_type: str, row: Any) -> dict:
    """格式化审批列表项."""
    return {
        "step_id": row["id"],
        "step": row["step"],
        "record_type": record_type,
        "record_type_label": _record_label(record_type),
        "record_id": row["record_id"],
        "approver_role": row["approver_role"],
        "created_at": row["created_at"],
        "applicant": {
            "user_id": row["applicant_id"],
            "name": row.get("applicant_name"),
            "department": row.get("applicant_dept"),
        },
        "detail": {
            "subtype": row.get("subtype"),
            "start_date": row.get("start_date"),
            "end_date": row.get("end_date"),
            "amount": row.get("amount_val"),
            "description": row.get("description"),
            "status": row.get("record_status"),
        },
    }
