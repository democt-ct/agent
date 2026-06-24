"""统一通知中心 -- 所有系统通知的发送,查询,标记.

当前系统通知散落在 create_ticket / submit_leave_request 等工具函数中,
此模块提供统一入口,支持:
  - 发送通知(自动去重:同一用户 + 同一标题 5 分钟内不重复发)
  - 查询未读通知
  - 批量标记已读
  - 发送摘要通知

Usage:
    from src.skills.notification import send_notification, get_unread_notifications
    send_notification("EMP001", "system", "工单状态更新", "工单 TK003 已完成")
"""

from __future__ import annotations

import logging
from src.tools.db import get_db, _uid, _now

logger = logging.getLogger(__name__)

# 去重窗口(秒):同一用户+同一标题在此窗口内不重复发送
_DEDUP_WINDOW_SECONDS = 300


def send_notification(
    user_id: str,
    type_: str,
    title: str,
    body: str = "",
    link_type: str | None = None,
    link_id: str | None = None,
    dedup: bool = True,
) -> dict:
    """发送一条通知给指定用户.

    Args:
        user_id: 接收用户 ID
        type_: 通知类型: approval_result | pending_approval | system
        title: 通知标题
        body: 通知正文
        link_type: 关联记录类型: leave | expense | ticket | null
        link_id: 关联记录 ID
        dedup: 是否启用去重(默认 True,5 分钟内同标题不重复发)

    Returns:
        {"success": True, "notification_id": "..."} 或被去重 {"skipped": True, "reason": "..."}
    """
    if dedup:
        with get_db() as conn:
            existing = conn.execute(
                """SELECT id FROM notifications
                   WHERE user_id = ? AND title = ?
                     AND created_at >= datetime('now', ?)
                   LIMIT 1""",
                (user_id, title, f"-{_DEDUP_WINDOW_SECONDS} seconds"),
            ).fetchone()
        if existing is not None:
            logger.debug("通知去重: user=%s title=%s", user_id, title)
            return {"skipped": True, "reason": f"5 分钟内已发送过相同通知", "existing_id": existing["id"]}

    nid = _uid()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO notifications (id, user_id, type, title, body, link_type, link_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (nid, user_id, type_, title, body, link_type, link_id, _now()),
        )
        conn.commit()

    logger.info("通知已发送: user=%s type=%s title=%s", user_id, type_, title)
    return {"success": True, "notification_id": nid}


def get_unread_notifications(user_id: str, limit: int = 30) -> dict:
    """获取用户的未读通知列表.

    Args:
        user_id: 用户 ID
        limit: 最大返回条数

    Returns:
        {"user_id": "...", "unread_count": N, "notifications": [...]}
    """
    with get_db() as conn:
        count_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,),
        ).fetchone()
        rows = conn.execute(
            """SELECT id, type, title, body, is_read, link_type, link_id, created_at
               FROM notifications
               WHERE user_id = ? AND is_read = 0
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()

    return {
        "user_id": user_id,
        "unread_count": count_row["cnt"] if count_row else 0,
        "notifications": [dict(r) for r in rows],
    }


def mark_notifications_read(user_id: str, ids: list[str] | None = None) -> dict:
    """标记通知为已读.

    Args:
        user_id: 用户 ID
        ids: 要标记的通知 ID 列表,None 表示标记全部未读

    Returns:
        {"success": True, "marked_count": N}
    """
    with get_db() as conn:
        if ids:
            placeholders = ",".join("?" * len(ids))
            cursor = conn.execute(
                f"UPDATE notifications SET is_read = 1 WHERE user_id = ? AND id IN ({placeholders})",
                [user_id] + ids,
            )
        else:
            cursor = conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
                (user_id,),
            )
        conn.commit()
        marked = cursor.rowcount

    return {"success": True, "marked_count": marked}


def send_digest(user_id: str, max_items: int = 10) -> dict:
    """发送未读通知摘要.

    将所有未读通知汇总为一条摘要消息,便于一次性查看.

    Args:
        user_id: 用户 ID
        max_items: 摘要中最多包含几条

    Returns:
        {"unread_count": N, "digest": [...], "summary": "..."}
    """
    notifications = get_unread_notifications(user_id, limit=max_items)
    items = notifications["notifications"]

    if not items:
        return {"unread_count": 0, "digest": [], "summary": "暂无未读通知"}

    digest_lines = []
    for n in items[:max_items]:
        time_str = n.get("created_at", "")[:16].replace("T", " ")
        digest_lines.append(f"- [{time_str}] {n['title']}:{n.get('body', '')}")

    summary = f"你有 {notifications['unread_count']} 条未读通知:\n" + "\n".join(digest_lines)

    return {
        "unread_count": notifications["unread_count"],
        "digest": items,
        "summary": summary,
    }
