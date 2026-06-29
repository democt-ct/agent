import sys
import os
from pathlib import Path

# 加载.env文件
env_path = Path("fastapi/.env")
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()

sys.path.insert(0, 'fastapi')

from services.poi_verifier import verify_place_exists, verify_recommendations, parse_recommendations_from_text

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

# 测试解析推荐文本
print("\n测试解析推荐文本:\n")

sample_text = """
## 推荐地点
1. **建设路美食街** - 成都最热闹的美食聚集地，周边布满了各种小吃摊和苍蝇馆子。
   类型：美食/休闲
   适合：想感受成都日常、寻找街头美食时前往

2. **宽窄巷子** - 老成都的缩影，保留了清朝建筑风格。
   类型：文化
   适合：想了解成都历史、体验传统建筑时前往

3. **春熙路** - 成都最繁华的商业街。
   类型：购物
   适合：想逛街购物时前往
"""

places = parse_recommendations_from_text(sample_text)
print(f"解析到 {len(places)} 个地点:")
for p in places:
    print(f"  - {p['name']} ({p['type']})")

# 测试批量验证
print("\n测试批量验证:\n")
verified = verify_recommendations(places, "成都")
for v in verified:
    status = "[OK]" if v["verification"]["verified"] else "[MISS]"
    matched = v["verification"]["matched_name"] or "未找到"
    print(f"  {status} {v['name']} -> {matched}")
