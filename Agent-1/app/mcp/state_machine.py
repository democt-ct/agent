"""会话状态机 — 医疗助手 Agent 会话生命周期 FSM.

状态转换规则:
  IDLE → IDENTIFYING → TRIAGE → CONSULTING → FOLLOW_UP → COMPLETED
    ↓        ↓            ↓           ↓            ↓
    ↓   IDENTITY_CONFIRMED↓      EMERGENCY    TIMEOUT
    ↓        ↓            ↓           ↓            ↓
    └────────┴────────────┴───→ HUMAN_ESCALATION ←─┘

终态: COMPLETED / HUMAN_ESCALATION / TIMEOUT — 不可再转换.
非法状态转换抛出 InvalidSessionStateTransition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import ClassVar


class SessionState(str, Enum):
    """会话状态枚举."""
    IDLE = "idle"
    IDENTIFYING = "identifying"
    TRIAGE = "triage"
    CONSULTING = "consulting"
    FOLLOW_UP = "follow_up"
    COMPLETED = "completed"
    HUMAN_ESCALATION = "human_escalation"
    TIMEOUT = "timeout"


class InvalidSessionStateTransition(Exception):
    """非法会话状态转换异常."""

    def __init__(self, current: str, target: str, session_id: str):
        super().__init__(
            f"非法会话状态转换: {current} → {target} (session={session_id})"
        )
        self.current = current
        self.target = target
        self.session_id = session_id


@dataclass
class SessionStateMachine:
    """会话状态机.

    每个会话持有一个实例，记录当前状态和转换历史.
    """

    TRANSITIONS: ClassVar[dict[str, set[str]]] = {
        SessionState.IDLE:              {SessionState.IDENTIFYING, SessionState.HUMAN_ESCALATION},
        SessionState.IDENTIFYING:       {SessionState.TRIAGE, SessionState.COMPLETED, SessionState.HUMAN_ESCALATION, SessionState.TIMEOUT},
        SessionState.TRIAGE:            {SessionState.CONSULTING, SessionState.HUMAN_ESCALATION, SessionState.COMPLETED, SessionState.TIMEOUT},
        SessionState.CONSULTING:        {SessionState.FOLLOW_UP, SessionState.COMPLETED, SessionState.HUMAN_ESCALATION, SessionState.TRIAGE, SessionState.TIMEOUT},
        SessionState.FOLLOW_UP:         {SessionState.CONSULTING, SessionState.COMPLETED, SessionState.HUMAN_ESCALATION, SessionState.TIMEOUT},
        SessionState.COMPLETED:         set(),   # 终态
        SessionState.HUMAN_ESCALATION:  set(),   # 终态
        SessionState.TIMEOUT:           set(),   # 终态
    }

    # 允许从任意非终态升级到 HUMAN_ESCALATION
    _ESCALATABLE_STATES: ClassVar[set[str]] = {
        SessionState.IDENTIFYING,
        SessionState.TRIAGE,
        SessionState.CONSULTING,
        SessionState.FOLLOW_UP,
    }

    session_id: str
    current_state: str = SessionState.IDLE
    history: list[tuple[str, str, str]] = field(default_factory=list)
    # (from_state, to_state, iso_timestamp)

    # ── 类方法 ──

    @classmethod
    def can_transition(cls, current: str, target: str) -> bool:
        """检查状态转换是否合法."""
        return target in cls.TRANSITIONS.get(current, set())

    @classmethod
    def can_escalate(cls, current: str) -> bool:
        """检查当前状态是否允许升级到人工."""
        return current in cls._ESCALATABLE_STATES

    @classmethod
    def is_terminal(cls, state: str) -> bool:
        """检查是否为终态."""
        return state in {
            SessionState.COMPLETED,
            SessionState.HUMAN_ESCALATION,
            SessionState.TIMEOUT,
        }

    # ── 实例方法 ──

    def transition(self, target: str) -> str:
        """执行状态转换，校验合法性.

        Returns:
            新状态字符串.

        Raises:
            InvalidSessionStateTransition: 非法转换
        """
        # 特殊处理：任何可升级状态都可以升级到 HUMAN_ESCALATION
        if target == SessionState.HUMAN_ESCALATION:
            if not self.can_escalate(self.current_state):
                raise InvalidSessionStateTransition(
                    self.current_state, target, self.session_id
                )
        elif not self.can_transition(self.current_state, target):
            raise InvalidSessionStateTransition(
                self.current_state, target, self.session_id
            )

        old_state = self.current_state
        self.current_state = target
        self.history.append(
            (old_state, target, datetime.now(timezone.utc).isoformat())
        )
        return self.current_state

    def escalate(self, reason: str = "") -> str:
        """便捷方法：升级到人工兜底."""
        return self.transition(SessionState.HUMAN_ESCALATION)

    def complete(self) -> str:
        """便捷方法：正常完成."""
        return self.transition(SessionState.COMPLETED)

    def reset(self) -> str:
        """重置到 IDLE（仅在终态允许）."""
        if not self.is_terminal(self.current_state):
            raise InvalidSessionStateTransition(
                self.current_state, SessionState.IDLE, self.session_id
            )
        self.current_state = SessionState.IDLE
        self.history.clear()
        return self.current_state

    def to_dict(self) -> dict:
        """序列化为字典，用于存入 Redis."""
        return {
            "session_id": self.session_id,
            "current_state": self.current_state,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionStateMachine":
        """从字典恢复状态机."""
        sm = cls(session_id=data["session_id"])
        sm.current_state = data.get("current_state", SessionState.IDLE)
        sm.history = data.get("history", [])
        return sm
