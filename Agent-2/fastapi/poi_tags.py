"""
Five-dimension POI tag system: replaces the flat `kind` string with structured
tags covering Function, Experience, Crowd, Time, and Budget dimensions.
"""
import re
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field


# ── Controlled vocabularies ────────────────────────────────────

EXPERIENCE_VOCAB = [
    "自然风光", "拍照打卡", "历史文化", "特种兵", "慢节奏",
    "亲子互动", "美食探索", "夜生活", "文艺小资", "购物休闲",
]

CROWD_VOCAB = [
    "亲子友好", "情侣约会", "带长辈", "单人", "朋友聚会",
]


# ── Enums ───────────────────────────────────────────────────────

class FunctionDimension(str, Enum):
    ATTRACTION = "attraction"
    FOOD = "food"
    STAY = "stay"
    TRANSPORT = "transport"


# ── Sub-models ──────────────────────────────────────────────────

class TimeDimension(BaseModel):
    duration_hours: float = Field(default=2.0, ge=0.5, le=12.0)
    best_time: List[str] = Field(default_factory=lambda: ["上午", "下午"])


class BudgetDimension(BaseModel):
    price_level: int = Field(default=2, ge=1, le=4)


# ── Core model ──────────────────────────────────────────────────

class POITag(BaseModel):
    function: FunctionDimension = FunctionDimension.ATTRACTION
    experience: List[str] = Field(default_factory=list)
    crowd: List[str] = Field(default_factory=list)
    time: TimeDimension = Field(default_factory=TimeDimension)
    budget: BudgetDimension = Field(default_factory=BudgetDimension)
    is_landmark: bool = False
    legacy_place_kind: str = ""


# ── Mapping tables ──────────────────────────────────────────────

LEGACY_KIND_TO_FUNCTION: Dict[str, FunctionDimension] = {
    "attraction": FunctionDimension.ATTRACTION,
    "museum": FunctionDimension.ATTRACTION,
    "park": FunctionDimension.ATTRACTION,
    "old_street": FunctionDimension.ATTRACTION,
    "night_view": FunctionDimension.ATTRACTION,
    "admin_area": FunctionDimension.TRANSPORT,
    "food_area": FunctionDimension.FOOD,
    "food_poi": FunctionDimension.FOOD,
    "cafe": FunctionDimension.FOOD,
    "bar": FunctionDimension.FOOD,
    "shopping": FunctionDimension.ATTRACTION,
    "lodging": FunctionDimension.STAY,
    "transport": FunctionDimension.TRANSPORT,
}

_FUNCTION_DURATION: Dict[FunctionDimension, float] = {
    FunctionDimension.ATTRACTION: 2.0,
    FunctionDimension.FOOD: 1.5,
    FunctionDimension.STAY: 1.0,
    FunctionDimension.TRANSPORT: 0.5,
}

_FUNCTION_BEST_TIME: Dict[FunctionDimension, List[str]] = {
    FunctionDimension.ATTRACTION: ["上午", "下午"],
    FunctionDimension.FOOD: ["中午", "晚上"],
    FunctionDimension.STAY: ["下午"],
    FunctionDimension.TRANSPORT: [],
}


def function_to_legacy_kind(tag: POITag) -> str:
    if tag.legacy_place_kind:
        return tag.legacy_place_kind
    if tag.function == FunctionDimension.ATTRACTION:
        if "历史文化" in tag.experience:
            return "museum"
        if "自然风光" in tag.experience:
            return "park"
        if "夜生活" in tag.experience:
            return "night_view"
        return "attraction"
    if tag.function == FunctionDimension.FOOD:
        if "文艺小资" in tag.experience:
            return "cafe"
        if "夜生活" in tag.experience:
            return "bar"
        if "美食探索" in tag.experience:
            return "food_area"
        return "food_poi"
    if tag.function == FunctionDimension.STAY:
        return "lodging"
    if tag.function == FunctionDimension.TRANSPORT:
        return "transport"
    return "attraction"


# ── Helpers ─────────────────────────────────────────────────────

def _norm(value: Any) -> str:
    return re.sub(r"[^一-龥a-z0-9]", "", str(value or "").strip().lower())


# ── Rule-based tag inference ───────────────────────────────────

def infer_poi_tags(
    name: str,
    category: str = "",
    query: str = "",
    legacy_place_kind: str = "",
) -> POITag:
    """
    Infer a POITag from available POI metadata.
    Subsumes and replaces _infer_planner_place_kind for new code paths.
    """
    source = " ".join([_norm(name), _norm(category), _norm(query)])
    func = FunctionDimension.ATTRACTION
    experience: List[str] = []
    crowd: List[str] = []
    duration = 2.0
    best_time = ["上午", "下午"]
    price_level = 2

    # ── Function determination (same cascade as old _infer_planner_place_kind) ──
    if re.search(r"(酒店|宾馆|旅馆|住宿|民宿|客栈|hotel)", source, re.IGNORECASE):
        func = FunctionDimension.STAY
    elif re.search(r"(地铁|公交|车站|机场|火车站|高铁|汽车站)", source):
        func = FunctionDimension.TRANSPORT
    elif re.search(r"(博物馆|纪念馆|美术馆|展览馆|科技馆|文化馆)", source):
        func = FunctionDimension.ATTRACTION
        experience = ["历史文化"]
        duration = 2.5
        best_time = ["上午", "下午"]
    elif re.search(r"(咖啡|cafe)", source, re.IGNORECASE):
        func = FunctionDimension.FOOD
        experience = ["文艺小资"]
        duration = 1.5
        best_time = ["下午"]
    elif re.search(r"(酒吧|清吧|bar)", source, re.IGNORECASE):
        func = FunctionDimension.FOOD
        experience = ["夜生活"]
        duration = 2.0
        best_time = ["晚上"]
    elif re.search(r"(夜景|夜游|夜市|江边夜景|观景台|灯光秀)", source):
        func = FunctionDimension.ATTRACTION
        experience = ["夜生活", "拍照打卡"]
        duration = 2.0
        best_time = ["晚上"]
    elif re.search(r"(商场|购物中心|商城|太古里|万象城|奥特莱斯)", source):
        func = FunctionDimension.ATTRACTION
        experience = ["购物休闲"]
        duration = 2.5
        best_time = ["下午", "晚上"]
    elif re.search(r"(美食街|小吃街|古街|步行街|街区|巷子|老街|商圈)", source):
        if re.search(r"(美食|小吃|餐饮|火锅|烧烤|串串)", source):
            func = FunctionDimension.FOOD
            experience = ["美食探索"]
            duration = 1.5
            best_time = ["中午", "晚上"]
        else:
            func = FunctionDimension.ATTRACTION
            experience = ["历史文化", "拍照打卡"]
            duration = 2.0
            best_time = ["下午", "晚上"]
    elif re.search(r"(火锅|餐厅|饭店|小吃|烧烤|面馆|餐饮|川菜|酒楼|食府)", source):
        func = FunctionDimension.FOOD
        experience = ["美食探索"]
        duration = 1.5
        best_time = ["中午", "晚上"]
    elif re.search(r"(公园|草坪|绿道|湿地)", source):
        func = FunctionDimension.ATTRACTION
        experience = ["自然风光", "慢节奏"]
        duration = 2.0
        best_time = ["上午", "下午"]
        price_level = 1
    elif re.search(r"^.{1,4}(镇|乡|街道|片区|新区|开发区|高新区|经济区)$", _norm(name)):
        func = FunctionDimension.TRANSPORT  # admin area, will be filtered
        experience = []
        best_time = []
    else:
        # Default attraction — check for experience hints
        if re.search(r"(山|湖|河|海|瀑布|峡谷|溶洞|草原|森林)", source):
            experience = ["自然风光", "拍照打卡"]
        elif re.search(r"(寺|庙|塔|阁|楼|宫|城墙|遗址|陵|故居)", source):
            experience = ["历史文化"]
        else:
            experience = ["拍照打卡"]

    # ── Crowd inference from name/category ──
    if re.search(r"(亲子|儿童|小朋友|孩子|游乐园|动物园|海洋馆|水族馆)", source):
        crowd = ["亲子友好"]
    elif re.search(r"(情侣|约会|浪漫|摩天轮)", source):
        crowd = ["情侣约会"]

    # ── Budget inference ──
    if re.search(r"(免费|公园|广场|绿道|湿地|步道|观景)", source):
        price_level = 1
    elif re.search(r"(高端|品质|奢华|五星|温泉|度假村)", source):
        price_level = 3

    # ── Fallback: if legacy_place_kind given and function not determined ──
    if legacy_place_kind and legacy_place_kind in LEGACY_KIND_TO_FUNCTION:
        if func == FunctionDimension.ATTRACTION and not experience:
            func = LEGACY_KIND_TO_FUNCTION[legacy_place_kind]

    # ── Duration from function ──
    duration = _FUNCTION_DURATION.get(func, 2.0)
    if not best_time or best_time == ["上午", "下午"]:
        best_time = list(_FUNCTION_BEST_TIME.get(func, ["上午", "下午"]))

    # ── Build legacy_place_kind for backward compat ──
    if not legacy_place_kind:
        legacy_place_kind = function_to_legacy_kind(POITag(
            function=func,
            experience=experience,
            crowd=crowd,
            time=TimeDimension(duration_hours=duration, best_time=best_time),
            budget=BudgetDimension(price_level=price_level),
            legacy_place_kind="",
        ))

    return POITag(
        function=func,
        experience=experience,
        crowd=crowd,
        time=TimeDimension(duration_hours=duration, best_time=best_time),
        budget=BudgetDimension(price_level=price_level),
        is_landmark=False,
        legacy_place_kind=legacy_place_kind,
    )
