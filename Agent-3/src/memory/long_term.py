"""长期记忆 -- L3 Semantic Memory.

存储用户偏好,历史决策,常用信息.
工作流完成后自动提取关键事实并写入.

存储方式:
  - SQLite long_term_memory 表(主要)
  - Chroma 向量库(可选,需要时启用)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from src.tools.db import get_db

logger = logging.getLogger(__name__)


class LongTermMemory:
    """长期记忆管理器."""

    def __init__(self):
        self._ensure_table()

    def _ensure_table(self) -> None:
        """确保 long_term_memory 表存在."""
        try:
            with get_db() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS long_term_memory (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id     TEXT    NOT NULL,
                        category    TEXT    NOT NULL,  -- preference / decision / fact
                        key         TEXT    NOT NULL,  -- 如 "leave_preference"
                        value       TEXT    NOT NULL,  -- 事实内容
                        source      TEXT,              -- 来源 session_id
                        created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                        updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ltm_user ON long_term_memory(user_id, category)
                """)
                conn.commit()
        except Exception as e:
            logger.warning("Failed to ensure long_term_memory table: %s", e)

    def remember(
        self,
        user_id: str,
        category: str,
        key: str,
        value: str,
        source: str = "",
    ) -> None:
        """写入一条长期记忆.

        Args:
            user_id: 用户 ID
            category: preference / decision / fact
            key: 唯一标识如 "leave_preference"
            value: 记忆内容
            source: 来源(session_id)
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            with get_db() as conn:
                # UPSERT: 如果 (user_id, key) 已存在则更新
                existing = conn.execute(
                    "SELECT id FROM long_term_memory WHERE user_id = ? AND key = ?",
                    (user_id, key),
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE long_term_memory SET value = ?, updated_at = ? WHERE id = ?",
                        (value, now, existing["id"]),
                    )
                else:
                    conn.execute(
                        """INSERT INTO long_term_memory (user_id, category, key, value, source, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (user_id, category, key, value, source, now, now),
                    )
                conn.commit()
        except Exception as e:
            logger.warning("Failed to remember: %s", e)

    def recall(self, user_id: str, category: str | None = None, limit: int = 10) -> list[dict]:
        """查询用户的长期记忆.

        Args:
            user_id: 用户 ID
            category: 可选过滤(preference / decision / fact)
            limit: 最大返回条数
        """
        try:
            with get_db() as conn:
                if category:
                    rows = conn.execute(
                        """SELECT category, key, value, source, updated_at
                           FROM long_term_memory
                           WHERE user_id = ? AND category = ?
                           ORDER BY updated_at DESC
                           LIMIT ?""",
                        (user_id, category, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """SELECT category, key, value, source, updated_at
                           FROM long_term_memory
                           WHERE user_id = ?
                           ORDER BY updated_at DESC
                           LIMIT ?""",
                        (user_id, limit),
                    ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning("Failed to recall: %s", e)
            return []

    def recall_as_context(self, user_id: str, limit: int = 5) -> str:
        """查询长期记忆并格式化为上下文文本,可注入 LLM prompt."""
        facts = self.recall(user_id, limit=limit)
        if not facts:
            return ""
        lines = ["## 用户长期记忆"]
        for f in facts:
            lines.append(f"- [{f['category']}] {f['key']}: {f['value']}")
        return "\n".join(lines)

    def extract_from_workflow(
        self,
        user_id: str,
        session_id: str,
        workflow_result: dict,
    ) -> None:
        """从工作流结果中自动提取关键事实.

        提取规则(简单启发式):
          - 请假审批通过 → 记住偏好假期类型和天数
          - 工具调用成功 → 记住
        """
        # 提取请假偏好
        if "年假" in str(workflow_result):
            self.remember(user_id, "preference", "leave_type", "年假", session_id)
        if "病假" in str(workflow_result):
            self.remember(user_id, "preference", "leave_type", "病假", session_id)

        # 提取最后使用的工具
        tool_calls = workflow_result.get("tool_calls", [])
        for tc in tool_calls:
            name = tc.get("name", "") or tc.get("tool_name", "")
            if name in ("submit_leave_request", "approve_leave"):
                self.remember(user_id, "fact", f"last_tool_{name}", "used", session_id)

        logger.info("Extracted long-term facts for user %s from session %s", user_id, session_id)
