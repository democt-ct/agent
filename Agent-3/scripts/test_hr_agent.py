"""快速验证 HR Agent 完整链路。

运行：python scripts/test_hr_agent.py
"""

import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.agents.base_agent import BaseAgent
from src.agents.orchestrator import Orchestrator
from src.protocol.types import AgentRequest
from src.rag.embedder import Embedder
from src.rag.knowledge_base import KnowledgeBase
from src.tools.hr_tools import HR_TOOLS

load_dotenv()
from src.llm_client import get_client, get_model
client = get_client()

# ── 初始化 ───────────────────────────────────────────────────────
print("=" * 60)
print("  [Test] HR Agent complete pipeline")
print("=" * 60)
print()

print("[1] 初始化...")
embedder = Embedder()
kb = KnowledgeBase("hr_kb", "data/hr/", embedder=embedder)
if os.path.exists(kb._metadata_path()):
    kb.load_index()
    print("    KB: 已加载")
else:
    kb.build_index()
    print("    KB: 构建完成")

agent = BaseAgent(
    name="HR 专家",
    tools=HR_TOOLS,
    kb=kb,
    client=client,
    model=get_model(),
)
orchestrator = Orchestrator(client)
print("    Agent: HR 专家 ready")
print()

# ── 测试用例 ─────────────────────────────────────────────────────
tests = [
    "我今年还剩几天年假？工龄3年",
    "帮我查一下员工 EMP002 的假期余额",
    "年假怎么申请",
]

for query in tests:
    print(f"[问] {query}")

    route = orchestrator.route(query)
    print(f"      路由 → {route['primary']} ({route['method']}:{route['confidence']:.0%})")

    t0 = time.time()
    response = agent.run(AgentRequest(
        query=query,
        agent_name="hr_agent",
        max_tool_calls=3,
        temperature=0.3,
    ))
    elapsed = time.time() - t0

    print(f"      回答: {response.answer}")
    print(f"      ⏱ {elapsed:.1f}s · 🔍 {len(response.retrieved_chunks)} chunks · 🪛 {len(response.tool_calls)} tools · 🪙 {response.tokens_used} tokens")
    print()

print("✅ 测试完成")
