# 07 - 实践：Docker 部署旅游 Agent

> 综合运用前六节的知识，用 Docker Compose 把旅游 Agent 及其全部依赖一键启动

---

## 目标

把第二阶段设计的「旅游 Agent V2 架构」真正跑起来——不是 Python 脚本，而是一个**多服务系统**：

```
旅游 Agent 系统 = Agent 服务 + Redis + PostgreSQL + Worker + Scheduler
```

---

## 系统拓扑

```
┌──────────────────────────────────────────────────┐
│                  Docker Compose                   │
│                                                   │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐  │
│  │  Nginx   │   │  Redis   │   │ PostgreSQL   │  │
│  │  :80     │   │  :6379   │   │    :5432     │  │
│  └────┬─────┘   └────┬─────┘   └──────┬───────┘  │
│       │              │                │          │
│       ▼              │                │          │
│  ┌──────────┐        │                │          │
│  │ Agent API│────────┘                │          │
│  │  :8000   │                         │          │
│  └──────────┘                         │          │
│       │                               │          │
│       │  提交任务                      │          │
│       ▼                               │          │
│  ┌──────────┐                         │          │
│  │  Worker  │─────────────────────────┘          │
│  │ (Celery) │                                    │
│  └──────────┘                                    │
│       │                                          │
│  ┌──────────┐                                    │
│  │ Scheduler│                                    │
│  └──────────┘                                    │
└──────────────────────────────────────────────────┘
```

---

## Step 1：项目结构

```
travel-agent/
├── docker-compose.yml
├── .env.example
├── Dockerfile
├── requirements.txt
├── src/
│   ├── main.py                # FastAPI 入口
│   ├── agent/
│   │   ├── orchestrator.py    # TravelAgentV2 主逻辑
│   │   ├── planner.py
│   │   ├── workflow.py
│   │   ├── state_machine.py
│   │   ├── router.py
│   │   └── hitl.py
│   ├── infrastructure/
│   │   ├── session.py         # SessionManager (Redis)
│   │   ├── database.py        # PostgreSQL 连接 + ORM
│   │   ├── queue.py           # TaskQueue / Celery
│   │   ├── cache.py           # ToolCache
│   │   └── monitoring.py      # Logger + Tracer + Metrics
│   ├── tools/
│   │   ├── flight_search.py
│   │   ├── hotel_search.py
│   │   ├── weather.py
│   │   └── web_search.py
│   └── models/
│       └── schemas.py         # Pydantic 请求/响应模型
├── worker/
│   └── worker.py              # Celery Worker 入口
├── scheduler/
│   └── scheduler.py           # 定时任务入口
└── tests/
    └── test_session.py
```

---

## Step 2：docker-compose.yml

```yaml
version: '3.8'

services:
  # ========== API 服务 ==========
  api:
    build: .
    container_name: travel-agent-api
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    volumes:
      - ./src:/app/src       # 开发时热重载
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # ========== Worker（异步任务处理）==========
  worker:
    build: .
    container_name: travel-agent-worker
    env_file:
      - .env
    depends_on:
      - redis
      - postgres
    command: celery -A worker.worker worker --loglevel=info --concurrency=4
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # ========== Scheduler（定时任务）==========
  scheduler:
    build: .
    container_name: travel-agent-scheduler
    env_file:
      - .env
    depends_on:
      - redis
      - postgres
    command: python -m scheduler.scheduler
    restart: unless-stopped

  # ========== Redis（Session + Cache + Queue）==========
  redis:
    image: redis:7-alpine
    container_name: travel-agent-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  # ========== PostgreSQL（数据库）==========
  postgres:
    image: postgres:16-alpine
    container_name: travel-agent-db
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: agent
      POSTGRES_PASSWORD: ${DB_PASSWORD:-agent_secret}
      POSTGRES_DB: travel_agent
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql  # 初始化 Schema
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agent -d travel_agent"]
      interval: 10s
      timeout: 3s
      retries: 5

volumes:
  redis_data:
  postgres_data:
```

---

## Step 3：Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 源码
COPY src/ ./src/
COPY worker/ ./worker/
COPY scheduler/ ./scheduler/

# 非 root 用户运行
RUN useradd -m agent && chown -R agent:agent /app
USER agent

# 默认命令（可被 docker-compose 覆盖）
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Step 4：FastAPI 入口（main.py）

```python
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from src.infrastructure.session import SessionManager
from src.infrastructure.database import Database
from src.infrastructure.queue import TaskQueue
from src.infrastructure.cache import ToolCache
from src.infrastructure.monitoring import AgentLogger, AgentTracer, AgentMetrics
from src.agent.orchestrator import TravelAgentV2
import redis

# ========== 初始化 ==========
app = FastAPI(title="Travel Agent API", version="2.0.0")

redis_client   = redis.Redis(host="redis", port=6379, decode_responses=True)
session_mgr    = SessionManager(redis_client)
db             = Database.from_env()
queue          = TaskQueue(redis_client)
cache          = ToolCache(redis_client)
logger         = AgentLogger()
tracer         = AgentTracer()
metrics        = AgentMetrics()
agent          = TravelAgentV2(session_mgr, db, queue, cache, logger, tracer, metrics)


# ========== 请求/响应模型 ==========
class ChatRequest(BaseModel):
    user_id: str
    session_id: str | None = None
    message: str

class UserResponse(BaseModel):
    user_id: str
    session_id: str
    action_id: str
    decision: str          # "approve" | "reject" | "modify"
    modifications: dict | None = None

class TaskStatusRequest(BaseModel):
    task_id: str


# ========== API 端点 ==========

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}

@app.post("/chat")
def chat(request: ChatRequest):
    """主对话入口"""
    try:
        result = agent.handle(
            user_input=request.message,
            user_id=request.user_id,
            session_id=request.session_id
        )
        return result
    except Exception as e:
        logger.error(request.session_id or "new", "api.chat", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/user-response")
def user_response(request: UserResponse):
    """用户对 HITL 确认的回应"""
    try:
        result = agent.handle_user_response(
            user_id=request.user_id,
            session_id=request.session_id,
            response={
                "action_id": request.action_id,
                "decision": request.decision,
                "modifications": request.modifications
            }
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks/{task_id}/status")
def task_status(task_id: str):
    """查询异步任务进度"""
    status = queue.get_result(task_id)
    if status["status"] == "not_found":
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return status

@app.get("/sessions/{user_id}")
def list_sessions(user_id: str):
    """列出用户的所有活跃会话"""
    return session_mgr.list_user_sessions(user_id)

@app.get("/metrics")
def get_metrics():
    """实时指标仪表盘"""
    return {
        "success_rate": metrics.success_rate(),
        "avg_latency_ms": metrics.avg_latency("session"),
        "total_cost": metrics.total_cost(),
        "total_tokens": metrics.total_tokens(),
        "dashboard": metrics.dashboard()
    }

@app.get("/cache/stats")
def cache_stats():
    """缓存统计"""
    return cache.stats()
```

---

## Step 5：.env 配置文件

```bash
# .env.example
REDIS_URL=redis://redis:6379/0
DATABASE_URL=postgresql://agent:agent_secret@postgres:5432/travel_agent
DB_PASSWORD=agent_secret

LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-your-key-here
LLM_BASE_URL=https://api.openai.com/v1

LOG_LEVEL=INFO
MAX_RETRIES=3
SESSION_TTL=1800
```

---

## Step 6：初始化 Schema（db/init.sql）

```sql
-- 在 PostgreSQL 首次启动时自动执行
CREATE TABLE IF NOT EXISTS users (
    id            VARCHAR(64) PRIMARY KEY,
    email         VARCHAR(255) UNIQUE,
    display_name  VARCHAR(128),
    preferences   JSONB DEFAULT '{}',
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
    id              VARCHAR(64) PRIMARY KEY,
    user_id         VARCHAR(64) NOT NULL REFERENCES users(id),
    goal            TEXT,
    current_state   VARCHAR(32),
    plan            JSONB,
    context         JSONB,
    state_history   JSONB,
    total_tokens    INT DEFAULT 0,
    total_cost      DECIMAL(10,6) DEFAULT 0,
    total_latency_ms INT DEFAULT 0,
    tool_calls_count INT DEFAULT 0,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at DESC);

CREATE TABLE IF NOT EXISTS tool_logs (
    id          SERIAL PRIMARY KEY,
    session_id  VARCHAR(64) NOT NULL,
    user_id     VARCHAR(64) NOT NULL,
    tool_name   VARCHAR(128) NOT NULL,
    input       JSONB,
    output      JSONB,
    status      VARCHAR(16) NOT NULL,
    latency_ms  INT,
    tokens_used INT DEFAULT 0,
    cost        DECIMAL(10,6) DEFAULT 0,
    error_msg   TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tool_logs_session ON tool_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_tool_logs_created ON tool_logs(created_at DESC);
```

---

## Step 7：启动与验证

```bash
# 1. 克隆/进入项目
cd travel-agent

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 LLM_API_KEY

# 3. 构建 & 启动全部服务
docker compose up -d

# 4. 验证各服务状态
docker compose ps
#   NAME                      STATUS
#   travel-agent-api          Up (healthy)
#   travel-agent-worker       Up
#   travel-agent-scheduler    Up
#   travel-agent-redis        Up (healthy)
#   travel-agent-db           Up (healthy)

# 5. 测试 API
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user", "message": "帮我规划成都三日游，预算3000"}'

# 6. 查看指标
curl http://localhost:8000/metrics

# 7. 查看日志
docker compose logs -f api
docker compose logs -f worker

# 8. 停止
docker compose down
```

---

## Step 8：完整测试流程

```python
# tests/test_integration.py

import requests
import time
import json

BASE = "http://localhost:8000"

def test_full_flow():
    """完整的旅游规划流程测试"""
    user_id = "test_user_001"
    
    # ① 发送规划请求
    print("\n📤 发送规划请求...")
    r = requests.post(f"{BASE}/chat", json={
        "user_id": user_id,
        "message": "帮我规划成都三日游，预算3000元，7月20日出发"
    })
    assert r.status_code == 200
    data = r.json()
    
    if data.get("status") == "awaiting_confirmation":
        # ② HITL：确认选择
        print(f"⏳ 等待确认: {data['message'][:100]}...")
        
        action_id = data["action_id"]
        session_id = data["session_id"]
        
        r2 = requests.post(f"{BASE}/user-response", json={
            "user_id": user_id,
            "session_id": session_id,
            "action_id": action_id,
            "decision": "approve"
        })
        assert r2.status_code == 200
        print(f"✅ 用户确认，Agent 继续执行")
    
    elif "task_id" in data:
        # ③ 异步任务：轮询进度
        task_id = data["task_id"]
        print(f"⏳ 异步任务 {task_id} 处理中...")
        
        for _ in range(30):  # 最多等 30 秒
            r3 = requests.get(f"{BASE}/tasks/{task_id}/status")
            status = r3.json()
            print(f"   进度: {status.get('progress', 0)}% - {status['status']}")
            
            if status["status"] in ("completed", "failed"):
                break
            time.sleep(1)
        
        assert status["status"] == "completed"
    
    # ④ 验证指标
    r4 = requests.get(f"{BASE}/metrics")
    metrics_data = r4.json()
    print(f"\n📊 指标:")
    print(f"   成功率: {metrics_data['success_rate']:.1%}")
    print(f"   总费用: ${metrics_data['total_cost']:.4f}")
    print(f"   总Token: {metrics_data['total_tokens']:,}")
    
    print("\n🎉 完整流程测试通过！")

if __name__ == "__main__":
    test_full_flow()
```

---

## Step 9：架构验证清单

运行以下验证，确保每个组件正常工作：

```
□ Redis：
  docker compose exec redis redis-cli PING
  → PONG

□ PostgreSQL：
  docker compose exec postgres psql -U agent -d travel_agent -c "SELECT count(*) FROM sessions;"

□ Agent API：
  curl http://localhost:8000/health
  → {"status": "ok", "version": "2.0.0"}

□ Session 持久化：
  ① 创建会话 → ② docker compose restart api → ③ 用 session_id 恢复 → 状态一致

□ 异步任务：
  ① 提交长任务 → ② 立即收到 task_id → ③ 轮询 /tasks/{task_id}/status → 看到进度推进

□ 监控仪表盘：
  curl http://localhost:8000/metrics
  → 返回 success_rate / avg_latency / total_cost / total_tokens

□ 缓存：
  ① 查询天气 → ② 再次查询相同城市 → ③ 第二次 _source = "cache"

□ 断路器：
  ① 模拟外部 API 连续失败 5 次 → ② 断路器 OPEN → ③ Agent 使用降级方案
```

---

## 完整设计文档模板

```markdown
# 旅游 Agent Production 部署文档

## 1. 系统架构
[贴拓扑图]

## 2. 服务清单
| 服务 | 镜像 | 端口 | 职责 |
|------|------|------|------|

## 3. 数据流
[画一次请求经过的全部服务]

## 4. 部署步骤
docker compose up -d 之后的验证步骤

## 5. 监控面板
[贴 metrics dashboard 截图或输出]

## 6. 告警规则
[贴告警阈值]

## 7. 已知问题 / TODO
```

---

→ 完成后进入：[04-Evaluation](../04-Evaluation/)
