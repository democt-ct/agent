# 02 - Agent Architecture

> **阶段目标**：掌握Agent的核心架构——Planner、Workflow、State Machine、Router、Multi-Agent、HITL
>
> **预计时间**：4-5周
>
> **完成标志**：能为旅游Agent加入完整的架构层，理解「什么时候用什么架构模式」

---

## 学习路径

| # | 文件 | 核心内容 | 预计时间 |
|---|------|----------|----------|
| 01 | [Planner — 任务规划](./01-Planner.md) | 任务分解、依赖图、ReAct vs Plan-Execute | 3天 |
| 02 | [Workflow — 工作流引擎](./02-Workflow.md) | State + Transition、DAG、条件分支 | 3天 |
| 03 | [State Machine — 状态机](./03-State-Machine.md) | 状态建模、转换规则、错误恢复 | 3天 |
| 04 | [Router — 智能路由](./04-Router.md) | 意图识别、工具分发、降级策略 | 2天 |
| 05 | [Multi-Agent — 多智能体](./05-Multi-Agent.md) | 协作模式、通信协议、何时不该用 | 3天 |
| 06 | [Human-in-the-Loop — 人机协同](./06-Human-in-the-Loop.md) | 审批节点、中断恢复、安全边界 | 3天 |
| 07 | [实践：升级旅游Agent架构](./07-实践：升级旅游Agent架构.md) | 综合设计，从Demo升级为Architecture | 5天 |
| 08 | [Tool Ecosystem — 工具生态](./08-Tool-Ecosystem.md) | Function Calling/MCP/A2A、Browser/Search/Vision/Code | 2天 |

> 📌 08（Tool Ecosystem）是俯瞰全局的一章，建议在学完 Router 和 Multi-Agent 后阅读，理解工具协议的全景。

---

## 四个核心认知

```
① 为什么要架构？
   Demo无需架构，Product必须有架构。
   架构解决的是：状态去哪了、出错了怎么办、怎么扩展。

② Workflow = State + Transition
   所有工作流框架（LangGraph、Temporal、Mastra）的本质都一样：
   你定义状态，定义转换规则，引擎负责执行。

③ 不要为了Multi-Agent而Multi-Agent
   增加Agent = 增加延迟 + 增加出错概率 + 增加调试难度。
   一个Agent能解决的问题不要用两个。

④ HITL是安全网，不是负担
   "删除数据库"前问一下用户，这不是打扰，是责任。
```

---

## 六大组件关系总览

学习之前，先理解它们怎么协作：

```
                          User Input
                              │
                              ▼
                      ┌──────────────┐
                      │    Router     │  ← "这是什么类问题？"
                      │   意图分类     │     决定走哪条路
                      └──────┬───────┘
                             │ intent
                             ▼
                      ┌──────────────┐
                      │   Planner     │  ← "先分解成哪些步骤？"
                      │   任务分解     │     产出 Task Graph
                      └──────┬───────┘
                             │ tasks
                             ▼
            ┌────────────────┴────────────────┐
            │                                 │
    ┌───────┴───────┐                 ┌───────┴───────┐
    │   Workflow    │  ← "按什么顺序 │  State Machine │  ← "现在到哪了？"
    │   驱动执行     │     执行？"    │   追踪状态      │     出错了怎么办？"
    └───────┬───────┘                 └───────┬───────┘
            │                                 │
            │  每一步都更新状态 ──────────────┘
            │
            ▼
    ┌──────────────┐     ┌──────────────┐
    │   HITL Gate  │ ←→  │ Multi-Agent  │  ← "一个人做还是多个人做？"
    │   安全确认     │     │   协作分配     │     需要用户确认吗？"
    └──────────────┘     └──────────────┘
            │                     │
            └─────────┬───────────┘
                      │
                      ▼
                  Tools 执行
```

> 📌 阅读顺序即学习顺序：Router → Planner → Workflow → State Machine → Multi-Agent → HITL，最后用 07 综合串联。

---

## 本阶段产出

完成后你应该能输出：

1. **旅游Agent的Task Graph**（任务怎么分解、依赖是什么）
2. **旅游Agent的Workflow图**（状态怎么流转）
3. **旅游Agent的State Machine图**（每个状态 + 转换条件）
4. **旅游Agent的Router设计**（意图分类 + 工具映射）
5. **旅游Agent的Multi-Agent设计**（如果需要的话）
6. **HITL节点设计**（哪些操作需要确认）
7. **完整的架构设计文档**（基于07的模板）

---

## 第一阶段回顾

← [01-Agent-Foundations](../01-Agent-Foundations/)

回顾：Agent生命周期 · Context Engineering · Memory体系

---

## 下一阶段

→ [03-Production-Engineering](../03-Production-Engineering/)

学习：Redis · PostgreSQL · Docker · Queue · Monitoring
