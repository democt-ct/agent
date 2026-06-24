"""数据库包 -- 对外 API 不变的兼容重导出.

Usage:
    from src.tools.db import get_db, bootstrap_company_workspace
    from src.tools.db import db_get_user, db_get_leave_balance
"""

from __future__ import annotations

# ── 连接 ──────────────────────────────────────────
from .connection import get_db, _now, _uid

# ── Schema DDL ────────────────────────────────────
from .schema import _SCHEMA

# ── 种子数据 ──────────────────────────────────────
from .seed import bootstrap_company_workspace

# ── 业务查询 ──────────────────────────────────────
from .queries import (
    # v1 兼容
    db_get_leave_balance,
    db_submit_leave_request,
    # 用户
    db_get_user,
    db_verify_password,
    # 组织架构
    db_get_org_chain,
    db_get_department_head,
    db_get_department_manager,
    db_get_user_by_role,
    # 审批流
    db_create_approval_flow,
    db_get_approval_status,
    db_get_pending_approvals,
    db_update_approval_step,
    # 假期记录
    db_deduct_leave_balance,
    db_get_used_leave_days,
    # 工作流任务
    db_create_task,
    db_update_task,
    # 统一申请记录
    db_get_my_applications,
    db_get_application,
    db_update_application,
    db_update_status,
    db_delete_application,
    # 财务
    db_get_budget,
    db_get_policy_doc,
    db_get_policy_docs,
    db_get_salary_profile,
    db_get_finance_approver,
    db_get_hr_approver,
    db_submit_expense,
    # IT
    db_get_ticket,
    db_create_ticket,
    db_get_inventory,
    db_list_inventory_names,
    # 法务
    db_search_contract,
    db_check_compliance,
    # 通知
    db_create_notification,
    db_get_notifications,
    db_mark_notifications_read,
    db_unread_count,
)
