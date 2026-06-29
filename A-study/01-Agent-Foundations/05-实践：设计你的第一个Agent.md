# 05 - 实践：设计你的第一个Agent

> 综合运用前四节的知识，完整设计一个Agent

---

## 目标

选一个你**真正想做**的场景（下面用「代码审查Agent」作为示例），按六个步骤输出完整设计文档。

---

## Step 1：画Agent生命周期

把你的Agent套进这个模板，填每个阶段实际做什么：

```
User Input: "帮我审查这段代码"
    ↓
[Goal Understanding]  → 识别语言/框架，明确审查重点（安全/性能/规范？）
    ↓
[Planning]            → 拆分：读代码 → 静态分析 → 安全扫描 → 生成报告
    ↓
[Tool Selection]      → 当前步骤用哪个工具？
    ↓
[Execution]           → 调用工具
    ↓
[Observation]         → 分析结果，有发现吗？
    ↓
[Reflection]          → 还需要做什么？
    ├── 未完成 → [Memory Update] → 回 Planning
    └── 完成   → 输出审查报告
```

**你的版本**：把上面每个`→`后面换成你场景的内容。

---

## Step 2：设计Context结构

```python
context = {
    "system": """
        角色：_______________
        核心能力：_______________
        行为规则：_______________
        输出格式：_______________
    """,

    "user": "当前用户消息",

    "history": [],          # 策略：保留最近___条，超出则___

    "memory": {
        "user_profile":  {},    # 从Long-term Memory加载
        "session_state": {},    # 从Session Memory加载
    },

    "tools": [],            # 列出你需要的工具

    "knowledge": []         # RAG检索结果（如果需要）
}
```

**填写要点**：
- System Prompt 不超过 500 tokens
- 历史保留策略写清楚（截断/摘要？保留几条？）
- 每个 memory 字段说明用途

---

## Step 3：设计Memory架构

```
┌──────────────────────────────────────────┐
│  Working Memory                           │
│  存：_______________                      │
│  上限：_____ tokens，超出时：___________  │
├──────────────────────────────────────────┤
│  Session Memory                           │
│  存：_______________                      │
│  存储：___   TTL：___                     │
├──────────────────────────────────────────┤
│  Long-term Memory                         │
│  存：_______________                      │
│  存储：___   写入条件：_______________    │
├──────────────────────────────────────────┤
│  Semantic Memory（可选）                  │
│  知识库内容：_______________              │
│  检索方式：_______________                │
└──────────────────────────────────────────┘
```

---

## Step 4：定义工具

```python
tools = [
    {
        "name": "___",
        "description": "___",     # 一句话说清楚这个工具做什么
        "parameters": {
            "param1": "类型 + 说明",
        },
        "returns": "返回值格式说明"
    },
    # ... 继续添加
]
```

**检查**：每个工具是否真的需要？工具太多会占用大量Context。

---

## Step 5：核心逻辑伪代码

```python
def my_agent(user_input, user_id):
    # 1. 加载记忆
    memory = load_memory(user_id)

    # 2. 理解目标
    goal = understand_goal(user_input, memory)
    if goal.missing_info:
        return ask_user(goal.missing_info)   # 先追问

    # 3. Agent循环
    for _ in range(MAX_ITER):
        context = build_context(goal, memory)

        # LLM决策（返回结构化输出）
        decision = llm.generate(context, schema={
            "thought": str,
            "action":  str,
            "tool":    str,
            "params":  dict,
            "done":    bool
        })

        if decision["done"]:
            break

        # 执行工具
        result = execute_tool(decision["tool"], decision["params"])
        memory.update(result)

    # 4. 生成输出
    return generate_final_output(goal, memory)
```

---

## Step 6：定义输出格式

```
# {场景名称} 输出

## 概览
___

## 详细结果
___

## 建议/后续步骤
___
```

设计原则：**格式固定、机器可解析、人类易读**。

---

## 完整设计文档模板

完成以上步骤后，整理成这份文档：

```markdown
# 我的 [Agent名称] 设计文档

## 1. 目标
___（一句话描述这个Agent解决什么问题）

## 2. Agent生命周期
[贴你的流程图]

## 3. Context设计
[贴你的Context结构]

## 4. Memory设计
[贴你的Memory架构]

## 5. 工具列表
[贴你的工具定义]

## 6. 核心逻辑
[贴你的伪代码]

## 7. 输出格式
[贴你的输出模板]

## 8. 待解决问题
- ___
- ___
```

---

## 自查清单

- [ ] 能画出Agent的完整生命周期
- [ ] Context各区域的内容和大小有规划
- [ ] Memory分层清晰，写入/读取策略明确
- [ ] 每个工具的必要性能说明
- [ ] 核心循环逻辑能用伪代码表达
- [ ] 输出格式固定且实用

---

→ 完成后进入：[02-Agent-Architecture](../02-Agent-Architecture/)
