import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fastapi"))

from social_discovery import discover_places_from_social

async def main():
    city = "成都"
    interests = ["美食"]
    
    print(f"正在搜索 {city} 的 {interests[0]} 推荐...\n")
    
    result = await discover_places_from_social(
        city=city,
        interests=interests,
        max_places=20
    )
    
    if result["status"] == "failed":
        print(f"搜索失败: {result.get('reason', 'unknown')}")
        return
    
    print(f"状态: {result['status']}")
    print(f"搜索查询: {len(result['queries_used'])} 个")
    print(f"原始结果: {result['total_raw_results']} 条")
    print(f"提取地点: {len(result['places'])} 个\n")
    
    print("=" * 50)
    print(f"{city} 美食地点推荐")
    print("=" * 50)
    
    for i, place in enumerate(result["places"], 1):
        print(f"\n{i}. {place['name']}")
        if place.get('source_title'):
            print(f"   来源: {place['source_title'][:50]}")
        if place.get('source_snippet'):
            print(f"   介绍: {place['source_snippet'][:80]}...")

if __name__ == "__main__":
    asyncio.run(main())
