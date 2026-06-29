# 🧭 Agent Systems 学习路线图（2026）

> **⚠️ 本文件为早期规划稿（v1.0），已不再维护。**
>
> **系统性学习请阅读主文档：→ [学习指南.md](./学习指南.md)**
>
> 本文件保留作为月度计划的节奏参考（第七节）。

---

## 一、为什么要学习这份路线图

### 1.1 现状

已完成多个 Agent 项目：AI 旅游规划 / AI 修图 / 医学科研 / MCP Tool Calling / RAG / Playwright 自动化 / FastAPI 后端 / Ollama 本地部署

✅ 已具备 Agent 应用开发能力。

### 1.2 核心问题

当前项目本质上是 **Demo 模式**：

```
LLM → Prompt → Tool Calling → Output
```

企业真正需要的是 **系统工程**：

```
                          User
                            │
                    Session Manager
                            │
          ┌─────────────────┴─────────────────┐
          │                                   │
    Memory Manager                     Permission Manager
          │                                   │
          └─────────────────┬─────────────────┘
                            │
                    Planner / Router
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
      Browser           Search Tool        Code Tool
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
                    Workflow Engine
                            │
                    State Management
                            │
                 Evaluation Platform
                            │
                  Monitoring System
```

> 真正要学习的是：**Agent Systems Engineering**

---

## 二、最终目标（6 个月后）

能够独立设计 **Production Agent**，具备以下能力：

| 能力域 | 具体技能 |
|--------|---------|
| **系统设计** | Context Engineering · Memory · Planner · Workflow · Multi-Agent · State Machine |
| **工程化** | Session Management · Monitoring · Evaluation · Deployment |
| **最终产出** | 一个真正可落地的 Agent 系统 |

---

## 三、知识地图

```
                         Agent System
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   Foundations        Architecture          Engineering
        │                    │                    │
  ┌─────┴─────┐      ┌──────┴──────┐      ┌─────┴──────┐
  │ LLM       │      │ Planner     │      │ Redis      │
  │ Prompt    │      │ Workflow    │      │ PostgreSQL │
  │ Tool      │      │ Router      │      │ Docker     │
  │ MCP       │      │ State       │      │ Queue      │
  │ Memory    │      │ Multi-Agent │      │ Monitoring │
  │ RAG       │      │ Permission  │      │ Deployment │
  │ Context   │      │ HITL        │      │ Evaluation │
  └───────────┘      └─────────────┘      └────────────┘
```

> 📌 学习重点不是框架，而是**整个系统**。

---

## 四、学习路线

---

### 🏗️ 第一阶段：Agent Foundations（2~3 周）

> 目标：建立 Agent 世界观——不要急着写代码，先理解本质。

#### 1.1 LLM 工作原理

- Token · Context Window · Attention
- Function Calling · Structured Output

**核心认知**：

```
LLM ≠ Agent

Agent = LLM + Environment + Loop
```

#### 1.2 Agent 生命周期（必须牢记）

```
User → Goal → Planning → Tool Selection → Execution
                                           │
  Finish ← Reflection ← Memory Update ← Observation
```

> 分析任何 Agent 的第一件事：画生命周期。

#### 1.3 Context Engineering

Context 的组成：

```
System Prompt  ·  User Input  ·  Memory
Retrieved Knowledge  ·  Scratchpad
Tool Result  ·  Environment
```

**关键理解**：`100K Context ≠ Agent 更聪明` — 真正重要的是 **Context Management**。

#### 1.4 Memory 体系

| 层级 | 类型 | 关键问题 |
|------|------|---------|
| 工作记忆 | Working Memory | 当前对话 |
| 会话记忆 | Session Memory | 跨轮次 |
| 长期记忆 | Long-term Memory | 跨会话 |
| 语义记忆 | Semantic Memory | 结构化知识 |
| 情景记忆 | Episodic Memory | 历史经验 |

> 理解：什么时候写入 / 更新 / 删除 / 压缩。

#### 🎯 第一阶段实践

- 画 Agent 生命周期图
- 画 Context Flow 图

---

### 🏛️ 第二阶段：Agent Architecture（4~5 周）

> ⚠️ 整个路线最重要的一部分。

#### 2.1 Planner — 任务规划

为什么不能 `User → LLM → Tool`？

而是：

```
Goal → Task Planning → Task Graph → Execution
```

**示例**：「去成都旅游五天」

```
交通 ↗       ↗ Day1
住宿 → 分解 → Day2
      ↘       ↘ Day3 → 预算 → 天气
```

#### 2.2 Workflow — 工作流引擎

LangGraph / CrewAI / Mastra / Temporal 都围绕同一个核心：

```
Workflow = State + Transition
```

#### 2.3 State Machine — 状态机

```
NEW → RUNNING → WAITING → FAILED → RETRY → SUCCESS
```

> 企业的 Agent 几乎都有状态。

#### 2.4 Router — 智能路由

```
User Query → Router → Browser / Search / Code / Vision / Database
```

#### 2.5 Multi-Agent — 多智能体

什么时候一个 Agent？什么时候多个？

> ⚠️ 不要为了 Multi-Agent 而 Multi-Agent。

#### 2.6 Human-in-the-Loop（人机协同）

```
删除数据库？ → 需要确认 → 继续执行
```

#### 🎯 第二阶段实践

**升级旅游 Agent**，加入：Planner · Workflow · State · Memory · Router

---

### ⚙️ 第三阶段：Production Engineering（4 周）

> 开始进入真正工程。

| 模块 | 技术栈 | 解决的问题 |
|------|--------|-----------|
| **Session** | Redis | 不能用 Python 全局变量保存状态 |
| **Database** | PostgreSQL / SQLite / MongoDB | 不同场景选不同存储 |
| **Queue** | Celery / RabbitMQ / Redis Queue | 长任务异步处理（如 20 分钟生成 PDF） |
| **Scheduler** | Cron / Scheduler | 每天自动重新规划 |
| **Retry** | Retry / Fallback / Timeout / Circuit Breaker | 容错与韧性 |
| **Cache** | Redis Cache | Tool 不能一直调用 |
| **Monitoring** | Logging / Tracing / Metrics / Latency / Token / Cost | 可观测性 |

#### 🎯 第三阶段实践

旅游 Agent 加入：Redis · PostgreSQL · Docker Compose · 日志 · 监控

---

### 📊 第四阶段：Evaluation（2~3 周）

> 企业越来越重视。

#### 评测对象

- Prompt Evaluation
- Agent Evaluation
- Benchmark

#### 核心指标

```
Accuracy  ·  Groundedness  ·  Hallucination
Latency   ·  Cost          ·  Success Rate
```

#### 自动化测试流

```
1000 条问题 → 自动运行 → 统计：
  · 成功率       · 失败率
  · Tool 调用次数 · 平均耗时
```

---

## 五、推荐学习资源

### Agent 基础 ⭐⭐⭐⭐⭐

| 资源 | 说明 |
|------|------|
| Anthropic Engineering Blog | Agent 设计最佳实践 |
| OpenAI Developer Docs | Function Calling & Structured Output |
| OpenAI Evals | 官方评测框架 |
| MCP Official Specification | 工具调用协议标准 |

### Workflow ⭐⭐⭐⭐⭐

| 资源 | 重点 |
|------|------|
| **LangGraph** | 理解思想，不是 API |

### Multi-Agent ⭐⭐⭐⭐☆

| 资源 | 重点 |
|------|------|
| AutoGen · CrewAI | 理解协作方式，不是堆 Agent |

### Agent Framework — 推荐读源码 ⭐⭐⭐⭐⭐

- OpenHands
- Mastra
- Open WebUI
- n8n AI Agent

> 不要只会用，重点是**分析架构**。

### 后端工程 ⭐⭐⭐⭐⭐

- Redis · PostgreSQL · Docker · Docker Compose
- FastAPI · Celery · RabbitMQ

### Evaluation ⭐⭐⭐⭐⭐

- DeepEval · Promptfoo
- LangSmith · OpenAI Evals

---

## 六、未来重构方向

> 不要继续做新的 Demo。**重构旅游 Agent。**

### 从 Demo 模式

```
User → LLM → Tool → 输出
```

### 升级为 Production System

```
User → Gateway → Session → Memory → Planner → Router
  → Workflow → State → Tools → Observation
  → Reflection → Evaluation → Monitoring → Finish
```

---

## 七、每月学习计划

| 月份 | 重点 | 完成目标 |
|------|------|---------|
| **第 1 个月** | Agent Foundations | Agent 生命周期图 · Context Flow 图 · Memory Flow 图 |
| **第 2 个月** | Architecture | 旅游 Agent 加入 Planner · Workflow · State Machine |
| **第 3 个月** | Production | Redis · PostgreSQL · Docker · Logging |
| **第 4 个月** | Evaluation | 自动评测平台：成功率 · Token · 延迟 · Cost |

---

## 八、最终能力画像

| ✅ | 能力 | 描述 |
|----|------|------|
| ✅ | 设计 Agent 架构 | 从需求到系统架构 |
| ✅ | 开发 Production Agent | 工程级代码，非 Demo |
| ✅ | 部署 Agent | Docker / 云原生 |
| ✅ | 监控 Agent | 可观测性全覆盖 |
| ✅ | 评估 Agent | 自动化评测 + 持续优化 |

> 🏁 从「会做 Agent Demo」成长为「**能设计、开发、部署、评估 Production Agent System 的 Agent Systems Engineer**」。
