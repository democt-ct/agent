# 01 - Evaluation Framework — 评测体系总览

> 学习目标：建立评测的全局视角——评测什么、怎么分层、为什么评测

---

## 1. 为什么 Agent 需要评测

普通软件：输入确定 → 输出确定 → 测试 = 断言。

Agent 软件：输入确定 → 输出不确定（LLM 的随机性 + 工具调用的不可预测性）→ 测试 ≠ 断言。

```
传统软件测试：
  输入 2+2 → 期望 4 → 断言通过✅

Agent 测试：
  输入 "成都三日游" → 
    Agent 可能输出行程A、B、C……
    哪个更好？不能说"等于某个答案"。
    只能说"满足某些条件"。
```

> **核心认知**：Agent 评测不是测"对不对"，而是测"好不好"。

---

## 2. 评测金字塔

```
            ┌─────────────┐
            │   System    │  ← 整体效果：用户满意度、留存率
            │   Evaluation│     (最难，最贵)
            └──────┬──────┘
                   │
          ┌────────┴────────┐
          │     Agent       │  ← 端到端：任务完成率、Success Rate
          │   Evaluation     │     (核心层)
          └────────┬────────┘
                   │
     ┌─────────────┼─────────────┐
     │             │             │
┌────┴────┐  ┌────┴────┐  ┌────┴────┐
│ Prompt  │  │  Tool   │  │ Memory  │  ← 组件层：各模块独立评测
│  Eval   │  │  Eval   │  │  Eval   │
└─────────┘  └─────────┘  └─────────┘
```

从下往上：
- **组件层**：Prompt 好不好？Tool 选择对不对？Memory 召回准不准？——最便宜，跑得最快
- **Agent 层**：整个 Agent 能完成任务吗？——核心
- **System 层**：用户满意吗？留存吗？——最真实但最慢（依赖线上数据）

> 学习重点在 Agent 层和 Prompt 层。System 层是上线后的事。

---

## 3. 评测什么

### 正确性维度

| 指标 | 衡量什么 | 怎么测 |
|------|---------|--------|
| **Accuracy** | 输出的事实是否正确 | 人工标注 golden answer |
| **Groundedness** | 输出是否基于检索到的文档而非幻觉 | 逐句检查是否有出处 |
| **Hallucination Rate** | 幻觉比例 | 标注幻觉句数 / 总句数 |
| **Task Success Rate** | 任务是否完成 | 人工判断 / LLM-as-Judge |

### 效率维度

| 指标 | 衡量什么 | 怎么测 |
|------|---------|--------|
| **Latency** | 从请求到完成的时间 | 计时 |
| **Tool Calls Count** | 完成任务的工具调用次数 | 计数 |
| **Token Usage** | Token 消耗 | API 返回 |

### 成本维度

| 指标 | 衡量什么 | 怎么测 |
|------|---------|--------|
| **Cost per Task** | 每次任务的花费 | Token × 单价 |
| **Cost per Successful Task** | 成功任务的成本（过滤掉失败重试） | 总费用 / 成功数 |

---

## 4. LLM-as-Judge

让 LLM 来评判 LLM 的输出。这是目前最常用的 Agent 评测方式——因为人工评测太贵太慢。

```python
class LLMJudge:
    JUDGE_PROMPT = """
    你是一个评测员。评估以下 Agent 输出是否满足用户需求。
    
    用户需求：{user_request}
    Agent 输出：{agent_output}
    
    请从以下维度打分（1-5）：
    1. 完整性：是否覆盖了用户需求的所有方面？
    2. 准确性：提供的信息是否准确？
    3. 有用性：是否给出了可执行的建议？
    4. 格式：输出是否结构清晰？
    
    返回 JSON：
    {{
        "completeness": 4,
        "accuracy": 5,
        "usefulness": 4,
        "format": 5,
        "overall": 4.5,
        "issues": ["缺少预算明细"]
    }}
    """
    
    def evaluate(self, user_request: str, agent_output: str) -> dict:
        prompt = self.JUDGE_PROMPT.format(
            user_request=user_request,
            agent_output=agent_output
        )
        return llm.generate_json(prompt)


# ⚠️ LLM-as-Judge 的局限：
# - LLM 有偏好（偏好长回答、偏好自己的输出风格）
# - 对事实性错误的检测不够可靠
# - 不能替代人工标注，只能作为辅助
```

---

## 5. 评测数据集设计

一个好的评测数据集应该：

```python
eval_dataset = [
    {
        "id": "eval_001",
        "category": "行程规划",          # 分类
        "difficulty": "easy",            # easy / medium / hard
        "user_input": "帮我规划成都三日游，预算3000",
        "golden_answer": None,           # Agent 任务无标准答案
        "success_criteria": [            # 用条件代替答案
            "输出包含 Day 1/2/3 结构",
            "总预算不超 3000",
            "包含交通和住宿建议",
            "至少推荐 3 个景点"
        ],
        "forbidden_patterns": [          # 不该出现的
            "我不知道",
            "作为AI"
        ]
    },
    # ... 100+ 条
]
```

关键原则：
- **用条件判断代替标准答案**——Agent 输出无唯一解
- **覆盖边界**——正常/异常/模糊/多语言
- **分层难度**——easy 测基本功能，hard 测鲁棒性

---

## 常见错误

| 错误 | 后果 | 正确做法 |
|------|------|---------|
| 用精确匹配测 Agent 输出 | Agent 永远"失败" | 用条件判断 + LLM-as-Judge |
| 只有 10 条测试用例 | 统计无意义 | 100+ 条起 |
| 只测 happy path | 生产环境异常场景全漏 | 20% 用例为异常场景 |
| 评测数据集从不更新 | 模型 adapts to test set | 定期更新 20% 用例 |

---

## 实践任务

**任务1**：画出你的旅游 Agent 的评测金字塔——每一层评测什么、用什么方法、预计频率。

**任务2**：设计 20 条评测用例（5 easy + 10 medium + 5 hard），每条用例包含 user_input 和 success_criteria。

**任务3**：用 LLM-as-Judge 评测你的旅游 Agent 的 5 次输出。LLM 的评分和你人工判断一致吗？不一致的地方在哪？

---

→ [02-Prompt-Evaluation.md](./02-Prompt-Evaluation.md)
