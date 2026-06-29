# 02 - Agent生命周期

> 学习目标：理解Agent的完整运行循环，这是分析任何Agent系统的第一步

---

## 1. Agent的核心：循环（Loop）

LLM是单次的：输入→输出。Agent是循环的：持续感知→决策→行动→观察，直到完成目标。

```
LLM：  [Input] ──→ [Output]

Agent：[Input] → [Plan] → [Act] → [Observe] → [Plan] → [Act] → ... → [Done]
```

---

## 2. 标准Agent生命周期

```
User Input
    ↓
[Goal Understanding]   理解用户意图，明确目标
    ↓
[Planning]             分解任务，制定执行步骤
    ↓
[Tool Selection]       选择当前步骤需要的工具
    ↓
[Execution]            调用工具执行
    ↓
[Observation]          分析执行结果
    ↓
[Reflection]           判断目标是否达成
    ├── 未完成 → [Memory Update] → 回到 Planning
    └── 完成   → [Final Output]
```

---

## 3. 各阶段详解

### Goal Understanding（目标理解）

把用户的自然语言转化为结构化目标，识别缺失信息。

```python
# 用户输入（模糊）
user_input = "帮我分析一下这份销售数据"

# 结构化后
goal = {
    "type": "data_analysis",
    "target": "销售数据",
    "missing_info": ["数据文件路径", "分析重点", "输出格式"]
}
# → 需要追问用户补全信息
```

### Planning（规划）

将目标分解为可执行的子任务，识别依赖关系。

```python
plan = {
    "tasks": [
        {"id": 1, "action": "读取数据文件",       "status": "pending"},
        {"id": 2, "action": "数据清洗和预处理",   "status": "pending"},
        {"id": 3, "action": "统计分析",           "status": "pending"},
        {"id": 4, "action": "生成可视化图表",     "status": "pending"},
        {"id": 5, "action": "撰写分析报告",       "status": "pending"},
    ],
    "dependencies": {
        2: [1],     # 清洗依赖读取
        3: [2],     # 分析依赖清洗
        4: [3],     # 图表依赖分析
        5: [3, 4],  # 报告依赖分析和图表
    }
}
```

### Tool Selection（工具选择）

根据当前子任务选择合适的工具。

```python
available_tools = ["read_file", "run_python", "web_search", "write_file"]

# 当前任务：读取数据文件
selected = "read_file"
params = {"path": "sales_2026.csv"}
```

### Execution → Observation（执行→观察）

```python
result = execute_tool(selected, params)

observation = {
    "success": True,
    "data_shape": (1500, 12),
    "columns": ["date", "product", "amount", "region", ...],
    "issues": ["amount列有23个空值", "date格式不统一"]
}
```

### Reflection（反思）

判断当前任务完成情况，决定下一步行动。

```python
reflection = {
    "current_task_done": True,
    "overall_goal_done": False,
    "next_action": "执行数据清洗，处理空值和日期格式",
    "blockers": []
}
```

### Memory Update（记忆更新）

将本轮信息存入记忆，供后续步骤使用。

```python
memory.update({
    "data_loaded": True,
    "data_issues": ["23个空值", "日期格式不统一"],
    "completed_steps": ["读取数据文件"]
})
```

---

## 4. 最简Agent循环实现

```python
def agent_loop(user_input, max_iterations=10):
    memory = []
    goal = understand_goal(user_input)

    for _ in range(max_iterations):
        plan   = create_plan(goal, memory)
        tool   = select_tool(plan)
        result = execute_tool(tool)
        obs    = observe(result)
        memory.append(obs)

        if is_complete(goal, memory):
            return generate_output(memory)

    return "达到最大迭代次数，任务未完成"
```

> `max_iterations` 是防止死循环的硬性限制，生产环境必须设置。

---

## 5. 三种典型Agent模式

### ReAct（最常见）

每步都是：思考（Thought）→ 行动（Action）→ 观察（Observation）

```
Thought: 需要先了解当前代码库结构
Action:  list_directory(path="./src")
Obs:     ["main.py", "utils.py", "models/", ...]
Thought: 找到了入口文件，读取 main.py
Action:  read_file(path="./src/main.py")
...
```

### Plan-and-Execute

先完整规划，再逐步执行（适合长流程、任务依赖复杂的场景）

```
[完整Plan] → 执行Step1 → 执行Step2 → ... → Final
```

### Multi-Agent

多个专业子Agent协同（适合任务可并行、需要专业分工的场景）

```
User → Orchestrator → Researcher ──┐
                    → Coder      ──┤→ Aggregator → Output
                    → Reviewer   ──┘
```

---

## 常见问题

**Q: Agent循环什么时候结束？**
达到目标 / 达到 max_iterations / 遇到不可恢复的错误 / 用户主动终止

**Q: Agent会死循环吗？**
会。两个防护：① 设 max_iterations ② 检测重复行为（连续三次相同Action则终止）

**Q: 应该用哪种Agent模式？**
任务简单用ReAct；流程复杂用Plan-and-Execute；需要并行或专业分工用Multi-Agent

---

## 实践任务

**任务1**：选一个你做过的AI功能，把它的执行过程套进上面的生命周期图——找出缺了哪些阶段。

**任务2**：分析这个残缺Agent的问题：

```python
def simple_agent(question):
    results = web_search(question)
    return llm.generate(f"基于以下信息回答：{results}")
```

缺少了哪些阶段？如果搜索结果不够，它会怎么处理？

**任务3**：设计一个任务分解：

```
用户需求：「帮我把这个Python项目迁移到TypeScript」
→ 分解子任务（至少5步）
→ 画出依赖关系
```

---

→ [03-Context Engineering.md](./03-Context%20Engineering.md)
