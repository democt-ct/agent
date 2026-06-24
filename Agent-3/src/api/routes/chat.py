"""对话 API 路由 -- POST /api/chat + SSE /api/chat/stream."""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import uuid
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from src.api.models.schemas import ChatErrorResponse, ChatRequest, ChatResponse
from src.api.service.chat_service import chat as chat_service
from src.config import config as app_config
from src.memory import SessionMemory

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


def _get_collector(request: Request) -> Any:
    """Return the TraceCollector from request state, or a no-op sentinel."""
    return getattr(request.state, "trace_collector", None)


def _get_memory(state: Any, session_id: str) -> SessionMemory | None:
    """Get or create a SessionMemory for the given session."""
    if not app_config.memory_enabled:
        return None
    if not hasattr(state, "_memories"):
        state._memories = {}
    if session_id not in state._memories:
        state._memories[session_id] = SessionMemory(
            window_size=app_config.memory_window_size,
        )
    return state._memories[session_id]


def _get_app_state(request: Request) -> Any:
    """获取应用全局状态."""
    return request.app.state.app_state


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, request: Request):
    """同步对话接口.

    接收用户问题,自动路由到对应 Agent,返回完整回答 + 思维链元数据.
    """
    state = _get_app_state(request)

    if state is None or state.orchestrator is None:
        return JSONResponse(
            status_code=503,
            content=ChatErrorResponse(
                error="服务未就绪",
                detail="Agent 引擎尚未初始化完成,请稍后重试",
            ).model_dump(),
        )

    session_id = req.session_id or uuid.uuid4().hex[:12]

    # ── Session 所有权校验 ──────────────────────────────────
    stream_session = getattr(request.state, "session", None)
    owner = state.session_owners.get(session_id) if hasattr(state, "session_owners") else None
    current_user = stream_session.user_id if stream_session else "anonymous"
    if owner and owner != current_user:
        session_id = uuid.uuid4().hex[:12]

    collector = _get_collector(request)
    memory = _get_memory(state, session_id)

    if collector:
        collector.start_trace(req.query, session_id)

    def _trace_step(event_type: str, data: Any) -> None:
        if collector:
            collector.add_event(event_type, data)

    try:
        # 截断历史
        history = req.history or []
        max_msgs = app_config.chat_history_window * 2
        if len(history) > max_msgs:
            history = history[-max_msgs:]

        result = chat_service(
            query=req.query,
            orchestrator=state.orchestrator,
            agent_instances=state.agent_instances,
            history=history,
            session_id=session_id,
            on_step=_trace_step if collector else None,
            planner=getattr(state, "planner", None),
            memory=memory,
            review_agent=getattr(state, "review_agent", None),
            conversation_store=getattr(state, "conversation_store", None),
            long_term_memory=getattr(state, "long_term_memory", None),
            session_ctx=getattr(request.state, "session", None),
        )

        if collector:
            collector.end_trace("success", total_tokens=result.get("tokens_used", 0))
    except Exception as e:
        logger.exception("对话处理异常")
        if collector:
            collector.add_event("error", {"message": str(e), "stage": "chat_service"})
            collector.end_trace("error")
        return JSONResponse(
            status_code=500,
            content=ChatErrorResponse(
                error="对话处理失败",
                detail=str(e) if app_config.debug_mode else "请求处理失败,请稍后重试",
            ).model_dump(),
        )

    session_ctx = getattr(request.state, "session", None)
    _save_session(state, session_id, req.query, result,
                  user_id=session_ctx.user_id if session_ctx else "anonymous")

    return ChatResponse(**result)


# ═══════════════════════════════════════════════════════════════
# SSE 流式对话
# ═══════════════════════════════════════════════════════════════


@router.get("/chat/stream")
async def chat_stream(
    query: str = Query(..., min_length=1, max_length=2000),
    session_id: str = Query(None),
    request: Request = None,
):
    """SSE 流式对话:逐步推送 routing → retrieval → tool_call → reasoning → answer.

    前端用 EventSource 或 fetch + ReadableStream 消费.
    """
    state = _get_app_state(request)

    if state is None or state.orchestrator is None:
        return JSONResponse(
            status_code=503,
            content=ChatErrorResponse(error="服务未就绪").model_dump(),
        )

    sid = session_id or uuid.uuid4().hex[:12]

    # ── Session 所有权校验 ──────────────────────────────────
    session_ctx = getattr(request.state, "session", None)
    owner = state.session_owners.get(sid) if hasattr(state, "session_owners") else None
    current_user = session_ctx.user_id if session_ctx else "anonymous"
    if owner and owner != current_user:
        sid = uuid.uuid4().hex[:12]  # 非法访问:重开新 session

    history = []
    collector = _get_collector(request)
    memory = _get_memory(state, sid)

    # 从已有会话中加载历史(优先 conversation_store,回退 state.sessions)
    if state.conversation_store:
        history = state.conversation_store.to_history_format(sid)
    elif state.sessions and sid in state.sessions:
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in state.sessions[sid]
            if m["role"] in ("user", "assistant")
        ]
    # 截断历史(最多保留最近 N 轮,防止 context window 溢出)
    max_msgs = app_config.chat_history_window * 2
    if len(history) > max_msgs:
        history = history[-max_msgs:]

    async def event_stream() -> AsyncGenerator[str, None]:
        """SSE 事件流生成器."""
        loop = asyncio.get_event_loop()

        if collector:
            collector.start_trace(query, sid)

        try:
            # 1️⃣ 路由 -- 在事件循环中执行(Orchestrator 是纯同步但轻量)
            route_result = await loop.run_in_executor(
                None, state.orchestrator.route, query, True, history
            )
            yield _sse("routing", route_result)

            if collector:
                collector.add_event("routing", route_result)

            # Fallback 快速返回
            primary = route_result.get("primary", "fallback")
            method = route_result.get("method", "unknown")
            if primary == "fallback" or method == "greeting":
                from src.api.service.chat_service import FALLBACK_RESPONSES
                answer = FALLBACK_RESPONSES.get(
                    "greeting" if method == "greeting" else "unknown",
                    FALLBACK_RESPONSES["unknown"],
                )
                yield _sse("answer", {"content": answer})
                yield _sse("done", {"session_id": sid})
                if collector:
                    collector.add_event("answer", {"content": answer, "agent_name": "fallback"})
                    collector.end_trace("fallback")
                return

            # 2️⃣ 执行 Agent,通过 queue 桥接逐步推送事件
            q: queue.Queue[tuple[str, Any]] = queue.Queue()

            def on_step(event_type: str, data: Any) -> None:
                q.put((event_type, data))
                if collector:
                    collector.add_event(event_type, data)

            future = loop.run_in_executor(
                None,
                lambda: chat_service(
                    query=query,
                    orchestrator=state.orchestrator,
                    agent_instances=state.agent_instances,
                    history=history,
                    session_id=sid,
                    on_step=on_step,
                    planner=getattr(state, "planner", None),
                    memory=memory,
                    review_agent=getattr(state, "review_agent", None),
                    conversation_store=getattr(state, "conversation_store", None),
                    long_term_memory=getattr(state, "long_term_memory", None),
                    session_ctx=getattr(request.state, "session", None),
                ),
            )

            # 3️⃣ 从 queue 消费事件,逐步推送到客户端
            while not future.done() or not q.empty():
                if await request.is_disconnected():
                    logger.info("SSE 客户端断开,清理后台任务")
                    future.cancel()
                    return
                try:
                    event_type, data = q.get_nowait()
                    yield _sse(event_type, data)
                except queue.Empty:
                    await asyncio.sleep(0.03)

            result = future.result()

            if collector:
                collector.add_event("answer", {
                    "content": result.get("answer", ""),
                    "agent_name": result.get("agent_name", ""),
                })
                collector.end_trace("success", total_tokens=result.get("tokens_used", 0))

            # 4️⃣ 最终事件(answer_chunk 已在 Agent 内通过 on_step 推送)
            reasoning = result.get("reasoning")
            if reasoning:
                yield _sse("reasoning", {"content": reasoning})

            yield _sse("answer", {
                "content": result.get("answer", ""),
                "agent_name": result.get("agent_name", ""),
                "tokens": result.get("tokens_used", 0),
                "time": result.get("processing_time_ms", 0),
                "action_card": result.get("action_card"),
            })

            yield _sse("done", {"session_id": sid})

            # 保存会话
            stream_session = getattr(request.state, "session", None)
            _save_session(state, sid, query, result,
                          user_id=stream_session.user_id if stream_session else "anonymous")

        except Exception as e:
            logger.exception("SSE 流处理异常")
            if collector:
                collector.add_event("error", {"message": str(e), "stage": "sse_stream"})
                collector.end_trace("error")
            yield _sse("error", {"message": str(e)})
            yield _sse("done", {"session_id": sid})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


def _sse(event: str, data: dict) -> str:
    """构造 SSE 事件字符串."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _save_session(state: Any, session_id: str, query: str, result: dict, user_id: str = "anonymous") -> None:
    """保存对话到会话记录."""
    if state.sessions is None:
        return
    if session_id not in state.sessions:
        state.sessions[session_id] = []
        state.session_owners[session_id] = user_id
    state.sessions[session_id].append({"role": "user", "content": query})
    state.sessions[session_id].append({
        "role": "assistant",
        "content": result.get("answer", ""),
        "agent": result.get("agent_name", ""),
        "routing": result.get("routing"),
    })
