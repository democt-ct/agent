"""审批状态机 -- 严格 FSM.

状态转换规则:
  leave_records:
    draft → pending → approved → completed
                    → rejected
                    → cancelled (仅 pending 状态可取消)
  approval_flow (单个步骤):
    pending → approved / rejected / skipped

非法状态转换抛出 InvalidStateTransition.
"""

from __future__ import annotations

from typing import ClassVar


class InvalidStateTransition(Exception):
    """非法状态转换异常."""
    def __init__(self, current: str, target: str, record_id: str):
        super().__init__(
            f"非法状态转换: {current} → {target} (record={record_id})"
        )
        self.current = current
        self.target = target
        self.record_id = record_id


class LeaveStateMachine:
    """请假记录状态机.

    状态流: draft → pending → approved → completed
                           → rejected
                           → cancelled
    """

    TRANSITIONS: ClassVar[dict[str, set[str]]] = {
        "draft":     {"pending"},
        "pending":   {"approved", "rejected", "cancelled"},
        "approved":  {"completed"},
        "rejected":  set(),      # 终态
        "completed": set(),      # 终态
        "cancelled": set(),      # 终态
    }

    @classmethod
    def can_transition(cls, current: str, target: str) -> bool:
        return target in cls.TRANSITIONS.get(current, set())

    @classmethod
    def transition(cls, record_id: str, current: str, target: str) -> str:
        """执行状态转换,校验合法性.

        Returns:
            新状态字符串.

        Raises:
            InvalidStateTransition: 非法转换
        """
        if not cls.can_transition(current, target):
            raise InvalidStateTransition(current, target, record_id)
        return target


class ApprovalStepStateMachine:
    """审批步骤状态机.

    状态流: pending → approved / rejected / skipped
    """

    TRANSITIONS: ClassVar[dict[str, set[str]]] = {
        "pending":  {"approved", "rejected", "skipped"},
        "approved": set(),   # 终态
        "rejected": set(),   # 终态
        "skipped":  set(),   # 终态
    }

    @classmethod
    def can_transition(cls, current: str, target: str) -> bool:
        return target in cls.TRANSITIONS.get(current, set())

    @classmethod
    def transition(cls, step_id: str, current: str, target: str) -> str:
        if not cls.can_transition(current, target):
            raise InvalidStateTransition(current, target, step_id)
        return target


# ═══════════════════════════════════════════════════════════════
# DB 集成:带 FSM 校验的数据库更新
# ═══════════════════════════════════════════════════════════════

def transition_leave_status(record_id: str, target: str) -> str:
    """带 FSM 校验地更新 leave_records 状态."""
    from src.tools.db import get_db

    with get_db() as conn:
        row = conn.execute(
            "SELECT status FROM leave_records WHERE id = ?", (record_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"请假记录不存在: {record_id}")

        current = row["status"]
        new_status = LeaveStateMachine.transition(record_id, current, target)

        conn.execute(
            "UPDATE leave_records SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (new_status, record_id),
        )
        conn.commit()

    return new_status


def transition_approval_step(step_id: str, target: str) -> str:
    """带 FSM 校验地更新 approval_flow 步骤状态."""
    from src.tools.db import get_db

    with get_db() as conn:
        row = conn.execute(
            "SELECT status FROM approval_flow WHERE id = ?", (step_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"审批步骤不存在: {step_id}")

        current = row["status"]
        new_status = ApprovalStepStateMachine.transition(step_id, current, target)

        conn.execute(
            "UPDATE approval_flow SET status = ?, decided_at = datetime('now') WHERE id = ?",
            (new_status, step_id),
        )
        conn.commit()

    return new_status
