"""EventBus -- Agent 间事件发布/订阅.

单进程内存实现,后续可换 Redis pub/sub.

支持的事件:
  approval.created      -- 审批流创建
  approval.approved     -- 某步骤审批通过
  approval.rejected     -- 某步骤被驳回
  approval.completed    -- 全部审批完成
  leave.submitted       -- 请假申请提交
  workflow.step_done    -- 工作流节点完成
  workflow.failed       -- 工作流失败
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)

Callback = Callable[[dict[str, Any]], None]


class EventBus:
    """轻量级事件总线 -- 发布/订阅模式."""

    def __init__(self):
        self._subscribers: dict[str, list[Callback]] = defaultdict(list)

    def subscribe(self, event: str, callback: Callback) -> None:
        """订阅事件."""
        self._subscribers[event].append(callback)

    def unsubscribe(self, event: str, callback: Callback) -> None:
        """取消订阅."""
        if event in self._subscribers:
            self._subscribers[event] = [
                cb for cb in self._subscribers[event] if cb != callback
            ]

    def publish(self, event: str, data: dict[str, Any]) -> None:
        """发布事件 -- 同步调用所有订阅者."""
        callbacks = self._subscribers.get(event, [])
        if not callbacks:
            return

        logger.debug("EventBus: %s → %d subscribers", event, len(callbacks))
        for cb in callbacks:
            try:
                cb(data)
            except Exception:
                logger.exception("EventBus: subscriber for %s failed", event)


# ── 全局单例 ──────────────────────────────────────────────────────

_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """获取全局 EventBus 单例."""
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


# ── 内置订阅:审批通知 ────────────────────────────────────────────

def _setup_builtin_subscribers(bus: EventBus) -> None:
    """注册系统级事件处理器."""

    def on_approval_completed(data: dict) -> None:
        """审批全部完成 → 记录日志."""
        logger.info(
            "📨 审批完成: record=%s type=%s approved=%s",
            data.get("record_id"),
            data.get("record_type"),
            data.get("all_approved"),
        )

    def on_workflow_failed(data: dict) -> None:
        """工作流失败 → 告警."""
        logger.error(
            "⚠️ 工作流失败: workflow=%s error=%s",
            data.get("workflow_id"),
            data.get("error"),
        )

    def on_leave_submitted(data: dict) -> None:
        """请假提交 → 通知审批人."""
        logger.info(
            "📝 请假申请已提交: user=%s type=%s days=%s approver=%s",
            data.get("user_id"),
            data.get("leave_type"),
            data.get("days"),
            data.get("approver_id"),
        )

    bus.subscribe("approval.completed", on_approval_completed)
    bus.subscribe("workflow.failed", on_workflow_failed)
    bus.subscribe("leave.submitted", on_leave_submitted)


# 自动注册内置订阅
_setup_builtin_subscribers(get_event_bus())
