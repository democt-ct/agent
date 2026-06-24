"""会话持久化 -- L2 Episodic Memory.

写入/读取 conversation_memory 表(SQLite).
支持自动 TTL 清理(保留最近 7 天).

Usage:
    store = ConversationStore()
    store.save(session_id, user_id, role, content, metadata)
    history = store.load_recent(session_id, limit=10)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from src.tools.db import get_db

logger = logging.getLogger(__name__)


class ConversationStore:
    """会话持久化存储."""

    def __init__(self, max_recent: int = 20, ttl_days: int = 7):
        self.max_recent = max_recent
        self.ttl_days = ttl_days

    def save(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        """保存一条对话消息.

        Args:
            session_id: 会话 ID
            user_id: 用户 ID
            role: user / assistant / system / tool / summary
            content: 消息文本
            metadata: 可选元数据 {agent, tool_calls, tokens, ...}
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        try:
            with get_db() as conn:
                conn.execute(
                    """INSERT INTO conversation_memory (session_id, user_id, role, content, metadata, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (session_id, user_id, role, content, meta_json, now),
                )
                conn.commit()
        except Exception as e:
            logger.warning("Failed to save conversation: %s", e)

    def load_recent(self, session_id: str, limit: int | None = None, user_id: str | None = None) -> list[dict]:
        """加载某个会话的最近消息.

        Args:
            session_id: 会话 ID
            limit: 返回条数上限
            user_id: 可选,传入则额外按 user_id 过滤(双重隔离)

        Returns:
            [{"role": "user", "content": "..."}, ...]
        """
        limit = limit or self.max_recent
        try:
            with get_db() as conn:
                if user_id:
                    rows = conn.execute(
                        """SELECT role, content, metadata, created_at
                           FROM conversation_memory
                           WHERE session_id = ? AND user_id = ?
                           ORDER BY created_at DESC
                           LIMIT ?""",
                        (session_id, user_id, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """SELECT role, content, metadata, created_at
                           FROM conversation_memory
                           WHERE session_id = ?
                           ORDER BY created_at DESC
                           LIMIT ?""",
                        (session_id, limit),
                    ).fetchall()
            # 反转回时间顺序
            result = []
            for r in reversed(rows):
                result.append({
                    "role": r["role"],
                    "content": r["content"],
                    "metadata": r["metadata"],
                    "created_at": r["created_at"],
                })
            return result
        except Exception as e:
            logger.warning("Failed to load conversation: %s", e)
            return []

    def to_history_format(self, session_id: str, limit: int = 10, user_id: str | None = None) -> list[dict]:
        """加载会话并转为 API history 格式 [{"role": "...", "content": "..."}].

        只返回 user/assistant 角色,过滤 system/tool/summary.
        """
        messages = self.load_recent(session_id, limit, user_id=user_id)
        return [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m["role"] in ("user", "assistant")
        ]

    def count_messages(self, session_id: str) -> int:
        """统计某会话的总消息数."""
        try:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) as c FROM conversation_memory WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
            return row["c"] if row else 0
        except Exception:
            return 0

    def cleanup_old(self) -> int:
        """清理超过 TTL 的旧消息."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.ttl_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            with get_db() as conn:
                cursor = conn.execute(
                    "DELETE FROM conversation_memory WHERE created_at < ?",
                    (cutoff,),
                )
                conn.commit()
                deleted = cursor.rowcount
                if deleted:
                    logger.info("Cleaned up %d old conversation messages", deleted)
                return deleted
        except Exception as e:
            logger.warning("Failed to cleanup conversations: %s", e)
            return 0

    def replace_with_summary(self, session_id: str, summary: str, before_message_count: int) -> None:
        """用摘要替换前 N 条旧消息.删除旧消息,插入 summary 行."""
        try:
            with get_db() as conn:
                # 找到第 N 条之后的第一个 id
                row = conn.execute(
                    """SELECT id FROM conversation_memory
                       WHERE session_id = ?
                       ORDER BY created_at ASC
                       LIMIT 1 OFFSET ?""",
                    (session_id, before_message_count),
                ).fetchone()
                if row:
                    conn.execute(
                        "DELETE FROM conversation_memory WHERE session_id = ? AND id < ?",
                        (session_id, row["id"]),
                    )
                # 插入摘要
                now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                conn.execute(
                    """INSERT INTO conversation_memory (session_id, user_id, role, content, metadata, created_at)
                       VALUES (?, 'system', 'summary', ?, '{}', ?)""",
                    (session_id, summary, now),
                )
                conn.commit()
        except Exception as e:
            logger.warning("Failed to replace with summary: %s", e)
