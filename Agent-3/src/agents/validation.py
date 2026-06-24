"""LLM 输出校验 -- Pydantic schema 验证 + 自动重试.

解决 LLM 返回格式不符合预期的兜底问题.

Usage:
    from src.agents.validation import RouteResult, validate_route_result
    validated = validate_route_result(llm_json_string)
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

# ── 路由结果 Schema ────────────────────────────────────────────────

class RouteResult(BaseModel):
    """Orchestrator LLM 路由输出的 schema 校验."""
    primary: str = Field(default="fallback", description="主领域 agent_key")
    secondary: str | None = Field(default=None, description="次领域 agent_key")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="置信度 0-1")
    intent: str = Field(default="action", pattern=r"^(action|query)$")


# ── 工具调用参数校验 ──────────────────────────────────────────────

class ToolCallArgs(BaseModel):
    """通用工具调用参数校验 -- 确保 LLM 返回的参数结构正确."""
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


# ── 校验函数 ──────────────────────────────────────────────────────

def validate_route_result(raw: dict | str) -> dict:
    """校验并归一化路由结果.

    Args:
        raw: LLM 返回的 JSON dict 或字符串

    Returns:
        校验后的 dict,字段不合法时用默认值填充.
    """
    if isinstance(raw, str):
        try:
            import json
            raw = json.loads(raw)
        except Exception:
            logger.warning("Route validation: JSON parse failed, using fallback")
            return {"primary": "fallback", "secondary": None, "confidence": 0.0, "intent": "action"}

    try:
        validated = RouteResult(**raw)
        return {
            "primary": validated.primary,
            "secondary": validated.secondary,
            "confidence": validated.confidence,
            "intent": validated.intent,
        }
    except ValidationError as e:
        logger.warning("Route validation failed: %s -- raw=%s", e.errors(), str(raw)[:200])
        # 降级:保留 primary 如果可以,否则 fallback
        primary = raw.get("primary", "fallback") if isinstance(raw, dict) else "fallback"
        return {
            "primary": primary,
            "secondary": None,
            "confidence": 0.3,
            "intent": "action",
        }


def validate_tool_args(raw_args: str | dict) -> dict:
    """校验 LLM function call 的 arguments.

    Args:
        raw_args: JSON 字符串或 dict

    Returns:
        校验后的 dict,JSON 解析失败返回 {}.
    """
    if isinstance(raw_args, dict):
        return raw_args
    try:
        import json
        parsed = json.loads(raw_args)
        if isinstance(parsed, dict):
            return parsed
        return {}
    except (json.JSONDecodeError, TypeError):
        logger.warning("Tool args parse failed: %s", str(raw_args)[:100])
        return {}
