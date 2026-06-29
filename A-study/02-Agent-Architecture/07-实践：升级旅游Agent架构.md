# 07 - 实践：升级旅游Agent架构

> 综合运用前六节的知识，将旅游 Agent 从 Demo 模式升级为完整的 Architecture

---

## 目标

把你第一阶段设计的旅游 Agent（或任意一个你做过的 Agent），从简单的 `User → LLM → Tool → Output` 模式，升级为包含 Planner、Workflow、State Machine、Router、HITL 的完整架构。

---

## 你的起点

```
当前你的旅游 Agent 大概是这样的：

User: "帮我规划成都五日游"
    ↓
LLM: 调用 web_search → 调用 flight_search → 调用 hotel_search → ...
    ↓
Output: 一份行程文档
```

问题：
- ❌ 没有 Planner，边走边搜，容易遗漏
- ❌ 没有 State Machine，不知道执行到哪一步
- ❌ 所有工具塞一个 Prompt，Context 浪费严重
- ❌ 没有 HITL，订票不确认
- ❌ 出错后从头再来

---

## Step 1：设计 Planner — 任务分解

### 1.1 画出你的 Task Graph

从「成都五日游」分解出至少 10 个子任务，标注依赖关系：

```python
tasks = [
    # 你的任务列表
    {"id": 1,  "name": "___", "depends_on": []},
    {"id": 2,  "name": "___", "depends_on": [1]},
    {"id": 3,  "name": "___", "depends_on": [1]},
    # ... 继续
]
```

### 1.2 识别并行机会

哪些任务可以并行？标注出来。

### 1.3 设计 Replan 策略

什么情况下需要重新规划？列出至少 3 种触发 replan 的场景。

```
触发 Replan 的场景：
1. ___
2. ___
3. ___
```

---

## Step 2：设计 Workflow — 执行流程

### 2.1 画出完整 Workflow 图

把 Step 1 的 Task Graph 扩展为 Workflow 图。必须包含：

- 至少 2 个**条件分支**（if/else）
- 至少 1 个**并行点**（fork/join）
- 每个步骤标注**转换条件**

```
[Start]
    │
    ▼
[理解需求] ── 信息不足 ──→ [追问用户] ──→ 回到理解
    │
    │ 信息充足
    ▼
[Planner 分解]
    │
    ├──→ [查天气] ──┐
    ├──→ [查交通] ──┼──→ [汇总分析]
    └──→ [查攻略] ──┘
    │
    ▼
[你的后续步骤...]
```

### 2.2 为关键步骤设错误处理

为每个可能失败的步骤设计重试和降级。

```python
error_handlers = {
    "search_flights": {
        "retry": 3,             # 最多重试3次
        "backoff": "exponential", # 退避策略
        "fallback": "使用缓存数据 / 返回官网链接"
    },
    "book_flight": {
        "retry": 1,
        "fallback": "告知用户手动预订"
    },
    # ... 继续
}
```

---

## Step 3：设计 State Machine — 状态管理

### 3.1 列出所有状态

至少 6 个状态：

```
□ IDLE
□ PLANNING
□ EXECUTING
□ WAITING
□ FAILED
□ DONE
□ （可选）RETRYING
```

### 3.2 画出状态转换图

用箭头标注每个转换的触发事件。

### 3.3 设计 WAITING 状态的子状态

旅游 Agent 在哪些节点需要等用户？

```
WAITING 子状态：
- WAITING_FLIGHT_SELECTION：用户在选航班
- WAITING_HOTEL_SELECTION：用户在选酒店
- WAITING_BOOKING_CONFIRM：用户在确认支付
- WAITING_FINAL_REVIEW：用户在审核完整行程
```

每个子状态标注：等多久超时、超时后怎么处理。

### 3.4 设计持久化方案

```python
# 你选择用什么存储状态？
persistent_state = {
    "storage": "___",  # Redis / PostgreSQL / SQLite / JSON file
    "key_pattern": "___",
    "ttl": "___",
    "saved_fields": ["当前状态", "已完成任务", "用户选择", "检查点"],
}
```

---

## Step 4：设计 Router — 智能路由

### 4.1 定义意图分类

```python
intents = {
    "planning":      {"keywords": ["规划", "行程", "安排", "几天"], 
                      "tools": ["___"]},
    "search":        {"keywords": ["搜索", "查询", "多少钱", "攻略"],
                      "tools": ["___"]},
    "booking":       {"keywords": ["订", "买", "预订", "下单"],
                      "tools": ["___"]},
    "modification":  {"keywords": ["改", "换", "调整", "取消"],
                      "tools": ["___"]},
    "chitchat":      {"keywords": ["你好", "谢谢"],
                      "tools": ["___"]},
}
```

### 4.2 为每个意图分配工具

确保每个意图涉及的工具不超过 8 个。

### 4.3 设计降级策略

列出你的 Agent 依赖的 5 个最关键的外部服务，每个准备降级方案。

---

## Step 5：设计 HITL — 人机协同节点

### 5.1 标注所有 HITL 节点

在你的 Workflow 图上标注：

- 🟢 自动（绿色）
- 🟡 确认（黄色）
- 🔴 审批（红色）

### 5.2 写出 3 个确认消息模板

用「人话」写出来，让用户能看懂。

```
确认消息 1（选航班）：
___

确认消息 2（支付）：
___

确认消息 3（最终审核）：
___
```

---

## Step 6：决定 Multi-Agent 策略

### 6.1 回答这个问题

你的旅游 Agent 真的需要 Multi-Agent 吗？

```
单 Agent + Planner 能解决吗？   [ ] 能  [ ] 不能
不同环节需要完全不同的工具集吗？ [ ] 是  [ ] 否
不同环节需要完全不同的行为规则吗？[ ] 是  [ ] 否

如果两个「否」，用单 Agent + Planner 就够了。
```

### 6.2 如果确实需要 Multi-Agent

画出 Orchestrator + Workers 架构图（最多 4 个 Worker）。

---

## Step 7：核心逻辑伪代码

```python
class TravelAgentV2:
    def __init__(self):
        self.planner       = Planner()
        self.workflow      = WorkflowEngine()
        self.state_machine = PersistentStateMachine()
        self.router        = HybridRouter()
        self.hitl          = HITLManager()
    
    def handle(self, user_input: str, user_id: str):
        # 1. 恢复或创建状态
        sm = self.state_machine.get_or_create(user_id)
        
        # 2. 路由——意图分类
        intent = self.router.classify(user_input)
        
        # 3. 如果新任务，规划
        if sm.current_state == AgentState.IDLE:
            plan = self.planner.decompose(user_input)
            sm.transition(AgentState.PLANNING, "start")
        
        # 4. 执行 Workflow
        while not sm.is_terminal():
            # 4.1 检查中止请求
            if self.hitl.should_stop(sm.session_id):
                break
            
            # 4.2 获取下一步
            next_step = self.workflow.get_next_step(sm)
            
            # 4.3 风险评估
            risk_check = self.hitl.check(next_step)
            if risk_check.requires_confirmation:
                sm.transition(AgentState.WAITING, "need_confirm")
                sm.save_checkpoint()
                return risk_check.confirmation_message  # 返回给用户
            
            # 4.4 执行
            try:
                result = self.workflow.execute(next_step, sm.context)
                sm.update_context(result)
            except Exception as e:
                sm.transition(AgentState.RETRYING, str(e))
                if not self.workflow.retry(next_step):
                    sm.transition(AgentState.FAILED, "exhausted_retries")
                    break
            
            # 4.5 检查是否需要 replan
            if result.get("needs_replan"):
                sm.context["plan"] = self.planner.replan(...)
        
        # 5. 生成输出
        if sm.current_state == AgentState.DONE:
            return self.assemble_output(sm)
        else:
            return {"status": sm.current_state.value, 
                    "message": self.format_status(sm)}
    
    def handle_user_response(self, user_id: str, response: dict):
        """处理用户对 HITL 确认的回应"""
        sm = self.state_machine.get(user_id)
        sm.handle_user_response(response)
        
        # 继续执行
        return self.resume(sm)
```

---

## Step 8：完整架构图

把前面所有步骤整合成一张图：

```
                            User
                              │
                     ┌───────[Gateway]────────┐
                     │                        │
               [Session Manager]      [Permission Manager]
                     │                        │
                     └──────────┬─────────────┘
                                │
                         [Router / Intent]
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
        [Planner]          [Workflow]        [HITL Gate]
              │                 │                 │
              └─────────────────┼─────────────────┘
                                │
                        [State Machine]
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
        [Search Tool]     [Booking Tool]    [Browser Tool]
              │                 │                 │
              └─────────────────┼─────────────────┘
                                │
                          [Evaluation]
                                │
                           [Monitoring]
```

---

## 完整设计文档模板

完成以上步骤后，整理成这份文档：

```markdown
# 旅游 Agent V2 架构设计文档

## 1. 从 V1 到 V2
V1 是什么样？V2 改了什么？解决了什么问题？

## 2. Task Graph（Planner）
[贴图 + 任务列表]

## 3. Workflow 图
[贴完整的 Workflow 图]

## 4. State Machine
[贴状态转换图 + 每个状态的说明]

## 5. Router 设计
[意图分类表 + 工具映射 + 降级策略]

## 6. HITL 节点
[标注过的 Workflow 图 + 确认消息模板]

## 7. Multi-Agent 决策
[为什么用/为什么不用 + 如果用的话架构图]

## 8. 核心逻辑伪代码
[贴 Step 7 的代码]

## 9. 架构总图
[贴 Step 8 的图]

## 10. 已知问题 / TODO
- ___
- ___
```

---

## 自查清单

- [ ] Planner：Task Graph 包含 10+ 子任务，标注依赖和并行机会
- [ ] Workflow：包含 2+ 条件分支、1+ 并行点，每个步骤有错误处理
- [ ] State Machine：6+ 状态，转换图完整，WAITING 子状态清晰
- [ ] Router：4+ 意图分类，每个意图 < 8 个工具，有降级策略
- [ ] HITL：关键操作标记确认，消息模板人类可读
- [ ] Multi-Agent：有明确的是/否决策和理由
- [ ] 核心逻辑：伪代码能跑通完整流程
- [ ] 架构图：一张图展示所有组件和它们的关系

---

## 预期效果对比

```
V1 (Demo)              →    V2 (Architecture)
─────────────────────────────────────────────────
User → LLM → Tool      →    User → Router → Planner → Workflow → Tools
无状态                  →    完整 State Machine + 持久化
所有工具塞一起           →    按意图过滤，Context 精简
出错重来                →    重试 + 降级 + Saga 补偿
无确认                  →    关键操作 HITL 确认
不可观测                →    每步记录状态变更历史
```

---

→ 完成后进入：[03-Production-Engineering](../03-Production-Engineering/)
