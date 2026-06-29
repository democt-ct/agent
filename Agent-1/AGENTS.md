# AGENTS.md — 患者智能辅助 Agent

> 每次新对话自动加载。修改项目后请调用 `/sync-docs` 同步 CHANGELOG 和项目文档。

---

## 1. 项目一句话

患者端 AI 助手原型。患者可以用自然语言查询自己的病历/就诊记录、上传图片理解报告、连续对话记忆、语音播报。

---

## 2. 目录结构（简要）

| 目录/文件 | 作用 |
|-----------|------|
| `app/` | ★ 后端核心（FastAPI + MCP + ORM + 服务层） |
| `app/api/` | HTTP 路由层（患者 CRUD、Agent、记忆、SSE 流式） |
| `app/core/` | 基础设施（PG 连接、Redis、调度器、日志、指标） |
| `app/middleware/` | 安全中间件（访问控制、速率限制） |
| `app/mcp/` | 自研 MCP 工具层（5 工具 + LLM 编排 + 视觉 + TTS） |
| `app/models/` | SQLAlchemy ORM（11 张表） |
| `app/services/` | 业务服务（RAG 检索、记忆抽取、偏好管理） |
| `app/schemas/` | Pydantic 请求/响应 Schema |
| `app/static/` | 旧版前端 + 质量评估控制台（`evaluate.html` + `css/` + `js/`） |
| `app/config/` | 配置层（`production.py`、`local_settings.py`、`evaluation_cases.py`） |
| `frontend/` | ★ 新版前端（React 18 + TypeScript + Vite） |
| `data/chroma_knowledge/` | ChromaDB 向量库 |
| `docs/` | 项目文档 |
| `scripts/` | 工具脚本（批量导入、质量评估、种子数据） |
| `tests/` | pytest 测试（131 个） |
| `docker-compose.yml` | PostgreSQL 15 (:5433) + Redis 7 (:6380) |
| `start_dev.bat` | 本地一键启动 |

> 完整目录树、每层详解、架构模式见 **[docs/项目结构文档.md](docs/项目结构文档.md)**

---

## 3. 启动方式

| 方式 | 命令 | 说明 |
|------|------|------|
| **后端开发** | `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload` | 开发模式热重载，需先启动 Docker |
| **Docker 服务** | `docker compose up -d` | 启动 PostgreSQL(:5433) + Redis(:6380) |
| **前端开发** | `cd frontend && npm run dev` | :3000 代理到 :8000 |
| **内网穿透** | 双击 `start_tunnel.bat` | 一键后端 + Cloudflare 隧道 |
| **质量评估** | `python scripts/run_evaluation.py --verbose` | 运行 15 条质量评估用例（用例数据源在 `app/config/evaluation_cases.py`） |

访问：
- `http://localhost:3000` — React 前端（聊天 + 记忆 + Debug）
- `http://localhost:3000/evaluate` — 质量评估控制台
- `http://127.0.0.1:8000/evaluate` — 评估控制台（直连）
- `http://127.0.0.1:8000/docs` — Swagger 文档
- `http://127.0.0.1:8000/metrics` — Prometheus 指标

---

## 4. 环境变量速查

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PG_HOST` / `PG_PORT` / `PG_USER` / `PG_PASSWORD` / `PG_DATABASE` | localhost:5433 / postgres / postgres / patient_agent | PostgreSQL（Docker 映射 5433→5432） |
| `REDIS_HOST` / `REDIS_PORT` | localhost:6380 | Redis（Docker 映射 6380→6379） |
| `TEXT_API_BASE` / `TEXT_MODEL` | ModelScope API / deepseek-ai/DeepSeek-V4-Flash | 文本 LLM |
| `TEXT_FALLBACK_MODEL` | Qwen/Qwen3-235B-A22B-Instruct-2507 | 备用 LLM（主模型失败时降级） |
| `VISION_API_BASE` / `VISION_MODEL` | ModelScope / Qwen3-VL-8B-Instruct | 视觉 LLM |
| `CORS_ORIGINS` | * | CORS 白名单（逗号分隔） |
| `RATE_LIMIT_PER_MINUTE` | 60 | 速率限制 |
| `KNOWLEDGE_HF_EMBEDDING_MODEL` | BAAI/bge-small-zh-v1.5 | 嵌入模型 |
| `RERANKER_ENABLED` | false | Cross-Encoder 重排序 |
| `QUERY_REWRITE_ENABLED` | true | LLM 查询改写 |
| `RERANKER_MODEL` | BAAI/bge-reranker-v2-m3 | 重排序模型 |
| `SCHEDULER_ENABLED` | false | 后台定时任务 |
| `TTS_PROVIDER` | kokoro | TTS 引擎 |

---

## 5. 关键约定

- **数据库**: PostgreSQL 为主，支持 SQLite 测试模式（`TEST_DATABASE_URL` 环境变量）。连接前 `database.py` 会自动探测 TCP 端口
- **LLM 配置**: 优先级 `app/config/local_settings.py` > 环境变量 > 默认值。支持主模型 + 备用模型自动降级
- **前端**: React 新版在 `frontend/`（`localhost:3000`），旧版在 `app/static/`（保留兼容）。质量评估控制台在 `/evaluate` 路由，已拆分为 `evaluate.html` + `css/evaluate.css` + `js/evaluate.js`
- **评估用例数据源**: 用例统一定义在 `app/config/evaluation_cases.py`（单一数据源），HTTP 接口 `GET /api/v1/evaluation/cases`、命令行运行器、前端控制台均从此处取数，禁止硬编码副本
- **端口映射**: Docker PG 映射 5433→5432，Redis 映射 6380→6379（见 `docker-compose.yml`）
- **Reranker/Scheduler**: 默认关闭。都是"增强型"功能，不影响核心问答链路
- **启动脚本**: `start_dev.bat` / `start_tunnel.bat`（`.bat` 文件）

---

## 6. 更新记录

> 详见 **[CHANGELOG.md](./CHANGELOG.md)**
