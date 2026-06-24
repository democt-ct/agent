"""Pydantic 请求/响应模型 -- API 数据契约."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── 请求模型 ─────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """对话请求."""

    query: str = Field(..., description="用户输入的问题", min_length=1, max_length=2000)
    session_id: str | None = Field(
        default=None,
        description="会话 ID.不传则服务端自动生成",
    )
    history: list[dict] = Field(
        default_factory=list,
        description="历史消息 [{\"role\": \"user\"|\"assistant\", \"content\": \"...\"}]",
    )


class ChatStreamRequest(BaseModel):
    """SSE 流式对话请求(预留)."""

    query: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None
    history: list[dict] = Field(default_factory=list)


# ── 响应模型 ─────────────────────────────────────────────────────

class ChatResponse(BaseModel):
    """同步对话响应."""

    session_id: str = Field(..., description="会话 ID")
    answer: str = Field(..., description="最终回答(markdown 格式)")
    routing: dict = Field(..., description="路由信息")
    """
    {
        "primary": "hr_agent",
        "secondary": null,
        "confidence": 0.95,
        "method": "keyword",
        "matched_keywords": ["年假"]
    }
    """
    agent_name: str = Field("", description="实际回答的 Agent 名称")
    retrieved_chunks: list[dict] = Field(
        default_factory=list,
        description="RAG 检索到的知识片段 [{source, content, score}]",
    )
    tool_calls: list[dict] = Field(
        default_factory=list,
        description="工具调用记录 [{name, arguments, result}]",
    )
    reasoning: str | None = Field(None, description="DeepSeek 思考过程")
    processing_time_ms: int = Field(0, description="处理耗时")
    tokens_used: int = Field(0, description="Token 消耗总数")
    action_card: dict | None = Field(None, description="操作卡片(前端渲染交互组件)")


class ChatErrorResponse(BaseModel):
    """错误响应."""

    error: str = Field(..., description="错误描述")
    detail: str | None = Field(None, description="详细错误信息")


# ── Agent 信息模型 ──────────────────────────────────────────────

class AgentInfo(BaseModel):
    """Agent 信息."""

    name: str = Field(..., description="Agent 标识名")
    display_name: str = Field(..., description="展示名称")
    description: str = Field(..., description="能力描述")
    tools: list[str] = Field(default_factory=list, description="工具列表")


class HealthStatus(BaseModel):
    """健康检查响应."""

    status: str = Field("ok", description="服务状态: ok | initializing | error")
    agents: list[AgentInfo] = Field(default_factory=list, description="已注册 Agent")
    kb_count: int = Field(0, description="已加载知识库数量")
    init_progress: dict | None = Field(None, description="初始化进度(initializing 时有值)")
    components: dict[str, str] = Field(
        default_factory=lambda: {"db": "unknown", "llm": "unknown"},
        description="组件状态: db/llm 各自的 ok/error/unknown"
    )


# ── 会话管理模型 ──────────────────────────────────────────────

class SessionInfo(BaseModel):
    """会话信息."""

    session_id: str
    message_count: int
    last_query: str = ""
    created_at: str = ""
