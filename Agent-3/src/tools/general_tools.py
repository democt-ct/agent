"""通用工具集 -- 跨域共享的工具,所有 Agent 均可调用.

工具:
    get_my_applications  -- 查询用户所有申请记录(请假 + IT工单 + 报销)
    get_my_notifications -- 查询用户未读通知
    get_pending_approvals -- 查询审批人待审批列表
    get_dashboard_summary -- 综合仪表盘
"""


from __future__ import annotations

from src.tools.base import ToolDef
from src.tools.db import db_get_my_applications


# ── 工具实现 ─────────────────────────────────────────────────────

def get_my_applications(user_id: str) -> dict:
    """查询用户的所有申请记录,包括请假,IT工单和报销.

    Args:
        user_id: 员工ID.

    Returns:
        统一格式的申请记录列表.
    """
    rows = db_get_my_applications(user_id)

    if not rows:
        return {
            "user_id": user_id,
            "total": 0,
            "applications": [],
            "by_type": {"请假": 0, "IT工单": 0, "报销": 0},
            "message": f"用户 {user_id} 暂无申请记录",
        }

    # 按类型统计
    by_type = {"请假": 0, "IT工单": 0, "报销": 0}
    for r in rows:
        label = r.get("app_type_label", "")
        if label in by_type:
            by_type[label] += 1

    # 状态映射
    status_map = {
        "pending": "待审批", "approved": "已通过", "rejected": "已驳回",
        "draft": "草稿", "cancelled": "已取消", "completed": "已完成",
        "待处理": "待处理", "处理中": "处理中", "已完成": "已完成",
        "reimbursed": "已报销",
    }

    def _format(app: dict) -> dict:
        raw_status = app.get("status", "")
        return {
            "app_type": app.get("app_type"),
            "app_type_label": app.get("app_type_label"),
            "id": app.get("id"),
            "subtype": app.get("subtype"),
            "start_date": app.get("start_date"),
            "end_date": app.get("end_date"),
            "amount": app.get("amount_val"),
            "description": app.get("description"),
            "status": raw_status,
            "status_label": status_map.get(raw_status, raw_status),
            "created_at": app.get("created_at"),
        }

    return {
        "user_id": user_id,
        "total": len(rows),
        "by_type": by_type,
        "applications": [_format(r) for r in rows],
    }


# ── 工具列表 ─────────────────────────────────────────────────────

GENERAL_TOOLS: list[ToolDef] = [
    ToolDef(
        name="get_my_applications",
        description=(
            "查询某个用户的所有申请记录,包括请假申请,IT工单和报销申请."
            "输入用户ID,返回统一格式的申请列表,包含类型,状态,时间等信息."
            "当用户询问'我的申请','申请记录','我有哪些申请','申请状态'时使用此工具."
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
        implementation=get_my_applications,
        permission={"roles": ["employee", "manager", "hr", "admin"], "scope": "self"},
        audit=False,
    ),
    ToolDef(
        name="get_my_notifications",
        description=(
            "查询当前用户的未读通知列表.当用户问'有什么通知','通知',"
            "'消息'时使用.返回未读数量 + 通知列表."
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
        implementation=lambda user_id: (
            __import__("src.skills.notification", fromlist=["get_unread_notifications"])
            .get_unread_notifications(user_id)
        ),
        permission={"roles": ["employee", "manager", "hr", "admin"], "scope": "self"},
        audit=False,
    ),
    ToolDef(
        name="get_pending_approvals",
        description=(
            "查询某个审批人的所有待审批项(包括请假和报销)."
            "当审批人/经理询问'待审批','有什么需要我审批的'时使用."
        ),
        parameters={
            "type": "object",
            "properties": {
                "approver_id": {
                    "type": "string",
                    "description": "审批人ID",
                },
            },
            "required": ["approver_id"],
        },
        implementation=lambda approver_id: (
            __import__("src.skills.approval_engine", fromlist=["get_pending_approvals"])
            .get_pending_approvals(approver_id)
        ),
        permission={"roles": ["manager", "hr", "admin"], "scope": "self"},
        audit=False,
    ),
    ToolDef(
        name="get_dashboard_summary",
        description=(
            "获取综合仪表盘数据:待处理工单数,待审批请假数,待审批报销数,"
            "本月已批准请假天数.当用户问'最近情况','目前有多少待处理'时使用."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        implementation=lambda **kw: (
            __import__("src.skills.reporting", fromlist=["dashboard_summary"])
            .dashboard_summary()
        ),
        audit=False,
    ),
]
