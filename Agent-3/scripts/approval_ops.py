#!/usr/bin/env python3
"""审批操作 CLI — 查看/审批/驳回。

用法:
    python scripts/approval_ops.py pending EMP002
    python scripts/approval_ops.py approve <step_id> EMP002 --comment "同意"
    python scripts/approval_ops.py reject <step_id> EMP002 --comment "不符合规定"
    python scripts/approval_ops.py status leave <record_id>
    python scripts/approval_ops.py submit leave EMP001 5 --leave_type 年假
    python scripts/approval_ops.py submit expense EMP001 8000 --description "出差住宿"
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.skills.approval_engine import (
    approve_step,
    reject_step,
    get_approval_status,
    get_pending_approvals,
    submit_for_approval,
)


def cmd_pending(args: argparse.Namespace) -> None:
    result = get_pending_approvals(args.approver_id)
    _print_result(result)


def cmd_approve(args: argparse.Namespace) -> None:
    result = approve_step(
        step_id=args.step_id,
        approver_id=args.approver_id,
        comment=args.comment or "",
    )
    _print_result(result)


def cmd_reject(args: argparse.Namespace) -> None:
    result = reject_step(
        step_id=args.step_id,
        approver_id=args.approver_id,
        comment=args.comment or "",
    )
    _print_result(result)


def cmd_status(args: argparse.Namespace) -> None:
    result = get_approval_status(args.record_type, args.record_id)
    _print_result(result)


def cmd_submit(args: argparse.Namespace) -> None:
    result = submit_for_approval(
        record_type=args.record_type,
        record_id=args.record_id,
        user_id=args.user_id,
        threshold_value=args.threshold,
    )
    _print_result(result)


def _print_result(result: dict) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="审批操作 CLI — 请假/报销审批管理",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/approval_ops.py pending EMP002
  python scripts/approval_ops.py approve abc123 EMP002 --comment "同意"
  python scripts/approval_ops.py reject abc123 EMP002 --comment "材料不全"
  python scripts/approval_ops.py status leave REC001
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # pending
    p_pending = sub.add_parser("pending", help="查看待审批列表")
    p_pending.add_argument("approver_id", help="审批人ID")
    p_pending.set_defaults(func=cmd_pending)

    # approve
    p_approve = sub.add_parser("approve", help="审批通过")
    p_approve.add_argument("step_id", help="审批步骤ID")
    p_approve.add_argument("approver_id", help="审批人ID")
    p_approve.add_argument("--comment", help="审批意见")
    p_approve.set_defaults(func=cmd_approve)

    # reject
    p_reject = sub.add_parser("reject", help="驳回")
    p_reject.add_argument("step_id", help="审批步骤ID")
    p_reject.add_argument("approver_id", help="审批人ID")
    p_reject.add_argument("--comment", help="驳回理由")
    p_reject.set_defaults(func=cmd_reject)

    # status
    p_status = sub.add_parser("status", help="查看审批进度")
    p_status.add_argument("record_type", choices=["leave", "expense"], help="记录类型")
    p_status.add_argument("record_id", help="记录ID")
    p_status.set_defaults(func=cmd_status)

    # submit (for already-created records)
    p_submit = sub.add_parser("submit", help="提交已有记录进入审批流")
    p_submit.add_argument("record_type", choices=["leave", "expense"], help="记录类型")
    p_submit.add_argument("user_id", help="申请人ID")
    p_submit.add_argument("threshold", type=float, help="阈值（请假天数/报销金额）")
    p_submit.add_argument("--record_id", default="", help="已有记录ID（可选）")
    p_submit.set_defaults(func=cmd_submit)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
