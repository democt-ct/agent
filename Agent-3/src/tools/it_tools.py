"""IT Agent 工具集 -- SQLite 持久化实现.

每个函数返回 dict,与 ToolDef.implementation 签名对齐.
"""

from __future__ import annotations

from src.tools.base import ToolDef
from src.tools.db import (
    db_get_ticket,
    db_create_ticket,
    db_get_inventory,
    db_list_inventory_names,
)

# ── 工具实现 ─────────────────────────────────────────────────────

def check_ticket_status(ticket_id: str) -> dict:
    """查询 IT 工单处理状态.

    Args:
        ticket_id: 工单ID,如 TK001.

    Returns:
        工单详情.
    """
    ticket = db_get_ticket(ticket_id)
    if ticket is None:
        return {"error": f"未找到工单 {ticket_id}"}
    return ticket


# 工单类型 → 责任部门映射(不同工单路由到不同部门经理)
_TICKET_DEPT_MAP: dict[str, str] = {
    "硬件报修": "dept-it",
    "软件安装": "dept-it",
    "网络问题": "dept-it",
    "账号问题": "dept-it",
    "设备申领": "dept-it",
    "报销问题": "dept-finance",
    "合同问题": "dept-it",        # 暂无独立法务部经理,暂归 IT
    "其他":     "dept-it",
}


def create_ticket(
    user_id: str,
    issue_type: str,
    description: str,
    priority: str = "中",
) -> dict:
    """创建工单,按问题类型自动路由到对应部门经理.

    Args:
        user_id: 员工ID.
        issue_type: 问题类型(硬件报修/软件安装/网络问题/账号问题/报销问题/合同问题/其他).
        description: 问题描述.
        priority: 优先级(高/中/低).

    Returns:
        创建结果.
    """
    valid_priorities = {"高", "中", "低"}
    if priority not in valid_priorities:
        priority = "中"

    # 按工单类型路由到对应部门
    dept_id = _TICKET_DEPT_MAP.get(issue_type, "dept-it")

    ticket = db_create_ticket(user_id, issue_type, description, priority, department_id=dept_id)

    # 通知对应部门经理
    manager_user_id = ticket.get("assigned_to") if ticket.get("assigned_to") != "待分配" else None
    if manager_user_id:
        try:
            from src.tools.db import get_db, _uid, _now
            with get_db() as conn:
                conn.execute(
                    """INSERT INTO notifications (id, user_id, type, title, body, link_type, link_id, created_at)
                       VALUES (?, ?, 'system', '新工单', ?, 'ticket', ?, ?)""",
                    (_uid(), manager_user_id,
                     f"[{issue_type}] {description[:50]}",
                     ticket["ticket_id"], _now()),
                )
                conn.commit()
        except Exception:
            pass

    return {
        "success": True,
        "ticket_id": ticket["ticket_id"],
        "message": f"工单 {ticket['ticket_id']} 已创建,已分配给 {ticket['assigned_to']}",
        "assigned_to": ticket["assigned_to"],
    }


def check_device_inventory(device_type: str) -> dict:
    """查询设备库存.

    Args:
        device_type: 设备类型(笔记本/显示器/鼠标/键盘/耳机).

    Returns:
        库存信息.
    """
    result = db_get_inventory(device_type)
    if result is None:
        return {
            "error": f"未找到设备类型: {device_type}",
            "available_types": db_list_inventory_names(),
        }

    return result


def request_device(
    user_id: str,
    device_type: str,
    reason: str = "",
    urgency: str = "普通",
) -> dict:
    """申请设备(自动查库存,创建工单,通知 IT 经理).

    Args:
        user_id: 员工ID
        device_type: 设备类型(笔记本/显示器/鼠标/键盘/耳机)
        reason: 申领原因
        urgency: 紧急程度(普通/紧急)

    Returns:
        申领结果.
    """
    # 先查库存
    inventory = check_device_inventory(device_type)
    if "error" in inventory:
        return inventory

    # 创建申领工单
    return create_ticket(
        user_id=user_id,
        issue_type="设备申领",
        description=f"申领 {device_type}.原因: {reason or '工作需要'}.急迫程度: {urgency}.当前库存: {inventory.get('available', 0)}/{inventory.get('total', 0)}",
        priority="高" if urgency == "紧急" else "中",
    )


# ── skills 工具(委托给 src/skills/) ──────────────────────

def update_ticket_status(ticket_id: str, action: str, operator_id: str, comment: str = "") -> dict:
    """更新工单状态(处理/完成/关闭/重开).

    Args:
        ticket_id: 工单ID.
        action: 操作类型:process(处理)/ complete(完成)/ close(关闭)/ reopen(重开).
        operator_id: 操作人ID.
        comment: 备注/原因.

    Returns:
        操作结果.
    """
    from src.skills.ticket_lifecycle import (
        process_ticket, complete_ticket, close_ticket, reopen_ticket,
    )
    action_map = {
        "process": process_ticket,
        "complete": complete_ticket,
        "close": close_ticket,
        "reopen": reopen_ticket,
    }
    fn = action_map.get(action)
    if fn is None:
        return {"error": f"无效操作: {action},可选: {', '.join(action_map)}"}
    return fn(ticket_id, operator_id, comment)


def escalate_ticket_tool(ticket_id: str, operator_id: str, reason: str = "") -> dict:
    """升级工单优先级."""
    from src.skills.ticket_lifecycle import escalate_ticket
    return escalate_ticket(ticket_id, operator_id, reason)


def get_ticket_summary_tool(group_by: str = "status", days: int = 7) -> dict:
    """工单统计摘要."""
    from src.skills.ticket_lifecycle import get_ticket_summary
    return get_ticket_summary(group_by=group_by, days=days)


def get_ticket_detail_tool(ticket_id: str) -> dict:
    """工单详情(含申请人信息,处理时长)."""
    from src.skills.ticket_lifecycle import get_ticket_detail
    return get_ticket_detail(ticket_id)


# ── 工具列表 ─────────────────────────────────────────────────────

IT_TOOLS: list[ToolDef] = [
    ToolDef(
        name="check_ticket_status",
        description=(
            "查询 IT 工单的当前处理状态.输入工单ID(如 TK001),"
            "返回处理进度,负责人等详情."
        ),
        parameters={
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "工单ID,如 TK001",
                },
            },
            "required": ["ticket_id"],
        },
        implementation=check_ticket_status,
    ),
    ToolDef(
        name="create_ticket",
        description=(
            "创建工单,按问题类型自动路由到对应部门经理."
            "需要提供员工ID,问题类型"
            "(硬件报修/软件安装/网络问题/账号问题/设备申领/报销问题/合同问题/其他),"
            "问题描述,优先级(高/中/低)."
            "硬件/设备→IT经理,报销→财务经理,合同→IT经理."
        ),
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "员工ID",
                },
                "issue_type": {
                    "type": "string",
                    "description": "问题类型",
                    "enum": ["硬件报修", "软件安装", "网络问题", "账号问题", "设备申领", "报销问题", "合同问题", "其他"],
                },
                "description": {
                    "type": "string",
                    "description": "问题描述",
                },
                "priority": {
                    "type": "string",
                    "description": "优先级",
                    "enum": ["高", "中", "低"],
                },
            },
            "required": ["user_id", "issue_type", "description"],
        },
        implementation=create_ticket,
    ),
    ToolDef(
        name="check_device_inventory",
        description=(
            "查询 IT 设备库存情况.输入设备类型(如 笔记本,显示器,鼠标),"
            "返回库存数量和品牌信息."
        ),
        parameters={
            "type": "object",
            "properties": {
                "device_type": {
                    "type": "string",
                    "description": "设备类型,如 笔记本,显示器,鼠标,键盘,耳机",
                },
            },
            "required": ["device_type"],
        },
        implementation=check_device_inventory,
    ),
    ToolDef(
        name="request_device",
        description=(
            "申请领用 IT 设备(笔记本/显示器/鼠标/键盘/耳机)."
            "自动检查库存,创建申领工单并通知 IT 经理审批."
            "需要员工ID,设备类型,申领原因."
        ),
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "员工ID",
                },
                "device_type": {
                    "type": "string",
                    "description": "设备类型",
                    "enum": ["笔记本", "显示器", "鼠标", "键盘", "耳机"],
                },
                "reason": {
                    "type": "string",
                    "description": "申领原因",
                },
                "urgency": {
                    "type": "string",
                    "description": "紧急程度",
                    "enum": ["普通", "紧急"],
                },
            },
            "required": ["user_id", "device_type"],
        },
        implementation=request_device,
    ),
    ToolDef(
        name="update_ticket_status",
        description=(
            "更新工单状态.action 可选: process(开始处理),complete(标记完成),"
            "close(关闭工单),reopen(重开已关闭工单).需提供工单ID,操作人ID和备注."
        ),
        parameters={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "工单ID"},
                "action": {
                    "type": "string",
                    "enum": ["process", "complete", "close", "reopen"],
                    "description": "操作类型",
                },
                "operator_id": {"type": "string", "description": "操作人ID"},
                "comment": {"type": "string", "description": "备注"},
            },
            "required": ["ticket_id", "action", "operator_id"],
        },
        implementation=update_ticket_status,
    ),
    ToolDef(
        name="escalate_ticket",
        description=(
            "升级工单优先级至'高',并通知部门经理.用于超时未处理或紧急情况."
            "需提供工单ID,操作人ID和升级原因."
        ),
        parameters={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "工单ID"},
                "operator_id": {"type": "string", "description": "操作人ID"},
                "reason": {"type": "string", "description": "升级原因"},
            },
            "required": ["ticket_id", "operator_id"],
        },
        implementation=escalate_ticket_tool,
    ),
    ToolDef(
        name="get_ticket_summary",
        description=(
            "工单统计摘要.按状态/类型/优先级统计工单分布."
            "可选参数: group_by(聚合维度: status/type/priority/department),"
            "days(统计最近N天,默认7天)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "group_by": {
                    "type": "string",
                    "enum": ["status", "type", "priority", "department"],
                    "description": "聚合维度",
                },
                "days": {"type": "integer", "description": "统计天数,默认7"},
            },
            "required": [],
        },
        implementation=get_ticket_summary_tool,
    ),
    ToolDef(
        name="get_ticket_detail",
        description=(
            "获取单个工单的详细信息,包括申请人姓名,部门,处理时长等."
            "输入工单ID即可."
        ),
        parameters={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "工单ID"},
            },
            "required": ["ticket_id"],
        },
        implementation=get_ticket_detail_tool,
    ),
]
