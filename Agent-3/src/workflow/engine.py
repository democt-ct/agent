"""Workflow Engine -- DAG 拓扑执行器.

接收 Planner 输出的 Plan(DAG),按拓扑序逐节点调度 Agent 执行,
追踪 task_state,支持超时/重试/失败降级.

Usage:
    engine = WorkflowEngine(agent_instances, tool_agent)
    result = engine.run(plan, session_ctx)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from src.agents.planner import Plan, SubTask
from src.agents.tool_agent import ToolAgent, ToolResult
from src.tools.db import db_create_task, db_update_task

logger = logging.getLogger(__name__)


class WorkflowError(Exception):
    """工作流执行异常."""
    pass


class WorkflowResult:
    """工作流执行结果."""

    def __init__(self):
        self.workflow_id: str = ""
        self.answer: str = ""
        self.steps: list[dict] = []
        self.status: str = "running"   # running | completed | failed
        self.total_elapsed_ms: int = 0


class WorkflowEngine:
    """DAG 拓扑执行引擎.

    职责:
      1. 接收 Plan → 拓扑排序 → 逐节点执行
      2. 每个节点根据 agent 类型调用对应 Agent
      3. 追踪 task_state 到数据库
      4. 节点失败 → 决定重试/跳过/终止
    """

    def __init__(
        self,
        agent_instances: dict[str, Any],
        tool_agent: ToolAgent | None = None,
        max_retries_per_node: int = 1,
        node_timeout_ms: int = 60000,
    ):
        self.agent_instances = agent_instances
        self.tool_agent = tool_agent or ToolAgent()
        self.max_retries = max_retries_per_node
        self.node_timeout_ms = node_timeout_ms

    def run(
        self,
        plan: Plan,
        session_ctx: Any = None,
        history: list[dict] | None = None,
        session_id: str = "default",
        on_step: Any = None,
    ) -> WorkflowResult:
        """执行一个 Plan DAG.

        Args:
            plan: Planner 输出的 DAG 计划
            session_ctx: 当前用户 SessionContext
            history: 对话历史
            session_id: 会话 ID
            on_step: 可选回调 (step_id, result) → None
        """
        result = WorkflowResult()
        t0 = time.perf_counter()

        # 单任务快速路径
        if not plan.is_complex or len(plan.subtasks) <= 1:
            return self._run_single(plan, session_ctx, history, on_step, t0)

        # 创建 task_state 记录
        order = plan.topological_order()
        plan_dict = {
            "tasks": [{"id": t.id, "query": t.query, "domain": t.domain, "agent": t.agent} for t in order],
            "dependencies": plan.dependencies,
        }
        result.workflow_id = db_create_task(
            session_ctx.user_id if session_ctx else "anonymous",
            plan.original_query,
            plan_dict,
            session_id,
        )

        # 拓扑序并发执行:每轮识别所有依赖已满足的就绪节点,批量并行
        completed: set[str] = set()
        step_results: dict[str, dict] = {}
        answers: list[str] = []
        pending: set[str] = {t.id for t in order}
        failed: bool = False

        import concurrent.futures

        while pending and not failed:
            # 找出所有依赖已满足的就绪节点
            ready = [
                t for t in order
                if t.id in pending and all(d in completed for d in t.depends_on)
            ]
            if not ready:
                # 有 pending 但无就绪 → 依赖循环或全部被跳过
                missing_deps = {
                    t.id: [d for d in t.depends_on if d not in completed]
                    for t in order if t.id in pending
                }
                logger.warning("Deadlock detected: pending=%s, missing_deps=%s", pending, missing_deps)
                for tid in list(pending):
                    step_results[tid] = {"error": "dependency not met", "task_id": tid}
                    completed.add(tid)
                    pending.discard(tid)
                break

            for task in ready:
                if on_step:
                    try:
                        on_step("workflow_step", {"step": task.id, "agent": task.agent, "query": task.query})
                    except Exception:
                        pass

            # 并发提交当前批次
            if len(ready) == 1:
                # 单节点:直接执行,省去线程开销
                task = ready[0]
                step_result = self._execute_node(task, session_ctx, history)
                step_results[task.id] = step_result
                completed.add(task.id)
                pending.discard(task.id)
                if step_result.get("error"):
                    logger.error("Task %s failed: %s", task.id, step_result["error"])
                    failed = True
                elif step_result.get("answer"):
                    answers.append(f"### {task.query}\n\n{step_result['answer']}")
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(ready)) as executor:
                    future_map = {
                        executor.submit(self._execute_node, task, session_ctx, history): task
                        for task in ready
                    }
                    for future in concurrent.futures.as_completed(future_map):
                        task = future_map[future]
                        try:
                            step_result = future.result()
                        except Exception as e:
                            step_result = {"error": str(e), "task_id": task.id}

                        step_results[task.id] = step_result
                        completed.add(task.id)
                        pending.discard(task.id)

                        if step_result.get("error"):
                            logger.error("Task %s failed: %s", task.id, step_result["error"])
                            failed = True
                        elif step_result.get("answer"):
                            answers.append(f"### {task.query}\n\n{step_result['answer']}")

            # 更新 task_state(仅标记已完成的)
            try:
                db_update_task(
                    result.workflow_id,
                    current_step=",".join(sorted(completed)),
                    step_results=str(step_results),
                )
            except Exception:
                pass

        result.answer = "\n\n---\n\n".join(answers) if answers else "工作流执行完毕"
        result.steps = [
            {"task_id": tid, "result": step_results.get(tid, {})}
            for tid in [t.id for t in order]
        ]
        result.status = "completed" if not failed else "failed"
        result.total_elapsed_ms = int((time.perf_counter() - t0) * 1000)

        # 更新最终状态
        try:
            db_update_task(
                result.workflow_id,
                status=result.status,
                step_results=str(step_results),
            )
        except Exception:
            pass

        return result

    def _run_single(self, plan: Plan, session_ctx, history, on_step, t0) -> WorkflowResult:
        """单任务快速路径 -- 直接调 Agent."""
        result = WorkflowResult()
        task = plan.subtasks[0]

        if on_step:
            try:
                on_step("workflow_step", {"step": task.id, "agent": task.agent, "query": task.query})
            except Exception:
                pass

        step_result = self._execute_node(task, session_ctx, history)
        result.answer = step_result.get("answer", "")
        result.steps = [{"task_id": task.id, "result": step_result}]
        result.status = "completed" if not step_result.get("error") else "failed"
        result.total_elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return result

    def _execute_node(
        self, task: SubTask, session_ctx: Any, history: list[dict] | None
    ) -> dict:
        """执行单个 DAG 节点.

        根据 task.agent 类型路由到对应处理器:
          - retrieval → 走 RAG Agent(当前委托给对应领域 Agent)
          - tool → 走 Tool Agent
          - memory → 走 DB 查询
          - review → 走 Review Agent
          - unknown → 走完整的领域 Agent run()
        """
        for attempt in range(self.max_retries + 1):
            try:
                if task.agent == "tool":
                    return self._execute_as_tool(task, session_ctx)
                elif task.agent == "memory":
                    return self._execute_as_memory(task, session_ctx)
                else:
                    return self._execute_as_agent(task, session_ctx, history)
            except Exception as e:
                if attempt < self.max_retries:
                    logger.warning("Task %s attempt %d failed: %s -- retrying", task.id, attempt + 1, e)
                    time.sleep(0.5 * (attempt + 1))
                else:
                    return {"error": str(e), "task_id": task.id}
        return {"error": "max retries exceeded", "task_id": task.id}

    def _execute_as_tool(self, task: SubTask, session_ctx: Any) -> dict:
        """工具节点 -- 委托给 Tool Agent.

        task.query 中包含工具名和参数线索,需要解析.
        简化实现:用 task.query 匹配 BaseAgent 执行(含工具调用能力).
        """
        # 找到对应领域的 Agent
        domain_map = {
            "hr": "hr_agent", "it": "it_agent",
            "legal": "legal_agent", "finance": "finance_agent",
        }
        agent_key = domain_map.get(task.domain, "hr_agent")
        agent = self.agent_instances.get(agent_key)

        if agent is None:
            return {"error": f"Agent {agent_key} not found", "task_id": task.id}

        from src.protocol.types import AgentRequest
        req = AgentRequest(
            query=task.query,
            agent_name=agent_key,
            max_tool_calls=2,
            temperature=0.5,
        )
        resp = agent.run(req)
        return {
            "answer": resp.answer,
            "tool_calls": [{"name": tc["name"], "result": tc["result"]} for tc in resp.tool_calls],
            "task_id": task.id,
        }

    def _execute_as_memory(self, task: SubTask, session_ctx: Any) -> dict:
        """记忆节点 -- 从 DB 读取用户状态."""
        from src.tools.db import db_get_user, db_get_org_chain, db_get_leave_balance

        if session_ctx is None:
            return {"error": "缺少登录用户上下文", "task_id": task.id}

        user_id = session_ctx.user_id
        user = db_get_user(user_id)

        if user is None:
            return {"error": f"User {user_id} not found", "task_id": task.id}

        chain = db_get_org_chain(user_id)
        balance = db_get_leave_balance(user_id)

        return {
            "answer": f"用户 {user['name']}({user['department_name']},角色 {user['role']})的假期余额:年假{balance.get('annual',0)}天,病假{balance.get('sick',0)}天,事假{balance.get('personal',0)}天",
            "user_state": {
                "user_id": user_id,
                "name": user["name"],
                "department": user.get("department_name"),
                "role": user["role"],
                "manager": chain[1]["name"] if len(chain) > 1 else None,
                "balance": balance,
            },
            "task_id": task.id,
        }

    def _execute_as_agent(self, task: SubTask, session_ctx: Any, history: list[dict] | None) -> dict:
        """通用 Agent 节点 -- 完整 ReAct 执行."""
        domain_map = {
            "hr": "hr_agent", "it": "it_agent",
            "legal": "legal_agent", "finance": "finance_agent",
        }
        agent_key = domain_map.get(task.domain, "hr_agent")
        agent = self.agent_instances.get(agent_key)

        if agent is None:
            return {"error": f"Agent {agent_key} not found", "task_id": task.id}

        from src.protocol.types import AgentRequest
        req = AgentRequest(
            query=task.query,
            agent_name=agent_key,
            conversation_history=history or [],
            max_tool_calls=3,
            temperature=0.5,
        )
        resp = agent.run(req)
        return {
            "answer": resp.answer,
            "tool_calls": [{"name": tc["name"], "result": tc["result"]} for tc in resp.tool_calls],
            "retrieved_chunks": resp.retrieved_chunks,
            "task_id": task.id,
        }
