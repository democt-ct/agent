"""Planner -- LLM-based task DAG decomposition.

Upgraded v2: 支持 DAG 依赖解析 + 拓扑排序.
单意图查询走关键词 fast-path(不调 LLM),跨域查询走 LLM DAG 拆解.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Data models ──────────────────────────────────────────────────

class SubTask(BaseModel):
    """A single decomposed sub-task node in the DAG."""

    id: str = Field(default="", description="Unique task id, e.g. t1")
    query: str = Field(..., description="The sub-query to route to an agent")
    domain: str = Field(default="unknown", description="hr | it | legal | finance | unknown")
    agent: str = Field(default="unknown", description="Which agent handles this: retrieval | tool | memory | review | unknown")
    depends_on: list[str] = Field(default_factory=list, description="IDs of tasks that must complete before this one")


class Plan(BaseModel):
    """DAG decomposition result."""

    original_query: str
    is_complex: bool = False
    subtasks: list[SubTask] = Field(default_factory=list)
    dependencies: dict[str, str] = Field(default_factory=dict)
    # dependencies: {"t1→t3": "需要 t1 的制度结果才能判断 t3 的审批级别"}
    raw_llm_response: str | None = None

    def topological_order(self) -> list[SubTask]:
        """Kahn's algorithm -- return subtasks in valid execution order."""
        if not self.is_complex or len(self.subtasks) <= 1:
            return list(self.subtasks)

        in_degree: dict[str, int] = {t.id: len(t.depends_on) for t in self.subtasks}
        adj: dict[str, list[str]] = {t.id: [] for t in self.subtasks}
        for t in self.subtasks:
            for dep in t.depends_on:
                if dep in adj:
                    adj[dep].append(t.id)

        queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
        order: list[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Map back to SubTask objects
        id_map = {t.id: t for t in self.subtasks}
        return [id_map[tid] for tid in order if tid in id_map]


# ── Planner prompt (v2 DAG) ──────────────────────────────────────

PLANNER_SYSTEM_PROMPT = """你是一个任务 DAG 规划专家.分析用户问题,拆解为有依赖关系的子任务.

## 规则
1. 单领域简单问题 → is_complex: false, subtasks 只有一条
2. 跨领域或多步骤问题 → is_complex: true, 拆为多条
3. 每个 subtask 必须有唯一 id(如 t1, t2, t3)
4. agent 字段表示执行者:
   - retrieval: 需要查制度文档(RAG 检索)
   - tool: 需要调工具(查余额,提交审批等)
   - memory: 需要读取用户状态
   - review: 最终审查(始终是最后一个节点)
5. depends_on 列出必须先完成的 subtask id 列表
6. 拆解时考虑:先获取信息(检索+状态),再执行操作(工具),最后审查

## 领域判断
- hr: 人事,请假,考勤,薪酬,社保
- it: 设备,报修,网络,VPN,密码,软件
- legal: 合同,合规,法务,保密,知识产权
- finance: 报销,预算,采购,出差

## 示例
用户: 我请年假6月1号到3号

输出:
{
  "is_complex": true,
  "subtasks": [
    {"id":"t1","query":"查询当前登录用户的身份和假期余额","domain":"hr","agent":"memory","depends_on":[]},
    {"id":"t2","query":"查询年假请假制度和审批流程","domain":"hr","agent":"retrieval","depends_on":[]},
    {"id":"t3","query":"请假制度合规检查:当前登录用户请年假3天是否满足条件","domain":"hr","agent":"tool","depends_on":["t1","t2"]},
    {"id":"t4","query":"提交请假申请并生成审批流","domain":"hr","agent":"tool","depends_on":["t3"]},
    {"id":"t5","query":"审查整个请假流程结果是否正确","domain":"hr","agent":"review","depends_on":["t4"]}
  ],
  "dependencies": {
    "t1→t3":"需要先知道用户身份和余额才能做合规检查",
    "t2→t3":"需要先检索制度才能判断合规",
    "t3→t4":"合规通过后才能提交",
    "t4→t5":"提交后审查结果"
  }
}

用户: 年假还剩几天

输出:
{
  "is_complex": false,
  "subtasks": [
    {"id":"t1","query":"查询年假余额","domain":"hr","agent":"tool","depends_on":[]}
  ],
  "dependencies": {}
}

## 输出格式 -- 严格 JSON,不要多余文字"""


# ── Fast-path keywords ───────────────────────────────────────────

# agent_key → Planner domain 映射(从 config.domain_keywords 派生)
_AGENT_TO_DOMAIN: dict[str, str] = {
    "hr_agent": "hr", "it_agent": "it",
    "legal_agent": "legal", "finance_agent": "finance",
}


def _get_domain_keywords() -> dict[str, list[str]]:
    """从统一配置 config.domain_keywords 构建 Planner 所需的关键词表.

    返回 {domain: [keywords]} 格式(如 {"hr": ["请假","年假",...]}).
    """
    from src.config import config
    result: dict[str, list[str]] = {}
    for agent_key, keywords in config.domain_keywords.items():
        domain = _AGENT_TO_DOMAIN.get(agent_key, agent_key)
        result[domain] = keywords
    return result


# ── Planner class ────────────────────────────────────────────────

class Planner:
    """LLM-based task DAG planner.

    Usage:
        planner = Planner(client)
        plan = planner.plan("请年假并报销出差费")
        for task in plan.topological_order():
            print(f"→ {task.id}: [{task.agent}] {task.query}")
    """

    def __init__(
        self,
        client: Any,
        model: str = "deepseek-v4-flash",
        enabled: bool = True,
    ) -> None:
        self.client = client
        self.model = model
        self.enabled = enabled

    def plan(self, query: str) -> Plan:
        """Decompose a user query into a DAG of sub-tasks."""
        if not self.enabled:
            return Plan(original_query=query, is_complex=False, subtasks=[
                SubTask(id="t1", query=query, domain="unknown", agent="tool", depends_on=[]),
            ])

        # 1. Fast-path: single-domain keyword check
        fast_result = self._fast_path(query)
        if fast_result is not None:
            return fast_result

        # 2. LLM decomposition
        return self._llm_plan(query)

    def _fast_path(self, query: str) -> Plan | None:
        qlower = query.lower()
        hits: dict[str, list[str]] = {}
        for domain, keywords in _get_domain_keywords().items():
            matched = [kw for kw in keywords if kw in qlower]
            if matched:
                hits[domain] = matched

        if len(hits) == 1:
            domain, _ = next(iter(hits.items()))
            return Plan(original_query=query, is_complex=False, subtasks=[
                SubTask(id="t1", query=query, domain=domain, agent="tool", depends_on=[]),
            ])
        return None

    def _llm_plan(self, query: str) -> Plan:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": f"用户: {query}\n输出:"},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            return self._parse_response(query, content)
        except Exception as e:
            logger.warning("Planner LLM call failed: %s -- falling back to single-task", e)
            return Plan(original_query=query, is_complex=False, subtasks=[
                SubTask(id="t1", query=query, domain="unknown", agent="tool", depends_on=[]),
            ])

    def _parse_response(self, query: str, raw: str) -> Plan:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Planner: invalid JSON, fallback to single-task")
            return Plan(original_query=query, is_complex=False, subtasks=[
                SubTask(id="t1", query=query, domain="unknown", agent="tool", depends_on=[]),
            ])

        try:
            is_complex = bool(data.get("is_complex", False))
            raw_subtasks = data.get("subtasks", [])
            subtasks = [
                SubTask(
                    id=st.get("id", f"t{i+1}"),
                    query=st.get("query", query),
                    domain=st.get("domain", "unknown"),
                    agent=st.get("agent", "unknown"),
                    depends_on=st.get("depends_on", []),
                )
                for i, st in enumerate(raw_subtasks)
            ]
            if not subtasks:
                subtasks = [SubTask(id="t1", query=query, domain="unknown", agent="tool", depends_on=[])]
            return Plan(
                original_query=query,
                is_complex=is_complex and len(subtasks) > 1,
                subtasks=subtasks,
                dependencies=data.get("dependencies", {}),
                raw_llm_response=raw,
            )
        except Exception as e:
            logger.warning("Planner: failed to parse response: %s", e)
            return Plan(original_query=query, is_complex=False, subtasks=[
                SubTask(id="t1", query=query, domain="unknown", agent="tool", depends_on=[]),
            ])
