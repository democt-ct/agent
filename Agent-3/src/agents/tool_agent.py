"""Tool Agent -- 统一工具调用入口.

所有 Agent 的工具调用统一走此入口:
  1. 查 ToolDef.permission → 对比 SessionContext 做权限校验
  2. 写入 audit_log
  3. 执行 tool.implementation
  4. 返回 ToolResult

替代 BaseAgent 内直接调 implementation 的做法.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from src.tools.base import ToolDef

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """工具执行结果."""

    tool_name: str
    success: bool
    data: Any = None                # 工具返回的 dict
    error: str | None = None        # 错误信息
    audit_id: str | None = None     # audit_log 记录 ID
    elapsed_ms: int = 0
    permission_denied: bool = False


class ToolAgent:
    """统一工具执行入口.

    Usage:
        agent = ToolAgent()
        result = agent.execute(tool_def, arguments, session_ctx)
    """

    def __init__(self, audit_enabled: bool = True) -> None:
        self.audit_enabled = audit_enabled

    # user_id 类参数名 -- 非 admin 角色强制覆盖为 session 值
    USER_ID_PARAMS: set[str] = {"user_id", "applicant_id", "employee_id"}

    def execute(
        self,
        tool_def: ToolDef,
        arguments: dict[str, Any],
        session_ctx: Any = None,   # SessionContext from auth middleware
    ) -> ToolResult:
        """执行工具,完成参数净化,权限校验和审计.

        Args:
            tool_def: 工具定义(含 permission 配置)
            arguments: 工具参数
            session_ctx: 当前用户 SessionContext(可为 None 表示跳过权限检查)
        """
        t0 = time.perf_counter()

        # ── 0. 参数净化:非 admin 角色强制绑定 user_id ──────────
        arguments = self._sanitize_args(arguments, session_ctx)

        # ── 1. 权限校验 ──────────────────────────────────────────
        if session_ctx is not None and tool_def.permission is not None:
            perm = tool_def.permission
            required_roles = perm.get("roles", [])
            scope = perm.get("scope", "tenant")

            # 角色检查
            if required_roles and session_ctx.role not in required_roles:
                return ToolResult(
                    tool_name=tool_def.name,
                    success=False,
                    error=f"权限不足: {tool_def.name} 需要角色 {required_roles},当前角色 {session_ctx.role}",
                    permission_denied=True,
                    elapsed_ms=int((time.perf_counter() - t0) * 1000),
                )

            # scope=self: 强制注入当前用户的 user_id
            if scope == "self" and "user_id" in arguments:
                if arguments["user_id"] != session_ctx.user_id:
                    if session_ctx.role not in ("hr", "admin"):
                        return ToolResult(
                            tool_name=tool_def.name,
                            success=False,
                            error=f"无权操作其他用户的数据 (scope=self, 尝试访问 {arguments['user_id']})",
                            permission_denied=True,
                            elapsed_ms=int((time.perf_counter() - t0) * 1000),
                        )

            # approver_id 必须等于当前用户(防止 LLM 伪造审批人身份)
            if "approver_id" in arguments:
                if arguments["approver_id"] != session_ctx.user_id:
                    if session_ctx.role not in ("hr", "admin"):
                        return ToolResult(
                            tool_name=tool_def.name,
                            success=False,
                            error=f"审批人身份不匹配: 参数为 {arguments['approver_id']},当前用户为 {session_ctx.user_id}",
                            permission_denied=True,
                            elapsed_ms=int((time.perf_counter() - t0) * 1000),
                        )

        # ── 2. 执行 ──────────────────────────────────────────────
        try:
            result_data = tool_def.implementation(**arguments)
            success = isinstance(result_data, dict) and "error" not in result_data
        except Exception as e:
            logger.exception("Tool %s execution failed", tool_def.name)
            result_data = {"error": str(e)}
            success = False

        elapsed = int((time.perf_counter() - t0) * 1000)

        # ── 3. 审计日志 ──────────────────────────────────────────
        audit_id = None
        if tool_def.audit and self.audit_enabled:
            audit_id = self._write_audit(
                tool_name=tool_def.name,
                arguments=arguments,
                success=success,
                user_id=session_ctx.user_id if session_ctx else "anonymous",
                elapsed_ms=elapsed,
            )

        return ToolResult(
            tool_name=tool_def.name,
            success=success,
            data=result_data,
            error=result_data.get("error") if isinstance(result_data, dict) else None,
            audit_id=audit_id,
            elapsed_ms=elapsed,
        )

    def _sanitize_args(self, tool_args: dict[str, Any], session_ctx: Any) -> dict[str, Any]:
        """参数净化:非 admin 角色强制将 user_id 类参数覆盖为 session 值.

        防止 LLM prompt injection 篡改 user_id 越权操作他人数据.
        """
        if session_ctx is None:
            return tool_args
        if getattr(session_ctx, "role", "") in ("admin",):
            return tool_args
        args = dict(tool_args)
        for key in self.USER_ID_PARAMS:
            if key in args and hasattr(session_ctx, "user_id"):
                args[key] = session_ctx.user_id
        # 同样保护 approver_id,防止伪造审批人身份
        if "approver_id" in args and hasattr(session_ctx, "user_id"):
            if getattr(session_ctx, "role", "") not in ("hr", "admin"):
                args["approver_id"] = session_ctx.user_id
        return args

    def _write_audit(
        self, tool_name: str, arguments: dict, success: bool,
        user_id: str, elapsed_ms: int,
    ) -> str | None:
        """写入审计日志到 audit_log 表."""
        import uuid
        import json
        from datetime import datetime, timezone
        from src.tools.db import get_db

        audit_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        detail = json.dumps({"arguments": arguments, "success": success, "elapsed_ms": elapsed_ms}, ensure_ascii=False)
        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO audit_log (id, user_id, action, resource, detail, created_at) VALUES (?, ?, 'tool_call', ?, ?, ?)",
                    (audit_id, user_id, tool_name, detail, now),
                )
                conn.commit()
        except Exception as e:
            logger.warning("Failed to write audit log: %s", e)
            return None
        return audit_id


# ── 便捷工厂 ──────────────────────────────────────────────────────

_tool_agent_instance: ToolAgent | None = None


def get_tool_agent() -> ToolAgent:
    """获取全局单例 ToolAgent."""
    global _tool_agent_instance
    if _tool_agent_instance is None:
        _tool_agent_instance = ToolAgent()
    return _tool_agent_instance
