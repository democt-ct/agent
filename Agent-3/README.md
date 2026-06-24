<# 企业多专家 Agent 系统

企业内部有大量分散的知识（HR 政策、IT 运维手册、法务合规文档、财务报销流程），员工需要花大量时间在多个系统/文档之间切换。本系统构建一个**多专家 Agent 系统**，每个 Agent 拥有独立的知识库和工具集，由 Orchestrator Agent 统一调度。

## 架构概览

```
用户输入 → Orchestrator Agent (路由/编排)
               ├── HR Agent    (人事制度/考勤/请假)
               ├── IT Agent    (设备/报修/工单)
               ├── 法务 Agent   (合规/合同/数据保护)
               └── 财务 Agent   (报销/预算/采购)
```

## 快速开始

```bash
# 安装依赖
poetry install

# 配置 API Key
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY

# 本地启动（双击或命令行）
scripts\start_local.bat
# 浏览器打开 http://127.0.0.1:8080

# 内网穿透（公网访问）
scripts\start_tunnel.bat
```

## 项目结构

```
src/
├── main.py              # CLI 入口
├── api/                 # FastAPI + SSE 流式路由
├── agents/              # Agent 实现 (BaseAgent + Orchestrator + Planner)
├── protocol/            # 协议层 (AgentRequest/Response/交割)
├── rag/                 # RAG Pipeline (加载/分块/检索/重排序)
├── tools/               # 工具定义 (HR/IT/法务/财务 mock 工具)
├── memory/              # 短期记忆 (L2) + 长期记忆 (L3)
├── gateway/             # JWT 认证 + 限流
├── evaluation/          # 评估体系
├── observability/       # 执行追踪
└── config.py            # 集中配置
frontend/                # 前端 (HTML/CSS/JS 单页应用)
data/                    # 知识库原始文档 + SQLite 业务库
chroma_db/               # Chroma 向量索引持久化
scripts/                 # 辅助脚本
```

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 语言 | Python ≥3.11 | |
| LLM | DeepSeek (兼容 OpenAI SDK) | 支持 thinking mode 推理链 |
| Agent 编排 | 手写 ReAct + LangGraph | query 模式单次调用，action 模式多轮工具调用 |
| Embedding | BGE-large-zh-v1.5 | 1024 维，ModelScope/HF 自动下载 |
| 向量库 | Chroma (持久化) | 零配置内嵌运行 |
| 关键词检索 | BM25 (rank-bm25 + jieba) | 与向量检索 RRF 融合 |
| 重排序 | Cohere Rerank / BGE Cross-Encoder | 可配置切换 |
| 前端 | 原生 HTML/CSS/JS | FastAPI StaticFiles 托管，SSE 流式推送 |
| 文档加载 | pypdf + python-docx | |

---

## 启动优化

启动流程经过三轮优化，从「阻塞等待 15 秒」降到「2 秒可访问、后台预热」：

### 优化历程

| 版本 | 方式 | 首屏时间 | 首条查询延迟 | 问题 |
|------|------|---------|-------------|------|
| v0 | `_init_engine()` 同步阻塞 lifespan | 8-15s | 即时 | 页面白屏等待 |
| v1 | daemon 线程后台初始化 | 2s | 2-5s | 首条查询触发 BGE 模型懒加载 |
| v2 | 后台初始化 + 预加载 Embedding 模型 | 2s | 即时 | ✅ 当前版本 |

### 技术细节

```
FastAPI lifespan
  ├─ 立即 yield（2s 内页面可访问）
  └─ 后台线程 _init_engine:
       ├─ bootstrap_company_workspace()   # SQLite DDL
       ├─ 串行加载 4 个 KB                 # Chroma + BM25 (ChromaDB 不支持并发 PersistentClient)
       ├─ Orchestrator + ToolAgent + ReviewAgent + Memory
       ├─ embedder.model                 # 🔥 预加载 1.3GB BGE 模型
       └─ state.ready.set()             # 标记就绪
```

关键设计决策：

- **非阻塞 lifespan**：FastAPI 先 accept 请求，初始化在后台线程跑。就绪前 `/api/chat` 返回 503 + `"引擎尚未初始化完成"`，`/api/health` 返回 `status: "initializing"` + 进度百分比。
- **串行加载 KB**：ChromaDB 底层 SQLite 不支持多个 `PersistentClient` 并发访问同一目录，因此 4 个 KB 串行加载。实际瓶颈不在 KB I/O（合计 <1s），而在 Embedding 模型加载。
- **预加载 Embedding 模型**：`SentenceTransformer("BAAI/bge-large-zh-v1.5")` 首次加载 1.3GB 权重需 2-5 秒。在 init 线程末尾显式触发 `embedder.model` 完成预热，避免第一条用户查询等待。
- **`Embedder.model` 双重检查锁**：`threading.Lock` + double-check 保证多线程环境下模型只初始化一次。
- **异常兜底**：`_init_engine` 外层 `try/except` 捕获全部异常并写入 `init_progress.error`，避免 daemon 线程静默死亡导致永久 503。

