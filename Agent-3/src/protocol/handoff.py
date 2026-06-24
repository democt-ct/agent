from __future__ import annotations

from src.protocol.types import AgentResponse


def build_handoff(
    from_agent: str,
    response: AgentResponse,
    shared_context: dict | None = None,
) -> dict:
    """用上一个 Agent 的输出构造交割上下文,传给下一个 Agent.

    交割消息格式(对齐 PRD §3.2.1):
    {
        "from_agent": "hr_agent",
        "context": { "query": "...", "already_answered": [...] },
        "summary": "已处理部分的摘要",
        "handoff_type": "chain"   # single | chain | parallel
    }

    Args:
        from_agent: 来源 Agent 名称.
        response: 该 Agent 的返回结果.
        shared_context: 跨 Agent 共享的上下文(用户 ID,原始 query 等).

    Returns:
        交割上下文字典,传给下一个 Agent 的 handoff_context.
    """
    already_answered = []
    if response.tool_calls:
        already_answered = [
            {"tool": tc.get("name", ""), "result": tc.get("result", "")}
            for tc in response.tool_calls
        ]

    return {
        "from_agent": from_agent,
        "context": {
            "query": (shared_context or {}).get("query", ""),
            "already_answered": already_answered,
            **(shared_context or {}),
        },
        "summary": response.answer,
        "status": response.status,
        "handoff_type": "chain",
    }


def merge_results(responses: list[AgentResponse]) -> str:
    """汇总多个 Agent 的回答,输出给用户的最终文本.

    Args:
        responses: 按执行顺序排列的 Agent 返回列表.

    Returns:
        格式化的最终回答文本.
    """
    if not responses:
        return "抱歉,没有获取到任何回答."

    if len(responses) == 1:
        return responses[0].answer

    parts: list[str] = []
    for r in responses:
        icon = {
            "hr_agent": "🏥",
            "it_agent": "💻",
            "legal_agent": "⚖️",
        }.get(r.agent_name, "🤖")
        status_tag = {
            "success": "✅",
            "partial": "⚠️",
            "failed": "❌",
        }.get(r.status, "")
        header = f"{icon} **{r.agent_name}** {status_tag}"
        parts.append(f"{header}\n{r.answer}")

    return "\n\n---\n\n".join(parts)
