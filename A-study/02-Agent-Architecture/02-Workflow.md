# 02 - Workflow — 工作流引擎

> 学习目标：理解 Workflow 的核心抽象（State + Transition），掌握条件分支、并行和循环

---

## 1. 什么是 Workflow

Planner 产出的是**静态的**任务列表。Workflow 负责**动态的**执行过程——什么时候走哪条路、什么条件下跳转、出错后怎么恢复。

```
Planner:    "做什么"（What）
Workflow:   "怎么做、按什么顺序、条件是什么"（How）
State:      "现在到哪了"（Where）
```

> ⚠️ **Planner vs Workflow 辨析**：初学者最容易把两者混为一谈。Planner 只产出 Task Graph（一张静态图），它不关心执行。Workflow 拿着这张图去执行——遇到条件分叉时走哪边、失败了重试还是跳过。一句话：**Planner 画地图，Workflow 开车。**

三者协作：

```
Planner 产出 Task Graph
    ↓
Workflow Engine 驱动执行
    ↓  依赖
State Machine 追踪状态
```

---

## 2. Workflow 的唯一公式

```
Workflow = State + Transition
```

不管用什么框架，本质都一样。你只需要定义两件事：

```python
# 1. State — 当前状态是什么
state = {
    "current_step": "booking_flight",
    "completed": ["understand_goal", "check_budget"],
    "data": {"departure": "北京", "destination": "成都", "budget": 5000}
}

# 2. Transition — 什么条件下从当前状态跳到下一个状态
def next_state(current_state, action_result):
    if action_result.success:
        return "next_step"       # 正常 → 下一步
    elif action_result.needs_input:
        return "ask_user"        # 缺信息 → 问用户
    else:
        return "error_handler"   # 失败 → 错误处理
```

---

## 3. 三种基本转换模式

### 顺序（Sequence）

```
Step1 → Step2 → Step3 → Done
```

```python
workflow = [
    {"step": "check_budget",    "next": "search_flights"},
    {"step": "search_flights",  "next": "book_flight"},
    {"step": "book_flight",     "next": "search_hotel"},
    {"step": "search_hotel",    "next": "book_hotel"},
    {"step": "book_hotel",      "next": "done"},
]
```

### 条件分支（Conditional）

```
               ┌─→ Step2a ─→ Step3
Step1 ─→ 判断 ─┤
               └─→ Step2b ─→ Step4
```

```python
workflow = [
    {
        "step": "search_transport",
        "branches": [
            {
                "condition": lambda ctx: ctx["budget"] > 3000,
                "next": "search_flights"     # 预算够 → 飞机
            },
            {
                "condition": lambda ctx: ctx["budget"] <= 3000,
                "next": "search_trains"      # 预算紧 → 高铁
            }
        ],
        "default": "search_trains"           # 兜底
    }
]
```

### 并行（Parallel）

```
              ┌─→ Step2a ─┐
Step1 ─→ fork ┤            ├─→ join → Step3
              └─→ Step2b ─┘
```

```python
parallel_tasks = [
    {"step": "search_hotels",     "depends_on": ["plan_route"]},
    {"step": "search_restaurants","depends_on": ["plan_route"]},
    {"step": "search_weather",    "depends_on": ["plan_route"]},
]
# 三个任务依赖相同的前置步骤，可以并行执行
# join 点等所有完成后才继续
```

---

## 4. 一个完整的旅游 Workflow

```
                          [Start]
                             │
                    [理解用户需求]
                             │
                    ┌── 信息是否完整？──┐
                    │ 否               │ 是
                    ▼                  ▼
            [追问用户]          [Planner 分解任务]
                    │                  │
                    └────→ 回到理解 ──→ │
                                       │
                              ┌─→ [查天气] ─┐
                              │             │
                    [查交通] ─┼─→ [订机票] ─┼─→ [订酒店]
                              │             │
                              └─→ [查攻略] ─┘
                                       │
                               ┌── 预算是否超支？──┐
                               │ 是               │ 否
                               ▼                  ▼
                       [调整方案]           [生成行程]
                               │                  │
                               └────→ 重新检查 ──→ │
                                                  ▼
                                            [用户确认]
                                                  │
                                          ┌── 是否满意？──┐
                                          │ 否           │ 是
                                          ▼              ▼
                                  [修改行程]         [Done]
                                          │
                                          └──→ 回到确认
```

---

## 5. 最简 Workflow Engine 实现

```python
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"

class WorkflowStep:
    def __init__(self, name: str, action: Callable,
                 next_step: Optional[str] = None,
                 branches: Optional[List[Dict]] = None,
                 on_error: Optional[str] = None):
        self.name = name
        self.action = action          # 要执行的函数
        self.next_step = next_step    # 默认下一步
        self.branches = branches or [] # 条件分支
        self.on_error = on_error       # 出错时跳转

class WorkflowEngine:
    def __init__(self):
        self.steps: Dict[str, WorkflowStep] = {}
        self.state: Dict[str, Any] = {}
  
    def add_step(self, step: WorkflowStep):
        self.steps[step.name] = step
  
    def run(self, start_step: str, context: dict):
        self.state = {"context": context, "history": []}
        current = start_step
      
        while current and current != "done":
            step = self.steps.get(current)
            if not step:
                raise ValueError(f"Step '{current}' not found")
          
            # 执行当前步骤
            try:
                result = step.action(self.state)
                self.state["history"].append({
                    "step": current, "result": result
                })
            except Exception as e:
                if step.on_error:
                    current = step.on_error
                    continue
                raise
          
            # 决定下一步
            next_step = None
          
            # 先检查条件分支
            for branch in step.branches:
                if branch["condition"](self.state):
                    next_step = branch["next"]
                    break
          
            # 没有匹配的分支，用默认下一步
            if next_step is None:
                next_step = step.next_step
          
            current = next_step
      
        return self.state


# 使用示例：旅游Agent的Workflow
def plan_trip(state):
    goal = state["context"]["user_input"]
    plan = llm.decompose(goal)
    state["plan"] = plan
    return {"status": "ok", "tasks": len(plan)}

def book_flight(state):
    # 实际调用机票搜索工具
    return {"status": "ok", "flight": "CA1234"}

workflow = WorkflowEngine()
workflow.add_step(WorkflowStep(
    name="plan", action=plan_trip, next_step="book"
))
workflow.add_step(WorkflowStep(
    name="book", action=book_flight, next_step="done",
    on_error="retry"
))
workflow.add_step(WorkflowStep(
    name="retry", 
    action=lambda s: {"status": "retrying"},
    branches=[{
        "condition": lambda s: s.get("retry_count", 0) < 3,
        "next": "book"
    }],
    next_step="done"
))
```

---

## 6. 业界 Workflow 框架对比

| 框架                | 特点                               | 适用场景           |
| ------------------- | ---------------------------------- | ------------------ |
| **LangGraph** | StateGraph + 条件边，LangChain生态 | LLM-heavy workflow |
| **Temporal**  | 企业级，持久化执行，自动重试       | 生产级长流程       |
| **Mastra**    | TypeScript，简洁API，built-in eval | TS全栈项目         |
| **Prefect**   | Python-native，数据流清晰          | 数据处理pipeline   |
| **自建**      | 你对 formula 的理解                | 学习目的，理解本质 |

> ⚠️ 学框架前，先理解 `Workflow = State + Transition`。框架只是这个公式的某种实现。

---

## 7. Workflow 常见模式

### 重试模式（Retry）

```python
# 方式一：直接用 WorkflowStep 的 on_error + branches
workflow.add_step(WorkflowStep(
    name="call_external_api",
    action=call_api,
    next_step="process_result",
    on_error="retry_handler"      # 失败跳转到这里
))

workflow.add_step(WorkflowStep(
    name="retry_handler",
    action=lambda s: s.update({"retry_count": s.get("retry_count", 0) + 1}),
    branches=[
        {
            # 还能重试 → 回去再试
            "condition": lambda s: s.get("retry_count", 0) < 3,
            "next": "call_external_api"
        }
    ],
    next_step="fallback_handler"   # 重试耗尽 → 降级
))
```

```python
# 方式二：通用的独立重试函数（不依赖 WorkflowEngine）
def retry_with_backoff(fn, max_retries=3, base_delay=1):
    """指数退避重试，适合包裹任何可能失败的调用"""
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            if attempt == max_retries - 1:
                raise  # 最后一次也失败，抛出
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)
```

### 超时模式（Timeout）

```python
def execute_with_timeout(step, state, timeout_seconds=30):
    import signal
    # 或使用 asyncio.wait_for
    try:
        result = asyncio.wait_for(
            step.action(state), 
            timeout=timeout_seconds
        )
        return result
    except asyncio.TimeoutError:
        return {"status": "timeout", "next": step.on_error or "done"}
```

### Saga 模式（补偿事务）

长流程中途失败时，需要回滚已完成的操作。

```python
saga_steps = {
    "book_flight": {
        "action":   lambda: airline.book("CA1234"),
        "compensate": lambda: airline.cancel("CA1234"),  # 回滚
    },
    "book_hotel": {
        "action":   lambda: hotel.book("锦江宾馆"),
        "compensate": lambda: hotel.cancel("锦江宾馆"),
    },
}

def run_saga(steps, state):
    executed = []
    for name, step in steps.items():
        try:
            result = step["action"]()
            executed.append(name)
        except Exception:
            # 回滚所有已执行的步骤
            for name in reversed(executed):
                steps[name]["compensate"]()
            raise
```

---

## 8. 常见错误

| 错误               | 后果                       | 正确做法                              |
| ------------------ | -------------------------- | ------------------------------------- |
| 没有条件分支       | 所有路径硬编码             | 根据状态动态路由                      |
| 没有错误处理       | 一步失败全流程崩           | 每个关键步骤设 on_error               |
| 忽略补偿逻辑       | 订了机票酒店订不到，钱花了 | 长事务用 Saga                         |
| Workflow 太复杂    | 自己都看不懂流转           | 分拆成子 Workflow                     |
| 状态和逻辑混在一起 | 调试地狱                   | State 单独管理，Transition 只读 State |

---

## 实践任务

**任务1**：把你旅游 Agent 的完整流程画成 Workflow 图——包含至少一个条件分支和一个并行点。

**任务2**：识别你的 Workflow 中哪些步骤可能失败，为每个失败点设计重试策略和兜底方案。

**任务3**：用代码实现一个最小 Workflow Engine（不要用框架），包含顺序、条件分支和错误处理。用旅游 Agent 的一个子流程测试它。

```python
# 起点：接收用户旅行需求
# 测试场景：
#   正常路径：需求明确 → 规划 → 执行 → 输出
#   异常路径：需求模糊 → 追问 → 收到回复 → 继续
#   失败路径：外部API超时 → 重试 → 仍失败 → 兜底方案
```

---

→ [03-State-Machine.md](./03-State-Machine.md)
