import os
import httpx
from typing import Optional, List, Dict, Any

# ================= 配置区 =================
openai_api_key = os.getenv("LLM_API_KEY", "ms-4ecca729-328f-4e74-9d9b-39fa76e5b56b")
openai_api_base = "https://api-inference.modelscope.cn/v1/"
TEXT_MODEL = "deepseek-ai/DeepSeek-V3.2"
# ==========================================

# 兴趣类型定义
INTEREST_TYPES = [
    "美食", "购物", "文化", "自然", "夜生活", "拍照", "咖啡", "酒吧", "亲子"
]

# 节奏类型
PACE_TYPES = {
    "轻松": "慢节奏，不赶时间，注重体验质量",
    "紧凑": "多去几个地方，效率优先",
    "适中": "平衡体验和效率"
}

# 预算类型
BUDGET_TYPES = {
    "经济": "人均100以内，性价比优先",
    "适中": "人均100-300，品质和价格平衡",
    "高端": "人均300+，追求品质体验"
}


def build_recommendation_prompt(
    city: str,
    interests: Optional[List[str]] = None,
    avoid: Optional[List[str]] = None,
    pace: str = "适中",
    budget: str = "适中",
    day_count: int = 1,
    hotel_area: str = "",
) -> Dict[str, str]:
    """
    构建推荐提示词，返回 system_prompt 和 user_prompt
    """
    interests = interests or []
    avoid = avoid or []
    
    # 动态生成兴趣说明
    if interests:
        interest_desc = f"用户特别感兴趣的领域：{', '.join(interests)}\n请重点围绕这些领域推荐。"
    else:
        interest_desc = "请给出该城市最有代表性的本地体验推荐，涵盖美食、文化、休闲等不同方面。"
    
    # 动态生成避坑说明
    avoid_desc = ""
    if avoid:
        avoid_desc = f"用户想避开的：{', '.join(avoid)}\n请不要推荐这些类型的地点。"
    
    # 节奏说明
    pace_desc = PACE_TYPES.get(pace, PACE_TYPES["适中"])
    
    # 预算说明
    budget_desc = BUDGET_TYPES.get(budget, BUDGET_TYPES["适中"])
    
    # 住宿区域说明
    hotel_desc = f"用户住在{hotel_area}附近" if hotel_area else ""
    
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

## 如果有些地方名不副实
（列出不推荐的地方及原因）"""

    user_prompt = f"""目的地：{city}
天数：{day_count}天
节奏：{pace}（{pace_desc}）
预算：{budget}（{budget_desc}）
{hotel_desc}

{interest_desc}

{avoid_desc}

请给出6-8个推荐地点，每个地点说明：
1. 具体名称
2. 为什么值得去（一句话）
3. 类型（美食/文化/休闲/购物等）
4. 什么情况下适合去"""

    return {"system": system_prompt, "user": user_prompt}


def query_recommendations(
    city: str,
    interests: Optional[List[str]] = None,
    avoid: Optional[List[str]] = None,
    pace: str = "适中",
    budget: str = "适中",
    day_count: int = 1,
    hotel_area: str = "",
    print_result: bool = True,
) -> Optional[str]:
    """
    查询推荐，返回推荐文本
    
    Args:
        city: 目的地城市
        interests: 用户兴趣列表
        avoid: 用户想避开的
        pace: 节奏（轻松/紧凑/适中）
        budget: 预算（经济/适中/高端）
        day_count: 天数
        hotel_area: 住宿区域
        print_result: 是否打印结果
    
    Returns:
        推荐文本，失败返回None
    """
    prompts = build_recommendation_prompt(
        city, interests, avoid, pace, budget, day_count, hotel_area
    )
    
    if print_result:
        print(f"正在查询 {city} 的推荐攻略...")
        print(f"用户兴趣: {interests if interests else '通用推荐'}")
        print(f"想避开: {avoid if avoid else '无'}")
        print(f"节奏: {pace}, 预算: {budget}, 天数: {day_count}天\n")
    
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
                print(f"  {city} 推荐攻略")
                print("=" * 60)
                print(result)
                print("=" * 60)
            
            return result
            
    except Exception as e:
        if print_result:
            print(f"发生错误: {e}")
        return None


# ================= 与现有项目架构集成 =================

def interpret_user_message(message: str) -> Dict[str, Any]:
    """
    从用户消息中提取偏好，与 core.py 的 interpret_requirement_payload 对接
    """
    import re
    
    text = message.strip()
    
    # 提取兴趣
    interests = []
    interest_keywords = {
        "美食": ["美食", "好吃", "小吃", "吃", "火锅", "烧烤", "川菜"],
        "购物": ["购物", "逛街", "商场", "买"],
        "文化": ["文化", "历史", "博物馆", "古迹", "古镇"],
        "自然": ["自然", "公园", "爬山", "徒步", "露营"],
        "夜生活": ["夜生活", "酒吧", "夜市", "夜景"],
        "拍照": ["拍照", "出片", "摄影", "打卡"],
        "咖啡": ["咖啡", "cafe"],
        "酒吧": ["酒吧", "清吧"],
        "亲子": ["亲子", "带娃", "小朋友", "孩子"],
    }
    
    for interest, keywords in interest_keywords.items():
        if any(kw in text for kw in keywords):
            interests.append(interest)
    
    # 提取想避开的
    avoid = []
    avoid_keywords = {
        "商场": ["不要商场", "不想逛商场", "避开商场"],
        "人多": ["人少", "不挤", "避开人群", "人太多"],
        "网红店": ["不要网红", "不想去网红", "避开网红"],
        "商业化": ["太商业化", "商业化"],
    }
    
    for avoid_item, keywords in avoid_keywords.items():
        if any(kw in text for kw in keywords):
            avoid.append(avoid_item)
    
    # 提取节奏
    pace = "适中"
    if any(kw in text for kw in ["轻松", "休闲", "慢慢逛", "不赶"]):
        pace = "轻松"
    elif any(kw in text for kw in ["紧凑", "特种兵", "暴走", "多去几个"]):
        pace = "紧凑"
    
    # 提取预算
    budget = "适中"
    if any(kw in text for kw in ["便宜", "省钱", "经济", "性价比"]):
        budget = "经济"
    elif any(kw in text for kw in ["高端", "品质", "贵一点"]):
        budget = "高端"
    
    # 提取天数
    day_count = 1
    day_match = re.search(r"(\d+)\s*天", text)
    if day_match:
        day_count = int(day_match.group(1))
    elif "两" in text:
        day_count = 2
    elif "三" in text:
        day_count = 3
    
    # 提取城市
    city_match = re.search(r"去(.+?)(?:玩|旅游|逛|吃|旅行|$)", text)
    city = city_match.group(1) if city_match else ""
    
    return {
        "city": city,
        "interests": interests,
        "avoid": avoid,
        "pace": pace,
        "budget": budget,
        "day_count": day_count,
    }


if __name__ == '__main__':
    # 测试不同场景
    test_cases = [
        {
            "desc": "场景1：想吃美食，不想逛商场",
            "city": "成都",
            "interests": ["美食"],
            "avoid": ["商场"],
        },
        {
            "desc": "场景2：想逛街购物",
            "city": "成都",
            "interests": ["购物", "拍照"],
        },
        {
            "desc": "场景3：周末轻松游",
            "city": "成都",
            "interests": ["美食", "文化"],
            "pace": "轻松",
            "budget": "经济",
        },
        {
            "desc": "场景4：3天深度游",
            "city": "成都",
            "day_count": 3,
            "pace": "紧凑",
        },
    ]
    
    for case in test_cases:
        print(f"\n{'='*60}")
        print(f"  {case['desc']}")
        print(f"{'='*60}\n")
        
        query_recommendations(
            city=case["city"],
            interests=case.get("interests"),
            avoid=case.get("avoid"),
            pace=case.get("pace", "适中"),
            budget=case.get("budget", "适中"),
            day_count=case.get("day_count", 1),
        )
        print("\n")
