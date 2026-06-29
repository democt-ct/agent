# 03 - Production Engineering

> **阶段目标**：把 Agent 从「能跑」升级为「能投产」——Session管理、数据库、异步队列、容错、缓存、监控
>
> **预计时间**：4周
>
> **完成标志**：旅游 Agent 能在 Docker Compose 中稳定运行，具备日志/监控/持久化能力

---

## 学习路径

| # | 文件 | 核心内容 | 预计时间 |
|---|------|----------|----------|
| 01 | [Session Management](./01-Session-Management.md) | Redis 会话、TTL、多设备恢复、分布式一致性 | 3天 |
| 02 | [Database Design](./02-Database-Design.md) | PostgreSQL/SQLite/MongoDB 选型、Schema设计 | 3天 |
| 03 | [Async Tasks](./03-Async-Tasks.md) | 消息队列（Celery/Redis Queue）+ 定时调度 | 3天 |
| 04 | [Resilience Patterns](./04-Resilience.md) | Retry/Fallback/Timeout/Circuit Breaker 实战 | 3天 |
| 05 | [Cache Strategy](./05-Cache-Strategy.md) | Redis 缓存 Tool 结果、缓存失效策略 | 2天 |
| 06 | [Monitoring](./06-Monitoring.md) | 日志/链路追踪/指标仪表盘/Token成本 | 3天 |
| 07 | [实践：Docker部署旅游Agent](./07-实践：Docker部署旅游Agent.md) | Docker Compose 编排，一键启动完整系统 | 5天 |

---

## 五个核心认知

```
① Session 不是"全局变量"
   Demo 可以用 dict 存状态。Production 必须用 Redis——
   服务重启不能丢用户进度，多实例不能互相看不见。

② 存储选型是取舍，不是对错
   SQLite 部署最简单，PostgreSQL 最全能，MongoDB 最灵活。
   选哪个取决于你的场景，不是技术信仰。

③ 长任务必须异步
   用户点了"生成30天完整行程"，你不能让他等5分钟看白屏。
   Queue 接收 → Worker 处理 → 回调通知。

④ 容错是设计出来的，不是补丁
   Retry + Timeout + Circuit Breaker + Fallback，
   四者组合才叫韧性。只加 try/except 是自我安慰。

⑤ 上线之前，先"看见"它
   没有监控的 Production Agent = 闭着眼睛开车。
   Latency、Token、Cost、Success Rate —— 这四个指标必须先有。
```

---

## 本阶段产出

完成后你应该能输出：

1. **Redis Session Manager**（创建、恢复、过期、跨实例共享）
2. **数据库 Schema 设计**（用户表、会话表、记忆表、审计日志表）
3. **异步任务系统**（Queue + Worker + 定时调度 + 重试）
4. **容错体系**（Retry/Timeout/Circuit Breaker/Fallback 四合一）
5. **缓存层**（Tool 结果缓存、语义缓存、失效策略）
6. **监控仪表盘**（Latency/Token/Cost/Success Rate 实时面板）
7. **Docker Compose 一键部署**（Agent + Redis + PostgreSQL + Worker）

---

## 第二阶段回顾

← [02-Agent-Architecture](../02-Agent-Architecture/)

回顾：Planner · Workflow · State Machine · Router · Multi-Agent · HITL

---

## 下一阶段

→ [04-Evaluation](../04-Evaluation/)

学习：自动化评测 · Benchmark · Prompt Eval · Agent Eval
