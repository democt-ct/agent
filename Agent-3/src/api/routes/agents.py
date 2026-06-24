"""Agent 信息 + 健康检查 API."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

from src.agents.orchestrator import AGENT_REGISTRY
from src.api.models.schemas import AgentInfo, HealthStatus

logger = logging.getLogger(__name__)
router = APIRouter(tags=["agents"])


def _get_state(request: Request) -> Any:
    return request.app.state.app_state


@router.get("/agents", response_model=list[AgentInfo])
async def list_agents(request: Request) -> list[AgentInfo]:
    """返回所有可用的 Agent 及其能力描述."""
    return [
        AgentInfo(
            name=name,
            display_name=reg.display_name,
            description=reg.description,
            tools=reg.tool_descriptions,
        )
        for name, reg in AGENT_REGISTRY.items()
    ]


@router.get("/health", response_model=HealthStatus)
async def health_check(request: Request) -> HealthStatus:
    """健康检查 -- 返回服务状态,Agent 数量,知识库数量,初始化进度."""
    state = _get_state(request)

    agents = [
        AgentInfo(
            name=name,
            display_name=reg.display_name,
            description=reg.description,
            tools=reg.tool_descriptions,
        )
        for name, reg in AGENT_REGISTRY.items()
    ]

    if state is None:
        return HealthStatus(status="error", agents=agents, kb_count=0)

    ready = state.ready.is_set()
    orchestrator_ok = state.orchestrator is not None

    # 真健康检查:DB + LLM 连通性
    components = {"db": "unknown", "llm": "unknown"}
    try:
        from src.tools.db.connection import get_db
        db = get_db()
        db.execute("SELECT 1")
        components["db"] = "ok"
    except Exception:
        components["db"] = "error"

    if state.orchestrator and state.orchestrator.client:
        try:
            state.orchestrator.client.models.list()
            components["llm"] = "ok"
        except Exception:
            components["llm"] = "error"

    phase = state.init_progress.get("phase", "")
    is_error = phase == "error"

    return HealthStatus(
        status="error" if is_error else ("ok" if ready and orchestrator_ok else "initializing"),
        agents=agents,
        kb_count=len(state.knowledge_bases),
        components=components,
        init_progress=None if ready else {
            "phase": phase,
            "kb_loaded": state.init_progress.get("kb_loaded", 0),
            "kb_total": state.init_progress.get("kb_total", 0),
            "kbs": state.init_progress.get("kbs", {}),
            "error": state.init_progress.get("error", ""),
        },
    )
