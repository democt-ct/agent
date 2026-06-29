# 02 - Database Design — 数据库设计

> 学习目标：理解 Agent 系统需要存什么数据，掌握不同场景下的数据库选型和 Schema 设计

---

## 1. 为什么需要数据库

Redis 存 Session 是"热数据"——快，但会过期。数据库存的是"冷数据"——需要持久、需要查询、需要分析的那些。

```
Redis：   "用户正在做什么"（Session，有TTL）
Database："用户做过什么"（历史，永久保留）
```

---

## 2. 三选一：SQLite / PostgreSQL / MongoDB

```
SQLite        PostgreSQL          MongoDB
─────────     ──────────────      ──────────
零配置        功能最全             文档灵活
单文件         连接池/主从          嵌套结构
嵌入式         SQL标准             无Schema
适合：         适合：               适合：
- 单机Demo    - 生产环境           - 非结构化数据
- 本地测试    - 复杂查询           - 快速迭代
- 小规模      - 多服务共享         - 嵌套文档
```

> **选择建议**：学习阶段 SQLite → 生产阶段 PostgreSQL。MongoDB 适合 Agent 的嵌套 JSON 但查询能力弱于 PG。

---

## 3. 旅游 Agent 需要哪些表

```
   ┌──────────┐
   │  users   │  用户账号、偏好
   └────┬─────┘
        │ 1:N
   ┌────▼──────┐
   │  sessions │  会话历史（从 Redis 归档）
   └────┬─────┘
        │ 1:N
   ┌────▼──────┐
   │  memories │  长期记忆（用户偏好、经验教训）
   └────┬─────┘
        │ 1:N
   ┌────▼──────┐
   │ tool_logs │  工具调用日志（审计、成本分析）
   └────┬─────┘
        │ 1:N
   ┌────▼──────┐
   │ eval_logs │  评测记录（成功率、延迟）
   └──────────┘
```

---

## 4. 完整 Schema 设计（PostgreSQL）

```sql
-- ============================================
-- 用户表
-- ============================================
CREATE TABLE users (
    id            VARCHAR(64) PRIMARY KEY,         -- UUID
    email         VARCHAR(255) UNIQUE,
    display_name  VARCHAR(128),
    preferences   JSONB DEFAULT '{}',              -- {"preferred_lang":"Python","style":"Google"}
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- 会话表（Redis 归档）
-- ============================================
CREATE TABLE sessions (
    id              VARCHAR(64) PRIMARY KEY,       -- session_id
    user_id         VARCHAR(64) NOT NULL REFERENCES users(id),
    goal            TEXT,                          -- "成都五日游，预算5000"
    current_state   VARCHAR(32),                   -- 终态：DONE / FAILED / TIMEOUT
    plan            JSONB,                         -- Planner 产出的 Task Graph
    context         JSONB,                         -- 最终上下文快照
    state_history   JSONB,                         -- 状态变更历史
    total_tokens     INT DEFAULT 0,                -- 消耗的 Token 总数
    total_cost       DECIMAL(10, 6) DEFAULT 0,     -- 消耗的费用
    total_latency_ms INT DEFAULT 0,                -- 总延迟（毫秒）
    tool_calls_count INT DEFAULT 0,                -- 工具调用次数
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_created ON sessions(created_at DESC);

-- ============================================
-- 长期记忆表
-- ============================================
CREATE TABLE memories (
    id          SERIAL PRIMARY KEY,
    user_id     VARCHAR(64) NOT NULL REFERENCES users(id),
    memory_type VARCHAR(32) NOT NULL,              -- 'preference' | 'lesson' | 'pattern'
    key         VARCHAR(255) NOT NULL,             -- 记忆的键
    value       JSONB NOT NULL,                    -- 记忆的值
    importance  FLOAT DEFAULT 0.5,                 -- 重要性 0-1（用于检索排序）
    access_count INT DEFAULT 0,                    -- 被访问次数
    last_accessed TIMESTAMP,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(user_id, memory_type, key)
);

CREATE INDEX idx_memories_user_type ON memories(user_id, memory_type);

-- ============================================
-- 工具调用日志表（审计 + 成本分析）
-- ============================================
CREATE TABLE tool_logs (
    id          SERIAL PRIMARY KEY,
    session_id  VARCHAR(64) NOT NULL,
    user_id     VARCHAR(64) NOT NULL,
    tool_name   VARCHAR(128) NOT NULL,
    input       JSONB,
    output      JSONB,
    status      VARCHAR(16) NOT NULL,              -- 'success' | 'error' | 'timeout'
    latency_ms  INT,
    tokens_used  INT DEFAULT 0,
    cost         DECIMAL(10, 6) DEFAULT 0,
    error_msg   TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tool_logs_session ON tool_logs(session_id);
CREATE INDEX idx_tool_logs_user ON tool_logs(user_id);
CREATE INDEX idx_tool_logs_created ON tool_logs(created_at DESC);

-- ============================================
-- 评测记录表
-- ============================================
CREATE TABLE eval_logs (
    id            SERIAL PRIMARY KEY,
    session_id    VARCHAR(64),
    eval_type     VARCHAR(32) NOT NULL,            -- 'accuracy' | 'latency' | 'success' | 'cost'
    metric_name   VARCHAR(64) NOT NULL,
    metric_value  FLOAT NOT NULL,
    metadata      JSONB,
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_eval_logs_type ON eval_logs(eval_type, created_at DESC);
```

---

## 5. 长期记忆的读写

```python
class LongTermMemoryStore:
    def __init__(self, db_conn):
        self.db = db_conn
    
    def remember(self, user_id: str, memory_type: str,
                 key: str, value: dict, importance: float = 0.5):
        """写入一条长期记忆"""
        self.db.execute("""
            INSERT INTO memories (user_id, memory_type, key, value, importance)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, memory_type, key)
            DO UPDATE SET value = %s, importance = %s, updated_at = NOW()
        """, [user_id, memory_type, key, json.dumps(value), importance,
              json.dumps(value), importance])
    
    def recall(self, user_id: str, memory_type: str = None, 
               limit: int = 10) -> list:
        """检索用户记忆，按重要性排序"""
        query = """
            SELECT key, value, importance, access_count
            FROM memories
            WHERE user_id = %s
        """
        params = [user_id]
        if memory_type:
            query += " AND memory_type = %s"
            params.append(memory_type)
        query += " ORDER BY importance DESC, last_accessed DESC LIMIT %s"
        params.append(limit)
        
        results = self.db.fetch_all(query, params)
        
        # 更新访问计数
        for row in results:
            self.db.execute("""
                UPDATE memories SET access_count = access_count + 1,
                last_accessed = NOW() WHERE user_id = %s AND key = %s
            """, [user_id, row['key']])
        
        return results
    
    def forget(self, user_id: str, key: str):
        """删除一条记忆"""
        self.db.execute(
            "DELETE FROM memories WHERE user_id = %s AND key = %s",
            [user_id, key]
        )
    
    def should_remember(self, event_type: str, 
                        confidence: float) -> bool:
        """判断是否值得写入长期记忆
        
        写入条件：
        - 用户明确表达的偏好 → 必存
        - 可复用的经验教训 → 必存
        - 重复出现3次以上的模式 → 必存
        - 一次性信息 → 不存
        """
        if event_type in ["user_preference", "lesson_learned"]:
            return True
        if event_type == "recurring_pattern" and confidence > 0.8:
            return True
        return False


# 使用示例
store = LongTermMemoryStore(pg_conn)

# 用户在旅游规划中表达了偏好
store.remember("u_abc", "preference", "travel_style", {
    "pace": "relaxed",           # 悠闲
    "interests": ["历史", "美食"],
    "budget_level": "mid_range",
    "dislikes": ["人太多的景点", "跟团游"]
}, importance=0.9)

# 下次规划时召回
prefs = store.recall("u_abc", "preference")
# → Agent 根据历史偏好自动调整规划
```

---

## 6. 成本分析查询

```sql
-- 按天统计 Token 消耗
SELECT 
    DATE(created_at) as day,
    SUM(tokens_used) as total_tokens,
    SUM(cost) as total_cost,
    COUNT(*) as tool_calls
FROM tool_logs
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY day
ORDER BY day DESC;

-- 找最贵的工具
SELECT 
    tool_name,
    COUNT(*) as calls,
    AVG(latency_ms) as avg_latency_ms,
    SUM(cost) as total_cost
FROM tool_logs
GROUP BY tool_name
ORDER BY total_cost DESC;

-- 找最常失败的工具
SELECT 
    tool_name,
    COUNT(*) FILTER (WHERE status = 'error') as errors,
    COUNT(*) as total,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'error') / COUNT(*), 1) as error_rate
FROM tool_logs
GROUP BY tool_name
HAVING COUNT(*) FILTER (WHERE status = 'error') > 0
ORDER BY error_rate DESC;
```

---

## 7. 常见错误

| 错误 | 后果 | 正确做法 |
|------|------|---------|
| 只用 Redis 不归档 | 历史数据全部丢失 | 会话完成/过期后归档到 PG |
| Schema 用 TEXT 存一切 | 无法查询、无法分析 | 结构化字段用对应类型，非结构化用 JSONB |
| 不建索引 | 查询越来越慢 | user_id、created_at、session_id 必建索引 |
| 生产用 SQLite | 并发写锁死 | 生产用 PostgreSQL |
| 记忆永不删除 | 数据库无限膨胀 | 低重要性记忆定期清理 |

---

## 实践任务

**任务1**：用 PostgreSQL（或 SQLite 先练手）创建上述 Schema，插入 3 条模拟数据到每张表，运行 3 条聚合查询。

**任务2**：实现 LongTermMemoryStore 的 should_remember 逻辑——什么情况下旅游 Agent 的交互值得写入长期记忆？列出至少 5 个具体场景。

**任务3**：用 SQL 回答以下问题（基于模拟数据）：
- 过去一周哪个用户的 Token 消耗最高？
- 哪个工具的失败率超过 5%？
- 平均每次会话的延迟是多少？

---

→ [03-Async-Tasks.md](./03-Async-Tasks.md)
