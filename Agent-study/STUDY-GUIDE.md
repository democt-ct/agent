# 📖 学习导航：路线图 → 手册文件映射

> 如何使用：每个阶段先看路线图目标，再按推荐顺序阅读手册文件，最后在 notes/ 下写心得。

---

## 🏗️ 第一阶段：Agent Foundations（2~3 周）

> 目标：建立 Agent 世界观 | 手册目录：`foundations/` + `systems/context-engineering`

### 推荐阅读顺序

| 序号 | 文件 | 对应路线图知识点 | 预计时间 |
|------|------|-----------------|---------|
| 1 | `foundations/agent-systems/what-is-agent.mdx` | LLM ≠ Agent 的认知 | 30 min |
| 2 | `foundations/agent-systems/what-is-agent-system.mdx` | Agent 系统全景 | 20 min |
| 3 | `foundations/history-of-agent-ideas.mdx` | Agent 思想演进史 | 25 min |
| 4 | `foundations/llm-foundations-for-agent-systems.mdx` | LLM 工作原理 | 40 min |
| 5 | `foundations/agents-vs-workflows.mdx` | Agent vs Workflow 对比 | 25 min |
| 6 | `foundations/the-agent-system.mdx` | Agent 生命周期 | 30 min |
| 7 | `systems/context-engineering.mdx` | Context Engineering | 35 min |
| 8 | `patterns/agent-memory-and-retrieval.mdx` | Memory 体系 | 35 min |

### 辅助阅读

| 文件 | 用途 |
|------|------|
| `reading-paths/explorer.mdx` | 快速概览式阅读路径 |
| `reading-paths/environment-setup.mdx` | 学习环境准备 |

### 🎯 阶段产出

- Agent 生命周期图 → `notes/phase1-foundations/agent-lifecycle.md`
- Context Flow 图 → `notes/phase1-foundations/context-flow.md`

---

## 🏛️ 第二阶段：Agent Architecture（4~5 周）

> 目标：掌握规划、工作流、状态、路由、多智能体、人机协同 | 最重要阶段

### 推荐阅读顺序

| 序号 | 文件 | 对应路线图知识点 | 预计时间 |
|------|------|-----------------|---------|
| 1 | `patterns/planning-and-reflection.mdx` | Planner + Reflection | 40 min |
| 2 | `patterns/reasoning-and-control-patterns.mdx` | Router + 推理控制 | 40 min |
| 3 | `patterns/agent-runtime-building-blocks.mdx` | Workflow + State Machine | 35 min |
| 4 | `case-studies/coding-agents.mdx` | 案例：代码 Agent 架构 | 30 min |
| 5 | `case-studies/customer-support-agents.mdx` | 案例：客服 Agent 架构 | 30 min |
| 6 | `case-studies/deep-research-agents.mdx` | 案例：深度研究 Agent | 30 min |
| 7 | `systems/protocols-and-interoperability.mdx` | Multi-Agent 通信协议 | 30 min |

### 辅助阅读

| 文件 | 用途 |
|------|------|
| `reading-paths/builder.mdx` | 构建者视角阅读路径 |
| `reading-paths/practitioner.mdx` | 实践者进阶路径 |
| `radar/2026-04-interoperability-watch.mdx` | 业界互操作性动态 |

### 🎯 阶段产出

- 旅游 Agent 架构升级方案 → `notes/phase2-architecture/agent-redesign.md`

---

## ⚙️ 第三阶段：Production Engineering（4 周）

> 目标：工程化落地 | 手册目录：`systems/` + `ecosystem/` + `radar/`

### 推荐阅读顺序

| 序号 | 文件 | 对应路线图知识点 | 预计时间 |
|------|------|-----------------|---------|
| 1 | `systems/agent-security-and-prompt-injection.mdx` | 安全 + 权限管理 | 35 min |
| 2 | `systems/evaluation-and-observability.mdx` | 监控 + Logging + Tracing | 35 min |
| 3 | `systems/agent-ui-protocols-and-generative-ui.mdx` | Session + 用户交互 | 25 min |
| 4 | `ecosystem/agent-frameworks.mdx` | 框架全景（Session/Queue 实现参考） | 30 min |
| 5 | `ecosystem/framework-comparison.mdx` | 框架对比选型 | 30 min |
| 6 | `ecosystem/agent-platforms-and-low-code-builders.mdx` | 部署平台 | 20 min |
| 7 | `ecosystem/model-ecosystem-map.mdx` | 模型选型（成本/延迟） | 20 min |

### 辅助阅读（Radar 行业动态）

| 文件 | 主题 |
|------|------|
| `radar/2026-04-local-agent-watch.mdx` | 本地 Agent 部署 |
| `radar/2026-06-agent-first-devices-watch.mdx` | Agent 优先设备 |
| `radar/2026-04-protocol-watch.mdx` | Agent 协议标准 |
| `radar/2026-04-assistant-safety-escalation-watch.mdx` | 安全升级机制 |
| `radar/2026-04-defense-agent-training-loop-watch.mdx` | Agent 训练循环 |
| `radar/2026-04-portable-assistant-memory-watch.mdx` | 可移植记忆 |
| `radar/2026-05-agentic-shopping-assistant-watch.mdx` | 购物 Agent 案例 |

### 🎯 阶段产出

- 旅游 Agent 工程化实现 → `notes/phase3-production/`

---

## 📊 第四阶段：Evaluation（2~3 周）

> 目标：可量化评估 | 手册目录：`systems/` + `skills/` + `workshops/`

### 推荐阅读顺序

| 序号 | 文件 | 对应路线图知识点 | 预计时间 |
|------|------|-----------------|---------|
| 1 | `systems/evaluation-and-observability.mdx` | 评测框架体系 | 重读重点 |
| 2 | `skills/index.mdx` | 技能包与可测试性 | 20 min |
| 3 | `workshops/skills-introduction.mdx` | 实操：构建可评测 Agent | 40 min |
| 4 | `reading-paths/sample-projects.mdx` | 参考项目评测方案 | 30 min |
| 5 | `publications/metadata-schema.mdx` | 评测元数据标准 | 20 min |

### 🎯 阶段产出

- 自动评测平台设计 → `notes/phase4-evaluation/eval-system.md`

---

## 📝 学习笔记模板

在 `notes/` 对应阶段目录下，按此模板创建笔记：

```markdown
# [知识点名称]

> 阅读来源：[手册文件名] | 日期：YYYY-MM-DD

## 核心概念
（用自己的话总结 3-5 个核心要点）

## 关键架构/流程图
（画 ASCII 图或文字描述关键流程）

## 与现有知识的联系
（这个知识点和你已有的 MEMORY.md 知识、项目经验的关联）

## 疑问与思考
- 疑问 1：...
- 思考 1：...

## 下一步行动
（看完这个，接下来要做什么？实践？深入哪个方向？）
```

---

## 📅 建议学习节奏

| 时间段 | 频率 | 内容 |
|--------|------|------|
| 每天 | 1-2 小时 | 按顺序阅读 1-2 个手册文件 + 写笔记 |
| 每周 | 1 次回顾 | 整理本周笔记，提炼到 `notes/summary/week-N.md` |
| 每阶段 | 1 次总结 | 完成阶段产出物，review 路线图目标达成情况 |
| 全周期 | 最终总结 | `notes/summary/final-review.md` |

---

## ⚡ 快速参考

- 🧭 路线图：`Agent-Systems-Learning-Roadmap-2026.md`
- 📁 笔记目录：`notes/phase{N}-xxx/`
- 📦 手册文件：按目录分类在根下
- 🏁 先读 `reading-paths/explorer.mdx` 可快速了解全貌
