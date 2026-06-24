#!/usr/bin/env python3
"""工单操作 CLI — 创建/处理/完成/关闭/重开/升级/报表。

用法:
    python scripts/ticket_ops.py create EMP001 硬件报修 "蓝屏无法启动" --priority 高
    python scripts/ticket_ops.py process TK004 EMP005 "已确认故障"
    python scripts/ticket_ops.py complete TK004 EMP005 "更换主板完成"
    python scripts/ticket_ops.py close TK005 EMP002 "重复工单"
    python scripts/ticket_ops.py reopen TK005 EMP001 "问题再次出现"
    python scripts/ticket_ops.py escalate TK003 EMP001 "超过 24 小时未处理"
    python scripts/ticket_ops.py report --type daily
    python scripts/ticket_ops.py summary TK004
    python scripts/ticket_ops.py list --status 待处理 --department dept-it

可被 cron / scheduler 调用: python scripts/ticket_ops.py report --type daily > report.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# 确保项目根目录在 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.skills.ticket_lifecycle import (
    create_ticket_full,
    process_ticket,
    complete_ticket,
    close_ticket,
    reopen_ticket,
    escalate_ticket,
    get_ticket_summary,
    get_ticket_detail,
)
from src.skills.reporting import ticket_daily_report, ticket_weekly_report, dashboard_summary
from src.tools.db import get_db


def cmd_create(args: argparse.Namespace) -> None:
    result = create_ticket_full(
        user_id=args.user_id,
        issue_type=args.type,
        description=args.description,
        priority=args.priority or "中",
    )
    _print_result(result)


def cmd_process(args: argparse.Namespace) -> None:
    result = process_ticket(
        ticket_id=args.ticket_id,
        operator_id=args.operator_id,
        comment=args.comment or "",
    )
    _print_result(result)


def cmd_complete(args: argparse.Namespace) -> None:
    result = complete_ticket(
        ticket_id=args.ticket_id,
        operator_id=args.operator_id,
        resolution=args.resolution or "",
    )
    _print_result(result)


def cmd_close(args: argparse.Namespace) -> None:
    result = close_ticket(
        ticket_id=args.ticket_id,
        operator_id=args.operator_id,
        reason=args.reason or "",
    )
    _print_result(result)


def cmd_reopen(args: argparse.Namespace) -> None:
    result = reopen_ticket(
        ticket_id=args.ticket_id,
        operator_id=args.operator_id,
        reason=args.reason or "",
    )
    _print_result(result)


def cmd_escalate(args: argparse.Namespace) -> None:
    result = escalate_ticket(
        ticket_id=args.ticket_id,
        operator_id=args.operator_id,
        reason=args.reason or "",
    )
    _print_result(result)


def cmd_report(args: argparse.Namespace) -> None:
    report_type = args.type or "daily"
    dept = args.department or ""

    if report_type == "weekly":
        result = ticket_weekly_report(department_id=dept)
    else:
        result = ticket_daily_report(department_id=dept)

    _print_result(result)


def cmd_summary(args: argparse.Namespace) -> None:
    result = get_ticket_detail(args.ticket_id)
    _print_result(result)


def cmd_list(args: argparse.Namespace) -> None:
    """列出工单。"""
    conditions = []
    params: list = []

    if args.status:
        conditions.append("t.status = ?")
        params.append(args.status)
    if args.department:
        conditions.append("t.department_id = ?")
        params.append(args.department)
    if args.priority:
        conditions.append("t.priority = ?")
        params.append(args.priority)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    limit = args.limit or 50

    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT t.ticket_id, t.issue_type, t.priority, t.status, t.description,
                      t.assigned_to, t.created_at, u.name as user_name
               FROM it_tickets t
               JOIN users u ON t.user_id = u.user_id
               {where}
               ORDER BY t.created_at DESC LIMIT ?""",
            params + [limit],
        ).fetchall()

    tickets = [dict(r) for r in rows]
    print(f"\n共 {len(tickets)} 条工单:\n")
    for t in tickets:
        print(f"  [{t['ticket_id']}] {t['issue_type']} | {t['priority']}优先级 | {t['status']}")
        print(f"    申请人: {t['user_name']} | 受理人: {t['assigned_to']} | {t['created_at'][:10]}")
        print(f"    描述: {t['description'][:80]}")
        print()


def cmd_dashboard(args: argparse.Namespace) -> None:
    dept = args.department or ""
    result = dashboard_summary(department_id=dept)
    _print_result(result)


def _print_result(result: dict) -> None:
    """打印结果 — JSON 格式，便于管道处理。"""
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="工单操作 CLI — 工单全生命周期管理",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/ticket_ops.py create EMP001 硬件报修 "蓝屏无法启动"
  python scripts/ticket_ops.py process TK004 EMP005
  python scripts/ticket_ops.py report --type weekly
  python scripts/ticket_ops.py list --status 待处理
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = sub.add_parser("create", help="创建工单")
    p_create.add_argument("user_id", help="员工ID")
    p_create.add_argument("type", help="问题类型（硬件报修/软件安装/网络问题/账号问题/设备申领/其他）")
    p_create.add_argument("description", help="问题描述")
    p_create.add_argument("--priority", default="中", choices=["高", "中", "低"], help="优先级")
    p_create.set_defaults(func=cmd_create)

    # process
    p_process = sub.add_parser("process", help="开始处理工单")
    p_process.add_argument("ticket_id", help="工单ID")
    p_process.add_argument("operator_id", help="操作人ID")
    p_process.add_argument("--comment", help="处理备注")
    p_process.set_defaults(func=cmd_process)

    # complete
    p_complete = sub.add_parser("complete", help="完成工单")
    p_complete.add_argument("ticket_id", help="工单ID")
    p_complete.add_argument("operator_id", help="操作人ID")
    p_complete.add_argument("--resolution", help="解决方案")
    p_complete.set_defaults(func=cmd_complete)

    # close
    p_close = sub.add_parser("close", help="关闭工单")
    p_close.add_argument("ticket_id", help="工单ID")
    p_close.add_argument("operator_id", help="操作人ID")
    p_close.add_argument("--reason", help="关闭原因")
    p_close.set_defaults(func=cmd_close)

    # reopen
    p_reopen = sub.add_parser("reopen", help="重开工单")
    p_reopen.add_argument("ticket_id", help="工单ID")
    p_reopen.add_argument("operator_id", help="操作人ID")
    p_reopen.add_argument("--reason", help="重开原因")
    p_reopen.set_defaults(func=cmd_reopen)

    # escalate
    p_esc = sub.add_parser("escalate", help="升级工单")
    p_esc.add_argument("ticket_id", help="工单ID")
    p_esc.add_argument("operator_id", help="操作人ID")
    p_esc.add_argument("--reason", help="升级原因")
    p_esc.set_defaults(func=cmd_escalate)

    # report
    p_report = sub.add_parser("report", help="工单报表")
    p_report.add_argument("--type", default="daily", choices=["daily", "weekly"], help="报表类型")
    p_report.add_argument("--department", help="部门筛选")
    p_report.set_defaults(func=cmd_report)

    # summary
    p_sum = sub.add_parser("summary", help="查看工单详情")
    p_sum.add_argument("ticket_id", help="工单ID")
    p_sum.set_defaults(func=cmd_summary)

    # list
    p_list = sub.add_parser("list", help="列出工单")
    p_list.add_argument("--status", help="状态筛选（待处理/处理中/已完成/已关闭）")
    p_list.add_argument("--department", help="部门筛选")
    p_list.add_argument("--priority", help="优先级筛选")
    p_list.add_argument("--limit", type=int, default=50, help="最大条数")
    p_list.set_defaults(func=cmd_list)

    # dashboard
    p_dash = sub.add_parser("dashboard", help="综合仪表盘")
    p_dash.add_argument("--department", help="部门筛选")
    p_dash.set_defaults(func=cmd_dashboard)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
