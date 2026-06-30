"""多级 Triage 分流 —— 三级分类：EMERGENCY / URGENT / ROUTINE.

EMERGENCY — 立即拨打 120 或前往急诊，自动触发人工升级
URGENT   — 建议 24 小时内就诊
ROUTINE  — 常规医疗咨询，正常对话
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TriageLevel(str, Enum):
    EMERGENCY = "emergency"
    URGENT = "urgent"
    ROUTINE = "routine"


# ── 紧急症状：危及生命，需立即就医 ──
EMERGENCY_SYMPTOM_MAP: dict[str, str] = {
    "胸痛": "疑似心绞痛/心肌梗死",
    "呼吸困难": "疑似呼吸系统急症",
    "剧烈头痛": "疑似脑血管意外",
    "意识模糊": "疑似神经系统急症",
    "大量出血": "疑似消化道出血/外伤",
    "高热不退": "疑似严重感染",
    "抽搐": "疑似癫痫/脑部病变",
    "晕厥": "疑似心血管急症",
    "剧烈腹痛": "疑似急腹症",
    "严重过敏": "疑似过敏性休克",
    "呕血": "疑似上消化道大出血",
    "黑便": "疑似消化道出血",
}

# ── 亚紧急症状：需尽快就医但不一定是即刻 ──
URGENT_SYMPTOMS: set[str] = {
    "胸痛",        # 已被紧急覆盖，但非剧烈时也可降级
    "呼吸困难",    # 同上
    "高烧",
    "突然加重",
    "不良反应",
    "副作用",
    "过敏反应",
    "心悸",
    "心慌",
    "胸闷",
    "水肿",
    "浮肿",
    "消瘦",
    "体重下降",
    "视力模糊",
    "血尿",
    "黄疸",
}

# ── 亚紧急药物信号 ──
URGENT_MEDICATION_SIGNALS: set[str] = {
    "不良反应",
    "副作用",
    "过敏反应",
    "重复用药",
}

# ── 紧急关键词列表（向后兼容） ──
EMERGENCY_KEYWORDS: list[str] = list(EMERGENCY_SYMPTOM_MAP.keys())

# ── 否定词和历时词（复用现有逻辑） ──
_NEGATION_WORDS = [
    "没", "不", "无", "否", "未", "没有", "不是", "不会",
    "不要", "不能", "不必", "不用", "已缓解", "已好转", "已消失", "好了", "没事",
]
_HISTORICAL_WORDS = [
    "之前", "以前", "过去", "曾", "曾经", "之前有过", "已有",
    "早就", "原来", "原来有", "既往", "旧病", "老毛病",
]


def _has_negation(text: str, term: str, window: int = 15) -> bool:
    """检查 term 附近是否有否定/缓解语义."""
    idx = text.find(term)
    if idx < 0:
        return False
    start = max(0, idx - window)
    prefix = text[start:idx]
    end = min(len(text), idx + len(term) + window)
    suffix = text[idx + len(term):end]
    combined = prefix + suffix
    return any(w in combined for w in _NEGATION_WORDS)


def _is_historical(text: str, term: str, window: int = 15) -> bool:
    """检查 term 附近是否有过去时语义."""
    idx = text.find(term)
    if idx < 0:
        return False
    start = max(0, idx - window)
    prefix = text[start:idx]
    return any(w in prefix for w in _HISTORICAL_WORDS)


def _is_explicit_negation_of_urgency(text: str) -> bool:
    """检查是否用户明确表示非紧急."""
    decline_patterns = [
        r"(?:不是|没有|并非|不算)(?:紧急|危重|重症|急症)",
        r"(?:不|没)(?:需要|用|会)(?:去|叫|打)(?:急诊|医院|120)",
        r"只是.{0,6}(?:问问|咨询|了解)",
        r"不要.{0,6}(?:紧张|担心)",
    ]
    return any(re.search(p, text) for p in decline_patterns)


@dataclass
class TriageResult:
    """分流结果."""
    level: TriageLevel
    reason: str = ""
    detected_symptoms: list[str] = field(default_factory=list)
    emergency_symptoms: list[str] = field(default_factory=list)
    urgent_signals: list[str] = field(default_factory=list)
    should_escalate: bool = False

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "reason": self.reason,
            "detected_symptoms": self.detected_symptoms,
            "emergency_symptoms": self.emergency_symptoms,
            "urgent_signals": self.urgent_signals,
            "should_escalate": self.should_escalate,
        }


def triage(
    text: str,
    *,
    red_flags: Optional[list[str]] = None,
    medication_flags: Optional[list[str]] = None,
) -> TriageResult:
    """对用户输入执行三级分流.

    Args:
        text: 用户输入的文本
        red_flags: 已提取的红旗信号列表
        medication_flags: 已提取的用药信号列表

    Returns:
        TriageResult 包含分流级别和详情
    """
    red_flags = red_flags or []
    medication_flags = medication_flags or []

    detected_symptoms: list[str] = []
    emergency_symptoms: list[str] = []
    urgent_signals: list[str] = []

    # 1. 检查紧急症状
    for symptom, description in EMERGENCY_SYMPTOM_MAP.items():
        if symptom not in text:
            continue
        if _has_negation(text, symptom):
            continue
        if _is_historical(text, symptom):
            continue
        detected_symptoms.append(symptom)
        emergency_symptoms.append(f"{symptom}（{description}）")

    # 2. 检查亚紧急症状（排除已被紧急覆盖的）
    for symptom in URGENT_SYMPTOMS:
        if symptom not in text:
            continue
        if symptom in emergency_symptoms:
            continue
        if _has_negation(text, symptom):
            continue
        if _is_historical(text, symptom):
            continue
        urgent_signals.append(symptom)

    # 3. 检查药物紧急信号
    for signal in URGENT_MEDICATION_SIGNALS:
        if signal in text and signal not in urgent_signals:
            urgent_signals.append(signal)

    # 4. 合并已提取的红旗和用药信号
    for flag in red_flags:
        if flag in EMERGENCY_SYMPTOM_MAP:
            if flag not in [s.split("（")[0] for s in emergency_symptoms]:
                emergency_symptoms.append(f"{flag}（{EMERGENCY_SYMPTOM_MAP.get(flag, '')})")
        else:
            if flag not in urgent_signals:
                urgent_signals.append(flag)

    for flag in medication_flags:
        if flag in URGENT_MEDICATION_SIGNALS and flag not in urgent_signals:
            urgent_signals.append(flag)

    # 5. 判定级别
    if _is_explicit_negation_of_urgency(text):
        # 用户明确表示不紧急
        return TriageResult(
            level=TriageLevel.ROUTINE,
            reason="用户表示非紧急",
            detected_symptoms=detected_symptoms,
            emergency_symptoms=[],
            urgent_signals=urgent_signals,
            should_escalate=False,
        )

    if emergency_symptoms:
        return TriageResult(
            level=TriageLevel.EMERGENCY,
            reason=f"检测到紧急症状: {', '.join(emergency_symptoms)}",
            detected_symptoms=detected_symptoms,
            emergency_symptoms=emergency_symptoms,
            urgent_signals=urgent_signals,
            should_escalate=True,
        )

    if urgent_signals:
        return TriageResult(
            level=TriageLevel.URGENT,
            reason=f"检测到需关注的信号: {', '.join(urgent_signals[:5])}",
            detected_symptoms=detected_symptoms,
            emergency_symptoms=[],
            urgent_signals=urgent_signals,
            should_escalate=False,
        )

    return TriageResult(
        level=TriageLevel.ROUTINE,
        reason="常规咨询",
        detected_symptoms=detected_symptoms,
        emergency_symptoms=[],
        urgent_signals=[],
        should_escalate=False,
    )


def triage_from_risk_signals(
    text: str,
    red_flags: Optional[list[str]] = None,
    medication_flags: Optional[list[str]] = None,
) -> TriageResult:
    """从 risk signals 上下文执行分流（用于 risk_signals 提取后调用）."""
    return triage(text, red_flags=red_flags, medication_flags=medication_flags)


def format_triage_advice(result: TriageResult) -> str:
    """根据分流结果生成用户可见的建议文本."""
    if result.level == TriageLevel.EMERGENCY:
        symptoms_text = "、".join(result.emergency_symptoms[:4])
        return (
            f"\n\n🚨 **紧急提醒**：你描述的症状包含 {symptoms_text}，"
            f"这些可能是危及生命的急症。请**立即拨打 120 急救电话**"
            f"或尽快前往最近的急诊科就诊，不要延误！"
        )
    elif result.level == TriageLevel.URGENT:
        signals_text = "、".join(result.urgent_signals[:4])
        return (
            f"\n\n⚠️ **建议尽快就医**：你提到的{signals_text}是需要重视的信号，"
            f"建议在 24 小时内前往医院就诊，不要仅依赖线上咨询来判断。"
        )
    else:
        return ""


def detect_emergency_symptoms(answer: str) -> list[str]:
    """向后兼容：检测回答中的紧急症状."""
    detected = []
    for keyword, description in EMERGENCY_SYMPTOM_MAP.items():
        if keyword in answer:
            detected.append(f"{keyword}（{description}）")
    return detected
