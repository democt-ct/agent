"""财务部工具集 -- SQLite 持久化实现.

工具:
    query_expense_policy  -- 查报销制度
    submit_expense_report -- 提交报销申请
    check_budget          -- 查部门预算余额
    query_salary_structure -- 查薪资构成
    check_travel_policy   -- 查出差标准
"""

from __future__ import annotations

from src.tools.base import ToolDef
from src.tools.db import (
    db_get_budget,
    db_submit_expense,
    db_get_org_chain,
    db_create_approval_flow,
    db_get_finance_approver,
    db_get_policy_doc,
    db_get_salary_profile,
)


# ── 工具实现 ─────────────────────────────────────────────────────

def query_expense_policy(expense_type: str = "") -> dict:
    """查询报销制度(类型/限额/流程)."""
    policy = db_get_policy_doc(expense_type or "报销", "finance") or db_get_policy_doc("报销", "finance")
    if policy is None:
        return {"error": "未找到报销制度记录,请联系财务部维护政策文档"}
    return {
        "policy": policy["title"],
        "expense_type": expense_type or "全部",
        "content": policy["content"],
        "source": policy.get("source_path", ""),
    }


def submit_expense_report(
    user_id: str,
    expense_type: str,
    amount: float,
    description: str,
    receipt_url: str = "",
    metadata: str = "",
) -> dict:
    """提交报销申请.

    Args:
        user_id: 员工ID
        expense_type: 报销类型(差旅/办公/招待/培训/其他)
        amount: 金额(元)
        description: 费用说明
        receipt_url: 发票附件链接(可选)
    """
    valid_types = {"差旅", "办公", "招待", "培训", "其他"}
    if expense_type not in valid_types:
        return {"error": f"无效的报销类型: {expense_type},可选: {', '.join(valid_types)}"}

    if amount <= 0:
        return {"error": "报销金额必须大于0"}

    record = db_submit_expense(user_id, expense_type, amount, description, receipt_url, metadata)

    # 自动创建审批流:直属上级 → 金额≥5000时加财务经理
    chain = db_get_org_chain(user_id)
    steps = []
    direct_manager = chain[1] if len(chain) > 1 else None
    if direct_manager:
        steps.append({"step": 1, "approver_id": direct_manager["user_id"], "approver_role": "direct_manager"})
    if amount >= 5000:
        finance_approver = db_get_finance_approver()
        if finance_approver is None:
            return {"error": "未配置财务审批人,无法提交大额报销"}
        steps.append({"step": len(steps) + 1, "approver_id": finance_approver["user_id"], "approver_role": "finance"})
    if steps:
        db_create_approval_flow("expense", record["id"], steps)

    needs_finance = amount >= 5000
    return {
        "success": True,
        "expense_id": record["id"],
        "amount": amount,
        "approval_steps": len(steps),
        "needs_finance_review": needs_finance,
        "message": (
            f"报销申请已提交({record['id']}),等待审批"
            + (",因金额≥5000元需财务部加签" if needs_finance else "")
        ),
    }


def check_budget(department_id: str, year: int | None = None) -> dict:
    """查询部门预算余额.

    Args:
        department_id: 部门ID,如 dept-eng
        year: 年份,默认当前年
    """
    budgets = db_get_budget(department_id, year)
    if not budgets:
        return {"error": f"未找到部门 {department_id} 的预算记录"}

    items = []
    for b in budgets:
        items.append({
            "category": b["category"],
            "total": b["total"],
            "used": b["used"],
            "remaining": b["total"] - b["used"],
            "usage_pct": round(b["used"] / b["total"] * 100, 1) if b["total"] > 0 else 0,
        })

    total_budget = sum(b["total"] for b in budgets)
    total_used = sum(b["used"] for b in budgets)

    return {
        "department_id": department_id,
        "year": year or budgets[0]["year"],
        "total_budget": total_budget,
        "total_used": total_used,
        "remaining": total_budget - total_used,
        "items": items,
    }


def query_salary_structure(user_id: str) -> dict:
    """查询薪资构成(仅限本人或HR/财务查询).

    Args:
        user_id: 员工ID
    """
    salary = db_get_salary_profile(user_id)
    if salary is None:
        return {"error": f"未找到员工 {user_id} 的薪资档案"}

    policy = db_get_policy_doc("薪资", "finance")
    gross = salary["base_salary"] + salary["allowance"]
    social = round(gross * salary["social_rate"], 2)
    housing = round(gross * salary["housing_rate"], 2)
    return {
        "user_id": user_id,
        "name": salary.get("name"),
        "department": salary.get("department_name"),
        "grade": salary["grade"],
        "components": {
            "base_salary": salary["base_salary"],
            "allowance": salary["allowance"],
            "gross_salary": gross,
        },
        "deductions": {
            "social_insurance_estimate": social,
            "housing_fund_estimate": housing,
        },
        "policy": policy["title"] if policy else "",
        "policy_source": policy.get("source_path", "") if policy else "",
        "updated_at": salary.get("updated_at"),
    }


def check_travel_policy(destination: str = "", days: int = 1) -> dict:
    """查询出差标准(交通/住宿/补助).

    Args:
        destination: 目的地城市
        days: 出差天数
    """
    policy = db_get_policy_doc("出差", "finance")
    if policy is None:
        return {"error": "未找到出差制度记录,请联系财务部维护政策文档"}
    return {
        "policy": policy["title"],
        "destination": destination or "未指定",
        "days": days,
        "content": policy["content"],
        "source": policy.get("source_path", ""),
    }


# ── 工具列表 ─────────────────────────────────────────────────────

FINANCE_TOOLS: list[ToolDef] = [
    ToolDef(
        name="query_expense_policy",
        description="查询报销制度,包括报销类型,限额,审批流程.可指定报销类型(差旅/办公/招待/培训/其他).",
        parameters={
            "type": "object",
            "properties": {
                "expense_type": {
                    "type": "string",
                    "description": "报销类型: 差旅, 办公, 招待, 培训, 其他",
                    "enum": ["差旅", "办公", "招待", "培训", "其他"],
                },
            },
            "required": [],
        },
        implementation=query_expense_policy,
    ),
    ToolDef(
        name="submit_expense_report",
        description="提交报销申请.需提供员工ID,报销类型,金额,费用说明.",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "员工ID"},
                "expense_type": {
                    "type": "string",
                    "description": "报销类型",
                    "enum": ["差旅", "办公", "招待", "培训", "其他"],
                },
                "amount": {"type": "number", "description": "报销金额(元)"},
                "description": {"type": "string", "description": "费用说明"},
                "receipt_url": {"type": "string", "description": "发票附件链接(可选)"},
            },
            "required": ["user_id", "expense_type", "amount", "description"],
        },
        implementation=submit_expense_report,
    ),
    ToolDef(
        name="check_budget",
        description="查询部门预算余额和使用情况.输入部门ID(如 dept-eng),返回预算总额,已用,剩余.",
        parameters={
            "type": "object",
            "properties": {
                "department_id": {"type": "string", "description": "部门ID: dept-eng, dept-hr, dept-it, dept-finance"},
                "year": {"type": "integer", "description": "年份,默认当前年"},
            },
            "required": ["department_id"],
        },
        implementation=check_budget,
        quick_triggers=["预算", "预算余额", "预算使用", "还剩多少预算"],
        quick_args_builder=lambda ctx: {"department_id": getattr(ctx, "department_id", "dept-eng")},
    ),
    ToolDef(
        name="query_salary_structure",
        description="查询薪资构成说明,包括基本工资,社保公积金比例,个税计算.仅限本人或HR/财务查询.",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "员工ID"},
            },
            "required": ["user_id"],
        },
        implementation=query_salary_structure,
        quick_triggers=["工资", "薪资", "工资条", "社保", "公积金", "个税"],
        quick_args_builder=lambda ctx: {"user_id": ctx.user_id},
    ),
    ToolDef(
        name="check_travel_policy",
        description="查询出差标准:交通等级,住宿限额,餐饮补助.输入目的地城市和预计天数.",
        parameters={
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "目的地城市"},
                "days": {"type": "integer", "description": "出差天数"},
            },
            "required": [],
        },
        implementation=check_travel_policy,
    ),
]
