"""测试 base_agent.py — 使用 DeepSeek API 真实对话

前置条件：项目根目录的 .env 文件中配置 DEEPSEEK_API_KEY
运行：python scripts/test_base_agent.py
"""

import os
import sys
from unittest.mock import MagicMock

from dotenv import load_dotenv
from openai import OpenAI

# 确保项目根在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.protocol.types import AgentRequest
from src.tools.base import ToolDef
from src.agents.base_agent import BaseAgent

# ─── 1. 加载 API Key ───────────────────────────────────────────
load_dotenv()
from src.llm_client import get_client, get_model
client = get_client()

# ─── 2. 准备 mock 知识库（Person B 完成后替换为真实 KnowledgeBase） ──
mock_kb = MagicMock()
mock_kb.query.return_value = [
    {
        "content": "员工年假根据工龄计算：1-5年工龄每年5天，5-10年工龄每年10天，10年以上每年15天。年假可累计但最多结转5天至下一年度。",
        "source": "年假管理制度.md",
        "score": 0.95,
    },
    {
        "content": "年假需提前至少3个工作日通过HR系统提交申请，直属上级审批。加急可走线下纸质流程。",
        "source": "请假审批流程.md",
        "score": 0.88,
    },
]

# ─── 3. 准备 mock 工具 ──────────────────────────────────────────
def mock_get_leave_balance(user_id: str) -> dict:
    """Mock：查询假期余额"""
    store = {
        "EMP001": {"annual": 7, "sick": 5},
        "EMP002": {"annual": 12, "sick": 3},
    }
    return store.get(user_id, {"annual": 5, "sick": 5})

hr_tools = [
    ToolDef(
        name="get_leave_balance",
        description="查询员工的年假和病假剩余天数。输入员工ID（如 EMP001），返回各类假期剩余天数。",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "员工ID，如 EMP001",
                }
            },
            "required": ["user_id"],
        },
        implementation=mock_get_leave_balance,
    ),
]

# ─── 4. 创建 Agent ──────────────────────────────────────────────
agent = BaseAgent(
    name="HR 专家",
    tools=hr_tools,
    kb=mock_kb,
    client=client,
    model=get_model(),
)

# ─── 5. 跑测试 ──────────────────────────────────────────────────
print("=" * 60)
print("  🧪 BaseAgent ReAct 循环测试 — DeepSeek")
print("=" * 60)
print()

test_cases = [
    {
        "label": "场景1: 纯知识问答（不需要工具）",
        "query": "我今年还剩几天年假？工龄3年",
        "user_id": "EMP001",
    },
    {
        "label": "场景2: 需要调用工具查询",
        "query": "帮我查一下员工 EMP002 的假期余额",
        "user_id": "EMP002",
    },
]

for i, tc in enumerate(test_cases):
    print(f"── {tc['label']} ──")
    print(f"   用户: {tc['query']}")
    print()

    request = AgentRequest(
        query=tc["query"],
        agent_name="hr_agent",
        max_tool_calls=3,
        temperature=0.3,
    )

    response = agent.run(request)

    print(f"   状态:   {response.status}  |  置信度: {response.confidence:.0%}")
    print(f"   耗时:   {response.processing_time_ms}ms  |  总token: {response.tokens_used}")
    print(f"   检索到: {len(response.retrieved_chunks)} 段")
    print(f"   工具调用: {len(response.tool_calls)} 次")
    for tc_log in response.tool_calls:
        print(f"     ⚙ {tc_log['name']}({tc_log.get('arguments', {})}) → {tc_log.get('result', {})}")
    print()
    print(f"   回答:")
    print(f"   {response.answer}")
    print()

print("✅ 测试完成")
