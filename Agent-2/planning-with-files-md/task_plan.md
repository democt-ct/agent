# Task Plan

## Goal

基于当前已经存在的后端能力和工作台页面，重新收敛 PRD，使项目从“大而全的智能旅游规划产品”切换为“可演示、可迭代的行程规划与修改工作台”。

本轮重点不是继续扩写全量产品愿景，而是明确：
- 当前行程是怎么生成的
- 当前界面到底服务哪条用户链路
- 前端页面接下来应该先做哪些能力
- 后端与页面之间的状态、接口、展示责任如何切分

## Current State

- Cloudflare Worker 已具备 `session`、`requirement`、`itinerary`、`replan`、`messages` 等主链路接口
- `src/services/llm/itineraryAgent.ts` 已支持基于 LLM 生成或重排 itinerary
- `src/services/templateItineraryGenerator.ts` 仍是兜底方案，LLM 不可用时回退到模板
- `fastapi/static/index.html` 是当前主要演示界面，形态为单页工作台
- 现有总 PRD 偏“平台级产品说明”，对当前页面的实现指导不够具体

## Phases

### Phase 1: Clarify Current Generation Flow
Status: completed

目标：
- 说明当前 itinerary 的真实来源
- 明确什么时候走大模型，什么时候走模板
- 明确当前页面拿到的是什么结构

Done criteria：
- 能直接回答“当前行程是否由大模型生成”
- 能说明 `template / llm / agent` 三种生成路径
- 能说明当前页面展示依赖的关键字段

### Phase 2: Redesign Current UI PRD
Status: completed

目标：
- 产出一份聚焦“当前界面”的 PRD 重规划文档
- 把页面目标从“泛旅游助手”收敛为“行程规划与修改工作台”
- 明确页面信息架构、关键状态、核心动作和后续实现顺序

Done criteria：
- 形成单独的当前界面 PRD 文档
- 文档能指导后续页面实现，而不仅是讲愿景
- 文档和现有接口能力基本对齐

### Phase 3: Translate PRD Into Build Milestones
Status: in_progress

目标：
- 把当前界面 PRD 转成前端实现阶段
- 标记必须先做、可以后做、暂不做的内容
- 为下一轮实际开发准备明确任务入口

Done criteria：
- 拆出页面实现优先级
- 拆出关键风险与依赖
- 能直接进入页面改造

### Phase 4: Implementation
Status: pending

目标：
- 依据新的当前界面 PRD 开始真正修改前端
- 先完成信息架构和关键交互，再做视觉和增强能力

Done criteria：
- 页面结构与 PRD 一致
- 用户能完成“输入需求 -> 生成初版 -> 发起修改 -> 查看结果”
- 状态展示比现在更清晰

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| PRD 继续写得过大 | 无法指导当前页面实现 | 强制聚焦当前工作台，不扩写远期平台能力 |
| LLM 输出结构不稳定 | 页面展示不稳定 | 保持结构化 schema 和模板兜底 |
| 页面目标不清 | 交互越来越像调试台 | 只保留围绕“生成与修改行程”的关键动作 |
| 界面状态过多 | 用户不清楚下一步做什么 | 用阶段状态和操作引导替代信息堆叠 |

## Next Actions

1. 按新的当前界面 PRD 开始梳理页面信息架构
2. 优先定义页面的四个关键状态：未开始、需求采集中、已生成初版、已进入修改
3. 再进入实际前端改造
