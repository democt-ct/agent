import sys
sys.path.insert(0, 'fastapi')

from services.enhanced_intent import recognize_intent_enhanced, to_requirement_payload

test_cases = [
    "我想去成都吃美食，不想逛商场",
    "成都3天怎么玩",
    "去成都旅游，想吃好吃的",
    "成都有什么好玩的",
]

for msg in test_cases:
    print(f"\n输入: {msg}")
    intent = recognize_intent_enhanced(msg)
    print(f"城市: {intent.city}")
    print(f"兴趣: {intent.interests}")
    print(f"避开: {intent.avoid}")
    print(f"节奏: {intent.pace}")
    print(f"预算: {intent.budget}")
    print(f"天数: {intent.day_count}")
    print(f"置信度: {intent.confidence:.2f}")
    print(f"来源: {intent.source}")
    
    payload = to_requirement_payload(intent)
    print(f"Payload格式:")
    print(f"  city: {payload['city']}")
    print(f"  theme: {payload['theme']}")
    print(f"  must_have: {payload['must_have']}")
    print(f"  avoid: {payload['avoid']}")
    print(f"  trip_style: {payload['trip_style']}")
    print(f"  day_count: {payload['day_count']}")
