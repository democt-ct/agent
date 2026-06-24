from __future__ import annotations

import logging
import os
import sys

# 确保项目根在 import path 中(直接 python src/main.py 时也需要)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows 下强制 UTF-8 输出(支持 emoji)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

import click
from dotenv import load_dotenv

from src.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

load_dotenv()


@click.command()
@click.option(
    "--model",
    default=None,
    show_default=True,
    help="LLM 模型名称(默认从 LLM_MODEL 环境变量读取)",
)
def main(model: str | None) -> None:
    """企业多专家 Agent 系统 -- CLI 入口

    输入自然语言问题,系统自动路由到对应的专家 Agent 回答.
    """
    model = model or config.llm_model
    click.echo(click.style("=" * 56, fg="blue"))
    click.echo(
        click.style(
            "  🏢  企业多专家 Agent 系统 v0.1",
            fg="cyan",
            bold=True,
        )
    )
    click.echo(click.style("=" * 56, fg="blue"))
    click.echo()
    click.echo("  模型: " + model)
    click.echo("  输入 /help 查看帮助,/quit 退出")
    click.echo()

    # 初始化知识库 + Agent 系统
    system = _init_system(model)

    try:
        _repl(system)
    finally:
        for kb in system["kbs"].values():
            kb.stop_watch()


def _init_system(model: str) -> dict:
    """初始化整个系统:知识库 + LLM 客户端 + Orchestrator + Agent 实例.

    Returns:
        {"kbs": ..., "orchestrator": ..., "agents": {name: BaseAgent}}
    """
    import time

    from openai import OpenAI

    from src.agents.base_agent import BaseAgent
    from src.agents.orchestrator import AGENT_REGISTRY, Orchestrator
    from src.config import config
    from src.protocol.types import AgentRequest
    from src.rag.embedder import Embedder
    from src.rag.knowledge_base import KnowledgeBase
    from src.tools.hr_tools import HR_TOOLS
    from src.tools.it_tools import IT_TOOLS
    from src.tools.legal_tools import LEGAL_TOOLS
    from src.tools.finance_tools import FINANCE_TOOLS
    from src.tools.general_tools import GENERAL_TOOLS
    from src.tools.db import bootstrap_company_workspace

    bootstrap_company_workspace()

    from src.llm_client import get_client
    client = get_client()
    orchestrator = Orchestrator(client)

    # Planner(如果配置开关打开)
    planner = None
    if config.planner_enabled:
        from src.agents.planner import Planner
        planner = Planner(client, model=model)
        click.echo(click.style("  📋 Planner 就绪", fg="cyan"))

    # ── Memory ──────────────────────────────────────────────
    from src.memory.conversation_store import ConversationStore
    from src.memory.long_term import LongTermMemory

    conversation_store = ConversationStore()
    long_term_memory = LongTermMemory()
    click.echo(click.style("  🧠 Memory (L2 + L3) 就绪", fg="cyan"))

    # ── 知识库 ──────────────────────────────────────────────
    click.echo(click.style("  📚 初始化知识库...", fg="cyan"))
    t0 = time.time()
    embedder = Embedder()

    kbs: dict = {}
    for kb_spec in config.kb_registry:
        name, docs_dir = kb_spec["name"], kb_spec["dir"]
        kb = KnowledgeBase(name, docs_dir, embedder=embedder)
        if os.path.exists(kb._metadata_path()):
            kb.load_index()
            click.echo(f"    {name}: 已加载索引")
        else:
            kb.build_index()
            click.echo(f"    {name}: 索引构建完成")
        kb.watch()
        kbs[name] = kb
    click.echo(f"    耗时 {time.time() - t0:.1f}s")

    # ── Agent 实例 ──────────────────────────────────────────
    click.echo(click.style("  🤖 初始化 Agent...", fg="cyan"))

    tool_map = {"HR_TOOLS": HR_TOOLS, "IT_TOOLS": IT_TOOLS, "LEGAL_TOOLS": LEGAL_TOOLS, "FINANCE_TOOLS": FINANCE_TOOLS}
    agents: dict = {}
    for kb_spec in config.kb_registry:
        tool_list = tool_map[kb_spec["tools_import"]]
        kb = kbs[kb_spec["name"]]
        agent = BaseAgent(
            name=kb_spec["agent_name"],
            tools=tool_list + GENERAL_TOOLS,
            kb=kb,
            client=client,
            model=model,
        )
        # 启用查询改写
        kb.set_rewriter(client, model)
        # 启用重排序(如果配置开关打开)
        if config.rerank_enabled:
            from src.rag.reranker import Reranker
            kb.set_reranker(Reranker(
                model_name=config.rerank_model,
                backend=config.rerank_backend,
            ))
        agents[kb_spec["agent_key"]] = agent

    for name, agent in agents.items():
        info = AGENT_REGISTRY.get(name)
        label = info.display_name if info else name
        click.echo(f"    {name}: {label} ({len(agent.tools)} 工具)")

    click.echo(click.style("  👀 文件监听已开启", fg="green"))
    click.echo()

    from src.memory.summary_compressor import SummaryCompressor
    compressor = SummaryCompressor(client)

    return {"kbs": kbs, "orchestrator": orchestrator, "agents": agents, "client": client, "planner": planner, "conversation_store": conversation_store, "long_term_memory": long_term_memory, "compressor": compressor}


def _build_request(query: str, route_result: dict, history: list, handoff_context: dict) -> "AgentRequest":
    from src.protocol.types import AgentRequest
    user_intent = route_result.get("intent", "action")
    if user_intent == "query":
        max_tool_calls, temperature = 1, 0.1
    else:
        conf = route_result.get("confidence", 0.8)
        max_tool_calls = 2 if conf >= 0.9 else (3 if conf >= 0.7 else 5)
        temperature = 0.5
    return AgentRequest(
        query=query,
        agent_name=route_result["primary"],
        conversation_history=history,
        handoff_context=handoff_context or None,
        max_tool_calls=max_tool_calls,
        temperature=temperature,
        intent=user_intent,
    )


def _repl(system: dict) -> None:
    """交互式 REPL 循环"""
    from src.agents.orchestrator import AGENT_REGISTRY

    orchestrator = system["orchestrator"]
    agents = system["agents"]
    conversation_store = system.get("conversation_store")
    long_term_memory = system.get("long_term_memory")
    compressor = system.get("compressor")
    history: list[dict] = []
    session_id = "cli_session"
    user_id = "cli_user"

    while True:
        try:
            query = click.prompt(click.style("你", fg="green", bold=True), prompt_suffix=" > ")
        except (EOFError, KeyboardInterrupt):
            click.echo()
            break

        if not query.strip():
            continue
        if query.strip().lower() in ("/quit", "/exit", "/q"):
            break
        if query.strip().lower() == "/help":
            _show_help()
            continue
        if query.strip().lower() == "/clear":
            history.clear()
            click.echo(click.style("对话历史已清空.", fg="yellow"))
            continue

        route_result = orchestrator.route(query)
        agent_name = route_result["primary"]
        agent = agents.get(agent_name)

        if agent is None:
            info = AGENT_REGISTRY.get(agent_name)
            label = info.display_name if info else agent_name
            click.echo()
            click.echo(click.style(f"  ⚠️  {label} 尚未接入,请等待后续更新.", fg="yellow"))
            click.echo()
            continue

        click.echo()
        click.echo(click.style(
            f"  🧭 路由 → {agent_name} (置信度 {route_result['confidence']:.0%} · {route_result['method']})",
            fg="cyan",
        ))

        # 注入长期记忆
        handoff_context: dict = {}
        if long_term_memory:
            try:
                memory_text = long_term_memory.recall_as_context(user_id, limit=5)
                if memory_text:
                    handoff_context["profile"] = memory_text
            except Exception:
                pass

        # 保存用户消息 + 按需压缩
        if conversation_store:
            try:
                conversation_store.save(session_id, user_id, "user", query)
                if compressor and len(history) > 16 and compressor.should_compress(conversation_store, session_id):
                    compressor.compress(conversation_store, session_id)
            except Exception:
                pass

        request = _build_request(query, route_result, history, handoff_context)
        response = agent.run(request)

        icon = {"hr_agent": "🏥", "it_agent": "💻", "legal_agent": "⚖️", "finance_agent": "💰"}.get(agent_name, "🤖")
        click.echo()
        click.echo(click.style(f"  {icon} {response.agent_name}:", fg="white", bold=True))
        click.echo(f"  {response.answer}")
        click.echo()
        click.echo(click.style(
            f"  ⏱ {response.processing_time_ms}ms  ·  "
            f"🔍 {len(response.retrieved_chunks)} chunks  ·  "
            f"🪛 {len(response.tool_calls)} tools  ·  "
            f"🪙 {response.tokens_used} tokens",
            fg="bright_black",
        ))
        click.echo()

        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": response.answer})

        if conversation_store:
            try:
                conversation_store.save(session_id, user_id, "assistant", response.answer)
            except Exception:
                pass
        user_intent = route_result.get("intent", "action")
        if long_term_memory and user_intent == "action" and response.status == "success":
            try:
                long_term_memory.extract_from_workflow(
                    user_id, session_id,
                    {"query": query, "agent": agent_name,
                     "tool_calls": response.tool_calls, "answer": response.answer[:200]},
                )
            except Exception:
                pass


def _show_help() -> None:
    """显示帮助信息"""
    help_text = f"""
{click.style("可用命令", fg="cyan", bold=True)}:
  /help, /h    显示此帮助
  /clear        清空对话历史
  /quit, /exit  退出系统

{click.style("使用说明", fg="cyan", bold=True)}:
  直接输入你的问题,系统会自动判断领域并路由到对应专家.

{click.style("支持的领域", fg="cyan", bold=True)}:
  🏥 HR 专家    -- 人事制度,考勤,请假,薪酬福利
  💻 IT 专家    -- 设备申领,报修,软件安装,密码
  ⚖️ 法务专家   -- 合规,合同,数据保护
  💰 财务专家   -- 报销,预算,出差标准,采购流程
"""
    click.echo(help_text)


@click.group()
def cli() -> None:
    """企业多专家 Agent 系统"""
    pass


cli.add_command(main, name="cli")


@click.command()
@click.option("--host", default=config.api_host, show_default=True, help="监听地址")
@click.option("--port", default=config.api_port, show_default=True, help="监听端口")
@click.option("--reload/--no-reload", default=True, help="是否启用热重载")
def serve(host: str, port: int, reload: bool) -> None:
    """启动 FastAPI Web 服务"""
    import uvicorn
    click.echo(click.style(f"  🌐 FastAPI 服务启动: http://{host}:{port}", fg="green"))
    uvicorn.run("src.api.app:app", host=host, port=port, reload=reload)


cli.add_command(serve, name="serve")

if __name__ == "__main__":
    sys.exit(cli())
