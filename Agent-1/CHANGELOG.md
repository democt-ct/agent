# CHANGELOG — 患者智能辅助 Agent

> 每次改完代码顺手加一条，格式：`YYYY-MM-DD — 简述改了啥`

---

## 2026-06-20 — 项目结构治理（P0/P1/P2 综合）

针对结构验收发现的问题，按优先级依次处理：

### P0: 评估用例单一数据源
- **新增 `app/config/evaluation_cases.py`**: 评估用例的唯一权威定义（生产可发布），含 15 条用例 + 每条三维加权 `scoring` 配置
- **新增 `app/api/evaluation_routes.py`**: HTTP 接口 `GET /api/v1/evaluation/cases`，在 `main.py` 注册路由
- **`tests/test_evaluation.py` 重构**: 数据定义迁移到 `app/config/`，本文件改为 re-export + 完整性测试（新增 `test_all_cases_have_scoring` 校验权重和为 1.0）
- **`evaluate.html` 改造**: 移除 15 条硬编码副本，启动时通过 `loadCases()` 从 API 拉取；保留失败告警但不阻塞页面

### P0: 根目录清理
- 归位 6 个错位文件：`cli_query.py` → `scripts/`；`test_risk_signals.py` / `codex_update_test.py` → `tests/`；`demo_0.wav` / `result.wav` / `image.png` → `data/`
- 删除 `nul`（Windows 误建空文件）+ `test.db`（测试残留）
- 根目录仅保留项目级入口文件

### P1: 评估控制台拆分
- `app/static/evaluate.html`（1083 行单文件）拆分为 3 文件：
  - `evaluate.html`（83 行）— 纯 HTML 骨架
  - `css/evaluate.css`（190 行）— 样式
  - `js/evaluate.js`（817 行）— 逻辑

### P1: 配置文件收敛
- `app/mcp/local_settings.py` + `local_settings.example.py` 迁移到 `app/config/`（与 `production.py` / `evaluation_cases.py` 同居）
- 删除冗余的 `app/mcp/local_settings.postgres.py`（内容已被 `local_settings.py` 包含）
- `app/mcp/config.py` 改为优先 `from app.config import local_settings`，回退到旧路径（向后兼容）
- `.gitignore` 更新：新增 `app/config/local_settings.py`，保留旧路径防残留

### P2: 文档同步
- `AGENTS.md`: 新增 `app/config/` 目录条目；评估用例数 20 → 15；`local_settings.py` 标注新位置；评估控制台标注拆分为 3 文件；新增"评估用例数据源"约定

---

## 2026-07-17 — 文档同步与版本修正

- **版本号更新**: `app/main.py` version `0.3.0` → `0.3.1`
- **脚本重命名**: `start_local.bat` → `start_dev.bat`（AGENTS.md、项目结构文档、README 同步修正）
- **测试计数更新**: pytest 测试从 127 增至 131（新增 `test_streaming.py` 检查点）
- **新增根目录文件**: `reasonix.toml`、`rebuild_frontend.bat` 加入项目结构文档
- **`frontend/README.md` 替换**: Vite 默认模板替换为项目前端说明
- **文档同步优化**: 全量运行 `sync-docs` 技能，同步 4 份核心文档

---

## 2026-06-19 — sync-docs skill 全局化：从项目级移至全局安装

- **skill 位置迁移**: `.reasonix/skills/sync-docs/SKILL.md` → `%APPDATA%/reasonix/skills/sync-docs/SKILL.md`（全局安装，跨项目复用）
- **skill 内容重写**: 不再硬编码 4 个特定文件路径（CHANGELOG / 项目结构文档 / README / AGENTS.md），改为自动发现项目文档并按文档角色（修改日志 / 架构文档 / 项目说明 / Agent 指南）适配更新
- **架构文档同步**: `docs/项目结构文档.md` 中 `.reasonix/` 章节移除已不存在的 `skills/sync-docs/SKILL.md` 条目

---

## 2026-06-19 — 意图识别改进（关键词 + LLM 提示词 + 评估闭环）

- **关键词层加固**: VISIT/MEDICAL/SYMPTOM/PROFILE 关键词从 30 条扩展到 150+ 条；新增 ALLERGY/SURGERY/MEDICATION 专用关键词组
- **历史语境检测**: 新增 `_has_historical_context()`，区分"以前有什么病"（查记录）vs "现在不舒服"（症状咨询）
- **多意图融合**: `_fallback_intent` 重写为优先级链决策——同时命中就诊+病历→profile_summary，过敏→medical_records_query 等
- **LLM 提示词增强**: `_identify_intent` 提示词改为 few-shot 格式（每类 1 示例）、增加 `uncertain` 兜底输出、增加推理理由字段
- **评估页面增强**: 聚合指标面板（通过率/意图准确率/关键词覆盖率/平均耗时/分类表现）+ 意图混淆矩阵（期望意图×实际意图交叉表）+ 数据来源说明
- **修复**: 移除过激的关键词短路逻辑（地址查询除外），让 LLM 处理更多歧义情况
- **AGENTS.md 去重**: 完整目录树（80+行）替换为简要表格 + 引用 `docs/项目结构文档.md`；底部更新记录替换为引用 `CHANGELOG.md`；顶部提示改为调用 `/sync-docs`。文件从 165 行缩减到 89 行
- **新增 sync-docs skill**: `.reasonix/skills/sync-docs/SKILL.md`，subagent 类型项目 skill，用于变更后自动同步 4 份核心文档（CHANGELOG、项目结构文档、README、AGENTS.md）

---

## 2026-06-19 — 五阶段生产化改造（综合）

### Phase 1: 基础设施建设
- **pytest 测试框架**: 创建 `tests/` 包 + conftest.py（SQLite 兼容 + 事务隔离），56 个测试覆盖 CRUD/Auth/API/知识检索
- **database.py**: 支持 SQLite 模式（跳过 PG pool 参数 + wait），测试时可使用 SQLite
- **openai SDK 替换**: `mcp/config.py` 裸 `urllib` → 官方 `openai` Python SDK，3 次指数退避重试（RateLimit/Timeout/5xx）
- **CORS 加固**: `main.py` 添加 `CORSMiddleware`，从 `CORS_ORIGINS` 环境变量读取白名单
- **凭据管理**: `.env` 添加 PG 凭据/auth secret/CORS 配置；`database.py` 默认密码告警
- **部署**: 添加 `gunicorn`；Dockerfile 改为 `gunicorn + UvicornWorker`（4 workers, 120s timeout）

### Phase 2: 数据接入管道
- **bulk_import.py**: 支持 CSV/JSON 批量导入患者/病历/就诊记录；字段校验 + 去重 + `--update` / `--dry-run`
- **自动知识切片**: `--chunk` 参数在导入后自动生成 5 个 domain 的 `MemoryKnowledgeChunk`（诊断/现病史/用药/就诊摘要/复诊计划）
- **增量同步**: `ImportTracker` 基于文件 mtime 跟踪，`--incremental` / `--tracker-status`
- **示例数据**: `data/examples/patients.example.json` + `records.example.csv`

### Phase 3: 安全与合规加固
- **PatientDataGuardMiddleware**: 拦截患者数据端点，验证 auth_token 与 patient_id 匹配，生产模式强制认证
- **AuditLog**: 新增 `audit_log` 表，异步记录每次患者数据访问（patient_id/endpoint/method/action/status_code/client_ip/auth_verified/duration_ms）
- **RateLimitMiddleware**: 内存令牌桶速率限制（`RATE_LIMIT_PER_MINUTE` 环境变量，可扩展 Redis）
- **敏感字段脱敏**: `app/utils/masking.py` — 手机号 `138****8000`、地址保留前 6 字、身份证掩码
- **数据保留**: `scheduler.py` 新增 `_cleanup_old_session_data`，每天凌晨清理 >90 天的会话缓冲/审计日志/过期切片

### Phase 4: Agent 能力增强
- **SSE 流式端点**: `POST /api/v1/mcp/agent/query-stream`，返回 `status→intent→planning→tool_execution→token*→done` 事件序列
- **LLM 自动降级**: `config.py` 主模型失败后自动切换到备用模型（`TEXT_FALLBACK_MODEL` 环境变量）
- **Agent 反思**: `_select_direct_path` 工具结果为空时自动回退到直接 LLM 回答
- **知识切片质量**: confidence + tags 字段 + ChromaDB 同步质量检查

### Phase 5: 可观测性与运维
- **Prometheus 指标**: `app/core/metrics.py` — HTTP 请求计数/延迟、Agent 查询计数/延迟、LLM 调用计数/延迟/Token；`GET /metrics` 端点
- **链路追踪**: `LoggingMiddleware` 自动生成 `trace_id`（UUID），日志 `[trace=xxx]` 输出，响应头 `X-Trace-Id` 返回
- **质量评估集**: `tests/test_evaluation.py` — 20 条测试问答对，覆盖患者事实/就诊/病历/症状/过敏/跨科室/用药/随访/一般医学/问候

---

## 2025-06-17

- **启动脚本全面加固**: Docker daemon 探活 + 容器 `exited` 自动 `down`+`up` 重建 + 快速 `running` 检查（不再死等 `healthy`）
- **React 前端工程化**: 新建 `frontend/` 目录，Vite + React 18 + TypeScript，5 个组件
- **Reranker**: `knowledge_retrieval.py` 集成 Cross-Encoder，默认关闭
- **后台定时调度**: 新增 `app/core/scheduler.py`，APScheduler 三个定时任务，默认关闭
- **database.py**: 新增 `_wait_for_postgres()` TCP 端口探测 + 指数退避
- **文档更新**: docs/ 下 5 个文件同步更新
- **AGENTS.md / CHANGELOG.md**: 新建项目规范和更新记录文件

---

## 更早

- 四层记忆架构（事实/工作/长期摘要/知识）
- 自研 MCP Server（5 个工具）
- 混合 RAG（ChromaDB 向量 + SQL 关键词 + 元数据 + 时效）
- 图文问答 + TTS 语音播报
- Memory Debug 可视化
- 患者过敏安全机制（五层防护）
- HMAC 身份 token
- PostgreSQL + Redis 迁移（从 SQLite）
- Docker 部署支持
