"""验证三个 Agent 完整链路。

运行：python scripts/test_all_agents.py
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time

from dotenv import load_dotenv
from openai import OpenAI

from src.agents.base_agent import BaseAgent
from src.agents.orchestrator import Orchestrator
from src.protocol.types import AgentRequest
from src.rag.embedder import Embedder
from src.rag.knowledge_base import KnowledgeBase
from src.tools.hr_tools import HR_TOOLS
from src.tools.it_tools import IT_TOOLS
from src.tools.legal_tools import LEGAL_TOOLS

load_dotenv()
from src.llm_client import get_client
client = get_client()

print("=" * 60)
print("  [Test] All 3 Agents Integration")
print("=" * 60)
print()

# ── 初始化 ───────────────────────────────────────────────────────
print("[Init] Loading...")
embedder = Embedder()

kbs = {}
for name, docs_dir in [("hr_kb", "data/hr/"), ("it_kb", "data/it/"), ("legal_kb", "data/legal/")]:
    kb = KnowledgeBase(name, docs_dir, embedder=embedder)
    if os.path.exists(kb._metadata_path()):
        kb.load_index()
    else:
        kb.build_index()
    kbs[name] = kb

agents = {
    "hr_agent": BaseAgent("HR 专家", HR_TOOLS, kbs["hr_kb"], client),
    "it_agent": BaseAgent("IT 专家", IT_TOOLS, kbs["it_kb"], client),
    "legal_agent": BaseAgent("法务专家", LEGAL_TOOLS, kbs["legal_kb"], client),
}
orchestrator = Orchestrator(client)
print(f"[Init] 3 agents + 3 KBs ready")
print()

# ── 测试 ─────────────────────────────────────────────────────────
tests = [
    # HR
    ("病假工资怎么算", "hr_agent"),
    ("帮我查 EMP001 的假期余额", "hr_agent"),
    # IT
    ("笔记本坏了怎么办", "it_agent"),
    ("帮我查 TK001 工单状态", "it_agent"),
    # Legal
    ("保密协议有什么条款", "legal_agent"),
    ("帮我检查跨境数据传输合规性", "legal_agent"),
]

total_tokens = 0
passed = 0

for query, expected_agent in tests:
    print(f"[Q] {query}")

    route = orchestrator.route(query)
    agent_name = route["primary"]
    correct = agent_name == expected_agent
    status = "OK" if correct else f"WRONG (expected {expected_agent})"
    print(f"    Route -> {agent_name} ({route['method']}) [{status}]")
    if correct:
        passed += 1

    agent = agents[agent_name]
    t0 = time.time()
    response = agent.run(AgentRequest(
        query=query, agent_name=agent_name,
        max_tool_calls=3, temperature=0.3,
    ))
    elapsed = time.time() - t0
    total_tokens += response.tokens_used

    answer_preview = response.answer[:100].replace("\n", " ")
    print(f"    Answer: {answer_preview}...")
    print(f"    {elapsed:.1f}s | {len(response.tool_calls)} tools | {response.tokens_used} tokens")
    print()

print("=" * 60)
print(f"  Routing: {passed}/{len(tests)}")
print(f"  Tokens: {total_tokens}")
print("=" * 60)
print("Done.")
