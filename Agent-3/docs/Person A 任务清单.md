# Person A 任务清单：第2~3周

> 架构 + Orchestrator 开发
> 依赖链：你的输出决定 B/C/D 何时能集成

---

## 总览

```
第2周                         第3周
├─────────────────────────────┼─────────────────────────────┤
base_agent.py ReAct 循环      Orchestrator 路由 + 编排
tools/base.py 检查            跨 Agent 串行交割
protocol/ 单元测试            集成联调
                              main.py 接入真实 Agent
```

---

## 🔵 第2周任务

### 任务 2.1：实现 `base_agent.py` 的 ReAct 循环

**背景**：当前 `run()` 还是 `NotImplementedError`，B/C/D 等着继承这个类来写他们的 Agent。

**实现内容**（参考 implementation-plan.md §5.3）：

```python
def run(self, request: AgentRequest) -> AgentResponse:
    # Step 1: RAG 检索
    # Step 2: 构造 system prompt（注入检索结果）
    # Step 3: ReAct 循环（最多 max_tool_calls 次）
    #   - LLM 返回 content → 结束
    #   - LLM 返回 tool_calls → _execute_tool → 塞回对话
    # Step 4: 达到上限 → 强制生成最终回答
```

**涉及文件**：`src/agents/base_agent.py`

**验收标准**：
- [ ] `run(AgentRequest)` 返回 `AgentResponse`
- [ ] LLM 认为不需要工具时直接返回 content
- [ ] LLM 调用工具时执行对应的 mock 函数
- [ ] 工具执行结果正确返回给 LLM 继续推理
- [ ] 达到最大工具调用次数后强制结束

### 任务 2.2：完善 `_build_system_prompt()`

把 RAG 检索结果格式化为 system prompt 中的知识上下文：

```python
你是{name}，基于知识库回答用户问题。
知识库找不到信息时明确告知，不要编造。

【知识库内容】
[来源: 年假管理制度.md · 相关度 0.94]
员工年假天数根据工龄计算……
```

**涉及文件**：`src/agents/base_agent.py`

### 任务 2.3：`tools/base.py` 检查

确保 `ToolDef` 能正确转换 `to_openai_format()`。B/C/D 会用它注册工具。

### 任务 2.4：protocol 单元测试

`tests/test_protocol.py`：

- `test_build_handoff()` — 交割上下文构造
- `test_merge_results_single()` — 单 Agent 回答汇总
- `test_merge_results_multi()` — 多 Agent 回答汇总
- `test_agent_request_defaults()` — 默认值覆盖
- `test_agent_response_status()` — 状态流转

---

## 🟠 第3周任务

### 任务 3.1：实现 `orchestrator.py` — AGENT_REGISTRY

硬编码 3 个 Agent 的注册信息：

```python
AGENT_REGISTRY = {
    "hr_agent": AgentRegistration(
        agent_name="hr_agent",
        display_name="HR 专家",
        description="负责回答人事制度、考勤、请假…",
        tool_descriptions=["get_leave_balance — 查询假期余额", ...],
    ),
    "it_agent": AgentRegistration(...),
    "legal_agent": AgentRegistration(...),
    "fallback": AgentRegistration(...),
}
```

**涉及文件**：`src/agents/orchestrator.py`

### 任务 3.2：LLM 意图路由

将用户问题送入 GPT-4o-mini，返回 JSON：

```json
{"primary": "hr_agent", "secondary": null}
```

**路由 prompt 设计**：
- 列出每个 Agent 的描述
- temperature=0.0（路由要稳定）
- 支持跨域（primary/secondary）
- LLM 无法判断时返回 fallback

**兜底策略**（面试必问）：
- LLM 路由 → fallback 时走兜底节点
- 加关键词规则层（"请假"→hr、"报修"→it）
- 关键词命中 > LLM 结果，避免抖动

**涉及文件**：`src/agents/orchestrator.py`

### 任务 3.3：LangGraph 编排图

```
Orchestrator Node → route_decision()
    ├── hr_agent_node    → END
    ├── it_agent_node    → END
    ├── legal_agent_node → END
    └── fallback_node    → END
```

**涉及文件**：`src/agents/orchestrator.py`、依赖 `langgraph`

### 任务 3.4：跨 Agent 串行编排

处理"我请病假 + 笔记本报修"这种跨域问题：

1. Orchestrator 路由 → HR Agent
2. HR 处理请假 → 返回 + handoff_suggestions
3. Orchestrator 再路由 → IT Agent
4. IT 处理报修 → 返回
5. `merge_results()` 汇总 → 最终回答

**交割协议**：已由你实现好的 `protocol/handoff.py` 提供

**涉及文件**：`src/agents/orchestrator.py`

### 任务 3.5：集成联调

等 B/C/D 完成各自的 Agent 后：

1. 在 `orchestrator.py` 中创建 AGENT_INSTANCES
2. 每个 Agent 绑定自己的 KnowledgeBase + tools
3. 跑通 3 个 Demo 场景

---

## 📦 交付物清单

| 周次 | 文件 | 状态 |
|------|------|------|
| W2 | `src/agents/base_agent.py` (ReAct 循环) | ❌ 未做 |
| W2 | `src/agents/base_agent.py` (_build_system_prompt) | ❌ 未做 |
| W2 | `tests/test_protocol.py` | ❌ 未做 |
| W3 | `src/agents/orchestrator.py` | ❌ 未做 |
| W3 | `src/main.py` (接入真实 Agent) | ❌ 骨架 |

---

## 🔗 依赖关系

```
你的产出              谁在等
───────────────────────────────────
base_agent.py (ReAct)  B: HRAgent extends BaseAgent
                       C: ITAgent extends BaseAgent
                       D: LegalAgent extends BaseAgent

orchestrator.py        全团队集成联调

main.py (真实 Agent)   全团队 Demo
```
