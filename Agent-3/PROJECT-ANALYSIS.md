# 企业多专家 Agent 系统 — 项目分析文档

> 分析日期: 2025-07-16  
> 版本: v0.1.0  
> 类型: 教学项目 + 求职作品集

---

## 目录

1. [项目概览](#1-项目概览)
2. [系统架构](#2-系统架构)
3. [模块实现详解](#3-模块实现详解)
4. [数据流与关键路径](#4-数据流与关键路径)
5. [API 接口清单](#5-api-接口清单)
6. [已实现功能清单](#6-已实现功能清单)
7. [发现的问题](#7-发现的问题)
8. [技术债务与改进建议](#8-技术债务与改进建议)

---

## 1. 项目概览

### 1.1 项目定位

企业内部多专家 Agent 系统，将分散的知识（HR 政策、IT 运维、法务合规、财务报销）整合为 4 个独立的 RAG Agent，由 Orchestrator 统一路由调度。员工用自然语言提问，系统自动路由到对应专家回答。

### 1.2 核心数字

| 维度 | 数值 |
|------|------|
| Agent 数量 | 5 个（Orchestrator + HR/IT/法务/财务） |
| 知识库 | 4 个（hr_kb / it_kb / legal_kb / finance_kb） |
| 文档总数 | 20 份 Markdown（每个知识库 5 份） |
| 工具总数 | 18 个（HR 8 + IT 3 + 法务 2 + 财务 5） |
| API 端点 | 12+ 个 REST + 1 个 SSE 流 |
| 数据库表 | 12 张企业核心表 |
| 源代码文件 | ~50 个 Python 模块 |
| Python 行数 | ~7,000+ 行 |

### 1.3 技术选型

| 层 | 选择 | 备注 |
|----|------|------|
| 语言 | Python ≥3.11 | |
| LLM | DeepSeek API (deepseek-v4-flash) | OpenAI 兼容客户端 |
| Embedding | BAAI/bge-large-zh-v1.5 (1024d) | 本地运行，ModelScope 加速下载 |
| 向量库 | Chroma (PersistentClient) | 本地零配置 |
| 重排序 | BAAI/bge-reranker-base (cross-encoder) / Cohere Rerank API | 可选开关 |
| BM25 | rank-bm25 + jieba 分词 | 混合检索 |
| Agent 框架 | 手写 ReAct + LangGraph | 核心逻辑可见 |
| 前端 | 原生 HTML/CSS/JS (SPA) | 现代化聊天界面 |
| API 框架 | FastAPI + SSE | 支持流式输出 |
| 数据库 | SQLite (WAL 模式) | 零配置持久化 |
| 测试 | pytest + 自建评估框架 | |
| 文件监听 | watchdog | 知识库热更新 |
| Web 服务 | uvicorn | ASGI server |

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────┐
│                    用户界面层                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  CLI (Click) │  │  FastAPI     │  │ 前端 SPA  │ │
│  │  REPL 交互    │  │  REST + SSE  │  │ HTML/JS   │ │
│  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘ │
└─────────┼──────────────────┼───────────────┼───────┘
          │                  │               │
          ▼                  ▼               ▼
┌─────────────────────────────────────────────────────┐
│                  网关层 (Gateway)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ JWT Auth │  │ 限流     │  │ Trace Collector  │  │
│  │ Middleware│  │ 令牌桶   │  │ (可观测性)       │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│                 Orchestrator (路由中枢)               │
│                                                     │
│  query → ① 寒暄检测 (regex)                         │
│       → ② 关键词匹配 (80+ 关键词 × 4 领域)           │
│       → ③ LLM 路由 (JSON structured output)          │
│       → {primary, secondary, confidence, intent}     │
└──┬────────┬────────┬────────┬──────────────────────┘
   │        │        │        │
   ▼        ▼        ▼        ▼
┌──────┐┌──────┐┌──────┐┌──────────┐
│  HR   ││  IT   ││ 法务 ││  财务     │
│ Agent ││ Agent ││Agent ││  Agent   │
│       ││       ││      ││          │
│ 8工具  ││ 3工具  ││ 2工具 ││ 5 工具    │
│ RAG   ││ RAG   ││ RAG  ││ RAG+Mock │
└──┬────┘└──┬────┘└──┬───┘└────┬─────┘
   │        │        │         │
   ▼        ▼        ▼         ▼
┌─────────────────────────────────────────────────────┐
│                   RAG 管线 (每个 Agent 独立)          │
│                                                     │
│  文档 → 加载 → 分块 → Embedding → Chroma             │
│                                          ↕           │
│  用户提问 → 查询改写 → 混合检索 → 重排序 → LLM 生成   │
│              (LLM)    (向量+BM25)  (cross-encoder)    │
└─────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│                 基础设施层                            │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────┐  │
│  │ SQLite  │ │ Planner │ │ Review   │ │ Tool    │  │
│  │ 12 表    │ │ DAG 规划 │ │ 审查 Agent│ │ Agent   │  │
│  └─────────┘ └─────────┘ └──────────┘ └─────────┘  │
│  ┌─────────┐ ┌───────────┐ ┌──────────┐            │
│  │ Memory  │ │ Workflow  │ │ EventBus │            │
│  │ L2+L3   │ │ Engine    │ │ 发布订阅  │            │
│  └─────────┘ └───────────┘ └──────────┘            │
└─────────────────────────────────────────────────────┘
```

### 2.2 目录结构

```
enterprise-multi-agent/
├── src/
│   ├── main.py              # CLI 入口 (Click)
│   ├── config.py            # 集中配置 (dataclass)
│   ├── llm_client.py        # LLM 客户端工厂
│   ├── protocol/            # 协议层
│   │   ├── types.py         # AgentRequest / AgentResponse / AgentRegistration
│   │   ├── handoff.py       # 跨 Agent 交割 + 结果合并
│   │   └── errors.py        # 异常体系 + 重试装饰器
│   ├── agents/              # Agent 实现
│   │   ├── base_agent.py    # ReAct 循环骨架
│   │   ├── orchestrator.py  # 三级路由引擎
│   │   ├── planner.py       # LLM DAG 任务规划
│   │   ├── review_agent.py  # 回答审查 (幻觉检测)
│   │   └── tool_agent.py    # 统一工具调用入口 (权限+审计)
│   ├── rag/                 # RAG 管线
│   │   ├── loader.py        # MD/PDF/TXT/DOCX 加载
│   │   ├── chunker.py       # RecursiveCharacter 分块
│   │   ├── embedder.py      # BGE-large-zh-v1.5 向量化
│   │   ├── retriever.py     # 向量 + BM25 混合检索 (RRF)
│   │   ├── reranker.py      # Cross-encoder / Cohere 重排序
│   │   ├── query_rewriter.py # LLM 查询改写
│   │   └── knowledge_base.py # 知识库统一接口 + 文件监听
│   ├── tools/               # 工具定义
│   │   ├── base.py          # ToolDef 数据类
│   │   ├── db.py            # SQLite 持久化层 (12 表 + 种子数据)
│   │   ├── hr_tools.py      # 8 个 HR 工具
│   │   ├── it_tools.py      # 3 个 IT 工具
│   │   ├── legal_tools.py   # 2 个法务工具
│   │   └── finance_tools.py # 5 个财务工具
│   ├── api/                 # FastAPI 层
│   │   ├── app.py           # 应用工厂 + 生命周期
│   │   ├── models/schemas.py # Pydantic 数据契约
│   │   ├── routes/          # chat / agents / auth / sessions / leaves / approvals
│   │   ├── service/chat_service.py # 对话编排服务
│   │   └── middleware/trace_middleware.py
│   ├── gateway/             # 网关层
│   │   ├── auth.py          # JWT 签发/验证
│   │   ├── middleware.py     # Auth 中间件
│   │   └── rate_limit.py    # 令牌桶限流
│   ├── workflow/            # 工作流引擎
│   │   ├── engine.py        # DAG 拓扑执行器
│   │   ├── state_machine.py # 请假/审批 FSM
│   │   └── event_bus.py     # 发布/订阅事件总线
│   ├── memory/              # 记忆系统
│   │   ├── conversation_store.py # L2 会话持久化 (SQLite)
│   │   ├── long_term.py     # L3 长期记忆
│   │   └── summary_compressor.py # LLM 上下文压缩
│   ├── evaluation/          # 评估体系
│   │   ├── models.py        # TestCase / EvalResult / EvalReport
│   │   ├── loader.py        # JSONL/JSON 测试集加载
│   │   └── runner.py        # 评估执行器
│   └── observability/       # 可观测性
│       ├── trace_models.py   # Trace / TraceEvent
│       └── trace_collector.py # JSONL trace 收集器
├── data/
│   ├── hr/     (5 份人事文档)
│   ├── it/     (5 份 IT 文档)
│   ├── legal/  (5 份法务文档)
│   ├── finance/(5 份财务文档)
│   └── eval/   (测试集 + 报告)
├── frontend/   (独立 SPA 前端)
│   ├── index.html
│   ├── app.js
│   └── style.css
├── scripts/    (测试/评估/种子数据脚本)
├── docs/       (设计文档)
└── tests/      (pytest 测试目录)
```

---

## 3. 模块实现详解

### 3.1 Protocol 层 (`src/protocol/`)

**三个核心数据结构：**

| 类型 | 用途 |
|------|------|
| `AgentRequest` | Orchestrator → Specialist Agent 的请求，含 query、历史、交割上下文、intent(query/action) |
| `AgentResponse` | Specialist → Orchestrator 的返回，含 answer、tool_calls、retrieved_chunks、reasoning |
| `AgentRegistration` | Agent 注册信息（display_name、description、tool_descriptions） |

**交割协议 (`handoff.py`)**：`build_handoff()` 从上一个 Agent 的 response 提取上下文，`merge_results()` 汇总多个 Agent 的回答为 Markdown 格式。

**异常体系 (`errors.py`)**：`AgentError → RetryableError / MaxRetriesExceeded / TimeoutError`，带指数退避 `@with_retry` 装饰器（max_retries=3, backoff=2.0）。

### 3.2 Agent 层 (`src/agents/`)

#### BaseAgent — ReAct 循环骨架

核心文件 [`src/agents/base_agent.py`](src/agents/base_agent.py:1)。

**双模式执行：**

| 模式 | intent | 特征 |
|------|--------|------|
| Query | `"query"` | 轻量提示词、top_k=3、单轮直接回答、不注入工具 |
| Action | `"action"` | 完整提示词、top_k=10、ReAct 循环（最多 N 次工具调用） |

**ReAct 循环流程：**
```
RAG 检索 → 构造 system prompt → messages=[system]+history+[user]
  → for _ in range(max_tool_calls):
       LLM 返回 content (无 tool_calls) → 结束，返回回答
       LLM 返回 tool_calls → _execute_tool → 结果塞回对话
  → 达到上限 → 强制生成最终回答
```

**支持 DeepSeek thinking mode**：回传 `reasoning_content` 字段，在 tool call 消息中也保留。

#### Orchestrator — 三级路由引擎

核心文件 [`src/agents/orchestrator.py`](src/agents/orchestrator.py:1)。

**路由链路（确定性优先）：**

| 层级 | 方法 | 说明 |
|------|------|------|
| ① 寒暄检测 | `_is_greeting()` | 5 个正则模式匹配"你好/谢谢/再见/你是谁/在吗" |
| ② 关键词匹配 | `_keyword_match()` | 80+ 关键词 × 4 领域，多命中时按数量+位置优先级 |
| ③ LLM 路由 | `_llm_route()` | temperature=0.0, JSON structured output |

**关键词多命中决策逻辑：**
- 只有一个领域命中 → 直接返回（confidence 按命中数/总关键词动态计算）
- 多个领域命中 → 命中数差异≥2倍 → 信任规则（第一领域）
- 多个领域命中数相近 → 按位置优先级（先提到的领域是主问题）

**意图检测 (`_detect_intent`)**：含操作动词（申请/提交/创建/审批…）→ `"action"`，否则 `"query"`。

#### Planner — LLM DAG 任务规划

核心文件 [`src/agents/planner.py`](src/agents/planner.py:1)。

将用户问题拆解为有依赖关系的子任务 DAG：
- 单领域简单问题 → 关键词 fast-path（不调 LLM）
- 跨领域/多步骤 → LLM 拆解为 SubTask 列表
- Kahn 拓扑排序 → 确定执行顺序
- 子任务 agent 类型：`retrieval` / `tool` / `memory` / `review`

#### Review Agent — 回答审查与幻觉检测

核心文件 [`src/agents/review_agent.py`](src/agents/review_agent.py:1)。

**五重检查：**
1. 数值一致性：回答中的数字是否和 tool_call 结果一致
2. 空回答检查：回答 < 10 字符视为无效
3. 错误透传检查：工具返回 error 但回答未体现
4. 编造检测：引用了不存在的制度条款
5. 制度溯源：`第X条`/`§X.Y` 是否能在 retrieved_chunks 中找到

#### Tool Agent — 统一工具调用入口

核心文件 [`src/agents/tool_agent.py`](src/agents/tool_agent.py:1)。

**职责：**
- 查 `ToolDef.permission` → 对比 `SessionContext` 做权限校验
- `scope=self` 强制注入当前用户 user_id
- `approver_id` 防止 LLM 伪造审批人身份
- 写入 audit_log 表
- 执行 tool.implementation
- 返回 ToolResult

### 3.3 RAG 管线 (`src/rag/`)

#### 检索流程

```
文档 (MD/PDF/TXT/DOCX)
  → loader.py:         加载为纯文本列表
  → chunker.py:        RecursiveCharacterTextSplitter (500 tokens, 80 overlap)
  → embedder.py:       BGE-large-zh-v1.5 (1024d) 向量化
  → knowledge_base.py: 写入 Chroma + 构建 BM25 索引

用户查询
  → query_rewriter.py: LLM 改写 (口语→书面)
  → retriever.py:      向量相似度 (Chroma) + BM25 (jieba 分词)
  → retriever.py:      RRF 融合 (k=10, bm25_weight=1.5)
  → reranker.py:       Cross-encoder 重排序 (可选)
  → 返回 top_k=3 给 Agent
```

#### 关键实现细节

| 组件 | 实现 |
|------|------|
| 混合检索 | 向量 (余弦相似度) + BM25 → RRF (Reciprocal Rank Fusion) |
| 查询改写 | LLM 将口语转书面（如"扣钱"→"扣款/处罚"） |
| 重排序 | 默认 cross-encoder (BAAI/bge-reranker-base)，失败回退到原顺序 |
| 文件监听 | watchdog 监听 docs_dir 变更，2s 防抖自动重建索引 |
| 缓存 | MD5 哈希的查询级缓存，TTL 60s |
| Embedding 下载 | ModelScope → HF 直连自动回退 |

### 3.4 工具层 (`src/tools/`)

#### 工具总览

| Agent | 工具数 | 工具列表 |
|-------|--------|---------|
| HR | 8 | get_leave_balance, submit_leave_request, get_org_chain, check_policy, approve_leave, reject_leave, get_approval_progress, get_pending_approvals |
| IT | 3 | check_ticket_status, create_ticket, check_device_inventory |
| 法务 | 2 | search_contract, check_compliance |
| 财务 | 5 | query_expense_policy, submit_expense_report, check_budget, query_salary_structure, check_travel_policy |

#### 数据库层 (`src/tools/db.py`)

12 张企业核心表：`departments`, `users`, `leave_records`, `approval_flow`, `task_state`, `expense_reports`, `budgets`, `audit_log`, `conversation_memory`, `long_term_memory`, `contracts`, `compliance_rules` + 2 张 v1 兼容表。

种子数据包含 4 个部门、4 个用户、5 种设备库存、2 个工单、5 份合同条款。

**审批流自动化：** 提交请假时，自动按天数分级构建审批链：
- ≤3 天 → 直属上级
- 3~7 天 → 直属上级 + 部门负责人
- >7 天 → 直属上级 + 部门负责人 + HR 总监

### 3.5 工作流层 (`src/workflow/`)

| 模块 | 职责 |
|------|------|
| `state_machine.py` | 请假/审批 FSM（严格状态转换校验，非法转换抛 InvalidStateTransition） |
| `engine.py` | DAG 拓扑执行器（Kahn 算法排序，逐节点执行，支持失败降级） |
| `event_bus.py` | 发布/订阅事件总线（内存实现，内置审批通知订阅者） |

**审批 FSM：**
```
leave_records:  draft → pending → approved → completed
                              → rejected
                              → cancelled
approval_flow:  pending → approved / rejected / skipped
```

### 3.6 网关层 (`src/gateway/`)

| 模块 | 实现 |
|------|------|
| JWT Auth | HS256 签名，24h 过期，种子用户密码统一 `123456` |
| Auth Middleware | 从 Bearer token 提取 JWT → 注入 `request.state.session` |
| Rate Limit | 双维度令牌桶（per-user 10rpm + per-IP 30rpm） |

### 3.7 记忆系统 (`src/memory/`)

| 层级 | 模块 | 存储 | 功能 |
|------|------|------|------|
| L2 (Episodic) | `conversation_store.py` | SQLite conversation_memory 表 | 会话持久化，7 天 TTL |
| L3 (Semantic) | `long_term.py` | SQLite long_term_memory 表 | 用户偏好、决策、事实 |
| 压缩 | `summary_compressor.py` | LLM 摘要 | 超过 20 条消息触发压缩 |

### 3.8 API 层 (`src/api/`)

FastAPI 应用工厂模式，支持：
- **同步对话** `POST /api/chat` — 完整回答 + 思维链元数据
- **SSE 流式** `GET /api/chat/stream` — 逐步推送 routing → retrieval → tool_call → reasoning → answer
- **认证** `POST /api/auth/login` / `GET /api/me`
- **Agent 信息** `GET /api/agents` / `GET /api/health`
- **会话管理** `GET /api/sessions` / `DELETE /api/sessions/{id}`
- **请假 CRUD** `GET/POST/PUT/DELETE /api/leaves`
- **审批操作** `GET /api/approvals/pending` / `POST /api/approvals/{step_id}/approve|reject`

### 3.9 前端 (`frontend/`)

独立 SPA（零构建工具），现代化聊天界面：
- 侧栏：用户登录面板（4 个种子用户切换）、新对话按钮、会话列表、请假记录入口、待审批入口
- 主区域：对话消息流（Markdown 渲染）、输入框（Enter 发送）
- 滑出面板：请假记录 CRUD、审批列表
- 弹窗：请假新建/编辑表单

### 3.10 可观测性 (`src/observability/`)

- Trace 收集器：per-request 的 Trace + TraceEvent
- JSONL 写入：按日期分文件 `traces/trace_YYYY-MM-DD.jsonl`
- 事件类型：routing / retrieval / tool_call / llm_call / answer / error

---

## 4. 数据流与关键路径

### 4.1 单 Agent 查询路径 (Query 模式)

```
用户: "年假还剩几天？"
  → Orchestrator.route()
    → 关键词匹配: ["年假"] → hr_agent, confidence=0.79
  → BaseAgent.run(intent="query")
    → RAG 检索 (top_k=3, 查询改写)
    → 轻量 prompt（角色 + 检索结果）
    → 单轮 LLM 调用 → 返回回答
  → ReviewAgent.review()
  → 保存到 ConversationStore + LongTermMemory
  → 返回给用户
```

### 4.2 单 Agent 操作路径 (Action 模式)

```
用户: "帮我请年假 6 月 1 号到 3 号"
  → Orchestrator.route()
    → 关键词匹配: ["请假", "年假"] → hr_agent, intent="action"
  → BaseAgent.run(intent="action")
    → RAG 检索 (top_k=10)
    → ReAct 循环:
        LLM → tool_call: check_policy(user_id, leave_type, ...)  → {allowed: true, ...}
        LLM → tool_call: submit_leave_request(user_id, ...)       → {success: true, request_id: "..."}
        LLM → content: "年假申请已提交，等待审批..."
    → 返回回答
  → ReviewAgent.review()
  → 保存会话
```

### 4.3 跨 Agent 串行交割路径

```
用户: "我请病假顺便笔记本报修"
  → Orchestrator.route()
    → 关键词匹配: ["请假", "病假", "报修"] → 多领域命中
    → primary=hr_agent, secondary=it_agent
  → HR Agent 执行 → 回答 (病假部分)
  → 构建 handoff_context {summary, from_agent}
  → IT Agent 执行 (含交割上下文) → 回答 (报修部分)
  → merge_results() → 汇总回答
  → 返回
```

### 4.4 Planner DAG 路径

```
用户: "请年假 6 月 1 号到 7 号，顺便报销出差费"
  → Planner.plan()
    → LLM DAG 拆解:
        t1: [memory]  查用户状态 + 余额
        t2: [retrieval] 查年假制度
        t3: [tool] 请假合规检查 (取决于 t1, t2)
        t4: [tool] 提交请假 (取决于 t3)
        t5: [tool] 提交报销 (独立)
        t6: [review] 审查结果 (取决于 t4, t5)
  → WorkflowEngine.run()
    → 拓扑排序: t1 → t2 → t3 → t4→t5 → t6
    → 逐节点执行
  → 返回
```

---

## 5. API 接口清单

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/auth/login` | ✗ | 登录获取 JWT |
| GET | `/api/me` | ✓ | 当前用户完整信息（含假期余额+汇报链+请假记录） |
| GET | `/api/me/leaves` | ✓ | 当前用户的请假记录列表 |
| POST | `/api/chat` | ✓ | 同步对话 |
| GET | `/api/chat/stream` | ✓ | SSE 流式对话 |
| GET | `/api/agents` | ✗ | 可用 Agent 列表 |
| GET | `/api/health` | ✗ | 健康检查 |
| GET | `/api/sessions` | ✓ | 用户会话列表 |
| GET | `/api/sessions/{id}` | ✓ | 会话详情 |
| DELETE | `/api/sessions/{id}` | ✓ | 删除会话 |
| GET | `/api/leaves` | ✓ | 请假列表（员工看自己，manager/hr 看下属） |
| GET | `/api/leaves/{id}` | ✓ | 请假详情 + 审批进度 |
| POST | `/api/leaves` | ✓ | 提交请假 |
| PUT | `/api/leaves/{id}` | ✓ | 编辑请假（仅 draft/pending + 本人） |
| DELETE | `/api/leaves/{id}` | ✓ | 取消请假（仅 pending + 本人） |
| GET | `/api/approvals/pending` | ✓ | 待审批列表 |
| POST | `/api/approvals/{step_id}/approve` | ✓ | 审批通过 |
| POST | `/api/approvals/{step_id}/reject` | ✓ | 驳回 |

---

## 6. 已实现功能清单

### ✅ 已完成 (PRD P0 + P1)

| ID | 功能 | 状态 |
|----|------|------|
| F1 | 用户输入自然语言，系统返回回答 | ✅ CLI + API + SSE |
| F2 | Orchestrator 三级路由（寒暄+关键词+LLM） | ✅ 含 intent 分类 |
| F3 | HR Agent 基于 RAG 回答人事政策 | ✅ 8 工具 + 审批流 |
| F4 | IT Agent 基于 RAG 回答 IT 问题 | ✅ 3 工具 |
| F5 | 法务 Agent 基于 RAG 回答合规问题 | ✅ 2 工具 |
| F6 | 每个 Agent 能调用工具 | ✅ 含权限+审计 |
| F7 | 每个 Agent 有独立 RAG 知识库 | ✅ 4 个知识库 |
| F8 | Orchestrator 跨 Agent 串行编排 | ✅ 含 handoff |
| F9 | RAG 混合检索 + 重排序 | ✅ 向量+BM25+RRF+cross-encoder |
| F10 | 对话历史记忆 | ✅ L2 (会话) + L3 (长期) |
| F11 | 前端 + 思维链可视化 | ✅ 独立 SPA + SSE 流 |
| F12 | 评估脚本 | ✅ JSONL 测试集 + 自动评分 |

### ➕ 额外实现（超出 PRD 范围）

| 功能 | 说明 |
|------|------|
| 财务 Agent | 第 4 个 Specialist Agent，5 个财务工具 |
| Planner DAG | LLM 任务拆解 + WorkflowEngine 拓扑执行 |
| Review Agent | 回答审查、数值一致性、幻觉检测 |
| Tool Agent | 统一工具调用入口，权限校验 + 审计日志 |
| JWT Auth | 用户认证 + SessionContext 注入 |
| Rate Limit | 双维度令牌桶限流 |
| FSM | 请假/审批状态机，严格状态转换校验 |
| Event Bus | 发布/订阅事件总线 |
| 文件热更新 | watchdog 监听知识库变更自动重建 |
| 查询改写 | LLM 口语→书面改写 |
| 上下文压缩 | 长会话 LLM 摘要压缩 |
| Trace 可观测性 | JSONL trace 收集 |
| 前端 SPA | 含用户切换、请假CRUD、审批面板 |
| SSE 流式 | 实时推送 routing → tool_call → reasoning → answer |

---

## 7. 发现的问题

### 🔴 高优先级

#### 7.1 Rate Limit 中间件存在重复 return 语句

**位置:** [`src/gateway/rate_limit.py:110-111`](src/gateway/rate_limit.py:110)

```python
if not path.startswith("/api"):
    return await call_next(request)
    return await call_next(request)  # ← 永远不会执行，死代码
```

**影响:** 第二条 return 语句不可达，代码逻辑不受影响但属于编码疏忽。

#### 7.2 会话数据在 API 重启后全部丢失

**位置:** [`src/api/app.py`](src/api/app.py) 中 `AppState.sessions` 使用内存 dict

**问题:** 虽然 ConversationStore 提供了 SQLite 持久化，但 API 启动时没有调用 `store.load_recent()` 恢复会话。重启后 `GET /api/sessions` 返回空列表。

**影响:** 前端会话列表在服务重启后丢失。

#### 7.3 上下文压缩未实际启用

**位置:** [`src/api/service/chat_service.py:208`](src/api/service/chat_service.py:208) `_try_compress()`

```python
def _try_compress(store: Any, session_id: str) -> None:
    # SummaryCompressor 需要 LLM client — 暂时跳过（需要注入 client）
    # 仅做消息计数日志
    count = store.count_messages(session_id)
    if count > 20:
        logger.info("Session %s has %d messages — compression recommended", session_id, count)
```

**影响:** 长会话窗口导致 token 成本持续增长，上下文窗口可能溢出。

#### 7.4 财务工具大部分为硬编码 Mock

**位置:** [`src/tools/finance_tools.py`](src/tools/finance_tools.py)

`query_expense_policy()`, `query_salary_structure()`, `check_travel_policy()` 返回硬编码数据，不查询数据库也不使用 RAG。

**影响:** 财务 Agent 的回答可能和知识库文档内容不一致。`query_salary_structure` 返回的个税起征点（5000元）等数据如果政策变更则无法自动更新。

#### 7.5 on_step 回调异常被静默吞掉

**位置:** [`src/agents/base_agent.py:94-100`](src/agents/base_agent.py:94) 等多处

```python
if on_step:
    try:
        on_step("retrieval", {...})
    except Exception:
        pass  # 静默吞掉所有异常
```

**影响:** SSE 流式推送或 trace 收集如果 on_step 出错，调试困难。

### 🟡 中优先级

#### 7.6 Embedding 模型与文档描述不一致

- `tech-stack.md` 和 `implementation-plan.md` 记录为 `text-embedding-3-small` (1536d)
- 实际代码使用 `BAAI/bge-large-zh-v1.5` (1024d)
- `config.py` 中 `dimension` 未定义，`embedder.py` 中 `dimension` property 返回 1024

**影响:** 文档和代码不同步，依赖 `text-embedding-3-small` 时实际不会生效。

#### 7.7 Document 重排序模型首次加载无进度提示

**位置:** [`src/rag/reranker.py:68`](src/rag/reranker.py:68)

首次调用时 `CrossEncoder("BAAI/bge-reranker-base")` 会下载 ~1GB 模型，阻塞请求但无进度提示。

#### 7.8 CLI 模式下 Planner 初始化依赖 Planner 配置

**位置:** [`src/main.py:60`](src/main.py:60)

```python
if config.planner_enabled:
    from src.agents.planner import Planner
    planner = Planner(client, model=model)
```

但如果 Planner 启用但客户端不可用（网络问题），初始化会失败。

#### 7.9 评估框架缺少 finance_agent 工具映射

**位置:** [`scripts/run_eval.py:62`](scripts/run_eval.py:62)

```python
tool_map = {"HR_TOOLS": HR_TOOLS, "IT_TOOLS": IT_TOOLS, "LEGAL_TOOLS": LEGAL_TOOLS}
```

缺少 `FINANCE_TOOLS`，如果 kb_registry 包含 finance 会 KeyError。

#### 7.10 Chroma 路径使用相对路径拼接

**位置:** [`src/rag/knowledge_base.py:27`](src/rag/knowledge_base.py:27)

```python
CHROMA_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")
```

在非标准工作目录下运行时可能指向错误位置。

### 🟢 低优先级

#### 7.11 缺少 pytest 单元测试

`tests/` 目录下只有 `__init__.py`，没有实际的测试文件。现有的测试脚本都在 `scripts/` 下，是独立脚本而非 pytest 集成。

#### 7.12 词汇命名字段不一致

- `AgentResponse` 中有 `processing_time_ms` 和 `tokens_used`
- CLI 输出显示为 `⏱ Xms · 🔍 N chunks · 🪛 N tools · 🪙 N tokens`
- 前端的 app.js 期望字段名可能不完全一致

#### 7.13 文件监听仅限同级目录

**位置:** [`src/rag/knowledge_base.py:157`](src/rag/knowledge_base.py:157)

```python
self._observer.schedule(event_handler, self.docs_dir, recursive=False)
```

如果知识库目录有子目录（如 `data/hr/subdir/`），变更不会被检测。

#### 7.14 LLM 调用无超时控制

`_call_llm_with_retry` 只捕获重试类异常，但 HTTP 请求本身没有设置 timeout，可能导致长时间挂起。

#### 7.15 种子数据密码明文存储

**位置:** [`src/tools/db.py`](src/tools/db.py) 种子数据

密码 `123456` 明文存储在数据库和代码中。`db_verify_password()` 用 `==` 比较。虽然这是教学项目，但生产环境中需要 bcrypt。

#### 7.16 前端 API base URL 硬编码

**位置:** [`frontend/index.html`](frontend/index.html) 中 `const API = '/api'`

如果前端和后端不在同一域名下需要代理或 CORS 配置。

---

## 8. 技术债务与改进建议

### 8.1 短期修复（可直接提交）

| # | 问题 | 修复方案 |
|---|------|---------|
| 1 | rate_limit.py 重复 return | 删除不可达的第二条 return |
| 2 | 评估脚本缺少 FINANCE_TOOLS | 在 tool_map 中加入 `"FINANCE_TOOLS": FINANCE_TOOLS` |
| 3 | 会话恢复缺失 | API 启动时调用 `store.load_recent()` 恢复最近会话 |
| 4 | 上下文压缩未启用 | 将 LLM client 注入 SummaryCompressor 并启用压缩 |

### 8.2 中期改进

| # | 建议 | 理由 |
|---|------|------|
| 1 | 财务工具接入真实 RAG | 提升回答准确性和一致性 |
| 2 | 添加 pytest 测试套件 | 确保重构安全 |
| 3 | on_step 异常记录日志而非静默 | 便于排查 SSE/流式 问题 |
| 4 | LLM 调用添加超时配置 | 防止长时间挂起 |
| 5 | Chroma/缓存路径使用绝对路径或配置化 | 提升部署灵活性 |
| 6 | 密码使用 bcrypt 哈希 | 即使是教学项目也养成好习惯 |

### 8.3 长期架构演进

| # | 建议 |
|---|------|
| 1 | 将 ConversationStore 和 LongTermMemory 完全集成到 API 生命周期中 |
| 2 | 支持多租户（tenant_id 隔离） |
| 3 | EventBus 从内存实现迁移到 Redis pub/sub（多进程部署） |
| 4 | 引入 LangSmith / LangFuse 等生产级可观测性平台 |
| 5 | 前端支持暗色模式、移动端响应式 |
| 6 | 添加 Docker Compose 一键部署 |

---

*本文档基于代码审查生成，所有引用均附带了源文件路径和行号。*  
*项目开发步骤见 [`docs/development-steps.md`](docs/development-steps.md)，技术规格见 [`implementation-plan.md`](implementation-plan.md)。*
