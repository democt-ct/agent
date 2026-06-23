# Cluade Code Superpowers 技能指南

> Superpowers 是 Cluade Code 的内置技能系统，通过结构化流程确保开发纪律——先想清楚再动手，先验证再宣布完成。

## 调用方式

| 方式 | 说明 |
|------|------|
| **描述需求（推荐）** | 直接告诉 Cluade 你想做什么，它会自动判断并调用合适的 skill |
| **斜杠命令** | 输入 `/<skill-name>` 显式指定，如 `/brainstorming`、`/review` |

---

## 技能列表

### 一、流程类（决定如何做事）

| 技能名称 | 触发场景 | 核心作用 |
|----------|---------|---------|
| **brainstorming** | 创建功能、构建组件、添加新功能前 | 探索用户意图、需求和设计，避免盲目动手 |
| **writing-plans** | 有明确需求/规格的多步骤任务 | 在写代码前先制定实现计划 |
| **executing-plans** | 已有写好的实现计划 | 在独立会话中执行计划，带审查检查点 |
| **test-driven-development** | 实现功能或修复 bug 前 | 先写测试再写代码，以测试驱动开发 |
| **systematic-debugging** | 遇到 bug、测试失败或异常行为时 | 系统化排查，而非盲目猜测和修改 |

### 二、完成类（确保做对了）

| 技能名称 | 触发场景 | 核心作用 |
|----------|---------|---------|
| **verification-before-completion** | 即将声称工作完成时 | 先运行验证命令确认，证据先行，不做无依据的成功声明 |
| **requesting-code-review** | 完成任务、实现重大功能或合并前 | 请求代码审查，确保工作满足需求 |
| **receiving-code-review** | 收到代码审查反馈时 | 技术严谨地验证反馈，而非盲目接受 |
| **finishing-a-development-branch** | 实现完成、测试通过后 | 决定如何集成工作（合并/PR/清理） |

### 三、并行开发类

| 技能名称 | 触发场景 | 核心作用 |
|----------|---------|---------|
| **dispatching-parallel-agents** | 面对 2 个以上独立任务时 | 并行派发 agent 处理，提高效率 |
| **subagent-driven-development** | 在当前会话中执行实现计划 | 用子 agent 执行计划中的独立任务 |

### 四、工程类

| 技能名称 | 触发场景 | 核心作用 |
|----------|---------|---------|
| **using-git-worktrees** | 做需要隔离的功能开发时 | 使用 git worktree 创建独立工作区 |
| **writing-skills** | 创建、编辑或验证 skill 时 | 确保 skill 本身的质量 |

---

## 典型工作流

### 开发新功能

```
用户需求 → brainstorming（探索需求）
         → writing-plans（制定计划）
         → test-driven-development（TDD 开发）
         → verification-before-completion（验证完成）
         → requesting-code-review（代码审查）
         → finishing-a-development-branch（集成分支）
```

### 修复 Bug

```
发现问题 → systematic-debugging（系统化排查）
        → test-driven-development（TDD 修复）
        → verification-before-completion（验证修复）
```

### 多任务并行

```
多个独立任务 → dispatching-parallel-agents / subagent-driven-development
            → 各子 agent 独立完成
            → 汇总验证
```

---

## 核心理念

1. **纪律优先** — 先想清楚再动手，先验证再宣布完成
2. **流程驱动** — 不是随意编码，而是按技能引导的结构化流程推进
3. **自动匹配** — 只需描述需求，系统自动判断并调用合适的技能
4. **证据先行** — 任何"完成"声明都必须有验证结果支撑

## Skill 调用优先级

当多个 skill 可能适用时，按以下顺序：

1. **流程类 skill 优先**（brainstorming、debugging）— 决定如何做事
2. **实现类 skill 其次**（frontend-design、mcp-builder）— 指导执行
