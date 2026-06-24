"""聚合报表 -- 工单日报/周报,请假月报,预算使用率统计.

所有报表函数返回结构化 dict,可被 Agent 通过 ToolDef 调用,
也可被 CLI 脚本独立运行.

Usage:
    from src.skills.reporting import ticket_daily_report, leave_monthly_report
    report = ticket_daily_report()
    report = leave_monthly_report("dept-eng", year=2026, month=6)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.tools.db import get_db

logger = logging.getLogger(__name__)


# ── 工单报表 ──────────────────────────────────────────────────────

def ticket_daily_report(department_id: str = "") -> dict:
    """当日工单汇总 -- 今日创建/处理中/已完成的工单统计.

    Args:
        department_id: 部门筛选(留空 = 全部门)

    Returns:
        {"date": "...", "created": N, "in_progress": N, "completed": N, ...}
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dept_filter = "AND t.department_id = ?" if department_id else ""
    params = [department_id] if department_id else []

    with get_db() as conn:
        # 今日创建
        created_row = conn.execute(
            f"SELECT COUNT(*) as cnt FROM it_tickets WHERE date(created_at) = ? {dept_filter}",
            [today] + params,
        ).fetchone()

        # 当前处理中(非终态)
        in_progress_row = conn.execute(
            f"""SELECT COUNT(*) as cnt FROM it_tickets
                WHERE status IN ('待处理', '处理中') {dept_filter}""",
            params,
        ).fetchone()

        # 今日完成
        completed_row = conn.execute(
            f"""SELECT COUNT(*) as cnt FROM it_tickets
                WHERE status = '已完成' {dept_filter}""",
            params,
        ).fetchone()

        # 按类型分布
        type_rows = conn.execute(
            f"""SELECT issue_type, COUNT(*) as cnt FROM it_tickets
                WHERE status IN ('待处理', '处理中') {dept_filter}
                GROUP BY issue_type ORDER BY cnt DESC""",
            params,
        ).fetchall()

        # 按优先级分布
        prio_rows = conn.execute(
            f"""SELECT priority, COUNT(*) as cnt FROM it_tickets
                WHERE status IN ('待处理', '处理中') {dept_filter}
                GROUP BY priority""",
            params,
        ).fetchall()

        # 今日创建的工单列表
        ticket_rows = conn.execute(
            f"""SELECT t.ticket_id, t.issue_type, t.priority, t.status,
                      t.description, t.created_at, u.name as user_name
               FROM it_tickets t
               JOIN users u ON t.user_id = u.user_id
               WHERE date(t.created_at) = ? {dept_filter}
               ORDER BY t.created_at DESC""",
            [today] + params,
        ).fetchall()

    return {
        "report_type": "daily",
        "date": today,
        "department_id": department_id or "全部",
        "summary": {
            "created_today": created_row["cnt"] if created_row else 0,
            "in_progress": in_progress_row["cnt"] if in_progress_row else 0,
            "completed_total": completed_row["cnt"] if completed_row else 0,
        },
        "by_type": [{"type": r["issue_type"], "count": r["cnt"]} for r in type_rows],
        "by_priority": {r["priority"]: r["cnt"] for r in prio_rows},
        "tickets_today": [
            {
                "ticket_id": r["ticket_id"],
                "user_name": r["user_name"],
                "issue_type": r["issue_type"],
                "priority": r["priority"],
                "status": r["status"],
                "description": r["description"][:60],
                "created_at": r["created_at"],
            }
            for r in ticket_rows
        ],
    }


def ticket_weekly_report(department_id: str = "") -> dict:
    """本周工单周报 -- 过去 7 天的工单趋势 + 当前积压.

    Args:
        department_id: 部门筛选(留空 = 全部门)

    Returns:
        周报数据.
    """
    dept_filter = "AND department_id = ?" if department_id else ""
    params = [department_id] if department_id else []

    with get_db() as conn:
        # 过去 7 天每日创建量
        daily_rows = conn.execute(
            f"""SELECT date(created_at) as day, COUNT(*) as cnt
                FROM it_tickets
                WHERE created_at >= datetime('now', '-7 days') {dept_filter}
                GROUP BY day ORDER BY day""",
            params,
        ).fetchall()

        # 总览
        total_row = conn.execute(
            f"SELECT COUNT(*) as cnt FROM it_tickets {('WHERE ' + dept_filter.lstrip('AND ')) if dept_filter else ''}",
            params,
        ).fetchone()

        # 各状态数量
        status_rows = conn.execute(
            f"""SELECT status, COUNT(*) as cnt FROM it_tickets
                {('WHERE ' + dept_filter.lstrip('AND ')) if dept_filter else ''}
                GROUP BY status""",
            params,
        ).fetchall()

        # 高优先级未解决
        high_prio_rows = conn.execute(
            f"""SELECT ticket_id, issue_type, description, created_at,
                      u.name as user_name
               FROM it_tickets t
               JOIN users u ON t.user_id = u.user_id
               WHERE priority = '高' AND status IN ('待处理', '处理中') {dept_filter}
               ORDER BY created_at ASC""",
            params,
        ).fetchall()

    return {
        "report_type": "weekly",
        "department_id": department_id or "全部",
        "daily_trend": [{"day": r["day"], "count": r["cnt"]} for r in daily_rows],
        "total": total_row["cnt"] if total_row else 0,
        "by_status": {r["status"]: r["cnt"] for r in status_rows},
        "high_priority_open": len(high_prio_rows),
        "high_priority_tickets": [
            {
                "ticket_id": r["ticket_id"],
                "user_name": r["user_name"],
                "issue_type": r["issue_type"],
                "description": r["description"][:60],
                "created_at": r["created_at"],
            }
            for r in high_prio_rows
        ],
    }


# ── 请假报表 ──────────────────────────────────────────────────────

def leave_monthly_report(department_id: str = "", year: int | None = None, month: int | None = None) -> dict:
    """月度请假统计 -- 按类型/部门聚合.

    Args:
        department_id: 部门筛选
        year: 年份(默认当年)
        month: 月份(默认当月)

    Returns:
        月度请假统计.
    """
    now = datetime.now(timezone.utc)
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    period = f"{year}-{month:02d}"
    dept_filter = "AND u.department_id = ?" if department_id else ""
    params = [period, department_id] if department_id else [period]

    with get_db() as conn:
        # 按类型统计
        type_rows = conn.execute(
            f"""SELECT l.leave_type, COUNT(*) as cnt, SUM(l.total_days) as total_days
                FROM leave_records l
                JOIN users u ON l.user_id = u.user_id
                WHERE substr(l.start_date, 1, 7) = ? {dept_filter}
                GROUP BY l.leave_type""",
            params,
        ).fetchall()

        # 按状态统计
        status_rows = conn.execute(
            f"""SELECT l.status, COUNT(*) as cnt
                FROM leave_records l
                JOIN users u ON l.user_id = u.user_id
                WHERE substr(l.start_date, 1, 7) = ? {dept_filter}
                GROUP BY l.status""",
            params,
        ).fetchall()

        # 总人数(有请假记录的)
        user_count_row = conn.execute(
            f"""SELECT COUNT(DISTINCT l.user_id) as cnt
                FROM leave_records l
                JOIN users u ON l.user_id = u.user_id
                WHERE substr(l.start_date, 1, 7) = ? {dept_filter}""",
            params,
        ).fetchone()

    return {
        "report_type": "monthly",
        "period": period,
        "department_id": department_id or "全部",
        "total_users": user_count_row["cnt"] if user_count_row else 0,
        "by_type": [
            {"leave_type": r["leave_type"], "count": r["cnt"], "total_days": r["total_days"] or 0}
            for r in type_rows
        ],
        "by_status": {r["status"]: r["cnt"] for r in status_rows},
    }


# ── 预算报表 ──────────────────────────────────────────────────────

def budget_usage_report(department_id: str = "", year: int | None = None) -> dict:
    """预算使用率统计 -- 各部门/各类别的预算执行情况.

    Args:
        department_id: 部门筛选
        year: 年份(默认当年)

    Returns:
        预算使用率报表.
    """
    if year is None:
        year = datetime.now(timezone.utc).year

    dept_filter = "AND b.department_id = ?" if department_id else ""
    params: list = [year, department_id] if department_id else [year]

    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT b.department_id, d.name as department_name,
                      b.category, b.total, b.used,
                      ROUND(CAST(b.used AS REAL) / b.total * 100, 1) as usage_pct
               FROM budgets b
               JOIN departments d ON b.department_id = d.id
               WHERE b.year = ? {dept_filter}
               ORDER BY usage_pct DESC""",
            params,
        ).fetchall()

    items = []
    total_budget = 0.0
    total_used = 0.0
    for r in rows:
        total_budget += r["total"]
        total_used += r["used"]
        items.append({
            "department_id": r["department_id"],
            "department_name": r["department_name"],
            "category": r["category"],
            "total": r["total"],
            "used": r["used"],
            "remaining": r["total"] - r["used"],
            "usage_pct": r["usage_pct"],
        })

    overall_pct = round(total_used / total_budget * 100, 1) if total_budget > 0 else 0

    # 超预算预警
    warnings = [
        {"department": item["department_name"], "category": item["category"],
         "usage_pct": item["usage_pct"]}
        for item in items if item["usage_pct"] >= 90
    ]

    return {
        "report_type": "budget",
        "year": year,
        "department_id": department_id or "全部部门",
        "summary": {
            "total_budget": total_budget,
            "total_used": total_used,
            "remaining": total_budget - total_used,
            "overall_usage_pct": overall_pct,
        },
        "items": items,
        "warnings": warnings,
    }


# ── 综合仪表盘 ────────────────────────────────────────────────────

def dashboard_summary(department_id: str = "") -> dict:
    """综合仪表盘 -- 一次性返回所有关键指标.

    适合 Agent 在用户问"最近情况怎么样"时调用.

    Args:
        department_id: 部门筛选

    Returns:
        综合仪表盘数据.
    """
    dept_filter = "WHERE department_id = ?" if department_id else ""
    dept_filter_all = "AND department_id = ?" if department_id else ""
    params = [department_id] if department_id else []

    with get_db() as conn:
        # 工单: 待处理 + 处理中
        open_tickets = conn.execute(
            f"""SELECT COUNT(*) as cnt FROM it_tickets
                WHERE status IN ('待处理', '处理中') {dept_filter_all}""",
            params,
        ).fetchone()

        # 待审批请假
        pending_leaves = conn.execute(
            f"""SELECT COUNT(*) as cnt FROM leave_records l
                JOIN users u ON l.user_id = u.user_id
                WHERE l.status = 'pending' {dept_filter_all.replace('department_id', 'u.department_id')}""",
            params,
        ).fetchone()

        # 待审批报销
        pending_expenses = conn.execute(
            f"""SELECT COUNT(*) as cnt FROM expense_reports e
                JOIN users u ON e.user_id = u.user_id
                WHERE e.status = 'pending' {dept_filter_all.replace('department_id', 'u.department_id')}""",
            params,
        ).fetchone()

        # 当前月份请假天数
        month_prefix = datetime.now(timezone.utc).strftime("%Y-%m")
        leave_this_month = conn.execute(
            f"""SELECT COALESCE(SUM(l.total_days), 0) as total
                FROM leave_records l
                JOIN users u ON l.user_id = u.user_id
                WHERE l.status = 'approved'
                  AND substr(l.start_date, 1, 7) = ?
                  {dept_filter_all.replace('department_id', 'u.department_id')}""",
            [month_prefix] + params,
        ).fetchone()

    return {
        "report_type": "dashboard",
        "department_id": department_id or "全部",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metrics": {
            "open_tickets": open_tickets["cnt"] if open_tickets else 0,
            "pending_leave_approvals": pending_leaves["cnt"] if pending_leaves else 0,
            "pending_expense_approvals": pending_expenses["cnt"] if pending_expenses else 0,
            "approved_leave_days_this_month": leave_this_month["total"] if leave_this_month else 0,
        },
    }
