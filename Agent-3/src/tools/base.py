from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolDef:
    """工具定义.

    Attributes:
        name: 工具名称(LLM 调用时使用的函数名).
        description: 工具描述(LLM 判断是否调用此工具的依据).
        parameters: JSON Schema 格式的参数定义.
        implementation: 实际执行的 Python 函数.
        permission: 权限配置(谁可以调用,数据范围).
        audit: 是否记录审计日志.
        quick_triggers: 快速查询触发关键词列表,命中时跳过 LLM 直接调工具.
        quick_args_builder: 快速查询参数构造函数 (session_ctx) → dict.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    implementation: Callable[..., Any]
    permission: dict[str, Any] | None = None
    # permission 格式: {"roles": ["employee","manager","hr"], "scope": "self"}
    # scope: "self" | "department" | "tenant"
    audit: bool = True
    quick_triggers: list[str] = field(default_factory=list)
    quick_args_builder: Callable[..., dict] | None = None

    def to_openai_format(self) -> dict[str, Any]:
        """转换为 OpenAI function calling 格式."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
