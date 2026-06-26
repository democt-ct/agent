"""
Enhanced Intent Recognition Module
混合意图识别：关键词匹配优先，LLM兜底
"""
import os
import re
import json
import httpx
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

# ================= 配置 =================
TEXT_MODEL = os.getenv("TEXT_MODEL", "deepseek-ai/DeepSeek-V3.2")
TEXT_API_KEY = os.getenv("TEXT_API_KEY", os.getenv("OPENAI_API_KEY", "ms-4ecca729-328f-4e74-9d9b-39fa76e5b56b"))
TEXT_API_BASE = os.getenv("TEXT_API_BASE", os.getenv("OPENAI_BASE_URL", "https://api-inference.modelscope.cn/v1/"))
# ==========================================


@dataclass
class EnhancedIntent:
    """增强版用户意图"""
    city: str = ""
    interests: List[str] = field(default_factory=list)
    avoid: List[str] = field(default_factory=list)
    pace: str = "适中"
    budget: str = "适中"
    day_count: int = 1
    hotel_area: str = ""
    confidence: float = 0.0
    source: str = "keyword"  # keyword / llm


# 关键词映射
INTEREST_KEYWORDS = {
    "美食": ["美食", "好吃", "小吃", "吃", "火锅", "烧烤", "川菜", "串串", "冒菜", "面", "粉", "兔头", "甜水面"],
    "购物": ["购物", "逛街", "商场", "买", "特产", "伴手礼"],
    "文化": ["文化", "历史", "博物馆", "古迹", "古镇", "古城", "遗址"],
    "自然": ["自然", "公园", "爬山", "徒步", "露营", "湖", "山"],
    "夜生活": ["夜生活", "酒吧", "夜市", "夜景", "宵夜"],
    "拍照": ["拍照", "出片", "摄影", "打卡"],
    "咖啡": ["咖啡", "cafe", "茶馆"],
    "亲子": ["亲子", "带娃", "小朋友", "孩子"],
}

AVOID_KEYWORDS = {
    "商场": ["不要商场", "不想逛商场", "避开商场", "不去商场"],
    "人多": ["人少", "不挤", "避开人群", "人太多"],
    "网红店": ["不要网红", "不想去网红", "避开网红"],
    "商业化": ["太商业化", "商业化"],
}

PACE_KEYWORDS = {
    "轻松": ["轻松", "休闲", "慢慢逛", "不赶", "佛系"],
    "紧凑": ["紧凑", "特种兵", "暴走", "多去几个"],
}

BUDGET_KEYWORDS = {
    "经济": ["便宜", "省钱", "经济", "性价比"],
    "高端": ["高端", "品质", "精致"],
}

CITY_PATTERNS = [
    r"去(.+?)(?:玩|旅游|逛|吃|旅行|攻略|推荐)",
    r"(.+?)(?:旅游|旅行|游玩|攻略)",
    r"在(.+?)(?:玩|逛|吃)",
]

DAY_PATTERNS = [
    (r"(\d+)\s*天", lambda m: int(m.group(1))),
    (r"(\d+)\s*日", lambda m: int(m.group(1))),
    (r"两\s*天", lambda m: 2),
    (r"三\s*天", lambda m: 3),
    (r"四\s*天", lambda m: 4),
    (r"五\s*天", lambda m: 5),
    (r"周末", lambda m: 2),
]


def extract_intent_by_keywords(message: str) -> EnhancedIntent:
    """快速路径：关键词匹配"""
    text = message.strip()
    intent = EnhancedIntent()
    
    # 提取城市
    for pattern in CITY_PATTERNS:
        match = re.search(pattern, text)
        if match:
            city = match.group(1).strip()
            if 2 <= len(city) <= 6:
                intent.city = city
                break
    
    # 提取兴趣
    for interest, keywords in INTEREST_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            intent.interests.append(interest)
    
    # 提取避开项
    for avoid_item, keywords in AVOID_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            intent.avoid.append(avoid_item)
    
    # 提取节奏
    for pace, keywords in PACE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            intent.pace = pace
            break
    
    # 提取预算
    for budget, keywords in BUDGET_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            intent.budget = budget
            break
    
    # 提取天数
    for pattern, extractor in DAY_PATTERNS:
        match = re.search(pattern, text)
        if match:
            intent.day_count = extractor(match)
            break
    
    # 计算置信度
    score = 0.3 if intent.city else 0
    score += 0.3 if intent.interests else 0
    score += 0.1 if intent.day_count > 1 else 0
    score += 0.1 if intent.pace != "适中" else 0
    score += 0.1 if intent.budget != "适中" else 0
    intent.confidence = min(score, 1.0)
    
    return intent


def needs_llm_fallback(message: str, intent: EnhancedIntent) -> bool:
    """判断是否需要LLM兜底"""
    text = message.strip()
    
    if intent.confidence < 0.4:
        return True
    if not intent.city:
        return True
    if "？" in text or "?" in text:
        return True
    vague_keywords = ["什么", "哪里", "哪些", "推荐", "攻略", "怎么", "如何"]
    if any(kw in text for kw in vague_keywords):
        return True
    return False


def analyze_intent_by_llm(message: str) -> Optional[EnhancedIntent]:
    """慢速路径：LLM深度分析"""
    system_prompt = """分析用户旅游需求，输出JSON：
{"city":"城市名","interests":["兴趣"],"avoid":["避开"],"pace":"轻松/紧凑/适中","budget":"经济/适中/高端","day_count":天数}

interests可选：美食、购物、文化、自然、夜生活、拍照、咖啡、亲子
avoid可选：商场、人多、网红店、商业化
只提取明确信息，未说明用默认值"""

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{TEXT_API_BASE}chat/completions",
                headers={
                    "Authorization": f"Bearer {TEXT_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": TEXT_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"分析：{message}"}
                    ],
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            
            json_match = re.search(r'\{[^{}]+\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return EnhancedIntent(
                    city=result.get("city", ""),
                    interests=result.get("interests", []),
                    avoid=result.get("avoid", []),
                    pace=result.get("pace", "适中"),
                    budget=result.get("budget", "适中"),
                    day_count=result.get("day_count", 1),
                    confidence=0.9,
                    source="llm"
                )
    except Exception as e:
        print(f"[LLM分析] 失败: {e}")
    
    return None


def recognize_intent_enhanced(message: str) -> EnhancedIntent:
    """
    混合意图识别主入口
    关键词优先，LLM兜底
    """
    # 快速路径
    intent = extract_intent_by_keywords(message)
    
    # 判断是否需要LLM
    if needs_llm_fallback(message, intent):
        print("[意图识别] 启用LLM分析...")
        llm_intent = analyze_intent_by_llm(message)
        if llm_intent:
            # 合并：LLM优先
            if llm_intent.city:
                intent.city = llm_intent.city
            if llm_intent.interests:
                intent.interests = llm_intent.interests
            if llm_intent.avoid:
                intent.avoid = llm_intent.avoid
            if llm_intent.pace != "适中":
                intent.pace = llm_intent.pace
            if llm_intent.budget != "适中":
                intent.budget = llm_intent.budget
            if llm_intent.day_count > 1:
                intent.day_count = llm_intent.day_count
            intent.confidence = llm_intent.confidence
            intent.source = "llm"
    else:
        print(f"[意图识别] 快速匹配成功，置信度: {intent.confidence:.2f}")
    
    return intent


def to_requirement_payload(intent: EnhancedIntent) -> Dict[str, Any]:
    """转换为现有项目的requirement_payload格式"""
    # 映射pace到trip_style
    pace_to_style = {"轻松": "relaxed", "紧凑": "compact", "适中": "moderate"}
    
    # 映射budget到budget_level
    budget_to_level = {"经济": "value", "适中": "moderate", "高端": "premium"}
    
    # 映射day_count到time_budget
    if intent.day_count == 1:
        time_budget = "one_day"
    elif intent.day_count > 1:
        time_budget = "multi_day"
    else:
        time_budget = "flexible"
    
    return {
        "city": intent.city,
        "theme": intent.interests[0] if intent.interests else "general",
        "trip_style": pace_to_style.get(intent.pace, "moderate"),
        "must_have": intent.interests,
        "avoid": intent.avoid,
        "time_budget": time_budget,
        "day_count": intent.day_count,
        "radius_meters": 5000,
        "location_scope": "city_only",
        "anchor_location": None,
        "poi_preference": None,
        "intent_clarity": intent.confidence,
        "follow_up_questions": [],
        "_enhanced_intent": {
            "source": intent.source,
            "budget": intent.budget,
            "hotel_area": intent.hotel_area,
        }
    }


# ================= 测试 =================
if __name__ == '__main__':
    test_cases = [
        "我想去成都吃美食，不想逛商场",
        "成都3天怎么玩",
        "去成都旅游，想吃好吃的",
        "成都有什么好玩的",
        "我想去成都逛街购物",
        "周末去成都轻松玩两天",
        "成都美食攻略",
        "带孩子去成都玩",
    ]
    
    for msg in test_cases:
        print(f"\n{'='*50}")
        print(f"输入: {msg}")
        intent = recognize_intent_enhanced(msg)
        print(f"城市: {intent.city}, 兴趣: {intent.interests}, 避开: {intent.avoid}")
        print(f"节奏: {intent.pace}, 预算: {intent.budget}, 天数: {intent.day_count}")
        print(f"置信度: {intent.confidence:.2f}, 来源: {intent.source}")
        
        payload = to_requirement_payload(intent)
        print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
