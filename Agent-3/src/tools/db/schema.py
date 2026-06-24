"""数据库 DDL -- 所有 CREATE TABLE 语句."""

from __future__ import annotations

_SCHEMA = """
-- ═══════════════════════════════════════════════════════════════
-- v1 遗留表(保留兼容,新代码优先使用 v2 表)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS employees (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   TEXT    UNIQUE NOT NULL,
    annual    INTEGER NOT NULL DEFAULT 0,
    sick      INTEGER NOT NULL DEFAULT 0,
    personal  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS leave_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id  TEXT    UNIQUE NOT NULL,
    user_id     TEXT    NOT NULL,
    leave_type  TEXT    NOT NULL,
    start_date  TEXT    NOT NULL,
    end_date    TEXT    NOT NULL,
    reason      TEXT    NOT NULL DEFAULT '',
    status      TEXT    NOT NULL DEFAULT 'pending',
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS it_tickets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id     TEXT    UNIQUE NOT NULL,
    user_id       TEXT    NOT NULL,
    department_id TEXT    NOT NULL DEFAULT '',
    issue_type    TEXT    NOT NULL,
    description   TEXT    NOT NULL,
    priority      TEXT    NOT NULL DEFAULT '中',
    status        TEXT    NOT NULL DEFAULT '待处理',
    assigned_to   TEXT    NOT NULL DEFAULT '待分配',
    created_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ticket_user ON it_tickets(user_id, status);
CREATE INDEX IF NOT EXISTS idx_ticket_created ON it_tickets(created_at);

CREATE TABLE IF NOT EXISTS inventory (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT    UNIQUE NOT NULL,
    total     INTEGER NOT NULL DEFAULT 0,
    available INTEGER NOT NULL DEFAULT 0,
    brand     TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS contracts (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT    UNIQUE NOT NULL,
    content TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS compliance_rules (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT    UNIQUE NOT NULL,
    risk    TEXT    NOT NULL,
    finding TEXT    NOT NULL
);

-- ═══════════════════════════════════════════════════════════════
-- v2 企业核心表
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS departments (
    id            TEXT PRIMARY KEY,           -- dept-eng
    name          TEXT    UNIQUE NOT NULL,    -- 工程部
    manager_id    TEXT,                       -- 部门负责人 user_id
    parent_id     TEXT REFERENCES departments(id),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    user_id       TEXT PRIMARY KEY,           -- EMP001
    name          TEXT    NOT NULL,           -- 张三
    department_id TEXT    NOT NULL REFERENCES departments(id),
    manager_id    TEXT REFERENCES users(user_id),
    role          TEXT    NOT NULL DEFAULT 'employee',  -- employee/manager/hr/admin
    hire_date     TEXT    NOT NULL,           -- 2020-03-01
    tenure_years  REAL    NOT NULL DEFAULT 0,
    annual        INTEGER NOT NULL DEFAULT 0, -- 年假总额(按工龄档位)
    sick          INTEGER NOT NULL DEFAULT 5,
    personal      INTEGER NOT NULL DEFAULT 2,
    password_hash TEXT    NOT NULL DEFAULT '', -- pbkdf2:sha256:600000$salt$hash
    status        TEXT    NOT NULL DEFAULT 'active',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_users_dept ON users(department_id);
CREATE INDEX IF NOT EXISTS idx_users_manager ON users(manager_id);

CREATE TABLE IF NOT EXISTS leave_records (
    id            TEXT PRIMARY KEY,           -- UUID
    user_id       TEXT    NOT NULL REFERENCES users(user_id),
    leave_type    TEXT    NOT NULL CHECK (leave_type IN ('年假','病假','事假')),
    start_date    TEXT    NOT NULL,
    end_date      TEXT    NOT NULL,
    total_days    REAL    NOT NULL,
    reason        TEXT    NOT NULL DEFAULT '',
    status        TEXT    NOT NULL DEFAULT 'draft',
    -- status: draft → pending → approved → completed
    --                        ↘ rejected
    --                        ↘ cancelled
    workflow_id   TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_leave_user ON leave_records(user_id, status);

CREATE TABLE IF NOT EXISTS approval_flow (
    id            TEXT PRIMARY KEY,           -- UUID
    record_type   TEXT    NOT NULL,           -- 'leave' | 'expense'
    record_id     TEXT    NOT NULL,           -- 关联 leave_records.id 等
    step          INTEGER NOT NULL CHECK (step >= 1),
    approver_id   TEXT    NOT NULL REFERENCES users(user_id),
    approver_role TEXT    NOT NULL,           -- 'direct_manager' | 'dept_head' | 'hr' | 'finance'
    status        TEXT    NOT NULL DEFAULT 'pending',
    -- status: pending → approved / rejected / skipped
    comment       TEXT,
    decided_at    TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_approval_record ON approval_flow(record_type, record_id);
CREATE INDEX IF NOT EXISTS idx_approval_approver ON approval_flow(approver_id, status);

CREATE TABLE IF NOT EXISTS task_state (
    workflow_id   TEXT PRIMARY KEY,
    user_id       TEXT    NOT NULL,
    query         TEXT    NOT NULL,
    plan_json     TEXT    NOT NULL DEFAULT '{}',   -- JSON string
    current_step  TEXT,
    step_results  TEXT    NOT NULL DEFAULT '{}',   -- JSON string
    status        TEXT    NOT NULL DEFAULT 'running',
    session_id    TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    completed_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_task_user ON task_state(user_id, status);

CREATE TABLE IF NOT EXISTS expense_reports (
    id            TEXT PRIMARY KEY,
    user_id       TEXT    NOT NULL REFERENCES users(user_id),
    expense_type  TEXT    NOT NULL,           -- 差旅/办公/招待/其他
    amount        REAL    NOT NULL,
    description   TEXT    NOT NULL DEFAULT '',
    receipt_url   TEXT,
    metadata      TEXT,                       -- JSON: trip/overtime 结构化字段
    status        TEXT    NOT NULL DEFAULT 'draft',
    -- status: draft → pending → approved → reimbursed
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_expense_user ON expense_reports(user_id, status);

CREATE TABLE IF NOT EXISTS budgets (
    id            TEXT PRIMARY KEY,
    department_id TEXT    NOT NULL REFERENCES departments(id),
    year          INTEGER NOT NULL,
    category      TEXT    NOT NULL,           -- 办公/差旅/招待/设备
    total         REAL    NOT NULL DEFAULT 0,
    used          REAL    NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS policy_documents (
    id            TEXT PRIMARY KEY,
    category      TEXT    NOT NULL,           -- hr/it/legal/finance
    title         TEXT    NOT NULL,
    content       TEXT    NOT NULL,
    source_path   TEXT    NOT NULL DEFAULT '',
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_policy_category ON policy_documents(category, title);

CREATE TABLE IF NOT EXISTS salary_profiles (
    user_id       TEXT PRIMARY KEY REFERENCES users(user_id),
    grade         TEXT    NOT NULL,
    base_salary   REAL    NOT NULL,
    allowance     REAL    NOT NULL DEFAULT 0,
    social_rate   REAL    NOT NULL DEFAULT 0,
    housing_rate  REAL    NOT NULL DEFAULT 0,
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_salary_user ON salary_profiles(user_id);

CREATE INDEX IF NOT EXISTS idx_budget_dept ON budgets(department_id, year);

CREATE TABLE IF NOT EXISTS audit_log (
    id            TEXT PRIMARY KEY,
    user_id       TEXT    NOT NULL,
    action        TEXT    NOT NULL,       -- 'tool_call' | 'approval' | 'access' | 'error'
    resource      TEXT,                   -- tool name / record id
    detail        TEXT    NOT NULL DEFAULT '{}',  -- JSON string
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);

CREATE TABLE IF NOT EXISTS conversation_memory (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT    NOT NULL,
    user_id       TEXT    NOT NULL,
    role          TEXT    NOT NULL,           -- user / assistant / system / tool / summary
    content       TEXT    NOT NULL,
    metadata      TEXT    NOT NULL DEFAULT '{}',  -- JSON
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_conv_session ON conversation_memory(session_id, created_at);

CREATE TABLE IF NOT EXISTS notifications (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    type        TEXT NOT NULL,   -- 'approval_result' | 'pending_approval' | 'system'
    title       TEXT NOT NULL,
    body        TEXT NOT NULL DEFAULT '',
    is_read     INTEGER NOT NULL DEFAULT 0,
    link_type   TEXT,            -- 'leave' | 'expense' | null
    link_id     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read, created_at);

CREATE TABLE IF NOT EXISTS feedback (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT,
    message_index  INTEGER,
    value          INTEGER,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attendance_records (
    id          TEXT    PRIMARY KEY,
    user_id     TEXT    NOT NULL,
    punch_type  TEXT    NOT NULL,
    punch_time  TEXT    NOT NULL,
    date        TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attendance_user_date ON attendance_records(user_id, date);

-- ═══════════════════════════════════════════════════════════════
-- Schema 版本管理
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash  TEXT    NOT NULL,
    user_id     TEXT    NOT NULL REFERENCES users(user_id),
    expires_at  TEXT    NOT NULL,
    revoked     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_tokens(user_id, revoked);
"""
