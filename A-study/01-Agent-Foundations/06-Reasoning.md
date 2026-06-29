# 06 - Reasoning — 推理策略

> 学习目标：理解 Agent 如何通过不同的推理策略来提升决策质量，掌握 CoT、ToT、Reflection、Self-Correction 的核心思想

---

## 1. Agent 为什么需要推理

LLM 的默认模式是"直接给出答案"。但 Agent 面对的任务往往需要多步推理：

```
❌ 直接回答模式：
  用户："这个项目应该用什么数据库？"
  LLM："PostgreSQL。"
  → 没有分析项目需求，答案可能对也可能错

✅ 推理模式：
  用户："这个项目应该用什么数据库？"
  LLM：
    1. 先看项目是做什么的（读 README）
    2. 分析数据特征（结构化？非结构化？读写比例？）
    3. 考虑团队技术栈
    4. 给出推荐 + 理由
  → 基于分析过程的决策
```

> **核心认知**：Reasoning 不是让 LLM "更聪明"，而是让它"先想清楚再说"。

---

## 2. Chain of Thought（CoT）— 思维链

最简单也最有效的推理策略：让 LLM 把思考过程写出来。

```python
# ❌ 无 CoT
prompt = "23 × 17 = ?"
# LLM 直接输出："391"（可能错）

# ✅ 有 CoT
prompt = """
计算 23 × 17。一步一步来：
1. 拆分
2. 计算
3. 汇总
"""
# LLM 输出：
# 23 × 17
# = 23 × (10 + 7)
# = 23×10 + 23×7
# = 230 + 161
# = 391
```

### Agent 中的 CoT 应用

```python
# Planner 用 CoT 分解任务
planner_prompt = """
将以下目标分解为子任务。先分析，再分解。

目标：{goal}

分析步骤：
1. 这个目标涉及哪些方面？（交通/住宿/行程/预算）
2. 哪些步骤必须先做？（依赖关系）
3. 哪些步骤可以并行？

然后输出 JSON 格式的任务列表。
"""
```

### Zero-shot CoT

不需要给示例，只需在 Prompt 末尾加一句 `"Let's think step by step"`，就能显著提升推理准确率。

---

## 3. Tree of Thoughts（ToT）— 思维树

CoT 是线性的（一条思维链）。ToT 是树状的——在关键分叉点探索多条路径，选最优的继续。

```
                    [怎么去成都？]
                    /      |      \
               [飞机]   [高铁]   [自驾]
                /  \      |        \
          [¥1200] [¥800] [¥600]   [太远]
            ✓       ✓      ✓        ✗
            │       │      │
            └───────┼──────┘
                    │
              [比价后选高铁]
                    │
              [查高铁时刻表]
```

```python
class TreeOfThoughts:
    def explore(self, problem: str, branching_factor: int = 3,
                max_depth: int = 3) -> str:
        """思维树搜索"""
        
        def generate_thoughts(state: str, n: int) -> list:
            """从当前状态生成 n 个可能的下一步"""
            prompt = f"""
            当前问题：{problem}
            当前进展：{state}
            
            生成 {n} 个不同的下一步方向。
            返回 JSON 数组。
            """
            return llm.generate_json(prompt)
        
        def evaluate_thoughts(thoughts: list) -> list:
            """评估每个方向的价值"""
            scored = []
            for t in thoughts:
                prompt = f"""
                评估以下方案的质量（1-10分）：
                问题：{problem}
                方案：{t}
                
                只返回数字。
                """
                score = float(llm.generate(prompt))
                scored.append((t, score))
            
            # 返回 top-2
            scored.sort(key=lambda x: x[1], reverse=True)
            return [s[0] for s in scored[:2]]
        
        # BFS 搜索
        current_states = [""]
        for depth in range(max_depth):
            next_states = []
            for state in current_states:
                thoughts = generate_thoughts(state, branching_factor)
                best = evaluate_thoughts(thoughts)
                next_states.extend(best)
            current_states = next_states
        
        return current_states[0]  # 最优路径
```

> ⚠️ ToT 的代价：每个分叉点都要多次 LLM 调用，Token 消耗是 CoT 的 3-10 倍。只在**高价值决策点**使用——例如 Planner 决定"先订机票还是先订酒店"。

---

## 4. Reflection — 自我反思

Agent 执行完一步后，不是直接进入下一步，而是先问自己："这一步做对了吗？还需要什么？"

这是 Agent 生命周期中的核心环节（回顾 01-Agent-Foundations 的生命周期图）。

```python
class ReflectiveAgent:
    def reflect(self, action: str, result: dict, goal: str) -> dict:
        """执行后的反思"""
        prompt = f"""
        你刚执行了以下操作：
        
        目标：{goal}
        执行动作：{action}
        执行结果：{result}
        
        请反思：
        1. 这个结果对目标的贡献是什么？（正向/负向/无关）
        2. 有没有遗漏？（需要补充的信息或步骤）
        3. 下一步应该做什么？
        4. 是否需要调整原始计划？
        
        返回 JSON：
        {{
            "contribution": "positive|negative|neutral",
            "gaps": ["遗漏1", ...],
            "next_action": "...",
            "need_replan": false
        }}
        """
        return llm.generate_json(prompt)


# 在 Agent 循环中使用
def agent_loop_with_reflection(goal, max_iter=10):
    plan = planner.decompose(goal)
    memory = []
    
    for step in range(max_iter):
        # 执行
        action = select_action(plan, memory)
        result = execute(action)
        
        # 反思
        reflection = reflective_agent.reflect(action, result, goal)
        
        if reflection["contribution"] == "negative":
            # 这一步走错了，回退
            memory.append({"type": "lesson", 
                          "content": f"避免重复：{action} 对目标无贡献"})
        
        if reflection["need_replan"]:
            plan = planner.replan(plan, completed, reflection["gaps"])
        
        if is_goal_achieved(goal, memory):
            return assemble_output(memory)
    
    return "达到最大迭代次数"
```

---

## 5. Self-Correction — 自我纠正

Reflection 发现了问题，Self-Correction 负责修正。

```python
class SelfCorrectingAgent:
    def generate_and_correct(self, task: str, max_attempts: int = 3):
        """生成 → 自我检查 → 修正 → 再检查"""
        
        draft = llm.generate(f"完成任务：{task}")
        
        for attempt in range(max_attempts):
            # 自我检查
            critique = llm.generate(f"""
            严格审查以下输出，找出所有问题：
            
            任务：{task}
            输出：{draft}
            
            检查：
            - 是否完全满足任务要求？
            - 有没有事实错误？
            - 有没有逻辑漏洞？
            
            返回问题和修改建议。如果没问题，返回 "PASS"。
            """)
            
            if "PASS" in critique:
                return draft
            
            # 根据批评修正
            draft = llm.generate(f"""
            根据以下反馈修改你的输出：
            
            原始输出：{draft}
            反馈：{critique}
            
            输出修改后的完整版本。
            """)
        
        return draft  # 返回最后一版


# 使用场景：Agent 生成的行程文档
agent_output = self_correcting.generate_and_correct(
    "生成成都三日游的完整行程文档"
)
# → 第一版 → 检查是否遗漏了餐厅 → 修正 → 检查预算是否超 → 修正 → PASS
```

---

## 6. Deliberation — 深思熟虑

最新（2025）的推理范式：不是想一次，而是反复推敲、权衡多个方案后给出最终答案。o1/o3 系列在内部隐式做了 Deliberation。

```
Reflection：做一步 → 反思一步（step-level）
Deliberation：想多步 → 比较 → 选最优（goal-level）
```

```python
def deliberate(goal: str, options: list) -> str:
    """深思熟虑：权衡多个方案"""
    prompt = f"""
    目标：{goal}
    
    可选方案：
    {json.dumps(options, indent=2)}
    
    请对每个方案进行深度分析：
    
    方案A：{options[0]['name']}
      - 优点：
      - 缺点：
      - 风险：
      - 成本（时间+金钱）：
    
    方案B：{options[1]['name']}
      ...
    
    然后：
    1. 两两比较
    2. 选出最优
    3. 说明为什么
    
    最后输出 JSON：{{"best_option": "...", "reasoning": "..."}}
    """
    return llm.generate_json(prompt)
```

---

## 7. 推理策略选择指南

```
任务复杂度      推荐策略        Token 成本   延迟
─────────────────────────────────────────────────
简单问答        直接回答        最低         最低
稍有推理需要    CoT             低           +
多步复杂推理    ToT             高           ++（取决于分支数和深度）
需要迭代改进    Reflection      中           ++（每步多一次 LLM 调用）
需要高质量输出  Self-Correction 高           +++（2-3 轮迭代）
高风险决策      Deliberation    很高         ++++
```

> **关键原则**：用最少的推理实现足够的质量。不需要每个 Agent 决策都用 ToT——大多数场景，CoT + Reflection 就够了。

---

## 常见错误

| 错误 | 后果 | 正确做法 |
|------|------|---------|
| 所有决策用 CoT | 简单任务浪费 Token | 简单问题直接回答 |
| ToT 分支太多 | Token 爆炸 | ≤3 分支，≤3 深度 |
| Reflection 只反思不记录 | 同样的错误犯两次 | 反思结果写入 Episodic Memory |
| Self-Correction 无限循环 | 永远不满意 | 设 max_attempts=3 |
| 用 Reasoning Model 做所有事 | 成本飙升 | 只在 Planning/Reflection 用 |

---

## 实践任务

**任务1**：选一个复杂任务（如"设计一个电商推荐系统的技术方案"），分别用直接回答和 CoT 两种方式提问，对比输出质量。

**任务2**：用 Tree of Thoughts 的思路，设计"成都五日游"的三个不同方案（穷游/舒适/豪华），评估后选最优。

**任务3**：为你旅游 Agent 的 Reflection 环节写一个完整的反思 Prompt——包含贡献判断、遗漏检查、replan 触发条件。

---

→ 回到 [学习指南](../学习指南.md) 继续 Part III：Architecture
