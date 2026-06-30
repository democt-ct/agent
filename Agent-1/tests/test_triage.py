"""多级 Triage 单元测试."""
import pytest

from app.mcp.triage import (
    TriageLevel,
    TriageResult,
    detect_emergency_symptoms,
    format_triage_advice,
    triage,
)


class TestTriageEmergency:
    """测试紧急级别分流."""

    def test_chest_pain_is_emergency(self):
        result = triage("我胸痛，像被压住一样")
        assert result.level == TriageLevel.EMERGENCY
        assert result.should_escalate
        assert any("胸痛" in s for s in result.emergency_symptoms)

    def test_breathing_difficulty_is_emergency(self):
        result = triage("我突然呼吸困难")
        assert result.level == TriageLevel.EMERGENCY
        assert result.should_escalate

    def test_multiple_emergency_symptoms(self):
        result = triage("胸痛伴呼吸困难，意识有点模糊")
        assert result.level == TriageLevel.EMERGENCY
        assert len(result.emergency_symptoms) >= 2

    def test_hematemesis_is_emergency(self):
        result = triage("我今天开始呕血，还有黑便")
        assert result.level == TriageLevel.EMERGENCY
        assert result.should_escalate


class TestTriageUrgent:
    """测试亚紧急级别分流."""

    def test_high_fever_is_urgent(self):
        result = triage("我一直高烧，三天了")
        assert result.level == TriageLevel.URGENT
        assert not result.should_escalate

    def test_palpitations_is_urgent(self):
        result = triage("最近总是心慌心悸")
        assert result.level == TriageLevel.URGENT

    def test_edema_is_urgent(self):
        result = triage("下肢浮肿持续一周了")
        assert result.level == TriageLevel.URGENT

    def test_drug_side_effect_is_urgent(self):
        result = triage("吃了这个药之后有不良反应")
        assert result.level == TriageLevel.URGENT


class TestTriageRoutine:
    """测试常规级别."""

    def test_common_cold_is_routine(self):
        result = triage("我有点咳嗽和流鼻涕")
        assert result.level == TriageLevel.ROUTINE
        assert not result.should_escalate

    def test_general_question_is_routine(self):
        result = triage("我血压有点偏高应该注意什么")
        assert result.level == TriageLevel.ROUTINE

    def test_empty_text_is_routine(self):
        result = triage("")
        assert result.level == TriageLevel.ROUTINE


class TestNegationHandling:
    """测试否定语义过滤."""

    def test_negated_chest_pain_not_emergency(self):
        result = triage("我没有胸痛")
        # "胸痛" should be filtered by negation
        assert result.level != TriageLevel.EMERGENCY

    def test_negated_breathing_not_emergency(self):
        result = triage("呼吸没有问题，不困难")
        assert result.level != TriageLevel.EMERGENCY

    def test_relieved_symptom_not_emergency(self):
        result = triage("之前胸痛但现在已缓解")
        assert result.level != TriageLevel.EMERGENCY

    def test_historical_symptom_not_emergency(self):
        result = triage("以前有过呼吸困难，已经确诊了")
        assert result.level != TriageLevel.EMERGENCY


class TestExplicitNegation:
    """测试显式非紧急声明."""

    def test_explicit_not_urgent(self):
        result = triage("不是紧急问题，就是想问一下检查结果")
        assert result.level == TriageLevel.ROUTINE

    def test_just_asking(self):
        result = triage("只是咨询一下，不用去医院")
        assert result.level == TriageLevel.ROUTINE


class TestFormatTriageAdvice:
    """测试分流建议生成."""

    def test_emergency_advice(self):
        result = TriageResult(
            level=TriageLevel.EMERGENCY,
            emergency_symptoms=["胸痛（疑似心绞痛/心肌梗死）"],
            should_escalate=True,
        )
        advice = format_triage_advice(result)
        assert "120" in advice or "急诊" in advice

    def test_urgent_advice(self):
        result = TriageResult(
            level=TriageLevel.URGENT,
            urgent_signals=["高烧", "心慌"],
        )
        advice = format_triage_advice(result)
        assert "24小时" in advice or "尽快" in advice

    def test_routine_no_advice(self):
        result = TriageResult(level=TriageLevel.ROUTINE)
        advice = format_triage_advice(result)
        assert advice == ""


class TestDetectEmergencySymptoms:
    """测试向后兼容的 detect_emergency_symptoms."""

    def test_detect_in_answer(self):
        detected = detect_emergency_symptoms("你的胸痛症状需要重视，建议尽快就医")
        assert any("胸痛" in d for d in detected)

    def test_no_emergency_in_answer(self):
        detected = detect_emergency_symptoms("你的血压偏高，注意低盐饮食")
        assert len(detected) == 0
