"""集中配置 -- 所有可调参数统一管理.

用法:
    from src.config import config
    model = config.llm_model
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Config:
    # ── LLM ─────────────────────────────────────────────────
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "deepseek-v4-flash")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    llm_temperature: float = 0.3
    llm_routing_temperature: float = 0.0  # Orchestrator 路由用低温

    # ── Agent ───────────────────────────────────────────────
    max_tool_calls_high: int = 2   # 置信度 ≥ 0.9
    max_tool_calls_med: int = 3    # 0.7 ~ 0.9
    max_tool_calls_low: int = 5    # < 0.7
    max_tool_calls_query: int = 1  # query 意图(纯查询,不需要工具)

    # ── Planner ─────────────────────────────────────────────
    planner_enabled: bool = os.getenv("PLANNER_ENABLED", "false").lower() == "true"

    # ── Memory ──────────────────────────────────────────────
    memory_enabled: bool = os.getenv("MEMORY_ENABLED", "false").lower() == "true"
    memory_window_size: int = int(os.getenv("MEMORY_WINDOW_SIZE", "5"))

    # ── RAG ─────────────────────────────────────────────────
    chunk_size: int = 500
    chunk_overlap: int = 80
    top_k_retrieval: int = 10
    top_k_rerank: int = 3
    rag_cache_ttl_seconds: int = 60

    # ── Reranker ────────────────────────────────────────────
    rerank_enabled: bool = os.getenv("RERANK_ENABLED", "false").lower() == "true"
    rerank_model: str = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-base")
    rerank_top_k: int = int(os.getenv("RERANK_TOP_K", "3"))
    rerank_retrieval_k: int = int(os.getenv("RERANK_RETRIEVAL_K", "20"))
    rerank_backend: str = os.getenv("RERANK_BACKEND", "cross-encoder")

    # ── 知识库注册表 ─────────────────────────────────────────
    kb_registry: list[dict[str, Any]] = field(default_factory=lambda: [
        {"name": "hr_kb",      "dir": "data/hr/",      "agent_key": "hr_agent",      "agent_name": "HR 专家",    "tools_import": "HR_TOOLS"},
        {"name": "it_kb",      "dir": "data/it/",      "agent_key": "it_agent",      "agent_name": "IT 专家",    "tools_import": "IT_TOOLS"},
        {"name": "legal_kb",   "dir": "data/legal/",   "agent_key": "legal_agent",   "agent_name": "法务专家",   "tools_import": "LEGAL_TOOLS"},
        {"name": "finance_kb", "dir": "data/finance/", "agent_key": "finance_agent", "agent_name": "财务专家",   "tools_import": "FINANCE_TOOLS"},
    ])

    # ── 领域关键词(路由 + Planner 共用,单一数据源)──────────
    # key = agent_key,value = 触发关键词列表
    # Orchestrator 和 Planner 都从这里引用,新增领域只需改此处
    domain_keywords: dict[str, list[str]] = field(default_factory=lambda: {
        "hr_agent": [
            "请假", "年假", "病假", "事假", "调休", "考勤", "打卡", "迟到",
            "早退", "加班", "薪酬", "社保", "公积金", "入职", "离职",
            "转正", "绩效", "福利", "培训", "晋升", "调岗", "产假",
            "陪产假", "婚假", "丧假", "哺乳假", "工龄", "审批", "待审批",
            "审批列表", "审批进度", "审批通过", "驳回申请",
        ],
        "it_agent": [
            "报修", "工单", "蓝屏", "卡顿", "死机", "坏了", "修", "笔记本",
            "电脑", "打印机", "网络", "wifi", "WiFi", "vpn", "VPN", "密码",
            "账号", "锁", "登录", "软件", "安装", "卸载", "设备", "申领",
            "鼠标", "键盘", "显示器", "邮箱", "outlook", "Outlook", "office",
            "Office", "系统", "重装", "中毒", "病毒", "U盘", "硬盘", "内存",
        ],
        "legal_agent": [
            "合同", "合规", "法律", "法务", "法规", "条款", "协议", "保密",
            "竞业", "知识产权", "专利", "商标", "版权", "数据保护", "个人信息",
            "隐私", "GDPR", "侵权", "仲裁", "诉讼", "违约", "审批流程",
        ],
        "finance_agent": [
            "报销", "发票", "出差", "差旅", "预算", "薪资", "工资条", "个税",
            "社保比例", "公积金", "采购", "招标", "比价", "招待费", "住宿标准",
            "餐饮补助", "财务", "费用", "支出", "决算",
        ],
    })

    # ── 路径 ─────────────────────────────────────────────────
    frontend_dir: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"
    )

    # ── CORS ────────────────────────────────────────────────
    cors_origins: list[str] = field(default_factory=lambda: [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8080").split(",")
    ])

    # ── Observability ───────────────────────────────────────
    trace_enabled: bool = os.getenv("TRACE_ENABLED", "true").lower() == "true"
    trace_output_dir: str = os.getenv("TRACE_OUTPUT_DIR", "traces/")

    # ── API ─────────────────────────────────────────────────
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8080"))

    # ── 安全 ─────────────────────────────────────────────────
    chat_history_window: int = int(os.getenv("CHAT_HISTORY_WINDOW", "10"))  # 传给 LLM 的最大轮数
    debug_mode: bool = os.getenv("DEBUG", "false").lower() == "true"
    app_env: str = os.getenv("APP_ENV", "dev")  # dev | production


config = _Config()


# 生产环境启动前校验
if config.app_env == "production":
    _missing = []
    if not os.getenv("JWT_SECRET") or os.getenv("JWT_SECRET") == "dev-secret-change-in-production-32b":
        _missing.append("JWT_SECRET(不能使用默认值)")
    if not os.getenv("LLM_API_KEY"):
        _missing.append("LLM_API_KEY")
    if _missing:
        raise RuntimeError(
            f"生产环境缺少必要配置: {', '.join(_missing)}.请设置环境变量后重试."
        )
