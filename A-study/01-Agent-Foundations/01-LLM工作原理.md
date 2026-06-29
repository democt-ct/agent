# 01 - LLM工作原理

> 学习目标：理解LLM的本质，以及它和Agent的根本区别

---

## 1. LLM的本质

LLM（Large Language Model）是一个**基于概率的文本预测模型**：给定输入，预测最可能的下一个词。

```
输入：今天天气
预测：真好（0.32）/ 不错（0.28）/ 很差（0.15）/ ...
输出：真好啊  ← 采样自概率分布
```

理解这一点很重要：LLM不是在"思考"，而是在"预测"。这决定了它的能力边界。

---

## 2. Token：LLM的最小处理单元

LLM不处理字符，它处理 **Token**（词片段）。

```python
import tiktoken
encoder = tiktoken.encoding_for_model("gpt-4")

texts = ["Hello world", "你好世界", "def calculate():"]
for text in texts:
    tokens = encoder.encode(text)
    print(f"{text!r} → {len(tokens)} tokens: {tokens}")
# "Hello world"     → 2 tokens
# "你好世界"        → 4 tokens  
# "def calculate():" → 5 tokens
```

**为什么要理解Token？**

- API费用按token计费（输入+输出分别计价）
- Context Window有token上限，超出就截断
- Token数影响生成速度

---

## 3. Context Window：LLM的"视野"

LLM每次推理只能看到Context Window内的内容，**窗口之外一无所知**。

```
┌─────────────────────────────────────────────────────┐
│                  Context Window (128K)               │
│                                                      │
│  [System Prompt]  [Chat History]  [User Message]     │
│       ↑                 ↑               ↑            │
│    你设定的          历史对话        当前输入          │
│    角色/规则        （可能很长）                      │
└─────────────────────────────────────────────────────┘
                           ↓
                      LLM 生成回答
```

**核心认知**：Context Window大 ≠ 更聪明。关键是**放进去什么、怎么组织**。

---

## 4. Attention：LLM理解关系的机制

Attention让LLM能建立词语之间的关联，理解指代和上下文。

```
句子：「系统报错了，重启它之后问题消失了」

"它" 指的是什么？
LLM通过Attention确定："它" = "系统"，而非"问题"
```

实际意义：这就是为什么LLM能理解复杂的长文本，也是为什么上下文越相关、答案越准确。

---

## 5. Function Calling：LLM与外部世界的接口

LLM本身无法执行代码或访问网络，但它可以**声明要调用什么函数**，由外部系统执行后把结果返回给它。

```python
# 定义工具
tools = [
    {
        "name": "read_file",
        "description": "读取文件内容",
        "parameters": {"path": "文件路径"}
    },
    {
        "name": "run_query",
        "description": "执行数据库查询",
        "parameters": {"sql": "SQL语句"}
    }
]

# 流程：
# 用户：「统计上个月新增用户数」
# LLM：→ 调用 run_query(sql="SELECT COUNT(*) ...")
# 系统：执行SQL，返回结果 42
# LLM：→ 「上个月新增用户 42 人」
```

```
User → LLM → [决定调用工具] → 你执行 → 结果返LLM → 最终回答
```

这是Agent的核心能力基础。

---

## 6. Structured Output：强制格式输出

让LLM输出机器可直接解析的结构化数据，而非自然语言。

```python
# 自然语言输出（不好处理）
"代码审查结果：发现3个问题，其中2个严重..."

# Structured Output（直接用）
{
    "issues": [
        {"severity": "critical", "line": 42, "message": "SQL注入风险"},
        {"severity": "critical", "line": 87, "message": "未校验用户权限"},
        {"severity": "warning",  "line": 23, "message": "未处理异常"}
    ],
    "summary": {"critical": 2, "warning": 1}
}
```

在Agent系统里，Planning、Tool Selection等环节都依赖Structured Output来稳定运行。

---

## 7. Reasoning Model：会用"慢思考"的 LLM

2024-2025 年出现了专门强化推理能力的模型——它们不是更快，而是**更准**。

### 传统 LLM vs Reasoning Model

```
传统 LLM（GPT-4o、Claude 3.5）：
  用户问 → 直接输出答案
  "快思考"——适合简单问题、对话、Tool Calling

Reasoning Model（o1、o3、DeepSeek-R1、Claude 3.7 Thinking）：
  用户问 → 内部推演（不可见）→ 输出答案
  "慢思考"——适合复杂推理、数学、多步规划
```

### 什么时候用 Reasoning Model？

```
✅ 适合：
  - 复杂多步推理（数学证明、逻辑谜题）
  - 需要深度分析（代码审查、架构决策）
  - Planner 的任务分解（复杂目标 → 子任务图）
  - Reflection 环节（判断任务是否真正完成）

❌ 不适合：
  - 简单对话（浪费钱和时间）
  - Tool Calling（增加延迟，传统模型够用）
  - 需要低延迟的场景
```

### Agent 中的使用策略

```python
def select_model(task_complexity: str) -> str:
    """根据任务复杂度选择模型"""
    match task_complexity:
        case "simple":     # 查天气、简单问答
            return "gpt-4o-mini"          # 便宜、快
        case "moderate":   # 常规 Tool Calling
            return "gpt-4o"               # 平衡
        case "complex":    # 多步规划、深度分析
            return "o1"                    # 贵但准
        case "reflection": # 反思/评估
            return "o1"                    # 需要深度判断
```

> **核心认知**：不是越强越好。一个 Agent 可以在 Planning 用 o1、在 Tool Calling 用 gpt-4o-mini、在 Reflection 用 o1——不同环节用不同模型，这是成本优化的重要手段。

---

## 8. LLM ≠ Agent

这是本节最重要的认知：

```
LLM = 大脑（能思考，但不能行动）
Agent = 大脑 + 手脚 + 环境感知 + 持续循环
```

| 维度     | LLM              | Agent        |
| -------- | ---------------- | ------------ |
| 运行方式 | 一次输入→一次输出 | 持续循环     |
| 行动能力 | 只能"说"          | 能"做"       |
| 状态     | 无状态            | 有记忆和状态 |
| 目标达成 | 被动响应          | 主动规划执行 |

---

## 实践任务

**任务1**：用 tiktoken 分析你项目中常用 prompt 的 token 数量，计算一下每次调用的成本。

**任务2**：观察一个你用过的 AI 产品，判断它是纯 LLM 还是 Agent —— 依据是什么？

**任务3**：画出 LLM 的输入/输出结构：
```
[System Prompt] + [History] + [User Input]
        ↓
      LLM
        ↓
 [Text Response] 或 [Function Call]
```

---

## 下一步

→ [02-Agent生命周期.md](./02-Agent生命周期.md)
