import os
import re
import httpx
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

# ================= 配置区 =================
openai_api_key = os.getenv("LLM_API_KEY", "ms-4ecca729-328f-4e74-9d9b-39fa76e5b56b")
openai_api_base = "https://api-inference.modelscope.cn/v1/"
TEXT_MODEL = "deepseek-ai/DeepSeek-V3.2"
# ==========================================


@dataclass
class UserIntent:
    """用户意图结构"""
    city: str = ""
    interests: List[str] = field(default_factory=list)
    avoid: List[str] = field(default_factory=list)
    pace: str = "适中"  # 轻松/紧凑/适中
    budget: str = "适中"  # 经济/适中/高端
    day_count: int = 1
    hotel_area: str = ""
    confidence: float = 0.0  # 意图识别置信度
    need_llm: bool = False   # 是否需要LLM进一步分析


# ================= 关键词匹配规则 =================

# 兴趣关键词映射
INTEREST_KEYWORDS = {
    "美食": ["美食", "好吃", "小吃", "吃", "火锅", "烧烤", "川菜", "串串", "冒菜", "面", "粉", "兔头", "甜水面"],
    "购物": ["购物", "逛街", "商场", "买", "特产", "伴手礼"],
    "文化": ["文化", "历史", "博物馆", "古迹", "古镇", "古城", "遗址", "祠堂", "庙"],
    "自然": ["自然", "公园", "爬山", "徒步", "露营", "湖", "山", "河"],
    "夜生活": ["夜生活", "酒吧", "夜市", "夜景", "宵夜", "深夜"],
    "拍照": ["拍照", "出片", "摄影", "打卡", "网红"],
    "咖啡": ["咖啡", "cafe", "茶", "茶馆"],
    "酒吧": ["酒吧", "清吧", "小酒馆"],
    "亲子": ["亲子", "带娃", "小朋友", "孩子", "小孩"],
}

# 避开关键词映射
AVOID_KEYWORDS = {
    "商场": ["不要商场", "不想逛商场", "避开商场", "不去商场", "拒绝商场"],
    "人多": ["人少", "不挤", "避开人群", "人太多", "太挤", "排队"],
    "网红店": ["不要网红", "不想去网红", "避开网红", "拒绝网红", "不是网红"],
    "商业化": ["太商业化", "商业化", "不要商业"],
}

# 节奏关键词映射
PACE_KEYWORDS = {
    "轻松": ["轻松", "休闲", "慢慢逛", "不赶", "慵懒", "佛系", "随性"],
    "紧凑": ["紧凑", "特种兵", "暴走", "多去几个", "效率", "赶时间"],
}

# 预算关键词映射
BUDGET_KEYWORDS = {
    "经济": ["便宜", "省钱", "经济", "性价比", "实惠", "平价"],
    "高端": ["高端", "品质", "贵一点", "精致", "豪华"],
}

# 城市识别正则
CITY_PATTERNS = [
    r"去(.+?)(?:玩|旅游|逛|吃|旅行|攻略|推荐)",
    r"(.+?)(?:旅游|旅行|游玩|攻略)",
    r"在(.+?)(?:玩|逛|吃)",
]

# 天数识别正则
DAY_PATTERNS = [
    (r"(\d+)\s*天", lambda m: int(m.group(1))),
    (r"(\d+)\s*日", lambda m: int(m.group(1))),
    (r"两\s*天", lambda m: 2),
    (r"三\s*天", lambda m: 3),
    (r"四\s*天", lambda m: 4),
    (r"五\s*天", lambda m: 5),
    (r"周末", lambda m: 2),
    (r"小长假", lambda m: 3),
]

# 住宿区域关键词
HOTEL_AREA_KEYWORDS = [
    "住在", "酒店在", "民宿在", "住宿在", "酒店位于", "民宿位于"
]


# ================= 快速路径：关键词匹配 =================

def extract_intent_by_keywords(message: str) -> UserIntent:
    """
    快速路径：通过关键词匹配提取用户意图
    速度极快，适用于大多数常见场景
    """
    text = message.strip()
    intent = UserIntent()
    
    # 1. 提取城市
    for pattern in CITY_PATTERNS:
        match = re.search(pattern, text)
        if match:
            city = match.group(1).strip()
            if len(city) >= 2 and len(city) <= 6:
                intent.city = city
                break
    
    # 2. 提取兴趣
    for interest, keywords in INTEREST_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            intent.interests.append(interest)
    
    # 3. 提取避开项
    for avoid_item, keywords in AVOID_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            intent.avoid.append(avoid_item)
    
    # 4. 提取节奏
    for pace, keywords in PACE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            intent.pace = pace
            break
    
    # 5. 提取预算
    for budget, keywords in BUDGET_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            intent.budget = budget
            break
    
    # 6. 提取天数
    for pattern, extractor in DAY_PATTERNS:
        match = re.search(pattern, text)
        if match:
            intent.day_count = extractor(match)
            break
    
    # 7. 提取住宿区域
    for keyword in HOTEL_AREA_KEYWORDS:
        if keyword in text:
            start = text.index(keyword) + len(keyword)
            area_text = text[start:start+10].split("，。、！？")[0].strip()
            if area_text:
                intent.hotel_area = area_text
                break
    
    # 8. 计算置信度
    score = 0
    if intent.city:
        score += 0.3
    if intent.interests:
        score += 0.3
    if intent.day_count > 1:
        score += 0.1
    if intent.pace != "适中":
        score += 0.1
    if intent.budget != "适中":
        score += 0.1
    if intent.hotel_area:
        score += 0.1
    
    intent.confidence = min(score, 1.0)
    
    return intent


def needs_llm_analysis(message: str, intent: UserIntent) -> bool:
    """
    判断是否需要LLM进一步分析
    """
    text = message.strip()
    
    # 1. 置信度太低
    if intent.confidence < 0.4:
        return True
    
    # 2. 没有识别到城市
    if not intent.city:
        return True
    
    # 3. 复杂句式（包含问号、多条件等）
    if "？" in text or "?" in text:
        return True
    
    # 4. 包含模糊表达
    vague_keywords = ["什么", "哪里", "哪些", "推荐", "攻略", "怎么", "如何", "最好"]
    if any(kw in text for kw in vague_keywords):
        return True
    
    # 5. 多个矛盾条件
    if "不要" in text and "想要" in text:
        return True
    
    return False


# ================= 慢速路径：LLM深度分析 =================

def analyze_intent_by_llm(message: str) -> Optional[UserIntent]:
    """
    慢速路径：使用LLM进行深度意图分析
    适用于复杂、模糊的用户输入
    """
    system_prompt = """你是一个用户意图分析专家。分析用户的旅游需求，提取结构化信息。

输出JSON格式：
{
  "city": "城市名",
  "interests": ["兴趣1", "兴趣2"],
  "avoid": ["想避开的1", "想避开的2"],
  "pace": "轻松/紧凑/适中",
  "budget": "经济/适中/高端",
  "day_count": 天数,
  "hotel_area": "住宿区域（如有）"
}

注意：
- 只提取明确的信息，不要猜测
- 如果用户没有说明某个字段，使用默认值
- interests 可选值：美食、购物、文化、自然、夜生活、拍照、咖啡、酒吧、亲子
- avoid 可选值：商场、人多、网红店、商业化
- pace 可选值：轻松、紧凑、适中
- budget 可选值：经济、适中、高端"""

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{openai_api_base}chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": TEXT_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"分析以下用户需求：{message}"}
                    ],
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            
            # 提取JSON
            import json
            json_match = re.search(r'\{[^{}]+\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return UserIntent(
                    city=result.get("city", ""),
                    interests=result.get("interests", []),
                    avoid=result.get("avoid", []),
                    pace=result.get("pace", "适中"),
                    budget=result.get("budget", "适中"),
                    day_count=result.get("day_count", 1),
                    hotel_area=result.get("hotel_area", ""),
                    confidence=0.9,
                    need_llm=False
                )
    except Exception as e:
        print(f"LLM分析失败: {e}")
    
    return None


# ================= 混合意图识别 =================

def recognize_intent(message: str) -> UserIntent:
    """
    混合意图识别：关键词匹配优先，LLM兜底
    
    流程：
    1. 先用关键词快速匹配
    2. 判断是否需要LLM分析
    3. 如果需要，调用LLM深度分析
    4. 合并结果，返回最终意图
    """
    # 快速路径
    intent = extract_intent_by_keywords(message)
    
    # 判断是否需要LLM
    if needs_llm_analysis(message, intent):
        print("[意图识别] 快速匹配置信度不足，启用LLM分析...")
        llm_intent = analyze_intent_by_llm(message)
        if llm_intent:
            # 合并结果：LLM结果优先，关键词匹配作为补充
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
            if llm_intent.hotel_area:
                intent.hotel_area = llm_intent.hotel_area
            intent.confidence = llm_intent.confidence
            intent.need_llm = False
    else:
        print(f"[意图识别] 快速匹配成功，置信度: {intent.confidence:.2f}")
        intent.need_llm = False
    
    return intent


# ================= 推荐查询 =================

def build_recommendation_prompt(intent: UserIntent) -> Dict[str, str]:
    """根据意图构建推荐提示词"""
    
    # 兴趣说明
    if intent.interests:
        interest_desc = f"用户特别感兴趣的领域：{', '.join(intent.interests)}\n请重点围绕这些领域推荐。"
    else:
        interest_desc = "请给出该城市最有代表性的本地体验推荐，涵盖美食、文化、休闲等不同方面。"
    
    # 避开说明
    avoid_desc = ""
    if intent.avoid:
        avoid_desc = f"用户想避开的：{', '.join(intent.avoid)}\n请不要推荐这些类型的地点。"
    
    # 节奏说明
    pace_map = {
        "轻松": "慢节奏，不赶时间，注重体验质量",
        "紧凑": "多去几个地方，效率优先",
        "适中": "平衡体验和效率"
    }
    
    # 预算说明
    budget_map = {
        "经济": "人均100以内，性价比优先",
        "适中": "人均100-300，品质和价格平衡",
        "高端": "人均300+，追求品质体验"
    }
    
    # 住宿说明
    hotel_desc = f"用户住在{intent.hotel_area}附近" if intent.hotel_area else ""
    
    system_prompt = """你是一个资深当地向导，熟悉本地人真正会去的地方。
你的推荐原则：
1. 优先推荐本地人常去的地方，而非游客陷阱
2. 给出具体推荐理由，说明为什么值得去
3. 根据用户兴趣和偏好动态调整推荐
4. 如果用户想避开某些类型，严格遵守
5. 考虑交通便利性，优先推荐顺路的地点组合

输出格式：
## 推荐地点
1. [地点名] - [一句话为什么值得去]
   类型：[美食/文化/休闲/购物等]
   适合：[什么情况下值得去]
   注意：[避坑建议，可选]

## 路线建议
（如果有多个地点，给出顺路的游览顺序）

## 如果有些地方名不副实
（列出不推荐的地方及原因）"""

    user_prompt = f"""目的地：{intent.city}
天数：{intent.day_count}天
节奏：{intent.pace}（{pace_map.get(intent.pace, pace_map['适中'])}）
预算：{intent.budget}（{budget_map.get(intent.budget, budget_map['适中'])}）
{hotel_desc}

{interest_desc}

{avoid_desc}

请给出6-8个推荐地点，每个地点说明：
1. 具体名称
2. 为什么值得去（一句话）
3. 类型（美食/文化/休闲/购物等）
4. 什么情况下适合去"""

    return {"system": system_prompt, "user": user_prompt}


def query_recommendations(intent: UserIntent, print_result: bool = True) -> Optional[str]:
    """查询推荐"""
    prompts = build_recommendation_prompt(intent)
    
    if print_result:
        print(f"\n正在查询 {intent.city} 的推荐攻略...")
        print(f"用户兴趣: {intent.interests if intent.interests else '通用推荐'}")
        print(f"想避开: {intent.avoid if intent.avoid else '无'}")
        print(f"节奏: {intent.pace}, 预算: {intent.budget}, 天数: {intent.day_count}天\n")
    
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{openai_api_base}chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": TEXT_MODEL,
                    "messages": [
                        {"role": "system", "content": prompts["system"]},
                        {"role": "user", "content": prompts["user"]}
                    ],
                    "temperature": 0.6,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            result = data["choices"][0]["message"]["content"]
            
            if print_result:
                print("=" * 60)
                print(f"  {intent.city} 推荐攻略")
                print("=" * 60)
                print(result)
                print("=" * 60)
            
            return result
            
    except Exception as e:
        if print_result:
            print(f"发生错误: {e}")
        return None


# ================= 主入口 =================

def get_recommendations(message: str, print_result: bool = True) -> Optional[str]:
    """
    主入口：根据用户消息获取推荐
    
    Args:
        message: 用户输入的消息
        print_result: 是否打印结果
    
    Returns:
        推荐文本，失败返回None
    """
    # 1. 意图识别（混合模式）
    intent = recognize_intent(message)
    
    if not intent.city:
        if print_result:
            print("无法识别目的地城市，请 specify 城市名称")
        return None
    
    # 2. 查询推荐
    return query_recommendations(intent, print_result)


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
        "想去成都，预算有限",
        "带孩子去成都玩",
        "成都夜生活哪里好玩",
    ]
    
    for msg in test_cases:
        print(f"\n{'='*60}")
        print(f"用户输入: {msg}")
        print(f"{'='*60}")
        
        # 意图识别
        intent = recognize_intent(msg)
        print(f"\n识别结果:")
        print(f"  城市: {intent.city}")
        print(f"  兴趣: {intent.interests}")
        print(f"  避开: {intent.avoid}")
        print(f"  节奏: {intent.pace}")
        print(f"  预算: {intent.budget}")
        print(f"  天数: {intent.day_count}")
        print(f"  置信度: {intent.confidence:.2f}")
        print(f"  需要LLM: {intent.need_llm}")
        
        # 只测试意图识别，不实际调用LLM（节省时间）
        # 如果想测试推荐，取消下面的注释
        # get_recommendations(msg)
