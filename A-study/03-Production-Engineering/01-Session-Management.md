# 01 - Session Management — 会话管理

> 学习目标：理解为什么不能用全局变量存状态，掌握 Redis 会话管理的完整生命周期

---

## 1. Demo 的做法（为什么不行）

```python
# ❌ Demo 做法：全局字典
sessions = {}  # 进程内存

def handle_request(user_id, message):
    if user_id not in sessions:
        sessions[user_id] = {"history": [], "state": "idle"}
    
    session = sessions[user_id]
    # ... 处理 ...
    session["history"].append(message)
```

三个致命问题：

```
问题1：服务重启 → sessions 字典清空 → 所有用户进度丢失
问题2：多实例部署 → 实例A存的session，实例B看不见
问题3：内存泄漏   → 永不清理的过期session撑爆内存
```

> **核心认知**：Session 必须外存（Redis），必须带 TTL，必须跨实例共享。

---

## 2. Redis Session 的完整设计

### 数据结构

```python
session_key = f"agent:session:{session_id}"

session_data = {
    "user_id":         "u_abc123",
    "current_state":   "WAITING",           # State Machine 当前状态
    "context": {
        "goal":        "成都五日游",
        "budget":      5000,
        "checkpoint":  {                     # 中断恢复点
            "step":    "select_flight",
            "snapshot": {...}
        }
    },
    "history": [                            # 状态变更历史
        {"from": "IDLE", "to": "PLANNING", "at": "2026-07-15T10:00:00"},
        {"from": "PLANNING", "to": "EXECUTING", "at": "..."}
    ],
    "plan": {                               # Planner 产出的 Task Graph
        "tasks": [...],
        "completed": [1, 2]
    },
    "created_at": "2026-07-15T10:00:00",
    "last_active": "2026-07-15T10:05:00",
}
```

### TTL 设计

```
活跃会话：TTL = 30分钟（每次交互刷新）
空闲会话：TTL = 5分钟（长时间不活动自动过期）
已完成会话：保留24小时（供用户查看历史），之后归档到 PostgreSQL
```

---

## 3. Session Manager 完整实现

```python
import json
import uuid
import redis
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

@dataclass
class Session:
    session_id: str
    user_id: str
    current_state: str = "IDLE"
    context: Dict[str, Any] = field(default_factory=dict)
    history: list = field(default_factory=list)
    plan: Optional[Dict] = None
    created_at: str = ""
    last_active: str = ""

class SessionManager:
    ACTIVE_TTL  = 30 * 60      # 30分钟（活跃）
    IDLE_TTL    = 5 * 60       # 5分钟（空闲）
    ARCHIVE_TTL = 24 * 60 * 60 # 24小时（完成归档）
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    # ──── 创建 ────
    def create(self, user_id: str) -> Session:
        session = Session(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            current_state="IDLE",
            created_at=datetime.now().isoformat(),
            last_active=datetime.now().isoformat()
        )
        self._save(session, self.ACTIVE_TTL)
        return session
    
    # ──── 读取 ────
    def get(self, session_id: str) -> Optional[Session]:
        key = f"agent:session:{session_id}"
        data = self.redis.get(key)
        if not data:
            return None
        return self._deserialize(json.loads(data))
    
    # ──── 更新 ────
    def update(self, session: Session):
        session.last_active = datetime.now().isoformat()
        self._save(session, self.ACTIVE_TTL)
    
    def update_state(self, session_id: str, new_state: str,
                     metadata: Optional[Dict] = None):
        """更新状态机状态（高频操作，优化为直接HSET而非全量序列化）"""
        key = f"agent:session:{session_id}"
        self.redis.hset(key, "current_state", new_state)
        self.redis.hset(key, "last_active", datetime.now().isoformat())
        self.redis.expire(key, self.ACTIVE_TTL)
        
        if metadata:
            self.redis.hset(key, "context",
                json.dumps(self._merge_context(key, metadata)))
    
    def update_checkpoint(self, session_id: str, step: str, snapshot: dict):
        """保存中断检查点"""
        key = f"agent:session:{session_id}"
        checkpoint = json.dumps({"step": step, "snapshot": snapshot})
        self.redis.hset(key, "checkpoint", checkpoint)
        self.redis.expire(key, self.ACTIVE_TTL)
    
    # ──── 删除 ────
    def delete(self, session_id: str):
        self.redis.delete(f"agent:session:{session_id}")
    
    def archive(self, session: Session):
        """完成/过期后归档到 PostgreSQL 长期存储"""
        # 写入 PostgreSQL（见 02-Database-Design）
        # db.sessions.insert(session)
        # 然后从 Redis 删除
        self.delete(session.session_id)
    
    # ──── 用户会话列表 ────
    def list_user_sessions(self, user_id: str) -> list:
        """获取用户的所有活跃会话（支持多设备恢复）"""
        pattern = f"agent:session:*"
        sessions = []
        for key in self.redis.scan_iter(match=pattern):
            data = self.redis.hgetall(key)
            if data.get(b"user_id", b"").decode() == user_id:
                sessions.append(self._deserialize({
                    k.decode(): v.decode() for k, v in data.items()
                }))
        return sessions
    
    # ──── 内部方法 ────
    def _save(self, session: Session, ttl: int):
        key = f"agent:session:{session.session_id}"
        self.redis.setex(key, ttl, json.dumps(self._serialize(session)))
    
    def _serialize(self, session: Session) -> dict:
        return {
            "session_id":    session.session_id,
            "user_id":       session.user_id,
            "current_state": session.current_state,
            "context":       session.context,
            "history":       session.history,
            "plan":          session.plan,
            "created_at":    session.created_at,
            "last_active":   session.last_active,
        }
    
    def _deserialize(self, data: dict) -> Session:
        return Session(**data)
    
    def _merge_context(self, key, metadata):
        existing = json.loads(self.redis.hget(key, "context") or "{}")
        existing.update(metadata)
        return existing
```

---

## 4. 跨实例 Session 共享

```
                   ┌──────────────┐
                   │   Nginx LB   │
                   └──┬───┬───┬──┘
                      │   │   │
          ┌───────────┘   │   └───────────┐
          ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │ Agent-1  │   │ Agent-2  │   │ Agent-3  │
    │ 实例 A   │   │ 实例 B   │   │ 实例 C   │
    └────┬─────┘   └────┬─────┘   └────┬─────┘
         │              │              │
         └──────────────┼──────────────┘
                        │
                 ┌──────▼──────┐
                 │    Redis    │  ← 唯一 Session 存储
                 │  (可配置    │
                 │   Sentinel) │
                 └─────────────┘
```

关键：无论请求落到哪个实例，都读同一个 Redis → 用户无感知。

---

## 5. 多设备场景

用户在手机上开始规划，想换到电脑继续：

```python
# 手机端
session = sm.create("u_abc")
# 开始规划... 状态变为 WAITING（等用户选航班）

# --- 用户换到电脑 ---

# 电脑端
sessions = sm.list_user_sessions("u_abc")
# → [{"session_id": "sess_xxx", "current_state": "WAITING",
#     "summary": "成都五日游，等待选择航班"}]

# 恢复
session = sm.get("sess_xxx")
print(f"欢迎回来！你之前在：{session.current_state}")
print(f"等待原因：{session.context['checkpoint']['step']}")
```

---

## 6. Session 生命周期

```
[创建] ──→ [活跃] ──→ [空闲] ──→ [过期/归档]
  │          │          │
  │    每次交互刷新TTL   │ 5分钟无操作
  │          │          │
  │          └──────────┘
  │
  └── TTL=30min（活跃期）
      
[完成] ──→ [归档]
              │
         Redis删除，写入PostgreSQL
         保留24小时可查看
```

---

## 7. 常见错误

| 错误 | 后果 | 正确做法 |
|------|------|---------|
| 用进程内存存 Session | 重启丢失、多实例不共享 | Redis 外存 |
| TTL 不刷新 | 用户在操作，Session 却过期了 | 每次交互刷新 TTL |
| 不设 TTL | 过期 Session 永不清除 | 所有 Session 设 max TTL |
| 全量读写整个 Session | 高频状态更新性能差 | 高频字段用 HSET 原子更新 |
| JSON 序列化 datetime | datetime 不可直接序列化 | 用 `.isoformat()` 统一 |

---

## 实践任务

**任务1**：用 Redis 实现 SessionManager，支持 create/get/update/delete。测试：创建→写入状态→模拟重启（flush redis）→验证数据还在。

**任务2**：实现"多设备恢复"场景——用同一个 user_id 创建两个 session，然后 list_user_sessions，选择一个恢复。

**任务3**：设计 Session TTL 策略——你的旅游 Agent 中，什么场景设什么 TTL？画出 Session 从创建到归档的完整时间线。

---

→ [02-Database-Design.md](./02-Database-Design.md)
