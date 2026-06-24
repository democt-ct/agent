"""Skills -- 复合业务能力层.

此层在 src/tools/(原子工具)之上,组合多个 db_* 调用实现完整的业务能力:
  - ticket_lifecycle  -- 工单全生命周期管理
  - approval_engine   -- 通用审批流引擎
  - notification      -- 统一通知中心
  - reporting         -- 聚合报表

每个模块的函数设计为:
  1. 可独立运行(import 即用,无状态)
  2. 可被 Agent 通过 ToolDef 调用
  3. 可被 CLI 脚本调用
  4. 可被定时任务调用
"""

from src.skills.ticket_lifecycle import (
    create_ticket_full,
    process_ticket,
    complete_ticket,
    close_ticket,
    reopen_ticket,
    escalate_ticket,
    get_ticket_summary,
)
from src.skills.approval_engine import (
    build_approval_chain,
    submit_for_approval,
    approve_step,
    reject_step,
    get_approval_status,
    get_pending_approvals,
)
from src.skills.notification import (
    send_notification,
    get_unread_notifications,
    mark_notifications_read,
    send_digest,
)
from src.skills.reporting import (
    ticket_daily_report,
    ticket_weekly_report,
    leave_monthly_report,
    budget_usage_report,
)

__all__ = [
    # ticket lifecycle
    "create_ticket_full", "process_ticket", "complete_ticket",
    "close_ticket", "reopen_ticket", "escalate_ticket", "get_ticket_summary",
    # approval engine
    "build_approval_chain", "submit_for_approval", "approve_step",
    "reject_step", "get_approval_status", "get_pending_approvals",
    # notification
    "send_notification", "get_unread_notifications",
    "mark_notifications_read", "send_digest",
    # reporting
    "ticket_daily_report", "ticket_weekly_report",
    "leave_monthly_report", "budget_usage_report",
]
