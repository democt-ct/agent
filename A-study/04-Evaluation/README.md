# 04 - Evaluation

> **阶段目标**：建立 Agent 自动评测体系——不再靠"感觉"判断 Agent 好坏，用数据和指标说话
>
> **预计时间**：2-3周
>
> **完成标志**：旅游 Agent 接入自动评测流水线，每次改动自动跑 100+ 条测试用例并生成报告

---

## 学习路径

| # | 文件 | 核心内容 | 预计时间 |
|---|------|----------|----------|
| 01 | [Evaluation Framework](./01-Evaluation-Framework.md) | 评测金字塔、评测什么、为什么评测 | 2天 |
| 02 | [Prompt Evaluation](./02-Prompt-Evaluation.md) | A/B Test、Regression Test、Promptfoo | 3天 |
| 03 | [Agent Evaluation](./03-Agent-Evaluation.md) | 端到端评测、Success Rate、Tool Selection | 3天 |
| 04 | [Metrics & Benchmark](./04-Metrics-and-Benchmark.md) | 核心指标定义、Benchmark 设计、统计方法 | 2天 |
| 05 | [Automated Eval Pipeline](./05-Automated-Eval-Pipeline.md) | CI 集成、批量测试、报告生成 | 3天 |
| 06 | [实践：搭建评测平台](./06-实践：搭建评测平台.md) | 为旅游 Agent 搭建完整评测体系 | 5天 |

---

## 四个核心认知

```
① 没有评测的 Agent = 盲飞
   改了一行 Prompt，是变好了还是变坏了？不知道。
   加了一个 Tool，成功率涨了还是跌了？不知道。
   评测让不可见的变成可见的。

② 评测是分层的
   不是"跑完看对不对"就完了。
   Prompt 评测 → Agent 评测 → System 评测，三层递进。

③ 指标不是越多越好
   Success Rate + Latency + Cost 三个就够了。
   再加就是锦上添花，少了就是盲飞。

④ 评测要自动化
   手动测 10 条 = 没用。自动跑 1000 条 = 有用。
   每次改代码自动跑 → CI 里集成 → 这才是 Production。
```

---

## 本阶段产出

完成后你应该能输出：

1. **评测金字塔图**（Prompt / Agent / System 三层）
2. **Prompt 评测脚本**（A/B 对比 + 回归测试）
3. **Agent 评测用例集**（100+ 条场景覆盖）
4. **Benchmark 设计文档**（指标定义 + 数据集 + 基线）
5. **CI 集成**（Git push → 自动跑评测 → 报告）

---

## 第三阶段回顾

← [03-Production-Engineering](../03-Production-Engineering/)

回顾：Session · Database · Queue · Resilience · Cache · Monitoring

---

## 下一部分

→ [05-Product-Design](../05-Product-Design/)（学习指南 Part VI）

学习：什么任务适合 Agent · Agent 产品设计原则
