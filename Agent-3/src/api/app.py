"""FastAPI 应用入口.

启动方式:
    python -m src.api.app
    或
    uvicorn src.api.app:app --reload
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv

# 确保项目根在 import path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("api")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routes import chat, agents, sessions
from src.config import config

# ── 预热导入:避免 daemon 线程冷加载耗时 ────────────────────
from src.tools.db import bootstrap_company_workspace
from src.agents.base_agent import BaseAgent
from src.agents.orchestrator import Orchestrator
from src.rag.embedder import Embedder
from src.rag.knowledge_base import KnowledgeBase
from src.tools.hr_tools import HR_TOOLS
from src.tools.it_tools import IT_TOOLS
from src.tools.legal_tools import LEGAL_TOOLS
from src.tools.finance_tools import FINANCE_TOOLS
from src.tools.general_tools import GENERAL_TOOLS
from src.llm_client import get_client
from src.rag.reranker import Reranker
from src.agents.tool_agent import ToolAgent
from src.agents.review_agent import ReviewAgent
from src.memory.conversation_store import ConversationStore
from src.memory.long_term import LongTermMemory
from src.agents.planner import Planner


# ── 全局应用状态 ──────────────────────────────────────────────

class AppState:
    """FastAPI 应用运行时状态,通过 request.app.state 访问."""

    def __init__(self) -> None:
        self.ready = threading.Event()
        self.init_progress: dict[str, object] = {
            "phase": "starting",
            "kb_loaded": 0,
            "kb_total": len(config.kb_registry),
            "kbs": {},
        }
        self.orchestrator = None
        self.planner = None
        self.review_agent = None
        self.conversation_store = None
        self.long_term_memory = None
        self.agent_instances: dict[str, object] = {}
        self.knowledge_bases: dict[str, object] = {}
        self.sessions: dict[str, list[dict]] = {}  # session_id → messages
        self.session_owners: dict[str, str] = {}   # session_id → user_id


def create_app() -> FastAPI:
    """工厂函数:创建并配置 FastAPI 应用."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """生命周期:后台初始化 Agent 引擎,不阻塞服务启动."""
        state = AppState()
        app.state.app_state = state

        # 后台线程并行初始化,不阻塞 yield
        init_thread = threading.Thread(
            target=_init_engine,
            args=(state,),
            daemon=True,
        )
        init_thread.start()
        logger.info("🌐 服务已启动,Agent 引擎后台初始化中...")
        yield
        _shutdown_engine(state)
        logger.info("👋 Agent 引擎已关闭")

    app = FastAPI(
        title="企业多专家 Agent 系统",
        description="多 Agent 协作 + RAG 知识库的企业智能助手 API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────
    origins = config.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Auth (JWT) ───────────────────────────────────────
    from src.gateway.middleware import AuthMiddleware
    app.add_middleware(AuthMiddleware)

    # ── Rate Limit ──────────────────────────────────────
    from src.gateway.rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)

    # ── Trace (observability) ─────────────────────────────
    from src.api.middleware.trace_middleware import TraceMiddleware
    app.add_middleware(TraceMiddleware)

    # ── 注册路由 ──────────────────────────────────────────
    from src.api.routes import auth as auth_routes
    from src.api.routes import leaves as leaves_routes
    from src.api.routes import approvals as approvals_routes
    from src.api.routes import applications as applications_routes
    from src.api.routes import admin as admin_routes
    from src.api.routes import attendance as attendance_routes
    from src.api.routes import expenses as expenses_routes
    from src.api.routes import notifications as notifications_routes
    from src.api.routes import traces as traces_routes
    from src.api.routes import tickets as tickets_routes
    app.include_router(auth_routes.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(agents.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    app.include_router(leaves_routes.router, prefix="/api")
    app.include_router(approvals_routes.router, prefix="/api")
    app.include_router(applications_routes.router, prefix="/api")
    app.include_router(admin_routes.router, prefix="/api")
    app.include_router(attendance_routes.router, prefix="/api")
    app.include_router(expenses_routes.router, prefix="/api")
    app.include_router(tickets_routes.router, prefix="/api")
    app.include_router(notifications_routes.router, prefix="/api")
    app.include_router(traces_routes.router, prefix="/api")

    # ── 开发时提供前端静态文件 ──────────────────────────
    frontend_path = config.frontend_dir
    if os.path.isdir(frontend_path):
        app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

    return app


# ── 引擎初始化 ──────────────────────────────────────────────

def _init_engine(state: AppState) -> None:
    """后台初始化知识库 + Agent 实例 + Orchestrator(并行加载 KB)."""
    import time
    import traceback
    t0 = time.time()

    logger.info("🔧 Agent 引擎初始化线程启动 (thread=%s)", threading.current_thread().name)
    try:
        _init_engine_impl(state, t0)
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("❌ Agent 引擎初始化失败:\n%s", tb)
        state.init_progress["phase"] = "error"
        state.init_progress["error"] = str(e)
        state.init_progress["traceback"] = tb
        # 不设置 ready,让路由继续返回 503


def _init_engine_impl(state: AppState, t0: float) -> None:
    """_init_engine 的实际实现,由 try/except 包裹."""
    import time  # elapsed 计算用

    # ── 阶段 0: 快速同步初始化 ──────────────────────────
    state.init_progress["phase"] = "bootstrap"
    bootstrap_company_workspace()
    logger.info("  🏢 企业工作空间就绪")

    try:
        client = get_client()
    except SystemExit as e:
        raise RuntimeError(
            "LLM_API_KEY 未配置,请在 .env 中设置 LLM_API_KEY."
        ) from e
    logger.info("  🤖 当前模型: %s (base_url: %s)", config.llm_model, config.llm_base_url)

    # 共享 Embedder
    embedder = Embedder()

    tool_map = {"HR_TOOLS": HR_TOOLS, "IT_TOOLS": IT_TOOLS, "LEGAL_TOOLS": LEGAL_TOOLS, "FINANCE_TOOLS": FINANCE_TOOLS}
    kb_configs = [
        (kb["name"], kb["dir"], tool_map[kb["tools_import"]], kb["agent_name"])
        for kb in config.kb_registry
    ]

    # ── 阶段 1: 串行加载所有 KB(ChromaDB 不支持并发 PersistentClient) ──
    state.init_progress["phase"] = "loading_kbs"
    total = len(kb_configs)

    for kb_name, docs_dir, tools_list, agent_name in kb_configs:
        try:
            kb = KnowledgeBase(kb_name, docs_dir, embedder=embedder)
            if kb.is_index_stale():
                kb.build_index()
                logger.info("  📚 %s: 索引构建完成", kb_name)
            else:
                kb.load_index()
                logger.info("  📚 %s: 已加载索引", kb_name)

            kb.watch()

            agent = BaseAgent(
                name=agent_name,
                tools=tools_list + GENERAL_TOOLS,
                kb=kb,
                client=client,
                model=config.llm_model,
            )

            kb.set_rewriter(client, config.llm_model)

            if config.rerank_enabled:
                kb.set_reranker(Reranker(
                    model_name=config.rerank_model,
                    backend=config.rerank_backend,
                ))
                logger.info("  🔄 %s: 重排序已启用 (%s)", kb_name, config.rerank_model)

            agent_key = kb_name.replace("_kb", "_agent")
            state.knowledge_bases[kb_name] = kb
            state.agent_instances[agent_key] = agent

            state.init_progress["kb_loaded"] = state.init_progress["kb_loaded"] + 1  # type: ignore[operator]
            state.init_progress["kbs"][kb_name] = "ready"  # type: ignore[index]
            logger.info(
                "  ✅ %s → %s (%d/%d)",
                kb_name, agent_name,
                state.init_progress["kb_loaded"], total,
            )
        except Exception as e:
            logger.error("  ❌ %s 加载失败: %s", kb_name, e)
            state.init_progress["kbs"][kb_name] = f"error: {e}"  # type: ignore[index]

    # ── 阶段 2: Orchestrator + 辅助模块 ──────────────────
    state.init_progress["phase"] = "orchestrator"
    state.orchestrator = Orchestrator(client, model=config.llm_model)
    logger.info("  🤖 Orchestrator 就绪")

    state.tool_agent = ToolAgent()
    state.review_agent = ReviewAgent(client=client, model=config.llm_model)
    logger.info("  🔍 Tool Agent + Review Agent 就绪")

    state.conversation_store = ConversationStore()
    state.long_term_memory = LongTermMemory()
    logger.info("  🧠 Memory (L2 + L3) 就绪")

    if config.planner_enabled:
        state.planner = Planner(client, model=config.llm_model)
        logger.info("  📋 Planner 就绪")
    else:
        state.planner = None

    # ── 完成:预加载 Embedding 模型,避免首条查询等待 ────
    state.init_progress["phase"] = "warming"
    logger.info("  🔥 预加载 Embedding 模型...")
    _ = embedder.model  # 触发 SentenceTransformer 懒加载
    state.init_progress["phase"] = "ready"
    state.ready.set()
    elapsed = time.time() - t0
    logger.info("🚀 Agent 引擎初始化完成 (%.1fs)", elapsed)


def _shutdown_engine(state: AppState) -> None:
    """关闭引擎:停止所有文件监听."""
    for kb in state.knowledge_bases.values():
        try:
            kb.stop_watch()
        except Exception:
            pass
    state.agent_instances.clear()
    state.knowledge_bases.clear()


# ── 快捷入口 ──────────────────────────────────────────────

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.app:app", host=config.api_host, port=config.api_port, reload=False)
