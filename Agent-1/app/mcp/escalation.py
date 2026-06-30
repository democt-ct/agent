"""人工兜底服务 —— 紧急/高风险场景升级到人工.

触发条件:
  1. 紧急症状检测 (TriageLevel.EMERGENCY)
  2. 用户明确要求转人工
  3. LLM 置信度 < 0.3 连续 2 轮
  4. 幻觉检测连续触发

升级记录持久化到 escalation_log 表，同时通过通知渠道告知值班医生.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

logger = logging.getLogger("agent.escalation")


class EscalationReason(str, Enum):
    EMERGENCY_SYMPTOM = "emergency_symptom"
    USER_REQUESTED = "user_requested"
    LOW_CONFIDENCE = "low_confidence"
    HALLUCINATION_REPEATED = "hallucination_repeated"
    SAFETY_GUARD_TRIGGERED = "safety_guard_triggered"
    UNKNOWN = "unknown"


class EscalationSeverity(str, Enum):
    CRITICAL = "critical"   # 危及生命，立即通知
    HIGH = "high"           # 高风险，5 分钟内通知
    MEDIUM = "medium"       # 中风险，30 分钟内通知


class EscalationStatus(str, Enum):
    PENDING = "pending"       # 待处理
    ACKNOWLEDGED = "acknowledged"  # 已确认
    RESOLVED = "resolved"     # 已处理
    TIMEOUT = "timeout"       # 超时未处理


@dataclass
class EscalationRecord:
    """升级记录."""
    escalation_id: str = field(default_factory=lambda: uuid4().hex[:12])
    session_id: str = ""
    patient_id: Optional[str] = None
    hospital_id: Optional[str] = None
    reason: EscalationReason = EscalationReason.UNKNOWN
    severity: EscalationSeverity = EscalationSeverity.MEDIUM
    status: EscalationStatus = EscalationStatus.PENDING
    question: str = ""
    context_summary: str = ""
    detected_signals: list[str] = field(default_factory=list)
    triage_level: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "escalation_id": self.escalation_id,
            "session_id": self.session_id,
            "patient_id": self.patient_id,
            "hospital_id": self.hospital_id,
            "reason": self.reason.value,
            "severity": self.severity.value,
            "status": self.status.value,
            "question": self.question,
            "context_summary": self.context_summary,
            "detected_signals": self.detected_signals,
            "triage_level": self.triage_level,
            "created_at": self.created_at,
            "acknowledged_at": self.acknowledged_at,
            "resolved_at": self.resolved_at,
            "notes": self.notes,
        }


# ── 通知渠道接口（可对接企微/钉钉/短信） ──

_notification_handlers: list[Callable[[EscalationRecord], None]] = []


def register_notification_handler(handler: Callable[[EscalationRecord], None]) -> None:
    """注册通知处理器."""
    _notification_handlers.append(handler)


def _notify(record: EscalationRecord) -> None:
    """通知所有已注册的渠道."""
    for handler in _notification_handlers:
        try:
            handler(record)
        except Exception:
            logger.exception("通知处理器异常 escalation_id=%s", record.escalation_id)


# ── 内存存储（可替换为 DB） ──

_escalations: dict[str, EscalationRecord] = {}


def create_escalation(
    session_id: str,
    reason: EscalationReason,
    severity: EscalationSeverity,
    *,
    patient_id: Optional[str] = None,
    hospital_id: Optional[str] = None,
    question: str = "",
    context_summary: str = "",
    detected_signals: Optional[list[str]] = None,
    triage_level: str = "",
    notify: bool = True,
) -> EscalationRecord:
    """创建升级记录并触发通知."""
    record = EscalationRecord(
        session_id=session_id,
        patient_id=patient_id,
        hospital_id=hospital_id,
        reason=reason,
        severity=severity,
        question=question,
        context_summary=context_summary,
        detected_signals=detected_signals or [],
        triage_level=triage_level,
    )
    _escalations[record.escalation_id] = record

    logger.warning(
        "人工升级创建 escalation_id=%s session=%s reason=%s severity=%s",
        record.escalation_id, session_id, reason.value, severity.value,
    )

    if notify:
        _notify(record)

    return record


def get_escalation(escalation_id: str) -> Optional[EscalationRecord]:
    """获取升级记录."""
    return _escalations.get(escalation_id)


def get_session_escalations(session_id: str) -> list[EscalationRecord]:
    """获取会话的所有升级记录."""
    return [r for r in _escalations.values() if r.session_id == session_id]


def acknowledge_escalation(escalation_id: str, notes: str = "") -> Optional[EscalationRecord]:
    """确认升级."""
    record = _escalations.get(escalation_id)
    if record and record.status == EscalationStatus.PENDING:
        record.status = EscalationStatus.ACKNOWLEDGED
        record.acknowledged_at = datetime.now(timezone.utc).isoformat()
        record.notes = notes
        logger.info("升级已确认 escalation_id=%s", escalation_id)
    return record


def resolve_escalation(escalation_id: str, notes: str = "") -> Optional[EscalationRecord]:
    """解决升级."""
    record = _escalations.get(escalation_id)
    if record and record.status in (EscalationStatus.PENDING, EscalationStatus.ACKNOWLEDGED):
        record.status = EscalationStatus.RESOLVED
        record.resolved_at = datetime.now(timezone.utc).isoformat()
        if notes:
            record.notes = notes
        logger.info("升级已解决 escalation_id=%s", escalation_id)
    return record


def list_pending_escalations() -> list[EscalationRecord]:
    """列出所有待处理的升级."""
    return [r for r in _escalations.values() if r.status == EscalationStatus.PENDING]


def get_escalation_stats() -> dict:
    """获取升级统计."""
    total = len(_escalations)
    pending = sum(1 for r in _escalations.values() if r.status == EscalationStatus.PENDING)
    acknowledged = sum(1 for r in _escalations.values() if r.status == EscalationStatus.ACKNOWLEDGED)
    resolved = sum(1 for r in _escalations.values() if r.status == EscalationStatus.RESOLVED)
    return {
        "total": total,
        "pending": pending,
        "acknowledged": acknowledged,
        "resolved": resolved,
    }


# ── 升级触发条件检查 ──

def should_escalate_from_triage(triage_level: str) -> bool:
    """分流级别为 EMERGENCY 时触发升级."""
    return triage_level == "emergency"


def should_escalate_from_user_request(text: str) -> bool:
    """检测用户是否明确要求转人工."""
    request_patterns = [
        "转人工", "人工客服", "找医生", "找大夫",
        "真人医生", "真人", "不要机器人", "不要AI",
        "我要找医生", "帮我叫医生", "联系医生",
    ]
    return any(p in text for p in request_patterns)


def should_escalate_from_low_confidence(
    confidence_history: list[float], threshold: float = 0.3, consecutive: int = 2
) -> bool:
    """连续 N 轮置信度低于阈值时触发升级."""
    if len(confidence_history) < consecutive:
        return False
    return all(c < threshold for c in confidence_history[-consecutive:])


def determine_escalation_priority(
    reason: EscalationReason,
    triage_level: str = "",
) -> EscalationSeverity:
    """根据原因和分流级别确定优先级."""
    if reason == EscalationReason.EMERGENCY_SYMPTOM or triage_level == "emergency":
        return EscalationSeverity.CRITICAL
    if reason in (EscalationReason.HALLUCINATION_REPEATED, EscalationReason.SAFETY_GUARD_TRIGGERED):
        return EscalationSeverity.HIGH
    if reason == EscalationReason.LOW_CONFIDENCE:
        return EscalationSeverity.MEDIUM
    return EscalationSeverity.MEDIUM
