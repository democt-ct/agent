# 00 - Agent 定义辨析

> 学习目标：明确 Agent 到底是什么，与 ChatBot、Workflow、RAG 的边界在哪里

---

## 1. ChatBot ≠ Agent

这是最常见的混淆。很多人以为接入了 LLM 就是 Agent。

```
ChatBot（问答机器人）：
  用户："成都有什么好玩的？"
  LLM："成都有宽窄巷子、锦里、大熊猫基地……"
  
  特点：一问一答，无工具、无规划、无状态
  本质：LLM + 对话界面

Agent（智能体）：
  用户："帮我规划成都三日游"
  Agent：
    ① 搜索成都攻略（Tool）
    ② 查7月天气（Tool）
    ③ 制定行程（Planning）
    ④ 比价酒店（Tool）
    ⑤ 生成文档（Output）
  
  特点：使用工具、自主规划、多步执行
  本质：LLM + Tools + Loop + Memory
```

> **判断标准**：如果它只能"说话"不能"做事"，就是 ChatBot。能调用外部工具完成任务的，才是 Agent。

---

## 2. Workflow ≠ Agent

```
Workflow（工作流）：
  固定的、预定义的步骤序列。
  
  订机票 Workflow：
    Step 1: 验证用户身份
    Step 2: 查询航班
    Step 3: 用户选择
    Step 4: 支付
    Step 5: 出票
  
  每一步是确定的，不需要 LLM "决策"走哪条路。

Agent（智能体）：
  步骤由 LLM 动态决定。
  
  用户："我下周想去成都，但预算只有2000"
  Agent 自己判断：
    → 预算紧，先查高铁而非飞机
    → 发现高铁票紧张，改查拼车
    → 发现无论如何超预算，主动建议缩短行程
  
  路径不是预设的，是 LLM 根据中间结果动态调整的。
```

> **判断标准**：路径固定 = Workflow。路径由 LLM 动态决策 = Agent。但注意——Agent 内部可以包含 Workflow（作为 Planner 产出后的执行引擎）。

---

## 3. RAG ≠ Agent

```
RAG（检索增强生成）：
  用户问 → 检索相关文档 → 把文档注入 Context → LLM 回答
  
  核心能力：让 LLM 能访问训练数据之外的知识
  局限：只做检索+回答，不做多步任务

Agent：
  RAG 只是 Agent 的一种 Tool。
  
  Agent 可以用 RAG 查资料，然后：
    → 根据查到的资料制定计划
    → 调用其他工具执行计划
    → 根据执行结果调整计划
```

> **RAG 是 Agent 的知识来源之一，不是 Agent 本身。**

---

## 4. Agent 的学术定义

Lilian Weng（OpenAI）的定义，引用最多的版本：

```
Agent = LLM + Planning + Memory + Tool Use

其中：
  Planning：    任务分解 + 反思
  Memory：      短期记忆 + 长期记忆
  Tool Use：    调用外部工具
```

Anthropic 的定义更简洁：

```
Agent 是一个能够自主使用工具来完成开放式任务的系统。
关键特征：tool use + loop + autonomy
```

---

## 5. 什么时候用 Agent，什么时候不用

```
适合 Agent ✅：
  - 开放式任务，步骤不确定
  - 需要多步推理和工具调用
  - 需要根据中间结果动态调整
  - 错误可容忍（有 HITL 兜底）

不适合 Agent ❌：
  - 步骤固定的业务流程 → 用 Workflow
  - 只需要信息检索 → 用 RAG
  - 只需要一次推理 → 直接调 LLM API
  - 错误不可容忍且无法人工审核 → 别用
```

---

## 6. 一张图说清楚关系

```
┌─────────────────────────────────────────────────────┐
│                   Agent System                       │
│                                                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐             │
│  │   LLM   │  │ Memory  │  │  Tools  │             │
│  │  推理引擎 │  │ 记忆系统 │  │ 工具系统 │             │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘             │
│       │             │             │                   │
│       └─────────────┼─────────────┘                   │
│                     │                                 │
│              ┌──────▼──────┐                          │
│              │   Planner   │  ← 动态决定做什么         │
│              └──────┬──────┘                          │
│                     │                                 │
│              ┌──────▼──────┐                          │
│              │  Workflow   │  ← 按确定的路径执行       │
│              └─────────────┘                          │
│                                                     │
│  内部可以包含 RAG 作为知识获取工具                     │
│  内部可以包含 Workflow 作为确定性执行引擎              │
└─────────────────────────────────────────────────────┘

ChatBot = LLM + 对话界面（无 Tool、无 Planning）
RAG     = LLM + 检索（只有一种 Tool）
Workflow = 固定步骤（无 LLM 动态决策）
Agent   = LLM + Tools + Planning + Memory + Loop
```

---

## 常见误解澄清

| 误解 | 真相 |
|------|------|
| "接入了 LLM API 就是 Agent" | ChatBot 也接了 LLM，不是 Agent |
| "用了 LangChain 就是 Agent" | LangChain 是工具集，你可以用它做 ChatBot、RAG 或 Agent |
| "Agent 一定会自己思考" | Agent 的"思考"只是 LLM 的推理输出，不是真正的意识 |
| "Agent 越多越好" | Agent 越多 = 延迟越高 + 成本越高 + 调试越难 |
| "Agent 可以完全自主" | Production Agent 必须有 HITL，尤其是高风险操作 |

---

→ [01-LLM工作原理.md](./01-LLM工作原理.md)
