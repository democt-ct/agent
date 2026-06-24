"""对话编排服务 -- 抽出 CLI 和 API 共用的 Agent 调用逻辑.

支持:
- 单 Agent 回答
- 动态 max_tool_calls(按置信度自适应)
- 跨域串行交割(primary → secondary)
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable

from src.agents.base_agent import BaseAgent
from src.agents.orchestrator import Orchestrator
from src.config import config
from src.llm_client import call_llm_with_retry
from src.protocol.types import AgentRequest

FALLBACK_RESPONSES: dict[str, str] = {
    "greeting": "你好!我是企业智能助手,可以帮你解答以下领域的问题:\n\n"
                "- 🏥 **HR 专家** -- 人事制度,考勤,请假,薪酬福利\n"
                "- 💻 **IT 专家** -- 设备报修,软件安装,网络 VPN,密码账号\n"
                "- ⚖️ **法务专家** -- 合同,合规,数据保护,知识产权\n"
                "- 💰 **财务专家** -- 报销,预算,出差标准,采购流程\n\n"
                "请问有什么可以帮你的?",
    "unknown": "抱歉,这个问题不在我的知识范围内.\n\n"
               "你可以询问以下领域的问题:\n"
               "- 🏥 **HR 人事** -- 请假,年假,考勤,薪酬\n"
               "- 💻 **IT 支持** -- 报修,设备申领,密码,网络\n"
               "- ⚖️ **法务合规** -- 合同,保密,数据保护\n"
               "- 💰 **财务支持** -- 报销,预算,差旅,采购",
}


def _calc_max_tool_calls(confidence: float) -> int:
    """根据置信度动态调整工具调用上限."""
    if confidence >= 0.9:
        return config.max_tool_calls_high   # 很确定,2 轮够了
    if confidence >= 0.7:
        return config.max_tool_calls_med    # 中等,3 轮
    return config.max_tool_calls_low         # 不确定,多试试


def chat(
    query: str,
    orchestrator: Orchestrator,
    agent_instances: dict[str, BaseAgent],
    history: list[dict] | None = None,
    session_id: str | None = None,
    on_step: Callable[[str, Any], None] | None = None,
    planner: Any = None,
    memory: Any = None,
    review_agent: Any = None,
    conversation_store: Any = None,
    long_term_memory: Any = None,
    session_ctx: Any = None,
) -> dict[str, Any]:
    """完整对话编排:路由 → Agent 执行 → 返回结果.

    支持跨域串行交割:如果路由识别出 secondary Agent,
    或 primary Agent 返回 handoff_suggestions,自动接力处理.

    如果提供了 Planner 且 PLANNER_ENABLED=true,则先进行任务规划:
    - 单意图 → 透传原路由逻辑
    - 多意图 → 拆分为子任务串行执行

    如果提供了 conversation_store,自动加载/保存会话历史.
    """
    if session_id is None:
        session_id = uuid.uuid4().hex[:12]

    t0 = time.time()

    # ── 加载会话历史(Memory L2) ──────────────────────────
    if conversation_store and not history:
        history = conversation_store.to_history_format(session_id)

    # ── 注入用户上下文:路由后才加,避免污染关键词匹配 ──────
    raw_query = query  # 路由用原始 query
    user_context_str = ""
    if session_ctx:
        user_context_str = (
            f"[当前登录用户 user_id={session_ctx.user_id} "
            f"姓名={session_ctx.name} "
            f"部门={session_ctx.department_name} "
            f"角色={session_ctx.role}."
            f"当用户说'我''帮我'时,user_id 就是 {session_ctx.user_id},"
            f"直接用这个 ID 调用工具,不要询问.]"
        )

    # ── 0. Planner(如果启用) ──────────────────────────────
    if planner and planner.enabled and config.planner_enabled:
        plan = planner.plan(raw_query)
        if plan.is_complex and len(plan.subtasks) > 1:
            return _execute_plan(
                plan, orchestrator, agent_instances, history,
                session_id, on_step, t0, memory,
                session_ctx=session_ctx,
                review_agent=review_agent,
                conversation_store=conversation_store,
                long_term_memory=long_term_memory,
                compressor=None,  # Planner 路径暂不触发压缩
            )

    # ── 对话历史(供路由上下文推断)──
    conv_history: list[dict] = history or []

    # ── 1. 路由(用原始 query,避免注入文字污染关键词匹配)──
    route_result = orchestrator.route(raw_query, history=conv_history)
    route_result["query"] = raw_query  # 供 ReviewAgent LLM 审查用
    method = route_result.get("method", "unknown")
    primary = route_result.get("primary", "fallback")
    secondary = route_result.get("secondary")
    confidence = route_result.get("confidence", 0.5)
    intent = route_result.get("intent", "action")
    action_card = route_result.get("action_card")

    # 路由完成后,query 保持原始内容,用户上下文通过 AgentRequest.user_context 注入
    query = raw_query
    if action_card:
        query = query + "\n[系统提示:用户意图已识别,界面将自动展示操作表单.你只需用一句简短友好的话引导用户填写,不要分析,不要四段式,不要重复说明流程.]"

    # ── Fallback(寒暄 / 未知领域) ────────────────────────
    if primary == "fallback" or method == "greeting":
        elapsed = int((time.time() - t0) * 1000)
        answer = FALLBACK_RESPONSES.get(
            "greeting" if method == "greeting" else "unknown",
            FALLBACK_RESPONSES["unknown"],
        )
        _record_memory(memory, query, answer)
        return {
            "session_id": session_id,
            "answer": answer,
            "routing": route_result,
            "agent_name": "fallback",
            "retrieved_chunks": [],
            "tool_calls": [],
            "reasoning": None,
            "processing_time_ms": elapsed,
            "tokens_used": 0,
            "action_card": None,
        }

    # ── 2. Primary Agent 执行 ──────────────────────────────
    max_calls = _calc_max_tool_calls(confidence)

    # 动态 temperature:query 用低温追求准确性,action 用中温追求丰富度
    run_temperature = 0.1 if intent == "query" else 0.5

    # Memory context: use session memory if available
    profile_text: str = ""
    if memory and memory.enabled:
        conv_history = memory.get_context()
        profile_text = memory.profile_text

    # Long-term memory: recall user facts and preferences
    ltm_context: str = ""
    if long_term_memory:
        try:
            uid = session_ctx.user_id if session_ctx else "anonymous"
            ltm_context = long_term_memory.recall_as_context(uid, limit=5)
        except Exception:
            pass

    def _run_agent(agent_key: str, handoff_ctx: dict | None = None, run_intent: str = "action") -> dict:
        agent = agent_instances.get(agent_key)
        if agent is None:
            return {
                "answer": f"抱歉,{agent_key} 当前不可用.",
                "agent_name": agent_key,
                "retrieved_chunks": [],
                "tool_calls": [],
                "reasoning": None,
                "handoff_suggestions": None,
            }

        # Inject user profile + LTM context into handoff context
        enriched_ctx = dict(handoff_ctx or {})
        if profile_text:
            enriched_ctx["profile"] = profile_text
        if ltm_context:
            existing_profile = enriched_ctx.get("profile", "")
            enriched_ctx["profile"] = (existing_profile + "\n" + ltm_context).strip()

        req = AgentRequest(
            query=query,
            agent_name=agent_key,
            conversation_history=conv_history,
            handoff_context=enriched_ctx if enriched_ctx else None,
            max_tool_calls=max_calls,
            temperature=run_temperature,
            intent=run_intent,
            user_context=user_context_str,
        )
        if session_ctx:
            agent._session_ctx = session_ctx
        resp = agent.run(req, on_step=on_step)
        return {
            "answer": resp.answer,
            "agent_name": resp.agent_name,
            "retrieved_chunks": resp.retrieved_chunks,
            "tool_calls": resp.tool_calls,
            "reasoning": resp.reasoning,
            "handoff_suggestions": resp.handoff_suggestions,
            "tokens_used": resp.tokens_used,
        }

    # ── 构建 SummaryCompressor(异步压缩长会话)────────────
    _compressor = None
    if conversation_store and agent_instances:
        try:
            _client = next(iter(agent_instances.values())).client
            from src.memory.summary_compressor import SummaryCompressor
            _compressor = SummaryCompressor(client=_client, model=config.llm_model)
        except Exception:
            pass

    # ── Query 意图:轻量路径(跳 Planner + Review)─────────
    if intent == "query":
        query_tool_result = _try_quick_tool(primary, raw_query, session_ctx, agent_instances)
        if query_tool_result is not None:
            elapsed = int((time.time() - t0) * 1000)
            answer = query_tool_result["answer"]
            _record_memory(memory, query, answer)
            result = {
                "session_id": session_id,
                "answer": answer,
                "routing": route_result,
                "agent_name": query_tool_result["agent_name"],
                "retrieved_chunks": [],
                "tool_calls": query_tool_result["tool_calls"],
                "reasoning": None,
                "processing_time_ms": elapsed,
                "tokens_used": 0,
                "action_card": action_card,
            }
            _save_conversation(conversation_store, long_term_memory, session_id, query, result,
                               compressor=_compressor,
                               user_id=session_ctx.user_id if session_ctx else "anonymous")
            return result

        primary_result = _run_agent(primary, run_intent="query")
        elapsed = int((time.time() - t0) * 1000)
        _record_memory(memory, query, primary_result["answer"])
        result = {
            "session_id": session_id,
            "answer": primary_result["answer"],
            "routing": route_result,
            "agent_name": primary_result["agent_name"],
            "retrieved_chunks": primary_result["retrieved_chunks"],
            "tool_calls": primary_result["tool_calls"],
            "reasoning": primary_result.get("reasoning"),
            "processing_time_ms": elapsed,
            "tokens_used": primary_result.get("tokens_used", 0),
            "action_card": action_card,
        }
        # Query 模式轻量审查:只写 review 字段,不修改 answer
        if review_agent and result.get("retrieved_chunks"):
            result = _apply_review(result, review_agent, modify_answer=False)
        _save_conversation(conversation_store, long_term_memory, session_id, query, result,
                           compressor=_compressor,
                           user_id=session_ctx.user_id if session_ctx else "anonymous")
        return result

    # ── Action 意图:完整路径 ──────────────────────────────
    if secondary and secondary != primary:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f_primary = executor.submit(_run_agent, primary)
            f_secondary = executor.submit(_run_agent, secondary)
            primary_result = f_primary.result()
            secondary_result = f_secondary.result()

        total_tokens = primary_result.get("tokens_used", 0) + secondary_result.get("tokens_used", 0)
        merge_results = [
            {"agent_name": primary_result['agent_name'], "answer": primary_result['answer']},
            {"agent_name": secondary_result['agent_name'], "answer": secondary_result['answer']},
        ]
        _raw_answers = "\n\n---\n\n".join(
            f"## {r['agent_name']} 的处理结果\n\n{r['answer']}" for r in merge_results
        )
        _llm_client = next(iter(agent_instances.values())).client if agent_instances else None
        _llm_model = config.llm_model
        merged_answer = _merge_answers(_llm_client, _llm_model, raw_query, merge_results) if _llm_client else _raw_answers
        elapsed = int((time.time() - t0) * 1000)
        _record_memory(memory, query, merged_answer)
        result = {
            "session_id": session_id,
            "answer": merged_answer,
            "raw_answers": _raw_answers,
            "routing": {**route_result, "handoff": secondary, "handoff_reason": "并行执行"},
            "agent_name": f"{primary_result['agent_name']} ‖ {secondary_result['agent_name']}",
            "retrieved_chunks": (
                primary_result["retrieved_chunks"] + secondary_result.get("retrieved_chunks", [])
            ),
            "tool_calls": (
                primary_result["tool_calls"] + secondary_result.get("tool_calls", [])
            ),
            "reasoning": (
                (primary_result.get("reasoning") or "")
                + "\n\n---\n\n"
                + (secondary_result.get("reasoning") or "")
                if primary_result.get("reasoning") or secondary_result.get("reasoning")
                else None
            ),
            "processing_time_ms": elapsed,
            "tokens_used": total_tokens,
            "action_card": action_card,
        }
        if review_agent:
            result = _apply_review(result, review_agent)
        _save_conversation(conversation_store, long_term_memory, session_id, query, result,
                           compressor=_compressor,
                           user_id=session_ctx.user_id if session_ctx else "anonymous")
        return result

    primary_result = _run_agent(primary)

    # ── 3. 判断是否需要跨域交割 ────────────────────────────
    handoff_target = None
    handoff_reason = ""

    # secondary 已在上方并行处理,此处仅处理 Agent 自身建议的交割
    # 信号 B:Primary Agent 自己建议转交
    suggestions = primary_result.get("handoff_suggestions")
    if suggestions and isinstance(suggestions, list) and len(suggestions) > 0:
        sug = suggestions[0]
        sug_target = sug.get("target_agent")
        if sug_target and sug_target != primary and agent_instances.get(sug_target):
            handoff_target = sug_target
            handoff_reason = sug.get("reason", f"{primary} 建议转交 {sug_target}")

    # ── 4. Secondary Agent 接力 ───────────────────────────
    total_tokens = primary_result.get("tokens_used", 0)

    if handoff_target:
        handoff_ctx = {
            "from_agent": primary,
            "summary": primary_result["answer"][:500],
            "unresolved_items": [handoff_reason],
        }
        secondary_result = _run_agent(handoff_target, handoff_ctx)
        total_tokens += secondary_result.get("tokens_used", 0)

        # 合并回答(LLM 综合摘要 + 回退拼接)
        merge_results = [
            {"agent_name": primary_result['agent_name'], "answer": primary_result['answer']},
            {"agent_name": secondary_result['agent_name'], "answer": secondary_result['answer']},
        ]
        _raw_answers = "\n\n---\n\n".join(
            f"## {r['agent_name']} 的处理结果\n\n{r['answer']}" for r in merge_results
        )
        _llm_client = next(iter(agent_instances.values())).client if agent_instances else None
        _llm_model = config.llm_model
        merged_answer = _merge_answers(_llm_client, _llm_model, raw_query, merge_results) if _llm_client else _raw_answers

        elapsed = int((time.time() - t0) * 1000)
        _record_memory(memory, query, merged_answer)
        result = {
            "session_id": session_id,
            "answer": merged_answer,
            "raw_answers": _raw_answers,
            "routing": {
                **route_result,
                "handoff": handoff_target,
                "handoff_reason": handoff_reason,
            },
            "agent_name": f"{primary_result['agent_name']} → {secondary_result['agent_name']}",
            "retrieved_chunks": (
                primary_result["retrieved_chunks"]
                + secondary_result.get("retrieved_chunks", [])
            ),
            "tool_calls": (
                primary_result["tool_calls"]
                + secondary_result.get("tool_calls", [])
            ),
            "reasoning": (
                (primary_result.get("reasoning") or "")
                + "\n\n---\n\n"
                + (secondary_result.get("reasoning") or "")
                if primary_result.get("reasoning") or secondary_result.get("reasoning")
                else None
            ),
            "processing_time_ms": elapsed,
            "tokens_used": total_tokens,
            "action_card": action_card,
        }
        if review_agent:
            result = _apply_review(result, review_agent)
        _save_conversation(conversation_store, long_term_memory, session_id, query, result,
                           compressor=_compressor,
                           user_id=session_ctx.user_id if session_ctx else "anonymous")
        return result

    # ── 5. 仅 primary(单域回答) ──────────────────────────
    elapsed = int((time.time() - t0) * 1000)
    _record_memory(memory, query, primary_result["answer"])
    result = {
        "session_id": session_id,
        "answer": primary_result["answer"],
        "routing": route_result,
        "agent_name": primary_result["agent_name"],
        "retrieved_chunks": primary_result["retrieved_chunks"],
        "tool_calls": primary_result["tool_calls"],
        "reasoning": primary_result.get("reasoning"),
        "processing_time_ms": elapsed,
        "tokens_used": total_tokens,
        "action_card": action_card,
    }
    if review_agent:
        result = _apply_review(result, review_agent)
    _save_conversation(conversation_store, long_term_memory, session_id, query, result,
                       compressor=_compressor,
                       user_id=session_ctx.user_id if session_ctx else "anonymous")
    return result


def _save_conversation(store, ltm, session_id, query, result, user_id="anonymous", compressor=None):
    """持久化本轮对话(L2)+ 提取长期记忆(L3)+ 触发压缩."""
    if store:
        store.save(session_id, user_id, "user", query)
        store.save(session_id, user_id, "assistant", result.get("answer", ""),
                   metadata={"agent": result.get("agent_name"),
                             "tool_calls": [tc.get("name") for tc in result.get("tool_calls", [])],
                             "tokens": result.get("tokens_used", 0)})
        if ltm:
            ltm.extract_from_workflow(user_id, session_id, result)
        # 触发上下文压缩(异步线程,不阻塞对话)
        _try_compress(store, session_id, compressor)


def _apply_review(result: dict, review_agent: Any, modify_answer: bool = True) -> dict:
    """对 chat 返回结果执行 Review Agent 审查,注入审查结论.

    Args:
        modify_answer: False 时只写 review 字段,不修改 answer(query 模式用).
    """
    import logging
    _log = logging.getLogger(__name__)
    try:
        verdict = review_agent.review(
            answer=result.get("answer", ""),
            tool_results=result.get("tool_calls", []),
            retrieved_chunks=result.get("retrieved_chunks", []),
            raw_query=result.get("routing", {}).get("query", ""),
        )
        if modify_answer and verdict.fixed_answer:
            result["answer"] = verdict.fixed_answer
        result["review"] = {
            "passed": verdict.passed,
            "confidence": verdict.confidence,
            "issues": verdict.issues,
            "warnings": verdict.warnings,
        }
        if not verdict.passed:
            _log.warning("Review issues: %s", verdict.issues)
    except Exception as e:
        _log.warning("Review Agent failed: %s", e)
    return result


def _try_compress(store: Any, session_id: str, compressor: Any = None) -> None:
    """触发上下文压缩(如果会话消息超过阈值)."""
    if compressor is None:
        return
    try:
        if not compressor.should_compress(store, session_id):
            return
        import threading
        threading.Thread(
            target=compressor.compress,
            args=(store, session_id),
            daemon=True,
        ).start()
    except Exception:
        pass


def _record_memory(memory: Any, query: str, answer: str) -> None:
    """Record a Q&A turn in session memory if enabled."""
    if memory and memory.enabled:
        try:
            memory.add("user", query)
            memory.add("assistant", answer)
        except Exception:
            pass


def _merge_answers(client: Any, model: str, query: str, results: list[dict]) -> str:
    """将多个 Agent 的回答用 LLM 综合为一段连贯的摘要.

    Args:
        client: OpenAI 兼容客户端
        model: 模型名
        query: 用户原始问题
        results: [{"agent_name": str, "answer": str}, ...]

    Returns:
        综合后的回答文本;LLM 调用失败时回退到分隔线拼接.
    """
    if len(results) <= 1:
        return results[0]["answer"] if results else ""

    parts = "\n\n".join(
        f"[{r['agent_name']}]\n{r['answer']}" for r in results
    )
    messages = [
        {"role": "system", "content": "你是一个信息整合助手,将多个专家的回答整合为一段连贯,无重复的回答.使用中文."},
        {"role": "user", "content": f"用户问题:{query}\n\n各专家回答:\n{parts}"},
    ]
    try:
        import logging
        resp = call_llm_with_retry(client, model=model, messages=messages, temperature=0.3)
        merged = resp.choices[0].message.content
        if merged and merged.strip():
            return merged.strip()
    except Exception as e:
        logging.getLogger(__name__).warning("_merge_answers LLM 调用失败,回退到拼接: %s", e)

    # 回退:带标题的分隔线拼接
    return "\n\n---\n\n".join(
        f"## {r['agent_name']} 的处理结果\n\n{r['answer']}" for r in results
    )


def _try_quick_tool(primary: str, raw_query: str, session_ctx: Any,
                   agent_instances: dict) -> dict[str, Any] | None:
    """通用快速查询路径:遍历 agent 的 tools,命中 quick_triggers 时跳过 LLM 直接调工具.

    相比旧版 _try_direct_query_tool(仅支持 HR 假期查询),新版本:
    - 遍历 Agent 的所有工具,按 ToolDef.quick_triggers 匹配
    - 任何 Agent 的查询类工具都可以声明 quick_triggers 获得加速
    - 新增快速查询只需在 ToolDef 上声明,无需改 chat_service
    """
    if session_ctx is None:
        return None
    agent = agent_instances.get(primary)
    if agent is None:
        return None

    for tool in agent.tools:
        if not tool.quick_triggers or tool.quick_args_builder is None:
            continue
        if not any(kw in raw_query for kw in tool.quick_triggers):
            continue
        try:
            args = tool.quick_args_builder(session_ctx)
            data = tool.implementation(**args)
        except Exception:
            continue  # 快速路径失败 → 回退到完整 ReAct

        tool_call = {
            "name": tool.name,
            "arguments": args,
            "result": data,
        }
        if isinstance(data, dict) and data.get("error"):
            answer = data["error"]
        else:
            answer = _format_tool_result(tool.name, session_ctx, data)

        agent_display = primary.replace("_agent", "")
        return {
            "answer": answer,
            "agent_name": f"{agent_display} 专家",
            "tool_calls": [tool_call],
        }

    return None


def _format_tool_result(tool_name: str, session_ctx: Any, data: Any) -> str:
    """将工具返回结果格式化为用户友好的文本."""
    if tool_name == "get_leave_balance" and isinstance(data, dict):
        annual = data.get("annual", 0)
        sick = data.get("sick", 0)
        personal = data.get("personal", 0)
        return (
            f"{session_ctx.name},你当前的假期余额是:\n\n"
            f"- 年假:**{annual} 天**\n"
            f"- 病假:**{sick} 天**\n"
            f"- 事假:**{personal} 天**"
        )
    if isinstance(data, dict):
        lines = [f"**{k}**:{v}" for k, v in data.items()
                 if not k.startswith("_") and v is not None]
        return "\n".join(lines) if lines else str(data)
    return str(data)


# ═══════════════════════════════════════════════════════════════
# Planner multi-task execution
# ═══════════════════════════════════════════════════════════════


def _execute_plan(
    plan: Any,
    orchestrator: Orchestrator,
    agent_instances: dict[str, BaseAgent],
    history: list[dict] | None,
    session_id: str,
    on_step: Callable[[str, Any], None] | None,
    t0: float,
    memory: Any = None,
    session_ctx: Any = None,
    review_agent: Any = None,
    conversation_store: Any = None,
    long_term_memory: Any = None,
    compressor: Any = None,
) -> dict[str, Any]:
    """使用 WorkflowEngine 执行 Planner 输出的 DAG.

    按拓扑序逐节点执行,支持依赖等待和失败降级.
    """
    from src.workflow.engine import WorkflowEngine
    from src.agents.tool_agent import get_tool_agent

    engine = WorkflowEngine(agent_instances, tool_agent=get_tool_agent())
    wf_result = engine.run(
        plan=plan,
        session_ctx=session_ctx,
        history=history,
        session_id=session_id,
        on_step=on_step,
    )

    elapsed = wf_result.total_elapsed_ms

    # 从 step 结果中聚合 tool_calls / chunks
    all_tools: list[dict] = []
    all_chunks: list[dict] = []
    for step in wf_result.steps:
        r = step.get("result", {})
        if r.get("tool_calls"):
            all_tools.extend(r["tool_calls"])
        if r.get("retrieved_chunks"):
            all_chunks.extend(r["retrieved_chunks"])

    if memory and memory.enabled:
        _record_memory(memory, plan.original_query, wf_result.answer)

    result = {
        "session_id": session_id,
        "answer": wf_result.answer,
        "routing": {
            "primary": plan.subtasks[0].domain + "_agent" if plan.subtasks else "fallback",
            "method": "planner_dag",
            "plan_subtasks": len(plan.subtasks),
        },
        "agent_name": " → ".join(
            t.domain for t in plan.subtasks
        ) if plan.subtasks else "planner",
        "retrieved_chunks": all_chunks,
        "tool_calls": all_tools,
        "reasoning": None,
        "processing_time_ms": elapsed,
        "tokens_used": 0,  # Engine 不追踪 token(后续可加)
    }
    if review_agent:
        result = _apply_review(result, review_agent)
    _save_conversation(conversation_store, long_term_memory, session_id,
                       plan.original_query, result,
                       compressor=compressor,
                       user_id=session_ctx.user_id if session_ctx else "anonymous")
    return result
