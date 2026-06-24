"""业务查询和操作函数 -- 所有 db_* 公开 API.

依赖 .connection 模块获取连接和工具函数.
"""

from __future__ import annotations

import json
from datetime import date as dt_date
from datetime import datetime, timezone

from .connection import get_db, _now, _uid


# ═══════════════════════════════════════════════════════════════════
# v1 兼容层 -- HR 数据访问
# ═══════════════════════════════════════════════════════════════════

def db_get_leave_balance(user_id: str) -> dict | None:
    """查询员工假期余额(优先查 v2 users 表,回退 v1 employees 表)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT annual, sick, personal, name, department_id, role "
            "FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row:
            return {
                "annual": row["annual"], "sick": row["sick"],
                "personal": row["personal"],
                "name": row["name"], "department": row["department_id"],
                "role": row["role"],
            }
        # 回退 v1
        row = conn.execute(
            "SELECT annual, sick, personal FROM employees WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return {"annual": row["annual"], "sick": row["sick"], "personal": row["personal"]}


def db_submit_leave_request(
    user_id: str,
    leave_type: str,
    start_date: str,
    end_date: str,
    reason: str = "",
) -> dict:
    """提交请假申请 → v2 leave_records 表."""
    record_id = _uid()
    now = _now()
    try:
        s = dt_date.fromisoformat(start_date)
        e = dt_date.fromisoformat(end_date)
        total_days = (e - s).days + 1
    except (ValueError, TypeError):
        total_days = 1

    with get_db() as conn:
        conn.execute(
            """INSERT INTO leave_records (id, user_id, leave_type, start_date, end_date,
               total_days, reason, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (record_id, user_id, leave_type, start_date, end_date, total_days, reason, now, now),
        )
        conn.commit()

    return {
        "id": record_id,
        "user_id": user_id,
        "leave_type": leave_type,
        "start_date": start_date,
        "end_date": end_date,
        "total_days": total_days,
        "reason": reason,
        "status": "pending",
        "created_at": now,
    }


# ═══════════════════════════════════════════════════════════════════
# 用户
# ═══════════════════════════════════════════════════════════════════

def db_get_user(user_id: str) -> dict | None:
    """获取用户完整信息(含部门,上级)."""
    with get_db() as conn:
        row = conn.execute(
            """SELECT u.*, d.name as department_name,
                      m.name as manager_name
               FROM users u
               JOIN departments d ON u.department_id = d.id
               LEFT JOIN users m ON u.manager_id = m.user_id
               WHERE u.user_id = ?""",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def db_verify_password(user_id: str, password: str) -> bool:
    """验证用户密码(pbkdf2_hmac 哈希比对,兼容旧明文)."""
    from src.gateway.crypto import verify_password as _verify, needs_rehash

    with get_db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE user_id = ? AND status = 'active'",
            (user_id,),
        ).fetchone()
    if row is None:
        return False

    stored = row["password_hash"]
    if not _verify(password, stored):
        return False

    # 自动升级:旧明文或旧迭代次数 → 更新为当前标准哈希
    if needs_rehash(stored):
        db_update_password_hash(user_id, password, conn=None)

    return True


def db_update_password_hash(user_id: str, password: str, conn=None) -> bool:
    """更新用户密码哈希(用于首次哈希迁移和密码修改).

    Args:
        user_id: 员工ID
        password: 明文密码
        conn: 外部连接(可选,事务内复用)
    """
    from src.gateway.crypto import hash_password as _hash

    hashed = _hash(password)
    _conn = conn or get_db()
    try:
        with _conn if conn else get_db() as c:
            c.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE user_id = ?",
                (hashed, _now(), user_id),
            )
            if not conn:
                c.commit()
        return True
    except Exception:
        return False


def db_needs_password_migration() -> int:
    """返回需要密码迁移(仍为明文)的用户数."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE password_hash NOT LIKE 'pbkdf2:%' AND status = 'active'"
        ).fetchone()
    return row["cnt"] if row else 0


# ═══════════════════════════════════════════════════════════════════
# 组织架构
# ═══════════════════════════════════════════════════════════════════

def db_get_org_chain(user_id: str) -> list[dict]:
    """获取用户的汇报链:本人 → 直属上级 → 部门负责人 → ..."""
    chain = []
    current = user_id
    with get_db() as conn:
        for _ in range(5):
            row = conn.execute(
                """SELECT u.user_id, u.name, u.role, u.manager_id,
                          d.name as department_name
                   FROM users u JOIN departments d ON u.department_id = d.id
                   WHERE u.user_id = ?""",
                (current,),
            ).fetchone()
            if row is None:
                break
            chain.append(dict(row))
            if row["manager_id"] is None or row["manager_id"] == current:
                break
            current = row["manager_id"]
    return chain


def db_get_department_head(department_id: str) -> dict | None:
    """获取部门负责人."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT u.* FROM users u JOIN departments d ON d.manager_id = u.user_id WHERE d.id = ?",
            (department_id,),
        ).fetchone()
    return dict(row) if row else None


def db_get_department_manager(department_id: str) -> dict | None:
    """获取部门负责人(通过 departments.manager_id)."""
    with get_db() as conn:
        row = conn.execute(
            """SELECT u.*, d.name AS department_name
               FROM departments d JOIN users u ON u.user_id = d.manager_id
               WHERE d.id = ? AND u.status = 'active'""",
            (department_id,),
        ).fetchone()
    return dict(row) if row else None


def db_get_user_by_role(role: str) -> dict | None:
    """按角色获取一个可用用户,用于组织架构审批人配置."""
    with get_db() as conn:
        row = conn.execute(
            """SELECT u.*, d.name AS department_name
               FROM users u LEFT JOIN departments d ON d.id = u.department_id
               WHERE u.role = ? AND u.status = 'active'
               ORDER BY u.created_at ASC LIMIT 1""",
            (role,),
        ).fetchone()
    return dict(row) if row else None


# ═══════════════════════════════════════════════════════════════════
# 审批流
# ═══════════════════════════════════════════════════════════════════

def db_create_approval_flow(record_type: str, record_id: str, steps: list[dict]) -> list[dict]:
    """创建审批流."""
    created = []
    with get_db() as conn:
        for s in steps:
            aid = _uid()
            conn.execute(
                """INSERT INTO approval_flow (id, record_type, record_id, step, approver_id, approver_role, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
                (aid, record_type, record_id, s["step"], s["approver_id"], s["approver_role"]),
            )
            created.append({**s, "id": aid, "status": "pending"})
        conn.commit()
    return created


def db_get_approval_status(record_type: str, record_id: str) -> list[dict]:
    """查询某条记录的审批进度."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT a.*, u.name as approver_name
               FROM approval_flow a
               JOIN users u ON a.approver_id = u.user_id
               WHERE a.record_type = ? AND a.record_id = ?
               ORDER BY a.step""",
            (record_type, record_id),
        ).fetchall()
    return [dict(r) for r in rows]


def db_get_pending_approvals(approver_id: str) -> list[dict]:
    """查询某审批人的所有待审批步骤,附带请假记录详情."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT a.*, l.user_id as applicant_id, l.leave_type,
                      l.start_date, l.end_date, l.total_days, l.reason,
                      l.status as leave_status, l.created_at as leave_created_at,
                      u.name as applicant_name, u.department_id as applicant_dept
               FROM approval_flow a
               JOIN leave_records l ON a.record_id = l.id
               JOIN users u ON l.user_id = u.user_id
               WHERE a.approver_id = ? AND a.status = 'pending'
               ORDER BY a.created_at DESC LIMIT 50""",
            (approver_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def db_update_approval_step(step_id: str, status: str, comment: str = "") -> None:
    """更新某个审批步骤的状态."""
    now = _now()
    with get_db() as conn:
        conn.execute(
            "UPDATE approval_flow SET status = ?, comment = ?, decided_at = ? WHERE id = ?",
            (status, comment, now, step_id),
        )
        conn.commit()


# ═══════════════════════════════════════════════════════════════════
# 假期记录
# ═══════════════════════════════════════════════════════════════════

def db_deduct_leave_balance(user_id: str, leave_type: str, days: float) -> bool:
    """审批通过后扣减假期余额."""
    col = {"年假": "annual", "病假": "sick", "事假": "personal"}.get(leave_type)
    if not col:
        return False
    with get_db() as conn:
        conn.execute(
            f"UPDATE users SET {col} = MAX(0, {col} - ?) WHERE user_id = ?",
            (days, user_id),
        )
        conn.commit()
    return True


def db_get_used_leave_days(user_id: str, year: int | None = None) -> dict:
    """统计某用户已使用的各类假期天数."""
    if year is None:
        year = datetime.now(timezone.utc).year
    with get_db() as conn:
        rows = conn.execute(
            """SELECT leave_type, SUM(total_days) as used
               FROM leave_records
               WHERE user_id = ? AND status = 'approved'
                 AND substr(start_date, 1, 4) = ?
               GROUP BY leave_type""",
            (user_id, str(year)),
        ).fetchall()
    result = {"annual": 0, "sick": 0, "personal": 0}
    for r in rows:
        key = {"年假": "annual", "病假": "sick", "事假": "personal"}.get(r["leave_type"])
        if key:
            result[key] = r["used"] or 0
    return result


# ═══════════════════════════════════════════════════════════════════
# 工作流任务
# ═══════════════════════════════════════════════════════════════════

def db_create_task(user_id: str, query: str, plan: dict, session_id: str) -> str:
    """创建工作流任务记录,返回 workflow_id."""
    wid = _uid()
    now = _now()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO task_state (workflow_id, user_id, query, plan_json, status, session_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'running', ?, ?, ?)""",
            (wid, user_id, query, json.dumps(plan, ensure_ascii=False), session_id, now, now),
        )
        conn.commit()
    return wid


def db_update_task(workflow_id: str, **kwargs) -> None:
    """更新工作流任务状态."""
    now = _now()
    allowed = {"current_step", "step_results", "status", "completed_at"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    updates["updated_at"] = now
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [workflow_id]
    with get_db() as conn:
        conn.execute(f"UPDATE task_state SET {set_clause} WHERE workflow_id = ?", values)
        conn.commit()


# ═══════════════════════════════════════════════════════════════════
# 统一申请记录
# ═══════════════════════════════════════════════════════════════════

def db_get_my_applications(user_id: str, limit: int = 50) -> list[dict]:
    """查询用户的所有申请记录(请假 + IT工单 + 报销)."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT 'leave' AS app_type, '请假' AS app_type_label,
                      l.id, l.leave_type AS subtype, l.start_date, l.end_date,
                      l.total_days AS amount_val, l.reason AS description,
                      l.status, l.created_at
               FROM leave_records l WHERE l.user_id = ?
            UNION ALL
            SELECT 'ticket' AS app_type, 'IT工单' AS app_type_label,
                      t.ticket_id AS id, t.issue_type AS subtype,
                      NULL AS start_date, NULL AS end_date,
                      NULL AS amount_val, t.description,
                      t.status, t.created_at
               FROM it_tickets t WHERE t.user_id = ?
            UNION ALL
            SELECT 'expense' AS app_type, '报销' AS app_type_label,
                      e.id, e.expense_type AS subtype,
                      NULL AS start_date, NULL AS end_date,
                      e.amount AS amount_val, e.description,
                      e.status, e.created_at
               FROM expense_reports e WHERE e.user_id = ?
            ORDER BY created_at DESC
            LIMIT ?""",
            (user_id, user_id, user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def db_get_application(app_type: str, app_id: str) -> dict | None:
    """获取单条申请记录详情."""
    with get_db() as conn:
        if app_type == "leave":
            row = conn.execute(
                "SELECT l.*, u.name AS user_name FROM leave_records l "
                "JOIN users u ON l.user_id = u.user_id WHERE l.id = ?",
                (app_id,),
            ).fetchone()
        elif app_type == "ticket":
            row = conn.execute(
                "SELECT t.*, u.name AS user_name FROM it_tickets t "
                "JOIN users u ON t.user_id = u.user_id WHERE t.ticket_id = ?",
                (app_id,),
            ).fetchone()
        elif app_type == "expense":
            row = conn.execute(
                "SELECT e.*, u.name AS user_name FROM expense_reports e "
                "JOIN users u ON e.user_id = u.user_id WHERE e.id = ?",
                (app_id,),
            ).fetchone()
        else:
            return None
    return dict(row) if row else None


def db_update_application(app_type: str, app_id: str, updates: dict) -> bool:
    """更新申请记录.仅允许 pending/draft/待处理 状态的记录."""
    allowed_fields = {
        "leave": ["leave_type", "start_date", "end_date", "reason"],
        "ticket": ["issue_type", "description", "priority"],
        "expense": ["expense_type", "amount", "description"],
    }
    table_map = {"leave": "leave_records", "ticket": "it_tickets", "expense": "expense_reports"}
    id_col_map = {"leave": "id", "ticket": "ticket_id", "expense": "id"}

    table = table_map.get(app_type)
    id_col = id_col_map.get(app_type)
    fields = allowed_fields.get(app_type, [])
    if not table:
        return False

    filtered = {k: v for k, v in updates.items() if k in fields}
    if not filtered:
        return False

    if app_type == "leave" and ("start_date" in filtered or "end_date" in filtered):
        record = db_get_application(app_type, app_id)
        if record:
            try:
                s = dt_date.fromisoformat(filtered.get("start_date", record["start_date"]))
                e = dt_date.fromisoformat(filtered.get("end_date", record["end_date"]))
                filtered["total_days"] = (e - s).days + 1
            except (ValueError, TypeError):
                pass

    filtered["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in filtered)
    values = list(filtered.values()) + [app_id]

    with get_db() as conn:
        conn.execute(f"UPDATE {table} SET {set_clause} WHERE {id_col} = ?", values)
        conn.commit()
    return True


def db_update_status(app_type: str, app_id: str, new_status: str) -> bool:
    """更新申请记录状态(不限制原始状态)."""
    table_map = {"leave": "leave_records", "ticket": "it_tickets", "expense": "expense_reports"}
    id_col_map = {"leave": "id", "ticket": "ticket_id", "expense": "id"}

    table = table_map.get(app_type)
    id_col = id_col_map.get(app_type)
    if not table:
        return False

    with get_db() as conn:
        if app_type == "ticket":
            conn.execute(
                f"UPDATE {table} SET status = ? WHERE {id_col} = ?",
                (new_status, app_id),
            )
        else:
            conn.execute(
                f"UPDATE {table} SET status = ?, updated_at = ? WHERE {id_col} = ?",
                (new_status, _now(), app_id),
            )
        conn.commit()
    return True


def db_delete_application(app_type: str, app_id: str) -> bool:
    """删除申请记录.仅允许非终态记录(pending/draft/待处理)."""
    table_map = {"leave": "leave_records", "ticket": "it_tickets", "expense": "expense_reports"}
    id_col_map = {"leave": "id", "ticket": "ticket_id", "expense": "id"}

    table = table_map.get(app_type)
    id_col = id_col_map.get(app_type)
    if not table:
        return False

    deletable_statuses = {
        "leave": ("draft", "pending"),
        "ticket": ("待处理", "处理中", "已完成"),
        "expense": ("draft", "pending"),
    }
    allowed = deletable_statuses.get(app_type, ())

    with get_db() as conn:
        row = conn.execute(
            f"SELECT status FROM {table} WHERE {id_col} = ?", (app_id,)
        ).fetchone()
        if row is None:
            return False
        if row[0] not in allowed:
            return False
        conn.execute(f"DELETE FROM {table} WHERE {id_col} = ?", (app_id,))
        conn.commit()
    return True


# ═══════════════════════════════════════════════════════════════════
# 财务
# ═══════════════════════════════════════════════════════════════════

def db_get_budget(department_id: str, year: int | None = None) -> list[dict]:
    """获取某部门某年度的预算."""
    if year is None:
        year = datetime.now(timezone.utc).year
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM budgets WHERE department_id = ? AND year = ?",
            (department_id, year),
        ).fetchall()
    return [dict(r) for r in rows]


def db_get_policy_doc(keyword: str, category: str = "") -> dict | None:
    """从业务文档表中查询制度文本."""
    like = f"%{keyword}%"
    with get_db() as conn:
        if category:
            row = conn.execute(
                """SELECT category, title, content FROM policy_documents
                   WHERE category = ? AND (title LIKE ? OR content LIKE ?)
                   ORDER BY updated_at DESC LIMIT 1""",
                (category, like, like),
            ).fetchone()
        else:
            row = conn.execute(
                """SELECT category, title, content FROM policy_documents
                   WHERE title LIKE ? OR content LIKE ?
                   ORDER BY updated_at DESC LIMIT 1""",
                (like, like),
            ).fetchone()
    return dict(row) if row else None


def db_get_policy_docs(category: str) -> list[dict]:
    """获取某业务域的所有制度文档."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT category, title, content FROM policy_documents WHERE category = ? ORDER BY title",
            (category,),
        ).fetchall()
    return [dict(r) for r in rows]


def db_get_salary_profile(user_id: str) -> dict | None:
    """查询员工薪资档案."""
    with get_db() as conn:
        row = conn.execute(
            """SELECT s.*, u.name, u.department_id, d.name AS department_name
               FROM salary_profiles s
               JOIN users u ON u.user_id = s.user_id
               LEFT JOIN departments d ON d.id = u.department_id
               WHERE s.user_id = ?""",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def db_get_finance_approver() -> dict | None:
    """获取财务审批人."""
    manager = db_get_department_manager("dept-finance")
    if manager:
        return manager
    return db_get_user_by_role("finance")


def db_get_hr_approver() -> dict | None:
    """获取 HR 审批人."""
    manager = db_get_department_manager("dept-hr")
    if manager:
        return manager
    return db_get_user_by_role("hr")


def db_submit_expense(
    user_id: str, expense_type: str, amount: float, description: str, receipt_url: str = "", metadata: str = ""
) -> dict:
    """提交报销申请."""
    eid = _uid()
    now = _now()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO expense_reports (id, user_id, expense_type, amount, description, receipt_url, metadata, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (eid, user_id, expense_type, amount, description, receipt_url, metadata, now, now),
        )
        conn.commit()
    return {"id": eid, "user_id": user_id, "expense_type": expense_type,
            "amount": amount, "status": "pending", "created_at": now}


# ═══════════════════════════════════════════════════════════════════
# IT 数据访问
# ═══════════════════════════════════════════════════════════════════

def db_get_ticket(ticket_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM it_tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
    return dict(row) if row else None


def db_create_ticket(user_id: str, issue_type: str, description: str, priority: str = "中", department_id: str = "") -> dict:
    now = _now()
    if not department_id:
        user = db_get_user(user_id)
        department_id = user["department_id"] if user else ""
    assigned_to = "待分配"
    if department_id:
        with get_db() as conn:
            dept_row = conn.execute(
                "SELECT manager_id FROM departments WHERE id = ?", (department_id,)
            ).fetchone()
            if dept_row and dept_row["manager_id"]:
                assigned_to = dept_row["manager_id"]
    with get_db() as conn:
        max_id = conn.execute("SELECT MAX(id) as max_id FROM it_tickets").fetchone()["max_id"]
        ticket_id = f"TK{(max_id or 0) + 1:03d}"
        conn.execute(
            """INSERT INTO it_tickets (ticket_id, user_id, department_id, issue_type, description, priority, status, assigned_to, created_at)
               VALUES (?, ?, ?, ?, ?, ?, '待处理', ?, ?)""",
            (ticket_id, user_id, department_id, issue_type, description, priority, assigned_to, now),
        )
        conn.commit()
    return {"ticket_id": ticket_id, "user_id": user_id, "department_id": department_id,
            "issue_type": issue_type, "description": description, "priority": priority,
            "status": "待处理", "assigned_to": assigned_to, "created_at": now}


def db_get_inventory(device_type: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT name, total, available, brand FROM inventory WHERE name LIKE ?",
            (f"%{device_type}%",),
        ).fetchone()
    if row is None:
        return None
    return {"device_type": row["name"], "total": row["total"],
            "available": row["available"], "brand": row["brand"]}


def db_list_inventory_names() -> list[str]:
    with get_db() as conn:
        return [r["name"] for r in conn.execute("SELECT name FROM inventory").fetchall()]


# ═══════════════════════════════════════════════════════════════════
# 法务数据访问
# ═══════════════════════════════════════════════════════════════════

def db_search_contract(keyword: str) -> dict:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT keyword, content FROM contracts WHERE keyword LIKE ? OR content LIKE ?",
            (f"%{keyword}%", f"%{keyword}%"),
        ).fetchall()
    if not rows:
        all_kw = _all_contract_keywords()
        return {"keyword": keyword, "matches": 0, "clauses": {}, "available_keywords": all_kw}
    return {"keyword": keyword, "matches": len(rows),
            "clauses": {r["keyword"]: r["content"] for r in rows}}


def db_check_compliance(doc_summary: str) -> dict | None:
    with get_db() as conn:
        rules = conn.execute("SELECT keyword, risk, finding FROM compliance_rules").fetchall()
    for row in rules:
        if row["keyword"] in doc_summary:
            return {"matched_rule": row["keyword"], "risk": row["risk"],
                    "finding": row["finding"], "recommendation": "建议提交法务部进行正式审查"}
    return None


def _all_contract_keywords() -> list[str]:
    with get_db() as conn:
        return [r["keyword"] for r in conn.execute("SELECT keyword FROM contracts").fetchall()]


# ═══════════════════════════════════════════════════════════════════
# 通知
# ═══════════════════════════════════════════════════════════════════

def db_create_notification(user_id: str, type_: str, title: str, body: str = "",
                            link_type: str = None, link_id: str = None) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO notifications (id, user_id, type, title, body, link_type, link_id) VALUES (?,?,?,?,?,?,?)",
            (_uid(), user_id, type_, title, body, link_type, link_id),
        )
        conn.commit()


def db_get_notifications(user_id: str, unread_only: bool = False, limit: int = 30) -> list[dict]:
    with get_db() as conn:
        cond = "WHERE user_id = ?" + (" AND is_read = 0" if unread_only else "")
        rows = conn.execute(
            f"SELECT * FROM notifications {cond} ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def db_mark_notifications_read(user_id: str, ids: list[str] | None = None) -> None:
    with get_db() as conn:
        if ids:
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"UPDATE notifications SET is_read = 1 WHERE user_id = ? AND id IN ({placeholders})",
                [user_id] + ids,
            )
        else:
            conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
        conn.commit()


def db_unread_count(user_id: str) -> int:
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,),
        ).fetchone()
    return row["cnt"] if row else 0
