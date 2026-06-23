"""
Two-stage intent assessment and five-dimension preference extraction.
Stage 1 (VAGUE): only recommend landmarks + ask follow-up questions.
Stage 2 (CLEAR): five-dimension weighted ranking.
"""
import re
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from poi_tags import (
    EXPERIENCE_VOCAB, CROWD_VOCAB, FunctionDimension,
    TimeDimension, BudgetDimension,
)


# ── Enums ───────────────────────────────────────────────────────

class IntentClarity(str, Enum):
    VAGUE = "vague"
    PARTIAL = "partial"
    CLEAR = "clear"


# ── Models ──────────────────────────────────────────────────────

class FiveDimPreference(BaseModel):
    function_weights: Dict[str, float] = Field(default_factory=lambda: {"attraction": 1.0})
    experience_desired: List[str] = Field(default_factory=list)
    crowd_required: List[str] = Field(default_factory=list)
    time_preference: Optional[TimeDimension] = None
    budget_preference: Optional[BudgetDimension] = None
    landmark_only: bool = False


class IntentExtractionResult(BaseModel):
    clarity: IntentClarity = IntentClarity.VAGUE
    preference: FiveDimPreference = Field(default_factory=FiveDimPreference)
    follow_up_questions: List[str] = Field(default_factory=list)


# ── Follow-up question templates ────────────────────────────────

_FOLLOW_UP_TEMPLATES = {
    "experience": "你更偏好哪种体验？（自然风光 / 历史文化 / 美食探索 / 慢节奏 / 拍照打卡）",
    "crowd": "这次出行是跟谁一起？（独自 / 情侣 / 亲子 / 带长辈 / 朋友聚会）",
    "budget": "你对预算有什么要求？（经济实惠 / 适中 / 品质优先）",
    "pace": "你希望行程节奏怎样？（轻松休闲 / 适中 / 紧凑特种兵）",
}


# ── Helpers ─────────────────────────────────────────────────────

def _norm(value: Any) -> str:
    return re.sub(r"[^一-龥a-z0-9]", "", str(value or "").strip().lower())


# ── Map existing requirement fields to five-dimension preference ──

def _map_requirement_to_fivedim(requirement_payload: Dict[str, Any], message: str) -> FiveDimPreference:
    func_weights: Dict[str, float] = {"attraction": 1.0}
    experience: List[str] = []
    crowd: List[str] = []
    time_pref: Optional[TimeDimension] = None
    budget_pref: Optional[BudgetDimension] = None

    must_have = set(requirement_payload.get("must_have") or [])
    avoid = set(requirement_payload.get("avoid") or [])
    theme = _norm(requirement_payload.get("theme"))
    trip_style = _norm(requirement_payload.get("trip_style"))
    text = _norm(message)

    # must_have → experience / function
    if "美食" in must_have:
        func_weights["food"] = func_weights.get("food", 0) + 1.5
        experience.append("美食探索")
    if "夜景" in must_have:
        experience.append("夜生活")
    if "公园" in must_have:
        experience.append("自然风光")
    if "博物馆" in must_have:
        experience.append("历史文化")
    if "商场" in must_have:
        experience.append("购物休闲")
    if "拍照" in must_have:
        experience.append("拍照打卡")
    if "古镇" in must_have:
        experience.append("历史文化")
    if "咖啡" in must_have:
        func_weights["food"] = func_weights.get("food", 0) + 0.8
        experience.append("文艺小资")

    # theme → experience
    if theme in ("nature", "自然"):
        experience.append("自然风光")
    elif theme in ("culture", "文化"):
        experience.append("历史文化")
    elif theme in ("food", "美食"):
        experience.append("美食探索")
        func_weights["food"] = func_weights.get("food", 0) + 1.0
    elif theme in ("night_view", "夜景"):
        experience.append("夜生活")

    # trip_style → experience
    if trip_style in ("relaxed", "轻松"):
        experience.append("慢节奏")
    elif trip_style in ("compact", "特种兵"):
        experience.append("特种兵")

    # memory_profile → crowd / budget
    mem = requirement_payload.get("memory_profile") or {}
    long_term = (mem.get("long_term") or {}).get("preferences") or {}

    if long_term.get("family_friendly"):
        crowd.append("亲子友好")
    if long_term.get("likes_food"):
        func_weights["food"] = func_weights.get("food", 0) + 0.5
        if "美食探索" not in experience:
            experience.append("美食探索")
    if long_term.get("low_fatigue") and "慢节奏" not in experience:
        experience.append("慢节奏")
    if long_term.get("likes_niche") and "拍照打卡" not in experience:
        experience.append("拍照打卡")

    budget_level = long_term.get("budget_level")
    if budget_level == "premium":
        budget_pref = BudgetDimension(price_level=3)
    elif budget_level == "value":
        budget_pref = BudgetDimension(price_level=1)
    elif budget_level == "moderate":
        budget_pref = BudgetDimension(price_level=2)

    # Direct text signals for crowd
    if re.search(r"(亲子|带娃|小朋友|孩子)", text):
        if "亲子友好" not in crowd:
            crowd.append("亲子友好")
    if re.search(r"(情侣|约会|浪漫)", text):
        if "情侣约会" not in crowd:
            crowd.append("情侣约会")
    if re.search(r"(带长辈|带老人|父母|爸妈|爸妈)", text):
        if "带长辈" not in crowd:
            crowd.append("带长辈")
    if re.search(r"(一个人|独自|单人)", text):
        if "单人" not in crowd:
            crowd.append("单人")

    # Direct text signals for budget
    if re.search(r"(预算高|贵一点|品质|高端)", text):
        budget_pref = BudgetDimension(price_level=3)
    elif re.search(r"(预算低|省钱|便宜|性价比)", text):
        budget_pref = BudgetDimension(price_level=1)

    # Deduplicate
    experience = list(dict.fromkeys(e for e in experience if e in EXPERIENCE_VOCAB))
    crowd = list(dict.fromkeys(c for c in crowd if c in CROWD_VOCAB))

    return FiveDimPreference(
        function_weights=func_weights,
        experience_desired=experience,
        crowd_required=crowd,
        time_preference=time_pref,
        budget_preference=budget_pref,
    )


# ── Main assessment function ────────────────────────────────────

def assess_intent_clarity(
    requirement_payload: Dict[str, Any],
    message: str,
) -> IntentExtractionResult:
    """
    Assess user intent clarity and extract five-dimension preferences.
    Returns IntentExtractionResult with clarity level, preference, and follow-up questions.
    """
    preference = _map_requirement_to_fivedim(requirement_payload, message)

    # Score how much information we have
    score = 0
    must_have = requirement_payload.get("must_have") or []
    score += min(len(must_have) * 2, 6)

    mem = requirement_payload.get("memory_profile") or {}
    long_term_prefs = (mem.get("long_term") or {}).get("preferences") or {}
    score += sum(1 for v in long_term_prefs.values() if v is not None)

    if preference.budget_preference is not None:
        score += 1
    theme = _norm(requirement_payload.get("theme"))
    if theme and theme != "general":
        score += 1
    trip_style = _norm(requirement_payload.get("trip_style"))
    if trip_style and trip_style not in ("moderate", ""):
        score += 1
    if preference.crowd_required:
        score += 2
    if len(preference.experience_desired) >= 2:
        score += 1

    # Determine clarity
    if score <= 2:
        clarity = IntentClarity.VAGUE
        preference.landmark_only = True
    elif score <= 5:
        clarity = IntentClarity.PARTIAL
    else:
        clarity = IntentClarity.CLEAR

    # Generate follow-up questions for missing dimensions
    follow_ups: List[str] = []
    if not preference.experience_desired:
        follow_ups.append(_FOLLOW_UP_TEMPLATES["experience"])
    if not preference.crowd_required:
        follow_ups.append(_FOLLOW_UP_TEMPLATES["crowd"])
    if preference.budget_preference is None:
        follow_ups.append(_FOLLOW_UP_TEMPLATES["budget"])
    if not preference.experience_desired and _norm(requirement_payload.get("trip_style")) not in ("relaxed", "compact"):
        follow_ups.append(_FOLLOW_UP_TEMPLATES["pace"])

    return IntentExtractionResult(
        clarity=clarity,
        preference=preference,
        follow_up_questions=follow_ups,
    )


# ── Ranking weight derivation ───────────────────────────────────

def derive_ranking_weights(preference: FiveDimPreference) -> Dict[str, float]:
    return {
        "function_match": 1.0,
        "experience_overlap": 1.5 if preference.experience_desired else 0.5,
        "crowd_match": 1.2 if preference.crowd_required else 0.3,
        "time_fit": 0.8,
        "budget_fit": 1.0 if preference.budget_preference else 0.3,
        "landmark_bonus": 0.6,
    }


def jaccard(a: List[str], b: List[str]) -> float:
    if not a and not b:
        return 0.0
    sa, sb = set(a), set(b)
    intersection = sa & sb
    union = sa | sb
    return len(intersection) / len(union) if union else 0.0


def time_fit_score(
    tag_best_time: List[str],
    pref_time: Optional[TimeDimension],
) -> float:
    if not pref_time or not pref_time.best_time:
        return 1.0
    if not tag_best_time:
        return 0.5
    overlap = set(tag_best_time) & set(pref_time.best_time)
    return len(overlap) / max(len(set(pref_time.best_time)), 1)


def budget_fit_score(
    tag_price_level: int,
    pref_budget: Optional[BudgetDimension],
) -> float:
    if not pref_budget:
        return 1.0
    diff = abs(tag_price_level - pref_budget.price_level)
    if diff == 0:
        return 1.0
    if diff == 1:
        return 0.5
    return 0.0
