from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Callable

from src.llm_client import call_llm_with_retry
from src.protocol.types import AgentRequest, AgentResponse
from src.tools.base import ToolDef

if TYPE_CHECKING:
    from openai import OpenAI
    from src.rag.knowledge_base import KnowledgeBase


class BaseAgent:
    """Agent 基类 -- ReAct 循环骨架.

    子类需实现 _build_system_prompt(),其余方法可直接复用.
    """

    def __init__(
        self,
        name: str,
        tools: list[ToolDef],
        kb: KnowledgeBase,
        client: OpenAI,
        model: str = "deepseek-v4-flash",
    ) -> None:
        self.name = name
        self.tools = tools
        self.kb = kb
        self.client = client
        self.model = model

    def run(self, request: AgentRequest, on_step: Callable[[str, Any], None] | None = None) -> AgentResponse:
        """ReAct 主循环.

        1. RAG 检索
        2. 构造 system prompt(检索结果做上下文)
        3. ReAct 循环(最多 max_tool_calls 次)
           - LLM 返回 tool_calls → 执行工具 → 将结果塞回对话
           - LLM 返回 content → 结束,返回 AgentResponse
        4. 达到上限 → 强制生成最终回答
        """
        import copy

        t0 = time.time()
        max_ms = getattr(request, "max_elapsed_ms", 0) or 30_000  # 默认 30 秒超时
        total_tokens = 0
        tool_call_log: list[dict[str, Any]] = []
        retrieved: list[dict[str, Any]] = []
        reasoning_text = ""

        total_tokens, retrieved, tool_call_log, answer, status, reasoning_text = (
            self._react_loop(request, total_tokens, tool_call_log, on_step, t0, max_ms)
        )

        processing_time_ms = int((time.time() - t0) * 1000)

        return AgentResponse(
            agent_name=self.name,
            answer=answer,
            confidence=0.85 if status == "success" else 0.6,
            tool_calls=tool_call_log,
            retrieved_chunks=retrieved,
            status=status,
            error=None,
            processing_time_ms=processing_time_ms,
            tokens_used=total_tokens,
            reasoning=reasoning_text or None,
        )

    def _react_loop(
        self,
        request: AgentRequest,
        total_tokens: int,
        tool_call_log: list[dict[str, Any]],
        on_step: Callable[[str, Any], None] | None = None,
        t0: float = 0.0,
        max_ms: int = 30000,
    ) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]], str, str, str]:
        """ReAct loop impl with timeout check. Returns (tokens, chunks, tool_log, answer, status, reasoning)."""
        is_query_mode = request.intent == "query"
        top_k = 3 if is_query_mode else 10

        # Step 1: RAG 检索
        try:
            retrieved = self.kb.query(request.query, top_k=top_k)
        except Exception:
            retrieved = []

        if on_step:
            try:
                meta = getattr(self.kb, "_last_query_meta", {})
                on_step("retrieval", {
                    "count": len(retrieved),
                    "cache_hit": meta.get("cache_hit", False),
                    "rewritten_query": meta.get("rewritten_query", request.query),
                    "rewrite_used": meta.get("rewrite_used", False),
                    "vector_count": meta.get("vector_count", 0),
                    "bm25_count": meta.get("bm25_count", 0),
                    "fused_count": meta.get("fused_count", 0),
                    "fusion_method": meta.get("fusion_method", ""),
                    "rerank_used": meta.get("rerank_used", False),
                    "sources": [
                        {"source": r.get("source", ""), "score": r.get("score", 0)}
                        for r in retrieved[:5]
                    ],
                })
            except Exception:
                pass

        # Step 2: 构造 system prompt
        system_prompt = self._build_system_prompt(
            request.query, retrieved, request.handoff_context, intent=request.intent
        )

        # Step 3: 初始化对话
        messages: list[dict[str, Any]] = []
        messages.append({"role": "system", "content": system_prompt})
        # 用户上下文作为独立 system 消息注入,不污染 user 消息
        if request.user_context:
            messages.append({"role": "system", "content": request.user_context})
        messages.extend(request.conversation_history)
        messages.append({"role": "user", "content": request.query})

        reasoning_parts: list[str] = []

        # ── Query 模式:单轮直接回答,不注入工具 ────────────
        if is_query_mode:
            if on_step:
                answer_text = self._stream_llm(
                    messages=messages,
                    temperature=request.temperature,
                    on_step=on_step,
                )
                return (total_tokens, retrieved, tool_call_log, answer_text, "success", "")
            response = call_llm_with_retry(
                self.client,
                model=self.model,
                messages=messages,
                temperature=request.temperature,
            )
            msg = response.choices[0].message
            if response.usage:
                total_tokens += response.usage.total_tokens
            if hasattr(msg, "reasoning_content") and msg.reasoning_content:
                reasoning_parts.append(msg.reasoning_content)
            return (
                total_tokens,
                retrieved,
                tool_call_log,
                msg.content or "抱歉,无法生成回答.",
                "success",
                "\n\n".join(reasoning_parts) if reasoning_parts else "",
            )

        # ── Action 模式:完整 ReAct 循环 ────────────────────
        tools_openai = [t.to_openai_format() for t in self.tools] if self.tools else None

        # Step 4: ReAct 循环
        for _ in range(request.max_tool_calls):
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": request.temperature,
            }
            if tools_openai:
                kwargs["tools"] = tools_openai

            response = call_llm_with_retry(self.client, **kwargs)
            msg = response.choices[0].message
            if response.usage:
                total_tokens += response.usage.total_tokens

            # 收集 reasoning(DeepSeek thinking mode)
            if hasattr(msg, "reasoning_content") and msg.reasoning_content:
                reasoning_parts.append(msg.reasoning_content)

            # 判断:LLM 直接给了最终回答(无 tool_calls)
            if msg.content and not msg.tool_calls:
                # 非流式路径已拿到完整内容,分块推送模拟流式显示
                if on_step:
                    content = msg.content
                    chunk_size = 20
                    for i in range(0, len(content), chunk_size):
                        on_step("answer_chunk", {
                            "chunk": content[i:i + chunk_size],
                            "done": False,
                        })
                    on_step("answer_chunk", {"chunk": "", "done": True})
                return (
                    total_tokens,
                    retrieved,
                    tool_call_log,
                    msg.content,
                    "success",
                    "\n\n".join(reasoning_parts) if reasoning_parts else "",
                )

            # 超时检查
            elapsed = int((time.time() - t0) * 1000)
            if elapsed > max_ms:
                return (
                    total_tokens, retrieved, tool_call_log,
                    "处理超时,请稍后重试.",
                    "timeout",
                    "\n\n".join(reasoning_parts) if reasoning_parts else "",
                )

            # 判断:LLM 要求调用工具
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    func_name = tc.function.name
                    try:
                        func_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        func_args = {}

                    # 工具参数校验
                    from src.agents.validation import validate_tool_args
                    func_args = validate_tool_args(func_args)

                    if on_step:
                        on_step("confirm_tool", {
                            "name": func_name,
                            "arguments": func_args,
                            "tool_call_id": tc.id,
                        })

                    result = self._execute_tool(func_name, func_args)

                    tool_call_log.append({
                        "name": func_name,
                        "arguments": func_args,
                        "result": result,
                    })

                    if on_step:
                        try:
                            on_step("tool_call", {
                                "name": func_name,
                                "arguments": func_args,
                                "result": result,
                            })
                        except Exception:
                            pass

                    # 把 tool_call 消息和执行结果塞回对话
                    assistant_msg: dict[str, Any] = {
                        "role": "assistant",
                        "content": msg.content,
                        "tool_calls": [{
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }],
                    }
                    # DeepSeek thinking mode: 必须回传 reasoning_content
                    if hasattr(msg, "reasoning_content") and msg.reasoning_content:
                        assistant_msg["reasoning_content"] = msg.reasoning_content
                    messages.append(assistant_msg)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

        # Step 5: 达到最大工具调用次数 → 强制生成最终回答
        messages.append({
            "role": "user",
            "content": "请基于以上所有工具调用结果,给出最终回答.不要调用更多工具.",
        })
        if on_step:
            answer_text = self._stream_llm(
                messages=messages,
                temperature=request.temperature,
                on_step=on_step,
            )
            return (total_tokens, retrieved, tool_call_log, answer_text, "partial",
                    "\n\n".join(reasoning_parts) if reasoning_parts else "")

        final_response = call_llm_with_retry(
            self.client,
            model=self.model,
            messages=messages,
            temperature=request.temperature,
        )
        final_msg = final_response.choices[0].message
        if final_response.usage:
            total_tokens += final_response.usage.total_tokens

        if hasattr(final_msg, "reasoning_content") and final_msg.reasoning_content:
            reasoning_parts.append(final_msg.reasoning_content)

        return (
            total_tokens,
            retrieved,
            tool_call_log,
            final_msg.content or "抱歉,无法生成回答.",
            "partial",
            "\n\n".join(reasoning_parts) if reasoning_parts else "",
        )

    def _stream_llm(
        self,
        messages: list[dict[str, Any]],
        temperature: float,
        on_step: Callable[[str, Any], None],
    ) -> str:
        """Stream LLM response, push answer_chunk events via on_step, return full text."""
        full_text = ""
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    full_text += delta.content
                    on_step("answer_chunk", {"chunk": delta.content, "done": False})
            on_step("answer_chunk", {"chunk": "", "done": True})
        except Exception:
            # 流式失败回退到非流式
            resp = call_llm_with_retry(self.client, model=self.model,
                                       messages=messages, temperature=temperature)
            full_text = resp.choices[0].message.content or ""
            on_step("answer_chunk", {"chunk": full_text, "done": True})
        return full_text

    def _build_system_prompt(
        self,
        query: str,
        retrieved: list[dict[str, Any]],
        handoff_context: dict[str, Any] | None = None,
        intent: str = "action",
    ) -> str:
        """构造 system prompt,将检索结果和交割上下文注入.

        Args:
            query: 用户原始问题.
            retrieved: RAG 检索结果([{content, source, score}, ...]).
            handoff_context: 来自前序 Agent 的交割上下文.
            intent: "query" 使用轻量 prompt(精简角色 + 无工具描述),
                    "action" 使用完整 prompt.

        Returns:
            完整的 system prompt 字符串.
        """
        from src.agents.prompts import ACTION_ROLE, QUERY_ROLE

        parts: list[str] = []
        template = QUERY_ROLE if intent == "query" else ACTION_ROLE
        parts.append(template.format(name=self.name))

        # ── 交割上下文 ──────────────────────────────────────
        if handoff_context:
            # User profile (injected by memory module)
            profile = handoff_context.get("profile", "")
            if profile:
                parts.append(profile)

            summary = handoff_context.get("summary", "")
            from_agent = handoff_context.get("from_agent", "")
            if summary and from_agent:
                parts.append(
                    f"[前序处理结果 -- 来自 {from_agent}]\n{summary}"
                )
            elif summary:
                parts.append(f"[上下文]\n{summary}")

        # ── 知识库检索结果 ──────────────────────────────────
        if retrieved:
            chunks_section = ["[知识库参考材料]"]
            for r in retrieved:
                chunks_section.append(
                    f"📄 来源: {r.get('source', '未知')} "
                    f"(相关度 {r.get('score', 0):.2f})\n"
                    f"{r.get('content', '')}"
                )
            parts.append("\n\n".join(chunks_section))
        else:
            parts.append(
                "[知识库参考材料]\n"
                "(当前知识库中未检索到相关内容.请明确告知用户你无法回答此问题,"
                "并建议他们联系对应部门获取帮助.)"
            )

        # ── 工具说明(仅 action 模式)──────────────────────
        if intent != "query" and self.tools:
            tool_desc = "\n".join(
                f"- {t.name}: {t.description}" for t in self.tools
            )
            parts.append(f"[可用工具]\n{tool_desc}")

        return "\n\n".join(parts)

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """执行工具并返回结果 -- 委托 Tool Agent 做权限校验和审计.

        Args:
            name: 工具名称.
            arguments: 工具参数字典.

        Returns:
            工具执行结果字典.
        """
        tool_map = {t.name: t for t in self.tools}
        tool = tool_map.get(name)
        if tool is None:
            return {"error": f"未知工具: {name}"}

        # 尝试通过 Tool Agent 执行(权限 + 审计)
        session = getattr(self, "_session_ctx", None)
        if session is not None:
            try:
                from src.agents.tool_agent import get_tool_agent
                ta = get_tool_agent()
                result = ta.execute(tool, arguments, session)
                if result.permission_denied:
                    return {"error": result.error or "权限不足"}
                if result.data is not None:
                    return result.data
            except Exception:
                pass  # Tool Agent 不可用时回退到直接调用

        # 回退:直接调用
        try:
            result = tool.implementation(**arguments)
            if isinstance(result, dict):
                return result
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}


