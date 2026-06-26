"""
POI验证与缓存模块
验证LLM推荐的地点是否真实存在，并提供缓存加速
"""
import os
import json
import time
import hashlib
import httpx
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

# ================= 配置 =================
AMAP_WEB_SERVICE_KEY = os.getenv("AMAP_WEB_SERVICE_KEY", os.getenv("AMAP_WEB_SERVICEKEY", ""))
CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_EXPIRE_HOURS = 24 * 7  # 缓存7天
# ==========================================


def _get_cache_key(query: str, city: str) -> str:
    """生成缓存key"""
    raw = f"{city}:{query}"
    return hashlib.md5(raw.encode()).hexdigest()


def _load_cache(key: str) -> Optional[Dict]:
    """加载缓存"""
    cache_file = CACHE_DIR / f"{key}.json"
    if not cache_file.exists():
        return None
    
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        # 检查是否过期
        if time.time() - data.get("timestamp", 0) > CACHE_EXPIRE_HOURS * 3600:
            return None
        return data.get("result")
    except Exception:
        return None


def _save_cache(key: str, result: Dict):
    """保存缓存"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{key}.json"
    
    data = {
        "timestamp": time.time(),
        "result": result
    }
    cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


async def search_poi_by_name(name: str, city: str, keywords: str = "") -> List[Dict[str, Any]]:
    """
    通过高德API搜索POI
    
    Args:
        name: POI名称
        city: 城市名
        keywords: 额外关键词（如"美食"、"餐厅"）
    
    Returns:
        POI列表，包含name, address, location, type等
    """
    if not AMAP_WEB_SERVICE_KEY:
        print("[POI验证] 未配置AMAP_WEB_SERVICE_KEY")
        return []
    
    # 检查缓存
    cache_key = _get_cache_key(name, city)
    cached = _load_cache(cache_key)
    if cached is not None:
        print(f"[POI验证] 缓存命中: {name}")
        return cached
    
    # 调用高德API
    search_text = f"{name} {keywords}".strip()
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://restapi.amap.com/v3/place/text",
                params={
                    "key": AMAP_WEB_SERVICE_KEY,
                    "keywords": search_text,
                    "city": city,
                    "output": "json",
                    "offset": 5,
                }
            )
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("status") != "1":
                print(f"[POI验证] API错误: {data.get('info')}")
                return []
            
            pois = data.get("pois") or []
            results = []
            
            for poi in pois[:5]:
                results.append({
                    "name": poi.get("name", ""),
                    "address": poi.get("address", ""),
                    "location": poi.get("location", ""),
                    "type": poi.get("type", ""),
                    "typecode": poi.get("typecode", ""),
                    "city": poi.get("cityname", ""),
                    "district": poi.get("adname", ""),
                    "tel": poi.get("tel", ""),
                    "distance": poi.get("distance", ""),
                })
            
            # 保存缓存
            if results:
                _save_cache(cache_key, results)
            
            return results
            
    except Exception as e:
        print(f"[POI验证] 请求失败: {e}")
        return []


def verify_place_exists(place_name: str, city: str, place_type: str = "") -> Dict[str, Any]:
    """
    验证地点是否真实存在
    
    Returns:
        {
            "exists": True/False,
            "confidence": 0.0-1.0,
            "matched_name": "匹配到的名称",
            "address": "地址",
            "type": "类型",
            "suggestions": ["其他可能的匹配"]
        }
    """
    import asyncio
    
    # 同步调用异步函数
    loop = asyncio.new_event_loop()
    try:
        pois = loop.run_until_complete(
            search_poi_by_name(place_name, city, place_type)
        )
    finally:
        loop.close()
    
    if not pois:
        return {
            "exists": False,
            "confidence": 0.0,
            "matched_name": "",
            "address": "",
            "type": "",
            "suggestions": []
        }
    
    # 精确匹配
    for poi in pois:
        if poi["name"] == place_name:
            return {
                "exists": True,
                "confidence": 1.0,
                "matched_name": poi["name"],
                "address": poi["address"],
                "type": poi["type"],
                "suggestions": []
            }
    
    # 模糊匹配
    for poi in pois:
        if place_name in poi["name"] or poi["name"] in place_name:
            return {
                "exists": True,
                "confidence": 0.8,
                "matched_name": poi["name"],
                "address": poi["address"],
                "type": poi["type"],
                "suggestions": [p["name"] for p in pois if p["name"] != poi["name"]][:2]
            }
    
    # 部分匹配
    for poi in pois:
        # 检查是否有共同字符
        common_chars = set(place_name) & set(poi["name"])
        if len(common_chars) >= 2:
            return {
                "exists": True,
                "confidence": 0.5,
                "matched_name": poi["name"],
                "address": poi["address"],
                "type": poi["type"],
                "suggestions": [p["name"] for p in pois if p["name"] != poi["name"]][:2]
            }
    
    return {
        "exists": False,
        "confidence": 0.0,
        "matched_name": "",
        "address": "",
        "type": "",
        "suggestions": [p["name"] for p in pois[:3]]
    }


def verify_recommendations(recommendations: List[Dict[str, Any]], city: str) -> List[Dict[str, Any]]:
    """
    批量验证推荐地点
    
    Args:
        recommendations: [{"name": "店名", "type": "美食", ...}, ...]
        city: 城市名
    
    Returns:
        验证后的推荐列表，每个地点添加verified字段
    """
    verified = []
    
    for rec in recommendations:
        name = rec.get("name", "")
        place_type = rec.get("type", "")
        
        result = verify_place_exists(name, city, place_type)
        
        verified_rec = dict(rec)
        verified_rec["verification"] = {
            "verified": result["exists"],
            "confidence": result["confidence"],
            "matched_name": result["matched_name"],
            "address": result["address"],
            "suggestions": result["suggestions"],
        }
        
        verified.append(verified_rec)
    
    return verified


def parse_recommendations_from_text(text: str) -> List[Dict[str, Any]]:
    """
    从LLM输出文本中解析推荐地点
    
    支持格式：
    1. **店名** - 描述
    1. **店名** - 描述
    """
    import re
    
    places = []
    
    # 匹配格式：数字. **店名** - 描述
    pattern = r'\d+\.\s*\*\*(.+?)\*\*\s*[-—]\s*(.+?)(?:\n|$)'
    matches = re.findall(pattern, text)
    
    for name, desc in matches:
        # 提取类型
        type_match = re.search(r'类型[：:]\s*(.+?)(?:\n|$)', desc)
        place_type = type_match.group(1).strip() if type_match else ""
        
        places.append({
            "name": name.strip(),
            "description": desc.strip()[:100],
            "type": place_type,
        })
    
    # 如果没匹配到，尝试简单格式
    if not places:
        pattern2 = r'\d+\.\s*(.+?)(?:\s*[-—]\s*|\n)'
        matches2 = re.findall(pattern2, text)
        
        for name in matches2:
            name = name.strip().strip('*')
            if len(name) >= 2 and len(name) <= 20:
                places.append({
                    "name": name,
                    "description": "",
                    "type": "",
                })
    
    return places


# ================= 测试 =================
if __name__ == '__main__':
    # 测试POI验证
    test_cases = [
        ("建设路美食街", "成都"),
        ("宽窄巷子", "成都"),
        ("春熙路", "成都"),
        ("天府广场", "成都"),
        ("不存在的店", "成都"),
    ]
    
    print("测试POI验证:\n")
    
    for name, city in test_cases:
        print(f"验证: {name} ({city})")
        result = verify_place_exists(name, city)
        print(f"  存在: {result['exists']}")
        print(f"  置信度: {result['confidence']:.2f}")
        if result['matched_name']:
            print(f"  匹配: {result['matched_name']}")
            print(f"  地址: {result['address']}")
        if result['suggestions']:
            print(f"  建议: {result['suggestions']}")
        print()
