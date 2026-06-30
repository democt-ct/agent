1

# 03 - State Machine — 状态机

> 学习目标：理解状态机在企业Agent中的核心地位，掌握状态建模和转换规则设计

---

## 1. 为什么需要 State Machine

Demo Agent 不需要状态机——请求来了处理，处理完结束。

Production Agent 完全不一样：

```
用户："帮我订一张去成都的机票"
Agent："找到了3个航班，你要哪个？"      ← 不能结束，得等用户选
用户："第二个"
Agent："好的，CA1234，确认吗？"          ← 还在等确认
用户："确认"
Agent："已预订，还需要订酒店吗？"        ← 继续
```

这就是状态——Agent 必须记住「现在在等什么」。

> **核心认知**：Demo 是 stateless，Product 是 stateful。状态机让 Agent 知道"我是谁、我在哪、我在等什么"。

---

## 2. 状态机的基本元素

```
┌──────────────────────────────────────────────┐
│  State Machine = States + Transitions + Events│
│                                               │
│  States:      系统可能处于的所有状态           │
│  Transitions: 什么事件触发什么状态转换         │
│  Events:      触发状态转换的外部/内部事件      │
│  Guards:      转换前的条件检查                 │
│  Actions:     转换时执行的副作用               │
└──────────────────────────────────────────────┘
```

---

## 3. Agent 通用状态模型

```
                              ┌──────────┐
                              │          │
                    ┌────────►│  IDLE    │◄─────────┐
                    │         │  空闲     │          │
                    │         └─────┬─────┘          │
                    │               │                │
                    │         收到用户请求             │
                    │               │                │
                    │         ┌─────▼─────┐          │
                    │         │           │          │
                    │         │ PLANNING  │          │
                    │         │  规划中    │          │
                    │         └─────┬─────┘          │
                    │               │                │
                    │          规划完成               │
                    │               │                │
                    │         ┌─────▼─────┐          │
                    │         │           │          │
                    │         │ EXECUTING │          │
                    │         │  执行中    │          │
                    │         └──┬───┬───┘          │
                    │            │   │              │
                    │      成功  │   │ 需要用户输入   │
                    │            │   │              │
                    │    ┌───────┘   └──────┐       │
                    │    ▼                  ▼       │
                    │ ┌──────┐         ┌──────────┐ │
                    │ │      │         │          │ │
                    │ │ DONE │         │ WAITING  │ │
                    │ │ 完成 │         │  等待中   │ │
                    │ └──┬───┘         └────┬─────┘ │
                    │    │                  │       │
                    │    │            收到用户回复   │
                    │    │                  │       │
                    │    │            ┌─────▼─────┐ │
                    │    │            │           │ │
                    │    └────────────┤ RESUMING  │ │
                    │                 │  恢复执行  │─┘
                    │                 └─────┬─────┘
                    │                       │
                    │                  ┌────┴────┐
                    │                  │         │
                    │             ┌────▼──┐  ┌──▼────┐
                    │             │       │  │       │
                    │             │RETRY  │  │FAILED │
                    │             │  重试  │  │  失败  │
                    │             └───┬───┘  └───────┘
                    │                 │
                    │            重试成功
                    │                 │
                    └─────────────────┘
```

---

## 4. 状态定义

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime

class IllegalTransitionError(Exception):
    """非法状态转换异常"""

class SessionNotFoundError(Exception):
    """会话不存在（恢复时发现无记录）"""

class AgentState(Enum):
    IDLE      = "idle"       # 空闲，等待输入
    PLANNING  = "planning"   # 正在规划
    EXECUTING = "executing"  # 正在执行
    WAITING   = "waiting"    # 等待用户输入/确认
    RESUMING  = "resuming"   # 收到用户回复，恢复执行
    RETRYING  = "retrying"   # 失败后重试
    FAILED    = "failed"     # 不可恢复的失败
    DONE      = "done"       # 完成

class StateTransition(Enum):
    """合法转换"""
    TRANSITIONS = {
        AgentState.IDLE:      [AgentState.PLANNING],
        AgentState.PLANNING:  [AgentState.EXECUTING, AgentState.FAILED],
        AgentState.EXECUTING: [AgentState.DONE, AgentState.WAITING, 
                               AgentState.RETRYING, AgentState.FAILED],
        AgentState.WAITING:   [AgentState.RESUMING, AgentState.FAILED],
        AgentState.RESUMING:  [AgentState.EXECUTING, AgentState.FAILED],
        AgentState.RETRYING:  [AgentState.EXECUTING, AgentState.FAILED],
        AgentState.FAILED:    [AgentState.IDLE],   # 重置
        AgentState.DONE:      [AgentState.IDLE],   # 完成，等待新任务
    }
```

---

## 5. 完整 State Machine 实现

```python
@dataclass
class AgentStateMachine:
    current_state: AgentState = AgentState.IDLE
    session_id: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    history: list = field(default_factory=list)  # 状态变更记录
  
    def can_transition(self, to_state: AgentState) -> bool:
        """检查状态转换是否合法"""
        allowed = StateTransition.TRANSITIONS.get(self.current_state, [])
        return to_state in allowed
  
    def transition(self, to_state: AgentState, 
                   event: str, metadata: Optional[Dict] = None) -> bool:
        """执行状态转换"""
        if not self.can_transition(to_state):
            raise IllegalTransitionError(
                f"Cannot transition from {self.current_state.value} "
                f"to {to_state.value}"
            )
    
        old_state = self.current_state
        self.current_state = to_state
    
        # 记录变更
        entry = {
            "timestamp": datetime.now().isoformat(),
            "from":      old_state.value,
            "to":        to_state.value,
            "event":     event,
            "metadata":  metadata or {}
        }
        self.history.append(entry)
    
        # 进入特定状态的钩子
        self._on_enter(to_state)
    
        return True
  
    def _on_enter(self, state: AgentState):
        """状态进入时的副作用"""
        match state:
            case AgentState.WAITING:
                # 设置等待超时
                self.context["wait_started_at"] = datetime.now()
                self.context["wait_timeout"] = 300  # 5分钟
        
            case AgentState.FAILED:
                # 记录失败信息供调试
                self.context["failed_at_state"] = self.history[-2]["from"]
        
            case AgentState.DONE:
                # 触发结果持久化
                self.context["completed_at"] = datetime.now()
  
    def get_wait_reason(self) -> Optional[str]:
        """当前在等待用户什么"""
        if self.current_state != AgentState.WAITING:
            return None
        return self.context.get("wait_reason", "等待用户输入")
  
    def is_terminal(self) -> bool:
        """是否处于终态"""
        return self.current_state in [AgentState.DONE, AgentState.FAILED]
```

---

## 6. 旅游 Agent 的实际状态流转

```python
# 场景：用户预订成都五日游

# ① IDLE → PLANNING
sm.transition(AgentState.PLANNING, "user_request",
    {"goal": "成都五日游", "budget": 5000})

# ② PLANNING → EXECUTING
sm.transition(AgentState.EXECUTING, "plan_ready",
    {"tasks": 8, "estimated_time": "5min"})

# ③ EXECUTING → WAITING（航班有多个选择，需要用户选）
sm.transition(AgentState.WAITING, "need_user_choice",
    {"wait_reason": "请从3个航班中选择一个",
     "options": ["CA1234 ¥1200", "MU5678 ¥980", "CZ9012 ¥1500"]})

# ... 用户选了第二个 ...

# ④ WAITING → RESUMING
sm.transition(AgentState.RESUMING, "user_replied",
    {"choice": "MU5678"})

# ⑤ RESUMING → EXECUTING（继续执行）
sm.transition(AgentState.EXECUTING, "resume",
    {"next_task": "book_flight", "flight": "MU5678"})

# ⑥ EXECUTING → DONE
sm.transition(AgentState.DONE, "all_tasks_complete",
    {"total_cost": 4600, "tasks_completed": 8})
```

---

## 7. 超时与心跳

WAITING 状态不能无限等待——用户可能走了。需要超时机制。

```python
import asyncio

class StateMachineWithTimeout(AgentStateMachine):
    async def wait_with_timeout(self, timeout_seconds: int = 300):
        """等待用户输入，超时自动转为失败"""
        wait_start = datetime.now()
    
        while self.current_state == AgentState.WAITING:
            elapsed = (datetime.now() - wait_start).total_seconds()
        
            if elapsed > timeout_seconds:
                self.transition(AgentState.FAILED, "timeout",
                    {"reason": f"等待用户输入超时（{timeout_seconds}s）"})
                return {"status": "timeout", 
                        "message": "等待超时，任务已取消"}
        
            await asyncio.sleep(5)  # 每5秒检查一次
    
        return {"status": "ok"}

# ⚠️ 生产环境建议：用 Redis key-expiry 事件代替轮询
# 
# SETEX session:{id}:wait_timeout 300 "waiting"
# 配置 Redis notify-keyspace-events Ex
# 订阅 __keyevent@*__:expired 事件
# → 超时自动触发回调，无需轮询，更省资源


# 使用
async def handle_waiting_state(sm):
    if sm.current_state == AgentState.WAITING:
        reason = sm.get_wait_reason()
        # 通知用户
        await send_message(f"⏳ {reason}")
    
        # 等待，带超时
        result = await sm.wait_with_timeout(timeout_seconds=300)
    
        if result["status"] == "timeout":
            await send_message("⏰ 等待超时。随时可以重新开始。")
```

---

## 8. 状态持久化

Production 中，状态必须存到外部存储，不能只在内存。

```python
import json
import redis

class PersistentStateMachine(AgentStateMachine):
    def __init__(self, session_id: str, redis_client: redis.Redis):
        super().__init__()
        self.session_id = session_id
        self.redis = redis_client
        self._load_or_init()
  
    def _load_or_init(self):
        """从 Redis 恢复状态（如果有的话）"""
        key = f"sm:{self.session_id}"
        data = self.redis.get(key)
        if data:
            saved = json.loads(data)
            self.current_state = AgentState(saved["current_state"])
            self.context = saved["context"]
            self.history = saved["history"]
  
    def transition(self, to_state, event, metadata=None):
        result = super().transition(to_state, event, metadata)
        self._persist()  # 每次转换后持久化
        return result
  
    def _persist(self):
        """将完整状态写入 Redis"""
        key = f"sm:{self.session_id}"
        data = {
            "current_state": self.current_state.value,
            "context":       self.context,
            "history":       self.history
        }
        self.redis.setex(key, 3600, json.dumps(data, default=str))
  
    @classmethod
    def resume(cls, session_id: str, redis_client: redis.Redis):
        """恢复一个已存在的会话"""
        sm = cls(session_id, redis_client)
        if sm.current_state == AgentState.IDLE:
            raise SessionNotFoundError(f"No session found: {session_id}")
        return sm

# 使用场景：用户关闭浏览器后又打开
sm = PersistentStateMachine.resume("sess_abc123", redis_client)
print(f"当前状态: {sm.current_state.value}")  # 例如：waiting
print(f"等待原因: {sm.get_wait_reason()}")     # 例如：请从3个航班中选择一个
```

---

## 9. 常见错误

| 错误               | 后果                   | 正确做法                          |
| ------------------ | ---------------------- | --------------------------------- |
| 状态不持久化       | 服务重启，用户进度全丢 | Redis/PG 持久化，每次转换后写入   |
| 非法状态转换没拦截 | 状态混乱，难以调试     | 定义合法转换表，转换前校验        |
| 没有超时机制       | WAITING 状态永远挂着   | 所有等待状态设 TTL                |
| 状态粒度太粗       | 状态内包含太多不同情况 | 一个状态 = 一种明确的行为模式     |
| 状态粒度太细       | 转换爆炸，管理困难     | 合并相似状态，用 context 区分细节 |

---

## 实践任务

**任务1**：为你的旅游 Agent 画完整的状态机图——至少包含 IDLE / PLANNING / EXECUTING / WAITING / DONE / FAILED 六个状态，标注每个转换的触发事件。

**任务2**：找出你旅游 Agent 中所有 WAITING 场景（需要等待用户输入的节点），为每个场景写清楚：等什么、等多久超时、超时后怎么办。

**任务3**：实现一个带持久化的 State Machine，使用 Redis（或本地 JSON 文件）。测试场景：

```python
# ① 启动，状态变为 EXECUTING
# ② 模拟服务重启
# ③ 从 Redis 恢复状态
# ④ 验证状态完全一致
# ⑤ 继续执行
```

---

→ [04-Router.md](./04-Router.md)
