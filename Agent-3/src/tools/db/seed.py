"""种子数据 -- 测试数据填充(仅 dev 环境调用).

bootstrap_company_workspace() 是幂等的:所有 INSERT 使用 OR IGNORE.
启动时自动执行未应用的 migration 文件.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from .connection import get_db

_log = logging.getLogger(__name__)

# migrations 目录(相对于 seed.py)
_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

_SEED_DEPARTMENTS = [
    ("dept-eng",    "工程部",   "EMP002", None),
    ("dept-hr",     "HR部",     "EMP003", None),
    ("dept-it",     "IT部",     "EMP005", None),
    ("dept-finance","财务部",   "EMP004", None),
]


def _seed_users() -> list[tuple]:
    from src.gateway.crypto import hash_password
    pwd = hash_password("123456")
    return [
        ("EMP001", "张三", "dept-eng",    "EMP002", "employee", "2021-03-01", 5.2, 10, 5, 2, pwd),
        ("EMP002", "李四", "dept-eng",    None,     "manager",  "2018-06-01", 8.0, 10, 3, 1, pwd),
        ("EMP003", "王五", "dept-hr",     None,     "manager",  "2020-01-15", 6.4, 10, 8, 3, pwd),
        ("EMP004", "赵六", "dept-finance",None,     "manager",  "2022-09-01", 3.7, 8,  5, 2, pwd),
        ("EMP005", "孙七", "dept-it",     None,     "manager",  "2019-04-01", 7.0, 12, 6, 2, pwd),
        ("EMP006", "周八", "dept-it",     "EMP005", "employee", "2023-07-01", 2.5, 10, 5, 2, pwd),
    ]


_SEED_BUDGETS = [
    ("budget-eng-2026",    "dept-eng",    2026, "办公", 50000,  12000),
    ("budget-eng-travel",  "dept-eng",    2026, "差旅", 80000,  35000),
    ("budget-hr-2026",     "dept-hr",     2026, "办公", 30000,  8000),
    ("budget-finance-2026","dept-finance",2026, "办公", 40000,  15000),
    ("budget-it-2026",     "dept-it",     2026, "设备", 120000, 45000),
]

_SEED_EMPLOYEES = [
    ("EMP001", 10, 5, 2),
    ("EMP002", 10, 3, 1),
    ("EMP003", 10, 8, 3),
    ("EMP004", 8,  5, 2),
    ("EMP005", 12, 6, 2),
    ("EMP006", 10, 5, 2),
]

_SEED_INVENTORY = [
    ("笔记本", 15, 3,  "ThinkPad X1"),
    ("显示器", 30, 12, "Dell U2723QE"),
    ("鼠标",   50, 28, "Logitech MX Master"),
    ("键盘",   40, 18, "Keychron K8"),
    ("耳机",   20, 7,  "Sony WH-1000XM5"),
]

_SEED_IT_TICKETS = [
    ("TK001", "EMP001", "dept-it", "硬件报修", "笔记本电脑无法开机", "高", "处理中", "EMP005", "2026-05-15"),
    ("TK002", "EMP002", "dept-it", "软件安装", "需要安装 Photoshop 2026", "中", "待处理", "EMP005", "2026-05-18"),
    ("TK003", "EMP001", "dept-hr", "制度咨询", "年假结转规则不清楚,需要HR确认", "低", "待处理", "EMP003", "2026-05-20"),
    ("TK004", "EMP006", "dept-hr", "入职手续", "新员工入职材料缺少体检报告", "中", "处理中", "EMP003", "2026-05-21"),
    ("TK005", "EMP001", "dept-finance", "报销问题", "上月差旅报销迟迟未到账", "高", "处理中", "EMP004", "2026-05-19"),
    ("TK006", "EMP002", "dept-finance", "发票问题", "电子发票抬头信息有误需重开", "中", "待处理", "EMP004", "2026-05-22"),
    ("TK007", "EMP001", "dept-eng", "环境问题", "测试环境数据库连接超时", "高", "处理中", "EMP002", "2026-05-16"),
    ("TK008", "EMP006", "dept-eng", "权限申请", "需要开通生产环境只读权限", "中", "待处理", "EMP002", "2026-05-23"),
]

_SEED_CONTRACTS = [
    ("保密",   "保密协议第3.2条:员工在职期间及离职后2年内,不得向第三方泄露公司商业秘密,技术资料,客户信息.违约需赔偿公司经济损失并承担法律责任."),
    ("竞业",   "竞业限制协议第5条:离职后1年内不得入职与公司有竞争关系的企业.公司按月支付竞业补偿金(月薪的30%).违反者需退还补偿金并支付违约金."),
    ("知识产权","知识产权归属条款:员工在职期间完成的职务成果,知识产权归公司所有.公司给予发明人一次性奖励(¥5000-50000 视贡献而定)."),
    ("违约",   "合同违约条款第8条:任何一方违约需向守约方支付合同金额20%的违约金.造成实际损失的,违约金不足以弥补的部分另行赔偿."),
    ("数据保护","数据处理协议附录A:禁止将个人信息传输至境外服务器.数据泄露须在24小时内通知数据保护官并在72小时内报告监管机构."),
]

_SEED_COMPLIANCE = [
    ("跨境",   "高", "涉及个人信息跨境传输,根据数据保护条例,需完成安全评估并获得用户明确同意后方可执行."),
    ("竞业",   "中", "竞业限制条款需明确补偿金额和限制范围.当前条款补偿比例(30%)符合行业标准."),
    ("数据处理","中", "数据处理协议需指定数据保护官,明确数据泄露通知时限.建议补充数据销毁条款."),
    ("合同",   "低", "合同基本条款齐全,建议增加争议解决条款(仲裁/诉讼选择).法务部模板可参考."),
]

_SEED_POLICY_DOCS = [
    ("policy-finance-expense", "finance", "报销管理制度", "报销类型包括差旅,办公,招待,培训和其他.单笔金额达到或超过5000元时,需要财务部加签.发票需在费用发生后30天内提交.", "data/finance/报销管理制度.md"),
    ("policy-finance-salary", "finance", "薪资结构说明", "薪资由基本工资,岗位津贴,绩效奖金,社保公积金扣缴和个人所得税组成.具体个人薪资以 salary_profiles 表为准.", "data/finance/薪资结构说明.md"),
    ("policy-finance-travel", "finance", "出差管理制度", "出差交通,住宿和餐补标准按职级及城市等级执行.出差结束后5个工作日内提交报销.", "data/finance/出差管理制度.md"),
]

_SEED_SALARY_PROFILES = [
    ("EMP001", "P3", 12000, 1200, 0.105, 0.10),
    ("EMP002", "P5", 20000, 2500, 0.105, 0.10),
    ("EMP003", "P5", 19000, 2200, 0.105, 0.10),
    ("EMP004", "P5", 19500, 2200, 0.105, 0.10),
]


def _run_migrations() -> None:
    """按序执行未应用的 migration 文件."""
    if not _MIGRATIONS_DIR.exists():
        return

    files = sorted(
        f for f in _MIGRATIONS_DIR.iterdir()
        if f.suffix == ".sql" and re.match(r"^\d{3}_", f.name)
    )
    if not files:
        return

    with get_db() as conn:
        # 获取当前版本号
        row = conn.execute(
            "SELECT MAX(version) as v FROM schema_version"
        ).fetchone()
        current_version = row["v"] or 0

        for f in files:
            version = int(f.name[:3])
            if version <= current_version:
                continue
            sql = f.read_text(encoding="utf-8").strip()
            if not sql:
                continue
            try:
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (version,),
                )
                conn.commit()
                _log.info("Migration %s applied (v%d)", f.name, version)
            except Exception:
                conn.rollback()
                _log.exception("Migration %s failed -- rolling back", f.name)
                raise


def bootstrap_company_workspace() -> None:
    """初始化种子数据(幂等:INSERT OR IGNORE).

    处理循环外键:先插部门(manager_id=NULL),再插用户,
    最后回填部门的 manager_id.
    """
    # ── 0. 执行增量迁移 ──────────────────────────────────
    _run_migrations()

    with get_db() as conn:
        # ── 1. 部门(先不带 manager_id,避免循环外键)──
        conn.executemany(
            "INSERT OR IGNORE INTO departments (id, name, manager_id, parent_id) VALUES (?, ?, NULL, ?)",
            [(d[0], d[1], d[3]) for d in _SEED_DEPARTMENTS],
        )
        # ── 2. 用户(先不带 manager_id,避免循环外键)──
        seed_users = _seed_users()
        conn.executemany(
            """INSERT OR IGNORE INTO users
               (user_id, name, department_id, manager_id, role, hire_date, tenure_years,
                annual, sick, personal, password_hash, status, created_at, updated_at)
               VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, 'active', datetime('now'), datetime('now'))""",
            [(u[0], u[1], u[2], u[4], u[5], u[6], u[7], u[8], u[9], u[10]) for u in seed_users],
        )
        # ── 2b. 回填用户 manager_id ──
        for user_row in seed_users:
            uid, name, dept, mgr = user_row[0], user_row[1], user_row[2], user_row[3]
            if mgr:
                conn.execute(
                    "UPDATE users SET manager_id = ? WHERE user_id = ?",
                    (mgr, uid),
                )
        # ── 3. 回填部门 manager_id ──
        for dept_id, name, mgr_id, parent_id in _SEED_DEPARTMENTS:
            if mgr_id:
                conn.execute(
                    "UPDATE departments SET manager_id = ? WHERE id = ? AND manager_id IS NULL",
                    (mgr_id, dept_id),
                )
        # v1 兼容
        conn.executemany(
            "INSERT OR IGNORE INTO employees (user_id, annual, sick, personal) VALUES (?, ?, ?, ?)",
            _SEED_EMPLOYEES,
        )
        # 预算
        conn.executemany(
            "INSERT OR IGNORE INTO budgets (id, department_id, year, category, total, used) VALUES (?, ?, ?, ?, ?, ?)",
            _SEED_BUDGETS,
        )
        # 库存
        conn.executemany(
            "INSERT OR IGNORE INTO inventory (name, total, available, brand) VALUES (?, ?, ?, ?)",
            _SEED_INVENTORY,
        )
        # 工单
        conn.executemany(
            """INSERT OR IGNORE INTO it_tickets
               (ticket_id, user_id, department_id, issue_type, description, priority, status, assigned_to, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            _SEED_IT_TICKETS,
        )
        # 合同
        conn.executemany(
            "INSERT OR IGNORE INTO contracts (keyword, content) VALUES (?, ?)",
            _SEED_CONTRACTS,
        )
        # 合规
        conn.executemany(
            "INSERT OR IGNORE INTO compliance_rules (keyword, risk, finding) VALUES (?, ?, ?)",
            _SEED_COMPLIANCE,
        )
        # 制度文档索引
        conn.executemany(
            """INSERT OR IGNORE INTO policy_documents
               (id, category, title, content, source_path) VALUES (?, ?, ?, ?, ?)""",
            _SEED_POLICY_DOCS,
        )
        # 薪资档案
        conn.executemany(
            """INSERT OR IGNORE INTO salary_profiles
               (user_id, grade, base_salary, allowance, social_rate, housing_rate)
               VALUES (?, ?, ?, ?, ?, ?)""",
            _SEED_SALARY_PROFILES,
        )
        conn.commit()
