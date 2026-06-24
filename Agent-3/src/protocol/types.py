from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentRequest:
    """Orchestrator → Specialist Agent 的请求"""

    query: str
    agent_name: str
    conversation_history: list[dict] = field(default_factory=list)
    extracted_entities: dict = field(default_factory=dict)
    handoff_context: dict | None = None
    max_tool_calls: int = 5
    temperature: float = 0.3
    intent: str = "action"  # "query" | "action" -- 决定 Agent 使用轻量还是完整模式
    user_context: str = ""  # 用户身份上下文,作为独立 system 消息注入,不污染 user 消息


@dataclass
class AgentResponse:
    """Specialist Agent → Orchestrator 的返回"""

    agent_name: str
    answer: str
    confidence: float
    tool_calls: list[dict] = field(default_factory=list)
    retrieved_chunks: list[dict] = field(default_factory=list)
    handoff_suggestions: list[dict] | None = None
    status: str = "success"  # "success" | "partial" | "failed"
    error: str | None = None
    processing_time_ms: int = 0
    tokens_used: int = 0
    reasoning: str | None = None  # DeepSeek thinking mode 的推理过程


@dataclass
class AgentRegistration:
    """Agent 注册信息(Orchestrator 路由用)"""

    agent_name: str
    display_name: str
    description: str
    tool_descriptions: list[str] = field(default_factory=list)
