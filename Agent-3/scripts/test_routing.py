"""Orchestrator 路由准确率测试

运行：python scripts/test_routing.py
"""

import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.orchestrator import Orchestrator

# ─── 配置 ───────────────────────────────────────────────────────
load_dotenv()
from src.llm_client import get_client, get_model
client = get_client()
orchestrator = Orchestrator(client, model=get_model())

# ─── 测试用例 ───────────────────────────────────────────────────
# (query, expected_primary, expected_secondary | None, 说明)
TEST_CASES = [
    # ── HR 单域 ──
    ("我今年还剩几天年假？", "hr_agent", None, "HR: 年假查询"),
    ("请3天病假怎么申请？", "hr_agent", None, "HR: 请假流程"),
    ("公司社保公积金缴纳比例是多少？", "hr_agent", None, "HR: 社保政策"),
    ("新员工入职需要准备什么材料？", "hr_agent", None, "HR: 入职流程"),
    ("年终奖什么时候发？", "hr_agent", None, "HR: 薪酬福利"),
    ("迟到三次会怎么处理？", "hr_agent", None, "HR: 考勤制度"),

    # ── IT 单域 ──
    ("笔记本蓝屏了怎么报修？", "it_agent", None, "IT: 设备报修"),
    ("公司 VPN 怎么配置？", "it_agent", None, "IT: VPN 配置"),
    ("我电脑开机特别卡怎么办？", "it_agent", None, "IT: 电脑故障"),
    ("怎么申请一个新的显示器？", "it_agent", None, "IT: 设备申领"),
    ("邮箱密码忘了怎么重置？", "it_agent", None, "IT: 密码重置"),
    ("打印机连不上怎么解决？", "it_agent", None, "IT: 打印机故障"),

    # ── 法务单域 ──
    ("竞业限制协议的条款怎么解读？", "legal_agent", None, "法务: 竞业限制"),
    ("个人信息保护法对公司有什么要求？", "legal_agent", None, "法务: 数据保护"),
    ("签合同时要注意哪些合规问题？", "legal_agent", None, "法务: 合同合规"),
    ("员工数据能存到境外服务器吗？", "legal_agent", None, "法务: 数据跨境"),

    # ── 跨域 ──
    ("我请病假顺便笔记本报修", "hr_agent", "it_agent", "跨域: HR+IT"),
    ("合同审批没过，影响我的年终奖吗？", "legal_agent", "hr_agent", "跨域: 法务+HR"),
    ("IT 设备采购合同需要法务审核吗？", "legal_agent", "it_agent", "跨域: 法务+IT"),

    # ── 兜底/边界 ──
    ("你好", "fallback", None, "兜底: 寒暄"),
    ("谢谢你的帮助", "fallback", None, "兜底: 感谢"),
    ("今天晚饭吃什么？", "fallback", None, "兜底: 无关问题"),
    ("你是谁？", "fallback", None, "兜底: 自我介绍"),
    ("帮我查一下", "fallback", None, "边界: 模糊查询"),
]

# ─── 跑测试 ─────────────────────────────────────────────────────
print("=" * 70)
print("  🧪 Orchestrator 路由准确率测试")
print("=" * 70)
print()

passed = 0
failed = 0
total_time = 0.0
details: list[str] = []

for i, (query, expected_primary, expected_secondary, note) in enumerate(TEST_CASES):
    t0 = time.time()
    result = orchestrator.route(query)
    elapsed = time.time() - t0
    total_time += elapsed

    primary_ok = result["primary"] == expected_primary
    secondary_ok = (
        result["secondary"] == expected_secondary
        if expected_secondary
        else result["secondary"] is None
    )

    if primary_ok and secondary_ok:
        passed += 1
        icon = "✅"
    else:
        failed += 1
        icon = "❌"

    method = result["method"]
    conf = result["confidence"]
    detail = (
        f"{icon} #{i+1:02d} [{method:7s} conf={conf:.0%}] "
        f"{note}\n"
        f"     Q: {query}\n"
        f"     → {result['primary']}"
    )
    if result["secondary"]:
        detail += f" → {result['secondary']}"
    if not primary_ok:
        detail += f"  (期望: {expected_primary}"
        if expected_secondary:
            detail += f" → {expected_secondary}"
        detail += ")"
    details.append(detail)

# ─── 输出报告 ───────────────────────────────────────────────────
for d in details:
    print(d)
    print()

accuracy = passed / len(TEST_CASES) * 100
keyword_hits = sum(1 for d in details if "[keyword" in d)
llm_hits = sum(1 for d in details if "[llm   " in d)
greeting_hits = sum(1 for d in details if "[greetin" in d)

print("=" * 70)
print(f"  准确率:  {passed}/{len(TEST_CASES)} = {accuracy:.1f}%")
print(f"  耗时:    {total_time:.1f}s (平均 {total_time/len(TEST_CASES):.1f}s/条)")
print(f"  关键词命中: {keyword_hits} 条  |  LLM 路由: {llm_hits} 条  |  寒暄: {greeting_hits} 条")
print("=" * 70)

if accuracy >= 90:
    print(f"  ✅ 达标！路由准确率 {accuracy:.1f}% ≥ 90%")
elif accuracy >= 80:
    print(f"  ⚠️  接近达标 {accuracy:.1f}%，需要进一步调优")
else:
    print(f"  ❌ 未达标 {accuracy:.1f}%，需要重点排查失败用例")

sys.exit(0 if accuracy >= 80 else 1)
