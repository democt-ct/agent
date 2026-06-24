"""数据库连接管理 -- 线程安全连接池 + 迁移自动执行 + 环境隔离.

特性:
    - 每线程一个连接(SQLite 串行写入最佳实践)
    - APP_ENV=dev 使用 data/dev.db,production 使用 data/enterprise.db
    - 启动时自动执行未应用的迁移(基于 schema_version 表)
    - WAL 模式 + 外键 + 合理超时

Usage:
    from src.tools.db.connection import get_db, _now, _uid
    with get_db() as conn: ...
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .schema import _SCHEMA

logger = logging.getLogger(__name__)

# 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"

# 环境隔离:dev → dev.db, production → enterprise.db
_APP_ENV = os.getenv("APP_ENV", "dev")
_DB_FILENAME = "dev.db" if _APP_ENV == "dev" else "enterprise.db"
_DB_PATH = _DATA_DIR / _DB_FILENAME

# 连接超时(秒)-- 写锁等待
_BUSY_TIMEOUT_MS = 5000

# 线程本地连接缓存
_tls = threading.local()


def get_db() -> sqlite3.Connection:
    """获取当前线程的数据库连接(自动创建,开启 WAL,执行迁移).

    每线程复用同一连接,线程退出时由 GC 清理.
    """
    conn = getattr(_tls, "conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
        except (sqlite3.ProgrammingError, sqlite3.OperationalError):
            conn = None

    if conn is None:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_DB_PATH), timeout=_BUSY_TIMEOUT_MS / 1000.0)
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout={:d}".format(_BUSY_TIMEOUT_MS))
        conn.execute("PRAGMA synchronous=NORMAL")  # WAL 模式下 NORMAL 足够安全
        conn.execute("PRAGMA cache_size=-8000")     # 8MB 缓存
        _tls.conn = conn

        # 建表 + 迁移
        _ensure_schema(conn)
        _run_migrations(conn)

    return conn


def close_db() -> None:
    """关闭当前线程的数据库连接."""
    conn = getattr(_tls, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _tls.conn = None


def get_db_path() -> Path:
    """返回当前环境的数据库路径."""
    return _DB_PATH


def get_db_size_mb() -> float:
    """返回数据库文件大小(MB)."""
    try:
        return _DB_PATH.stat().st_size / (1024 * 1024)
    except FileNotFoundError:
        return 0.0


# ═══════════════════════════════════════════════════════════════════
# Schema + Migration
# ═══════════════════════════════════════════════════════════════════

_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """确保基础 DDL 表存在(幂等 CREATE TABLE IF NOT EXISTS)."""
    conn.executescript(_SCHEMA)
    conn.commit()


def _run_migrations(conn: sqlite3.Connection) -> None:
    """自动执行未应用的迁移文件.

    迁移目录: src/tools/db/migrations/
    命名规则: NNN_description.sql(如 001_baseline.sql)
    版本追踪: schema_version 表
    """
    # 获取当前版本
    row = conn.execute("SELECT MAX(version) as ver FROM schema_version").fetchone()
    current_version = row["ver"] if row and row["ver"] else 0

    # 扫描迁移文件
    if not _MIGRATIONS_DIR.exists():
        return

    migration_files = sorted(
        f for f in _MIGRATIONS_DIR.iterdir()
        if f.suffix == ".sql" and f.name[0].isdigit()
    )

    applied = 0
    for mf in migration_files:
        try:
            version = int(mf.name.split("_")[0])
        except (ValueError, IndexError):
            logger.warning("Skipping migration with non-numeric prefix: %s", mf.name)
            continue

        if version <= current_version:
            continue

        logger.info("Applying migration %s ...", mf.name)
        sql = mf.read_text(encoding="utf-8")
        try:
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (version,),
            )
            conn.commit()
            applied += 1
            logger.info("Migration %s applied successfully", mf.name)
        except Exception as e:
            logger.error("Migration %s failed: %s", mf.name, e)
            conn.rollback()
            raise RuntimeError(f"Migration {mf.name} failed: {e}") from e

    if applied:
        logger.info("%d migration(s) applied (now at v%d)", applied,
                    current_version + applied)


# ═══════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _uid() -> str:
    return uuid.uuid4().hex[:12]
