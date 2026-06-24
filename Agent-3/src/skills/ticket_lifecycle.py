"""工单全生命周期管理 -- 创建 → 处理 → 完成 → 关闭 → 重开 → 升级 → 统计.

基于现有 it_tickets 表,在原子 db_create_ticket / db_get_ticket 之上提供
完整的状态机和业务流程.

状态流转:
    待处理 ──→ 处理中 ──→ 已完成
      │          │
      └── 已关闭 ←┘
           │
           └── 待处理 (重开)

升级: 任意非终态 → 提升优先级 + 通知更高层级

Usage:
    from src.skills.ticket_lifecycle import create_ticket_full, process_ticket
    result = create_ticket_full("EMP001", "硬件报修", "蓝屏无法启动", priority="高")
    result = process_ticket("TK004", "EMP005", "已确认故障,安排更换主板")
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.tools.db import get_db, _uid, _now
from src.skills.notification import send_notification

logger = logging.getLogger(__name__)

# ── 状态机定义 ────────────────────────────────────────────────────

# 合法状态
VALID_STATUSES = {"待处理", "处理中", "已完成", "已关闭"}

# 非终态(可以进行状态转移)
NON_FINAL_STATUSES = {"待处理", "处理中"}

# 状态转移表
TRANSITIONS: dict[str, set[str]] = {
    "待处理": {"处理中", "已关闭"},
    "处理中": {"已完成", "已关闭"},
    "已关闭": {"待处理"},       # 重开
    "已完成": set(),            # 终态
}

# 状态 → 中文标签
STATUS_LABELS: dict[str, str] = {
    "待处理": "待处理",
    "处理中": "处理中",
    "已完成": "已完成",
    "已关闭": "已关闭",
}


class TicketStateError(Exception):
    """工单状态转换非法."""
    def __init__(self, ticket_id: str, current: str, target: str):
        super().__init__(f"工单 {ticket_id}: 不允许 {current} → {target}")
        self.ticket_id = ticket_id
        self.current = current
        self.target = target


def _transition(ticket_id: str, current: str, target: str) -> str:
    """校验并执行状态转换.

    Returns:
        新状态字符串.

    Raises:
        TicketStateError: 非法转换.
    """
    allowed = TRANSITIONS.get(current, set())
    if target not in allowed:
        raise TicketStateError(ticket_id, current, target)
    return target


def _get_ticket(ticket_id: str) -> dict | None:
    """获取工单完整信息."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM it_tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
    return dict(row) if row else None


# ── 工单类型 → 责任部门映射 ──────────────────────────────────────

_TICKET_DEPT_MAP: dict[str, str] = {
    "硬件报修": "dept-it",
    "软件安装": "dept-it",
    "网络问题": "dept-it",
    "账号问题": "dept-it",
    "设备申领": "dept-it",
    "报销问题": "dept-finance",
    "合同问题": "dept-it",
    "制度咨询": "dept-hr",
    "其他":     "dept-it",
}


# ── 公共 API ──────────────────────────────────────────────────────

def create_ticket_full(
    user_id: str,
    issue_type: str,
    description: str,
    priority: str = "中",
    department_id: str = "",
) -> dict:
    """创建工单(增强版)-- 含自动路由,通知,幂等去重.

    相比 src/tools/it_tools.create_ticket 的增强:
      - 返回结构化 result 含 FSM 初始状态
      - 使用 skills 通知中心(带去重)
      - 幂等:同一用户 + 同类型 + 同描述,5 分钟内不重复创建

    Args:
        user_id: 员工ID
        issue_type: 问题类型(硬件报修/软件安装/网络问题/账号问题/设备申领/报销问题/合同问题/制度咨询/其他)
        description: 问题描述
        priority: 优先级(高/中/低)
        department_id: 部门ID(留空则按类型自动路由)

    Returns:
        {"success": True, "ticket_id": "TK...", "message": "...", ...}
        或被幂等拦截 {"skipped": True, "ticket_id": "TK...", "reason": "5分钟内重复创建"}
    """
    valid_priorities = {"高", "中", "低"}

    # 幂等去重:同一用户 + 同类型 + 同描述,5 分钟内不重复创建
    import hashlib
    dedup_key = hashlib.md5(
        f"{user_id}|{issue_type}|{description.strip()}".encode()
    ).hexdigest()[:16]
    with get_db() as conn:
        dup = conn.execute(
            """SELECT ticket_id, status, created_at FROM it_tickets
               WHERE user_id = ? AND issue_type = ? AND description = ?
                 AND created_at >= datetime('now', '-5 minutes')
               ORDER BY created_at DESC LIMIT 1""",
            (user_id, issue_type, description),
        ).fetchone()
    if dup is not None:
        return {
            "success": True,
            "skipped": True,
            "ticket_id": dup["ticket_id"],
            "status": dup["status"],
            "reason": f"5 分钟内已创建相同工单 {dup['ticket_id']}",
            "message": f"工单 {dup['ticket_id']} 已存在,无需重复创建",
        }
    if priority not in valid_priorities:
        priority = "中"

    if not department_id:
        department_id = _TICKET_DEPT_MAP.get(issue_type, "dept-it")

    # 获取部门经理作为受理人
    assigned_to = "待分配"
    with get_db() as conn:
        dept_row = conn.execute(
            "SELECT manager_id FROM departments WHERE id = ?", (department_id,)
        ).fetchone()
        if dept_row and dept_row["manager_id"]:
            assigned_to = dept_row["manager_id"]

    # 生成工单 ID
    now = _now()
    with get_db() as conn:
        max_id = conn.execute("SELECT MAX(id) as max_id FROM it_tickets").fetchone()["max_id"]
        ticket_id = f"TK{(max_id or 0) + 1:03d}"
        conn.execute(
            """INSERT INTO it_tickets
               (ticket_id, user_id, department_id, issue_type, description, priority, status, assigned_to, created_at)
               VALUES (?, ?, ?, ?, ?, ?, '待处理', ?, ?)""",
            (ticket_id, user_id, department_id, issue_type, description, priority, assigned_to, now),
        )
        conn.commit()

    # 通知受理人
    if assigned_to != "待分配":
        send_notification(
            user_id=assigned_to,
            type_="system",
            title=f"新工单 {ticket_id}",
            body=f"[{priority}优先级] {issue_type}: {description[:80]}",
            link_type="ticket",
            link_id=ticket_id,
        )

    # 通知申请人
    send_notification(
        user_id=user_id,
        type_="system",
        title=f"工单 {ticket_id} 已创建",
        body=f"你的工单已提交,类型: {issue_type},当前状态: 待处理",
        link_type="ticket",
        link_id=ticket_id,
    )

    return {
        "success": True,
        "ticket_id": ticket_id,
        "user_id": user_id,
        "department_id": department_id,
        "issue_type": issue_type,
        "priority": priority,
        "status": "待处理",
        "assigned_to": assigned_to,
        "message": f"工单 {ticket_id} 已创建,已分配给 {assigned_to},状态: 待处理",
        "created_at": now,
    }


def process_ticket(ticket_id: str, operator_id: str, comment: str = "") -> dict:
    """开始处理工单 -- 状态: 待处理 → 处理中.

    Args:
        ticket_id: 工单ID
        operator_id: 操作人ID(通常为受理人)
        comment: 处理备注

    Returns:
        处理结果.
    """
    ticket = _get_ticket(ticket_id)
    if ticket is None:
        return {"error": f"未找到工单 {ticket_id}"}

    try:
        new_status = _transition(ticket_id, ticket["status"], "处理中")
    except TicketStateError as e:
        return {"error": str(e)}

    now = _now()
    with get_db() as conn:
        conn.execute(
            "UPDATE it_tickets SET status = ? WHERE ticket_id = ?",
            (new_status, ticket_id),
        )
        conn.commit()

    # 通知申请人
    send_notification(
        user_id=ticket["user_id"],
        type_="system",
        title=f"工单 {ticket_id} 处理中",
        body=f"工单状态已更新为'处理中'" + (f",备注: {comment}" if comment else ""),
        link_type="ticket",
        link_id=ticket_id,
    )

    return {
        "success": True,
        "ticket_id": ticket_id,
        "old_status": ticket["status"],
        "new_status": new_status,
        "operator_id": operator_id,
        "comment": comment,
        "message": f"工单 {ticket_id} 已开始处理",
    }


def complete_ticket(ticket_id: str, operator_id: str, resolution: str = "") -> dict:
    """完成工单 -- 状态: 处理中 → 已完成.

    Args:
        ticket_id: 工单ID
        operator_id: 操作人ID
        resolution: 解决方案描述

    Returns:
        完成结果.
    """
    ticket = _get_ticket(ticket_id)
    if ticket is None:
        return {"error": f"未找到工单 {ticket_id}"}

    try:
        new_status = _transition(ticket_id, ticket["status"], "已完成")
    except TicketStateError as e:
        return {"error": str(e)}

    now = _now()
    with get_db() as conn:
        conn.execute(
            "UPDATE it_tickets SET status = ? WHERE ticket_id = ?",
            (new_status, ticket_id),
        )
        conn.commit()

    # 通知申请人
    send_notification(
        user_id=ticket["user_id"],
        type_="system",
        title=f"工单 {ticket_id} 已完成",
        body=f"你的工单已处理完成" + (f",解决方案: {resolution}" if resolution else ""),
        link_type="ticket",
        link_id=ticket_id,
    )

    return {
        "success": True,
        "ticket_id": ticket_id,
        "old_status": ticket["status"],
        "new_status": new_status,
        "operator_id": operator_id,
        "resolution": resolution,
        "message": f"工单 {ticket_id} 已完成",
    }


def close_ticket(ticket_id: str, operator_id: str, reason: str = "") -> dict:
    """关闭工单 -- 待处理/处理中 → 已关闭.

    用于重复工单,用户撤销,无法处理等情况.

    Args:
        ticket_id: 工单ID
        operator_id: 操作人ID
        reason: 关闭原因

    Returns:
        关闭结果.
    """
    ticket = _get_ticket(ticket_id)
    if ticket is None:
        return {"error": f"未找到工单 {ticket_id}"}

    try:
        new_status = _transition(ticket_id, ticket["status"], "已关闭")
    except TicketStateError as e:
        return {"error": str(e)}

    now = _now()
    with get_db() as conn:
        conn.execute(
            "UPDATE it_tickets SET status = ? WHERE ticket_id = ?",
            (new_status, ticket_id),
        )
        conn.commit()

    # 通知申请人
    send_notification(
        user_id=ticket["user_id"],
        type_="system",
        title=f"工单 {ticket_id} 已关闭",
        body=f"你的工单已被关闭" + (f",原因: {reason}" if reason else ""),
        link_type="ticket",
        link_id=ticket_id,
    )

    return {
        "success": True,
        "ticket_id": ticket_id,
        "old_status": ticket["status"],
        "new_status": new_status,
        "operator_id": operator_id,
        "reason": reason,
        "message": f"工单 {ticket_id} 已关闭",
    }


def reopen_ticket(ticket_id: str, operator_id: str, reason: str = "") -> dict:
    """重开工单 -- 已关闭 → 待处理.

    Args:
        ticket_id: 工单ID
        operator_id: 操作人ID
        reason: 重开原因

    Returns:
        重开结果.
    """
    ticket = _get_ticket(ticket_id)
    if ticket is None:
        return {"error": f"未找到工单 {ticket_id}"}

    try:
        new_status = _transition(ticket_id, ticket["status"], "待处理")
    except TicketStateError as e:
        return {"error": str(e)}

    now = _now()
    with get_db() as conn:
        conn.execute(
            "UPDATE it_tickets SET status = ? WHERE ticket_id = ?",
            (new_status, ticket_id),
        )
        conn.commit()

    # 重新通知受理人
    if ticket.get("assigned_to") and ticket["assigned_to"] != "待分配":
        send_notification(
            user_id=ticket["assigned_to"],
            type_="system",
            title=f"工单 {ticket_id} 已重开",
            body=f"工单已重新激活,原因: {reason}" if reason else "工单已重新激活",
            link_type="ticket",
            link_id=ticket_id,
        )

    return {
        "success": True,
        "ticket_id": ticket_id,
        "old_status": ticket["status"],
        "new_status": new_status,
        "operator_id": operator_id,
        "reason": reason,
        "message": f"工单 {ticket_id} 已重开,当前状态: 待处理",
    }


def escalate_ticket(ticket_id: str, operator_id: str, reason: str = "") -> dict:
    """升级工单 -- 提升优先级到"高"并通知部门经理.

    用于工单处理超时或用户投诉升级.

    Args:
        ticket_id: 工单ID
        operator_id: 操作人ID
        reason: 升级原因

    Returns:
        升级结果.
    """
    ticket = _get_ticket(ticket_id)
    if ticket is None:
        return {"error": f"未找到工单 {ticket_id}"}

    if ticket["status"] not in NON_FINAL_STATUSES:
        return {"error": f"工单 {ticket_id} 当前状态 '{ticket['status']}' 不可升级"}

    old_priority = ticket["priority"]

    # 获取部门经理
    with get_db() as conn:
        dept_row = conn.execute(
            "SELECT manager_id FROM departments WHERE id = ?", (ticket["department_id"],)
        ).fetchone()
        mgr_id = dept_row["manager_id"] if dept_row else None

    now = _now()
    with get_db() as conn:
        conn.execute(
            "UPDATE it_tickets SET priority = '高' WHERE ticket_id = ?",
            (ticket_id,),
        )
        conn.commit()

    # 通知部门经理(如果不同于当前受理人)
    if mgr_id and mgr_id != ticket.get("assigned_to"):
        send_notification(
            user_id=mgr_id,
            type_="system",
            title=f"工单 {ticket_id} 已升级",
            body=f"工单优先级提升为'高',原因: {reason}" if reason else "工单优先级提升为'高'",
            link_type="ticket",
            link_id=ticket_id,
        )

    return {
        "success": True,
        "ticket_id": ticket_id,
        "old_priority": old_priority,
        "new_priority": "高",
        "operator_id": operator_id,
        "reason": reason,
        "message": f"工单 {ticket_id} 优先级已从 {old_priority} 升级为高",
    }


def get_ticket_summary(
    department_id: str = "",
    group_by: str = "status",
    days: int = 7,
) -> dict:
    """工单统计摘要 -- 按状态/类型/优先级/部门聚合.

    Args:
        department_id: 部门筛选(留空 = 全部门)
        group_by: 聚合维度: status | type | priority | department
        days: 统计最近 N 天

    Returns:
        {"total": N, "groups": [...], "by_priority": {...}}
    """
    date_filter = f"datetime('now', '-{days} days')"

    with get_db() as conn:
        # 总数
        where_clause = f"WHERE created_at >= {date_filter}"
        params: list = []
        if department_id:
            where_clause += " AND department_id = ?"
            params.append(department_id)

        total_row = conn.execute(
            f"SELECT COUNT(*) as cnt FROM it_tickets {where_clause}", params
        ).fetchone()
        total = total_row["cnt"] if total_row else 0

        # 按维度聚合
        valid_groups = {"status": "status", "type": "issue_type", "priority": "priority", "department": "department_id"}
        group_col = valid_groups.get(group_by, "status")

        group_rows = conn.execute(
            f"""SELECT {group_col} as label, COUNT(*) as count
                FROM it_tickets {where_clause}
                GROUP BY {group_col}
                ORDER BY count DESC""",
            params,
        ).fetchall()

        # 按优先级统计
        prio_rows = conn.execute(
            f"""SELECT priority, COUNT(*) as count
                FROM it_tickets {where_clause}
                GROUP BY priority""",
            params,
        ).fetchall()

    groups = [{"label": r["label"], "count": r["count"]} for r in group_rows]
    by_priority = {r["priority"]: r["count"] for r in prio_rows}

    return {
        "total": total,
        "group_by": group_by,
        "days": days,
        "department_id": department_id or "全部",
        "groups": groups,
        "by_priority": by_priority,
    }


def get_ticket_detail(ticket_id: str) -> dict:
    """获取工单详情(含申请人姓名,部门名).

    Args:
        ticket_id: 工单ID

    Returns:
        工单完整信息.
    """
    with get_db() as conn:
        row = conn.execute(
            """SELECT t.*, u.name as user_name, d.name as department_name
               FROM it_tickets t
               JOIN users u ON t.user_id = u.user_id
               LEFT JOIN departments d ON t.department_id = d.id
               WHERE t.ticket_id = ?""",
            (ticket_id,),
        ).fetchone()

    if row is None:
        return {"error": f"未找到工单 {ticket_id}"}

    ticket = dict(row)
    ticket["status_label"] = STATUS_LABELS.get(ticket.get("status", ""), ticket.get("status", ""))

    # 计算处理时长
    if ticket.get("created_at"):
        try:
            created = datetime.fromisoformat(ticket["created_at"].replace("Z", "+00:00"))
            elapsed = datetime.now(timezone.utc) - created
            ticket["elapsed_hours"] = round(elapsed.total_seconds() / 3600, 1)
        except (ValueError, TypeError):
            ticket["elapsed_hours"] = None

    return ticket
