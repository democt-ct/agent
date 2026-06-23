"""后台定时任务调度模块。

使用 APScheduler 管理定时任务：
- 记忆抽取：每 30 分钟对活跃会话触发一次记忆抽取
- 过期知识清理：每天凌晨清理已过期的知识块
- 会话缓存过期清理：每小时清理 Redis 过期会话

所有任务均可通过环境变量控制开关和间隔。
"""

import os
import threading
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.database import SessionLocal
from app.core.logging import get_logger

logger = get_logger(__name__)

_scheduler: Optional[BackgroundScheduler] = None
_scheduler_lock = threading.Lock()

# ---- 环境变量配置 ----
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")
MEMORY_EXTRACTION_INTERVAL_MINUTES = int(os.getenv("SCHEDULER_MEMORY_EXTRACTION_INTERVAL", "30"))
KNOWLEDGE_CLEANUP_HOUR = int(os.getenv("SCHEDULER_KNOWLEDGE_CLEANUP_HOUR", "3"))
SESSION_CLEANUP_INTERVAL_MINUTES = int(os.getenv("SCHEDULER_SESSION_CLEANUP_INTERVAL", "60"))


def _cleanup_expired_knowledge_chunks():
    """清理已过期的知识块。"""
    from app.models.memory_knowledge_chunk import MemoryKnowledgeChunk

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        deleted = (
            db.query(MemoryKnowledgeChunk)
            .filter(
                MemoryKnowledgeChunk.expires_at.isnot(None),
                MemoryKnowledgeChunk.expires_at < now,
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        if deleted:
            logger.info(f"[scheduler] 清理了 {deleted} 条过期知识块")
    except Exception as exc:
        db.rollback()
        logger.warning(f"[scheduler] 清理知识块失败: {exc}")
    finally:
        db.close()


def _cleanup_expired_sessions():
    """清理 Redis 中过期的会话缓存（Redis 自身有 TTL，此处做二次保障）。"""
    try:
        from app.core.redis_client import clear_expired_sessions

        clear_expired_sessions()
        logger.debug("[scheduler] 会话缓存清理检查完成")
    except Exception as exc:
        logger.warning(f"[scheduler] 会话缓存清理失败: {exc}")


def _cleanup_old_session_data():
    """清理超过 90 天的临时会话数据和审计日志，满足数据保留策略。"""
    from datetime import timedelta

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=90)
        deleted_total = 0

        # 清理旧会话缓冲消息
        from app.models.memory_session_buffer import MemorySessionBufferMessage
        deleted = (
            db.query(MemorySessionBufferMessage)
            .filter(MemorySessionBufferMessage.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        deleted_total += deleted
        if deleted:
            logger.info(f"[scheduler] 清理了 {deleted} 条超过 90 天的会话缓冲消息")

        # 清理旧审计日志
        from app.models.audit_log import AuditLog
        deleted = (
            db.query(AuditLog)
            .filter(AuditLog.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        deleted_total += deleted
        if deleted:
            logger.info(f"[scheduler] 清理了 {deleted} 条超过 90 天的审计日志")

        # 清理旧知识切片（不引用活跃记录的过期切片）
        from app.models.memory_knowledge_chunk import MemoryKnowledgeChunk
        deleted = (
            db.query(MemoryKnowledgeChunk)
            .filter(
                MemoryKnowledgeChunk.expires_at.isnot(None),
                MemoryKnowledgeChunk.expires_at < cutoff,
            )
            .delete(synchronize_session=False)
        )
        deleted_total += deleted
        if deleted:
            logger.info(f"[scheduler] 清理了 {deleted} 条超过有效期的知识切片")

        db.commit()
        if deleted_total:
            logger.info(f"[scheduler] 数据保留清理完成，共清理 {deleted_total} 条记录")
    except Exception as exc:
        db.rollback()
        logger.warning(f"[scheduler] 数据保留清理失败: {exc}")
    finally:
        db.close()


def _trigger_memory_extraction():
    """对最近活跃的会话触发记忆抽取。

    遍历最近 N 条有对话消息的患者会话，调用记忆抽取服务。
    """
    from app.models.memory_conversation import MemoryConversationMessage
    from app.services.memory_extraction_service import extract_long_term_memory

    db = SessionLocal()
    try:
        # 找出最近 24 小时内有消息的 (patient_id, session_id) 组合
        recent_cutoff = datetime.utcnow()
        # APScheduler 的 interval trigger 不支持动态 cutoff，简单起见查询最近消息
        recent_messages = (
            db.query(
                MemoryConversationMessage.patient_id,
                MemoryConversationMessage.session_id,
            )
            .filter(
                MemoryConversationMessage.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
            )
            .distinct()
            .limit(20)
            .all()
        )

        extracted = 0
        for patient_id, session_id in recent_messages:
            try:
                extract_long_term_memory(db, patient_id=patient_id)
                extracted += 1
            except Exception:
                pass

        if extracted:
            logger.info(f"[scheduler] 记忆抽取完成，处理了 {extracted} 个患者")
    except Exception as exc:
        logger.warning(f"[scheduler] 记忆抽取失败: {exc}")
    finally:
        db.close()


def start_scheduler() -> None:
    """启动后台定时调度器。"""
    global _scheduler

    if not SCHEDULER_ENABLED:
        logger.info("[scheduler] 后台调度已禁用（SCHEDULER_ENABLED=false）")
        return

    with _scheduler_lock:
        if _scheduler is not None:
            return
        _scheduler = BackgroundScheduler(
            timezone="Asia/Shanghai",
            job_defaults={"misfire_grace_time": 300, "coalesce": True},
        )

        # 记忆抽取 — 每 N 分钟
        _scheduler.add_job(
            _trigger_memory_extraction,
            trigger="interval",
            minutes=MEMORY_EXTRACTION_INTERVAL_MINUTES,
            id="memory_extraction",
            name="记忆抽取",
            replace_existing=True,
        )
        logger.info(
            f"[scheduler] 记忆抽取任务已注册，间隔 {MEMORY_EXTRACTION_INTERVAL_MINUTES} 分钟"
        )

        # 知识块过期清理 — 每天凌晨
        _scheduler.add_job(
            _cleanup_expired_knowledge_chunks,
            trigger="cron",
            hour=KNOWLEDGE_CLEANUP_HOUR,
            minute=0,
            id="knowledge_cleanup",
            name="知识块过期清理",
            replace_existing=True,
        )
        logger.info(
            f"[scheduler] 知识块清理任务已注册，每天 {KNOWLEDGE_CLEANUP_HOUR}:00 执行"
        )

        # 会话缓存清理 — 每小时
        _scheduler.add_job(
            _cleanup_expired_sessions,
            trigger="interval",
            minutes=SESSION_CLEANUP_INTERVAL_MINUTES,
            id="session_cleanup",
            name="会话缓存清理",
            replace_existing=True,
        )
        logger.info(
            f"[scheduler] 会话缓存清理任务已注册，间隔 {SESSION_CLEANUP_INTERVAL_MINUTES} 分钟"
        )

        # 数据保留清理 — 每天凌晨（与知识块清理同时）
        _scheduler.add_job(
            _cleanup_old_session_data,
            trigger="cron",
            hour=KNOWLEDGE_CLEANUP_HOUR,
            minute=15,
            id="data_retention_cleanup",
            name="数据保留清理",
            replace_existing=True,
        )
        logger.info(
            f"[scheduler] 数据保留清理任务已注册，每天 {KNOWLEDGE_CLEANUP_HOUR}:15 执行"
        )

        _scheduler.start()
        logger.info("[scheduler] 后台调度器已启动")


def shutdown_scheduler() -> None:
    """关闭后台调度器。"""
    global _scheduler
    with _scheduler_lock:
        if _scheduler is not None:
            _scheduler.shutdown(wait=False)
            _scheduler = None
            logger.info("[scheduler] 后台调度器已关闭")
