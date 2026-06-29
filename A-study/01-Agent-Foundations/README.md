# 01 - Agent Foundations

> **阶段目标**：建立Agent世界观——理解本质，不是急着写代码
>
> **预计时间**：2-3周
>
> **完成标志**：能画出Agent生命周期图、Context Flow图、Memory架构图

---

## 学习路径

| # | 文件 | 核心内容 | 预计时间 |
|---|------|----------|----------|
| 01 | [LLM工作原理](./01-LLM工作原理.md) | Token、Context Window、Function Calling、LLM≠Agent | 2天 |
| 02 | [Agent生命周期](./02-Agent生命周期.md) | Agent循环、Planning、Tool Selection、Reflection | 2天 |
| 03 | [Context Engineering](./03-Context%20Engineering.md) | Context组成、管理策略、信息密度优化 | 2天 |
| 04 | [Memory体系](./04-Memory体系.md) | 四层Memory架构、读写操作、设计原则 | 2天 |
| 05 | [实践：设计你的第一个Agent](./05-实践：设计你的第一个Agent.md) | 综合练习，输出完整Agent设计文档 | 3天 |

---

## 三个核心认知

```
① LLM ≠ Agent
  Agent = LLM + Tools + Loop + Memory

② Context ≠ 更聪明
  Context Management = 更聪明

③ 先设计，后编码
  没有清晰的架构图，写出来的Agent很难维护
```

---

## 本阶段产出

完成后你应该能输出：

1. **Agent生命周期图**（你的场景，非示例）
2. **Context Flow图**（信息怎么流入、怎么压缩）
3. **Memory架构图**（分几层、存什么、用什么技术）
4. **你的Agent设计文档**（基于05的模板）

---

## 下一阶段

→ [02-Agent-Architecture](../02-Agent-Architecture/)

学习：Planner · Workflow · State Machine · Router · Multi-Agent
